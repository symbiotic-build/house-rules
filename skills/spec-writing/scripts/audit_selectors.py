#!/usr/bin/env python3
"""Execute every declared Implementation selector; normal checking stays static."""
import argparse
import importlib.util
from fnmatch import fnmatchcase
import math
import os
import signal
from pathlib import Path
import subprocess
import sys
import time
import unittest

import spec_docs as s


def execute(root, path, selector):
    """Run one Python unittest selector, returning 2 when it cannot be loaded."""
    target = root / path
    if target.suffix != '.py' or not target.is_file():
        print(f'missing: unsupported or absent executable test file {path}')
        return 2
    sys.path[:0] = [str(target.parent), str(root)]
    spec = importlib.util.spec_from_file_location(target.stem, target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[target.stem] = module
    try:
        spec.loader.exec_module(module)
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(selector.replace('::', '.'), module)
        if loader.errors or suite.countTestCases() == 0:
            print('\n'.join(loader.errors) or 'missing: empty selector')
            return 2
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        print(f'missing: {path}::{selector}: {exc}')
        return 2
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def audit(corpus, root, timeout_seconds=30):
    """List trace links and execute every selector in isolated child processes."""
    diagnostics = s.check(corpus)
    if diagnostics.errors:
        raise s.SpecDocsError(diagnostics)
    passed = missing = failing = 0
    for declaration in corpus.declarations.values():
        if declaration['kind'] != 'Acceptance test':
            continue
        requirements = sorted(s.declaration_targets(corpus, declaration, 'Requirements'))
        print(f"acceptance {declaration['id']} requirements={','.join(requirements)}", flush=True)
        for link in declaration['fields'].get('Implementation', ('', []))[1]:
            path, selector = link.label.split('::', 1)
            started = time.monotonic()
            runner = next((entry for entry in corpus.manifest.get('test_runners', [])
                           if fnmatchcase(path, entry['pattern'])), None)
            command = ([argument.format(file=path, selector=selector)
                        for argument in runner['command']] if runner else
                       [sys.executable, '-B', str(Path(__file__).resolve()),
                        '--root', str(root), '--execute', path, selector])
            try:
                if not (root / path).is_file():
                    code, output = 2, f'missing: absent executable test file {path}'
                else:
                    with subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True, start_new_session=True) as child:
                        try:
                            stdout, stderr = child.communicate(timeout=timeout_seconds)
                            code, output = child.returncode, stdout + stderr
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid, signal.SIGKILL)
                            stdout, stderr = child.communicate()
                            code, output = 1, f'test exceeded {timeout_seconds} seconds\n' + stdout + stderr
            except OSError as exc:
                code, output = 2, f'missing: cannot start runner: {exc}'
            outcome = 'pass' if code == 0 else 'missing' if code == 2 else 'failing'
            passed += code == 0
            missing += code == 2
            failing += code not in (0, 2)
            print(f'{outcome}: {link.label} ({time.monotonic() - started:.3f}s)', flush=True)
            if code:
                print(output, flush=True)
    print(f'selector audit: {passed} passed, {missing} missing, {failing} failing', flush=True)
    return passed, missing, failing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--fixture', action='store_true')
    parser.add_argument('--timeout-seconds', type=float, default=30, help='Per-selector runaway ceiling (default: 30).')
    parser.add_argument('--execute', nargs=2, metavar=('FILE', 'SELECTOR'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        parser.error('--timeout-seconds must be positive')
    root = args.root.resolve()
    if args.execute:
        return execute(root, *args.execute)
    try:
        corpus = s.load_corpus(s.Snapshot.from_git(root, fixture=args.fixture))
        _, missing, failing = audit(corpus, root, args.timeout_seconds)
        return int(bool(missing or failing))
    except s.SpecDocsError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code


if __name__ == '__main__':
    sys.exit(main())
