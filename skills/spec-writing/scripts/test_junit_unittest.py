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
    def run_fixture(self, source, report='report.xml', arguments=(), jobs=1):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'test_sample.py').write_text(source)
        result = subprocess.run([sys.executable, '-B', str(RUNNER), '--report', report, '--jobs', str(jobs),
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

    def test_fallback_packaged_test_imports_a_repository_root_module(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'shared_values.py').write_text('VALUE = 5\n')
            package = root / 'project' / 'tests'
            package.mkdir(parents=True)
            (package / '__init__.py').write_text('')
            (package / 'test_sample.py').write_text(
                'import unittest\nfrom shared_values import VALUE\n'
                'class Suite(unittest.TestCase):\n'
                ' def test_value(self): self.assertEqual(VALUE, 5)\n')
            (root / 'selectors.json').write_text(json.dumps(['project/tests/test_sample.py::Suite::test_value']))
            result = subprocess.run([sys.executable, '-B', str(RUNNER), '--report', 'report.xml',
                                     '--selectors-file', 'selectors.json'], cwd=root,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = ET.parse(root / 'report.xml').getroot()
            self.assertEqual((report.get('tests'), report.get('failures'), report.get('errors')), ('1', '0', '0'))

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

    def test_fallback_relative_and_absolute_imports_share_helper_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'project' / 'tests'
            package.mkdir(parents=True)
            (package / '__init__.py').write_text('')
            (package / 'helper.py').write_text('class Payload: pass\n')
            (package / 'test_sample.py').write_text(
                'import unittest\nfrom .helper import Payload\n'
                'from tests.helper import Payload as AbsolutePayload\n'
                'class Suite(unittest.TestCase):\n'
                ' def test_identity(self): self.assertIs(Payload, AbsolutePayload)\n')
            (root / 'selectors.json').write_text(json.dumps(['project/tests/test_sample.py::Suite::test_identity']))
            result = subprocess.run([sys.executable, '-B', str(RUNNER), '--report', 'report.xml',
                                     '--selectors-file', 'selectors.json'], cwd=root,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = ET.parse(root / 'report.xml').getroot()
            self.assertEqual((report.get('tests'), report.get('failures'), report.get('errors')), ('1', '0', '0'))
            self.assertEqual(report[0].get('classname'), 'tests.test_sample.Suite')

    def test_fallback_refuses_equal_package_names_in_distinct_source_roots(self):
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
            self.assertEqual(result.returncode, 2, result.stderr)
            for detail in ("tests", str(root / 'one'), str(root / 'two'), 'supply runner reports'):
                self.assertIn(detail, result.stderr)
            for name in ('one', 'two'):
                package = root / name / 'tests'
                self.assertFalse((package / 'test_sample.loaded').exists())
                self.assertFalse((package / 'test_sample.ran').exists())
    def test_parallel_preserves_output_outcomes_and_report_identities(self):
        source = ('import unittest\n'
            'class A(unittest.TestCase):\n'
            ' @classmethod\n'
            ' def setUpClass(cls): cls.value = 1\n'
            ' def test_pass(self): print("ordinary output"); self.assertEqual(self.value, 1)\n'
            ' def test_subtests(self):\n'
            '  for i in (0,1):\n'
            '   with self.subTest(i=i): self.assertEqual(i,0)\n'
            'class B(unittest.TestCase):\n'
            ' @unittest.skip("synthetic skip")\n'
            ' def test_skip(self): pass\n'
            ' @unittest.expectedFailure\n'
            ' def test_expected(self): self.fail("expected")\n'
            ' def test_error(self): raise ValueError("synthetic error")\n'
            'class C(unittest.TestCase):\n'
            ' @classmethod\n'
            ' def setUpClass(cls): raise ValueError("fixture error")\n'
            ' def test_never(self): pass\n')
        serial, root = self.run_fixture(source, arguments=('-v', '-b'))
        parallel = subprocess.run([sys.executable, '-B', str(RUNNER), '--report', 'parallel.xml',
                                   '--jobs', '2', 'discover', '-s', '.', '-v', '-b'], cwd=root,
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
        self.assertEqual(serial.returncode, parallel.returncode)
        self.assertEqual(serial.stdout, parallel.stdout)
        # unittest's elapsed duration is the only changing console summary.
        import re
        normalize = lambda text: re.sub(r'Ran (\d+) tests in [\d.]+s', r'Ran \1 tests', text)
        self.assertEqual(normalize(serial.stderr), normalize(parallel.stderr))
        reports = [ET.parse(root / name).getroot() for name in ('report.xml', 'parallel.xml')]
        for report in reports:
            report.attrib.pop('time')
            for case in report:
                case.attrib.pop('time')
        self.assertEqual(ET.tostring(reports[0]), ET.tostring(reports[1]))

    def test_parallel_workers_keep_class_fixtures_and_isolate_environment(self):
        result, root = self.run_fixture('import os, pathlib, unittest, multiprocessing\n'
            'parent = os.getpid()\n'
            'barrier = multiprocessing.get_context("fork").Barrier(2)\n'
            'class A(unittest.TestCase):\n'
            ' @classmethod\n'
            ' def setUpClass(cls):\n'
            '  assert os.getpid() != parent\n'
            '  assert "SYNTHETIC_CLASS_ENV" not in os.environ\n'
            '  os.environ["SYNTHETIC_CLASS_ENV"] = cls.__name__\n'
            '  cls.pid = os.getpid()\n'
            '  pathlib.Path(cls.__name__).write_text(str(cls.pid))\n'
            '  barrier.wait(timeout=2)\n'
            ' def test_a(self): self.assertEqual(os.environ["SYNTHETIC_CLASS_ENV"], type(self).__name__)\n'
            ' def test_b(self): self.assertEqual(os.getpid(), self.pid)\n'
            'class B(A): pass\n', jobs=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual((root / 'A').read_text(), (root / 'B').read_text())
        self.assertEqual(ET.parse(root / 'report.xml').getroot().get('tests'), '4')

    def test_parallel_worker_crash_and_invalid_jobs_fail_visibly(self):
        source = ('import os, pathlib, unittest\n'
            'class A(unittest.TestCase):\n'
            ' def test_exit(self):\n'
            '  pathlib.Path("test-effect").touch()\n'
            '  if not pathlib.Path("recovered").exists(): os._exit(3)\n'
            'class B(unittest.TestCase):\n def test_pass(self): pass\n')
        result, root = self.run_fixture('import unittest\n'
            'class Previous(unittest.TestCase):\n def test_old_pass(self): pass\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        previous_report = (root / 'report.xml').read_bytes()
        (root / 'test_sample.py').write_text(source)
        command = [sys.executable, '-B', str(RUNNER), '--report', 'report.xml',
                   '--jobs', '2', 'discover', '-s', '.']
        result = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('terminated abruptly', result.stderr)
        self.assertEqual((root / 'report.xml').read_bytes(), previous_report)
        self.assertEqual(ET.parse(root / 'report.xml').getroot()[0].get('name'), 'test_old_pass')
        self.assertTrue((root / 'test-effect').exists())
        (root / 'recovered').touch()
        result = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = ET.parse(root / 'report.xml').getroot()
        self.assertEqual([report.get(key) for key in ('tests', 'failures', 'errors')], ['2', '0', '0'])
        self.assertEqual([case.get('name') for case in report], ['test_exit', 'test_pass'])
        result, root = self.run_fixture(source, jobs=2)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse((root / 'report.xml').exists())
        result, root = self.run_fixture('# no tests\n', jobs=0)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('positive integer', result.stderr)
        self.assertFalse((root / 'report.xml').exists())

    @unittest.skipUnless(hasattr(unittest.TestResult, 'addDuration'), 'native durations require Python 3.12+')
    def test_parallel_preserves_requested_duration_summary(self):
        source = ('import unittest\n'
            'class A(unittest.TestCase):\n def test_pass(self): pass\n'
            'class B(unittest.TestCase):\n def test_pass(self): pass\n')
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                result, _ = self.run_fixture(source, jobs=jobs, arguments=('--durations', '0', '-v'))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Slowest test durations', result.stderr)
                summary = result.stderr.split('Slowest test durations', 1)[1]
                for name in ('A', 'B'):
                    self.assertIn(f'test_pass (test_sample.{name}.test_pass)', summary)

    def test_parallel_custom_suite_hooks_and_module_fixtures_are_preserved(self):
        source = ('import unittest\n'
                  'class A(unittest.TestCase):\n def test_pass(self): pass\n'
                  'class B(unittest.TestCase):\n def test_pass(self): pass\n'
                  'class Hook(unittest.TestSuite):\n'
                  ' def run(self, result, debug=False):\n'
                  '  print("hook start")\n'
                  '  super().run(result, debug)\n'
                  '  print("hook end")\n'
                  '  return result\n'
                  'def load_tests(loader, tests, pattern): return Hook(tests)\n')
        for extra in ('', 'def setUpModule(): print("module setup")\ndef tearDownModule(): print("module teardown")\n'):
            with self.subTest(module_fixtures=bool(extra)):
                result, root = self.run_fixture(source + extra, jobs=2)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.count('hook start'), 1)
                self.assertEqual(result.stdout.count('hook end'), 1)
                if extra:
                    self.assertEqual(result.stdout.count('module setup'), 1)
                    self.assertEqual(result.stdout.count('module teardown'), 1)
                self.assertEqual(ET.parse(root / 'report.xml').getroot().get('tests'), '2')

    def test_single_custom_suite_receives_the_job_allowance(self):
        source = ('import unittest\n'
                  'class A(unittest.TestCase):\n def test_pass(self): pass\n'
                  'class Hook(unittest.TestSuite):\n'
                  ' def run(self, result, debug=False):\n'
                  '  print("jobs", getattr(result, "jobs", 1))\n'
                  '  return super().run(result, debug)\n'
                  'def load_tests(loader, tests, pattern): return Hook(tests)\n')
        for jobs in (1, 3):
            with self.subTest(jobs=jobs):
                result, _ = self.run_fixture(source, jobs=jobs)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f'jobs {jobs}', result.stdout)

    def test_parallel_executes_adjacent_custom_suites_including_failures(self):
        source = ('import unittest\n'
                  'class A(unittest.TestCase):\n'
                  ' def test_pass(self): pass\n'
                  ' def test_fail(self): self.fail("second custom suite")\n'
                  'class B(unittest.TestCase):\n def test_pass(self): pass\n'
                  'class Hook(unittest.TestSuite):\n'
                  ' def run(self, result, debug=False):\n'
                  '  print("hook")\n'
                  '  return super().run(result, debug)\n'
                  'def load_tests(loader, tests, pattern):\n'
                  ' return unittest.TestSuite([Hook([A("test_pass")]),\n'
                  '                            Hook([A("test_fail")]), B("test_pass")])\n')
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                result, root = self.run_fixture(source, jobs=jobs)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout.count('hook'), 2)
                report = ET.parse(root / 'report.xml').getroot()
                self.assertEqual([report.get(key) for key in ('tests', 'failures', 'errors')], ['3', '1', '0'])

    def test_parallel_failfast_stops_in_serial_order(self):
        result, root = self.run_fixture('import pathlib, unittest\n'
            'class A(unittest.TestCase):\n def test_fail(self): self.fail("stop here")\n'
            'class B(unittest.TestCase):\n def test_never(self): pathlib.Path("unexpected").touch()\n',
            jobs=2, arguments=('-f', '-b', '-v'))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((root / 'unexpected').exists())
        self.assertEqual(ET.parse(root / 'report.xml').getroot().get('tests'), '1')

    def test_parallel_selected_dynamic_modules_preserve_repeated_cases(self):
        result, root = self.run_fixture('import unittest\n'
            'class A(unittest.TestCase):\n def test_pass(self): pass\n'
            'class B(unittest.TestCase):\n def test_pass(self): pass\n')
        import json
        (root / 'selectors.json').write_text(json.dumps(['test_sample.py::A::test_pass', 'test_sample.py::B::test_pass']))
        result = subprocess.run([sys.executable, '-B', str(RUNNER), '--jobs', '2', '--report', 'selected.xml',
                                 '--selectors-file', 'selectors.json'], cwd=root, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ET.parse(root / 'selected.xml').getroot().get('tests'), '2')
        result, root = self.run_fixture('import unittest\n'
            'class A(unittest.TestCase):\n def test_pass(self): pass\n'
            'class B(unittest.TestCase):\n def test_pass(self): pass\n'
            'def load_tests(loader, tests, pattern):\n'
            ' case = A("test_pass")\n'
            ' return unittest.TestSuite([case, case, B("test_pass")])\n', jobs=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([case.get('name') for case in ET.parse(root / 'report.xml').getroot()], ['test_pass'] * 3)

    def test_parallel_captures_binary_streams_and_native_descriptors(self):
        result, _ = self.run_fixture('import os, sys, unittest\n'
            'class A(unittest.TestCase):\n'
            ' def test_output(self):\n'
            '  sys.stdout.buffer.write(b"binary stream\\n"); sys.stdout.flush()\n'
            '  os.write(1, b"native stdout\\n")\n'
            '  os.write(2, b"native stderr\\n")\n'
            'class B(unittest.TestCase):\n'
            ' def test_output(self): print("second class")\n', jobs=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'binary stream\nnative stdout\nsecond class\n')
        self.assertIn('native stderr', result.stderr)

    def test_parallel_preserves_non_utf8_output_bytes(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'test_sample.py').write_text('import os, unittest\n'
            'class A(unittest.TestCase):\n'
            ' def test_output(self): os.write(1, bytes([255])); os.write(2, bytes([254]))\n'
            'class B(unittest.TestCase):\n def test_pass(self): pass\n')
        result = subprocess.run([sys.executable, '-B', str(RUNNER), '--jobs', '2', '--report', 'report.xml',
                                 'discover', '-s', '.'], cwd=root, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, bytes([255]))
        self.assertIn(bytes([254]), result.stderr)

    def test_parallel_noncontiguous_classes_keep_fixture_reentry_order(self):
        result, root = self.run_fixture('import unittest\n'
            'class A(unittest.TestCase):\n'
            ' count = 0\n'
            ' @classmethod\n'
            ' def setUpClass(cls): cls.count += 1\n'
            ' def test_first(self): self.assertEqual(self.count, 1)\n'
            ' def test_second(self): self.assertEqual(self.count, 2)\n'
            'class B(unittest.TestCase):\n def test_pass(self): pass\n'
            'def load_tests(loader, tests, pattern):\n'
            ' return unittest.TestSuite([A("test_first"), B("test_pass"), A("test_second")])\n', jobs=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ET.parse(root / 'report.xml').getroot().get('tests'), '3')

    def test_catch_break_keeps_native_serial_process(self):
        result, _ = self.run_fixture('import os, unittest\n'
            'parent = os.getpid()\n'
            'class A(unittest.TestCase):\n'
            ' def test_process(self): self.assertEqual(os.getpid(), parent)\n'
            'class B(A): pass\n', jobs=2, arguments=('--catch',))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_parallel_runs_fork_inherited_local_classes_and_callbacks(self):
        result, root = self.run_fixture('import os, unittest\n'
            'def load_tests(loader, tests, pattern):\n'
            ' parent = os.getpid()\n'
            ' class Local(unittest.TestCase):\n'
            '  def test_pass(self): self.assertNotEqual(os.getpid(), parent)\n'
            ' def callback(): assert os.getpid() != parent\n'
            ' return unittest.TestSuite([Local("test_pass"), unittest.FunctionTestCase(callback)])\n', jobs=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ET.parse(root / 'report.xml').getroot().get('tests'), '2')

    def test_parallel_preserves_console_encoding(self):
        import os
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'test_sample.py').write_text('import unittest\n'
            'class A(unittest.TestCase):\n def test_output(self): print("caf\u00e9")\n'
            'class B(unittest.TestCase):\n def test_pass(self): pass\n')
        result = subprocess.run([sys.executable, '-B', str(RUNNER), '--jobs', '2', '--report', 'report.xml',
                                 'discover', '-s', '.'], cwd=root, stdin=subprocess.DEVNULL,
                                env=dict(os.environ, PYTHONIOENCODING='latin-1'), capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'caf\xe9\n')


    def test_fallback_jobs_keeps_one_process_and_loads_each_file_once(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'project' / 'tests'
            package.mkdir(parents=True)
            (package / '__init__.py').write_text('')
            (root / 'shared_values.py').write_text('VALUE = 5\n')
            (package / 'test_sample.py').write_text(
                'import os, pathlib, unittest\n'
                'from shared_values import VALUE\n'
                'import tests.test_sample as same_module\n'
                'loaded_pid = os.getpid()\n'
                'marker = pathlib.Path("loads")\n'
                'with marker.open("a") as stream: stream.write("loaded\\n")\n'
                'class A(unittest.TestCase):\n'
                ' def test_identity(self):\n'
                '  self.assertEqual(os.getpid(), loaded_pid)\n'
                '  self.assertEqual(same_module.loaded_pid, loaded_pid)\n'
                '  self.assertEqual(VALUE, 5)\n'
                'class B(A): pass\n')
            labels = ['project/tests/test_sample.py::A::test_identity',
                      'project/tests/test_sample.py::B::test_identity']
            for name in ('one', 'two'):
                standalone = root / name
                standalone.mkdir()
                (standalone / 'test_sample.py').write_text(
                    'import os, unittest\n'
                    'loaded_pid = os.getpid()\n'
                    'class Suite(unittest.TestCase):\n'
                    ' def test_identity(self): self.assertEqual(os.getpid(), loaded_pid)\n')
                labels.append(name + '/test_sample.py::Suite::test_identity')
            (root / 'selectors.json').write_text(json.dumps(labels))
            result = subprocess.run([sys.executable, '-B', str(RUNNER), '--jobs', '4',
                '--report', 'report.xml', '--selectors-file', 'selectors.json'], cwd=root,
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'loads').read_text(), 'loaded\n')
            report = ET.parse(root / 'report.xml').getroot()
            self.assertEqual(report.get('tests'), '4')
            self.assertEqual([case.get('classname') for case in report],
                ['tests.test_sample.A', 'tests.test_sample.B',
                 '_selector_1.Suite', '_selector_2.Suite'])
