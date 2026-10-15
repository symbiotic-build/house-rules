"""Small executable regressions for the acceptance-selector audit."""
from contextlib import redirect_stdout
import io
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
