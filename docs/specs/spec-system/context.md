<a id="context"></a>
# Snapshots, agent context and review

Agents need the same declared meanings that readers receive.
Context preparation derives complete inputs from one immutable selection of source bytes.
It must expose missing or excessive input before dispatch.

<a id="source-snapshot"></a>
## Source snapshot

A source snapshot is one immutable set of repository paths and bytes selected for checking, generation or assignment.

Commit review reads the selected commit.
Staged checking reads the complete Git index.
Authoring captures immutable working-tree bytes.
These modes never mix content.
An unstaged repair cannot hide a broken staged corpus.
Dirty files cannot affect a commit-built pack.

The existing pack manifest records revision or digest, input fingerprints, registry digest, tool and profile versions, assignment and inclusion reasons.
Base and candidate material carry separate labels.
Do not add another provenance store.

A changed registry or home invalidates packs from its earlier digest.
Explicit uses, recognized uses and dependencies identify affected assignments.
Changed requirements also select their linked tests.
Affected authors receive regenerated inputs and changed declarations.
They recheck surrounding explanations and complete [scenarios](sources.md#scenario).
Other assignments require a current-baseline pack or a mechanically verified rebase.

<a id="req-snapshots"></a>
### Requirement: isolated snapshot provenance

**Actor:** Source loader and review preparer.

**Condition:** A check or assignment selects working-tree, staged or commit input.

**Result:** Read only the selected snapshot. Record its provenance and reject stale assignment baselines. Regenerate affected packs after source changes.

**Verification:** Compare staged and commit outputs while unrelated working-tree bytes change.

**Tests:** [Snapshot isolation and invalidation](acceptance.md#test-snapshots).

**Status:** specified.

**Basis:** [Context decision](reference.md#context-decision).

<a id="complete-registry"></a>
## Complete registry

The complete registry is a generated combination of every entity's identity, names, meaning, literal facts and home.

The [entity index](sources.md#entity-index) supplies identity and naming authority.
Markdown supplies meanings and declarations.
The result is transient and rebuildable from the selected [source snapshot](#source-snapshot).
Authors never edit it.
No persistent registry database, cache, mirror or separate traceability store is required.

Every writer and reviewer receives the whole result.
Material outside reading dependencies is marked as reference.
Its presence cannot excuse a missing explanation in a chapter.
There is no universal entity-count limit.

<a id="context-pack"></a>
## Context pack

A context pack contains the complete mandatory documentation input for an explicit authoring or review assignment.

Every writer and reviewer receives the [complete registry](#complete-registry), assigned sections, relevant complete homes, declared dependencies, applicable profile, decisions and provenance.
A home includes its entire heading subtree.
The [document manifest](sources.md#document-manifest) declares explanatory dependencies on sections and gives each a reason.
A home uses its containing section's dependencies.

**Procedure: assemble mandatory context**

1. **Capture the source.**
   - Use one immutable [source snapshot](#source-snapshot).
   - Assemble the [complete registry](#complete-registry).
2. **Resolve explicit selectors.**
   - Select assigned sections or a whole [scenario](sources.md#scenario).
   - Unknown selectors fail preparation.
   - Missing scope never silently selects all homes.
3. **Expand declared dependencies.**
   - Follow them transitively.
   - Deduplicate cycles.
4. **Collect relevant homes.**
   - Find entities owned or used in selected sections through declarations, links and recognized registered uses.
   - Include their complete source ranges.
   - Ordinary links inside an included home do not recursively expand selection.
5. **Emit the input.**
   - Include each source range once.
   - Record identities, exact UTF-8 byte counts and inclusion reasons.
   - Include applicable decisions and the [writing profile](reference.md#writing-profile).

A whole-[scenario](sources.md#scenario) assignment includes every section containing its actions, requirements and linked tests.
Further home expansion requires a declared dependency with a reason.
An ordinary link cannot turn into an unbounded traversal.

The tool counts exact UTF-8 bytes for mandatory documentation input.
The [dispatcher](../../design/75-subagent-profiles.md#dispatcher) applies its configured model budget, including rules, task and response allowance.

Mandatory input is never truncated.
An excessive pack stops before dispatch.
Narrow the assignment or remove an unjustified dependency to recover.
The [complete registry](#complete-registry) remains compulsory.
If it alone cannot fit, the operator must choose a different execution resource.

Extend the existing [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) ([skills/pr-ready/scripts/prompt.py](../../../skills/pr-ready/scripts/prompt.py)) with one documentation-context call.
Reserve its complete output before optional context.
The launcher and review service use the same selector.

An extracted compiler includes its matching helper, profile and format contract from the pinned House Rules revision.
It never imports a helper from an unrelated live checkout.
The review service prepares and checks packs.
Reviewers remain read-only and run no builds, tests or external writes.

<a id="req-context"></a>
### Requirement: complete bounded assignment input

**Actor:** Documentation selector, [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) and [dispatcher](../../design/75-subagent-profiles.md#dispatcher).

**Condition:** A writer or reviewer assignment is prepared.

**Result:** Include every mandatory source range from one snapshot exactly once. Expand declared dependencies, not ordinary home links. Refuse unknown selectors, omitted context, stale baselines and excessive input before dispatch.

**Verification:** Exercise explicit selectors, dependencies, cycles, overlapping ranges, [scenarios](sources.md#scenario) and model budgets.

**Tests:** [Context selection](acceptance.md#test-context).

**Status:** specified.

**Basis:** [Context decision](reference.md#context-decision).

<a id="failure-context"></a>
### Failure state: invalid or excessive assignment

**Trigger:** A selector is unknown, mandatory context is missing, the baseline is stale or the configured budget is insufficient.

**Outcome:** Preparation stops before dispatch and reports the selector, missing input, baseline mismatch or required size.

**Retained state:** Canonical sources and previous packs remain; no previous pack silently substitutes for the failed selection.

**Recovery:** Correct selectors or narrow the assignment, repair dependencies, or rebuild from the selected baseline. If the compulsory registry alone exceeds the budget, obtain an operator resource decision.

**Authority:** The editor may narrow assignments inside scope. The operator authorizes a changed execution resource when required.

**Verification:** [Context selection](acceptance.md#test-context), [snapshot isolation](acceptance.md#test-snapshots).

<a id="semantic-review"></a>
## Semantic review

Semantic review establishes whether checked documents explain correct behavior and provide adequate evidence.

Structural checks cannot establish measurement meaning, test adequacy or complete concurrent behavior.
Warnings do not prove a defect.
A reviewer cites a rule or demonstrates what the reader cannot understand and the consequence.
Formatting that changes behavior receives this review.

One editor owns manifest and entity-index changes per round.
Each entity has one responsible home owner.
Authors receive disjoint assignments and propose changes to facts owned elsewhere.
They do not introduce local replacement definitions.
One fixer integrates accepted findings and refreshes affected assignments.
These responsibilities set no agent count and authorize no larger panel.

The [authoring procedure](../../../skills/spec-writing/SKILL.md#author-the-document) coordinates the outline, home owners, authors and fixer.

The [dispatcher](../../design/75-subagent-profiles.md#dispatcher) validates technical, readability, design/cost, failure/recovery and whole-[scenario](sources.md#scenario) coverage.
One generalist may cover several responsibilities.
Coverage validation launches no additional reviewers.

Use the [fresh-reader procedure](../../../skills/spec-writing/SKILL.md#fresh-reader-review) for the readability responsibility.
Its reader must explain this document's tour, refusal and recovery without author coaching.
Registry reference material cannot replace a missing explanation.

<a id="req-review"></a>
### Requirement: review coverage and fresh understanding

**Actor:** [Dispatcher](../../design/75-subagent-profiles.md#dispatcher), editor and reviewers.

**Condition:** A specification or design receives an authoring or review assignment.

**Result:** Validate all review responsibilities and include changed requirements' linked tests. Require a fresh reader to explain the tour, refusal and recovery without author coaching.

**Verification:** Inspect prepared assignments and reader responses through normal entry points.

**Tests:** [Real authoring and review](acceptance.md#test-real-use).

**Status:** specified.

**Basis:** [Context decision](reference.md#context-decision).

<a id="failure-review"></a>
### Failure state: incomplete review assignment

**Trigger:** The plan omits a required responsibility or linked-test review input.

**Outcome:** Preparation fails with the missing coverage named.

**Retained state:** Existing source and findings remain; no extra reviewer launches automatically.

**Recovery:** Repair the assignment using the approved reviewers and regenerate its input.

**Authority:** The lead assigns responsibilities inside the existing review resource envelope.

**Verification:** [Real authoring and review](acceptance.md#test-real-use).
