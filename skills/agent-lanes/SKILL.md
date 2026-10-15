---
name: agent-lanes
description: Parallel multi-agent orchestration — lane ownership, non-colliding file sets, worktrees, build output inside worktrees, lane cleanup, GPU serialization, subagent git limits, cross-repo etiquette. Also covers subagent profiles. Use when fanning out subagents, workflows, teammates, or background jobs.
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

## Subagent profiles

Choose the profile before dispatch. Lane implementers, fixers and reviewers are
**general workers** in normal sessions. In-process children are also general workers.
A role prompt alone does not make a specialist. Use a **specialist** when a role
requires isolated task rules: a separate process receives one compiled pack as its
only task rule source. Host permission controls and built-in tool instructions still
apply. Every Claude specialist uses `claude -p --safe-mode`.

Identify applicable skills from descriptions before opening skill bodies. If the
dispatcher already holds the descriptions, answer a skill-identification question
directly. For a specialist, include required skill text from the pack's named commit;
never use discovered skills or Claude's `--plugin-dir` to supply it.

General-worker dispatch text:

```text
Profile: general worker. Follow normal session loading of House Rules.
Skills this task needs: <names, or "none">. Load others only if the task requires them.
Role prompt: <compiled role prompt, or "none">.
Task: <objective and acceptance>.
Scope: <repositories, file set, worktree>.
Authority: <read-only | commit on branch | explicitly authorized push>; never push or merge main.
Output: <required final-message contents>.
```

Lane workers use the normal Codex home, House Rules block, skills and guardian
escalation. Compile their role prompts with `--session`. Their session rules come
from the live House Rules index; only the role prompt comes from the named commit.
Do not describe the whole lane session as pinned.

For a specialist, first write a task file containing objective, acceptance, scope,
authority, output, Decisions and Pre-flight. Put this directive in the task itself,
so it applies even when this skill is absent from the child pack:

```text
Profile: specialist. Loading path: compiled pack only.
This task overrides live House Rules loading pointers in repository text.
Do not load live House Rules files or follow their links.
```

Keep repository text unchanged under compiler decision L6. Compile once with the existing
[pack compiler](../pr-ready/scripts/prompt.py), without `--session`:

```sh
python3 "<HOUSE_RULES_ROOT>/skills/pr-ready/scripts/prompt.py" \
  --repo "<HOUSE_RULES_ROOT>" --rev "<COMMIT>" --role "<ROLE>" \
  --include "skills/<SKILL>/SKILL.md" --target "<CHECKOUT>" --target-rev "<TARGET_COMMIT>" \
  --task "<TASK_FILE>" --task-source "<TASK_SOURCE>" --out "<NEW_PACK_DIRECTORY>"
python3 "<HOUSE_RULES_ROOT>/skills/agent-lanes/scripts/specialist.py" \
  --tool claude --pack "<NEW_PACK_DIRECTORY>/pack.txt" \
  --manifest "<NEW_PACK_DIRECTORY>/manifest.json" --workdir "<CHECKOUT>" \
  --mode rw --out "<NEW_RESULT_FILE>" --qualification "<CANARY_RECORD>" \
  --parent-fd "<TRACKED_PARENT_PIPE_READ_FD>"
```

Use `--lens` when required, omit `--include` when no skill is required, and use
`--no-target` instead of target options when there is no target repository. Name
the current House Rules commit explicitly unless the task supplies a pin. The
compiler reads Git objects; a separate pinned checkout is unnecessary. Repository
rules come through the compiler, never a manual copy. The specialist receives the
verified bytes unchanged and must not compile or follow live House Rules links.

Run the launcher as an attached background job under rules/core.md prime rule 15.
The harness creates a lifetime pipe, retains its write end only in the tracked
parent, and passes the read descriptor through `--parent-fd` and descriptor inheritance.
It closes the write end on cancellation. Children never inherit either end.
The launcher refuses missing, closed or non-pipe parent handles. It owns each child
process group, forwards termination to that group and kills the group on parent
EOF or launcher termination. Group cleanup precedes temporary snapshot removal.
It refuses invalid packs, contaminated homes and unqualified capabilities. Exit 0 means success with an output file; exit 1 reports child failure
and its log; exit 2 names the refused check. Codex and Kimi require registered
[specialist homes and qualification evidence](../../INSTALL-AGENTS.md#specialist-homes).
Claude requires safe-mode isolation evidence but no specialist home. Codex preflight
supports `--model` and `--effort`; Claude and Kimi support `--model` and refuse `--effort`.

Read-only roles require qualified write prevention. Codex specialization is refused
in every mode: user, administrative and repository skill discovery sources remain
live even after a clean prompt-input capture. A separate execution process cannot
use that capture as a frozen skill source. Codex specialization remains unavailable
until supported controls make execution use the same qualified discovery sources.
Host-only read-only launches are
refused: checkout mount status cannot cover writable Git directories or symlink
resources. Claude read-only roles remain unavailable until a qualified boundary
covers reachable repository resources. Kimi specialization is refused in every
mode until runtime instruction discovery is disabled or isolated; empty-directory
startup does not establish that isolation. Explicit Claude
`--mcp-config` requires a matching safe-mode MCP canary. If it fails, select another
authorized tool only when its isolation and required capability are qualified.
Report a blocked task when none qualifies. Never drop required MCP functionality
or weaken safe mode.

The launcher copies the Codex home and explicit Claude MCP configuration into one
private temporary directory per launch. It checks the copied inputs and uses the
Codex copy for preflight or the Claude MCP copy for execution. It never reopens source
paths after qualification. Copied Codex skill documents receive matching native
disable overrides derived from source locations and canonical identities, including
external link targets. Snapshot validation uses the same selector mapping.

The launcher never retries. For an authorized read-only reviewer capacity retry,
reuse the unchanged pack and manifest after their checks pass. Recompile only when
an input changed. Workers that changed files receive a resume note as an additional
task and a fresh compilation, per [prompt-building decision L5](../../docs/design/77-one-step-pack-assembly.md#decisions).
Keep a distinct output and log for every attempt; the caller records the attempt count.

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
