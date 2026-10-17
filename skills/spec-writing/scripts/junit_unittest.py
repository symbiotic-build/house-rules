#!/usr/bin/env python3
"""Run ordinary unittest arguments and write a standard-library JUnit report."""
import argparse
import importlib
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
import itertools
import multiprocessing
import os
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import time
import tempfile
import unittest
import xml.etree.ElementTree as ET


class JUnitResult(unittest.TextTestResult):
    """Preserve unittest output while collecting one XML case per test."""

    def __init__(self, *args, root=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = Path(root or Path.cwd()).resolve()
        self.cases = []
        self.current = None
        self.started = None

    def case(self, test):
        """Return the report element, including errors outside startTest."""
        if self.current is None or self.current[0] is not test:
            classname, _, name = test.id().rpartition('.')
            attrs = dict(classname=classname or type(test).__name__, name=name, time='0')
            if isinstance(test, unittest.TestCase):
                path = Path(inspect.getfile(type(test))).resolve()
                attrs['file'] = path.relative_to(self.root).as_posix() if path.is_relative_to(self.root) else path.as_posix()
            case = ET.Element('testcase', attrs)
            self.cases.append(case)
            self.current = test, case
        return self.current[1]

    def startTest(self, test):
        super().startTest(test)
        self.case(test)
        self.started = time.perf_counter()

    def stopTest(self, test):
        self.case(test).set('time', f'{time.perf_counter() - self.started:.6f}')
        self.current = None
        self.started = None
        super().stopTest(test)

    def problem(self, test, tag, message):
        """Append a visible outcome without losing previous subtest failures."""
        ET.SubElement(self.case(test), tag, message=message.splitlines()[-1] if message else tag).text = message

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.problem(test, 'failure', self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.problem(test, 'error', self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.problem(getattr(test, 'test_case', test), 'skipped', reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.problem(test, 'skipped', 'expected failure: ' + self._exc_info_to_string(err, test))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.problem(test, 'failure', 'unexpected success')

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            self.problem(test, 'failure' if issubclass(err[0], test.failureException) else 'error',
                         str(subtest) + '\n' + self._exc_info_to_string(err, test))

    def write_report(self, path):
        """Write a rebuildable report, failing visibly on filesystem errors."""
        cases = self.cases
        suite = ET.Element('testsuite', tests=str(len(cases)),
                           failures=str(sum(case.find('failure') is not None for case in cases)),
                           errors=str(sum(case.find('error') is not None for case in cases)),
                           skipped=str(sum(case.find('skipped') is not None for case in cases)),
                           time=f'{sum(float(case.get("time")) for case in cases):.6f}')
        suite.extend(cases)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(suite).write(path, encoding='utf-8', xml_declaration=True)


def selected_suite(root, labels):
    """Load cited Python files once and combine their selected tests in one suite."""
    modules = {}
    package_roots = {}
    locations = {}
    # Resolve the whole batch before importing: neither side of a package-name
    # conflict can safely use Python's single native module identity.
    for label in dict.fromkeys(labels):
        path = label.split('::', 1)[0]
        if path in locations:
            continue
        target = root / path
        package_root = target.parent
        parts = [target.stem]
        while (package_root / '__init__.py').is_file():
            parts.insert(0, package_root.name)
            package_root = package_root.parent
        if len(parts) > 1:
            previous = package_roots.setdefault(parts[0], package_root)
            if previous != package_root:
                raise ValueError(f"package '{parts[0]}' has conflicting roots '{previous}' and "
                                 f"'{package_root}'; supply runner reports")
        locations[path] = target, parts
    sys.path[:0] = [str(path) for path in dict.fromkeys([*package_roots.values(), root])]
    suite = unittest.TestSuite()
    for label in dict.fromkeys(labels):
        path, selector = label.split('::', 1)
        target, parts = locations[path]
        if path not in modules:
            try:
                if len(parts) > 1:
                    module = importlib.import_module('.'.join(parts))
                else:
                    sys.path[:0] = [str(target.parent), str(root)]
                    # Distinct names keep standalone files with equal stems separate.
                    name = '_selector_' + str(len(modules))
                    spec = importlib.util.spec_from_file_location(name, target)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[name] = module
                    spec.loader.exec_module(module)
                modules[path] = module
            except Exception as exc:
                print(f'missing: cannot load {path}: {exc}', file=sys.stderr)
                modules[path] = None
        if modules[path] is None:
            continue
        loader = unittest.TestLoader()
        try:
            selected = loader.loadTestsFromName(selector.replace('::', '.'), modules[path])
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            print(f'missing: {label}: {exc}', file=sys.stderr)
            continue
        if loader.errors or not selected.countTestCases():
            print(f'missing: {label}: ' + ('\n'.join(loader.errors) or 'empty suite'), file=sys.stderr)
        else:
            suite.addTests(selected)
    return suite



def test_cases(suite):
    """Flatten discovery while preserving order and repeated test objects."""
    for test in suite:
        if type(test) is unittest.TestSuite:
            yield from test_cases(test)
        else:
            yield test


class ReportedTest:
    """Retain unittest's description after a worker serializes a failure."""

    def __init__(self, description):
        self.description = description

    def __str__(self):
        return self.description

    def shortDescription(self):
        return None


def initialize_classes(groups, options):
    """Retain fork-inherited tests, including local classes and callbacks."""
    global worker_groups, worker_options
    worker_groups, worker_options = groups, options


def run_class(index):
    """Run one class in an isolated process and return output and outcomes."""
    tests, options = worker_groups[index], worker_options
    with tempfile.TemporaryFile(mode='w+', encoding=sys.stdout.encoding or 'utf-8',
                                errors=sys.stdout.errors or 'strict') as stdout, \
            tempfile.TemporaryFile(mode='w+', encoding=sys.stderr.encoding or 'utf-8',
                                   errors=sys.stderr.errors or 'backslashreplace') as stderr:
        stdout.reconfigure(line_buffering=getattr(sys.stdout, 'line_buffering', False),
                           write_through=getattr(sys.stdout, 'write_through', False))
        stderr.reconfigure(line_buffering=getattr(sys.stderr, 'line_buffering', False),
                           write_through=getattr(sys.stderr, 'write_through', False))
        original_fds = os.dup(1), os.dup(2)
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(stdout.fileno(), 1)
        os.dup2(stderr.fileno(), 2)
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = JUnitResult(unittest.runner._WritelnDecorator(stderr), options['descriptions'], options['verbosity'], root=options['root'])
                result.buffer = options['buffer']
                result.tb_locals = options['tb_locals']
                result.startTestRun()
                try:
                    unittest.TestSuite(tests).run(result)
                finally:
                    result.stopTestRun()
                outcomes = {}
                for name in ('failures', 'errors', 'skipped', 'expectedFailures'):
                    outcomes[name] = [(result.getDescription(test), message) for test, message in getattr(result, name)]
                outcomes['unexpectedSuccesses'] = [result.getDescription(test) for test in result.unexpectedSuccesses]
                outcomes['collectedDurations'] = getattr(result, 'collectedDurations', [])
        finally:
            stdout.flush()
            stderr.flush()
            os.dup2(original_fds[0], 1)
            os.dup2(original_fds[1], 2)
            for descriptor in original_fds:
                os.close(descriptor)
        stdout.buffer.seek(0)
        stderr.buffer.seek(0)
        return result.testsRun, result.cases, outcomes, stdout.buffer.read(), stderr.buffer.read()


class ParallelSuite(unittest.TestSuite):
    """Merge class workers in discovery order through the ordinary runner."""

    def __init__(self, suite, jobs, verbosity):
        super().__init__([suite])
        self.jobs = jobs
        self.verbosity = verbosity

    def run(self, result, debug=False):
        tests = list(test_cases(self))
        # Fail-fast must stop at the same test. Module fixtures must run once,
        # including classes separated by a different module in a custom suite.
        modules = {sys.modules.get(type(test).__module__) for test in tests}
        if result.failfast or debug or any(hasattr(module, name) for module in modules
                                          for name in ('setUpModule', 'tearDownModule')):
            return super().run(result, debug)
        groups = [list(group) for _, group in itertools.groupby(tests, type)]
        if len(groups) < 2 or len({type(group[0]) for group in groups}) != len(groups):
            # A lone custom suite, such as one file's load_tests, still receives the allowance.
            previous_jobs = getattr(result, 'jobs', 1)
            result.jobs = self.jobs
            try:
                return super().run(result, debug)
            finally:
                result.jobs = previous_jobs
        # Keep custom run hooks in discovery order. Join ordinary class
        # workers before each hook; a hook can use the same class runner with
        # the full allowance, without nested pools or reserved idle workers.
        for custom, phase in itertools.groupby(groups, lambda group: isinstance(group[0], unittest.TestSuite)):
            phase = list(phase)
            if custom:
                previous_jobs = getattr(result, 'jobs', 1)
                result.jobs = self.jobs
                try:
                    for group in phase:
                        for suite in group:
                            suite.run(result, debug)
                finally:
                    result.jobs = previous_jobs
            else:
                self.run_classes(result, phase)
        return result

    def run_classes(self, result, groups):
        """Join a class phase and merge output and outcomes in discovery order."""
        options = dict(descriptions=result.descriptions, verbosity=self.verbosity,
                       root=result.root, buffer=result.buffer, tb_locals=result.tb_locals)
        # Fork retains discovery's dynamic selector modules and custom load_tests
        # objects without rediscovering tests or running a fixture in the parent.
        with ProcessPoolExecutor(max_workers=min(self.jobs, len(groups)),
                                 mp_context=multiprocessing.get_context('fork'),
                                 initializer=initialize_classes, initargs=(groups, options)) as workers:
            for count, cases, outcomes, stdout, stderr in workers.map(
                    run_class, range(len(groups))):
                result.testsRun += count
                result.cases.extend(cases)
                for name in ('failures', 'errors', 'skipped', 'expectedFailures'):
                    getattr(result, name).extend((ReportedTest(test), message) for test, message in outcomes[name])
                result.unexpectedSuccesses.extend(ReportedTest(test) for test in outcomes['unexpectedSuccesses'])
                if hasattr(result, 'collectedDurations'):
                    result.collectedDurations.extend(outcomes['collectedDurations'])
                sys.stdout.flush()
                sys.stdout.buffer.write(stdout)
                sys.stdout.flush()
                result.stream.flush()
                result.stream.stream.buffer.write(stderr)
                result.stream.flush()



def positive_jobs(value):
    """Reject worker counts that cannot execute a suite."""
    jobs = int(value)
    if jobs < 1:
        raise argparse.ArgumentTypeError('--jobs must be a positive integer')
    return jobs

def main(argv=None):
    """Accept report options followed by the unchanged unittest command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--jobs', type=positive_jobs, default=os.cpu_count() or 1,
                        help='maximum worker processes (default: CPU count); 1 runs serially')
    parser.add_argument('--selectors-file', type=Path, help=argparse.SUPPRESS)
    args, unittest_args = parser.parse_known_args(argv)
    class ReportingRunner(unittest.TextTestRunner):
        resultclass = JUnitResult

        def run(self, test):
            result = super().run(ParallelSuite(test, args.jobs, self.verbosity) if args.jobs > 1 else test)
            result.write_report(args.report)
            return result

    class ReportingProgram(unittest.TestProgram):
        def runTests(self):
            # Native catch-break stops after the current test, rather than
            # leaving already dispatched worker classes running.
            if self.catchbreak:
                args.jobs = 1
            super().runTests()

    try:
        if args.selectors_file:
            # The audit fallback stays in one serial child, independent of discovery workers.
            args.jobs = 1
            suite = selected_suite(Path.cwd(), json.loads(args.selectors_file.read_text()))
            result = ReportingRunner(verbosity=2).run(suite)
            return int(not result.wasSuccessful())
        # Passing the runner class lets unittest apply verbosity, failfast, buffer
        # and its other native options. TestProgram owns the native exit status.
        ReportingProgram(module=None, argv=['unittest', *unittest_args], testRunner=ReportingRunner)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'JUnit runner: {exc}; fix the report path or unittest inputs and rerun', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
