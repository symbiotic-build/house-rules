---
name: work-tracking
description: Track work in Git with a Git-host view — claims, handoffs, and campaign attempts are empty commits with trailers on the work branch (so tracking works offline), mirrored to issues on a project board with one assignee, a Status field, `<issue>-<slug>` branches, and PRs that close their issue. Use when creating, claiming, handing off, or closing work, when coordinating several agents or people, when asked about work state, when working offline, or when migrating a Markdown task ledger (tasks/, NEXT.md).
license: MIT
---

# Work Tracking

The default implementation of rules/delivery.md §Work tracking & continuity. **Git is the record:**
each work item's claim, handoffs, and campaign attempts are commits on its work branch, so
they travel with the code, work offline, and can be read by any Git-native orchestrator.
**The Git host is the shared view:** issues, assignees, a project board, and pull requests,
synchronized whenever the host is reachable. Examples use GitHub Issues, a GitHub Project,
and the `gh` CLI; on another host or orchestrator, map the view and keep the record.

## External reporting

When `custom/INDEX.md` lists an external work-reporting capability, report each lane's
boundaries there: start, checkpoint, waiting, failure and finish. The product installs and
updates itself; agents load it as its own Skill and MCP server, not as part of House Rules.
- Reporting is one-way. It never claims, assigns or controls work.
- Reporting never blocks. If the service is down, continue and note the gap in the handoff.
- Send no code, diffs, prompts, transcripts or credentials.
- Add no reporting scripts or kits to product repositories for this.

## Work item and owner

- A work item has a work branch and, once the host is reachable, an issue. Branches follow
  `STRUCTURE.md`: `<issue>-<slug>`, or `<slug>` until the issue exists.
- The owner holds the branch; on the host, the issue's single assignee is the same owner.
- **Claim:**
  1. When the host is reachable, `git fetch`; the issue must have no assignee.
  2. `git branch -a --list '<issue>-*' '*/<issue>-*'` (for a slug-only item, its slug)
     must print nothing. It covers this clone's branches and remote branches as last
     fetched; a match means the item is taken, unless its latest record has
     `Status: Todo` (released): then check that branch out and record a claim on it.
  3. Create the branch from the default branch in your lane's worktree
     (`git worktree add -b <branch> <path> "$d"`), which refuses a name already taken in
     this clone and its worktrees.
  4. Record a claim (§The Git record).
  5. On the host: assign yourself, re-read the assignees (anyone else listed means
     coordinate first), set Status, and mirror the claim.
- **Takeover** is explicit: work in the worktree that holds the branch, or check the
  branch out (`git worktree add <path> <branch>`); record a claim saying from whom and
  why; then reassign on the host.
- **Release** unfinished work: a handoff record with `Status: Todo`, then set Status and
  unassign on the host.
- Agents that share one host account tell lanes apart by the `Agent` trailer: an issue
  assigned to your login whose latest claim names another agent is taken.
- Priority ([priority labels](../../rules/priority-labels.md)) is a `P0`–`P3` label; dependencies are the host's
  blocked-by links.
- **Approved for later:** work the operator approved that waits on another step or another session
  carries the label `approved` and an `Owner:` line in its body naming the owning session or agent and its
  next action or awaited event. It is one issue per approved deliverable or plan step, not per answer;
  answers are decisions and go where they apply. The issue closes when the work is done. The session-start
  hook lists open `approved` items for the GitHub owners named in the machine-local
  `custom/approved-work.conf`, at every start and after every compaction.

## The Git record

