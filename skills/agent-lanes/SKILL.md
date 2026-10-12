---
name: agent-lanes
description: Parallel multi-agent orchestration — lane ownership, non-colliding file sets, worktrees, build output inside worktrees, lane cleanup, shared-machine locks for builds, tests and review panels, GPU serialization, subagent git limits, cross-repo etiquette. Use when fanning out subagents, workflows, teammates, or background jobs, and before builds, test suites or review panels on a shared machine.
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

## Shared machine

Commands for the turn-taking rules in
[rules/delivery.md §Parallel work](../../rules/delivery.md#parallel-work).
[`scripts/turn.py`](scripts/turn.py) waits for the build lock or a free review slot and for the
load to allow a new job. It then runs one command at nice 10 with the job limit, and releases
the lock when the command exits. Cancelling the helper stops the command's whole process group
and keeps the lock until that group has exited.

```bash
turn=<House Rules checkout>/skills/agent-lanes/scripts/turn.py
python3 "$turn" build -- cargo test -p intake        # one build or test command per turn
python3 "$turn" build -- cmake --build build         # make, cmake and cargo read the job limit from the environment
python3 "$turn" build -- ninja -j "$(python3 "$turn" --jobs)"   # other tools get it as a flag
```

- Wrap each heavy command on its own. Never wrap a shell, an editor, a watcher or a whole
  script of edits and waits.
- Locks live in `${HOUSE_RULES_LOCK_DIR:-~/.local/state/house-rules/locks}` as `build.lock`
  and `review-1.lock` to `review-<n>.lock`, with n = `HOUSE_RULES_REVIEW_SLOTS` (default 3).
  Never remove them while agents run. Agents under different user accounts on one machine
  set `HOUSE_RULES_LOCK_DIR` to one shared directory.
- `HOUSE_RULES_JOBS` sets the machine's job limit and `HOUSE_RULES_MAX_LOAD` the load above
  which no new job starts. A lower job count the caller set, such as a build queue's core
  budget, stays in force; a higher one is lowered to the job limit.
- Without the House Rules checkout, `lockf -k <lock file> nice -n 10 <command>` on macOS or
  `flock -o <lock file> nice -n 10 <command>` on Linux takes the same lock. `-k` keeps the
  file; without it `lockf` removes it. These forms set no job limit and skip the load check.
- `skills/pr-ready/scripts/review-panel.sh` takes a review slot itself and runs at most half
  the job limit of reviewers at once. Its Codex reviewers run with
  `--ignore-user-config --disable shell_snapshot`, which starts one process per reviewer
  instead of the user's MCP servers, plugins and hooks.
- Review from a detached worktree at the reviewed head, so no build output sits beside the
  code: `git worktree add --detach <lane folder>/review <head>`.
  Remove it with the lane (§Lane cleanup).

**Overloaded machine.** Check the load before a heavy job and whenever commands slow down,
and apply the overload rules with these commands.

```bash
getconf _NPROCESSORS_ONLN                         # online cores
sysctl -n vm.loadavg                              # macOS; Linux: cat /proc/loadavg
ps -Ao pid,ppid,pcpu,etime,command -r | head -20  # macOS; Linux: ps -eo pid,ppid,pcpu,etime,args --sort=-pcpu
lsof -a -d cwd -p <pid>                           # working directory: which lane owns it
```

In the report, mark which of the heaviest processes are yours.

**Waiting for another job.** Wait on its process ID or on a file it writes when it ends,
with a deadline, and fail when the deadline passes. A `pgrep -f` pattern also matches the
waiting shell's own command line.

```bash
deadline=$(( $(date +%s) + 3600 ))
while kill -0 "$pid" 2>/dev/null; do
  [ "$(date +%s)" -lt "$deadline" ] || { echo "timeout: $pid still running" >&2; exit 1; }
  sleep 10
done
until [ -e "$done_file" ]; do
  [ "$(date +%s)" -lt "$deadline" ] || { echo "timeout: no $done_file" >&2; exit 1; }
  sleep 10
done
```

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
