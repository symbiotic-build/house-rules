"""Executable regressions for report evidence and batched selector execution."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_selectors as a
import spec_docs as s
from test_spec_docs import miniature, refresh, ACCEPTANCE, edit


class SelectorAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = ('import unittest\nclass Suite(unittest.TestCase):\n'
                       '    def test_pass(self): pass\n'
                       '    def test_fail(self): self.fail("synthetic defect")\n'
                       '    def test_error(self): raise ValueError("synthetic error")\n'
                       '    @unittest.skip("synthetic skip")\n'
                       '    def test_skip(self): pass\n')

    def corpus(self, labels, runners=None):
        paths = miniature()
        for label in labels:
            path = label.split('::', 1)[0]
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_text(self.source if path.endswith('.py') else 'synthetic input')
            paths[path] = target.read_bytes()
        if runners is not None:
            manifest = json.loads(paths['docs/DOCUMENTS.json'])
            manifest['test_runners'] = runners
            paths['docs/DOCUMENTS.json'] = s.canonical(manifest)
        edit(paths, ACCEPTANCE, '**Method:** analysis.', '**Method:** test.')
        paths[ACCEPTANCE] += ('\n**Implementation:** ' + ', '.join(
            f'[{label}](../../{label.split("::", 1)[0]})' for label in labels) + '\n').encode()
        return refresh(paths)

    def audit(self, corpus, **kwargs):
        with redirect_stdout(io.StringIO()) as output:
            result = a.audit(corpus, self.root, **kwargs)
        return result, output.getvalue()

    def test_audit_distinguishes_pass_missing_and_failure(self):
        labels = [f'tests/sample.py::Suite::test_{name}' for name in ('pass', 'absent', 'fail')]
        result, output = self.audit(self.corpus(labels))
        self.assertEqual(result, (1, 1, 1))
        self.assertIn('1 passed, 1 missing, 1 failing', output)
        self.assertEqual(self.audit(self.corpus([labels[0]] * 3))[0], (3, 0, 0))

    def test_reports_match_outcomes_without_execution(self):
        labels = [f'tests/sample.py::Suite::test_{name}' for name in ('pass', 'fail', 'error', 'skip', 'absent')]
        labels += ['tests/names.test.ts::batch > accepts full name']
        runner = dict(pattern='*.ts', kind='junit', testcase=dict(classname='{file}', name='{selector}'))
        corpus = self.corpus(labels + [labels[0]], [runner])
        (self.root / 'python.xml').write_text('<testsuites><testsuite>' + ''.join(
            f'<testcase file="./tests/sample.py" classname="sample.Suite" name="test_{name}">{child}</testcase>'
            for name, child in [('pass', ''), ('fail', '<failure/>'), ('error', '<error/>'), ('skip', '<skipped/>')]) + '</testsuite></testsuites>')
        (self.root / 'vitest.xml').write_text('<testsuite><testcase classname="tests/names.test.ts" name="batch &gt; accepts full name"/></testsuite>')
        with patch.object(a.subprocess, 'Popen', side_effect=AssertionError('report mode ran tests')):
            self.assertEqual(self.audit(corpus, reports=['*.xml'])[0], (3, 1, 3))
            # Declared reports work without a CLI report; explicit CLI patterns override them.
            runner['reports'] = ['absent.xml']
            self.assertEqual(self.audit(self.corpus([labels[-1]], [runner]), reports=['vitest.xml'])[0], (1, 0, 0))
            runner['reports'] = ['vitest.xml']
            self.assertEqual(self.audit(self.corpus([labels[-1]], [runner]))[0], (1, 0, 0))
        cases = a.read_reports(self.root, ['python.xml', '*.xml'])
        self.assertEqual(len(cases), 5)  # overlapping globs do not duplicate report cases
        self.assertEqual(a.match_case([({'classname': 'tests.sample.Suite', 'name': 'test_pass'}, False)], labels[0], dict(kind='unittest')), 'passed')
        cases.append((dict(file='tests/sample.py', classname='Suite', name='test_pass'), True))
        self.assertEqual(a.match_case(cases, labels[0], dict(kind='unittest')), 'failing')

    def test_report_loading_leaves_inbound_links_to_structural_check(self):
        valid = self.corpus(['tests/sample.py::Suite::test_pass'])
        paths = dict(valid.source.files)
        paths['NOTES.md'] = b'[Retired section](docs/example/acceptance.md#gone)\n'
        paths[ACCEPTANCE] += b'\n[Outside note](../../NOTES.md#gone)\n'
        manifest = json.loads(paths['docs/DOCUMENTS.json'])
        manifest['inventory'].append(dict(path='NOTES.md', kind='other', reason='Synthetic input.'))
        paths['docs/DOCUMENTS.json'] = s.canonical(manifest)
        with patch.object(s, 'parse_markdown', wraps=s.parse_markdown) as parse:
            loaded = s.load_corpus(s.Snapshot.from_mapping(paths, fixture=True))
            self.assertNotIn('NOTES.md', [call.args[0] for call in parse.call_args_list])
        self.assertEqual({item.path for item in s.check(loaded).errors if item.code == 'D06'},
                         {'NOTES.md', ACCEPTANCE})

    def test_bad_or_absent_reports_name_the_fix(self):
        corpus = self.corpus(['tests/sample.py::Suite::test_pass'])
        with patch.object(a.subprocess, 'Popen', side_effect=AssertionError('must not fall back')):
            for content in ('<testsuite', '<wrong/>', '<testsuite><testcase name="test_pass"/></testsuite>'):
                (self.root / 'bad.xml').write_text(content)
                with self.assertRaisesRegex(a.ReportError, 'bad.xml.*regenerate'):
                    self.audit(corpus, reports=['bad.xml'])
            with self.assertRaisesRegex(a.ReportError, 'no report matches.*normal tests'):
                self.audit(corpus, reports=['absent*.xml'])
            with self.assertRaisesRegex(a.ReportError, 'no report matches'):
                self.audit(corpus, reports=['bad.xml', 'absent*.xml'])
        (self.root / 'empty.xml').write_text('<testsuites/>')
        self.assertEqual(self.audit(corpus, reports=['empty.xml'])[0], (0, 1, 0))

    def test_python_batch_loads_files_once_and_preserves_outcomes(self):
        labels = [f'{path}::Suite::test_{name}' for path, name in (
            ('one/sample.py', 'pass'), ('one/sample.py', 'fail'), ('one/sample.py', 'error'),
            ('one/sample.py', 'skip'), ('one/sample.py', 'absent'), ('two/sample.py', 'pass'))]
        labels.append('one/sample.py::Suite::unsupported')
        corpus = self.corpus(labels + [labels[0]])
        for directory in ('one', 'two'):
            target = self.root / directory / 'sample.py'
            target.write_text('from pathlib import Path\np=Path(__file__).with_suffix(".count")\n'
                              'p.write_text(p.read_text()+"x" if p.exists() else "x")\n' + self.source + '    unsupported = 7\n')
        with patch.object(a.subprocess, 'Popen', wraps=a.subprocess.Popen) as launch:
            self.assertEqual(self.audit(corpus)[0], (3, 2, 3))
            self.assertEqual(launch.call_count, 1)
        for directory in ('one', 'two'):
            self.assertEqual((self.root / directory / 'sample.count').read_text(), 'x')

    def test_declared_batch_runs_once_and_times_out(self):
        labels = ['case.spec::accepts full name', 'case.spec::absent', 'case.spec::fail']
        runner = dict(pattern='*.spec', kind='junit', testcase=dict(classname='{file}', name='{selector}'),
                      batch=[a.sys.executable, 'runner.py', '{report}', '{selectors}'])
        corpus = self.corpus(labels + labels[:1], [runner])
        (self.root / 'runner.py').write_text('import pathlib,sys,xml.etree.ElementTree as E\n'
            'assert sys.stdin.read()==""\n'
            'pathlib.Path("arguments.json").write_text(__import__("json").dumps(sys.argv[2:]))\n'
            's=E.Element("testsuite")\n'
            'for label in sys.argv[2:]:\n'
            ' file,name=label.split("::",1)\n'
            ' if name=="absent": continue\n'
            ' c=E.SubElement(s,"testcase",classname=file,name=name)\n'
            ' if name=="fail": E.SubElement(c,"failure")\n'
            'E.ElementTree(s).write(sys.argv[1])\n')
        with patch.object(a.subprocess, 'Popen', wraps=a.subprocess.Popen) as launch:
            self.assertEqual(self.audit(corpus)[0], (2, 1, 1))
            self.assertEqual(launch.call_count, 1)
        self.assertEqual(json.loads((self.root / 'arguments.json').read_text()), labels)
        (self.root / 'runner.py').write_text('import time\ntime.sleep(10)\n')
        result, output = self.audit(corpus, timeout_seconds=0.1)
        self.assertEqual(result, (0, 0, 4))
        self.assertIn('exceeded', output)
        (self.root / 'runner.py').write_text('raise SystemExit(1)\n')
        self.assertEqual(self.audit(corpus)[0], (0, 0, 4))
        runner.pop('batch')
        with self.assertRaisesRegex(a.ReportError, 'reports or a batch command'):
            self.audit(self.corpus(labels, [runner]))
        runner['batch'] = ['absent-command', '{report}', '{selectors}']
        self.assertEqual(self.audit(self.corpus(labels, [runner]))[0], (0, 0, 3))
