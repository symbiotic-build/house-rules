"""Small executable regressions for the acceptance-selector audit."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import audit_selectors as a
import spec_docs as s
from test_spec_docs import miniature, refresh, ACCEPTANCE, edit


class SelectorAuditTests(unittest.TestCase):
    def test_audit_distinguishes_pass_missing_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tests = root / 'tests'
            tests.mkdir()
            (tests / 'sample.py').write_text('import unittest\nclass Suite(unittest.TestCase):\n'
                '    def test_pass(self): pass\n'
                '    def test_fail(self): self.fail("synthetic defect")\n')
            paths = miniature()
            paths['tests/sample.py'] = (tests / 'sample.py').read_bytes()
            edit(paths, ACCEPTANCE, '**Method:** analysis.', '**Method:** test.')
            paths[ACCEPTANCE] += (b'\n**Implementation:** '
                b'[tests/sample.py::Suite::test_pass](../../tests/sample.py), '
                b'[tests/sample.py::Suite::test_absent](../../tests/sample.py), '
                b'[tests/sample.py::Suite::test_fail](../../tests/sample.py)\n')
            corpus = refresh(paths)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(a.audit(corpus, root), (1, 1, 1))
            self.assertIn('1 passed, 1 missing, 1 failing', output.getvalue())
            edit(paths, ACCEPTANCE, 'Suite::test_absent', 'Suite::test_pass')
            edit(paths, ACCEPTANCE, 'Suite::test_fail', 'Suite::test_pass')
            with redirect_stdout(io.StringIO()):
                self.assertEqual(a.audit(refresh(paths), root), (3, 0, 0))

    def test_declared_non_python_runner_reports_pass_missing_failure_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'case.spec').write_text('synthetic test input')
            (root / 'runner.sh').write_text('case "$2" in\npass) test -f "$1";;\nmissing) exit 2;;\nfail) exit 1;;\nhang) exec sleep 10;;\nesac\n')
            paths = miniature()
            manifest = json.loads(paths['docs/DOCUMENTS.json'])
            manifest['test_runners'] = [dict(pattern='*.spec', command=['sh', 'runner.sh', '{file}', '{selector}'])]
            paths['docs/DOCUMENTS.json'] = s.canonical(manifest)
            paths['case.spec'] = b'synthetic test input'
            edit(paths, ACCEPTANCE, '**Method:** analysis.', '**Method:** test.')
            paths[ACCEPTANCE] += ('\n**Implementation:** ' + ', '.join(
                f'[case.spec::{selector}](../../case.spec)' for selector in ('pass', 'missing', 'fail', 'hang')) + '\n').encode()
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(a.audit(refresh(paths), root, timeout_seconds=0.5), (1, 1, 2))
            self.assertIn('exceeded', output.getvalue())
            self.assertIn('1 passed, 1 missing, 2 failing', output.getvalue())
            (root / 'case.spec').unlink()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(a.audit(refresh(paths), root, timeout_seconds=0.5), (0, 4, 0))
