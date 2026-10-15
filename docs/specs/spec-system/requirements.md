<a id="requirements"></a>
# Requirements

These obligations define the observable behavior that the batch example exercises.
The preceding mechanisms explain their purpose; acceptance provides their evidence.

<a id="req-adoption"></a>
### Requirement: faithful conversion and branch use

This obligation makes faithful conversion and branch use observable to callers.

**Actor:** Repository editor and lead.

**Condition:** Existing specifications or naming material adopt this system.

**Result:** Preserve technical distinctions, qualifications and settled decisions. Replace duplicate current contracts atomically and validate branch rules through normal authoring and review paths before merge.

**Verification:** Compare source inventory with resulting homes and inspect real branch-run evidence.

**Tests:** [Real authoring and review](acceptance-evidence.md#test-real-use).

**Status:** specified.

**Basis:** [Source decision](decisions.md#source-decision), [context decision](decisions.md#context-decision).
<a id="req-profile"></a>
### Requirement: structural procedures and advisory prose checks

This obligation makes structural procedures and advisory prose checks observable to callers.

**Actor:** [Documentation checker](documentation-checker.md#documentation-checker) and readability reviewer.

**Condition:** Authored prose or numbered actions are checked.

**Result:** Read the shared machine-readable profile. Enforce procedure structure; keep approximate language and length checks advisory. Preserve qualifications during review.

**Verification:** Check valid procedures, single-item lists, the operator-question boundary and warning-only prose.

**Tests:** [Prose checks](acceptance-evidence.md#test-profile).

**Status:** specified.

**Basis:** [Writing decision](decisions.md#writing-decision).

<a id="req-review"></a>
### Requirement: review coverage and fresh understanding

This obligation makes review coverage and fresh understanding observable to callers.

**Actor:** [Dispatcher](../../design/75-subagent-profiles.md#dispatcher), editor and reviewers.

**Condition:** A specification or design receives an authoring or review assignment.

**Result:** Validate all review responsibilities and include changed requirements' linked tests. Require a fresh reader to explain the tour, refusal and recovery without author coaching.

**Verification:** Inspect prepared assignments and reader responses through normal entry points.

**Tests:** [Real authoring and review](acceptance-evidence.md#test-real-use).

**Status:** specified.

**Basis:** [Context decision](decisions.md#context-decision).

<a id="req-context"></a>
### Requirement: complete bounded assignment input

This obligation makes complete bounded assignment input observable to callers.

**Actor:** Documentation selector, [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) and [dispatcher](../../design/75-subagent-profiles.md#dispatcher).

**Condition:** A writer or reviewer assignment is prepared.

**Result:** Include every mandatory source range from one snapshot exactly once. Expand declared dependencies, not ordinary home links. Refuse unknown selectors, omitted context, stale baselines and excessive input before dispatch.

**Verification:** Exercise explicit selectors, dependencies, cycles, overlapping ranges, [scenarios](scenario.md#scenario) and model budgets.

**Tests:** [Context selection](acceptance-evidence.md#test-context).

**Status:** specified.

**Basis:** [Context decision](decisions.md#context-decision).

<a id="req-snapshots"></a>
### Requirement: isolated snapshot provenance

This obligation makes isolated snapshot provenance observable to callers.

**Actor:** Source loader and review preparer.

**Condition:** A check or assignment selects working-tree, staged or commit input.

**Result:** Read only the selected snapshot. Record its provenance and reject stale assignment baselines. Regenerate affected packs after source changes.

**Verification:** Compare staged and commit outputs while unrelated working-tree bytes change.

**Tests:** [Snapshot isolation and invalidation](acceptance-evidence.md#test-snapshots).

**Status:** specified.

**Basis:** [Context decision](decisions.md#context-decision).

<a id="req-failures"></a>
### Requirement: visible recovery contract

This obligation makes visible recovery contract observable to callers.

**Actor:** [Documentation checker](documentation-checker.md#documentation-checker) and semantic reviewer.

**Condition:** A mechanism can stop, refuse or remain blocked.

**Result:** Require a complete [failure declaration](failure-declaration.md#failure-declaration). Review whether the named actor can repair retained state without invoking the failing operation again.

**Verification:** Inspect complete and incomplete failure fields and trace the documented recovery.

**Tests:** [Failure completeness](acceptance-evidence.md#test-failures).

**Status:** specified.

**Basis:** [Source decision](decisions.md#source-decision).
<a id="req-traceability"></a>
### Requirement: reciprocal and changed-test review

This obligation makes reciprocal and changed-test review observable to callers.

**Actor:** [Documentation checker](documentation-checker.md#documentation-checker) and review preparer.

**Condition:** Requirements and tests are checked against an optional base snapshot.

**Result:** Refuse missing or one-sided relationships. Report changed declarations and directly referenced facts with tests from both snapshots. Include affected tests in review input and require decisions for removals.

**Verification:** Mutate declarations, relationships, fact qualifications and requirement presence across two snapshots.

**Tests:** [Traceability and change selection](acceptance-evidence.md#test-traceability).

**Status:** specified.

**Basis:** [Source decision](decisions.md#source-decision).

<a id="req-literals"></a>
### Requirement: literal equality

This obligation makes literal equality observable to callers.

**Actor:** [Documentation checker](documentation-checker.md#documentation-checker).

**Condition:** A value is declared or a link targets its fact anchor.

**Result:** Require one home anchor in the declaring Key cell and a resolving target. Compare value-bearing labels as literal text under grouping normalization.

**Verification:** Exercise descriptive labels, equal and unequal literals, punctuation, grouping and equivalent measurements.

**Tests:** [Literal values](acceptance-evidence.md#test-literals).

**Status:** specified.

**Basis:** [Literal-value decision](decisions.md#literal-decision).

<a id="req-homes"></a>
### Requirement: unique homes and direct links

This obligation makes unique homes and direct links observable to callers.

**Actor:** [Documentation checker](documentation-checker.md#documentation-checker).

**Condition:** Registered names, symbols, home declarations or their uses appear in the selected corpus.

**Result:** Require complete unique homes, declared document scope and direct first-use and forward-use links. Refuse rejected forms and structured naming violations.

**Verification:** Check valid uses and mutations of home identity, scope, name, target and reading order.

**Tests:** [Homes and names](acceptance-evidence.md#test-homes).

**Status:** specified.

**Basis:** [Source decision](decisions.md#source-decision).

<a id="req-roles"></a>
### Requirement: complete document roles

This obligation makes complete document roles observable to callers.

**Actor:** [Documentation checker](documentation-checker.md#documentation-checker).

**Condition:** A document is checked or submitted for approval.

**Result:** Require purpose, audience, scope, non-goals, tour, mechanisms, requirements, decisions, questions, reference and acceptance in that order. Refuse blocking unresolved contracts at approval.

**Verification:** Check complete, incomplete, draft and approval-blocked declarations.

**Tests:** [Document roles](acceptance-evidence.md#test-roles).

**Status:** specified.

**Basis:** [Source decision](decisions.md#source-decision).

<a id="req-navigation"></a>
### Requirement: rebuildable navigation

This obligation makes rebuildable navigation observable to callers.

**Actor:** [Documentation checker](documentation-checker.md#documentation-checker) and generator.

**Condition:** Navigation is generated or checked for freshness.

**Result:** Derive bytes deterministically from valid authored declarations. Validate before replacement and refuse stale or partial output.

**Verification:** Generate twice, change an authored summary and edit generated output directly.

**Tests:** [Navigation and interrupted output](acceptance-evidence.md#test-navigation).

**Status:** specified.

**Basis:** [Source decision](decisions.md#source-decision).

<a id="req-checking"></a>
### Requirement: deterministic visible checking

This obligation makes deterministic visible checking observable to callers.

**Actor:** [Documentation checker](documentation-checker.md#documentation-checker).

**Condition:** The caller selects a corpus and operation.

**Result:** Parse one snapshot, refuse invalid inputs and report deterministic uncapped diagnostics with the declared exit status. Keep warnings non-blocking.

**Verification:** Check malformed inputs, path boundaries, diagnostic order, invocation conflicts and warning-only input.

**Tests:** [Checker failures](acceptance-evidence.md#test-checking).

**Status:** specified.

**Basis:** [Source decision](decisions.md#source-decision).

<a id="req-toolchain"></a>
### Requirement: pinned tool ownership

This obligation makes pinned tool ownership observable to callers.

**Actor:** Tool setup and repository integrator.

**Condition:** The shared tool is installed, invoked or extracted with a [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler).

**Result:** Use the pinned runtime contract and wheel versions. Keep helper, profile and format contract from the same House Rules revision. Refuse unsupported or inconsistent environments.

**Verification:** Inspect pins and extraction inputs; run supported and mismatched environment cases.

**Tests:** [Toolchain ownership](acceptance-evidence.md#test-toolchain).

**Status:** specified.

**Basis:** [Toolchain decision](decisions.md#toolchain-decision).

