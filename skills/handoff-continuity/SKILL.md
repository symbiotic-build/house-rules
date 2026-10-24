---
name: handoff-continuity
description: Session continuity — immutable handoff records before compaction, campaign ledgers, .agents/rules.md bible maintenance, dated reports, filing, and durable paid runs. Use before context compaction, at session end, when work spans sessions, when spawning successor agents, when the operator says "handover", and before launching paid, long-running, or non-reproducible external runs.
license: MIT
---

# Handoff & Continuity

Durable continuation preserves useful context across sessions.

## The 80% rule

At ~80% context (or before any compaction), write the handoff and give it to a successor
that is attached to your lead (a started session, or a background job in the lead's session).
End the session only after the lead confirms the successor holds the work. Also write one at session end and on ownership change. The
handoff is an **immutable record** — by default a handoff record (an empty commit on the
work branch, mirrored to the issue when the host is reachable), or the legacy ledger until
the repository migrates (skill `work-tracking`). Same required contents everywhere:

```
  Objective   — the standing goal, verbatim (incl. numeric targets)
  Completed   — with evidence pointers (run dirs, commits, file:line)
  Pending     — ordered next steps, cheapest/highest-signal first
  Blockers    — exact state: what's running, what's waiting on whom/what
  Decisions   — settled choices made this session + rejected alternatives (with why)
```

Handoffs are events, not documents you maintain: never edit an existing handoff —
corrections go in a new one. Never continue degraded, and never let a compaction eat
unpersisted findings.

When preparing a handoff, capture consequential near misses caught by chance: what
almost went wrong, what caught it, and which gap remains. Use the existing work record
and link it from the handoff; no separate incident log or entry is needed when there
is nothing material to preserve. A near miss does not automatically justify a new
standing rule; follow rules/core.md §Operator correction.

## The bible (repository .agents/rules.md)

Reading order: rules/core.md §Session start. Append settled repo-wide decisions to the bible
(timing: rules/core.md prime rule 11) so they're never re-litigated: chosen models, rejected
alternatives (with the evidence), credential-provider locations, owned defaults,
environment facts that were forgotten twice.

## Filing

Destinations for findings (rules/core.md prime rule 11):

- experiments/results → the work item's record and the campaign ledger
- audits/reviews → dated `docs/reports/YYYY-MM-DD-topic.md`
- operational knowledge → RUNBOOK.md; architecture → docs system map + deep dives
- open follow-ups, deferrals, and plan steps → work items in the owning repository
  (rules/delivery.md §Work tracking & continuity); a report, doc, or plan links them but never
  stands in for them

Paths for runs, reports, ledgers, debug evidence, and scratch: `STRUCTURE.md`.

- Follow rules/core.md prime rule 11 for decision and finding timing and destinations.
- Cross-check cleanup or supersession against the active work record and newer docs/code.
- Record old-to-new mappings and verification evidence in the work item.

## Authorized, bounded, and durable external runs

Scope and authorization: rules/delivery.md §Verification. Before launch, record the envelope that
authorizes the run (rules/outcome.md §Resource envelopes) in the active work record: approved
agents/providers, concurrency, round limits, any configured cost/token/runtime ceiling (off
while testing), and stop condition. Report the run's start, failure and finish to the
operator as rules/delivery.md §Verification requires.

Before the first substantive call of any paid, long-running, or non-reproducible external
agent/model/tool run:

1. Choose a durable path for stdout/stderr or the native session transcript. Apply
   rules/core.md §Security: redact at capture and restrict any necessary sensitive raw records.
2. Enable the tool's persistent/resumable session mode where available.
3. Record the session/process ID, exact model/tool, start time, any configured ceiling, and
   output path in the active work record.
4. Confirm that output is actually being appended or that the native session can be
   resumed before allowing major spend or runtime to accumulate.

At meaningful milestones, record actual spend, tokens, runtime, and rounds against the
remaining envelope (what counts as a new round: rules/outcome.md §Resource envelopes).

During a quiet or apparently stalled run, distinguish UI/wrapper silence from process
failure: inspect the process, terminal/session state, transcript growth, checkpoints, and
provider status. A timeout is an observation, not authorization to kill the run.

Before interrupt/restart/replacement, persist the latest recoverable output and decide
whether the evidence proves no progress. For a materially paid or unique run, apply the
approval requirement and exceptions in rules/delivery.md §Verification. An urgent safety stop
takes precedence; capture only what can be captured without delaying it. If durable
capture cannot be established at launch, ask the operator to accept the loss risk or use
a cheaper/reproducible probe instead.

- Apply the routine-command exemption in rules/delivery.md §Verification.

## Resuming

"continue #NNN" (or "continue <branch>", or "continue" with a legacy ledger in an
un-migrated repo) is a complete instruction. Resume means: read the work item's latest
claim record, the Decisions of every handoff since it, and its latest handoff record on
its work branch; its host state when reachable; the bible; and its campaign ledger; verify claimed state against reality (is that run still live? did the commit
land?), then continue the Pending list — without re-testing what the ledger settles
absent new evidence and without re-asking answered questions. After a crash: commit
recoverable work first (when commits are authorized), then resume.
