---
name: bench-discipline
description: Design and interpret controlled benchmarks, evaluations, A/B tests, and tuning sweeps with production-valid inputs, appropriate uncertainty, and bounded costs. Use for comparative experiments, not as a prerequisite for a simple bug reproduction.
license: MIT
---

# Bench Discipline

Plan a new campaign, and revisit its plan, with skill `experiment-planning`; this skill
executes and interprets the comparison.

Paid experiments run autonomously inside the approved envelope (rules/outcome.md §Resource envelopes); crossing it requires a proposed expansion, never a silent reduction of rigor.

**Waste is never answered by reducing rigor.** Making yourself less capable is not
hardening.

Retrieval evaluations also apply the [retrieval rules](references/retrieval-evals.md).

## Production-valid comparisons

- The evaluated system must use only information available at its intended production
  boundary. Keep held-out answers, labels, and test-only identifiers out of its prompts,
  training examples, routing, and heuristics. Keep evaluation access separate.
- Category routing, regex extraction, and other deterministic logic are valid when they
  implement a production requirement using production-available inputs. Document the
  requirement and evaluate generalization; never special-case held-out items to raise
  their scores.
- Use designated development data for tuning and independent evaluation data for the
  claimed generalization result. Record prior exposure and reuse limitations when an
  independent holdout is unavailable.
- Never tune to match broken gold — cross-check a "miss" against raw source first.
  Cross-check suspicious labels against the raw source and benchmark specification.
  Record label corrections separately so they do not masquerade as system improvement.
  An oracle or gold-assisted diagnostic may estimate a stage's headroom, but label it as
  diagnostic and keep its artifacts separate from production-valid comparisons.

## Controls and attribution

- State the hypothesis, intended decision, acceptance criterion, and independent variable
  before launch. Preserve other relevant conditions across arms: inputs, software,
  configuration, measurement process, hardware, and runtime conditions. A model, judge,
  concurrency level, or dataset can itself be the declared variable; explain what that
  comparison measures and what it cannot isolate.
- Choose an appropriate baseline or control. A feature-off arm is useful when it isolates
  the feature; a no-op or oracle is useful only when it answers the actual question.
  Verify that controls measure the intended behavior before interpreting the treatment.
- Prefer a single changed factor when attributing a mechanism. A planned factorial or
  bundled comparison is valid; attribute conclusions only as narrowly as the design
  supports and investigate interactions when they matter to the decision.
- Prove the change took effect through effective configuration, executed paths, or output
  artifacts. A large change with little effect warrants a wiring check, but may also be
  a valid null result or insufficient precision; distinguish them with evidence.
- The baseline run is the bare default run — zero tuning env vars; flags exist only
  for the lever under test. When a default flips, re-baseline — scores across a default
  change are not comparable; running the old value afterwards is a pinned, named test.
- Keep experiment settings explicit and reproducible. Name the baseline configuration;
  do not silently change shipped defaults to simplify a benchmark command (rules/core.md
  §Autonomy).
- When drift or a configuration error affects a run, identify the affected measurements,
  record their validity limits, and repeat only the comparisons whose evidence is no
  longer usable. Preserve the original artifacts and the correction.

## Measurement and uncertainty

- Choose the metric, direction, aggregation, sampling unit, pairing, and uncertainty
  method for the workload and decision. Means, quantiles, ranks, and rates answer
  different questions; no single summary is universally preferred.
- Determine repeat counts from observed variability and the precision needed for the
  decision, within the approved budget. A deterministic check may need no replicates;
  one noisy observation usually supports exploration rather than a reliable comparison.
- Account for dependencies such as repeated requests for the same item or shared seeds.
  Pair comparable units when appropriate. Reusing stored stochastic outputs isolates
  downstream effects; resampling them measures a different source of uncertainty.
- Report sample size, relevant spread or uncertainty, effect size, and limitations beside
  the result. Overlapping or separated sample ranges alone do not establish a win or a
  null effect. If the evidence cannot resolve the decision, say so; propose a more
  informative design within the resource envelope rather than declaring a winner.
- Predefine any subgroup analysis used for a decision where feasible. Label exploratory
  slices as exploratory and avoid treating repeated searches for a favorable subset as
  independent confirmation.

## Cost ladder — cheapest useful evidence

- Start with existing artifacts, a single-item probe, or a small smoke workload when it
  can answer the question. Scale when the next run provides decision-relevant evidence,
  including confirmation of a null result or a correctness check.
- Reuse valid compatible artifacts and resume completed stages. A planned independent
  replicate is new evidence, not redundant work. Inspect in-flight work before launching
  duplicates; obey the approved concurrency and stop conditions. Paid runs may run in
  parallel inside the approved envelope. Before a new run of the same experiment starts,
  finish or cancel its in-flight run. The agent chooses which, by best judgment.
  Paid-run parallelism does not cover benchmarks or measured performance runs: [rules/delivery.md §Parallel work](../../rules/delivery.md#parallel-work).
- Validate a judge or grader against its specification and representative source-backed
  examples before trusting it. Inspect relevant raw traces when aggregate results are
  surprising; use `failure-forensics` for an unexplained failure or regression.
- Use current provider units and pricing for estimates, and distinguish estimated cost
  from billed cost.

## Execution and record

- Match the build profile, workload, and concurrency to the deployment or study question.
  Define expected resource behavior before diagnosing serialization or low utilization.
  Measured-run concurrency and overlap: [rules/delivery.md §Parallel work](../../rules/delivery.md#parallel-work). This skill does not
  relax stronger shared-host, provider, or hardware restrictions.
- Checkpoint expensive or non-reproducible stages according to the continuity policy.
  Record with each run: revision, effective configuration, dataset version, seed when
  applicable, model/provider settings, measurement environment, output paths, actual
  usage and cost, deviations from the plan, and the next decision.
- Keep each run's tried → result → verdict record in the work item, and in the campaign
  ledger for sustained iteration (skill `work-tracking`). Store large or sensitive run
  artifacts under the project's retention policy and link the evidence.
