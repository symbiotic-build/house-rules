<a id="commands-and-diagnostics"></a>
# Interfaces and encodings

This chapter connects caller-visible diagnostics and selector-audit outcomes to their remedies and behavioral evidence. Use the [source formats](source-formats.md#source-format) for exact command arguments and declaration shapes. For the bounded batch, a capacity link displaying `3` against the home value `2` produces `D10`; assignment `example#main` succeeds after repair and regeneration.

<a id="diagnostics"></a>
## Diagnostic reference

Diagnostics identify a failed structural condition and the repair that lets checking continue. Every active code below names a behavioral regression in [skills/spec-writing/scripts/test_spec_docs.py](../../../skills/spec-writing/scripts/test_spec_docs.py). Those tests exercise a trigger and a repaired or valid condition; their existence alone is not a recorded run.

| Code | Meaning | Remedy |
|---|---|---|
| D01 | Unclassified Markdown | Classify the path |
| D02 | Invalid shape or invocation | Repair the reported field |
| D03 | Duplicate or retired identity | Restore identity uniqueness |
| D04 | Incomplete or shared home | Restore heading and definition |
| D05 | Invalid input boundary | Use regular UTF-8 inputs |
| D06 | Unresolved destination | Repair the direct target |
| D07 | Entity outside scope | Correct scope or use |
| D08 | Invalid fact anchor | Anchor the Key cell once |
| D10 | Unequal literal display | Match the home literal |
| D11 | Requirement lacks test | Link an acceptance case |
| D12 | Missing direct home link | Link the intended home |
| D13 | Rejected name | Use its registered replacement |
| D14 | Naming pattern violation | Follow the declared pattern |
| D15 | Absent or misordered role | Complete the reading path |
| D16 | Forward prerequisite lacks handoff | Link the prerequisite directly |
| D17 | Generated output differs | Regenerate valid sources |
| D18 | Invalid numbered procedure | Label at least two actions |
| D21 | Approval has unresolved contract | Resolve before approval |
| D22 | Requirement removal lacks decision | Supply a resolving decision |
| D24 | Stale assignment baseline | Regenerate current-snapshot input |
| D25 | Mandatory bytes exceed budget | Narrow the assignment |
| D26 | Missing review coverage | Repair the actual plan |
| D27 | Environment or I/O failure | Repair the named input |
| D28 | Test lacks requirement | Link its obligation |
| D29 | One-sided trace link | Repair both directions |
| D30 | Incomplete stopping declaration | Complete fields and verification |
| D31 | Affected test input missing | Select every affected test |
| D32 | Numbered heading | Use an unnumbered title |
| D33 | Link inside heading | Move the link into text |
| D34 | Filename differs from title slug | Rename the chapter file |
| D35 | Repeated authored sentence | Consolidate repeated explanation |
| D36 | Summary repeats only title | State the reader outcome |

`D02` includes duplicate JSON keys, unsupported versions, unknown fields, malformed patterns, invalid declarations and conflicting snapshot arguments. Its message identifies the rejected shape. `D27` names failures reading Git, source, runtime inputs or destinations. A diagnostic's code alone does not certify the document's technical validity.

Codes `D09`, `D19`, `D20` and `D23` are retired. Warning `W03` is also retired. There is no typed-value evaluator, reference-valued fact resolver or heuristic claim that ordinary numerals identify unlinked fact restatements.

The following lookup names each active code's executable behavioral selector. The file destination is shared; the selector identifies the individual regression to inspect or run.

| Code | Behavioral selector |
|---|---|
| D01 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_tracked_markdown_requires_classification](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D02 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_unknown_fields_and_versions_are_refused](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D03 | [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_retired_trace_identity_is_checked_against_base_history_only](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D04 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_home_needs_heading_anchor_and_introductory_meaning](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D05 | [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_symlinks_are_not_local_inputs](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D06 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_local_fragment_must_be_explicit_and_present](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D07 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_entity_scope_cannot_omit_its_own_document](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D08 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_fact_anchor_belongs_inside_its_key_cell](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D10 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_mismatched_literal_and_equivalent_measurement_are_refused](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D11 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_requirement_needs_linked_acceptance_test](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D12 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_first_use_requires_direct_home_link](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D13 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_rejected_forms_are_diagnosed](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D14 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_structured_symbols_obey_compiled_naming_rule](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D15 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_every_role_preserves_contract_order](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D16 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_forward_prerequisite_requires_direct_link](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D17 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_generated_navigation_and_attributes_are_freshness_checked](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D18 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_procedure_needs_label_and_two_direct_actions](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D21 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_unresolved_contract_blocks_approval](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D22 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_removed_requirement_requires_resolving_decision](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D24 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_refuses_omission_stale_baseline_budget_and_missing_review_coverage](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D25 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_refuses_omission_stale_baseline_budget_and_missing_review_coverage](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D26 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_review_plan_is_checked_without_spawning_reviewers](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D27 | [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_commands_share_the_same_checker_and_exit_codes](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D28 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_acceptance_test_needs_linked_requirement](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D29 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_traceability_is_reciprocal](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D30 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_failure_declaration_requires_each_field](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D31 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_changed_requirement_requires_test_review_input](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D32 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_numbered_headings_are_refused_without_changing_anchors](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D33 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_links_in_headings_are_refused](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D34 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_chapter_filename_matches_first_heading_slug](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D35 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_three_repeated_sentences_fail_with_whitespace_normalization](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| D36 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_summary_explains_more_than_title_or_generic_verb](../../../skills/spec-writing/scripts/test_spec_docs.py) |

Warnings guide review without changing command success or blocking pack preparation. Review every remaining warning group and state whether it reveals a concrete problem or why its wording is retained.

| Code | Meaning | Disposition |
|---|---|---|
| W01 | Sentence over target | Review wording or retain |
| W02 | Paragraph over target | Review grouping or retain |
| W04 | Ambiguous registered phrase | Review intended meaning |
| W05 | Possible prose-profile violation | Inspect the passage |
| W06 | Predecessor-only prerequisites | Review conceptual dependencies |

| Code | Behavioral selector |
|---|---|
| W01 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_warnings_do_not_fail_a_valid_structural_gate](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| W02 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_warnings_do_not_fail_a_valid_structural_gate](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| W04 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_ambiguous_registered_phrase_warns_instead_of_guessing](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| W05 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_suspected_multi_action_and_long_cells_warn](../../../skills/spec-writing/scripts/test_spec_docs.py) |
| W06 | [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_predecessor_only_prerequisites_warn_above_five_sections](../../../skills/spec-writing/scripts/test_spec_docs.py) |

Unambiguous registered phrases and exact symbols receive blocking checks. Ambiguous phrases produce `W04` rather than a guessed identity. Unlinked literal restatements and unregistered technical meanings require [semantic review](writing-and-review-workflow.md#semantic-review). A warning becomes a finding only when review demonstrates the contradiction or reader problem.

<a id="selector-audit"></a>
## Selector audit

The selector audit establishes whether an acceptance case's executable references load and pass. Run `python skills/spec-writing/scripts/audit_selectors.py --root REPOSITORY` after a successful structural check. Add `--fixture` only for synthetic fixture authority.

The audit lists each acceptance identity with its linked requirements. It executes every Implementation selector in a separate child process using the same interpreter. Python unittest `.py` files are supported; the label's file must exist under the selected root. Nested `Class::test_method` selectors become dotted unittest names. Unsupported executable files, absent selectors, loader errors and empty suites are reported as missing.

A successful selector increments `passed`. A test failure, child error or exceeded ceiling increments `failing`. Each selector line records outcome and runtime. The final line reports `passed`, `missing` and `failing` counts; any missing or failing result makes the audit unsuccessful. Ordinary success output is summarized rather than reproduced as another log.

`--timeout-seconds` is a positive per-selector runaway ceiling, defaulting to 30 seconds in this interface version. A timeout fails visibly. This ceiling is not a recommended test duration: individual tests should finish in seconds. Other test frameworks need an explicit supported execution contract before their files can provide executable evidence here.

The audit reads live executable files under its root after capturing documentation. It has no staged or commit-execution switch. Use a checkout matching the accepted candidate when claiming source-bound execution evidence. The [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_audit_distinguishes_pass_missing_and_failure](../../../skills/spec-writing/scripts/test_audit_selectors.py) exercises one passing, one missing and one failing selector, then repairs them to three passes.

Inspection, analysis and demonstration cases omit Implementation and link their evidence. Their meaning and adequacy receive review; the selector audit cannot turn a linked inspection plan into an observed result.

<a id="continuing-example-reference"></a>
## Bounded-batch lookup

This lookup lets a caller move from the continuing example to exact source and evidence. The example's `Full` result describes admission refusal, while `D10` describes a documentation mismatch.

| Need | Destination |
|---|---|
| Complete source files | [Minimal corpus](minimal-corpus.md#minimal-example) |
| Capacity and refusal encoding | [Markdown declarations](source-formats.md#markdown-declarations) |
| Wrong displayed capacity | [Diagnostic reference](#diagnostics) |
| `example#main` assignment | [Callable core and assignment](source-formats.md#callable-core-and-context-assignment) |
| Exact fixture regression | [Literal values](acceptance-evidence.md#test-literals) |

The minimal corpus's acceptance case inspects retained state; it asserts no executable batch implementation. The independent-repository regression executes the [documentation checker](checking-and-navigation.md#documentation-checker) against those exact fixture files. Keep those two evidence claims distinct when reporting acceptance.
