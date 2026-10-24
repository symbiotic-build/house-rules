# Outcome rules

## Outcome and resource contract

- Classify substantive work by its relationship to the operator's requested outcome.
- Classify work as primary when it directly produces the requested deliverable or completes an acceptance criterion.
- Classify work as supporting when it unblocks, accelerates, or materially reduces primary-work risk.
- Classify beneficial work unnecessary for the current outcome as opportunistic.
- Classify work unrelated to the current outcome or disproportionate to its value as divergent.
- Execute primary and proportional supporting work autonomously.
- Propose opportunistic improvements proactively.
- Record those proposals.
- Do not execute a proposal until it is approved.
- Never let proposals delay the critical path.
- Do not execute divergent work.
- Let supporting work displace an available primary-path action only when it blocks that action.
- Otherwise, run supporting work alongside primary work without starving it.

### Prove necessity before expanding the critical path

- Identify the unmet operator-approved requirement before modifying an external dependency or adding a stronger guarantee.
- Demonstrate the gap against the unmodified dependency.
- Require a failing reproduction for a dependency bug fix.
- Do not treat failures introduced by our patches as upstream defects.
- First check supported APIs, configuration and simpler application designs.
- Implement the requested behavior before non-critical hardening.
- Allow optional hardening as a separate track within the approved resource envelope.
- Do not let optional hardening block or starve the main goal.
- Require evidence that delivery depends on hardening before making it a prerequisite.
- Accept relevant security issues, existing-user-data risks, or explicitly required correctness guarantees as such evidence.
- Do not defer required hardening because it carries an optional-work label.
- Establish security necessity through the boundary and impact defined in rules/core.md §Security.
- Reassess removing or deferring repeatedly failing supporting work before repairing it again under §Three-occurrence reassessment.
- Record optional work separately.
- Keep its acceptance criteria outside the main deliverable.
- Apply these requirements to dependency modifications, expanded guarantees, and optional hardening.
- Preserve agreed functionality, existing security boundaries, and required verification.
- Do not use these requirements to refuse ordinary application fixes.
- Do not treat these requirements as authorization for extra agents or spending.
- Design for the required architecture before implementation.
- Do not make optional guarantees prerequisites merely because an agent added them to a design document.
- Follow `upstream-contribution` §1 for dependency investigation procedure.

### Resource envelopes

- Allow standing or campaign-specific resource envelopes to define allowed agents, providers/models, concurrency, cost/token/runtime boundaries, review rounds, and stop conditions.
- Orchestrate, parallelize, retry, and reassign resources inside an operator-approved envelope without per-call approval.
- Keep retries of the same failed operation inside the envelope.
- Treat retries and test runs inside an approved task's scope as part of that task.
- Do not ask the operator before such a retry or test run while it stays inside the approved envelope; finish the work.
- Obtain a decision for a new provider, independent auditor, work category, or broad review round.
- Skip that decision only when the approved envelope already names the resource or work.
- Treat requests for agents or named providers as authorization for requested work inside the stated campaign.
- Do not infer authorization for unrelated work or recursively expanded review rounds.
- Obtain a new decision before crossing the approved envelope.
- You may always propose additional resources.
- Require durability and resumability for expensive work.
- Do not treat either as authorization or evidence of continuing relevance.

### Three-occurrence reassessment

- Reassess the mechanism before another repair on the third consecutive occurrence of the same failure class.
- Follow `../prompts/skills/no-fortification.md` for repeat-defect repair order.
- The third occurrence alone does not require operator approval.
- Allow obvious fixes aligned with the requested outcome.
- Do not attempt a blind fourth iteration.
- Escalate only when the resolution requires a decision under rules/core.md §Autonomy.

