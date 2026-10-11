---
name: decision-brief
description: Present one or more decisions to the operator so they can choose without reading anything else — context, what exists today, options with side effects, a recommendation and an answer format. Use whenever a choice needs operator input, in chat or as a document, including follow-ups that go deeper on one decision. Not for recording a decision already made (spec-writing §Decisions) or for audit findings (audit-report-authoring).
license: MIT
---

# Decision Brief

Write every brief with skill `operator-writing`; option formatting follows
[operator-writing §Structure](../operator-writing/SKILL.md#structure).

The reader is deciding, not reviewing your work. They must understand each choice, what
it changes and what it costs, without opening another document. Missing context is the
most common failure: a term, a mechanism or a side effect the reader cannot see.

## Scale

| Size | Shape |
|---|---|
| One or two decisions in chat | The per-decision block below, plus a short glossary of only the terms it uses and a one-line answer format. |
| Three or more decisions, or any decision that changes a design | A Markdown document with the full structure below ([rules/session-writing.md §Format](../../rules/session-writing.md#format)), sent to the operator as a file they can open, never only a local path. |
| A follow-up asking for depth on one decision | That decision's block again, expanded, with a diagram of the data or flow it concerns. Keep its ID. |

## Explaining on request

When the operator asks you to explain something, says there is not enough context, or does
not understand a decision, answer in this shape rather than restating the summary:

1. **One concrete example end to end,** with a diagram of what is stored or what
   flows where, using real names and realistic sizes.
2. **What each thing physically is:** where it lives, what it owns (access, history,
   lifecycle), what it points to, and what it is not.
3. **The dividing tests,** stated as questions with an answer for each case (for example:
   "did a producer compute it from something stored? then it is derived").
4. **Trade-offs as a table with numbers** — quality, cost, storage, latency, limits — each
   number labelled with its basis.
5. **What is recorded and how it is regenerated** when inputs, versions or settings change.
6. **Gaps the explanation exposed,** labelled as gaps, with a recommendation.
7. **Decisions,** with stable IDs, options and a recommendation, answerable in one line.

Ground every claim in the current spec or code; say where the spec is silent.

## Document structure

1. **What you are deciding.** One line per decision with its ID, then how to answer
   (`Decision 1 = Option 2, Decision 2 = Option 1`).
2. **Glossary.** Each term once, in plain language, with a small example. A small brief
   lists only the terms its decisions use; never skip a term the reader may not know.
3. **Walkthrough.** One concrete example followed through the system as numbered steps
   (W1, W2 …) that decisions refer back to. Mark each step's real status (built, merged,
   missing).
4. **Decisions,** each in this order:
   - in one sentence;
   - what exists today, with evidence;
   - why it was added (what it did before a removal, or what gap an addition fills);
   - what depends on it;
   - the problem;
   - options — each with what changes, a before/after example, side effects including
     what breaks or gets harder, and size per
     [rules/core.md prime rule 13](../../rules/core.md#prime-rules);
   - recommendation, and why each other option is rejected;
   - next steps if chosen.
5. **Reopened settled decisions,** each with the new evidence that reopened it, kept
   separate and not adopted by default.
6. **Impact** by component or work package.
7. **Evidence appendix** (skill `audit-report-authoring` §Evidence).

## Before sending

The brief's author, usually the lead, runs these checks before the operator sees the
brief, also when a subagent drafted the questions. Fix a brief that fails one; never send
it.

- The brief passes [rules/writing.md §Checks before sending](../../rules/writing.md#checks-before-sending).
- The brief defines every term it uses.
- A concept the brief introduces says why it exists and what happens without it.
- Each decision lists the real alternatives with their side effects, including the
  simplest design and, when a dependency limit drives the choice, a change to that
  dependency.
- No option takes its shape or counts from code scheduled for removal or replacement
  ([premise check](../../prompts/util/premise-check.md)).

## Rules

- Follow [rules/writing.md §Claim labels](../../rules/writing.md#claim-labels).
- One recommendation per decision. Options must be genuinely viable.
- Stable decision IDs (`Decision 1`, `Decision 2`) across the brief and every follow-up.
  Option formatting: [operator-writing §Structure](../operator-writing/SKILL.md#structure).
- Concrete over abstract: real names, sizes and numbers with their basis, and a
  before/after example for every change.
- Comparisons and diagrams follow [rules/writing.md §Format](../../rules/writing.md#format).
- Organize by consequence, not by the order the work happened. No activity logs.
- After the operator answers, record each choice where it belongs (rules/core.md prime rule
  11) and stop asking about it until new evidence reopens it
  ([rules/writing.md §Claim labels](../../rules/writing.md#claim-labels)). A reopened
  decision gets a new brief that states the new evidence.
- For a foundational choice, every option carries its premise-check counts
  ([premise check](../../prompts/util/premise-check.md)).
