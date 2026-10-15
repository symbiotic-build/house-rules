<a id="behavior-and-change"></a>
# Requirements, tests and failures

Authors connect required behavior to evidence so reviewers can detect violations and reassess later changes. The bounded batch supplies one concrete obligation: a full batch returns `Full` and retains its items. Its declarations connect that result to verification without creating a separate traceability store.

<a id="behavior-and-evidence"></a>
## Behavior and evidence

Review needs the required result, its evidence and the consequences of refusal together. A [requirement declaration](#requirement-declaration) states the behavior, and an [acceptance test](#acceptance-test) makes its pass condition assessable. A [scenario](#scenario) joins actions across explanations, while a [failure declaration](#failure-declaration) tells the caller what refusal retains and how to recover.

<a id="requirement-declaration"></a>
### Requirement declaration

A requirement declaration is an identified obligation stating an actor, condition, result and verification relationship. It makes a contract reviewable by separating required behavior from the examples that explain it.

In the bounded-batch example, the actor is the batcher. When a submitted item would exceed capacity `2`, the required result is `Full` with the existing items unchanged. Capacity means the maximum admitted item count, so the third attempted item triggers refusal. The requirement links directly to the capacity row rather than copying its value without a source.

The record supplies Actor, Condition, Result, Verification, Tests, Status and Basis. Its opening explains why the obligation exists. Put the condition before the result in normative English. A quality bound also states operating conditions, measurement and pass condition; literal comparison alone cannot establish any bound's validity.

Every requirement links at least one [acceptance test](#acceptance-test), and each linked case points back to the same requirement. Missing targets, absent relationships and one-sided relationships fail checking. These links establish structural traceability; reviewers still determine whether the case proves the result. Implementation unit tests need no individual documentation requirement unless they serve as declared acceptance evidence.

The explicit anchor starts with `req-` followed by a nonempty kebab-case suffix of lowercase letters and digits. It is permanent and repository-unique across specifications and designs. Preserve it when moving or revising the same obligation. A split or replacement that introduces a new obligation receives a new identity; retired identities remain unavailable for reuse.

<a id="acceptance-test"></a>
### Acceptance test

An acceptance test is an identified verification case with a method, inputs and expected result linked to requirements. It tells a reviewer how to assess an obligation rather than merely asserting that testing exists.

The batcher's inspection case starts with a full batch and one additional item. Its expected result is `Full` and the same retained items. The linked evidence explains the retained-state inspection so the reviewer can assess that expectation. A tour showing refusal does not become an acceptance test without the declared method and requirement relationship.

Each case supplies Method, Requirements, Inputs and Expected. Its permanent anchor starts with `test-` and follows the same suffix and uniqueness rules as a [requirement declaration](#requirement-declaration). Moving a case preserves its identity; replacing it with a different case does not permit reuse of a retired anchor.

Method `test` requires an Implementation field containing executable file-and-selector links. Static checking verifies the link grammar and file destination. The selector audit then executes every declared selector and reports passed, missing and failing counts. Acceptance requires zero missing or failing selectors; a resolvable source file alone does not prove execution.

Methods `inspection`, `analysis` and `demonstration` have linked evidence instead of an Implementation field. That evidence can be a review lens or a run record appropriate to the method. The checker can establish that a link exists, but reviewers establish whether the evidence supports the pass condition. The exact encoding belongs to [Markdown declarations](source-formats.md#markdown-declarations).

The [Selector audit](interfaces-and-encodings.md#selector-audit) reference defines supported executable selectors, timeout configuration and outcome reporting.

<a id="scenario"></a>
### Scenario

A scenario is a declared sequence or branching set of actions with concrete inputs and caller-visible results. It makes a complete behavior trace selectable across the sections that explain it.

For the batcher, a scenario could admit items until the batch fills, attempt one more item, and observe `Full` with earlier items retained. The [minimal corpus](minimal-corpus.md#example-documents) leaves its scenario list empty; its inspection case needs no separate scenario declaration. To make this trace selectable as a whole scenario, declare Purpose, Inputs and Expected, then link its [requirement declaration](#requirement-declaration) and [acceptance test](#acceptance-test). The [source formats](source-formats.md#markdown-declarations) define the record’s encoding.

The [document manifest](documents-homes-and-values.md#document-manifest) names whole scenarios for assignment. Selection includes their containing explanation and the sections containing linked obligations and cases, including cases reached through requirements. A whole-scenario assignment therefore gives the reviewer more than a fragment describing the final error. Selection details belong to [Agent context](agent-context.md#agent-context).

Write each action and its visible result as a procedure step, with exact payloads in labelled detail beneath the action. When actions are concurrent, name the branches and synchronization points. Sequential numbering must not turn independent branches into a serial execution. A completed competing action followed by a later submission is sequential, even if its effect makes the submission fail.

<a id="failure-declaration"></a>
### Failure declaration

A failure declaration is a contract for a stopping condition, its visible outcome, retained state and recovery authority. It lets callers distinguish a refused action from a partially completed one and choose a valid next action.

Explain ordinary behavior first: the batcher accepts an item while capacity remains. Once capacity `2` is reached, another item produces `Full`. The existing items remain unchanged, and the refused item is not added. The caller can submit that item in a new batch using ordinary submission authority.

The record requires Trigger, Outcome, Retained state, Recovery, Authority and linked Verification. An Actor field can identify the participant separately; Authority must make clear who may recover and with what permission. The following illustrative record keeps refusal and recovery together.

```markdown
<a id="failure-full"></a>
### Failure state: full batch

This refusal explains how the caller can submit an item after the batch fills.

**Trigger:** Submission would exceed [2](#capacity) items.

**Outcome:** The caller receives `Full`.

**Retained state:** Existing items remain unchanged.

**Recovery:** Submit the item in a new batch.

**Authority:** The submitting caller may start a new batch.

**Verification:** [Full batch](#test-capacity).
```

Every mechanism that stops, refuses or remains blocked needs such a declaration. If recovery is unavailable, state that absence and explain its consequence. A mechanism that cannot stop explains why no refusal applies. Do not suggest that retrying or restarting repairs retained invalid state when the contract does not provide that recovery.

The checker requires the declared fields and resolving verification links. Reviewers trace entry, retained state, restart behavior and possible exits. Public interfaces also need review of how the failure maps to their returned errors. Declaring no recovery exposes a limitation; it does not establish that the limitation is an acceptable design.

<a id="change-review"></a>
## Reviewing a changed contract

A contract change can invalidate evidence even when the evidence’s text stays the same. A changed [requirement declaration](#requirement-declaration) brings its linked [acceptance tests](#acceptance-test) into review even when those cases did not change. A directly referenced [canonical fact](documents-homes-and-values.md#canonical-fact) can trigger the same selection.

Correcting only a link displaying `3` to the capacity row's `2` repairs a literal mismatch. Changing the row itself changes the admission contract. If a requirement directly references that row, comparison reports the affected requirement and its tests. The comparison also observes changes to the fact's status, basis, basis targets and linked qualifications, because these can change the claim without changing the literal.

Comparison derives new, changed and removed requirements from both snapshots. It includes old and new declaration text, linked cases from both sides, and added or removed test relationships. A requirement move retains its permanent anchor, so comparison can follow the obligation across files or documents. A textual change within its declared subtree can also select it; the report is not a semantic equivalence proof.

Review input must include every selected case from both snapshots. Removing a requirement also needs a resolving decision reference supplied by the task or work item. The checker verifies that this reference resolves. Reviewers determine whether the authority permits removal and whether the retained contract remains complete. The existing review resolution records that disposition.

When a Git-backed base is supplied, checking derives retired requirement and test anchors from that base's reachable history. It reads historical manifests to find declared contract paths, then parses relevant distinct blobs. Literal code examples do not reserve identities because only actual declaration headings count. Without a Git-backed base, reviewers check historical reuse themselves.

The underlying Git work consists of native history selection, tree inventory and blob reads. Parsing historical declarations earns its cost by detecting reuse across removed files and earlier versions. The change report is rebuilt from Markdown, metadata and Git; it adds no identity ledger, approval stamp or persistent traceability cache.

The [Writing and review workflow](writing-and-review-workflow.md#authoring-and-review) chapter explains how the editor integrates accepted resolutions. After a contract change, affected authors recheck surrounding explanations and complete [scenarios](#scenario) using regenerated input. An assignment whose baseline is stale is regenerated from the current snapshot; no documentation rebase verifier exists.
