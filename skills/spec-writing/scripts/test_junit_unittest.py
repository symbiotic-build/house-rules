"""Exercise the dependency-free runner through its real command line."""
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

RUNNER = Path(__file__).with_name('junit_unittest.py').resolve()


class JUnitRunnerTests(unittest.TestCase):
    def run_fixture(self, source, report='report.xml', arguments=()):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'test_sample.py').write_text(source)
        result = subprocess.run([sys.executable, '-B', str(RUNNER), '--report', report,
                                 'discover', '-s', '.', '-p', 'test_sample.py', *arguments], cwd=root,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
        return result, root

    def test_discovery_report_preserves_outcomes(self):
        result, root = self.run_fixture('import unittest\nclass Suite(unittest.TestCase):\n'
            ' def test_pass(self): pass\n'
            ' def test_fail(self): self.fail("synthetic failure")\n'
            ' def test_error(self): raise ValueError("synthetic error")\n'
            ' @unittest.skip("synthetic skip")\n'
            ' def test_skip(self): pass\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        report = ET.parse(root / 'report.xml').getroot()
        self.assertEqual([report.get(key) for key in ('tests', 'failures', 'errors', 'skipped')], ['4', '1', '1', '1'])
        for case in report:
            self.assertEqual(case.get('file'), 'test_sample.py')
            self.assertEqual(case.get('classname'), 'test_sample.Suite')
            self.assertGreaterEqual(float(case.get('time')), 0)
        cases = {case.get('name'): case for case in report}
        self.assertIsNotNone(cases['test_fail'].find('failure'))
        self.assertIsNotNone(cases['test_error'].find('error'))
        self.assertIsNotNone(cases['test_skip'].find('skipped'))
        self.assertEqual(list(cases['test_pass']), [])
        result, root = self.run_fixture('import unittest\nclass Suite(unittest.TestCase):\n def test_pass(self): pass\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ET.parse(root / 'report.xml').getroot().get('tests'), '1')

    def test_subtests_fixture_errors_and_write_errors_are_visible(self):
        result, root = self.run_fixture('import unittest\nclass Suite(unittest.TestCase):\n'
            ' def test_subtests(self):\n'
            '  for i in (0,1):\n'
            '   with self.subTest(i=i): self.assertEqual(i,0)\n'
            'class Broken(unittest.TestCase):\n'
            ' @classmethod\n'
            ' def setUpClass(cls): raise ValueError("synthetic fixture error")\n'
            ' def test_never_runs(self): pass\n')
        self.assertEqual(result.returncode, 1, result.stderr)
        report = ET.parse(root / 'report.xml').getroot()
        self.assertEqual(report.get('errors'), '1')
        self.assertEqual(report.get('failures'), '1')
        self.assertIn('synthetic fixture error', ET.tostring(report).decode())
        result, _ = self.run_fixture('import unittest\nclass Suite(unittest.TestCase):\n def test_pass(self): pass\n', report='test_sample.py/report.xml')
        self.assertEqual(result.returncode, 2)
        self.assertIn('fix the report path', result.stderr)

    def test_unittest_options_and_empty_discovery_keep_native_behavior(self):
        result, root = self.run_fixture('import unittest\nclass Suite(unittest.TestCase):\n'
            ' def test_a_fail(self): self.fail("synthetic failure")\n'
            ' def test_b_pass(self): print("buffered output")\n', arguments=('-f', '-b', '-v'))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(ET.parse(root / 'report.xml').getroot().get('tests'), '1')
        self.assertIn('test_a_fail', result.stderr)
        self.assertNotIn('buffered output', result.stdout)
        result, root = self.run_fixture('# no tests\n')
        native = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', '.'],
                                cwd=root, stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, native.returncode)
        self.assertEqual(ET.parse(root / 'report.xml').getroot().get('tests'), '0')

    def test_repeated_test_object_records_each_execution(self):
        result, root = self.run_fixture('import unittest\nclass Suite(unittest.TestCase):\n'
            ' def test_pass(self): pass\n'
            'def load_tests(loader, tests, pattern):\n'
            ' case = Suite("test_pass")\n'
            ' return unittest.TestSuite([case, case])\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Ran 2 tests', result.stderr)
        report = ET.parse(root / 'report.xml').getroot()
        self.assertEqual(report.get('tests'), '2')
        self.assertEqual([case.get('name') for case in report], ['test_pass', 'test_pass'])

    def test_fallback_packaged_test_imports_its_package_by_absolute_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'project' / 'tests'
            package.mkdir(parents=True)
            (package / '__init__.py').write_text('')
            (package / 'helper.py').write_text('VALUE = 7\n')
            (package / 'test_sample.py').write_text(
                'import unittest\nfrom tests.helper import VALUE\n'
                'class Suite(unittest.TestCase):\n'
                ' def test_value(self): self.assertEqual(VALUE, 7)\n')
            (root / 'selectors.json').write_text(json.dumps(['project/tests/test_sample.py::Suite::test_value']))
            result = subprocess.run([sys.executable, '-B', str(RUNNER), '--report', 'report.xml',
                                     '--selectors-file', 'selectors.json'], cwd=root,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = ET.parse(root / 'report.xml').getroot()
            self.assertEqual((report.get('tests'), report.get('failures'), report.get('errors')), ('1', '0', '0'))

    def test_fallback_keeps_equal_package_names_in_distinct_source_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            labels = []
            for name in ('one', 'two'):
                package = root / name / 'tests'
                package.mkdir(parents=True)
                (package / '__init__.py').write_text('')
                (package / 'helper.py').write_text(f'VALUE = {name!r}\n')
                (package / 'test_sample.py').write_text(
                    'import unittest\nfrom pathlib import Path\nfrom .helper import VALUE\n'
                    'loaded = Path(__file__).with_suffix(".loaded")\n'
                    'with loaded.open("a") as record: record.write("loaded\\n")\n'
                    'class Suite(unittest.TestCase):\n'
                    ' def test_first(self):\n'
                    f'  self.assertEqual(VALUE, {name!r})\n'
                    '  with Path(__file__).with_suffix(".ran").open("a") as record: record.write("first\\n")\n'
                    ' def test_second(self): pass\n')
                labels.extend(f'{name}/tests/test_sample.py::Suite::{method}'
                              for method in ('test_first', 'test_second', 'test_first'))
            (root / 'selectors.json').write_text(json.dumps(labels))
            result = subprocess.run([sys.executable, '-B', str(RUNNER), '--report', 'report.xml',
                                     '--selectors-file', 'selectors.json'], cwd=root,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = ET.parse(root / 'report.xml').getroot()
            self.assertEqual(report.get('tests'), '4')
            classes = {case.get('classname') for case in report}
            self.assertEqual(len(classes), 2)
            for name in ('one', 'two'):
                package = root / name / 'tests'
                self.assertEqual((package / 'test_sample.loaded').read_text(), 'loaded\n')
                self.assertEqual((package / 'test_sample.ran').read_text(), 'first\n')
                self.assertEqual(sum(case.get('file') == f'{name}/tests/test_sample.py' for case in report), 2)
