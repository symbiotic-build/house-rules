---
name: reasoning-moves
description: Proportional reasoning checkpoints for complex changes, experiments, investigations, and evidence-based reports. Use when assumptions, causal claims, or verification need a deliberate check; scale to the task without relying on model-tier labels.
license: MIT
---

# Reasoning Moves

Use the relevant checkpoints to catch unsupported assumptions and wasted work. They are
a review aid, not a requirement to narrate every step, invent extra documents, or apply
an experiment protocol to a simple question. Decision authority and the operator's
selected collaboration mode come from rules/core.md; these checkpoints do not redefine them.

## Ground

- Read current state, existing evidence, and applicable project rules before building
  on assumptions. Reuse settled decisions and valid completed work.
- Verify changing ecosystem facts against current primary sources when relevant to the
  answer. Label unverified assumptions instead of presenting memory as evidence.
- Identify the requested outcome and the uncertainty that matters to it. For a study,
  use `experiment-planning` to establish the comparison and decision criterion
  (controls: skill `bench-discipline` §Controls and attribution).

## Gate

- Before a bug fix, establish what failed, the affected requirement, and how the repair
  will be confirmed (skill `failure-forensics` §Establish what failed).
- Before changing shared files, resources, or live processes, identify their owner and
  the likely impact. Apply the existing authority, security, and resource boundaries.
- For an ambiguous diagnosis, use skill `failure-forensics`; do not force a fixed number
  of hypotheses.
- Support a claimed blocker with observed evidence. Do not attempt a prohibited or
  destructive action merely to prove a known permission or safety boundary.

## Verify

- Confirm that the measured outputs, input coverage, configuration, and measurement
  boundaries match the claim. A successful process exit alone does not establish
  correct behavior.
- Before attributing a delta, prove the change took effect and compare the arms'
  effective conditions (skill `bench-discipline` §Controls and attribution).
- Treat surprising physical signals per skill `failure-forensics` §Performance signals
  are clues; pause dependent conclusions while the measurement is suspect.
- Keep sustained iteration in the campaign ledger (skill `bench-discipline` §Execution
  and record). Preserve evidence before reverting a failed candidate. Avoid layering
  compensating changes on an unexplained regression.

## Report

- Distinguish measured results, source-backed facts, extrapolations, and hypotheses.
  Use [rules/writing.md §Claim labels](../../rules/writing.md#claim-labels).
  Apply its labeling scope and attach the evidence and limits needed to assess each claim.
- For noisy comparisons, report per skill `bench-discipline` §Measurement and uncertainty.
- Inspect enough primary records to verify field meaning, data integrity, and the
  important aggregate claims. Choose coverage for the heterogeneity and consequence
  of the claim rather than a fixed record count. Verify delegated key claims against
  primary evidence before repeating them.
- Lead with the result and explain its evidence, implications, remaining work, and any
  required decision. Follow skills/operator-writing/SKILL.md and rules/core.md prime rule 13.

## Learn

- Tie causal claims to traces, measurements, or reproductions (skill `failure-forensics`).
- After a failed or interrupted run, resume at the cheapest informative point (skill
  `bench-discipline` §Cost ladder).
- Record negative and inconclusive results, tested conditions, and the evidence in the
  work item or campaign ledger. Do not infer a mechanism from a score alone.
- Correct erroneous durable claims explicitly and propagate the correction to affected
  reports (a released report gets an erratum or a new dated report: `STRUCTURE.md`).
  Preserve the original evidence and explain changed interpretations.
- Apply rules/outcome.md §Three-occurrence reassessment before repeating the same failure
  class again. Reconsider the mechanism and scope, not just the next patch.
