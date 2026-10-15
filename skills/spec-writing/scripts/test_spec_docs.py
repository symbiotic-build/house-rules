"""Small behavioral red/green fixtures for the shared documentation pipeline."""
import copy
from dataclasses import replace
import json
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
    paths[s.PROFILE_PATH] = (FIXTURES / "writing.md").read_bytes()
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

    def test_each_subsection_resets_first_use(self):
        edit(self.paths, ACCEPTANCE, '### Relations', '### More\n\nThe writer refuses it.\n\n### Relations')
        self.red_green("D12")

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

    def test_operator_decision_options_are_exempt(self):
        edit(self.paths, SETTINGS, 'None for this fixture.', '### 1\\. Which option applies?\n\n1. **First choice.**\n2. Second choice.\n\n**Answer like so:**\n\n```text\n1. 1\n```')
        self.assertTrue(s.check(refresh(self.paths)).ok)

    def test_unresolved_contract_blocks_approval(self):
        metadata(self.paths, s.JSON_PATHS[1], lambda v: v["documents"][0].update(unresolved_contracts=["example-demo#fixture-decision"]))
        self.red_green("D21")

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
        self.assertTrue({'W01', 'W02', 'W03'} <= {item.code for item in d.warnings})
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
        ctx = self.context(assignment)
        self.context_error('D23', dict(assignment, pack=dict(baseline=ctx.manifest['baseline'], registry_digest=ctx.manifest['registry_digest'], included=[])))
        self.context_error('D24', dict(assignment, baseline='wrong'))
        self.context_error('D25', dict(assignment, budget_bytes=1))
        self.context_error('D26', dict(assignment, review_plan=[{'responsibilities': ['technical']}]))

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
        self.paths[s.PROFILE_PATH] = b'# No machine-readable profile\n'
        self.red_green('D02')

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
