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
| D18 | error | Invalid numbered procedure | Label the procedure and bold each action | [Procedure structure](../../../skills/spec-writing/scripts/test_spec_docs.py "skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_procedure_needs_label_and_two_direct_actions") |
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
spec-docs: error D10 docs/example.md:49: value link differs from home at docs/example.md:46; align the label with the canonical value
spec-docs: 1 error, 0 warnings
```

The same check with `--json` returns:

```json
{"errors": [{"code": "D10", "line": 49, "message": "value link differs from home at docs/example.md:46; align the label with the canonical value", "path": "docs/example.md", "severity": "error"}], "ok": false, "warnings": []}
```

The line numbers belong to the exact minimal source; preceding edits can change them. Both examples locate the conflicting link and home without copying document prose or values into diagnostics.

For another diagnostic, a tour declares a prerequisite on a later admission section. Without a direct source link to that prerequisite, checking reports `D16`.
Add `See [Admission](admission.md#admission) for the capacity rule` inside the tour's selected section. A generated map link alone does not satisfy this rule.

`D02` includes duplicate JSON keys, unsupported versions, unknown fields, malformed patterns, invalid declarations and conflicting snapshot arguments. Its message identifies the rejected shape. `D27` names failures reading Git, source, runtime inputs or destinations. A diagnostic's code alone does not certify the document's technical validity.

Codes `D09`, `D19`, `D20` and `D23` are retired. Warning `W03` is also retired. There is no typed-value evaluator, reference-valued fact resolver or heuristic claim that ordinary numerals identify unlinked fact restatements.

Warnings guide review without changing command success or blocking pack preparation. Review every remaining warning group and state whether it reveals a concrete problem or why its wording is retained.

The [direct-link behavior](checking-and-navigation.md#documentation-checker) distinguishes blocking missing links from advisory phrase ambiguity. Unlinked literal restatements and unregistered technical meanings require [semantic review](writing-and-review-workflow.md#semantic-review). A warning becomes a finding only when review demonstrates the contradiction or reader problem.

<a id="selector-audit"></a>
## Selector audit

The selector audit checks executable acceptance references against results from the normal test run. Run `python skills/spec-writing/scripts/audit_selectors.py --root REPOSITORY --report 'reports/*.xml'` after a successful structural check. Repeat `--report` to combine reports. Add `--fixture` only for synthetic fixture authority.

The audit loads declarations and validates Implementation fields; the preceding structural check owns the complete corpus check. It also validates links between the corpus and preserved Markdown.

The audit lists each acceptance identity and its linked requirements, then reports each Implementation selector as passed, missing or failing. A matching JUnit XML testcase passes only when it has no failure, error or skipped child. No matching case counts as missing. If several cases match, any failure, error or skip makes the selector failing. Acceptance requires zero missing and zero failing selectors. Repeated citations share one result and each citation contributes to the counts.

Report paths and globs resolve from the repository root. Explicit `--report` arguments override per-runner `reports`. Every supplied pattern must match a readable report.

Malformed XML or a root other than `testsuite` or `testsuites` is an invocation error. A testcase must have `name` and `classname`. These errors name the report and ask the caller to regenerate it. An empty report is valid and leaves cited cases missing. Report mode never executes tests or silently falls back.

Reports must come from the accepted candidate's normal test run; the audit does not attest their freshness.

For Python unittest, `tests/test_batches.py::Suite::test_full` matches `name="test_full"` and either `file="tests/test_batches.py"` with `classname="Suite"` or a module-qualified classname ending in `.Suite`, or, without `file`, `classname="tests.test_batches.Suite"`. Nested class components use dots in classname. File attributes use root-relative paths with `/` separators; a leading `./` is accepted. Declared runners can use the [testcase mapping](source-formats.md#metadata) for other frameworks. For Vitest, declare the report attributes that equal the file and full `describe > test name` selector. Spaces in these selectors are preserved.

Generate Python reports without dependencies using `python skills/spec-writing/scripts/junit_unittest.py --report reports/spec-writing.xml discover -s skills/spec-writing/scripts -p 'test_*.py'`. The arguments after `--report PATH` are unchanged unittest arguments. Plain `python -m unittest discover` remains available locally.

The runner writes root-relative `file`, module-qualified `classname`, method `name` and duration in seconds. Failure, error or skipped children include subtest and fixture errors. Each test execution gets its own testcase, including repeated runs of one test object. It preserves unittest's exit status and fails visibly if the report cannot be written. The XML report is a rebuildable test-run artifact, not an independent source of truth.

Without explicit or declared reports, the audit batches all unique cited selectors of each runner once. Python uses one in-process unittest suite inside one child process, loading each file once. Loader errors or empty suites are missing selectors. Failures, errors or skips fail their selector.

Python fallback imports packaged tests by their native dotted names with each package root on `sys.path`. Relative and absolute imports therefore share module identity. If cited files from different roots share a top-level package name, the batch is refused before loading either file. The diagnostic names the package and both roots and asks the caller to supply runner reports. The unsuccessful batch marks its selectors failing. Standalone files retain distinct `_selector_N` module names.

Other runners require a declared `batch` command that receives every full selector in one invocation and writes a JUnit report at `{report}`. Absence of a batch declaration is an invocation error naming the report or batch fix. Children receive EOF on standard input. No path starts a process per selector.

`--timeout-seconds` is a positive per-batch runaway ceiling, defaulting to 300 seconds. A timeout kills that batch's process group, closes output pipes without draining descendant-held handles and marks all its selectors failing. A runner that cannot start or exits unsuccessfully fails its batch visibly, even if it wrote passing cases. Successful batches use the same report matching as report mode. Each selector line records its outcome; each runner batch records runtime. The final line reports `passed`, `missing` and `failing` counts.

The audit reads live files under its root. It has no staged or commit-execution switch. Use a checkout matching the accepted candidate for execution evidence. The [report and batch acceptance cases](acceptance-evidence.md#test-selector-reports) cover report outcomes, refusal, Python report generation and batched fallback.

Inspection, analysis and demonstration cases omit Implementation and link their evidence. Their meaning and adequacy receive review under the [acceptance evidence distinction](acceptance-evidence.md#acceptance).

<a id="selector-audit-interrupted"></a>
### Failure state: interrupted selector batch

An interrupted batch cannot establish passing acceptance evidence. Cleanup separates the audit's temporary resources from effects produced by tests.

**Trigger:** A batch exceeds its timeout, a runner is interrupted, or the audit itself is interrupted.

**Outcome:** A timeout or unsuccessful runner marks every selector in that batch failing. An interrupted audit ends unsuccessfully and may leave incomplete results; those results do not establish acceptance.

**Retained state:** On timeout, the audit kills its child process group and closes its output pipes. Normal unwinding removes its temporary report directory. An interrupted audit may leave that directory or child processes behind. Effects produced by the tests remain; the audit does not roll them back.

**Recovery:** Terminate any remaining audit child process group and remove its leftover temporary report directory. Recover test effects through the repository's own recovery procedure, then rerun the tests and audit. The audit supplies no recovery for test-owned effects.

**Actor:** The audit performs normal cleanup. The caller recovers resources left by an interrupted audit; the repository's designated actor recovers test effects.

**Authority:** The caller needs authority over its audit process group and temporary directory. Recovery of test effects requires the authority defined by the repository's own procedure.

**Verification:** [Report and batch acceptance cases](acceptance-evidence.md#test-selector-reports).

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
