<a id="acceptance"></a>
# Acceptance evidence

These cases define the evidence required to accept the documentation system. They connect obligations to behavioral regressions and normal-run inspections. The [tour’s successful check](tour-fixing-a-wrong-capacity.md#capacity-repair) distinguishes structural validation from observed service behavior. A declaration names planned verification; observed evidence requires actual command output or reader responses.

<a id="planned-acceptance"></a>
## Verification coverage

The following permanent cases let reviewers distinguish executable structure checks from inspection of real understanding and conversion. Executable outcomes follow the [Selector audit](interfaces-and-encodings.md#selector-audit) contract.

<a id="test-roles"></a>
### Acceptance test: document roles

Check whether declared content and approval can form a complete reading path.

**Method:** test.

**Requirements:** [roles](requirements.md#req-roles).

**Inputs:** Complete single-file and multi-file documents, draft role gaps, misordered roles and unresolved approval contracts.

**Expected:** A complete document with correctly ordered roles is accepted. Missing content and blocking contracts fail. Fixture authority is confined to fixture mode.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_required_document_roles_are_not_optional_for_approval](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_every_role_preserves_contract_order](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_unresolved_contract_blocks_approval](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_fixture_approval_does_not_authorize_production](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_fixture_authority_diagnostic_names_the_production_fix](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-homes"></a>
### Acceptance test: homes and names

Check that registered meanings have unique homes and required links reach those homes.

**Method:** test.

**Requirements:** [homes](requirements.md#req-homes).

**Inputs:** Duplicate and missing anchors, scoped names, repeated uses before and after homes, deeper subsections, wrong destinations, literal blocks and retired trace identities.

**Expected:** Valid scoped homes pass. Missing, duplicated or wrong destinations fail. Level-2 sections reset first use regardless of home order; deeper sections share it. Ambiguous phrases and unambiguous missing links follow the [direct-link behavior](checking-and-navigation.md#documentation-checker).

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_literal_home_links_can_be_in_adjacent_explanatory_prose](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_duplicate_anchor_is_not_a_unique_home](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_subsections_share_level_two_first_use_scope](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_level_two_sections_restart_first_use](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_wrong_target_is_not_a_home_link](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_literal_examples_need_adjacent_links_for_each_block](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_trace_identities_are_unique_across_documents_and_retired_records](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_retired_trace_identity_is_checked_against_base_history_only](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_link_inserts_only_missing_unambiguous_body_uses](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_repeated_uses_before_home_share_level_two_first_use_scope](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_repeated_uses_of_home_in_another_document_share_first_use_scope](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_link_preserves_authored_repeated_links_before_and_after_home](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_link_leaves_headings_code_literals_existing_links_and_ambiguity](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_ambiguous_registered_phrase_warns_instead_of_guessing](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_unambiguous_registered_form_and_symbol_require_home_links](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_link_preserves_markdown_and_links_only_first_uses_in_lists_quotes_and_tables](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_fact_table_without_owner_names_line_and_repair](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_link_replacement_rejects_concurrent_source_edits_and_symlinks](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_link_command_writes_repairs_reports_remaining_errors_and_is_idempotent](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_link_refuses_intersecting_first_use_edits](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-literals"></a>
### Acceptance test: literal values

Check the capacity repair and the limits of literal comparison.

**Method:** test.

**Requirements:** [literals](requirements.md#req-literals).

**Inputs:** Exact minimal corpus; capacity 2 linked as 3; grouped integers; different measurement spellings; fact anchors inside and outside Key cells.

**Expected:** The wrong display fails with D10 and its repair passes. Grouping normalization succeeds without unit conversion. Each declaring row has exactly one Key-cell anchor.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_literal_values_allow_grouping_and_markdown_formatting](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_mismatched_literal_and_equivalent_measurement_are_refused](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_fact_anchor_belongs_inside_its_key_cell](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_two_anchors_in_one_fact_row_are_refused](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::MinimalExampleTests::test_published_example_is_the_checked_fixture_in_an_independent_repository](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_descriptive_fact_labels_and_code_only_literals](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_fact_status_uses_contract_vocabulary](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-traceability"></a>
### Acceptance test: traceability and change selection

Check that a changed contract brings its evidence into review.

**Method:** test.

**Requirements:** [traceability](requirements.md#req-traceability).

**Inputs:** Reciprocal and one-sided links, requirement and fact changes across snapshots, affected unchanged tests and explicit removal decisions.

**Expected:** One-sided links fail. Reports include base and candidate declarations, directly linked changed facts and tests from both sides. Removed requirements need a resolving decision; affected tests enter mandatory input.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_traceability_is_reciprocal](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_changed_fact_and_qualification_select_unchanged_linked_tests](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_changed_requirement_requires_test_review_input](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_removed_requirement_requires_resolving_decision](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_change_review_context_contains_base_tests_and_changed_declarations](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/pr-ready/scripts/test_documentation_context.py::DocumentationContextTests::test_review_preparer_compares_base_and_selects_unchanged_tests](../../../skills/pr-ready/scripts/test_documentation_context.py), [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_unsuccessful_batch_fails_all_selectors](../../../skills/spec-writing/scripts/test_audit_selectors.py), [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_declared_batch_runs_once_and_times_out](../../../skills/spec-writing/scripts/test_audit_selectors.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_declaration_ignores_blockquoted_detail_fields_only](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_fact_basis_evidence_changes_select_tests_from_both_snapshots](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_fact_evidence_in_preserved_markdown_uses_captured_section](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_history_filter_covers_accepted_anchor_whitespace](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-failures"></a>
### Acceptance test: failure completeness

Check whether stopping paths declare enough information for recovery review.

**Method:** test.

**Requirements:** [failures](requirements.md#req-failures).

**Inputs:** Complete refusal fields, one missing field at a time, absent verification links and an explicit absence of recovery.

**Expected:** Incomplete declarations fail visibly. An explained absence of recovery is structurally valid. [Semantic review](writing-and-review-workflow.md#semantic-review) still establishes whether the stated recovery is possible and authorized.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_failure_declaration_requires_each_field](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_failure_verification_requires_a_resolving_link](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_missing_recovery_can_be_explicit_and_explained](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-checking"></a>
### Acceptance test: checker failures

Check input failures and deterministic visible results through the shared command path.

**Method:** test.

**Requirements:** [checking](requirements.md#req-checking).

**Inputs:** Duplicate JSON keys, invalid UTF-8, path escapes, missing fragments, malformed external URLs, malformed metadata types and warning-only prose.

**Expected:** Invalid input returns diagnostics without a fallback or silent omission. Local targets resolve within the selected input; external syntax needs no network. Commands distinguish document failures from invocation or I/O failures.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_duplicate_json_keys_are_not_last_value_wins](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_all_declared_metadata_types_fail_visibly_instead_of_crashing](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_invalid_utf8_is_not_silently_skipped](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_local_fragment_must_be_explicit_and_present](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_external_url_syntax_is_checked_without_network](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_commands_share_the_same_checker_and_exit_codes](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_runner_declarations_validate_commands_and_patterns](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_text_diagnostic_counts_agree_for_zero_one_and_many](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_implementation_uses_collected_field_outside_detail_examples](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_procedure_requires_each_direct_action_to_open_bold](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-navigation"></a>
### Acceptance test: navigation and interrupted output

Check deterministic [navigation generation](checking-and-navigation.md#navigation-generation) and recovery after incomplete replacement.

**Method:** test.

**Requirements:** [navigation](requirements.md#req-navigation).

**Inputs:** Repeated generation, changed summaries, edited generated content, concurrent authored-destination changes and interrupted multioutput replacement.

**Expected:** Fresh navigation matches source-derived bytes. Validation failure preserves previous output. A partial generated set fails freshness and can be repaired by regeneration. Writers serialize cooperating runs and refuse destinations changed since capture at the final byte check. Editor saves during replacement are outside this guarantee.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_navigation_keeps_complete_introduction_together](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_generated_navigation_and_attributes_are_freshness_checked](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_entity_index_uses_definition_sentence_without_following_purpose](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_map_places_diagram_before_generated_overview](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_generation_preserves_prior_output_on_validation_failure](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_interrupted_multioutput_generation_is_visible_and_regenerable](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_generation_refuses_concurrent_attributes_edits](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_generation_replaces_stale_navigation_before_checking_freshness](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_navigation_ignores_literal_marker_examples](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_generated_navigation_encodes_paths_and_fragments](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_writers_refuse_lock_contention](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_writer_rechecks_destination_after_temporary_file_is_written](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-toolchain"></a>
### Acceptance test: toolchain ownership

Check that direct and extracted consumers use their owning environment and helper.

**Method:** test.

**Requirements:** [toolchain](requirements.md#req-toolchain).

**Inputs:** Locked dependencies and runtime metadata, a mismatched installed version, the minimum supported grammar and pinned compiler extraction.

**Expected:** Mismatch fails visibly. Extracted compiler inputs come from the selected revision despite live edits. Parsing under the minimum supported Python grammar does not prove execution on every supported interpreter.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_runtime_and_dependency_mismatch_stop_without_a_fallback_parser](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::MinimalExampleTests::test_checker_parses_under_the_minimum_supported_python_grammar](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/pr-ready/scripts/test_documentation_context.py::DocumentationContextTests::test_commit_compiler_uses_pinned_helper_and_profile_after_live_edits](../../../skills/pr-ready/scripts/test_documentation_context.py), [skills/pr-ready/scripts/test_documentation_context.py::DocumentationContextTests::test_missing_pinned_helper_fails_instead_of_importing_live_tool](../../../skills/pr-ready/scripts/test_documentation_context.py), [skills/pr-ready/scripts/test_documentation_context.py::DocumentationContextTests::test_extracted_compiler_uses_matching_pinned_selector](../../../skills/pr-ready/scripts/test_documentation_context.py)

<a id="test-snapshots"></a>
### Acceptance test: snapshot isolation and invalidation

Check that selected source bytes cannot be repaired or changed by unrelated working-tree edits.

**Method:** test.

**Requirements:** [snapshots](requirements.md#req-snapshots).

**Inputs:** A defective staged source with an unstaged repair, commit-selected source with dirty files, immutable captured bytes and stale assignment baselines.

**Expected:** Index checking sees the staged defect. Commit context ignores dirty bytes, captured snapshots remain stable and stale baselines fail until the assignment is regenerated.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_unstaged_repair_cannot_hide_broken_index](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_commit_pack_ignores_dirty_bytes_and_snapshot_is_immutable](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_refuses_omission_stale_baseline_budget_and_missing_review_coverage](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-context"></a>
### Acceptance test: context selection

Check explicit complete selection and refusal before dispatch.

**Method:** test.

**Requirements:** [context](requirements.md#req-context).

**Inputs:** The [complete registry](agent-context.md#complete-registry), explicit assignments, whole [scenarios](requirements-tests-and-failures.md#scenario), transitive dependencies, cycles, overlapping ranges, missing review coverage and exact byte budgets.

**Expected:** Ranges deduplicate while keeping reasons. Added homes do not recursively follow ordinary links. Missing scope, unknown targets, stale input and excessive size fail without truncating mandatory content.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_contains_entire_registry_exact_bytes_and_unique_ranges](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_rejects_unknown_selector_and_missing_scope](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_dependencies_expand_transitively_and_deduplicate_cycles](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_ordinary_links_in_added_home_do_not_expand_context](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_applies_whole_scenario_and_changed_test_selectors](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_review_plan_is_checked_without_spawning_reviewers](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/pr-ready/scripts/test_documentation_context.py::DocumentationContextTests::test_preparer_reserves_context_before_optional_material_and_never_trims_it](../../../skills/pr-ready/scripts/test_documentation_context.py), [skills/pr-ready/scripts/test_documentation_context.py::DocumentationContextTests::test_complete_pack_budget_counts_rules_tasks_and_unicode_bytes](../../../skills/pr-ready/scripts/test_documentation_context.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_sources_follow_manifest_order_then_source_order](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/pr-ready/scripts/test_prompt.py::CommitPackTest::test_pack_helper_finishes_with_callers_standard_input_left_open](../../../skills/pr-ready/scripts/test_prompt.py), [skills/pr-ready/scripts/test_documentation_context.py::DocumentationContextTests::test_panel_prepares_registered_context_once_and_stops_missing_assignment_before_dispatch](../../../skills/pr-ready/scripts/test_documentation_context.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_rewrites_only_links_to_included_destinations](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_preserves_literal_links_and_handles_reference_links_and_base](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_keeps_links_to_source_outside_selected_ranges](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/pr-ready/scripts/test_documentation_context.py::DocumentationContextTests::test_credential_bearing_documentation_refuses_before_publication](../../../skills/pr-ready/scripts/test_documentation_context.py)

<a id="test-profile"></a>
### Acceptance test: writing profile

Check that structural writing rules and approximate prose targets have different consequences.

**Method:** test.

**Requirements:** [profile](requirements.md#req-profile).

**Inputs:** Labelled procedures, single-item numbered lists, long sentences and paragraphs, code punctuation, attributed quotations and long table cells.

**Expected:** Invalid procedure structure fails. Approximate prose, number-format and action warnings do not fail valid input. Literal exclusions do not erase ordinary explanatory prose from counting.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_warnings_do_not_fail_a_valid_structural_gate](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_procedure_needs_label_and_two_direct_actions](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_sentence_counter_preserves_decimals_and_code_punctuation](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_ordinary_detail_prose_counts_but_attributed_quotation_does_not](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_suspected_multi_action_and_long_cells_warn](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_three_repeated_sentences_fail_with_whitespace_normalization](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_summary_explains_more_than_title_or_generic_verb](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-real-use"></a>
### Inspection: real authoring and review

This inspection establishes whether normal loading, authoring and review produce a usable contract. The [Fresh-reader review](../../../skills/spec-writing/SKILL.md#fresh-reader-review) and [prompts/lenses/naming-readability.md](../../../prompts/lenses/naming-readability.md) identify the inspection method. Apply the evidence distinction in this chapter’s opening. The lead names the run record and responsible author in the assignment.

**Method:** inspection.

**Requirements:** [Review coverage](requirements.md#req-review), [faithful adoption](requirements.md#req-adoption).

**Inputs:** A short feature brief, an unconverted design, a deliberately messy document, a source-content inventory and a pinned author session that loads repository rules and the spec-writing skill. Supply fresh reader contexts and the real review plan. The lead runs a fresh author session from the feature brief and separate conversion sessions for the existing design and messy document. Each session loads repository rules and the pinned spec-writing skill. Each resulting document passes structural checking and reader review.

**Expected:** Normal authoring produces a multi-chapter contract. Conversion preserves substantive rules, distinctions, qualifications and settled decisions.

Two fresh readers using different models answer all ten questions with citations. Each constructs a corpus whose first check has zero errors and rates every chapter “yes”. No unanswered question, guess, stuck point or unaddressed quoted passage remains. Every polish note is fixed or answered with a reason under the canonical rating procedure.

Each reader follows a map link to a chapter and a term link to its definition. A value link must reach its fact row. Each records the reached destinations. The reader also reproduces the tour’s D10 refusal, repairs the display, regenerates and records a clean check.

The assigned author retains source revision, candidate digest, first-check output, navigation destinations, reader responses and dispositions in that assigned run record. Inspect approved designs for implementation or an explicit reasoned change. Repair source owners and repeat normal entry points instead of editing generated packs. The [delivery decision](decisions-and-open-questions.md#delivery-decision) defines the renderer’s acceptance boundary.

<a id="test-selector-reports"></a>
### Acceptance test: selector reports and batched fallback

Check acceptance evidence without repeating a normal test run.

**Method:** test.

**Requirements:** [traceability](requirements.md#req-traceability).

**Inputs:** Python and Vitest JUnit reports with pass, failure, error, skip and missing cases; multiple reports and malformed or absent reports; unittest discovery arguments, repeated test objects, subtests and fixture errors; repeated citations across files and a declared batch runner.

**Expected:** Reports execute no tests and distinguish passed, missing and failing selectors. Inbound link checks stay in the structural gate. Invalid or absent reports name the regeneration fix. The standard-library runner preserves unittest arguments and exit status and writes matching identities. Fallback runs each runner once and fails every selector on unsuccessful runner exit or timeout.

**Implementation:** [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_reports_match_outcomes_without_execution](../../../skills/spec-writing/scripts/test_audit_selectors.py), [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_report_loading_leaves_inbound_links_to_structural_check](../../../skills/spec-writing/scripts/test_audit_selectors.py), [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_bad_or_absent_reports_name_the_fix](../../../skills/spec-writing/scripts/test_audit_selectors.py), [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_python_batch_loads_files_once_and_fails_unsuccessful_batch](../../../skills/spec-writing/scripts/test_audit_selectors.py), [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_declared_batch_runs_once_and_times_out](../../../skills/spec-writing/scripts/test_audit_selectors.py), [skills/spec-writing/scripts/test_junit_unittest.py::JUnitRunnerTests::test_discovery_report_preserves_outcomes](../../../skills/spec-writing/scripts/test_junit_unittest.py), [skills/spec-writing/scripts/test_junit_unittest.py::JUnitRunnerTests::test_subtests_fixture_errors_and_write_errors_are_visible](../../../skills/spec-writing/scripts/test_junit_unittest.py), [skills/spec-writing/scripts/test_junit_unittest.py::JUnitRunnerTests::test_unittest_options_and_empty_discovery_keep_native_behavior](../../../skills/spec-writing/scripts/test_junit_unittest.py), [skills/spec-writing/scripts/test_junit_unittest.py::JUnitRunnerTests::test_repeated_test_object_records_each_execution](../../../skills/spec-writing/scripts/test_junit_unittest.py), [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_failed_class_cleanup_fails_entire_fallback_batch](../../../skills/spec-writing/scripts/test_audit_selectors.py), [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_timeout_does_not_drain_descendant_held_pipes](../../../skills/spec-writing/scripts/test_audit_selectors.py)
