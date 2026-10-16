"""Small behavioral red/green fixtures for the shared documentation pipeline."""
import copy
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import io
import json
import re
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import spec_docs as s

FIXTURES = Path(__file__).parent / "fixtures" / "miniature"
ACCEPTANCE = "docs/example/acceptance.md"
SETTINGS = "docs/example/settings.md"


def miniature():
    paths = {"docs/" + name: (FIXTURES / name).read_bytes() for name in ("ENTITIES.json", "DOCUMENTS.json")}
    paths.update({"docs/example/" + name: (FIXTURES / name).read_bytes() for name in ("acceptance.md", "settings.md")})
    corpus = s.load_corpus(s.Snapshot.from_mapping(paths, fixture=True))
    paths.update(s.generate_navigation(corpus))
    return paths


def corpus(paths):
    return s.load_corpus(s.Snapshot.from_mapping(paths, fixture=True))


def edit(paths, path, before, after):
    assert before in paths[path].decode(), before
    paths[path] = paths[path].decode().replace(before, after).encode()


def metadata(paths, path, mutate):
    value = json.loads(paths[path])
    mutate(value)
    paths[path] = s.canonical(value)


def refresh(paths):
    paths.update(s.generate_navigation(corpus(paths)))
    return corpus(paths)


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = miniature()

    def setUp(self):
        self.paths = self.clean.copy()
        self.started = time.monotonic()

    def tearDown(self):
        # Standard test output records fixture trigger, outcome and duration.
        print(f"fixture {self.id()}: completed in {time.monotonic() - self.started:.3f}s")

    def codes(self, paths=None, base=None):
        return {d.code for d in s.check(corpus(self.paths if paths is None else paths), base).errors}

    def red_green(self, code, repair=None):
        self.assertIn(code, self.codes(), "invalid fixture must fail")
        fixed = repair() if repair else self.clean
        self.assertTrue(s.check(corpus(fixed)).ok, s.check(corpus(fixed)).errors)

    def context(self, assignment=None, paths=None):
        return s.select_context(corpus(paths or self.paths), assignment or {"version": 1, "sections": ["example-demo#acceptance"]})

    def context_error(self, code, assignment):
        with self.assertRaises(s.SpecDocsError) as caught:
            self.context(assignment)
        self.assertIn(code, {d.code for d in caught.exception.diagnostics.errors})
        self.assertGreater(self.context().size_bytes, 0)

    def test_changed_sections_compare_source_subtrees_without_line_number_noise(self):
        base = corpus(self.paths)
        self.paths[ACCEPTANCE] = b'Unregistered preamble.\n\n' + self.paths[ACCEPTANCE]
        self.assertEqual(s.changed_sections(base, corpus(self.paths)), [])
        edit(self.paths, ACCEPTANCE, '**Result:** Return', '**Result:** Report')
        self.assertEqual(s.changed_sections(base, corpus(self.paths)), ['example-demo#acceptance'])
        metadata(self.paths, 'docs/DOCUMENTS.json', lambda value: value['documents'][0]['sections'].append(
            dict(id='writer-only', path=ACCEPTANCE, anchor='writer', roles=['mechanism'],
                 summary='Process writes.', prerequisites=[], explanatory_dependencies=[])))
        self.assertEqual(s.changed_sections(base, corpus(self.paths)),
                         ['example-demo#acceptance', 'example-demo#writer-only'])

    def test_link_refuses_intersecting_first_use_edits(self):
        metadata(self.paths, 'docs/ENTITIES.json', lambda value: (
            value['entities']['example.writer'].update(forms=['prepared write']),
            value['entities']['example.acceptance'].update(forms=['write request'])))
        self.paths[ACCEPTANCE] += b'\n<a id="overlap"></a>\n## Overlap\n\nA prepared write request arrives.\n'
        with self.assertRaisesRegex(s.SpecDocsError, 'intersecting.*rewrite'):
            s.link_missing(corpus(self.paths))

    def test_implementation_uses_collected_field_outside_detail_examples(self):
        self.paths['tests/example.py'] = b'# synthetic test file\n'
        edit(self.paths, ACCEPTANCE, '**Method:** analysis.', '**Method:** test.')
        edit(self.paths, ACCEPTANCE, '**Expected:** `Conflict`, unchanged allocation state and no appended write.',
             '> **Detail — invalid field example**\n>\n> **Implementation:** invalid example.\n\n'
             '**Expected:** `Conflict`, unchanged allocation state and no appended write.\n\n'
             '**Implementation:** [tests/example.py::Suite::test_case](../../tests/example.py)')
        self.assertTrue(s.check(corpus(self.paths)).ok, s.check(corpus(self.paths)).errors)

    def test_fact_basis_evidence_changes_select_tests_from_both_snapshots(self):
        edit(self.paths, ACCEPTANCE, '**Result:** Return', '**Result:** Apply [capacity](settings.md#commit-capacity-default) and return')
        base = corpus(self.paths)
        edit(self.paths, SETTINGS, 'The fixture author must resolve the candidate capacity before adoption.',
             'The fixture author must resolve the candidate capacity after measurement.')
        candidate = corpus(self.paths)
        changes = s.requirement_changes(base, candidate).changes
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['tests'], ['example-demo#test-stale-revision'])
        self.assertEqual(changes[0]['changed_facts'][0]['id'], 'example.commit-capacity#default')
        self.assertIn('after measurement', changes[0]['changed_facts'][0]['candidate']['evidence'][0]['text'])
        self.assertIn('before adoption', changes[0]['changed_facts'][0]['base']['evidence'][0]['text'])
        # Unrelated sections do not become recursive evidence dependencies.
        self.paths = self.clean.copy()
        self.assertEqual(s.requirement_changes(base, base).changes, [])

    def test_fact_evidence_in_preserved_markdown_uses_captured_section(self):
        self.paths['docs/evidence.md'] = b'<a id="proof"></a>\n## Proof\n\nSequential submissions only.\n\n<a id="unrelated"></a>\n## Other evidence\n\nUnrelated evidence.\n'
        metadata(self.paths, 'docs/DOCUMENTS.json', lambda value: value['inventory'].append(
            dict(path='docs/evidence.md', kind='evidence')))
        edit(self.paths, SETTINGS, '[Capacity qualification](#open-questions)', '[Capacity qualification](../evidence.md#proof)')
        edit(self.paths, ACCEPTANCE, '**Result:** Return', '**Result:** Apply [capacity](settings.md#commit-capacity-default) and return')
        base = corpus(self.paths)
        edit(self.paths, 'docs/evidence.md', 'Unrelated evidence.', 'An unrelated revision.')
        self.assertEqual(s.requirement_changes(base, corpus(self.paths)).changes, [])
        edit(self.paths, 'docs/evidence.md', 'Sequential submissions only.', 'Sequential or concurrent submissions.')
        changes = s.requirement_changes(base, corpus(self.paths)).changes
        self.assertEqual(changes[0]['tests'], ['example-demo#test-stale-revision'])
        self.assertIn('Sequential or concurrent', changes[0]['changed_facts'][0]['candidate']['evidence'][0]['text'])

    def test_navigation_ignores_literal_marker_examples(self):
        metadata(self.paths, 'docs/DOCUMENTS.json', lambda value: value['documents'][0].update(
            navigation={'path': ACCEPTANCE, 'region': 'example-demo'}))
        del self.paths['docs/generated/example-demo.md']
        marker = s.START.format(document='example-demo')
        example = f'\n```markdown\n{marker}\nliteral example\n{s.END}\n```\n'
        self.paths[ACCEPTANCE] += (example + f'\n{marker}\nold\n{s.END}\n').encode()
        c = refresh(self.paths)
        self.assertTrue(s.check(c).ok, s.check(c).errors)
        self.assertIn(example.encode(), self.paths[ACCEPTANCE])
        self.assertEqual(s.generate_navigation(c)[ACCEPTANCE], self.paths[ACCEPTANCE])

    def test_generated_navigation_encodes_paths_and_fragments(self):
        fixture = Path(__file__).parent / 'fixtures/minimal'
        self.paths = {p.relative_to(fixture).as_posix(): p.read_bytes() for p in fixture.rglob('*') if p.is_file()}
        new = 'docs/example guide.md'
        self.paths[new] = self.paths.pop('docs/example.md')
        for path in ('docs/DOCUMENTS.json', 'docs/ENTITIES.json'):
            self.paths[path] = self.paths[path].replace(b'example.md', b'example guide.md')
        self.paths[new] = self.paths[new].replace(b'example.md#', b'example%20guide.md#')
        c = refresh(self.paths)
        self.assertIn(b'example%20guide.md#', self.paths[new])
        self.assertTrue(s.check(c).ok, s.check(c).errors)
        self.assertEqual(s.relative_link('docs/nav.md', 'docs/a b.md', 'a b'), 'a%20b.md#a%20b')

    def test_navigation_escapes_visible_labels_in_every_entry(self):
        title = 'Files [local] C:\\'
        edit(self.paths, ACCEPTANCE, '\n# Acceptance\n', '\n# `Files [local] C:\\`\n')
        edit(self.paths, ACCEPTANCE, '\n## Writer\n', '\n## `Files [local] C:\\`\n')
        c = corpus(self.paths)
        # Exercise the entity label independently from its naming contract.
        c.entities['example.writer']['title'] = title
        output = s.project_navigation(c)['docs/generated/example-demo.md'].decode()
        md = s.parse_markdown('docs/generated/example-demo.md', output, s.Diagnostics())
        links = [link for link in md.links if link.label == title]
        self.assertEqual(len(links), 4)  # section, nested heading, prerequisite, entity
        self.assertEqual({link.target.split('#')[-1] for link in links}, {'acceptance-section', 'writer'})

    def test_procedure_requires_each_direct_action_to_open_bold(self):
        self.paths[ACCEPTANCE] += b'\n**Procedure: inspect results**\n\n1. Read the result.\n2. **Check the state.** It remains intact.\n'
        errors = s.check(corpus(self.paths)).errors
        self.assertTrue(any(d.code == 'D18' and 'bold action' in d.message for d in errors), errors)
        edit(self.paths, ACCEPTANCE, '1. Read the result.', '1. **Read the result.**')
        self.assertTrue(s.check(corpus(self.paths)).ok)

    def test_link_inserts_only_missing_unambiguous_body_uses(self):
        edit(self.paths, ACCEPTANCE, '[writer](#writer)', 'writer')
        before = self.paths[ACCEPTANCE]
        self.assertIn('D12', self.codes())
        self.paths.update(s.link_missing(corpus(self.paths)))
        self.assertNotEqual(self.paths[ACCEPTANCE], before)
        self.assertTrue(s.check(corpus(self.paths)).ok)
        self.assertEqual(s.link_missing(corpus(self.paths)), {})

    def test_link_repair_preserves_markdown_sensitive_visible_names(self):
        metadata(self.paths, s.JSON_PATHS[0], lambda value:
                 value['entities']['example.writer']['forms'].append('C:\\'))
        self.paths[ACCEPTANCE] += b'\n<a id="path-use"></a>\n## Path use\n\nUse C:\\ here.\n'
        before = corpus(self.paths)
        self.assertIn('D12', {d.code for d in s.check(before).errors})
        self.paths.update(s.link_missing(before))
        after = corpus(self.paths)
        self.assertEqual([s.visible(t.children) for t in before.markdown[ACCEPTANCE].tokens if t.type == 'inline'],
                         [s.visible(t.children) for t in after.markdown[ACCEPTANCE].tokens if t.type == 'inline'])
        self.assertEqual([(link.label, link.target) for link in after.markdown[ACCEPTANCE].links
                          if link.label == 'C:\\'], [('C:\\', '#writer')])
        self.assertTrue(s.check(refresh(self.paths)).ok)
        self.assertEqual(s.link_missing(after), {})

    def test_link_prunes_repeats_per_level_two_scope_preserving_label_markup(self):
        self.paths[ACCEPTANCE] += b'\n<a id="repeats"></a>\n## Repeats\n\n[writer](#writer), [**Writer**](acceptance.md#writer).\n\n### Deeper\n\n[writer](#writer).\n\n<a id="next-scope"></a>\n## Next scope\n\n[writer](#writer), [writer](#writer).\n'
        before = self.paths[ACCEPTANCE]
        self.assertEqual(s.link_missing(corpus(self.paths)), {})
        self.paths.update(s.link_missing(corpus(self.paths), prune_repeats=True))
        self.assertNotEqual(before, self.paths[ACCEPTANCE])
        self.assertIn(b'[writer](#writer), **Writer**.', self.paths[ACCEPTANCE])
        self.assertIn(b'### Deeper\n\nwriter.', self.paths[ACCEPTANCE])
        self.assertIn(b'## Next scope\n\n[writer](#writer), writer.', self.paths[ACCEPTANCE])
        self.assertTrue(s.check(refresh(self.paths)).ok)
        self.assertEqual(s.link_missing(corpus(self.paths), prune_repeats=True), {})

    def test_link_pruning_exclusions(self):
        cases = {
            'headings': '### [writer](#writer)\n',
            'tables': '| Owner |\n|---|\n| [writer](#writer) |\n',
            'fenced literals': '```markdown\n[writer](#writer)\n```\n',
            'indented literals': '    [writer](#writer)\n',
            'example annotations': '**Entities in this example:** [writer](#writer).\n',
            'digit labels': '[writer 2](#writer).\n',
            'code labels': '[`writer`](#writer).\n',
            'deliberate wording': '[the author](#writer).\n',
            'inline literals': '`[writer](#writer)`\n',
        }
        # Registered numeric forms prove that the value exclusion precedes form matching.
        metadata(self.paths, s.JSON_PATHS[0], lambda v: v['entities']['example.writer']['forms'].append('writer 2'))
        for name, protected in cases.items():
            with self.subTest(exclusion=name):
                paths = self.paths.copy()
                paths[ACCEPTANCE] += ('\n<a id="protected"></a>\n## Protected\n\n[writer](#writer).\n\n' + protected
                                      + '\nA separate paragraph intervenes.\n\n[writer](#writer).\n').encode()
                outputs = s.link_missing(corpus(paths), prune_repeats=True)
                self.assertIn(protected.encode(), outputs[ACCEPTANCE])
                self.assertTrue(outputs[ACCEPTANCE].endswith(b'\nwriter.\n'))

    def test_link_pruning_keeps_literal_annotations_and_distinct_fact_homes(self):
        self.paths[ACCEPTANCE] += b'\n<a id="annotations"></a>\n## Annotations\n\n[writer](#writer).\n\n```text\nwriter\n```\n\nThe [writer](#writer) handles this example.\n\n[commit capacity](settings.md#commit-capacity), [commit capacity](settings.md#commit-capacity-default), [commit capacity](settings.md#commit-capacity-default).\n'
        self.paths.update(s.link_missing(corpus(self.paths), prune_repeats=True))
        self.assertIn(b'The [writer](#writer) handles this example.', self.paths[ACCEPTANCE])
        self.assertIn(b'[commit capacity](settings.md#commit-capacity), [commit capacity](settings.md#commit-capacity-default), commit capacity.', self.paths[ACCEPTANCE])
        self.assertTrue(s.check(refresh(self.paths)).ok, s.check(corpus(self.paths)).errors)

    def test_link_pruning_includes_newly_inserted_first_links(self):
        self.paths[ACCEPTANCE] += b'\n<a id="missing-first"></a>\n## Missing first\n\nwriter, [writer](#writer).\n'
        self.paths.update(s.link_missing(corpus(self.paths), prune_repeats=True))
        self.assertTrue(self.paths[ACCEPTANCE].endswith(b'[writer](#writer), writer.\n'))
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_link_pruning_keeps_first_registered_use_after_deliberate_wording(self):
        self.paths[ACCEPTANCE] += b'\n<a id="wording"></a>\n## Wording\n\n[the author](#writer), [writer](#writer), [writer](#writer).\n'
        self.paths.update(s.link_missing(corpus(self.paths), prune_repeats=True))
        self.assertTrue(self.paths[ACCEPTANCE].endswith(b'[the author](#writer), [writer](#writer), writer.\n'))
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_link_leaves_headings_code_literals_existing_links_and_ambiguity(self):
        self.paths[ACCEPTANCE] += b'\n### Writer\n\n`writer`\n\n```text\nwriter\n```\n\n[writer](#acceptance)\n'
        before = self.paths[ACCEPTANCE]
        self.assertEqual(s.link_missing(corpus(self.paths)), {})
        self.assertEqual(self.paths[ACCEPTANCE], before)
        metadata(self.paths, s.JSON_PATHS[0], lambda v: v['entities']['example.acceptance']['forms'].append('writer'))
        self.paths[ACCEPTANCE] += b'\nwriter\n'
        self.assertEqual(s.link_missing(corpus(self.paths)), {})
        self.assertIn('W04', {d.code for d in s.check(corpus(self.paths)).warnings})
        self.assertNotIn('D12', self.codes())

    def test_link_preserves_markdown_and_links_only_first_uses_in_lists_quotes_and_tables(self):
        extra = '\n## More uses\n\n> writer &amp; **writer**\n\n- writer and writer.\n\n## Table uses\n\n| Item | Owner |\n|---|---|\n| label \\| writer | writer |\n| [writer](#writer) | writer |\n'
        edit(self.paths, ACCEPTANCE, '<a id="writer"></a>', extra + '\n<a id="writer"></a>')
        self.paths.update(s.link_missing(corpus(self.paths)))
        text = self.paths[ACCEPTANCE].decode()
        self.assertIn('> [writer](#writer) &amp; **writer**', text)
        self.assertIn('- writer and writer.', text)
        self.assertIn('| label \\| [writer](#writer) | writer |', text)
        self.assertIn('| [writer](#writer) | writer |', text)
        self.assertNotIn('D12', self.codes())
        self.assertEqual(s.link_missing(corpus(self.paths)), {})

    def test_declaration_ignores_blockquoted_detail_fields_only(self):
        edit(self.paths, ACCEPTANCE, '**Purpose:** Follow',
             '> **Detail — input:**\n>\n> **Inputs:** A concrete request.\n>\n> **Nested:** More detail.\n\n**Purpose:** Follow')
        self.assertNotIn('D02', self.codes())
        declaration = corpus(self.paths).declarations['example-demo#stale-revision']
        self.assertEqual(declaration['fields']['Inputs'][0], 'Expected revision 7; current revision 8.')
        self.assertNotIn('Nested', declaration['fields'])
        self.paths[ACCEPTANCE] += b'\n**Unexpected:** Still a malformed field.\n'
        self.assertIn('D02', self.codes())

    def test_fact_table_without_owner_names_line_and_repair(self):
        self.paths[ACCEPTANCE] += b'\n<a id="orphan"></a>\n## Orphan\n\n| Key | Value | Status | Basis |\n|---|---|---|---|\n| x | 1 | specified | [Fixture](settings.md#fixture-decision) |\n'
        errors = [d for d in self.codes_for('D04')]
        line = len(self.paths[ACCEPTANCE].splitlines())
        self.assertEqual(errors[0].message, f"fact table at line {line} is not inside a registered entity's home; move it under the owning entity's heading or register that entity")

    def codes_for(self, code):
        return [d for d in s.check(corpus(self.paths)).errors if d.code == code]

    def test_fact_status_uses_contract_vocabulary(self):
        for status in ('later source note', 'inherited draft', 'conflicting source expression'):
            with self.subTest(status=status):
                self.paths = self.clean.copy()
                edit(self.paths, SETTINGS, '| specified |', f'| {status} |')
                errors = self.codes_for('D02')
                self.assertTrue(any('specified, provisional, observed, unresolved' in d.message for d in errors), errors)
        for status in ('specified', 'provisional', 'observed', 'unresolved'):
            self.paths = self.clean.copy()
            edit(self.paths, SETTINGS, '| specified |', f'| {status} |')
            self.assertNotIn('D02', self.codes())

    def test_context_rewrites_html_encoded_anchors_with_attribute_escaping(self):
        for prefix in ('', '> '):
            with self.subTest(container=bool(prefix)):
                self.paths = self.clean.copy()
                self.paths[ACCEPTANCE] += (
                    '\n' + prefix + '<div>\n' + prefix + '<a id="limits&amp;bounds&quot;quoted"></a>\n'
                    + prefix + '</div>\n\n[Limits](#limits%26bounds%22quoted)\n'
                    + '\nInline <a id="inline&amp;bounds&quot;quoted"></a> anchor.\n\n'
                    + '[Inline](#inline%26bounds%22quoted)\n').encode()
                text = self.context().content.decode()
                self.assertIn(prefix + '<a id="pack-0-limits&amp;bounds&quot;quoted"></a>', text)
                self.assertIn('[Limits](#pack-0-limits%26bounds%22quoted)', text)
                self.assertIn('<a id="pack-0-inline&amp;bounds&quot;quoted"></a>', text)
                self.assertIn('[Inline](#pack-0-inline%26bounds%22quoted)', text)

    def test_context_rewrites_only_links_to_included_destinations(self):
        self.paths[ACCEPTANCE] += b'\n> <div>\n> <a id="proof"></a>\n> Preserved evidence.\n> <a\n> id="proof-lines"></a>\n> </div>\n\n[Proof](#proof).\n'
        ctx = self.context()
        text = ctx.content.decode()
        self.assertIn('> <a id="pack-0-proof"></a>\n> Preserved evidence.', text)
        self.assertIn('[Proof](#pack-0-proof)', text)
        self.assertIn('> <a\n> id="pack-0-proof-lines"></a>', text)
        self.assertIn('[log group byte limit](#pack-1-log-group-limit)', text)
        self.assertIn('<a id="pack-1-log-group-limit"></a>', text)
        self.assertNotIn('](settings.md#log-group-limit)', text)
        self.assertIn('[writer](#pack-0-writer)', text)
        self.assertIn('<a id="writer"></a>', self.paths[ACCEPTANCE].decode())
        self.assertEqual(ctx.size_bytes, len(ctx.content))
        self.assertNotIn('</a></a>', text)

    def test_context_preserves_literal_links_and_handles_reference_links_and_base(self):
        self.paths[ACCEPTANCE] += b'\n[Writer reference][owner]\n\n[owner]: #writer "Owner"\n\n```markdown\n[writer](#writer)\n<a id="writer"></a>\n```\n\n[Writer](#writer) names the literal example.\n\n| Choice | Destination |\n|---|---|\n| Actor | [Writer \\| owner](#writer) |\n\n[Outside](https://example.invalid/x#writer)\n'
        c = refresh(self.paths)
        c.base = corpus(self.clean)
        ctx = s.select_context(c, {'version': 1, 'sections': ['example-demo#acceptance'],
                                  'required_test_reviews': ['example-demo#test-stale-revision']})
        text = ctx.content.decode()
        self.assertRegex(text, r'\[Writer reference\]\(#pack-\d+-writer "Owner"\)')
        self.assertIn('```markdown\n[writer](#writer)\n<a id="writer"></a>\n```', text)
        self.assertIn('[Outside](https://example.invalid/x#writer)', text)
        self.assertRegex(text, r'\[Writer \\\| owner\]\(#pack-\d+-writer\)')
        ids = re.findall(r'<a id="(pack-[^"<>]+)"></a>', text)
        self.assertEqual(len(ids), len(set(ids)))
        destinations = re.findall(r'\]\(#(pack-[^\s)]+)', text)
        self.assertTrue(set(destinations) <= set(ids))
        self.assertEqual(ctx.size_bytes, len(ctx.content))

    def test_context_keeps_links_to_source_outside_selected_ranges(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'][0].update(explanatory_dependencies=[]))
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0].pop('approval'))
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0].update(status='draft'))
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'].append(dict(
            id='writer-only', path=ACCEPTANCE, anchor='writer', roles=[], summary='Explain the writer.',
            prerequisites=[], explanatory_dependencies=[])))
        edit(self.paths, ACCEPTANCE, 'It performs [acceptance](#acceptance) before allocating numbers.',
             'See [open questions](settings.md#open-questions) for unsettled work.')
        refresh(self.paths)
        ctx = self.context({'version': 1, 'sections': ['example-demo#writer-only']})
        self.assertIn('[open questions](settings.md#open-questions)', ctx.content.decode())

    def test_chapter_filename_matches_first_heading_slug(self):
        edit(self.paths, SETTINGS, '# Settings', '# Unrelated title')
        self.red_green('D34')

    def test_summary_explains_more_than_title_or_generic_verb(self):
        for summary in ('Acceptance.', 'Understand Acceptance.',
                        'Learn about acceptance', 'Read about acceptance',
                        'Overview of acceptance', 'Acceptance acceptance'):
            with self.subTest(summary=summary):
                self.paths = self.clean.copy()
                metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'][0].update(summary=summary))
                self.red_green('D36')

    def test_diagnostics_locate_document_text_without_echoing_it(self):
        marker = 'private-fixture-' + 'marker-123'
        for mode, code in (('escape', 'D05'), ('value', 'D10'), ('ambiguous', 'W04'),
                           ('rejected', 'D13'), ('symbol', 'D14'), ('duplicate-field', 'D02'),
                           ('unknown-field', 'D02'), ('fact-status', 'D02'), ('fact-anchor', 'D08'),
                           ('fact-duplicate', 'D03'), ('fact-fields', 'D02'), ('anchor', 'D03')):
            with self.subTest(mode=mode):
                self.paths = self.clean.copy()
                if mode == 'escape':
                    self.paths[ACCEPTANCE] += f'\n[Outside](../../../../{marker})\n'.encode()
                elif mode == 'value':
                    edit(self.paths, SETTINGS, '| 1,024 |', f'| {marker} |')
                    self.paths[ACCEPTANCE] += f'\n[999 {marker}](settings.md#commit-capacity-default)\n'.encode()
                elif mode == 'ambiguous':
                    metadata(self.paths, s.JSON_PATHS[0], lambda v: (
                        v['entities']['example.writer']['forms'].append(marker),
                        v['entities']['example.acceptance']['forms'].append(marker)))
                    self.paths[ACCEPTANCE] += f'\n{marker}\n'.encode()
                elif mode == 'rejected':
                    metadata(self.paths, s.JSON_PATHS[0], lambda v:
                        v['entities']['example.writer']['rejected_forms'].append(
                            dict(text=marker, replacement=marker + '-replacement', reason='Synthetic example.')))
                    self.paths[ACCEPTANCE] += f'\n{marker}\n'.encode()
                elif mode == 'symbol':
                    metadata(self.paths, s.JSON_PATHS[0], lambda v:
                        v['entities']['example.commit-capacity']['symbols'].append(marker))
                elif mode in ('duplicate-field', 'unknown-field'):
                    self.paths[ACCEPTANCE] += (f'\n**{marker}:** Synthetic field.\n' *
                                              (2 if mode == 'duplicate-field' else 1)).encode()
                elif mode == 'anchor':
                    self.paths[ACCEPTANCE] += (f'\n<a id="{marker}"></a>\n' * 2).encode()
                else:
                    row = f'| <a id="synthetic-row"></a>{marker} | 3 | specified | [Fixture](#fixture-decision) |'
                    if mode == 'fact-status':
                        row = row.replace('specified', 'invalid')
                    elif mode == 'fact-anchor':
                        row = row.replace('<a id="synthetic-row"></a>', '')
                    elif mode == 'fact-fields':
                        row = row.replace('[Fixture](#fixture-decision)', '')
                    elif mode == 'fact-duplicate':
                        row += '\n' + row.replace('synthetic-row', 'second-row')
                    edit(self.paths, SETTINGS, '| <a id="commit-capacity-default"></a>default | 1,024 | provisional | [Capacity qualification](#open-questions) |',
                         '| <a id="commit-capacity-default"></a>default | 1,024 | provisional | [Capacity qualification](#open-questions) |\n' + row)
                diagnostics = s.check(corpus(self.paths))
                self.assertTrue(any(d.code == code for d in diagnostics.items))
                self.assertFalse(marker in json.dumps(diagnostics.to_dict()),
                                 'document text escaped into diagnostics')

    def test_three_repeated_sentences_fail_with_whitespace_normalization(self):
        sentence = 'The displayed capacity comes from the single declared batch value.'
        self.paths[SETTINGS] += ('\n' + sentence + '\n\n' + sentence.replace(' ', '\n') + '\n').encode()
        self.assertNotIn('D35', self.codes())
        self.paths[ACCEPTANCE] += ('\n' + sentence + '\n').encode()
        self.red_green('D35')

    def test_repetition_ignores_generated_regions_literals_and_attributed_quotes(self):
        sentence = 'The displayed capacity comes from the single declared batch value.'
        self.paths[SETTINGS] += ('\n' + sentence + '\n\n```text\n' + sentence + '\n' + sentence +
                                 '\n```\n\n> ' + sentence + '\n>\n> — Example author\n').encode()
        self.assertNotIn('D35', self.codes())
        refresh(self.paths)
        self.assertTrue(s.check(corpus(self.paths)).ok)

    def test_predecessor_only_prerequisites_warn_above_five_sections(self):
        def extend(v):
            doc = v['documents'][0]
            for i in range(4):
                previous = doc['sections'][-1]['id']
                doc['sections'].append(dict(id=f'extra-{i}', path=SETTINGS, anchor=f'extra-{i}',
                    roles=[], summary=f'Explain case {i} and its result.',
                    prerequisites=['example-demo#' + previous], explanatory_dependencies=[]))
        metadata(self.paths, s.JSON_PATHS[1], extend)
        for i in range(4):
            self.paths[SETTINGS] += f'\n<a id="extra-{i}"></a>\n## Extra {i}\n\nCase {i} returns its result.\n'.encode()
        self.assertIn('W06', {d.code for d in s.check(corpus(self.paths)).warnings})
        self.assertTrue(s.check(refresh(self.paths)).ok)
        six_sections = self.paths[s.JSON_PATHS[1]]
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'].pop())
        self.assertNotIn('W06', {d.code for d in s.check(corpus(self.paths)).warnings})
        self.paths[s.JSON_PATHS[1]] = six_sections
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'][-1].update(prerequisites=[]))
        self.assertNotIn('W06', {d.code for d in s.check(corpus(self.paths)).warnings})

    def test_entity_index_uses_definition_sentence_without_following_purpose(self):
        edit(self.paths, SETTINGS, 'Commit capacity bounds documents in one commit.',
             'Commit capacity is the maximum document count in one commit.\nIt prevents oversized submissions.')
        output = s.generate_navigation(corpus(self.paths))['docs/generated/example-demo.md'].decode()
        self.assertIn('Commit capacity is the maximum document count in one commit.', output)
        self.assertNotIn('It prevents oversized submissions.', output)

    def test_map_places_diagram_before_generated_overview(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0].update(navigation={'path': ACCEPTANCE, 'region': 'example-demo'}))
        self.paths.pop('docs/generated/example-demo.md')
        edit(self.paths, ACCEPTANCE, 'This tour follows a refusal before explaining its limits.',
             'This tour follows a refusal before explaining its limits.\n\nWhat does the tool check?\n\n```mermaid\nflowchart TD\n    A[Source] --> B[Check]\n```')
        self.paths[ACCEPTANCE] += ('\n' + s.START.format(document='example-demo') + '\n' + s.END + '\n').encode()
        c = refresh(self.paths)
        text = self.paths[ACCEPTANCE].decode()
        self.assertLess(text.index('```mermaid'), text.index('## Overview'))
        self.assertTrue(s.check(c).ok)

    def test_navigation_keeps_complete_introduction_together(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0].update(
            navigation={'path': ACCEPTANCE, 'region': 'example-demo'}))
        self.paths.pop('docs/generated/example-demo.md')
        original = 'This tour follows a refusal before explaining its limits.'
        for diagram in ('', '\n\nWhat does the tool check?\n\n```mermaid\nflowchart TD\n    A[Source] --> B[Check]\n```'):
            with self.subTest(diagram=bool(diagram)):
                paths = self.paths.copy()
                edit(paths, ACCEPTANCE, original,
                     original + diagram + '\n\nRead these prerequisites before the tour.')
                paths[ACCEPTANCE] += ('\n' + s.START.format(document='example-demo') + '\n' + s.END + '\n').encode()
                refresh(paths)
                text = paths[ACCEPTANCE].decode()
                self.assertLess(text.index('Read these prerequisites'), text.index('## Overview'))
                self.assertEqual(s.generate_navigation(corpus(paths))[ACCEPTANCE], paths[ACCEPTANCE])
                self.assertTrue(s.check(corpus(paths)).ok)

    def test_literal_home_links_can_be_in_adjacent_explanatory_prose(self):
        for quote in ('', '> '):
            with self.subTest(quote=quote):
                self.paths = self.clean.copy()
                example = ('[Writer](#writer) is the actor shown below.\n\n```text\nwriter\n```\n')
                example = '\n'.join(quote + line for line in example.splitlines()) + '\n\n'
                edit(self.paths, ACCEPTANCE, '**Procedure: demonstrate', example + '**Procedure: demonstrate')
                self.assertNotIn('D12', self.codes())
                refresh(self.paths)
                self.assertTrue(s.check(corpus(self.paths)).ok)
                # A link for one block cannot cover a later block across unrelated prose.
                self.paths[ACCEPTANCE] += b'\nUnrelated explanation.\n\n```text\nwriter\n```\n'
                self.assertIn('D12', self.codes())

    def test_every_role_preserves_contract_order(self):
        for role in ('requirements', 'decisions', 'questions', 'reference', 'acceptance'):
            with self.subTest(role=role):
                self.paths = self.clean.copy()
                def reorder(v):
                    first, last = v['documents'][0]['sections']
                    last['roles'].remove(role)
                    first['roles'].append(role)
                metadata(self.paths, s.JSON_PATHS[1], reorder)
                self.red_green('D15')

    def test_inbound_links_from_other_markdown_are_checked(self):
        self.paths['CHANGELOG.md'] = b'[Retired section](docs/example/acceptance.md#gone)\n'
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['inventory'].append(
            dict(path='CHANGELOG.md', kind='other', reason='Change history.')))
        self.assertIn('D06', self.codes())
        edit(self.paths, 'CHANGELOG.md', '#gone', '#writer')
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_failure_verification_requires_a_resolving_link(self):
        edit(self.paths, ACCEPTANCE, '**Verification:** [Stale request](#test-stale-revision).',
             '**Verification:** checked manually.')
        self.red_green('D30')

    def test_executable_method_requires_implementation_and_other_methods_require_evidence(self):
        edit(self.paths, ACCEPTANCE, '**Method:** analysis.', '**Method:** test.')
        self.assertIn('D02', self.codes())
        self.paths['tests/example.py'] = b'import unittest\nclass Suite(unittest.TestCase):\n    def test_ok(self): pass\n'
        self.implementation('[tests/example.py::Suite::test_ok](../../tests/example.py)')
        self.assertTrue(s.check(refresh(self.paths)).ok)
        edit(self.paths, ACCEPTANCE, '**Method:** test.', '**Method:** analysis.')
        self.assertIn('D02', self.codes())
        self.paths[ACCEPTANCE] = self.paths[ACCEPTANCE].split(b'\n**Implementation:**')[0]
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_selected_test_expands_homes_and_declared_dependencies(self):
        # The narrow assigned section has no test-related names or dependencies.
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'][0].update(explanatory_dependencies=[]))
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'].append(dict(
            id='questions-only', path=SETTINGS, anchor='open-questions', roles=[],
            summary='Questions only.', prerequisites=[], explanatory_dependencies=[])))
        refresh(self.paths)
        ctx = self.context({'version': 1, 'sections': ['example-demo#questions-only'],
                            'required_test_reviews': ['example-demo#test-stale-revision']})
        self.assertIn('example.writer', ctx.manifest['included'])

    def test_repeated_example_annotations_are_not_duplicate_declaration_fields(self):
        self.paths[SETTINGS] += b'\n```text\nwriter\n```\n\n**Entities in this example:** [Writer](acceptance.md#writer).\n\n```text\nwriter\n```\n\n**Entities in this example:** [Writer](acceptance.md#writer).\n'
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_repository_without_writing_rules_uses_the_tool_profile(self):
        self.paths.pop(s.PROFILE_PATH, None)
        self.assertTrue(s.check(refresh(self.paths)).ok)
        self.assertEqual(corpus(self.paths).profile['name'], 'house-technical-english')

    def test_prose_dates_do_not_claim_to_detect_fact_restatements(self):
        self.paths[SETTINGS] += b'\nRecorded on 2026-10-16 with 7 examples.\n'
        self.assertNotIn('W03', {d.code for d in s.check(refresh(self.paths)).warnings})

    def test_selection_validates_each_corpus_only_once(self):
        c = corpus(self.paths)
        with patch.object(s, 'check', wraps=s.check) as checker:
            s.select_context(c, {'version': 1, 'sections': ['example-demo#acceptance']})
        self.assertEqual(checker.call_count, 1)

    def test_scenario_follows_requirement_tests_without_a_tests_field(self):
        # Put the test in a distinct manifest section and remove incidental dependencies.
        text = self.paths[ACCEPTANCE].decode()
        first = text.index('<a id="test-stale-revision">')
        test = text[first:]
        self.paths[ACCEPTANCE] = text[:first].replace('**Tests:** [Stale request](#test-stale-revision).', '**Tests:** [Stale request](acceptance-test-stale-request.md#test-stale-revision).', 1).replace('**Tests:** [Stale request](#test-stale-revision).', '').replace('](#test-stale-revision)', '](acceptance-test-stale-request.md#test-stale-revision)').encode()
        self.paths['docs/example/acceptance-test-stale-request.md'] = test.replace('](#req-stale-revision)', '](acceptance.md#req-stale-revision)').replace('](#writer)', '](acceptance.md#writer)').replace('](#acceptance)', '](acceptance.md#acceptance)').replace('](#acceptance-stale-failure)', '](acceptance.md#acceptance-stale-failure)').encode()
        def update(v):
            v['inventory'].append({'path': 'docs/example/acceptance-test-stale-request.md', 'kind': 'specification'})
            v['documents'][0]['sections'][0]['explanatory_dependencies'] = []
            v['documents'][0]['sections'].append(dict(id='test', path='docs/example/acceptance-test-stale-request.md', anchor='test-stale-revision', roles=[], summary='Acceptance evidence.', prerequisites=[], explanatory_dependencies=[]))
        metadata(self.paths, s.JSON_PATHS[1], update)
        c = refresh(self.paths)
        ctx = s.select_context(c, {'version': 1, 'sections': ['example-demo#settings'], 'scenarios': ['example-demo#stale-revision']})
        self.assertIn('example-demo#test', ctx.manifest['included'])

    def test_moving_requirement_between_documents_preserves_identity(self):
        base = corpus(self.paths)
        def move(v):
            document = v['documents'][0]
            document['id'] = 'moved-demo'
            document['approval']['decision'] = 'moved-demo#fixture-decision'
            document['scenarios'] = ['moved-demo#stale-revision']
            for section in document['sections']:
                section['prerequisites'] = [x.replace('example-demo#', 'moved-demo#') for x in section['prerequisites']]
                for dep in section['explanatory_dependencies']:
                    dep['section'] = dep['section'].replace('example-demo#', 'moved-demo#')
        metadata(self.paths, s.JSON_PATHS[1], move)
        def homes(v):
            for e in v['entities'].values():
                e['scope'] = ['moved-demo']
                e['home']['section'] = e['home']['section'].replace('example-demo#', 'moved-demo#')
        metadata(self.paths, s.JSON_PATHS[0], homes)
        candidate = refresh(self.paths)
        self.assertEqual(s.requirement_changes(base, candidate).changes, [])
        edit(self.paths, ACCEPTANCE, '**Result:** Return', '**Result:** Report')
        change = s.requirement_changes(base, corpus(self.paths)).changes
        self.assertEqual([item['kind'] for item in change], ['changed'])
        self.assertEqual(change[0]['added_tests'], [])
        self.assertEqual(change[0]['removed_tests'], [])

    def test_navigation_region_follows_introduction_before_first_subheading(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0].update(navigation={'path': ACCEPTANCE, 'region': 'example-demo'}))
        del self.paths['docs/generated/example-demo.md']
        self.paths[ACCEPTANCE] += ('\n' + s.START.format(document='example-demo') + '\nold\n' + s.END + '\n').encode()
        c = refresh(self.paths)
        text = self.paths[ACCEPTANCE].decode()
        self.assertLess(text.index('**Procedure:'), text.index(s.START.format(document='example-demo')))
        self.assertLess(text.index(s.END), text.index('<a id="writer"></a>'))
        self.assertEqual(text.splitlines().count('# Acceptance'), 1)
        self.assertFalse(text.endswith('\n\n'))
        self.assertTrue(s.check(c).ok)

    def test_navigation_lists_registered_sections_once(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda value:
                 value['documents'][0]['sections'].append(dict(
                     id='writer', path=ACCEPTANCE, anchor='writer', roles=[],
                     summary='Find the write owner.', prerequisites=[], explanatory_dependencies=[])))
        output = s.project_navigation(corpus(self.paths))['docs/generated/example-demo.md'].decode()
        navigation = output.split('## Entity index')[0]
        self.assertEqual(navigation.count('](../example/acceptance.md#writer)'), 1)
        self.assertIn('[Acceptance]', navigation)

    def test_navigation_lists_second_level_sections(self):
        output = self.paths['docs/generated/example-demo.md'].decode()
        self.assertIn('[Writer](../example/acceptance.md#writer)', output.split('## Entity index')[0])
        self.assertIn('Use this map to choose the next explanation to read.', output)
        self.assertIn('Each technical term below links to its defining Markdown section.', output)

    def test_miniature_retains_multirow_table_and_complete_registry(self):
        c = corpus(self.paths)
        self.assertTrue(s.check(c).ok)
        self.assertEqual(len(c.entities), 5)
        self.assertEqual(len(c.facts), 3)
        self.assertEqual(c.facts["example.log-group-limit#default"]["value"], "4 MiB")
        self.assertEqual(c.facts["example.log-group-limit#scope"]["value"], "instance")

    def test_tracked_markdown_requires_classification(self):
        self.paths["docs/forgotten.md"] = b"# Forgotten\n"
        self.red_green("D01")

    def test_duplicate_json_keys_are_not_last_value_wins(self):
        edit(self.paths, s.JSON_PATHS[0], '"version": 1', '"version": 1, "version": 1')
        self.red_green("D02")

    def test_unknown_fields_and_versions_are_refused(self):
        for mutate in (lambda v: v.update(version=2), lambda v: v["entities"]["example.writer"].update(unknown=True)):
            self.paths = self.clean.copy()
            metadata(self.paths, s.JSON_PATHS[0], mutate)
            self.red_green("D02")

    def test_duplicate_section_identity_has_source(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v["documents"][0]["sections"].append(v["documents"][0]["sections"][0].copy()))
        self.red_green("D03")

    def test_trace_anchors_require_type_prefix_and_nonempty_kebab_identity(self):
        for old, invalid in (('req-stale-revision', 'stale-revision-rule'),
                             ('test-stale-revision', 'stale-revision-test'),
                             ('req-stale-revision', 'req-'),
                             ('test-stale-revision', 'test-'),
                             ('req-stale-revision', 'req-Bad_identity')):
            with self.subTest(anchor=invalid):
                self.paths = self.clean.copy()
                edit(self.paths, ACCEPTANCE, old, invalid)
                self.red_green('D02')

    def test_trace_identities_are_unique_across_documents_and_retired_records(self):
        for anchor, kind in (('req-stale-revision', 'Requirement'),
                             ('test-stale-revision', 'Acceptance test')):
            with self.subTest(kind=kind):
                self.paths = self.clean.copy()
                other = 'docs/example/other.md'
                self.paths[other] = (f'<a id="other"></a>\n# Other\n\nA second document.\n\n'
                                     f'<a id="{anchor}"></a>\n### {kind}: another title\n\n'
                                     '**Status:** retired.\n').encode()
                def add_document(v):
                    v['inventory'].append({'path': other, 'kind': 'specification'})
                    v['documents'].append(dict(id='other', title='Other', status='draft',
                        purpose='Test identities', audience='Test authors', scope='Identity checking',
                        non_goals='Execution', navigation={'path': 'docs/generated/other.md'},
                        sections=[dict(id='other', path=other, anchor='other', roles=[],
                            summary='Duplicate identities', prerequisites=[], explanatory_dependencies=[])],
                        scenarios=[], gaps=corpus(self.clean).contract['roles']))
                metadata(self.paths, s.JSON_PATHS[1], add_document)
                self.red_green('D03')

    def test_home_needs_heading_anchor_and_introductory_meaning(self):
        edit(self.paths, ACCEPTANCE, 'The writer processes write requests.', '')
        edit(self.paths, ACCEPTANCE, 'It performs [acceptance](#acceptance) before allocating numbers.', '')
        self.red_green("D04")

    def test_name_attribute_does_not_replace_explicit_id(self):
        edit(self.paths, ACCEPTANCE, '<a id="writer"></a>', '<a name="writer"></a>')
        self.red_green("D02")

    def test_duplicate_anchor_is_not_a_unique_home(self):
        edit(self.paths, ACCEPTANCE, '<a id="writer"></a>', '<a id="writer"></a>\n<a id="writer"></a>')
        self.assertIn("D03", self.codes())
        self.red_green("D04")

    def test_path_escape_in_input_is_refused(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v["inventory"].append({"path": "../escape.md", "kind": "specification"}))
        self.red_green("D02")

    def test_invalid_utf8_is_not_silently_skipped(self):
        self.paths[SETTINGS] += b"\xff"
        self.red_green("D05")

    def test_missing_source_is_visible_io_failure(self):
        del self.paths[SETTINGS]
        self.red_green("D27")

    def test_local_fragment_must_be_explicit_and_present(self):
        edit(self.paths, ACCEPTANCE, '(#writer)', '(#missing-writer)')
        self.red_green("D06")

    def test_external_url_syntax_is_checked_without_network(self):
        edit(self.paths, ACCEPTANCE, '(#writer)', '(https://)')
        self.red_green("D06")

    def test_entity_scope_cannot_omit_its_own_document(self):
        metadata(self.paths, s.JSON_PATHS[0], lambda v: v["entities"]["example.writer"].update(scope=[]))
        self.red_green("D07")

    def test_fact_anchor_belongs_inside_its_key_cell(self):
        edit(self.paths, SETTINGS, '<a id="log-group-limit-default"></a>default', 'default')
        self.red_green("D08")

    def test_two_anchors_in_one_fact_row_are_refused(self):
        edit(self.paths, SETTINGS, '<a id="log-group-limit-default"></a>default', '<a id="extra"></a><a id="log-group-limit-default"></a>default')
        self.red_green("D08")

    def test_fact_status_and_linked_basis_are_required(self):
        edit(self.paths, SETTINGS, '| 4 MiB | specified | [Fixture](#fixture-decision) |', '| 4 MiB | | Fixture |')
        self.red_green("D02")

    def test_literal_values_allow_grouping_and_markdown_formatting(self):
        for value in ("1024", "1_024", "1 024", "**1,024**", "`1024`"):
            paths = self.clean.copy()
            edit(paths, SETTINGS, 'Its provisional default borrows the [default]', f'Its provisional default borrows the [{value}]')
            self.assertTrue(s.check(refresh(paths)).ok, value)

    def test_runner_declarations_validate_commands_and_patterns(self):
        valid = dict(pattern='tests/*.spec', kind='junit',
                     testcase=dict(classname='{file}', name='{selector}'),
                     batch=['runner', '{report}', '{selectors}'], reports=['reports/*.xml'])
        for invalid in (None, {}, [None], [dict(valid, pattern='../*.spec')],
                        [dict(valid, command=['old-runner'])], [dict(valid, kind='unknown')],
                        [dict(valid, reports=[])], [dict(valid, reports=['../*.xml'])],
                        [dict(valid, testcase={})], [dict(valid, testcase=dict(name='{unknown}'))],
                        [dict(valid, testcase=dict(unknown='{file}::{selector}'))],
                        [dict(valid, batch=[])], [dict(valid, batch=['runner', '{report}'])],
                        [dict(valid, batch=['runner', '{report}', 'prefix{selectors}'])],
                        [dict(valid, batch=['runner', '{report}', '{selectors}', '{unknown}'])],
                        [dict(valid, kind='unittest')], [valid, valid]):
            paths = self.clean.copy()
            metadata(paths, s.JSON_PATHS[1], lambda value: value.update(test_runners=invalid))
            self.assertIn('D02', {item.code for item in s.check(corpus(paths)).errors})
        for runner in (valid, dict(pattern='*.py', kind='unittest', reports=['reports/python.xml'])):
            metadata(self.paths, s.JSON_PATHS[1], lambda value: value.update(test_runners=[runner]))
            self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_descriptive_fact_labels_and_code_only_literals(self):
        for label in ('declared limit', 'borrowing limit', '**declared limit**', '`1024`', '``1024``'):
            paths = self.clean.copy()
            edit(paths, SETTINGS, 'Its provisional default borrows the [default]', f'Its provisional default borrows the [{label}]')
            self.assertTrue(s.check(refresh(paths)).ok, label)
        for label in ('`wrong`', '``wrong``', 'revision 2'):
            paths = self.clean.copy()
            edit(paths, SETTINGS, 'Its provisional default borrows the [default]', f'Its provisional default borrows the [{label}]')
            self.assertIn('D10', {d.code for d in s.check(corpus(paths)).errors}, label)

    def test_context_sources_follow_manifest_order_then_source_order(self):
        # Reverse lexical path order without changing the document's reading order.
        paths = {p.replace('acceptance.md', 'z.md').replace('settings.md', 'a.md'):
                 b.replace(b'acceptance.md', b'z.md').replace(b'settings.md', b'a.md')
                 for p, b in self.clean.items()}
        edit(paths, 'docs/example/z.md', '# Acceptance', '# Z')
        edit(paths, 'docs/example/a.md', '# Settings', '# A')
        refresh(paths)
        result = self.context(paths=paths)
        sources = result.manifest['ranges']
        self.assertEqual([item['path'] for item in sources], ['docs/example/z.md', 'docs/example/a.md'])

    def test_fact_key_and_owner_name_are_descriptive_links(self):
        for label in ("default", "commit capacity", "commit_max_documents", "Commit capacity"):
            paths = self.clean.copy()
            edit(paths, SETTINGS, 'Its provisional default borrows the [default]', f'Its provisional default borrows the [{label}]')
            self.assertTrue(s.check(refresh(paths)).ok, label)

    def test_mismatched_literal_and_equivalent_measurement_are_refused(self):
        for label in ("2048", "1.024", "1024 documents"):
            self.paths = self.clean.copy()
            edit(self.paths, SETTINGS, 'Its provisional default borrows the [default]', f'Its provisional default borrows the [{label}]')
            self.red_green("D10")
        self.paths = self.clean.copy()
        edit(self.paths, ACCEPTANCE, 'Its [default](settings.md#log-group-limit-default)', 'Its [4194304 bytes](settings.md#log-group-limit-default)')
        self.red_green("D10")

    def test_arbitrary_literal_values_have_no_reserved_meanings(self):
        for literal in ('pending', 'required', 'null', 'a: b', '"Quoted"', '1.234,5', '[x, y]'):
            paths = self.clean.copy()
            edit(paths, SETTINGS, '| 4 MiB |', f'| {literal} |')
            self.assertTrue(s.check(refresh(paths)).ok, literal)
        self.assertNotEqual(s.normalize_literal('1.024', corpus(self.clean).contract), '1024')

    def test_requirement_needs_linked_acceptance_test(self):
        edit(self.paths, ACCEPTANCE, '**Tests:** [Stale request](#test-stale-revision).', '**Tests:** None.')
        self.red_green("D11")

    def test_acceptance_test_needs_linked_requirement(self):
        edit(self.paths, ACCEPTANCE, '**Requirements:** [Stale-revision requirement](#req-stale-revision).', '**Requirements:** None.')
        self.red_green("D28")

    def test_traceability_is_reciprocal(self):
        edit(self.paths, ACCEPTANCE, '**Tests:** [Stale request](#test-stale-revision).', '**Tests:** None.')
        self.red_green("D29")

    def test_first_use_requires_direct_home_link(self):
        edit(self.paths, ACCEPTANCE, 'The [writer](#writer) performs', 'The writer performs')
        self.red_green("D12")

    def test_later_link_does_not_satisfy_first_use_in_same_paragraph(self):
        edit(self.paths, ACCEPTANCE, 'The [writer](#writer) performs', 'The writer asks the [writer](#writer) and performs')
        self.red_green("D12")

    def test_repeated_uses_before_home_share_level_two_first_use_scope(self):
        edit(self.paths, ACCEPTANCE, 'defines the refusal.',
             'defines the refusal. The writer refuses it.\n\n### More detail\n\nThe writer retains it.')
        self.assertNotIn('D12', self.codes())
        self.assertEqual(s.link_missing(corpus(self.paths)), {})

    def test_repeated_uses_of_home_in_another_document_share_first_use_scope(self):
        other = 'docs/other.md'
        def add_document(value):
            document = copy.deepcopy(value['documents'][0])
            document.update(id='other', status='draft', scenarios=[],
                            navigation={'path': 'docs/generated/other.md'},
                            sections=[{'id': 'main', 'path': other, 'anchor': 'other',
                                       'roles': ['tour', 'mechanism', 'requirements', 'decisions', 'questions', 'reference', 'acceptance'],
                                       'summary': 'Follow requests across document boundaries.',
                                       'prerequisites': [], 'explanatory_dependencies': []}])
            document.pop('approval')
            value['documents'].append(document)
            value['inventory'].append({'path': other, 'kind': 'specification'})
        metadata(self.paths, s.JSON_PATHS[1], add_document)
        metadata(self.paths, s.JSON_PATHS[0], lambda v: v['entities']['example.writer']['scope'].append('other'))
        self.paths[other] = b'<a id="other"></a>\n# Other\n\nThe [writer](example/acceptance.md#writer) checks it. The writer retains it.\n\n### Detail\n\nThe writer refuses it.\n'
        checked = s.check(refresh(self.paths))
        self.assertTrue(checked.ok, checked.errors)
        self.assertEqual(s.link_missing(corpus(self.paths)), {})
        self.paths[other] += b'\n## Next use\n\nThe writer checks it. The writer retains it.\n'
        self.assertEqual(len(self.codes_for('D12')), 1)
        self.paths.update(s.link_missing(corpus(self.paths)))
        self.assertIn(b'The [writer](example/acceptance.md#writer) checks it. The writer retains it.', self.paths[other])
        self.assertNotIn('D12', self.codes())
        self.assertEqual(s.link_missing(corpus(self.paths)), {})

    def test_link_preserves_authored_repeated_links_before_and_after_home(self):
        for path, target in ((ACCEPTANCE, '#writer'), (SETTINGS, 'acceptance.md#writer')):
            with self.subTest(path=path):
                self.paths = self.clean.copy()
                extra = f'\n## More uses\n\nwriter and [writer]({target}) and [writer]({target}).\n'
                if path == ACCEPTANCE:
                    edit(self.paths, path, '<a id="writer"></a>', extra + '\n<a id="writer"></a>')
                else:
                    self.paths[path] += extra.encode()
                self.paths.update(s.link_missing(corpus(self.paths)))
                self.assertIn(f'[writer]({target}) and [writer]({target}) and [writer]({target}).'.encode(), self.paths[path])
                self.assertEqual(s.link_missing(corpus(self.paths)), {})

    def test_subsections_share_level_two_first_use_scope(self):
        edit(self.paths, ACCEPTANCE, '### Relations', 'The [writer](#writer) checks it.\n\n### More\n\nThe writer refuses it.\n\n#### Detail\n\nThe writer retains it.\n\n### Relations')
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_level_two_sections_restart_first_use(self):
        self.paths[ACCEPTANCE] += b'\n<a id="another"></a>\n## Another\n\nThe writer refuses it.\n'
        self.red_green('D12')

    def test_heading_mentions_do_not_license_body_uses(self):
        edit(self.paths, ACCEPTANCE, '### Relations', '### Writer behavior\n\nThe writer refuses it.\n\n### Relations')
        errors = s.check(corpus(self.paths)).errors
        uses = [d for d in errors if d.code == 'D12']
        self.assertEqual(len(uses), 1)
        self.assertEqual(uses[0].line, self.paths[ACCEPTANCE].decode().splitlines().index('The writer refuses it.') + 1)
        edit(self.paths, ACCEPTANCE, 'The writer refuses it.', 'The [writer](#writer) refuses it.')
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_links_in_headings_are_refused(self):
        edit(self.paths, ACCEPTANCE, '### Relations', '### [Writer](#writer) relations')
        self.red_green('D33')

    def test_heading_text_still_refuses_rejected_names(self):
        edit(self.paths, ACCEPTANCE, '### Relations', '### Acceptance gate')
        self.red_green('D13')

    def test_table_links_may_repeat_after_the_home(self):
        edit(self.paths, ACCEPTANCE, '### Relations', '### Mentions\n\n| Use | Meaning |\n|---|---|\n| [Writer](#writer) | First use here |\n| Writer | Repeated use |\n\n### Relations')
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_numbered_headings_are_refused_without_changing_anchors(self):
        for prefix in ('1. ', '4.1 ', '4.1.2 ', '1\\. ', '§ ', '§4.1 '):
            with self.subTest(prefix=prefix):
                self.paths = self.clean.copy()
                edit(self.paths, ACCEPTANCE, '## Writer', '## ' + prefix + 'Writer')
                self.assertIn('D32', self.codes())
                edit(self.paths, ACCEPTANCE, '## ' + prefix + 'Writer', '## Writer')
                self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_unnumbered_heading_can_start_with_a_quantity(self):
        edit(self.paths, ACCEPTANCE, '### Relations', '### 4 workers')
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_acceptance_case_is_identified_by_its_permanent_anchor(self):
        edit(self.paths, ACCEPTANCE, '### Acceptance test: stale request', '### Stale request')
        c = refresh(self.paths)
        self.assertEqual(c.declarations['example-demo#test-stale-revision']['kind'], 'Acceptance test')
        edit(self.paths, ACCEPTANCE, '**Requirements:** [Stale-revision requirement](#req-stale-revision).', '**Requirements:** None.')
        self.assertIn('D28', self.codes())

    def test_wrong_target_is_not_a_home_link(self):
        edit(self.paths, ACCEPTANCE, '[writer](#writer)', '[writer](#acceptance-section)')
        self.red_green("D12")

    def test_rejected_forms_are_diagnosed(self):
        edit(self.paths, ACCEPTANCE, 'defines the refusal.', 'defines the acceptance gate.')
        self.red_green("D13")

    def test_structured_symbols_obey_compiled_naming_rule(self):
        metadata(self.paths, s.JSON_PATHS[0], lambda v: v["entities"]["example.call-capacity"].update(symbols=["BadName"]))
        self.red_green("D14")

    def test_malformed_naming_patterns_are_input_errors(self):
        metadata(self.paths, s.JSON_PATHS[0], lambda v: v["naming_rules"][0].update(pattern="["))
        self.red_green("D02")

    def test_required_document_roles_are_not_optional_for_approval(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v["documents"][0]["sections"][1]["roles"].remove("reference"))
        self.red_green("D15")

    def test_forward_prerequisite_requires_direct_link(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v["documents"][0]["sections"][0].update(prerequisites=["example-demo#settings"]))
        self.red_green("D16")
        edit(self.paths, ACCEPTANCE, 'This tour follows', 'See [settings](settings.md#settings-section).\nThis tour follows')
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_generated_navigation_and_attributes_are_freshness_checked(self):
        self.paths["docs/generated/example-demo.md"] += b"Manual edit\n"
        self.red_green("D17")
        self.assertTrue(s.check(refresh(self.paths)).ok)
        self.assertIn(b'linguist-generated=true', self.paths['.gitattributes'])
        self.assertEqual(s.generate_navigation(corpus(self.paths)), s.generate_navigation(corpus(self.paths)))

    def test_procedure_needs_label_and_two_direct_actions(self):
        edit(self.paths, ACCEPTANCE, '**Procedure: demonstrate a stale revision**', '**Demonstration**')
        self.red_green("D18")
        self.paths = self.clean.copy()
        edit(self.paths, ACCEPTANCE, '2. **Complete another write.**', '- **Complete another write.**')
        edit(self.paths, ACCEPTANCE, '3. **Submit the prepared request.**', '- **Submit the prepared request.**')
        self.red_green("D18")

    def test_operator_questions_are_not_specification_procedures(self):
        edit(self.paths, SETTINGS, 'The fixture author must resolve the candidate capacity before adoption.', '### 1\\. Which option applies?\n\n1. **First choice.**\n2. Second choice.\n\n**Answer like so:**\n\n```text\n1. 1\n```')
        c = corpus(self.paths)
        diagnostics = s.Diagnostics()
        s.check_prose(c, c.markdown[SETTINGS], diagnostics)
        self.assertIn('D18', {d.code for d in diagnostics.errors})
        # Operator-facing question formatting does not apply inside specifications.
        self.assertIn('D32', self.codes())

    def test_unresolved_contract_blocks_approval(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v["documents"][0].update(unresolved_contracts=["example-demo#fixture-decision"]))
        self.red_green("D21")

    def test_fixture_authority_diagnostic_names_the_production_fix(self):
        result = s.check(s.load_corpus(s.Snapshot.from_mapping(self.clean)))
        self.assertTrue(any("authority 'fixture' is accepted only in fixture mode; use operator or delegated" in d.message
                            for d in result.errors), result.errors)

    def test_fixture_approval_does_not_authorize_production(self):
        c = s.load_corpus(replace(s.Snapshot.from_mapping(self.paths), fixture=False))
        self.assertIn("D02", {d.code for d in s.check(c).errors})
        self.assertTrue(s.check(corpus(self.clean)).ok)

    def test_failure_declaration_requires_each_field(self):
        for field_name in corpus(self.paths).contract["failure_fields"]:
            self.paths = self.clean.copy()
            edit(self.paths, ACCEPTANCE, f'**{field_name}:**', f'**Omitted {field_name}:**')
            self.red_green("D30")

    def test_missing_recovery_can_be_explicit_and_explained(self):
        edit(self.paths, ACCEPTANCE, '**Recovery:** Read current state and prepare a new request.', '**Recovery:** none. This fixture cannot recover.')
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_literal_examples_need_adjacent_links_for_each_block(self):
        new = '```text\nwriter\n```\n\n**Entities in this example:** [Writer](#writer).\n\n'
        edit(self.paths, ACCEPTANCE, '**Procedure: demonstrate', new + '**Procedure: demonstrate')
        self.assertTrue(s.check(refresh(self.paths)).ok)
        edit(self.paths, ACCEPTANCE, '**Entities in this example:** [Writer](#writer).', '**Unrelated:** Writer.')
        self.red_green("D12")

    def test_warnings_do_not_fail_a_valid_structural_gate(self):
        extra = ' '.join(['word'] * 29) + '.\n\n' + ' '.join(['Short.'] * 7) + '\n\n42 is shown.\n'
        edit(self.paths, SETTINGS, 'The fixture author must resolve the candidate capacity before adoption.', 'The fixture author must resolve the candidate capacity before adoption.\n\n' + extra)
        c = refresh(self.paths)
        d = s.check(c)
        self.assertTrue(d.ok)
        self.assertTrue({'W01', 'W02'} <= {item.code for item in d.warnings})
        self.assertEqual(d.to_dict(), s.check(c).to_dict())

    def test_ambiguous_registered_phrase_warns_instead_of_guessing(self):
        metadata(self.paths, s.JSON_PATHS[0], lambda v: v['entities']['example.call-capacity']['forms'].append('commit capacity'))
        c = corpus(self.paths)
        diagnostics = s.check(c)
        self.assertTrue(diagnostics.ok, diagnostics.errors)
        self.assertIn('W04', {d.code for d in diagnostics.warnings})
        self.assertNotIn('D12', {d.code for d in diagnostics.errors})
        self.assertEqual(s.link_missing(c), {})
        edit(self.paths, SETTINGS, 'Commit capacity bounds', '[Commit capacity](#commit-capacity) bounds')
        diagnostics = s.check(refresh(self.paths))
        self.assertTrue(diagnostics.ok, diagnostics.errors)
        linked_line = self.paths[SETTINGS].decode().splitlines().index('[Commit capacity](#commit-capacity) bounds documents in one commit.') + 1
        self.assertFalse(any(d.code == 'W04' and d.path == SETTINGS and d.line == linked_line
                             for d in diagnostics.warnings))

    def test_unambiguous_registered_form_and_symbol_require_home_links(self):
        for text in ('writer', 'commit_max_documents'):
            with self.subTest(text=text):
                paths = self.clean.copy()
                paths[ACCEPTANCE] += f'\n<a id="use"></a>\n## Use\n\n{text}\n'.encode()
                diagnostics = s.check(corpus(paths))
                self.assertEqual({d.code for d in diagnostics.errors}, {'D12'})
                self.assertNotIn('W04', {d.code for d in diagnostics.warnings})
                outputs = s.link_missing(corpus(paths))
                if text == 'writer':
                    self.assertIn('[writer](#writer)', outputs[ACCEPTANCE].decode())
                    paths.update(outputs)
                else:
                    self.assertEqual(outputs, {})  # Code symbols need an author link.
                    edit(paths, ACCEPTANCE, '\ncommit_max_documents\n',
                         '\n[commit_max_documents](settings.md#commit-capacity)\n')
                self.assertTrue(s.check(refresh(paths)).ok)

    def test_context_contains_entire_registry_exact_bytes_and_unique_ranges(self):
        ctx = self.context()
        self.assertEqual(ctx.size_bytes, len(ctx.content))
        self.assertEqual(ctx.manifest['size_bytes'], len(ctx.content))
        self.assertIn(b'example.call-capacity', ctx.content)
        ranges = ctx.manifest['ranges']
        for a, b in zip(ranges, ranges[1:]):
            self.assertTrue(a['path'] != b['path'] or a['end'] < b['start'])
        self.assertIn('complete-registry', ctx.manifest['included'])

    def test_context_rejects_unknown_selector_and_missing_scope(self):
        self.context_error('D06', {'version': 1, 'sections': ['example-demo#missing']})
        self.context_error('D02', {'version': 1, 'sections': []})

    def test_context_dependencies_expand_transitively_and_deduplicate_cycles(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'][1]['explanatory_dependencies'].append({'section': 'example-demo#acceptance', 'reason': 'Demonstrate a cycle.'}))
        refresh(self.paths)
        ctx = self.context()
        self.assertIn('example-demo#settings', ctx.manifest['included'])
        self.assertEqual(len(ctx.manifest['ranges']), 2)

    def test_parent_selection_expands_nested_registered_dependencies(self):
        # Only the nested section declares the external dependency. Exercise both
        # snapshots: comparison tests can select the same parent subtree in base.
        self.paths[ACCEPTANCE] += b'\n<a id="nested"></a>\n## Nested operation\n\nRead its recovery explanation.\n'
        self.paths[SETTINGS] += b'\n<a id="recovery"></a>\n## Recovery explanation\n\nResolve the request before resubmission.\n'
        def register(value):
            doc = value['documents'][0]
            doc.update(status='draft')
            del doc['approval']
            doc['sections'][0]['explanatory_dependencies'] = []
            doc['sections'].extend([
                dict(id='nested', path=ACCEPTANCE, anchor='nested', roles=[],
                     summary='Explain recovery needs.', prerequisites=[], explanatory_dependencies=[
                         dict(section='example-demo#recovery', reason='Explain request recovery.')]),
                dict(id='recovery', path=SETTINGS, anchor='recovery', roles=[],
                     summary='Recover a request.', prerequisites=[], explanatory_dependencies=[])])
        metadata(self.paths, s.JSON_PATHS[1], register)
        refresh(self.paths)
        for label in ('candidate', 'base'):
            with self.subTest(label=label):
                ctx = self.context(dict(version=1, sections=['example-demo#acceptance'], label=label))
                identity = ('base:' if label == 'base' else '') + 'example-demo#recovery'
                self.assertIn(identity, ctx.manifest['included'])
                self.assertTrue(any(r['label'] == label and identity in r['identities']
                                    for r in ctx.manifest['ranges']))

    def test_base_acceptance_selects_base_approval_and_its_dependencies(self):
        # The approval is outside the acceptance subtree and differs in candidate.
        def register(value):
            doc = value['documents'][0]
            doc['sections'][0]['explanatory_dependencies'] = []
            doc['sections'].extend([
                dict(id='decision', path=SETTINGS, anchor='fixture-decision', roles=[],
                     summary='Record approval authority.', prerequisites=[], explanatory_dependencies=[
                         dict(section='example-demo#questions', reason='Qualify this approval.')]),
                dict(id='questions', path=SETTINGS, anchor='open-questions', roles=[],
                     summary='Qualify candidate capacity.', prerequisites=[], explanatory_dependencies=[])])
        metadata(self.paths, s.JSON_PATHS[1], register)
        # Do not select the whole settings chapter incidentally through entities.
        edit(self.paths, SETTINGS, '**Reason:** It covers homes, literal values, shared defaults and [acceptance](acceptance.md#acceptance) links.',
             '**Reason:** Retain the base approval evidence.')
        base = refresh(self.paths)
        edit(self.paths, SETTINGS, 'Retain the base approval evidence.', 'Use the candidate approval evidence.')
        edit(self.paths, ACCEPTANCE, '**Result:** Return `Conflict`', '**Result:** Report `Conflict`')
        candidate = refresh(self.paths)
        candidate.base = base
        ctx = s.select_context(candidate, dict(version=1, sections=['example-demo#questions'],
            required_test_reviews=['example-demo#test-stale-revision']))
        for selector in ('fixture-decision', 'questions'):
            self.assertIn('base:example-demo#' + selector, ctx.manifest['included'])
        decision = next(r for r in ctx.manifest['ranges']
                        if r['label'] == 'base' and 'base:example-demo#fixture-decision' in r['identities'])
        source = base.markdown[decision['path']].range_bytes(decision['start'], decision['end'])
        self.assertIn(b'Retain the base approval evidence.', source)
        self.assertNotIn(b'Use the candidate approval evidence.', source)

    def test_automatic_decisions_expand_homes_and_dependencies_until_closure(self):
        for mode in ('approval', 'removal', 'approval-chain'):
            with self.subTest(mode=mode):
                self.paths = self.clean.copy()
                self.paths[SETTINGS] += b'\n<a id="selection"></a>\n## Selection\n\nStart with this narrow assignment.\n'
                edit(self.paths, SETTINGS, '**Reason:** It covers homes, literal values, shared defaults and [acceptance](acceptance.md#acceptance) links.',
                     '**Reason:** Use [commit capacity](#commit-capacity) to explain the selected policy.')
                def sections(value):
                    doc = value['documents'][0]
                    doc['sections'].extend([
                        dict(id=identity, path=SETTINGS, anchor=anchor, roles=[], summary=summary,
                             prerequisites=[], explanatory_dependencies=deps)
                        for identity, anchor, summary, deps in (
                            ('selection', 'selection', 'Start a narrow assignment.', []),
                            ('decision', 'fixture-decision', 'Record the approval authority.',
                             [dict(section='example-demo#questions', reason='Explain recovery qualification.')]),
                            ('questions', 'open-questions', 'Qualify candidate capacity.',
                             [dict(section='example-demo#reference', reason='Read supporting evidence.')]),
                            ('reference', 'reference', 'Locate refusal evidence.',
                             [dict(section='example-demo#decision', reason='Return to the governing choice.')]))])
                    if mode == 'removal':
                        doc['status'] = 'draft'
                        del doc['approval']
                    elif mode == 'approval-chain':
                        doc['approval']['decision'] = 'authority#decision'
                        value['inventory'].append(dict(path='docs/example/authority.md', kind='specification'))
                        value['documents'].append(dict(
                            id='authority', title='Authority', status='approved',
                            approval=dict(authority='fixture', decision='example-demo#fixture-decision'),
                            purpose='Record delegated approval.', audience='Authors.', scope='One approval.', non_goals='Other policies.',
                            navigation=dict(path='docs/generated/authority.md'), scenarios=[],
                            sections=[dict(id='main', path='docs/example/authority.md', anchor='authority-section',
                                           roles=corpus(self.clean).contract['roles'], summary='Find delegated approval evidence.',
                                           prerequisites=[], explanatory_dependencies=[])]))
                metadata(self.paths, s.JSON_PATHS[1], sections)
                if mode == 'approval-chain':
                    self.paths['docs/example/authority.md'] = b'<a id="authority-section"></a>\n# Authority\n\nDelegated approval applies here.\n\n<a id="decision"></a>\n## Decision\n\nUse the declared approval source.\n'
                refresh(self.paths)
                assignment = dict(version=1, sections=['example-demo#selection'])
                if mode == 'removal':
                    assignment['removal_decisions'] = {'example-demo#req-removed': 'example-demo#fixture-decision'}
                ctx = self.context(assignment)
                for identity in ('example-demo#questions', 'example-demo#reference', 'example.commit-capacity'):
                    self.assertIn(identity, ctx.manifest['included'])
                if mode == 'approval-chain':
                    self.assertIn('authority#decision', ctx.manifest['included'])
                self.assertIn(b'Qualify candidate capacity', ctx.content)

    def test_added_home_selects_owning_document_approval_and_decision_dependencies(self):
        def separate_documents(value):
            doc = value['documents'][0]
            doc.update(status='draft', scenarios=[], gaps=corpus(self.clean).contract['roles'])
            del doc['approval']
            settings = doc['sections'].pop()
            doc['sections'][0]['explanatory_dependencies'] = []
            authority = copy.deepcopy(doc)
            authority.update(id='settings', title='Settings authority', status='approved',
                             approval=dict(authority='fixture', decision='settings#fixture-decision'),
                             navigation=dict(path='docs/generated/settings.md'),
                             sections=[settings, dict(id='decision', path=SETTINGS, anchor='fixture-decision',
                                 roles=[], summary='Record approval authority.', prerequisites=[],
                                 explanatory_dependencies=[dict(section='settings#questions', reason='Qualify this approval.')]),
                                 dict(id='questions', path=SETTINGS, anchor='open-questions', roles=[],
                                      summary='Qualify candidate capacity.', prerequisites=[], explanatory_dependencies=[])])
            settings.update(prerequisites=[], roles=corpus(self.clean).contract['roles'])
            value['documents'].append(authority)
            doc['sections'].append(dict(id='writer-only', path=ACCEPTANCE, anchor='writer', roles=[],
                summary='Select the writer policy.', prerequisites=[], explanatory_dependencies=[]))
        metadata(self.paths, s.JSON_PATHS[1], separate_documents)
        def move_homes(value):
            for entity in value['entities'].values():
                entity['scope'].append('settings')
                if entity['home']['section'] == 'example-demo#settings':
                    entity['home']['section'] = 'settings#settings'
        metadata(self.paths, s.JSON_PATHS[0], move_homes)
        edit(self.paths, SETTINGS, '**Reason:** It covers homes, literal values, shared defaults and [acceptance](acceptance.md#acceptance) links.',
             '**Reason:** Approval uses [call capacity](#call-capacity).')
        edit(self.paths, ACCEPTANCE, 'The writer processes write requests.',
             'The writer processes write requests using [commit capacity](settings.md#commit-capacity).')
        refresh(self.paths)
        ctx = self.context(dict(version=1, sections=['example-demo#writer-only']))
        self.assertIn('settings#fixture-decision', ctx.manifest['included'])
        self.assertIn('settings#questions', ctx.manifest['included'])
        self.assertIn('example.call-capacity', ctx.manifest['included'])
        # The added Acceptance home links a byte policy, but its links do not expand homes.
        self.assertNotIn('example.log-group-limit', ctx.manifest['included'])

    def test_ordinary_links_in_added_home_do_not_expand_context(self):
        # Narrow the assigned range to Writer. Its home links Acceptance, which is
        # registered but must not join source context merely because it is linked.
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'].append(dict(id='writer-only', path=ACCEPTANCE, anchor='writer', roles=[], summary='Writer alone.', prerequisites=[], explanatory_dependencies=[])))
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'][0].update(explanatory_dependencies=[]))
        refresh(self.paths)
        ctx = self.context({'version': 1, 'sections': ['example-demo#writer-only']})
        self.assertIn('example.acceptance', ctx.manifest['inclusion_reasons'])
        self.assertIn('example.writer', ctx.manifest['included'])
        # The selected writer section actually uses Acceptance, so its home belongs.
        # A second ordinary link in that added home (the byte-policy setting) does not.
        self.assertNotIn('example.log-group-limit', ctx.manifest['inclusion_reasons'])

    def test_context_refuses_omission_stale_baseline_budget_and_missing_review_coverage(self):
        assignment = {'version': 1, 'sections': ['example-demo#acceptance']}
        self.context_error('D24', dict(assignment, baseline='wrong'))
        self.context_error('D25', dict(assignment, budget_bytes=1))
        self.context_error('D26', dict(assignment, review_plan=[{'responsibilities': ['technical']}]))

    def test_assignment_rejects_removed_documentation_budget_alias(self):
        self.context_error('D02', {'version': 1, 'sections': ['example-demo#acceptance'], 'available_bytes': 100})

    def test_assignment_rejects_removed_caller_pack_inventory(self):
        assignment = {'version': 1, 'sections': ['example-demo#acceptance']}
        ctx = self.context(assignment)
        pack = dict(baseline=ctx.manifest['baseline'], registry_digest=ctx.manifest['registry_digest'], included=[])
        self.context_error('D02', dict(assignment, pack=pack))

    def test_one_generalist_can_cover_all_review_responsibilities(self):
        ctx = self.context({'version': 1, 'sections': ['example-demo#acceptance'], 'review_plan': [{'id': 'generalist', 'responsibilities': corpus(self.paths).contract['review_responsibilities']}]})
        self.assertGreater(ctx.size_bytes, 0)

    def test_changed_fact_and_qualification_select_unchanged_linked_tests(self):
        base = corpus(self.paths)
        # The requirement explicitly references its canonical fact.
        edit(self.paths, ACCEPTANCE, '**Condition:** A request', '**Condition:** The [default](settings.md#commit-capacity-default) applies. A request')
        base = refresh(self.paths)
        for before, after in (('| 1,024 |', '| 2,048 |'), ('| 1,024 | provisional', '| 1,024 | specified'), ('Qualify the selected capacity', 'Inspect the selected capacity')):
            changed = self.paths.copy()
            edit(changed, SETTINGS, before, after)
            report = s.requirement_changes(base, corpus(changed))
            self.assertEqual(report.changes[0]['tests'], ['example-demo#test-stale-revision'])
            self.assertEqual(report.changes[0]['changed_facts'][0]['id'], 'example.commit-capacity#default')

    def test_changed_requirement_requires_test_review_input(self):
        base = corpus(self.paths)
        edit(self.paths, ACCEPTANCE, '**Result:** Return `Conflict`', '**Result:** Report `Conflict`')
        candidate = corpus(self.paths)
        self.assertIn('D31', {d.code for d in s.check(candidate, base).errors})
        candidate.assignment = {'required_test_reviews': ['example-demo#test-stale-revision']}
        self.assertNotIn('D31', {d.code for d in s.check(candidate, base).errors})

    def test_removed_requirement_requires_resolving_decision(self):
        base = corpus(self.paths)
        edit(self.paths, ACCEPTANCE, '### Requirement: stale-revision', '### Former stale-revision')
        candidate = corpus(self.paths)
        self.assertIn('D22', {d.code for d in s.check(candidate, base).errors})
        candidate.assignment = {'removal_decisions': {'example-demo#req-stale-revision': 'example-demo#fixture-decision'}, 'required_test_reviews': ['example-demo#test-stale-revision']}
        self.assertNotIn('D22', {d.code for d in s.check(candidate, base).errors})

    def test_single_file_navigation_region_preserves_authored_source(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0].update(navigation={'path': ACCEPTANCE, 'region': 'example-demo'}))
        del self.paths['docs/generated/example-demo.md']
        self.paths[ACCEPTANCE] += ('\n' + s.START.format(document='example-demo') + '\nold\n' + s.END + '\n').encode()
        c = refresh(self.paths)
        self.assertTrue(s.check(c).ok)
        self.assertIn(b'## Writer', self.paths[ACCEPTANCE])
        self.assertEqual(len(c.facts), 3)

    def test_generated_regions_cannot_supply_fact_homes(self):
        edit(self.paths, SETTINGS, '<a id="log-group-limit"></a>', s.START.format(document='example-demo') + '\n<a id="log-group-limit"></a>')
        self.paths[SETTINGS] += ('\n' + s.END + '\n').encode()
        self.red_green('D04')


    def test_all_declared_metadata_types_fail_visibly_instead_of_crashing(self):
        probes = 0
        for path in s.JSON_PATHS:
            original = json.loads(self.clean[path])
            slots = []
            def visit(value, keys=()):
                if isinstance(value, dict):
                    for key, child in value.items():
                        slots.append(keys + (key,))
                        visit(child, keys + (key,))
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        slots.append(keys + (index,))
                        visit(child, keys + (index,))
            visit(original)
            for keys in slots:
                for wrong_type in (None, 0, {}, True):
                    value = copy.deepcopy(original)
                    target = value
                    for key in keys[:-1]:
                        target = target[key]
                    target[keys[-1]] = wrong_type
                    paths = self.clean.copy()
                    paths[path] = s.canonical(value)
                    result = s.check(corpus(paths))
                    self.assertFalse(result.ok, (path, keys, wrong_type))
                    probes += 1
        print(f'malformed metadata: {probes} invalid inputs rejected')
        self.assertTrue(s.check(corpus(self.clean)).ok)

    def test_ordinary_detail_prose_counts_but_attributed_quotation_does_not(self):
        long = ' '.join(['word'] * 29) + '.'
        edit(self.paths, SETTINGS, 'The fixture author must resolve the candidate capacity before adoption.', f'The fixture author must resolve the candidate capacity before adoption.\n\n> **Detail — explanation**\n>\n> {long}\n')
        c = refresh(self.paths)
        self.assertIn('W01', {d.code for d in s.check(c).warnings})
        quoted = self.clean.copy()
        edit(quoted, SETTINGS, 'The fixture author must resolve the candidate capacity before adoption.', f'The fixture author must resolve the candidate capacity before adoption.\n\n> {long}\n>\n> — A synthetic source\n')
        self.assertNotIn('W01', {d.code for d in s.check(refresh(quoted)).warnings})

    def test_blockquote_lazy_continuations_warn_with_source_lines_and_remedy(self):
        cases = (
            ('> **Detail — values**\n> First line.\nContinuation.\nAnother continuation.\n', [2, 3]),
            ('> A quotation.\nContinuation.\n> — Synthetic source\n', [1]),
            ('> > Nested quotation.\n> Nested continuation.\nOuter continuation.\n', [1, 2]),
            ('- > Quotation in a list.\n  Continuation.\n', [1]),
            ('> First line.\n> Continuation.\n>\n> Next paragraph.\n', []),
            ('> > Nested quotation.\n> > Continuation.\n', []),
            ('- > Quotation in a list.\n  > Continuation.\n', []),
            ('> Quotation.\n\nOrdinary paragraph.\n', []),
            ('> Quotation.\n\n    Literal text.\n', []),
            ('```markdown\n> Literal quotation.\nLiteral continuation.\n```\n', []),
            ('    > Literal quotation.\n    Literal continuation.\n', []),
            ('> ```text\n> Literal text.\n> ```\n', []),
        )
        for text, offsets in cases:
            with self.subTest(text=text):
                paths = self.clean.copy()
                paths[SETTINGS] += ('\n' + text).encode()
                first = len(paths[SETTINGS].decode().splitlines()) - len(text.splitlines()) + 1
                result = s.check(refresh(paths))
                warnings = [d for d in result.warnings if d.code == 'W07']
                self.assertTrue(result.ok, result.errors)
                self.assertEqual([(d.path, d.line) for d in warnings],
                                 [(SETTINGS, first + offset) for offset in offsets])
                self.assertTrue(all('prefix every line of the quote with >' in d.message for d in warnings))

    def test_link_and_generate_preserve_explicit_blockquote_prefixes(self):
        self.paths[ACCEPTANCE] += '\n<a id="ownership"></a>\n## Ownership\n\n> **Detail — ownership**\n> The writer handles this example.\n> More detail follows.\n>\n> A separate paragraph.\n'.encode()
        outputs = s.link_missing(corpus(self.paths))
        self.assertIn(b'> The [writer](#writer)', outputs[ACCEPTANCE])
        self.paths.update(outputs)
        linked = self.paths[ACCEPTANCE]
        c = refresh(self.paths)
        self.assertEqual(self.paths[ACCEPTANCE], linked)
        self.assertTrue(s.check(c).ok, s.check(c).errors)
        self.assertNotIn('W07', {d.code for d in s.check(c).warnings})
        self.assertEqual(s.link_missing(c), {})
        self.assertEqual(s.generate_navigation(c), s.generate_navigation(corpus(self.paths)))

    def test_sentence_counter_preserves_decimals_and_code_punctuation(self):
        tokens = s.MarkdownIt('commonmark').parse('Use 1.25 and `x. y! z?`. Next is 42. Done.')
        inline = next(t for t in tokens if t.type == 'inline')
        self.assertEqual(len(s.sentences(inline.children)), 3)

    def test_suspected_multi_action_and_long_cells_warn(self):
        edit(self.paths, ACCEPTANCE, '**Prepare a request.**', '**Read a request and then write its result.**')
        edit(self.paths, SETTINGS, 'bounds encoded bytes in one log group.', 'bounds encoded bytes in one log group.')
        edit(self.paths, SETTINGS, 'The fixture author must resolve the candidate capacity before adoption.', 'The fixture author must resolve the candidate capacity before adoption.\n\n| Name | Meaning |\n|---|---|\n| Example | ' + ' '.join(['word'] * 30) + ' |')
        c = refresh(self.paths)
        self.assertTrue(s.check(c).ok)
        self.assertIn('W05', {d.code for d in s.check(c).warnings})

    def test_unknown_table_columns_are_not_silently_ignored(self):
        edit(self.paths, SETTINGS, '| Key | Value | Status | Basis |', '| Key | Value | Status | Unknown |')
        self.red_green('D02')

    def implementation(self, value):
        self.paths[ACCEPTANCE] = self.paths[ACCEPTANCE].replace(b'**Method:** analysis.', b'**Method:** test.')
        self.paths[ACCEPTANCE] += ('\n**Implementation:** ' + value + '\n').encode()

    def test_implementation_links_resolve_files_and_leave_code_selectors_to_review(self):
        self.paths['tests/example.py'] = b'# Selector existence belongs to the later pass.\n'
        self.paths['tests/other.py'] = b'# Another test file.\n'
        self.implementation('[tests/example.py::Suite::test_refusal](../../tests/example.py), '
                            '[tests/other.py::test_other](../../tests/other.py)')
        self.assertTrue(s.check(refresh(self.paths)).ok)
        del self.paths['tests/other.py']
        self.red_green('D06')

    def test_implementation_accepts_framework_names_with_spaces(self):
        self.paths['tests/example.py'] = b'# synthetic test source\n'
        self.implementation('[tests/example.py::batch > accepts full name](../../tests/example.py)')
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_implementation_requires_only_file_and_selector_links(self):
        invalid = ('None; no executable yet.', '', 'tests/example.py::test_refusal',
                   '[Executable test](../../tests/example.py)',
                   '[tests/example.py::](../../tests/example.py)',
                   '[tests/example.py:: test_refusal](../../tests/example.py)',
                   '[tests/example.py::test_refusal ](../../tests/example.py)',
                   '[tests/example.py::test_refusal](../../tests/example.py#test_refusal)',
                   '[tests/example.py::test_refusal](../../tests/example.py?test=refusal)',
                   '[tests/example.py::test_refusal](https://example.com/test.py)',
                   '[tests/wrong.py::test_refusal](../../tests/example.py)',
                   '[tests/example.py::test_refusal](../../tests/example.py).',
                   '[tests/example.py::test_refusal](../../tests/example.py) and more',
                   '[tests/example.py::test_refusal](../../tests/example.py), prose',
                   '[tests/example.py::test_refusal](../../tests/example.py) '
                   '[tests/example.py::test_other](../../tests/example.py)')
        for value in invalid:
            with self.subTest(value=value):
                self.paths = self.clean.copy()
                self.paths['tests/example.py'] = b'def test_refusal(): pass\n'
                self.implementation(value)
                self.red_green('D02')

    def test_declared_dependency_requires_reason_and_known_section(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'][0]['explanatory_dependencies'][0].update(reason=''))
        self.red_green('D02')
        self.paths = self.clean.copy()
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0]['sections'][0]['explanatory_dependencies'][0].update(section='example-demo#absent'))
        self.red_green('D06')

    def test_absent_profile_is_not_replaced_by_local_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / 'writing.md'
            profile.write_text('# No machine-readable profile\n')
            with patch.object(s, 'PROFILE', profile):
                self.assertIn('D02', self.codes())
        self.assertTrue(s.check(corpus(self.paths)).ok)

    def test_context_review_plan_is_checked_without_spawning_reviewers(self):
        assignment = {'version': 1, 'sections': ['example-demo#acceptance'], 'review_plan': []}
        with self.assertRaises(s.SpecDocsError) as caught:
            self.context(assignment)
        errors = caught.exception.diagnostics.errors
        self.assertEqual(len([d for d in errors if d.code == 'D26']), 5)

    def test_context_applies_whole_scenario_and_changed_test_selectors(self):
        ctx = self.context({'version': 1, 'sections': ['example-demo#settings'], 'scenarios': ['example-demo#stale-revision'], 'required_test_reviews': ['example-demo#test-stale-revision'], 'label': 'candidate'})
        self.assertIn('example-demo#acceptance', ctx.manifest['included'])
        self.assertIn('example-demo#test-stale-revision', ctx.manifest['included'])
        self.assertEqual(ctx.manifest['label'], 'candidate')

    def test_runtime_and_dependency_mismatch_stop_without_a_fallback_parser(self):
        with patch('spec_docs.importlib.metadata.version', return_value='0.0'):
            with self.assertRaises(s.SpecDocsError) as caught:
                s.validate_runtime()
            self.assertEqual(caught.exception.exit_code, 2)
        s.validate_runtime()

    def test_declared_source_is_parsed_once_and_reused_by_all_operations(self):
        with patch('spec_docs.parse_markdown', wraps=s.parse_markdown) as parser:
            c = corpus(self.paths)
            s.check(c)
            s.generate_navigation(c)
            s.select_context(c, {'version': 1, 'sections': ['example-demo#acceptance']})
            paths = [call.args[0] for call in parser.call_args_list]
            self.assertEqual(paths.count(ACCEPTANCE), 1)
            self.assertEqual(paths.count(SETTINGS), 1)


    def test_change_review_context_contains_base_tests_and_changed_declarations(self):
        base = corpus(self.paths)
        edit(self.paths, ACCEPTANCE, '**Result:** Return `Conflict`', '**Result:** Report `Conflict`')
        candidate = refresh(self.paths)
        candidate.base = base
        assignment = {'version': 1, 'sections': ['example-demo#settings'], 'required_test_reviews': ['example-demo#test-stale-revision']}
        ctx = s.select_context(candidate, assignment)
        self.assertIn('base:example-demo#test-stale-revision', ctx.manifest['included'])
        self.assertIn('base:example.writer', ctx.manifest['included'])
        self.assertIn('example.writer', ctx.manifest['included'])
        self.assertIn(b'**Result:** Return `Conflict`', ctx.content)
        self.assertIn(b'**Result:** Report `Conflict`', ctx.content)
        self.assertIn('base_provenance', ctx.manifest)
        self.assertEqual(ctx.size_bytes, len(ctx.content))

    def test_malformed_context_fields_produce_diagnostics(self):
        for key, value in [('removal_decisions', []), ('removal_decisions', {'x': 1}), ('label', []), ('budget_bytes', True), ('review_plan', [{'responsibilities': [1]}]), ('pack', 0)]:
            assignment = {'version': 1, 'sections': ['example-demo#acceptance'], key: value}
            self.context_error('D02', assignment)

    def test_cross_document_value_links_obey_entity_scope(self):
        self.paths['docs/foreign.md'] = b'<a id="foreign"></a>\n# Foreign\n\nUse [1024](example/settings.md#commit-capacity-default).\n'
        def add_document(manifest):
            manifest['inventory'].append({'path': 'docs/foreign.md', 'kind': 'specification'})
            manifest['documents'].append(dict(id='foreign', title='Foreign', status='draft', purpose='Show scope.', audience='Readers.', scope='One example.', non_goals='Other examples.', navigation={'path': 'docs/generated/foreign.md'}, sections=[dict(id='main', path='docs/foreign.md', anchor='foreign', roles=corpus(self.clean).contract['roles'], summary='Scope example.', prerequisites=[], explanatory_dependencies=[])], scenarios=[]))
        metadata(self.paths, s.JSON_PATHS[1], add_document)
        self.red_green('D07')

    def test_reading_order_places_tour_before_mechanisms(self):
        def wrong_order(manifest):
            manifest['documents'][0]['sections'][0]['roles'].remove('tour')
            manifest['documents'][0]['sections'][1]['roles'].append('tour')
        metadata(self.paths, s.JSON_PATHS[1], wrong_order)
        self.red_green('D15')


