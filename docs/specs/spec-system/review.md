<a id="semantic-review"></a>
# Semantic review

Semantic review finds incorrect meaning and missing explanation that structural checks cannot establish.

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

The [dispatcher](../../design/75-subagent-profiles.md#dispatcher) validates technical, readability, design/cost, failure/recovery and whole-[scenario](scenarios.md#scenario) coverage.
One generalist may cover several responsibilities.
Coverage validation launches no additional reviewers.

Use the [fresh-reader procedure](../../../skills/spec-writing/SKILL.md#fresh-reader-review) for the readability responsibility.
Its reader must explain this document's tour, refusal and recovery without author coaching.
Registry reference material cannot replace a missing explanation.

<a id="failure-review"></a>
### Failure state: incomplete review assignment

This refusal explains incomplete review assignment and the actor who can recover.

**Trigger:** The plan omits a required responsibility or linked-test review input.

**Outcome:** Preparation fails with the missing coverage named.

**Retained state:** Existing source and findings remain; no extra reviewer launches automatically.

**Recovery:** Repair the assignment using the approved reviewers and regenerate its input.

**Authority:** The lead assigns responsibilities inside the existing review resource envelope.

**Verification:** [Real authoring and review](acceptance.md#test-real-use).

In the bounded-batch example, reviewers check that `Full` preserves the existing items, rather than trusting a resolving test link.
The exact files are explained later in [Minimal corpus](example.md#minimal-example).
