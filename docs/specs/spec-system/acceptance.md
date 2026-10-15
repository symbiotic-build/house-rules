<a id="acceptance"></a>
# Acceptance evidence

These cases define how the system's obligations are proved.
They require behavior, successful repairs and visible failures, rather than one assertion per diagnostic code.
An executable implementation link is evidence only after the named test is inspected and run.
No case below claims a completed run merely by existing.
Each section below is an [acceptance test](sources.md#acceptance-test).

Use small synthetic fixtures.
Every single test must be explicitly bounded and finish in seconds.
Continuous integration owns the full suite; local checks target changed behavior.
Existing test output records triggers, outcomes and runtime.
Add no separate result ledger.
Scale evidence moves to a named replacement rather than disappearing.

<a id="test-roles"></a>
## Document roles

**Method:** test and inspection.

**Requirements:** [Complete document roles](sources.md#req-roles).

**Inputs:** Single-file and multi-file manifests; missing roles; explicit inapplicability; draft gaps; approved unresolved contracts; production and fixture approval authorities.

**Expected:** Complete documents pass. Missing required content and blocking approval gaps fail visibly. Fixture authority is accepted only by the fixture runner. Review detects classifications that hide specifications or designs.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_required_document_roles_are_not_optional_for_approval](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_unresolved_contract_blocks_approval](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-homes"></a>
## Homes and names

**Method:** test and inspection.

**Requirements:** [Unique homes and direct links](sources.md#req-homes).

**Inputs:** Permanent prefixed anchors; cross-document duplicates and retired identities; several entities sharing a section; first uses in level-2 sections and their deeper subsections; repeated forward uses; cross-document uses; wrong-target links; rejected forms; structured naming patterns; literal blocks with adjacent home links; linked or numbered headings.

**Expected:** Valid homes and required direct links pass. Deeper subsections do not reset first use; level-2 sections do. Missing, duplicate, out-of-scope or wrongly targeted uses fail. Linked and numbered headings fail. Heading mentions do not satisfy body links. Every repeated literal block before a home has its own adjacent links. Ambiguous ordinary words warn instead of becoming false structural certainty.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_duplicate_anchor_is_not_a_unique_home](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_trace_anchors_require_type_prefix_and_nonempty_kebab_identity](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_trace_identities_are_unique_across_documents_and_retired_records](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_subsections_share_level_two_first_use_scope](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_level_two_sections_restart_first_use](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_heading_mentions_do_not_license_body_uses](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_links_in_headings_are_refused](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_numbered_headings_are_refused_without_changing_anchors](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_acceptance_case_is_identified_by_its_permanent_anchor](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-literals"></a>
## Literal values

**Method:** test.

**Requirements:** [Literal equality](sources.md#req-literals).

**Inputs:** Multi-row tables with inline Key anchors; missing and duplicate fact anchors; descriptive labels; value-bearing links; grouped digit runs; decimals; punctuation; code-span values; distinct measurement spellings.

**Expected:** Exactly one anchor per declaring row preserves the table. Descriptive labels navigate. Equal literal labels pass after permitted grouping normalization. Mismatches fail. Equivalent measurements and differently formatted literals receive no semantic evaluation. Unlinked restatements remain review work.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_literal_values_allow_grouping_and_markdown_formatting](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_mismatched_literal_and_equivalent_measurement_are_refused](../../../skills/spec-writing/scripts/test_spec_docs.py)

The [capacity-repair walkthrough](overview.md#capacity-repair) supplies a complete author-facing example.
It proves no product-specific capacity guarantee.

<a id="test-traceability"></a>
## Traceability and change selection

**Method:** test and inspection.

**Requirements:** [Reciprocal and changed-test review](sources.md#req-traceability).

**Inputs:** Comma-separated implementation links with file paths and test selectors; invalid implementation syntax and missing files; two [source snapshots](context.md#source-snapshot) with added, changed and removed requirements; reciprocal and one-sided links; missing targets; changed literal values, Status, Basis and adjacent qualifications; unchanged linked tests; resolving removal decisions.

**Expected:** Missing and one-sided links fail. Change reports contain declarations and tests from both snapshots, relationship changes and directly referenced changed facts. Review input includes affected tests even when their text is unchanged. Removal without a resolving decision fails. No persistent suspect-link state is added.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_traceability_is_reciprocal](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_changed_fact_and_qualification_select_unchanged_linked_tests](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_implementation_links_resolve_files_and_leave_code_selectors_to_review](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_implementation_requires_only_file_and_selector_links](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-failures"></a>
## Failure completeness

**Method:** test and analysis.

**Requirements:** [Visible recovery contract](sources.md#req-failures).

**Inputs:** Complete and incomplete stopping declarations; an explicit absence of recovery; retained invalid state; authority distinctions; public error mappings.

**Expected:** Missing required fields or unresolved links fail. Review traces entry, retained state, restart and exits. The declared actor can perform the documented recovery, or the consequence of no recovery is explicit. A field-presence check alone does not approve a recovery design.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_failure_declaration_requires_each_field](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_missing_recovery_can_be_explicit_and_explained](../../../skills/spec-writing/scripts/test_spec_docs.py)

Checker fixtures prove structure and [semantic review](context.md#semantic-review) proves recovery meaning.

<a id="test-checking"></a>
## Checker failures

**Method:** test.

**Requirements:** [Deterministic visible checking](checking.md#req-checking).

**Inputs:** Duplicate JSON keys, unknown fields, malformed patterns, invalid encoding, path escapes, symlinks, unresolved fragments, malformed external URLs, conflicting snapshot options, several simultaneous defects and warning-only prose.

**Expected:** Invalid inputs fail without being skipped. Diagnostics have deterministic order, source locations and no cap. Invocation or input/output failures differ from document errors. Warning-only input succeeds. No network result affects deterministic checking. One parsed model supports all operations.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_duplicate_json_keys_are_not_last_value_wins](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_all_declared_metadata_types_fail_visibly_instead_of_crashing](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-navigation"></a>
## Navigation and interrupted output

**Method:** test and inspection.

**Requirements:** [Rebuildable navigation](checking.md#req-navigation).

**Inputs:** Standalone and in-file navigation arrangements; changed summaries; direct edits to generated text; an unwritable destination; interrupted replacement of several outputs.

**Expected:** Repeated generation produces identical bytes. Outputs contain only authored navigation claims and direct destinations. Stale or partial output fails freshness. Validation precedes replacement. Unreplaced old output survives failure. Regeneration repairs a partial set. Standalone generated files receive generated-file attributes.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_generated_navigation_and_attributes_are_freshness_checked](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_generation_preserves_prior_output_on_validation_failure](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-toolchain"></a>
## Toolchain ownership

**Method:** inspection and test.

**Requirements:** [Pinned tool ownership](checking.md#req-toolchain).

**Inputs:** Shared direct dependency input, hash lock and runtime metadata; a supported isolated environment; mismatched installed versions; failed hash acquisition; an extracted compiler package.

**Expected:** Declared runtime and installed versions are checked. Installation uses selected wheels and unchanged hashes. Unsupported input stops visibly without alternate parsers or source builds. Extraction contains helper, profile and format from the same pinned revision. The supported range is not reported as completed compatibility testing.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_runtime_and_dependency_mismatch_stop_without_a_fallback_parser](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-snapshots"></a>
## Snapshot isolation and invalidation

**Method:** test.

**Requirements:** [Isolated snapshot provenance](context.md#req-snapshots).

**Inputs:** A broken staged source with an unstaged repair; a selected commit with dirty working-tree files; captured authoring bytes; a changed registry or home; stale and current assignment baselines.

**Expected:** Staged checking still detects the staged defect. Commit-built output ignores dirty files. Captured authoring input remains immutable. Changes invalidate earlier packs. Provenance labels base and candidate separately. A stale baseline fails or is mechanically rebased before use.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_unstaged_repair_cannot_hide_broken_index](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::SnapshotTests::test_commit_pack_ignores_dirty_bytes_and_snapshot_is_immutable](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-context"></a>
## Context selection

**Method:** test.

**Requirements:** [Complete bounded assignment input](context.md#req-context).

**Inputs:** Explicit section and [scenario](sources.md#scenario) selectors; unknown or missing scope; [complete registry](context.md#complete-registry); relevant home uses; ordinary links inside homes; declared transitive dependencies and cycles; overlapping source ranges; omitted mandatory identities; exact and insufficient byte budgets.

**Expected:** Mandatory registry, selected ranges, dependencies, homes, decisions, profile and provenance appear exactly once per source range. Cycles deduplicate. Ordinary home links do not expand selection; declared dependencies do. Whole [scenarios](sources.md#scenario) contain actions, requirements and tests. Missing, stale or excessive input refuses dispatch without truncation. The exact UTF-8 size is reported.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_dependencies_expand_transitively_and_deduplicate_cycles](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_context_refuses_omission_stale_baseline_budget_and_missing_review_coverage](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-profile"></a>
## Writing profile

**Method:** test and inspection.

**Requirements:** [Structural procedures and advisory prose checks](reference.md#req-profile).

**Inputs:** The shared machine-readable profile; prose exceeding sentence and paragraph targets; quantities and dates; decimals and code-span punctuation; attributed quotations; valid procedures; single-item numbered lists; exempt operator options; simultaneous actions.

**Expected:** The checker reads one profile owner. Structural procedure violations fail. Approximate writing and numeral findings warn without affecting success or dispatch. Excluded literal content does not distort prose counts. Review retains conditions, uncertainty and consequences instead of deleting them to clear counters.

**Implementation:** [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_warnings_do_not_fail_a_valid_structural_gate](../../../skills/spec-writing/scripts/test_spec_docs.py), [skills/spec-writing/scripts/test_spec_docs.py::CorpusTests::test_sentence_counter_preserves_decimals_and_code_punctuation](../../../skills/spec-writing/scripts/test_spec_docs.py)

<a id="test-real-use"></a>
## Real authoring and review

**Method:** bounded authoring campaign, inspection and fresh-reader review.

**Requirements:** [Review coverage and fresh understanding](context.md#req-review), [faithful conversion and branch use](reference.md#req-adoption).

**Inputs:** An exact branch revision through normal loading and dispatch; single-file and multi-file assignments; a complete converted path with multi-row facts, reciprocal tests and recovery; a naming-content inventory; fresh reader contexts; complete and incomplete review plans.

**Expected:** Real assignments use branch rules and complete mandatory input. Missing coverage stops preparation without launching extra reviewers. Converted homes preserve names, meanings, boundaries, actors, states, interfaces, qualifications and settled decisions. Fresh readers explain the system, complete tour, refusal and recovery from the supplied document alone. Findings identify concrete reader failures. No pack or export is hand-repaired.

Normal branch-run records provide acceptance evidence; no executable implementation is asserted here.

This case includes actual anchor behavior and useful navigation in the source-reading environment.
Static inspection alone does not establish those results.
The lead reviews existing run output for defects, false positives and required repairs before merge.