class MinimalExampleTests(unittest.TestCase):
    def test_unstaged_chapter_rename_checks_candidate_paths_and_missing_declarations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = miniature()
            for path, content in paths.items():
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            subprocess.run(['git', 'init', '-q', directory], stdin=subprocess.DEVNULL, check=True)
            subprocess.run(['git', '-C', directory, 'add', '.'], stdin=subprocess.DEVNULL, check=True)
            old = 'docs/example/settings.md'
            new = 'docs/example/batch-limits.md'
            (root / old).rename(root / new)
            for path, content in paths.items():
                target = root / (new if path == old else path)
                target.write_text(content.decode().replace('settings.md', 'batch-limits.md').replace('# Settings\n', '# Batch limits\n'))
            c = s.load_corpus(s.Snapshot.from_git(root, fixture=True))
            self.assertTrue(s.check(c, _freshness=False).ok, s.check(c, _freshness=False).errors)
            (root / new).unlink()
            broken = s.check(s.load_corpus(s.Snapshot.from_git(root, fixture=True)), _freshness=False)
            self.assertIn('D27', {d.code for d in broken.errors})

    def test_checker_parses_under_the_minimum_supported_python_grammar(self):
        import ast
        ast.parse(Path(s.__file__).read_text(), feature_version=(3, 11))

    def test_every_ci_python_consumer_uses_the_locked_environment(self):
        root = Path(s.__file__).resolve().parents[3]
        workflow = (root / '.github/workflows/checks.yml').read_text()
        lock = 'skills/spec-writing/scripts/requirements.lock'
        self.assertIn('--require-hashes --only-binary=:all: --no-deps -r ' + lock, workflow)
        consumers = [line.strip() for line in workflow.splitlines() if 'run:' in line and
                     ('skills/pr-ready/scripts' in line or 'scripts/check_review_staging.py' in line)]
        self.assertTrue(consumers)
        for line in consumers:
            self.assertNotIn('python3 ', line)
            self.assertIn('.tmp/spec-docs-env/bin/python', line)
        self.assertLess(workflow.index(lock), min(workflow.index(line) for line in consumers))

    def test_published_example_is_the_checked_fixture_in_an_independent_repository(self):
        fixture = Path(__file__).parent / 'fixtures/minimal'
        paths = {p.relative_to(fixture).as_posix(): p.read_bytes() for p in fixture.rglob('*') if p.is_file()}
        chapter = (Path(s.__file__).resolve().parents[3] / 'docs/specs/spec-system/minimal-corpus.md').read_text()
        tokens = s.MarkdownIt('commonmark').parse(chapter)
        fenced = [t.content.encode() for t in tokens if t.type == 'fence' and t.info in ('json', 'markdown')]
        self.assertEqual(sorted(paths.values()), sorted(fenced))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in paths.items():
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            subprocess.run(['git', '-C', str(root), 'init', '-q'], stdin=subprocess.DEVNULL, check=True)
            result = subprocess.run([__import__('sys').executable, '-B', s.__file__, 'check', '--root', str(root)], stdin=subprocess.DEVNULL, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(b'0 errors', result.stdout)
            self.assertFalse((root / 'rules/writing.md').exists())

    def test_pre_adoption_base_has_no_requirements_but_normal_missing_metadata_fails(self):
        source = s.Snapshot.from_mapping({'README.md': '# Existing project\n'})
        base = s.load_corpus(source, comparison=True)
        self.assertEqual(base.declarations, {})
        self.assertTrue(s.check(base).ok)
        self.assertFalse(s.check(s.load_corpus(source)).ok)
        fixture = Path(__file__).parent / 'fixtures/minimal'
        paths = {p.relative_to(fixture).as_posix(): p.read_bytes() for p in fixture.rglob('*') if p.is_file()}
        candidate = s.load_corpus(s.Snapshot.from_mapping(paths, fixture=True))
        self.assertEqual([c['kind'] for c in s.requirement_changes(base, candidate).changes], ['new'])

    def test_documented_vocabulary_agrees_with_the_machine_contract(self):
        path = Path(s.__file__).resolve().parents[3] / 'docs/specs/spec-system/source-formats.md'
        text = re.sub(r'\[(`[^`]+`)\]\([^)]*\)', r'\1', path.read_text())
        contract = json.loads(s.REFERENCE.read_text())
        for key, values in contract.items():
            if isinstance(values, list) and key != 'group_separators':
                self.assertIn('| `' + key + '` | ' + ', '.join('`' + value + '`' for value in values) + ' |', text)
        for key, values in contract['relationship_targets'].items():
            self.assertIn('| `' + key + '` | ' + ', '.join('`' + value + '`' for value in values) + ' |', text)

    def test_valid_draft_skeleton_generates_before_registering_homes(self):
        paths = {'docs/ENTITIES.json': s.canonical(dict(version=1, entities={}, naming_rules=[])),
                 'docs/outline.md': b'<a id="outline"></a>\n# Draft outline\n\nA pending outline.\n'}
        paths['docs/DOCUMENTS.json'] = s.canonical(dict(version=1, inventory=[dict(path='docs/outline.md', kind='specification')], documents=[dict(id='outline', title='Outline', status='draft', purpose='Sketch the contract.', audience='Authors.', scope='Outline only.', non_goals='Implementation.', gaps=json.loads(s.REFERENCE.read_text())['roles'], navigation=dict(path='docs/generated/outline.md'), sections=[dict(id='main', path='docs/outline.md', anchor='outline', roles=[], summary='The draft skeleton.', prerequisites=[], explanatory_dependencies=[])], scenarios=[])]))
        paths.update(s.generate_navigation(s.load_corpus(paths)))
        self.assertTrue(s.check(s.load_corpus(paths)).ok)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.started = time.monotonic()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        for path, data in miniature().items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture: initial corpus')

    def tearDown(self):
        self.temp.cleanup()
        print(f'fixture {self.id()}: completed in {time.monotonic() - self.started:.3f}s')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], stdin=subprocess.DEVNULL, capture_output=True, check=True).stdout

    def test_repeated_sentence_diagnostic_never_echoes_credential_url(self):
        username, password = 'fixture' + '-user', 'fixture' + '-password'
        sentence = f'The synthetic endpoint https://{username}:{password}@example.invalid/path is used only for this example.'
        target = self.root / ACCEPTANCE
        target.write_text(target.read_text() + ('\n' + sentence + '\n') * 3)
        diagnostics = s.check(s.load_corpus(s.Snapshot.from_git(self.root, fixture=True)))
        repeated = [d for d in diagnostics.errors if d.code == 'D35']
        self.assertEqual(len(repeated), 1)
        self.assertEqual(repeated[0].path, ACCEPTANCE)
        self.assertGreater(repeated[0].line, 0)
        self.assertIn('3 times', repeated[0].message)
        self.assertIn('develop the example where introduced', repeated[0].message)
        outputs = [str(s.SpecDocsError(diagnostics)), json.dumps(diagnostics.to_dict())]
        for format_args in ([], ['--json']):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = s.main(['check', '--root', str(self.root), '--fixture', *format_args])
            self.assertEqual(status, 1)
            outputs.extend([stdout.getvalue(), stderr.getvalue()])
        self.assertFalse(any(value in output for value in (username, password, sentence) for output in outputs),
                         'source prose escaped into checker diagnostics')

    def test_rejected_urls_never_expose_credentials_in_diagnostics_or_cli(self):
        # Synthetic values are assembled at runtime and never printed by assertions.
        username, password = 'fixture' + '-user', 'fixture' + '-password'
        target = self.root / ACCEPTANCE
        target.write_text(target.read_text() + f'\n[Remote](ftp://{username}:{password}@example.invalid/file)\n')
        c = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        diagnostics = s.check(c)
        self.assertTrue(any(d.code == 'D06' for d in diagnostics.errors))
        outputs = [str(s.SpecDocsError(diagnostics)), json.dumps(diagnostics.to_dict())]
        for format_args in ([], ['--json']):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = s.main(['check', '--root', str(self.root), '--fixture', *format_args])
            self.assertEqual(status, 1)
            outputs.extend([stdout.getvalue(), stderr.getvalue()])
        self.assertFalse(any(value in output for value in (username, password) for output in outputs),
                         'credential-bearing destination escaped into checker diagnostics')

    def test_history_filter_covers_accepted_anchor_whitespace(self):
        target = self.root / ACCEPTANCE
        original = target.read_text()
        declaration = original[original.index('<a id="req-stale-revision"'):original.index('<a id="acceptance-stale-failure"')]
        for index, spacing in enumerate(('  ', '\t', ' \t ')):
            identity = f'req-spaced-history-{index}'
            spaced = declaration.replace('<a id="req-stale-revision"', f'<a{spacing}id="{identity}"')
            target.write_text(original + spaced)
            self.git('add', ACCEPTANCE)
            self.git('commit', '-qm', 'fixture: accepted spaced anchor')
            target.write_text(original)
            self.git('add', ACCEPTANCE)
            self.git('commit', '-qm', 'fixture: retire spaced identity')
            base = s.load_corpus(s.Snapshot.from_git(self.root, rev='HEAD', fixture=True))
            target.write_text(original + spaced)
            candidate = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
            self.assertTrue(any(d.code == 'D03' and identity in d.message
                                for d in s.check(candidate, base).errors), spacing)
            target.write_text(original)

    def test_writers_refuse_lock_contention(self):
        import fcntl
        lock = self.root / '.tmp/spec-docs.lock'
        lock.parent.mkdir()
        c = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        with lock.open('a+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(s.SpecDocsError, 'another spec-docs writer'):
                s.write_outputs(c, s.generate_navigation(c))
        s.write_outputs(c, s.generate_navigation(c))

    def test_writer_rechecks_destination_after_temporary_file_is_written(self):
        c = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        outputs = s.generate_navigation(c)
        target = self.root / 'docs/generated/example-demo.md'
        original = s.os.fdopen
        def edited(*args, **kwargs):
            stream = original(*args, **kwargs)
            if args[1] == 'wb':
                target.write_bytes(b'A concurrent destination edit.\n')
            return stream
        with patch.object(s.os, 'fdopen', side_effect=edited):
            with self.assertRaisesRegex(s.SpecDocsError, 'destination differs'):
                s.write_outputs(c, outputs)
        self.assertEqual(target.read_bytes(), b'A concurrent destination edit.\n')

    def test_link_replacement_rejects_concurrent_source_edits_and_symlinks(self):
        target = self.root / ACCEPTANCE
        target.write_text(target.read_text().replace('[writer](#writer)', 'writer'))
        c = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        outputs = s.link_missing(c)
        target.write_text(target.read_text() + '\nAn authored edit.\n')
        with self.assertRaisesRegex(s.SpecDocsError, 'authored destination differs'):
            s.write_outputs(c, outputs, repair=True)
        self.assertIn('An authored edit.', target.read_text())
        target.unlink()
        target.symlink_to(self.root / SETTINGS)
        with self.assertRaisesRegex(s.SpecDocsError, 'symlink destination'):
            s.write_outputs(c, outputs, repair=True)

    def test_link_pruning_command_uses_replacement_safety_and_is_idempotent(self):
        target = self.root / ACCEPTANCE
        target.write_text(target.read_text() + '\n[writer](#writer), [writer](#writer).\n')
        c = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        outputs = s.link_missing(c, prune_repeats=True)
        target.write_text(target.read_text() + '\nAn authored edit.\n')
        with self.assertRaisesRegex(s.SpecDocsError, 'authored destination differs'):
            s.write_outputs(c, outputs, repair=True)
        original = target.read_text()
        target.unlink()
        target.symlink_to(self.root / SETTINGS)
        with self.assertRaisesRegex(s.SpecDocsError, 'symlink destination'):
            s.write_outputs(c, outputs, repair=True)
        target.unlink()
        target.write_text(original)
        args = ['link', '--prune-repeats', '--root', str(self.root), '--fixture', '--json']
        for expected in ([ACCEPTANCE], []):
            with patch('builtins.print') as output:
                self.assertEqual(s.main(args), 0)
                self.assertEqual(json.loads(output.call_args[0][0])['linked'], expected)
        self.assertIn('writer, writer.', target.read_text())
        for command in ('check', 'generate', 'context'):
            with patch('builtins.print'):
                self.assertEqual(s.main([command, '--prune-repeats', '--root', str(self.root)]), 2)

    def test_link_command_writes_repairs_reports_remaining_errors_and_is_idempotent(self):
        target = self.root / ACCEPTANCE
        target.write_text(target.read_text().replace('[writer](#writer)', 'writer'))
        args = ['link', '--root', str(self.root), '--fixture', '--json']
        with patch('builtins.print') as output:
            self.assertEqual(s.main(args), 0)
            self.assertEqual(json.loads(output.call_args[0][0])['linked'], [ACCEPTANCE])
        self.assertIn('[writer](#writer)', target.read_text())
        with patch('builtins.print') as output:
            self.assertEqual(s.main(args), 0)
            self.assertEqual(json.loads(output.call_args[0][0])['linked'], [])
        target.write_text(target.read_text().replace('[writer](#writer)', 'writer') + '\n`writer`\n')
        with patch('builtins.print') as output:
            self.assertEqual(s.main(args), 1)
            result = json.loads(output.call_args[0][0])
            self.assertEqual(result['linked'], [ACCEPTANCE])
            self.assertTrue(any(d['code'] == 'D12' for d in result['errors']))
        for option in ('--staged', '--rev', '--base', '--assignment'):
            with patch('builtins.print'):
                extra = [option] if option == '--staged' else [option, 'HEAD']
                # --assignment is refused before reading its path.
                self.assertEqual(s.main(args + extra), 2)
        (self.root / s.JSON_PATHS[0]).unlink()
        with patch('builtins.print'):
            self.assertEqual(s.main(args), 2)

    def test_text_diagnostic_counts_agree_for_zero_one_and_many(self):
        target = self.root / ACCEPTANCE
        original = target.read_text()
        for command in ('check', 'link'):
            for count in (0, 1, 2):
                with self.subTest(command=command, count=count):
                    target.write_text(original + '\n`writer`\n' * count)
                    with patch('builtins.print') as output:
                        self.assertEqual(s.main([command, '--root', str(self.root), '--fixture']), int(count > 0))
                    noun = 'error' if count == 1 else 'errors'
                    self.assertIn(f'spec-docs: {count} {noun}, 0 warnings',
                                  [call.args[0] for call in output.call_args_list])
        target.write_text(original + '\n' + ' '.join(['word'] * 29) + '.\n')
        for command in ('check', 'link'):
            with self.subTest(command=command, warnings=1):
                with patch('builtins.print') as output:
                    self.assertEqual(s.main([command, '--root', str(self.root), '--fixture']), 0)
                self.assertIn('spec-docs: 0 errors, 1 warning',
                              [call.args[0] for call in output.call_args_list])

    def test_generation_replaces_stale_navigation_before_checking_freshness(self):
        target = self.root / 'docs/generated/example-demo.md'
        expected = target.read_bytes()
        target.write_bytes(expected + b'Stale manual output.\n')
        c = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        self.assertEqual({d.code for d in s.check(c).errors}, {'D17'})
        with patch('builtins.print'):
            self.assertEqual(s.main(['generate', '--root', str(self.root), '--fixture']), 0)
        self.assertEqual(target.read_bytes(), expected)
        self.assertTrue(s.check(s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))).ok)

    def test_literal_trace_examples_do_not_reserve_historical_identities(self):
        target = self.root / SETTINGS
        target.write_text(target.read_text() + '\n```markdown\n<a id="req-fenced-only"></a>\n### Requirement: example\n```\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture: literal identity example')
        target.write_text(target.read_text().split('\n```markdown')[0])
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture: retire literal example')
        base = s.load_corpus(s.Snapshot.from_git(self.root, rev='HEAD', fixture=True))
        source = self.root / ACCEPTANCE
        source.write_text(source.read_text().replace('req-stale-revision', 'req-fenced-only'))
        candidate = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        self.assertNotIn('D03', {d.code for d in s.check(candidate, base).errors})

    def test_retired_trace_identity_is_checked_against_base_history_only(self):
        # Retire both declarations without keeping tombstones in current source.
        target = self.root / ACCEPTANCE
        original = target.read_text()
        retired = original.replace('req-stale-revision', 'req-retired-replacement').replace(
            'test-stale-revision', 'test-retired-replacement')
        target.write_text(retired)
        manifest = self.root / s.JSON_PATHS[1]
        manifest.write_text(manifest.read_text().replace('stale-revision', 'retired-replacement'))
        # Keep the scenario identity consistent with the manifest.
        target.write_text(target.read_text().replace('id="stale-revision"', 'id="retired-replacement"'))
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture: retire identities')
        base = s.load_corpus(s.Snapshot.from_git(self.root, rev='HEAD', fixture=True))
        target.write_text(original)
        manifest.write_text(manifest.read_text().replace('retired-replacement', 'stale-revision'))
        candidate = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        self.assertNotIn('D03', {d.code for d in s.check(candidate).errors})
        errors = s.check(candidate, base).errors
        self.assertTrue(any(d.code == 'D03' and 'retired' in d.message for d in errors), errors)

    def test_retirement_includes_registration_without_anchor_edits(self):
        target = self.root / ACCEPTANCE
        original = target.read_text()
        manifest = self.root / s.JSON_PATHS[1]
        registered = manifest.read_bytes()
        value = json.loads(registered)
        value['inventory'] = [entry for entry in value['inventory'] if entry['path'] != ACCEPTANCE]
        value['inventory'].append(dict(path=ACCEPTANCE, kind='preserved'))
        value['documents'] = []
        manifest.write_bytes(s.canonical(value))
        self.git('checkout', '--orphan', 'adoption')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture: existing unregistered declarations')
        manifest.write_bytes(registered)
        self.git('add', s.JSON_PATHS[1])
        self.git('commit', '-qm', 'fixture: register without anchor edits')
        # Delete the registered source without adding any anchor lines.
        target.unlink()
        manifest.write_bytes(s.canonical(value))
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture: delete registered source')
        base = s.load_corpus(s.Snapshot.from_git(self.root, rev='HEAD', fixture=True))
        target.write_text(original)
        manifest.write_bytes(registered)
        candidate = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        errors = s.check(candidate, base).errors
        for identity in ('req-stale-revision', 'test-stale-revision'):
            self.assertTrue(any(d.code == 'D03' and identity in d.message for d in errors), errors)

    def test_retirement_includes_heading_only_requirement_promotion(self):
        target = self.root / ACCEPTANCE
        original = target.read_text()
        declaration = original[original.index('<a id="req-stale-revision"'):original.index('<a id="acceptance-stale-failure"')]
        promoted = declaration.replace('req-stale-revision', 'req-promoted-history')
        target.write_text(original + promoted.replace('### Requirement: stale-revision', '### Draft obligation'))
        self.git('add', ACCEPTANCE)
        self.git('commit', '-qm', 'fixture: anchored draft heading')
        target.write_text(original + promoted)
        self.git('add', ACCEPTANCE)
        self.git('commit', '-qm', 'fixture: promote heading without anchor edits')
        target.write_text(original)
        self.git('add', ACCEPTANCE)
        self.git('commit', '-qm', 'fixture: retire promoted requirement')
        base = s.load_corpus(s.Snapshot.from_git(self.root, rev='HEAD', fixture=True))
        target.write_text(original + promoted)
        candidate = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        self.assertNotIn('D03', {d.code for d in s.check(candidate).errors})
        self.assertTrue(any(d.code == 'D03' and 'req-promoted-history' in d.message
                            for d in s.check(candidate, base).errors))

    def test_interrupted_multioutput_generation_is_visible_and_regenerable(self):
        manifest_path = self.root / s.JSON_PATHS[1]
        manifest_value = json.loads(manifest_path.read_bytes())
        manifest_value['documents'][0]['purpose'] = 'An updated purpose.'
        manifest_value['documents'][0]['navigation']['path'] = 'docs/generated/new-demo.md'
        manifest_value['inventory'].append(dict(path='docs/generated/example-demo.md', kind='generated'))
        old_attributes = (self.root / '.gitattributes').read_bytes()
        manifest_path.write_bytes(s.canonical(manifest_value))
        c = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        outputs = s.generate_navigation(c)
        old = (self.root / 'docs/generated/example-demo.md').read_bytes()
        real_replace = s.os.replace
        count = 0
        def interrupted(source, destination):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('synthetic interrupted replacement')
            return real_replace(source, destination)
        with patch.object(s.os, 'replace', side_effect=interrupted):
            with self.assertRaisesRegex(s.SpecDocsError, 'interrupted replacement'):
                s.write_outputs(c, outputs)
        self.assertEqual((self.root / 'docs/generated/example-demo.md').read_bytes(), old)
        self.assertNotEqual((self.root / '.gitattributes').read_bytes(), old_attributes)
        self.assertIn(b'new-demo.md', (self.root / '.gitattributes').read_bytes())
        self.assertFalse((self.root / 'docs/generated/new-demo.md').exists())
        # Persist the authored change, then regenerate from a newly captured source.
        manifest = self.root / s.JSON_PATHS[1]
        manifest.write_bytes(s.canonical(c.manifest))
        broken = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        self.assertIn('D17', {d.code for d in s.check(broken).errors})
        s.write_outputs(broken, s.generate_navigation(broken))
        self.assertTrue(s.check(s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))).ok)

    def test_snapshot_does_not_load_unrelated_binary_bytes(self):
        (self.root / 'asset.bin').write_bytes(b'large unrelated asset')
        self.git('add', 'asset.bin')
        self.git('commit', '-qm', 'fixture: asset')
        for args in ({}, {'staged': True}, {'rev': 'HEAD'}):
            snapshot = s.Snapshot.from_git(self.root, fixture=True, **args)
            self.assertIn('asset.bin', snapshot.tracked)
            self.assertNotIn('asset.bin', snapshot.files)
            self.assertTrue(s.check(s.load_corpus(snapshot)).ok)

    def test_generation_refuses_concurrent_attributes_edits(self):
        c = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        output = s.generate_navigation(c)
        target = self.root / '.gitattributes'
        target.write_text(target.read_text() + 'authored text eol=lf\n')
        with self.assertRaisesRegex(s.SpecDocsError, 'authored destination differs'):
            s.write_outputs(c, output)
        self.assertIn('authored text', target.read_text())

    def test_unstaged_repair_cannot_hide_broken_index(self):
        target = self.root / ACCEPTANCE
        clean = target.read_text()
        target.write_text(clean.replace('[writer](#writer)', 'writer'))
        self.git('add', ACCEPTANCE)
        target.write_text(clean)
        staged = s.load_corpus(s.Snapshot.from_git(self.root, staged=True, fixture=True))
        working = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        self.assertIn('D12', {d.code for d in s.check(staged).errors})
        self.assertTrue(s.check(working).ok)

    def test_commit_pack_ignores_dirty_bytes_and_snapshot_is_immutable(self):
        committed = s.Snapshot.from_git(self.root, rev='HEAD', fixture=True)
        initial = s.select_context(s.load_corpus(committed), {'version': 1, 'sections': ['example-demo#acceptance']})
        (self.root / ACCEPTANCE).write_text('Broken dirty source')
        again = s.select_context(s.load_corpus(s.Snapshot.from_git(self.root, rev='HEAD', fixture=True)), {'version': 1, 'sections': ['example-demo#acceptance']})
        self.assertEqual(initial.content, again.content)
        self.assertEqual(committed.files[ACCEPTANCE], miniature()[ACCEPTANCE])

    def test_symlinks_are_not_local_inputs(self):
        target = self.root / SETTINGS
        target.unlink()
        target.symlink_to(self.root / ACCEPTANCE)
        c = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        self.assertIn('D05', {d.code for d in s.check(c).errors})

    def test_generation_preserves_prior_output_on_validation_failure(self):
        old = (self.root / 'docs/generated/example-demo.md').read_bytes()
        c = s.load_corpus(s.Snapshot.from_git(self.root, fixture=True))
        with self.assertRaises(s.SpecDocsError):
            s.write_outputs(c, {SETTINGS: b'invalid source'})
        self.assertEqual((self.root / 'docs/generated/example-demo.md').read_bytes(), old)

    def test_commands_share_the_same_checker_and_exit_codes(self):
        script = Path(s.__file__).resolve()
        def invoke(*args):
            return subprocess.run([__import__('sys').executable, '-B', str(script), *args, '--root', str(self.root), '--fixture'], stdin=subprocess.DEVNULL, capture_output=True)
        self.assertEqual(invoke('check').returncode, 0)
        self.assertEqual(invoke('generate').returncode, 0)
        assignment = self.root / 'assignment.json'
        assignment.write_text(json.dumps({'version': 1, 'sections': ['example-demo#acceptance']}))
        result = invoke('context', '--assignment', str(assignment), '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreater(json.loads(result.stdout)['size_bytes'], 0)
        self.assertEqual(invoke('check', '--staged', '--rev', 'HEAD').returncode, 2)
        target = self.root / ACCEPTANCE
        target.write_text(target.read_text().replace('[writer](#writer)', 'writer'))
        self.assertEqual(invoke('check').returncode, 1)
        (self.root / s.JSON_PATHS[0]).unlink()
        self.assertEqual(invoke('check').returncode, 2)


class DiagnosticCoverageSuite(unittest.TestSuite):
    """Use existing test runs as the diagnostic coverage record, without rerunning them."""
    def run(self, result, debug=False):
        import re
        emitted = set()
        original = s.Diagnostics.add
        def record(diagnostics, code, *args, **kwargs):
            emitted.add(code)
            return original(diagnostics, code, *args, **kwargs)
        with patch.object(s.Diagnostics, 'add', record):
            super().run(result, debug)
        reference = Path(s.__file__).resolve().parents[3] / 'docs/specs/spec-system/interfaces-and-encodings.md'
        expected = set(re.findall(r'^\| ([DW]\d{2}) \|', reference.read_text(), re.M))
        def verify():
            unittest.TestCase().assertEqual(emitted, expected)
            print(f'diagnostic coverage: {len(expected)} active codes emitted by behavioral tests; 0 missing')
        unittest.FunctionTestCase(verify, description='Every referenced diagnostic is exercised').run(result)
        return result


def load_tests(loader, tests, pattern):
    return DiagnosticCoverageSuite(tests)


if __name__ == '__main__':
    unittest.main(verbosity=2)
