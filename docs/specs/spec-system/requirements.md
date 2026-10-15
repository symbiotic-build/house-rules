<a id="requirements"></a>
# Requirements

These obligations specify the observable results of authoring, checking and preparing documentation. The mechanisms explain how those results arise; each record below links reciprocal acceptance evidence.

<a id="requirement-coverage"></a>
## Required system behavior

These records let implementers and reviewers find each obligation independently of its explanatory chapter. Their permanent identities survive changes to headings, wording and chapter locations.

<a id="req-roles"></a>
### Requirement: complete document roles

Make each document provide the explanations its audience needs.

**Actor:** [Documentation checker](checking-and-navigation.md#documentation-checker) and editor.

**Condition:** A document is checked or presented for approval.

**Result:** Require purpose, audience, scope and non-goals, followed by tour, mechanisms, requirements, decisions, questions, reference and acceptance. Keep declared roles in order and refuse unresolved implementation contracts at approval.

**Verification:** Exercise complete corpora, draft gaps, misordered roles and approval refusals.

**Tests:** [Complete document roles](acceptance-evidence.md#test-roles).

**Status:** specified.

**Basis:** [Source decision](decisions-and-open-questions.md#source-decision).

<a id="req-homes"></a>
### Requirement: unique homes and direct links

Keep each registered meaning reachable at one complete source home.

**Actor:** [Documentation checker](checking-and-navigation.md#documentation-checker) and home owners.

**Condition:** [Registered entities](documents-homes-and-values.md#registered-entity), facts, names or symbols appear in a corpus.

**Result:** Require unique complete homes, valid document scope and direct first-use and forward-use links. Reject forbidden names and violations of declared naming patterns.

**Verification:** Mutate home anchors, scope, reading order, accepted names and destinations.

**Tests:** [Unique homes and direct links](acceptance-evidence.md#test-homes).

**Status:** specified.

**Basis:** [Source decision](decisions-and-open-questions.md#source-decision).

<a id="req-literals"></a>
### Requirement: literal equality

Prevent a linked display from contradicting the declared value.

**Actor:** [Documentation checker](checking-and-navigation.md#documentation-checker).

**Condition:** A fact row or a link to its anchor is checked.

**Result:** Require exactly one anchor in the declaring Key cell. Compare value-bearing labels with the home literal using only declared normalization; descriptive labels navigate without claiming a value.

**Verification:** Check capacity 2 against displayed 3, then repair the label. Exercise grouping and measurement spellings.

**Tests:** [Literal equality](acceptance-evidence.md#test-literals).

**Status:** specified.

**Basis:** [Literal decision](decisions-and-open-questions.md#literal-decision).

<a id="req-traceability"></a>
### Requirement: reciprocal and changed-test review

Expose the evidence affected by a changed obligation.

**Actor:** [Documentation checker](checking-and-navigation.md#documentation-checker) and review preparer.

**Condition:** Requirements and acceptance cases are checked, with an optional comparison base.

**Result:** Require reciprocal requirement–test links. Report changed requirements and directly referenced fact contracts with tests from both snapshots. Require affected test input and a resolving decision for each removed requirement.

**Verification:** Change requirement fields, test links, fact qualifications and requirement presence across snapshots.

**Tests:** [Reciprocal and changed-test review](acceptance-evidence.md#test-traceability).

**Status:** specified.

**Basis:** [Source decision](decisions-and-open-questions.md#source-decision).

<a id="req-failures"></a>
### Requirement: visible recovery contract

Make the consequences of a stopping path reviewable.

**Actor:** [Documentation checker](checking-and-navigation.md#documentation-checker) and semantic reviewer.

**Condition:** A mechanism can refuse, stop or remain blocked.

**Result:** Require trigger, caller outcome, retained state, recovery or its explicit absence, authority and linked verification. Review whether the stated actor can perform the recovery.

**Verification:** Remove each required field and inspect retained-state recovery against its explanation.

**Tests:** [Visible recovery contract](acceptance-evidence.md#test-failures).

**Status:** specified.

**Basis:** [Source decision](decisions-and-open-questions.md#source-decision).

<a id="req-checking"></a>
### Requirement: deterministic visible checking

Let callers distinguish invalid documents from failed invocation or input access.

**Actor:** [Documentation checker](checking-and-navigation.md#documentation-checker).

**Condition:** A caller checks, generates or selects a corpus.

**Result:** Use one captured source model. Report deterministic uncapped diagnostics and the declared exit status; warnings remain non-blocking. Refuse invalid input without fallback parsing.

**Verification:** Exercise malformed input, path boundaries, multiple defects, warning-only input and command failures.

**Tests:** [Deterministic visible checking](acceptance-evidence.md#test-checking).

**Status:** specified.

**Basis:** [Source decision](decisions-and-open-questions.md#source-decision).

<a id="req-navigation"></a>
### Requirement: rebuildable navigation

Keep the reading map derived from authored declarations.

**Actor:** Navigation generator and documentation checker.

**Condition:** A caller generates navigation or checks its freshness.

**Result:** Derive deterministic output bytes from valid sources. Validate the proposed output before replacing destinations. Report stale or partially replaced output so regeneration can repair it.

**Verification:** Generate repeatedly, mutate summaries, edit generated bytes and interrupt replacement.

**Tests:** [Rebuildable navigation](acceptance-evidence.md#test-navigation).

**Status:** specified.

**Basis:** [Source decision](decisions-and-open-questions.md#source-decision).

<a id="req-toolchain"></a>
### Requirement: pinned tool ownership

Keep all consumers on the shared parsing and selection contract.

**Actor:** Tool integrator and [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler).

**Condition:** The tool is invoked directly or through an extracted compiler.

**Result:** Use the owning runtime contract and dependency lock. Keep helper, profile and format contract from the selected House Rules revision. Refuse mismatched environments instead of switching parsers.

**Verification:** Inspect locked inputs and exercise matching, mismatched and extracted environments.

**Tests:** [Pinned tool ownership](acceptance-evidence.md#test-toolchain).

**Status:** specified.

**Basis:** [Toolchain decision](decisions-and-open-questions.md#toolchain-decision).

<a id="req-snapshots"></a>
### Requirement: isolated snapshot provenance

Make a selected source version independent of later working-tree changes.

**Actor:** Source loader and review preparer.

**Condition:** A caller chooses working-tree, staged or commit input.

**Result:** Read the selected snapshot and record its provenance. Reject stale assignment baselines and rebuild affected packs after registry or home changes.

**Verification:** Compare index and commit results while unrelated working-tree bytes change.

**Tests:** [Isolated snapshot provenance](acceptance-evidence.md#test-snapshots).

**Status:** specified.

**Basis:** [Context decision](decisions-and-open-questions.md#context-decision).

<a id="req-context"></a>
### Requirement: complete bounded assignment input

Give an agent enough source to understand its explicit assignment.

**Actor:** Documentation selector, [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) and [dispatcher](../../design/75-subagent-profiles.md#dispatcher).

**Condition:** A writer or reviewer assignment is prepared.

**Result:** Include compulsory registry, metadata, profile and complete selected explanations from one snapshot. Expand declared dependencies and deduplicate ranges. Refuse unknown scope, stale baselines, missing mandatory input and excessive byte size before dispatch.

**Verification:** Exercise example#main, unknown selectors, whole [scenarios](requirements-tests-and-failures.md#scenario), dependency cycles, range overlaps and exact byte budgets.

**Tests:** [Complete bounded assignment input](acceptance-evidence.md#test-context).

**Status:** specified.

**Basis:** [Context decision](decisions-and-open-questions.md#context-decision).

<a id="req-profile"></a>
### Requirement: structural procedures and advisory prose checks

Apply writing checks without deleting meaning to satisfy counters.

**Actor:** [Documentation checker](checking-and-navigation.md#documentation-checker) and readability reviewer.

**Condition:** Prose and ordered actions are checked.

**Result:** Read the shared versioned profile. Enforce procedure structure and keep approximate language, length and numeral checks advisory. Preserve conditions and qualifications during review.

**Verification:** Check procedure labels, short and long prose, excluded literal content and warning-only success.

**Tests:** [Structural procedures and advisory prose checks](acceptance-evidence.md#test-profile).

**Status:** specified.

**Basis:** [Writing decision](decisions-and-open-questions.md#writing-decision).

<a id="req-review"></a>
### Requirement: review coverage and fresh understanding

Require evidence that the document can be understood without author coaching.

**Actor:** [dispatcher](../../design/75-subagent-profiles.md#dispatcher), editor and reviewers.

**Condition:** The system prepares or accepts authoring and review assignments.

**Result:** Validate technical, readability, design/cost, failure/recovery and whole-scenario coverage. Include affected linked tests. Apply the current fresh-reader procedure with independent corpus construction and chapter ratings.

**Verification:** Inspect normal prepared assignments and cited fresh-reader responses.

**Tests:** [Review coverage and fresh understanding](acceptance-evidence.md#test-real-use).

**Status:** specified.

**Basis:** [Context decision](decisions-and-open-questions.md#context-decision).

<a id="req-adoption"></a>
### Requirement: faithful conversion and branch use

Preserve existing contract meaning while qualifying changes through normal use.

**Actor:** Repository editor and lead.

**Condition:** Existing material adopts the system or House Rules behavior changes.

**Result:** Account for source rules, distinctions, qualifications and settled decisions. Replace competing current contracts together and validate branch-pinned real authoring and review before merge.

**Verification:** Inspect the conversion inventory and source-bound normal-run evidence.

**Tests:** [Faithful conversion and branch use](acceptance-evidence.md#test-real-use).

**Status:** specified.

**Basis:** [Delivery decision](decisions-and-open-questions.md#delivery-decision).
