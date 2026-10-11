---
name: agent-lanes
description: Parallel multi-agent orchestration — lane ownership, non-colliding file sets, worktrees, build output inside worktrees, lane cleanup, GPU serialization, subagent git limits, cross-repo etiquette. Use when fanning out subagents, workflows, teammates, or background jobs.
license: MIT
---

# Agent Lanes

Mechanics for the parallel-work invariants in rules/delivery.md §Parallel work. The main thread
stays interactive for the operator; heavy work goes to attached background agents/workflows with
explicit goals.

## Lane rules

- **Ownership.** Each lane's work item lists its explicit file set; before merging a
  lane's work, check its diff against that list.
- **Isolation.** Lanes work in worktrees/branches; the main repo checkout stays untouched.
  Build output lives inside the lane's own worktree (its `target/`, native build dirs under
  its `.tmp/`), so parallel builds never share a lock and removing the worktree removes its
  build output. Only a lane without a worktree uses `.tmp/cargo-target/<lane>` in a shared
  checkout, and it deletes that directory when the lane ends.
  Compiler-cache policy: [worker rules](../../prompts/roles/implementer.md).
- **Git limits.** Lanes push only their own work branches, within the delivery authority
  recorded in the bible (policy: rules/git.md). Commits follow the repo's canon; lanes
  report exactly which files they touched.
- **Multi-repo work (owned repos) is normal.** One work item, a branch per repo touched
  (named per `STRUCTURE.md` after the owning issue),
  and every repo+path in the item's lane declaration. Flag shared-kit impacts for owner
  review — flag, don't block.
- **Audits have round boundaries.** An audit-only request produces findings and proposed
  fixes. Repair and confirmation belong to the round when the operator requested them;
  do not infer mutation authority from a request to inspect or explain. What counts as a
  new round: rules/outcome.md §Resource envelopes.

## Resource budgets

- Respect global provider concurrency across ALL lanes combined (e.g. "provider A under
  500 total, provider B under 2000 in total") — budgets are fleet-wide, not per-lane.
  ⚒ Make one lane the budget owner when several hit the same provider.
- Record the intended concurrency and measurement conditions before launch (bounds and
  measured-run concurrency: [rules/delivery.md §Parallel work](../../rules/delivery.md#parallel-work)).
- Builds and targeted tests follow `rust-canon` §Code rules and use the lane's own target
  directory, never a shared tree where a paused run may depend on the existing binary.

## Lane cleanup

Housekeeping is part of the workflow, not a later chore. Cleanup follows rules/core.md
§Security; these checks are what make a lane's leftovers removable.

- **At lane end.** When its PR merges or the work is abandoned, the lane owner removes its
  worktree and any build directory outside it in the same step as deleting the branch
  (skill `design-flow` §6).
- **Not before.** A lane with an open PR keeps its worktree and build output while it waits
  for review or CI, however long it idles; later fix rounds rebuild incrementally from it.
  Under disk pressure, clear finished experiment and benchmark checkouts first, then ask
  the operator.
- **At session start, for every repo the session works in**, remove stale lanes left by
  any session: linked worktrees whose branch is merged (its PR merged at the same head, or
  its HEAD is on the default branch), and `.tmp/cargo-target/<lane>` directories whose lane
  no longer exists. Then run `git worktree prune`.
- **Removable only when all hold:** no uncommitted changes (`git status --porcelain` is
  empty); no commits missing from the remote (`git log HEAD --not --remotes` is empty, or
  its PR merged at this HEAD or a descendant of it — a squash merge deletes the branch);
  no evidence, run results or secret files to keep (`.debug-session/`, `runs/`,
  `.env.local`; move them to the main checkout first, without overwriting existing
  files); and no running process has its working directory or open files inside it.
  `git worktree remove` deletes ignored files, including build output.
- Anything failing a check stays. List it with the failing check in the session report;
  the owning lane or the operator decides.
- Shared caches (compiler cache, model caches) stay.

```bash
git worktree list --porcelain            # candidates: branch + HEAD per worktree
gh pr list --state merged --head <branch> --json headRefOid   # merged at this head?
git -C <wt> status --porcelain; git -C <wt> log --oneline HEAD --not --remotes
lsof +D <wt>                             # nothing may be using it
git worktree remove <wt> && git branch -D <branch>; git worktree prune
```

## Orchestration patterns

- **Recon sweep → design → build → proportional critique → gate → fix.** When to add an
  adversarial verifier: rules/delivery.md §Parallel work.
- **Decision handling.** Lanes decide and escalate per skill `operator-protocol`
  §Decisions.
- **Attached workers.** rules/core.md prime rule 15.
- **Background monitors.** Every long-running run has a watcher that surfaces failures instantly
  and feeds concrete counters into status lines. Prove work is running: process name, output
  path, dashboard link.
- **Handoff on saturation.** A lane near context limits writes a handoff and dies; a fresh
  agent with a handoff beats a saturated one every time (skill `handoff-continuity`).
