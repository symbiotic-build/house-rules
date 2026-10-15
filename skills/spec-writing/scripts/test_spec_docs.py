"""Small behavioral red/green fixtures for the shared documentation pipeline."""
import copy
from dataclasses import replace
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

    def test_navigation_region_follows_title_and_opening_paragraph(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v['documents'][0].update(navigation={'path': ACCEPTANCE, 'region': 'example-demo'}))
        del self.paths['docs/generated/example-demo.md']
        self.paths[ACCEPTANCE] += ('\n' + s.START.format(document='example-demo') + '\nold\n' + s.END + '\n').encode()
        c = refresh(self.paths)
        text = self.paths[ACCEPTANCE].decode()
        self.assertLess(text.index(s.START.format(document='example-demo')), text.index('**Procedure:'))
        self.assertEqual(text.splitlines().count('# Acceptance'), 1)
        self.assertFalse(text.endswith('\n\n'))
        self.assertTrue(s.check(c).ok)

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
            edit(paths, SETTINGS, 'Its default uses the [default]', f'Its default uses the [{value}]')
            self.assertTrue(s.check(refresh(paths)).ok, value)

    def test_runner_declarations_validate_commands_and_patterns(self):
        valid = dict(pattern='tests/*.spec', command=['sh', 'runner.sh', '{file}', '{selector}'])
        for invalid in (None, {}, [None], [dict(valid, pattern='../*.spec')],
                        [dict(valid, command=[])], [dict(valid, command=['sh', '{file}'])],
                        [dict(valid, command=['sh', '{file}', '{selector}', '{unknown}'])],
                        [valid, valid]):
            paths = self.clean.copy()
            metadata(paths, s.JSON_PATHS[1], lambda value: value.update(test_runners=invalid))
            self.assertIn('D02', {item.code for item in s.check(corpus(paths)).errors})
        metadata(self.paths, s.JSON_PATHS[1], lambda value: value.update(test_runners=[valid]))
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_descriptive_fact_labels_and_code_only_literals(self):
        for label in ('declared limit', 'borrowing limit', '**declared limit**', '`1024`', '``1024``'):
            paths = self.clean.copy()
            edit(paths, SETTINGS, 'Its default uses the [default]', f'Its default uses the [{label}]')
            self.assertTrue(s.check(refresh(paths)).ok, label)
        for label in ('`wrong`', '``wrong``', 'revision 2'):
            paths = self.clean.copy()
            edit(paths, SETTINGS, 'Its default uses the [default]', f'Its default uses the [{label}]')
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
            edit(paths, SETTINGS, 'Its default uses the [default]', f'Its default uses the [{label}]')
            self.assertTrue(s.check(refresh(paths)).ok, label)

    def test_mismatched_literal_and_equivalent_measurement_are_refused(self):
        for label in ("2048", "1.024", "1024 documents"):
            self.paths = self.clean.copy()
            edit(self.paths, SETTINGS, 'Its default uses the [default]', f'Its default uses the [{label}]')
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

    def test_one_link_cannot_license_another_forward_use_in_same_paragraph(self):
        edit(self.paths, ACCEPTANCE, 'The [writer](#writer) performs', 'The writer asks the [writer](#writer) and performs')
        self.red_green("D12")

    def test_repeated_forward_uses_each_need_home_links(self):
        edit(self.paths, ACCEPTANCE, 'defines the refusal.', 'defines the refusal.\n   The writer refuses it.')
        self.red_green("D12")

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
        edit(self.paths, SETTINGS, 'None for this fixture.', '### 1\\. Which option applies?\n\n1. **First choice.**\n2. Second choice.\n\n**Answer like so:**\n\n```text\n1. 1\n```')
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
        edit(self.paths, SETTINGS, 'None for this fixture.', 'None for this fixture.\n\n' + extra)
        c = refresh(self.paths)
        d = s.check(c)
        self.assertTrue(d.ok)
        self.assertTrue({'W01', 'W02'} <= {item.code for item in d.warnings})
        self.assertEqual(d.to_dict(), s.check(c).to_dict())

    def test_ambiguous_registered_phrase_warns_instead_of_guessing(self):
        metadata(self.paths, s.JSON_PATHS[0], lambda v: v['entities']['example.call-capacity']['forms'].append('commit capacity'))
        c = refresh(self.paths)
        self.assertTrue(s.check(c).ok)
        self.assertIn('W04', {d.code for d in s.check(c).warnings})

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
        edit(self.paths, SETTINGS, 'None for this fixture.', f'None for this fixture.\n\n> **Detail — explanation**\n>\n> {long}\n')
        c = refresh(self.paths)
        self.assertIn('W01', {d.code for d in s.check(c).warnings})
        quoted = self.clean.copy()
        edit(quoted, SETTINGS, 'None for this fixture.', f'None for this fixture.\n\n> {long}\n>\n> — A synthetic source\n')
        self.assertNotIn('W01', {d.code for d in s.check(refresh(quoted)).warnings})

    def test_sentence_counter_preserves_decimals_and_code_punctuation(self):
        tokens = s.MarkdownIt('commonmark').parse('Use 1.25 and `x. y! z?`. Next is 42. Done.')
        inline = next(t for t in tokens if t.type == 'inline')
        self.assertEqual(len(s.sentences(inline.children)), 3)

    def test_suspected_multi_action_and_long_cells_warn(self):
        edit(self.paths, ACCEPTANCE, '**Prepare a request.**', '**Read a request and then write its result.**')
        edit(self.paths, SETTINGS, 'bounds encoded bytes in one log group.', 'bounds encoded bytes in one log group.')
        edit(self.paths, SETTINGS, 'None for this fixture.', 'None for this fixture.\n\n| Name | Meaning |\n|---|---|\n| Example | ' + ' '.join(['word'] * 30) + ' |')
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

    def test_implementation_requires_only_file_and_selector_links(self):
        invalid = ('None; no executable yet.', '', 'tests/example.py::test_refusal',
                   '[Executable test](../../tests/example.py)',
                   '[tests/example.py::](../../tests/example.py)',
                   '[tests/example.py::test refusal](../../tests/example.py)',
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
            subprocess.run(['git', 'init', '-q', directory], check=True)
            subprocess.run(['git', '-C', directory, 'add', '.'], check=True)
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
            subprocess.run(['git', '-C', str(root), 'init', '-q'], check=True)
            result = subprocess.run([__import__('sys').executable, '-B', s.__file__, 'check', '--root', str(root)], capture_output=True)
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
        return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, check=True).stdout

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
            return subprocess.run([__import__('sys').executable, '-B', str(script), *args, '--root', str(self.root), '--fixture'], capture_output=True)
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