A record is a commit with no file changes on the work branch. Its message file starts with
the subject `chore(<item>): <kind> by <agent>` (or the repository's commit canon), and it
carries trailers:

```
Work-Item: 42          # the issue number, or the slug before the issue exists
Record: handoff        # claim | handoff | attempt
Agent: claude-1
Status: In progress    # Todo | In progress | In review | Blocked
```

- **claim** — the item's definition: Scope, Acceptance criteria, Decisions, and, when
  present, Lane, Design, Execution constraints, and Pre-flight (§The host view). The latest
  claim is the definition; record a new claim whenever it changes (issue body edited, an
  operator or reviewer comment accepted, a campaign's completion gap or knob map updated,
  pre-flight pruned).
- **handoff** — contents: skill `handoff-continuity`. The latest handoff is the
  continuation state. The item's decisions are the latest claim's plus every later
  handoff's Decisions.
- **attempt** — one per campaign attempt: tried → result → verdict (the campaign ledger).

Every record carries the item's Status after it; the host's Status is set from the latest
record. Records are never amended, squashed, or rebased — a rebase changes the SHAs that
mirroring keys on; update a work branch by merging the default branch into it. Merge work
branches with a merge commit so the records stay in the default branch's history; where a
repository requires squash merges, mirror every record before the merge.

## The host view

- **Issue body** — only the owner edits it. It opens with the problem in the issue form of
  skill `operator-writing` §GitHub text (summary, reproduction or current behavior,
  evidence, cause), then holds Scope, Acceptance criteria, Decisions
  (settled and rejected, with why), Lane (paths this item owns while active; skill
  `agent-lanes`), Design (link to the design doc; `STRUCTURE.md`), Execution constraints
  (campaigns that use external resources: outcome, acceptance criteria, explicit
  exclusions, resource envelope, approved external providers, review-round expectations,
  actual resource usage; rules/outcome.md §Resource envelopes), and Pre-flight (multi-phase work:
  verified facts, wrong assumptions to avoid, phase status; maintained and pruned).
- **Mirroring** — each record is posted as an issue comment headed with its kind and agent
  (`## Handoff — claude-1`) and ending with `Mirrors: <full commit sha>`. A record whose
  SHA is in no comment is unposted. Never edit or delete a mirrored comment.
- **Status** — the project's Status field shows the latest record's Status, or Done once
  the merge closes the issue (the project's built-in "item closed" workflow; if that
  workflow is off, the assignee sets it). Only the assignee sets Status; everyone else
  comments. In review starts when the PR opens; Blocked names the blocker.
- **Pull requests** — the PR body says `Closes #<issue>` and carries the closeout
  checklist (skill `design-flow` §Closeout); merging into the default branch closes the
  issue. Work spanning repositories uses one branch per repository; PRs in the other
  repositories reference the issue as `OWNER/REPO#<issue>` without a closing keyword.
- **Board** — the project view, plus the local board (§Commands) for work not yet synced;
  answer status questions from them, never from memory or a status file.

## Session loop: fetch, update, reconcile

The tracker is worked every session, not only written to at the end.

1. **Fetch at start.** Read local work branches and each one's latest handoff. When the
   host is reachable, `git fetch`, read the board for the repositories you will touch
   (items assigned to you, anything In progress or Blocked, and open items that match the
   operator's request), and record a new claim for any item of yours whose issue body
   changed since its latest claim. Continue items you own before starting new ones; when a
   request matches an existing item, work under that item instead of creating a duplicate.
2. **Update as it happens.** Record each Status change in Git (a handoff record) and, when
   reachable, set it on the host and mirror. File each accepted finding, deferral, scoped-out piece, or
   follow-up as a work item in the owning repository when it arises, not at the end, and
   link it from the item, PR, review, or document that set it aside. A line such as
   "deferred", "not done here" or "belongs to the other side" in any document, PR, or
   handoff carries that item's link.
3. **Reconcile before stopping** (session end, compaction, handoff): every item you touched
   has a current handoff record and, when the host is reachable, the right Status and
   mirrored records. Go through the operator's requests from the session: each is done,
   or it has a work item, existing or new. The final report lists the items created,
   updated, and closed.
4. **Surface stale work.** Whoever finds an In progress item with no handoff or activity
   for 7 days comments on it and asks the owner, or the operator if there is no owner,
   to resume, release, or close it.

- Follow rules/core.md §Session start for reading order.

## Offline and sync

Being offline (no network or host down) or without host access (CLI missing, logged out,
missing token scope) changes nothing in the Git record: claim, record, and hand off as
usual and skip the host steps. Offline, only this clone's branches and remote branches as
last fetched are visible, so an issue claimed elsewhere since the last fetch may look free:
claim an existing issue offline only when the operator directs it. New work starts on a
`<slug>` branch with `Work-Item: <slug>`.

When the host is reachable again, sync each work branch:

1. `git fetch`. For a slug-only item, search open issues for the same work and adopt a
   match, otherwise create the issue; rename the branch (`git branch -m <slug>
   <issue>-<slug>`), its design doc, and its prototype folder, and record a claim with
   `Work-Item: <issue>` and `Replaces: <slug>`.
2. If the issue is assigned to anyone but you, a remote branch for it exists that is not
   yours (another name, or your name with commits you lack:
   `git merge-base --is-ancestor origin/<branch> <branch>` fails), or its latest mirrored
   claim names another agent, stop and coordinate (rules/delivery.md §Work tracking & continuity); never merge another agent's
   claim into your branch.
3. `git push -u origin <issue>-<slug>` (delete the old remote name if it was pushed),
   assign yourself, re-read the assignees, and set Status from the latest record.
4. Post unposted records, oldest first.

Missing host access is a pending operator action (INSTALL-AGENTS.md); being offline is
not.

## Commands

Git record, in the lane's worktree. Set `d` to the default branch's name; queries exclude
it both local and fetched (omit `"origin/$d"` without a remote) and match the item's
`Work-Item` (and its slug if it started offline). Set `workspace` to the durable workspace
root and `repo` to the repository name (paths: `STRUCTURE.md`):

```sh
d=main
git branch -a --list '42-*' '*/42-*'                                         # must be empty
git worktree add -b 42-rerank-stage2 "$workspace/worktrees/$repo/42-rerank-stage2" "$d" # claim
git commit --allow-empty --only -F .tmp/record.md \
  --trailer "Work-Item: 42" --trailer "Record: handoff" --trailer "Agent: claude-1" \
  --trailer "Status: In progress"
git log -1 --format=%B -E --all-match --grep='^Record: handoff$' \
  --grep='^Work-Item: (42|rerank-stage2)$' 42-rerank-stage2 --not "$d" "origin/$d"   # latest handoff
git log --reverse --format='%h%x09%(trailers:key=Record,valueonly,separator=)%x09%s' \
  42-rerank-stage2 --not "$d" "origin/$d" | awk -F'\t' '$2 != ""'            # all records
for b in $(git for-each-ref --format='%(refname:short)' refs/heads); do     # local board
  [ "$b" = "$d" ] || git log -1 --grep='^Record: ' --format="$b%x09%(trailers:key=Record,valueonly,separator=)%x09%(trailers:key=Agent,valueonly,separator=)%x09%(trailers:key=Status,valueonly,separator=)%x09%cr" \
    "$b" --not "$d" "origin/$d"
done
```

Host view on GitHub. Project operations (`gh project …` and the `--project` flags) need
the `project` token scope (read-only use needs `read:project`); the operator grants it
with `gh auth refresh -s project`. Set up a project once, before any item has a status:
create the `P0`–`P3` labels with `gh label create`, set the Status options (the mutation
replaces the whole option list and changes option IDs), then record the project number,
project ID, and Status field and option IDs in the bible:

```sh
gh project view 7 --owner OWNER --format json --jq .id
gh project field-list 7 --owner OWNER --format json --jq '.fields[] | select(.name == "Status")'
gh api graphql -f f=STATUS_FIELD_ID -f query='mutation($f: ID!) {
  updateProjectV2Field(input: {fieldId: $f, singleSelectOptions: [
    {name: "Todo", color: GRAY, description: ""},
    {name: "In progress", color: YELLOW, description: ""},
    {name: "In review", color: BLUE, description: ""},
    {name: "Blocked", color: RED, description: ""},
    {name: "Done", color: GREEN, description: ""}]}) {
  projectV2Field { ... on ProjectV2SingleSelectField { options { id name } } } } }'
```

Everyday use, with issue 42 on project 7:

```sh
# create
gh issue create --title "Rerank stage 2" --label P2 --project "Board title" \
  --body-file .tmp/body.md
gh issue edit 42 --add-blocked-by 40
# claim: an empty assignee list means unclaimed
gh issue view 42 --json assignees --jq '.assignees[].login'
gh issue edit 42 --add-assignee @me
item=$(gh project item-add 7 --owner OWNER --url https://github.com/OWNER/REPO/issues/42 \
  --format json --jq .id)
gh project item-edit --project-id PROJECT_ID --id "$item" --field-id STATUS_FIELD_ID \
  --single-select-option-id IN_PROGRESS_OPTION_ID
# mirror a record; list mirrored SHAs
gh issue comment 42 --body-file .tmp/mirror.md
gh issue view 42 --json comments --jq '.comments[].body' | grep -oE 'Mirrors: [0-9a-f]{40}'
# publish the branch and open the PR
git push -u origin 42-rerank-stage2
gh pr create --title "Rerank stage 2" --body-file .tmp/pr.md
# board
gh project item-list 7 --owner OWNER --query "-status:Done" --limit 500
```

Bodies are drafted in `.tmp/` (`STRUCTURE.md`); `--body-file -` reads standard input
instead. `gh project item-add` returns the item ID, adding the issue first if it is not on
the project yet. Never use `gh issue comment --edit-last` or `--delete-last` on a mirrored
record.

## Repository without a Git host

Use the Git record alone; design docs and prototypes use the branch slug in place of an
issue number. Add a host before work spans machines.

## Migration from Markdown ledgers

For a repository still tracking work in `tasks/`, `NEXT.md`, or dated handover files:
create one issue and work branch per live item. Copy its body sections (scope, acceptance
criteria, decisions, lane, design link, execution constraints, pre-flight) into the issue
body and a claim record, its latest handoff into a handoff record, and any campaign ledger
into one attempt record linking the ledger at the last commit before deletion; mirror
them. Rename its design doc and prototype folder to the issue number, and promote finished
items' unpromoted decisions to the bible. Then delete the ledger and its mentions in
repository canon in the same commit. Until that commit the existing ledger stays
authoritative; the two never run as writable trackers side by side (rules/core.md
§Applicability and loading).
