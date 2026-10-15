<a id="acceptance"></a>
# Acceptance evidence

These cases define how the system's obligations are proved.
They require behavior, successful repairs and visible failures, rather than one assertion per diagnostic code.
An executable implementation link is evidence only after the named test is inspected and run.
No case below claims a completed run merely by existing.

Use small synthetic fixtures.
Every single test must be explicitly bounded and finish in seconds.
Continuous integration owns the full suite; local checks target changed behavior.
Existing test output records triggers, outcomes and runtime.
Add no separate result ledger.
Scale evidence moves to a named replacement rather than disappearing.

<a id="test-roles"></a>
## [Acceptance test](sources.md#acceptance-test): document roles

**Method:** test and inspection.

**Requirements:** [Complete document roles](sources.md#require-roles).

**Inputs:** Single-file and multi-file manifests; missing roles; explicit inapplicability; draft gaps; approved unresolved contracts; production and fixture approval authorities.

**Expected:** Complete documents pass. Missing required content and blocking approval gaps fail visibly. Fixture authority is accepted only by the fixture runner. Review detects classifications that hide specifications or designs.

**Implementation:** Not asserted here; the shared checker fixtures provide execution evidence.

<a id="test-homes"></a>
## [Acceptance test](sources.md#acceptance-test): homes and names

**Method:** test and inspection.

**Requirements:** [Unique homes and direct links](sources.md#require-homes).

**Inputs:** Unique and duplicate anchors; several entities sharing a section; first uses in subsections; repeated forward uses; cross-document uses; wrong-target links; rejected forms; structured naming patterns; literal blocks with adjacent home links.

**Expected:** Valid homes and required direct links pass. Missing, duplicate, out-of-scope or wrongly targeted uses fail. Every repeated literal block before a home has its own adjacent links. Ambiguous ordinary words warn instead of becoming false structural certainty.

**Implementation:** Not asserted here; the shared checker fixtures provide execution evidence.

<a id="test-literals"></a>
## [Acceptance test](sources.md#acceptance-test): literal values

**Method:** test.

**Requirements:** [Literal equality](sources.md#require-literals).

**Inputs:** Multi-row tables with inline Key anchors; missing and duplicate fact anchors; descriptive labels; value-bearing links; grouped digit runs; decimals; punctuation; code-span values; distinct measurement spellings.

**Expected:** Exactly one anchor per declaring row preserves the table. Descriptive labels navigate. Equal literal labels pass after permitted grouping normalization. Mismatches fail. Equivalent measurements and differently formatted literals receive no semantic evaluation. Unlinked restatements remain review work.

**Implementation:** Not asserted here; the shared checker fixtures provide execution evidence.

The [capacity-repair walkthrough](overview.md#capacity-repair) supplies a complete author-facing example.
It proves no product-specific capacity guarantee.

<a id="test-traceability"></a>
## [Acceptance test](sources.md#acceptance-test): traceability and change selection

**Method:** test and inspection.

**Requirements:** [Reciprocal and changed-test review](sources.md#require-traceability).

**Inputs:** Two [source snapshots](context.md#source-snapshot) with added, changed and removed requirements; reciprocal and one-sided links; missing targets; changed literal values, Status, Basis and adjacent qualifications; unchanged linked tests; resolving removal decisions.

**Expected:** Missing and one-sided links fail. Change reports contain declarations and tests from both snapshots, relationship changes and directly referenced changed facts. Review input includes affected tests even when their text is unchanged. Removal without a resolving decision fails. No persistent suspect-link state is added.

**Implementation:** Not asserted here; the shared checker fixtures and review integration provide execution evidence.

<a id="test-failures"></a>
## [Acceptance test](sources.md#acceptance-test): failure completeness

**Method:** test and analysis.

**Requirements:** [Visible recovery contract](sources.md#require-failures).

**Inputs:** Complete and incomplete stopping declarations; an explicit absence of recovery; retained invalid state; authority distinctions; public error mappings.

**Expected:** Missing required fields or unresolved links fail. Review traces entry, retained state, restart and exits. The declared actor can perform the documented recovery, or the consequence of no recovery is explicit. A field-presence check alone does not approve a recovery design.

**Implementation:** Not asserted here; checker fixtures prove structure and [semantic review](context.md#semantic-review) proves recovery meaning.

<a id="test-checking"></a>
## [Acceptance test](sources.md#acceptance-test): checker failures

**Method:** test.

**Requirements:** [Deterministic visible checking](checking.md#require-checking).

**Inputs:** Duplicate JSON keys, unknown fields, malformed patterns, invalid encoding, path escapes, symlinks, unresolved fragments, malformed external URLs, conflicting snapshot options, several simultaneous defects and warning-only prose.

**Expected:** Invalid inputs fail without being skipped. Diagnostics have deterministic order, source locations and no cap. Invocation or input/output failures differ from document errors. Warning-only input succeeds. No network result affects deterministic checking. One parsed model supports all operations.

**Implementation:** Not asserted here; the shared checker fixtures provide execution evidence.

<a id="test-navigation"></a>
## [Acceptance test](sources.md#acceptance-test): navigation and interrupted output

**Method:** test and inspection.

**Requirements:** [Rebuildable navigation](checking.md#require-navigation).

**Inputs:** Standalone and in-file navigation arrangements; changed summaries; direct edits to generated text; an unwritable destination; interrupted replacement of several outputs.

**Expected:** Repeated generation produces identical bytes. Outputs contain only authored navigation claims and direct destinations. Stale or partial output fails freshness. Validation precedes replacement. Unreplaced old output survives failure. Regeneration repairs a partial set. Standalone generated files receive generated-file attributes.

**Implementation:** Not asserted here; generation fixtures provide execution evidence.

<a id="test-toolchain"></a>
## [Acceptance test](sources.md#acceptance-test): toolchain ownership

**Method:** inspection and test.

**Requirements:** [Pinned tool ownership](checking.md#require-toolchain).

**Inputs:** Shared direct dependency input, hash lock and runtime metadata; a supported isolated environment; mismatched installed versions; failed hash acquisition; an extracted compiler package.

**Expected:** Declared runtime and installed versions are checked. Installation uses selected wheels and unchanged hashes. Unsupported input stops visibly without alternate parsers or source builds. Extraction contains helper, profile and format from the same pinned revision. The supported range is not reported as completed compatibility testing.

**Implementation:** Not asserted here; setup and extraction tests provide execution evidence.

<a id="test-snapshots"></a>
## [Acceptance test](sources.md#acceptance-test): snapshot isolation and invalidation

**Method:** test.

**Requirements:** [Isolated snapshot provenance](context.md#require-snapshots).

**Inputs:** A broken staged source with an unstaged repair; a selected commit with dirty working-tree files; captured authoring bytes; a changed registry or home; stale and current assignment baselines.

**Expected:** Staged checking still detects the staged defect. Commit-built output ignores dirty files. Captured authoring input remains immutable. Changes invalidate earlier packs. Provenance labels base and candidate separately. A stale baseline fails or is mechanically rebased before use.

**Implementation:** Not asserted here; snapshot fixtures and preparer tests provide execution evidence.

<a id="test-context"></a>
## [Acceptance test](sources.md#acceptance-test): context selection

**Method:** test.

**Requirements:** [Complete bounded assignment input](context.md#require-context).

**Inputs:** Explicit section and [scenario](sources.md#scenario) selectors; unknown or missing scope; [complete registry](context.md#complete-registry); relevant home uses; ordinary links inside homes; declared transitive dependencies and cycles; overlapping source ranges; omitted mandatory identities; exact and insufficient byte budgets.

**Expected:** Mandatory registry, selected ranges, dependencies, homes, decisions, profile and provenance appear exactly once per source range. Cycles deduplicate. Ordinary home links do not expand selection; declared dependencies do. Whole [scenarios](sources.md#scenario) contain actions, requirements and tests. Missing, stale or excessive input refuses dispatch without truncation. The exact UTF-8 size is reported.

**Implementation:** Not asserted here; context fixtures and prompt integration provide execution evidence.

<a id="test-profile"></a>
## [Acceptance test](sources.md#acceptance-test): [writing profile](reference.md#writing-profile)

**Method:** test and inspection.

**Requirements:** [Structural procedures and advisory prose checks](reference.md#require-profile).

**Inputs:** The shared machine-readable profile; prose exceeding sentence and paragraph targets; quantities and dates; decimals and code-span punctuation; attributed quotations; valid procedures; single-item numbered lists; exempt operator options; simultaneous actions.

**Expected:** The checker reads one profile owner. Structural procedure violations fail. Approximate writing and numeral findings warn without affecting success or dispatch. Excluded literal content does not distort prose counts. Review retains conditions, uncertainty and consequences instead of deleting them to clear counters.

**Implementation:** Not asserted here; profile fixtures and readability review provide execution evidence.

<a id="test-real-use"></a>
## [Acceptance test](sources.md#acceptance-test): real authoring and review

**Method:** bounded authoring campaign, inspection and fresh-reader review.

**Requirements:** [Review coverage and fresh understanding](context.md#require-review), [faithful conversion and branch use](reference.md#require-adoption).

**Inputs:** An exact branch revision through normal loading and dispatch; single-file and multi-file assignments; a complete converted path with multi-row facts, reciprocal tests and recovery; a naming-content inventory; fresh reader contexts; complete and incomplete review plans.

**Expected:** Real assignments use branch rules and complete mandatory input. Missing coverage stops preparation without launching extra reviewers. Converted homes preserve names, meanings, boundaries, actors, states, interfaces, qualifications and settled decisions. Fresh readers explain the system, complete tour, refusal and recovery from the supplied document alone. Findings identify concrete reader failures. No pack or export is hand-repaired.

**Implementation:** Not asserted here; normal branch-run records provide acceptance evidence.

This case includes actual anchor behavior and useful navigation in the source-reading environment.
Static inspection alone does not establish those results.
The lead reviews existing run output for defects, false positives and required repairs before merge.
