#!/usr/bin/env python3
"""Run ordinary unittest arguments and write a standard-library JUnit report."""
import argparse
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import time
from types import ModuleType
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
    suite = unittest.TestSuite()
    for label in dict.fromkeys(labels):
        path, selector = label.split('::', 1)
        target = root / path
        if path not in modules:
            sys.path[:0] = [str(target.parent), str(root)]
            package_root = target.parent
            parts = [target.stem]
            while (package_root / '__init__.py').is_file():
                parts.insert(0, package_root.name)
                package_root = package_root.parent
            try:
                if len(parts) > 1:
                    # Scope package identities by source root, preserving relative imports.
                    if package_root not in package_roots:
                        name = '_selector_root_' + str(len(package_roots))
                        namespace = ModuleType(name)
                        namespace.__path__ = [str(package_root)]
                        sys.modules[name] = namespace
                        package_roots[package_root] = name
                    module = importlib.import_module('.'.join([package_roots[package_root], *parts]))
                else:
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


def main(argv=None):
    """Accept report options followed by the unchanged unittest command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--selectors-file', type=Path, help=argparse.SUPPRESS)
    args, unittest_args = parser.parse_known_args(argv)
    class ReportingRunner(unittest.TextTestRunner):
        resultclass = JUnitResult

        def run(self, test):
            result = super().run(test)
            result.write_report(args.report)
            return result

    try:
        if args.selectors_file:
            suite = selected_suite(Path.cwd(), json.loads(args.selectors_file.read_text()))
            result = ReportingRunner(verbosity=2).run(suite)
            return int(not result.wasSuccessful())
        # Passing the runner class lets unittest apply verbosity, failfast, buffer
        # and its other native options. TestProgram owns the native exit status.
        unittest.TestProgram(module=None, argv=['unittest', *unittest_args], testRunner=ReportingRunner)
    except (OSError, ValueError) as exc:
        print(f'JUnit runner: {exc}; fix the report path or unittest inputs and rerun', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
