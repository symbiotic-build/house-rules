#!/usr/bin/env python3
"""Audit acceptance selectors from JUnit reports, or one batch per runner."""
import argparse
from fnmatch import fnmatchcase
import glob
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import spec_docs as s


class ReportError(ValueError):
    """A report or runner invocation needs a caller-visible repair."""


def read_reports(root, patterns):
    """Parse each supplied report once, refusing malformed or absent inputs."""
    files = set()
    for pattern in patterns:
        matches = glob.glob(str(root / pattern), recursive=True)
        if not matches:
            raise ReportError(f'no report matches {pattern!r}; run the normal tests with JUnit output or fix --report')
        files.update(matches)
    cases = []
    for path in sorted(files):
        try:
            tree = ET.parse(path)
            if tree.getroot().tag not in ('testsuite', 'testsuites'):
                raise ValueError('expected testsuite or testsuites root')
            for case in tree.iter('testcase'):
                if not case.get('name') or not case.get('classname'):
                    raise ValueError('testcase requires name and classname')
                cases.append((dict(case.attrib), any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped'))))
        except (OSError, ET.ParseError, ValueError) as exc:
            raise ReportError(f'invalid JUnit report {path}: {exc}; regenerate it from the normal test run') from exc
    return cases


def match_case(cases, label, runner):
    """Resolve one selector with its runner's declared testcase identity rule."""
    path, selector = label.split('::', 1)
    python_runner = runner['kind'] == 'unittest'
    if python_runner:
        classname, separator, method = selector.rpartition('::')
        if not separator:
            return 'missing'
        classname = classname.replace('::', '.')
        qualified_class = path[:-3].replace('/', '.') + '.' + classname
    else:
        expected = {key: value.format(file=path, selector=selector) for key, value in runner['testcase'].items()}
    found = False
    for attrs, failed in cases:
        if python_runner:
            actual_class = attrs['classname']
            file = attrs.get('file')
            matched = attrs['name'] == method and (
                (file is not None and file.removeprefix('./') == path and
                 (actual_class == classname or actual_class.endswith('.' + classname))) or
                (file is None and actual_class == qualified_class))
        else:
            matched = all((attrs.get(key, '').removeprefix('./') if key == 'file' else attrs.get(key)) == value
                          for key, value in expected.items())
        if matched:
            if failed:
                return 'failing'
            found = True
    return 'passed' if found else 'missing'


def run_batch(root, labels, runner, timeout_seconds):
    """Invoke one runner with all its selectors and parse its temporary report."""
    with tempfile.TemporaryDirectory(prefix='selector-audit-') as directory:
        report = Path(directory) / 'results.xml'
        if runner['kind'] == 'unittest':
            selection = Path(directory) / 'selectors.json'
            selection.write_text(json.dumps(labels))
            command = [sys.executable, '-B', str(Path(__file__).with_name('junit_unittest.py').resolve()),
                       '--report', str(report), '--selectors-file', str(selection)]
        elif 'batch' in runner:
            command = []
            for argument in runner['batch']:
                command.extend(labels if argument == '{selectors}' else [argument.format(report=str(report))])
        else:
            raise ReportError(f"runner {runner['pattern']} needs reports or a batch command; declare one in test_runners")
        started = time.perf_counter()
        try:
            with subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, start_new_session=True) as child:
                try:
                    stdout, stderr = child.communicate(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.stdout.close()
                    child.stderr.close()
                    child.wait()
                    print(f'batch exceeded {timeout_seconds} seconds; output pipes closed', flush=True)
                    return dict.fromkeys(labels, 'failing')
            if child.returncode:
                print(f'batch exited {child.returncode}\n{stdout}{stderr}', flush=True)
                return dict.fromkeys(labels, 'failing')
            cases = read_reports(root, [str(report)])
            return {label: match_case(cases, label, runner) for label in labels}
        except OSError as exc:
            print(f'cannot start batch runner: {exc}; fix its executable', flush=True)
            return dict.fromkeys(labels, 'failing')
        finally:
            print(f'batch runtime: {time.perf_counter() - started:.3f}s', flush=True)


def audit(corpus, root, timeout_seconds=300, reports=None):
    """Match report evidence or batch each runner once after structural checking."""
    diagnostics = s.Diagnostics(corpus.diagnostics.items[:])
    citations = []
    for declaration in corpus.declarations.values():
        if declaration['kind'] == 'Acceptance test':
            requirements = sorted(s.declaration_targets(corpus, declaration, 'Requirements'))
            print(f"acceptance {declaration['id']} requirements={','.join(requirements)}", flush=True)
            if 'Implementation' in declaration['fields']:
                s.check_implementation(corpus, declaration, diagnostics)
                citations.extend(link.label for link in declaration['fields']['Implementation'][1])
    if diagnostics.errors:
        raise s.SpecDocsError(diagnostics)
    groups = {}
    runners = corpus.manifest.get('test_runners', [])
    for label in dict.fromkeys(citations):
        path = label.split('::', 1)[0]
        index = next((i for i, entry in enumerate(runners) if fnmatchcase(path, entry['pattern'])), -1)
        groups.setdefault(index, []).append(label)
    results = {}
    # Parse shared CLI reports only once, even with several declared runners.
    cases = read_reports(root, reports) if reports else None
    for index, labels in groups.items():
        runner = runners[index] if index >= 0 else dict(kind='unittest')
        supported = [label for label in labels if (root / label.split('::', 1)[0]).is_file()
                     and (index >= 0 or label.split('::', 1)[0].endswith('.py'))]
        results.update(dict.fromkeys(set(labels) - set(supported), 'missing'))
        if cases is not None or runner.get('reports'):
            evidence = cases if cases is not None else read_reports(root, runner['reports'])
            results.update({label: match_case(evidence, label, runner) for label in supported})
        elif supported:
            results.update(run_batch(root, supported, runner, timeout_seconds))
    for label in citations:
        print(f'{results[label]}: {label}', flush=True)
    counts = tuple(sum(results[label] == outcome for label in citations) for outcome in ('passed', 'missing', 'failing'))
    print('selector audit: %d passed, %d missing, %d failing' % counts, flush=True)
    return counts


def main():
    """Read report paths from the CLI or the selected runner declaration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--fixture', action='store_true')
    parser.add_argument('--report', action='append', help='JUnit file or glob; repeat to combine reports.')
    parser.add_argument('--timeout-seconds', type=float, default=300, help='Per-batch runaway ceiling (default: 300).')
    args = parser.parse_args()
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error('--timeout-seconds must be positive')
    root = args.root.resolve()
    try:
        corpus = s.load_corpus(s.Snapshot.from_git(root, fixture=args.fixture))
        _, missing, failing = audit(corpus, root, args.timeout_seconds, args.report)
        return int(bool(missing or failing))
    except s.SpecDocsError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except ReportError as exc:
        print(f'selector audit: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
