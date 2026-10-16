<a id="commands-and-diagnostics"></a>
# Interfaces and encodings

This chapter connects caller-visible diagnostics and selector-audit outcomes to their remedies and behavioral evidence. Use the [source formats](source-formats.md#source-format) for exact command arguments and declaration shapes.

<a id="diagnostics"></a>
## Diagnostic reference

Diagnostics identify a failed structural condition and the repair that lets checking continue. Every active code below names a behavioral regression in [skills/spec-writing/scripts/test_spec_docs.py](../../../skills/spec-writing/scripts/test_spec_docs.py). Report their outcomes using the [acceptance evidence distinction](acceptance-evidence.md#acceptance).

| Code | Severity | Meaning | Remedy | Behavioral regression |
|---|---|---|---|---|
| D01 | error | Unclassified Markdown | Classify the path | [Markdown classification](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_tracked_markdown_requires_classification") |
| D02 | error | Invalid shape or invocation | Repair the reported field | [Envelope validation](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_unknown_fields_and_versions_are_refused") |
| D03 | error | Duplicate or retired identity | Remove a duplicate; preserve the same obligation’s identity; give a different obligation a new, never-retired identity | [Retired identities](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_retired_trace_identity_is_checked_against_base_history_only") |
| D04 | error | Incomplete or shared home | Restore heading and definition | [Complete homes](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_home_needs_heading_anchor_and_introductory_meaning") |
| D05 | error | Invalid input boundary | Use regular UTF-8 inputs | [Symlink refusal](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_symlinks_are_not_local_inputs") |
| D06 | error | Unresolved destination | Repair the direct target | [Explicit destinations](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_local_fragment_must_be_explicit_and_present") |
| D07 | error | Entity outside scope | Correct scope or use | [Entity scope](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_entity_scope_cannot_omit_its_own_document") |
| D08 | error | Invalid fact anchor | Anchor the Key cell once | [Fact anchors](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_fact_anchor_belongs_inside_its_key_cell") |
| D10 | error | Unequal literal display | Match the home literal | [Literal comparison](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_mismatched_literal_and_equivalent_measurement_are_refused") |
| D11 | error | Requirement lacks test | Link an acceptance case | [Requirement tests](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_requirement_needs_linked_acceptance_test") |
| D12 | error | Missing direct home link | Link the intended home | [First-use links](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_first_use_requires_direct_home_link") |
| D13 | error | Rejected name | Use its registered replacement | [Rejected forms](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_rejected_forms_are_diagnosed") |
| D14 | error | Naming pattern violation | Follow the declared pattern | [Naming patterns](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_structured_symbols_obey_compiled_naming_rule") |
| D15 | error | Absent or misordered role | Complete the reading path | [Role order](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_every_role_preserves_contract_order") |
| D16 | error | Later prerequisite lacks source link | Link the prerequisite directly | [Forward prerequisites](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_forward_prerequisite_requires_direct_link") |
| D17 | error | Generated output differs | Regenerate valid sources | [Navigation freshness](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_generated_navigation_and_attributes_are_freshness_checked") |
| D18 | error | Invalid numbered procedure | Label at least two actions | [Procedure structure](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_procedure_needs_label_and_two_direct_actions") |
| D21 | error | Approval has unresolved contract | Resolve before approval | [Unresolved contracts](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_unresolved_contract_blocks_approval") |
| D22 | error | Requirement removal lacks decision | Supply a resolving decision | [Requirement removal](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_removed_requirement_requires_resolving_decision") |
| D24 | error | Stale assignment baseline | Regenerate current-snapshot input | [Stale assignment](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_refuses_omission_stale_baseline_budget_and_missing_review_coverage") |
| D25 | error | Mandatory bytes exceed budget | Narrow the assignment | [Context budget](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_refuses_omission_stale_baseline_budget_and_missing_review_coverage") |
| D26 | error | Missing review coverage | Repair the actual plan | [Review coverage](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_review_plan_is_checked_without_spawning_reviewers") |
| D27 | error | Environment or I/O failure | Repair the reported environment, input, Git access or output destination | [Command failures](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_commands_share_the_same_checker_and_exit_codes") |
| D28 | error | Test lacks requirement | Link its obligation | [Test requirements](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_acceptance_test_needs_linked_requirement") |
| D29 | error | One-sided trace link | Repair both directions | [Reciprocal traceability](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_traceability_is_reciprocal") |
| D30 | error | Incomplete stopping declaration | Complete fields and verification | [Failure fields](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_failure_declaration_requires_each_field") |
| D31 | error | Affected test input missing | Select every affected test | [Affected tests](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_changed_requirement_requires_test_review_input") |
| D32 | error | Numbered heading | Use an unnumbered title | [Numbered headings](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_numbered_headings_are_refused_without_changing_anchors") |
| D33 | error | Link inside heading | Move the link into text | [Heading links](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_links_in_headings_are_refused") |
| D34 | error | Filename differs from title slug | Rename the chapter file | [Chapter filenames](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_chapter_filename_matches_first_heading_slug") |
| D35 | error | Repeated authored sentence | Consolidate repeated explanation | [Repeated sentences](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_three_repeated_sentences_fail_with_whitespace_normalization") |
| D36 | error | Summary repeats only title | State the reader outcome | [Useful summaries](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_summary_explains_more_than_title_or_generic_verb") |
| W01 | warning | Sentence over target | Review wording or retain | [Advisory warnings](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_warnings_do_not_fail_a_valid_structural_gate") |
| W02 | warning | Paragraph over target | Review grouping or retain | [Advisory warnings](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_warnings_do_not_fail_a_valid_structural_gate") |
| W04 | warning | Ambiguous registered phrase | Review intended meaning | [Ambiguous phrases](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_ambiguous_registered_phrase_warns_instead_of_guessing") |
| W05 | warning | Possible prose-profile violation | Inspect the passage | [Prose warnings](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_suspected_multi_action_and_long_cells_warn") |
| W06 | warning | Predecessor-only prerequisites | Review conceptual dependencies | [Prerequisite chains](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_predecessor_only_prerequisites_warn_above_five_sections") |
| W07 | warning | Lazy blockquote continuation | Prefix every line of the quote with > | [Explicit quote prefixes](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_blockquote_lazy_continuations_warn_with_source_lines_and_remedy") |

For the tour's deliberate mutation, text output is:

```text
spec-docs: error D10 docs/example.md:46: value link for 'example.batcher#capacity' differs: home '2', link '3'
spec-docs: 1 error, 0 warnings
```

The same check with `--json` returns:

```json
{"errors": [{"code": "D10", "line": 46, "message": "value link for 'example.batcher#capacity' differs: home '2', link '3'", "path": "docs/example.md", "severity": "error"}], "ok": false, "warnings": []}
```

The line number belongs to the exact minimal source; preceding edits can change it. Both examples report a failed check and preserve the conflicting literals.

For another diagnostic, a tour declares a prerequisite on a later admission section. Without a direct source link to that prerequisite, checking reports `D16`.
Add `See [Admission](admission.md#admission) for the capacity rule` inside the tour's selected section. A generated map link alone does not satisfy this rule.

`D02` includes duplicate JSON keys, unsupported versions, unknown fields, malformed patterns, invalid declarations and conflicting snapshot arguments. Its message identifies the rejected shape. `D27` names failures reading Git, source, runtime inputs or destinations. A diagnostic's code alone does not certify the document's technical validity.

Codes `D09`, `D19`, `D20` and `D23` are retired. Warning `W03` is also retired. There is no typed-value evaluator, reference-valued fact resolver or heuristic claim that ordinary numerals identify unlinked fact restatements.

Warnings guide review without changing command success or blocking pack preparation. Review every remaining warning group and state whether it reveals a concrete problem or why its wording is retained.

The [direct-link behavior](checking-and-navigation.md#documentation-checker) distinguishes blocking missing links from advisory phrase ambiguity. Unlinked literal restatements and unregistered technical meanings require [semantic review](writing-and-review-workflow.md#semantic-review). A warning becomes a finding only when review demonstrates the contradiction or reader problem.

<a id="selector-audit"></a>
## Selector audit

The selector audit establishes whether an acceptance case's executable references load and pass. Run `python skills/spec-writing/scripts/audit_selectors.py --root REPOSITORY` after a successful structural check. Add `--fixture` only for synthetic fixture authority.

The audit lists each acceptance identity with its linked requirements. It executes every Implementation selector in a separate child process. The [runner declarations](source-formats.md#metadata) select commands for any language. Unmatched `.py` files use Python unittest with the audit interpreter. The label's file must exist under the selected root.

For `tests/test_batches.py::Suite::test_full`, the built-in runner loads that file as a module and asks unittest to run `Suite.test_full`. It uses the audit interpreter and does not require `tests` to be an importable package. Both missing and failing outcomes fail acceptance. An unmatched non-Python file, absent selector, loader error or empty suite counts as missing. A declared runner reports a missing selector with exit `2`; failure to start its executable also counts as missing. Children receive EOF on standard input.

A successful selector increments `passed`. A test failure, child error or exceeded ceiling increments `failing`. Each selector line records outcome and runtime. The final line reports `passed`, `missing` and `failing` counts; acceptance requires zero missing and zero failing selectors. A file link alone does not establish execution. Ordinary success output is summarized rather than reproduced as another log.

`--timeout-seconds` is a positive per-selector runaway ceiling, defaulting to 30 seconds in this interface version. A timeout terminates the selector process group and fails visibly. This ceiling is not a recommended test duration: individual tests should finish in seconds. A declared command supplies the execution contract for other test frameworks.

The audit reads live executable files under its root after capturing documentation. It has no staged or commit-execution switch. Use a checkout matching the accepted candidate when claiming source-bound execution evidence. The [skills/spec-writing/scripts/test_audit_selectors.py::SelectorAuditTests::test_audit_distinguishes_pass_missing_and_failure](../../../skills/spec-writing/scripts/test_audit_selectors.py) exercises one passing, one missing and one failing selector, then repairs them to three passes. Its adjacent non-Python regression also covers a declared shell runner and a timeout.

Inspection, analysis and demonstration cases omit Implementation and link their evidence. Their meaning and adequacy receive review under the [acceptance evidence distinction](acceptance-evidence.md#acceptance).

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
