---
name: operator-protocol
description: Interpret operator instructions, report progress, and handle decisions within the chosen collaboration mode. Use when answering a status request, interpreting steering (yes, continue, stop, a numbered reply), reporting progress on long-running work, or escalating a decision.
license: MIT
---

# Operator Protocol

Follow skills/operator-writing/SKILL.md for response style. Follow rules/core.md,
rules/outcome.md, and rules/delivery.md for authority. Infer the operator's needs
from the current task and recorded preferences; do not assume their device, team size,
expertise, tone, or visual style. Technology and presentation choices belong to
`PREFERENCES.md` and the project, not this communication procedure.

## Interpret steering in context

- A status request asks for current evidence and blockers.
- An affirmative response selects the recommendation or action actually under discussion.
- A numbered or lettered response selects the corresponding offered option.
- A request to continue resumes pending authorized work; it does not reactivate deferred scope.
- A stop or wait instruction halts the affected work (rules/core.md §Operator correction);
  preserve state.
- A request for more depth expands effort only inside the agreed scope and resource limits.
- Questions and reported symptoms: rules/core.md prime rule 2.

## Progress

Report at meaningful intervals with real counters, artifact locations, and actual cost
when relevant (content: [rules/writing.md §Communication rules](../../rules/writing.md#communication-rules)). For paid or
non-reproducible work, include the durable record and resumable session ID (rules/delivery.md
§Verification).

Name the current plan step, the question it resolves and what remains before it closes.
Before a meaningful command group, state its purpose briefly; omit narration for trivial
commands and unchanged status. Separate completed results, hypotheses and pending verification.
Derive progress displays from existing work records; do not create another writable tracker.
When repairs recur, use the campaign count under
[rules/outcome.md §Three-occurrence reassessment](../../rules/outcome.md#three-occurrence-reassessment),
including attempts by earlier workers.

## Decisions

Use the collaboration mode recorded under rules/core.md §Autonomy. A routine implementation
choice inside that agreement is different from a change rules/core.md §Autonomy says
requires a decision. State that distinction when escalating a decision.

For a decision needing input, explain its consequence, offer the viable options and a
recommendation, and ask once; format: skill `decision-brief`. Batch independent decisions when that makes answering easier;
continue work that does not depend on the answers; silence is not approval. Do not re-ask
settled questions.

Changing a measured experiment setting follows the recorded experiment plan. An improved
score alone never authorizes changing a shipped product default or invalidating baseline
comparability; both need a recorded decision (rules/core.md §Autonomy).

- Follow rules/core.md §Protected operator assets for exact-action confirmation.
- When no collaboration mode exists, ask once whether to proceed autonomously or pause at consequential decision forks.
- Record the collaboration mode in the bible, or the work item for an item-scoped choice.

## Collaboration

Deliver the requested behavior before proposing optional changes. Critique a requirement
when evidence shows a problem, with a concrete alternative and trade-off, then follow the
ruling. Correct errors plainly and persist the relevant task-local decision. Standing
policy changes follow rules/core.md §Operator correction.

## Find transcript instruction gaps

Use this optional periodic step to find lasting human instructions that never reached
House Rules or a local decisions file. Extraction uses only Python 3's standard library,
with no model or network calls. Comparison uses the whole
[compare prompt](../../prompts/util/transcript-gaps.md) in one locally configured,
approved model run. Findings are proposals for the operator, not automatic rule edits.

Run from a pinned House Rules checkout, optionally sourcing trusted local shell settings:

```sh
set -eu
if [ -f custom/transcript-gaps.env ]; then
    set -a
    . ./custom/transcript-gaps.env
    set +a
fi
python3 skills/operator-protocol/scripts/transcript_gaps.py
```

`custom/` is ignored by Git. Keep real source and decisions paths there or in the
environment; never commit them. Settings are exported shell variables:

| Variable | Meaning and default |
|---|---|
| `CODEX_HOME` | Primary Codex home; defaults to `~/.codex`. Reads `sessions/**/*.jsonl`. |
| `KIMI_CODE_HOME` | Kimi home; defaults to `~/.kimi-code`. Reads `user-history/*.jsonl`. |
| `TRANSCRIPT_GAPS_CODEX_HOMES` | Extra Codex homes, colon-separated on macOS/Linux; default empty. Reads each home's `sessions` tree in addition to the primary. |
| `TRANSCRIPT_GAPS_CLAUDE_ROOTS` | Extra Claude project roots, colon-separated; default empty. Each has the same `*/*.jsonl` layout as `~/.claude/projects`, which is always read. |
| `XDG_STATE_HOME` | Base user state directory; defaults to `~/.local/state`. |
| `TRANSCRIPT_GAPS_STATE_DIR` | Marker and JSONL directory; defaults to `$XDG_STATE_HOME/house-rules/transcript-gaps`. Must be outside all repositories. |
| `TRANSCRIPT_GAPS_DECISIONS_FILE` | Optional decisions file for the compare caller; default unset. Extraction does not read it. |

Extraction prints only the new batch's absolute path. No new human text means no stdout;
do not compare an old batch in that case. It reads all history on the first run, then
uses byte offsets in `last-run.json`; offsets also include excluded entries. Batches are
retained as `messages-<digest>.jsonl`, containing `tool`, `session`, `timestamp`, `text`.
Run one extractor at a time. File order is tool, configured root, sorted directory and
filename, then transcript line order; dates do not control incremental extraction.
Sources must be append-only. Truncation, malformed JSON and incomplete lines fail visibly
without advancing the marker. Newly created state directories are mode 0700; files are
0600. No files are written into the checkout, and no content is sent by the extractor.

Claude requires `origin.kind: human` and excludes meta entries, sidechains, peers and
notifications. Codex uses user `response_item` messages, not their duplicate event log;
it excludes exec/subagent sessions and injected rule/context/notification blocks.
Whole-part filtering also drops human text starting with an opening tag after leading whitespace.
Kimi excludes slash commands. Its history stores only text: a missing timestamp stays
null and `session` is the history-file stem, not a conversation ID. The compare prompt
reports that missing provenance rather than guessing.

Native cost is directory discovery plus sequential JSONL reads: new bytes and the Codex
metadata line after the first run. The required offset marker avoids rereading old
messages; JSONL batches carry the comparison input. There is no database, index or cache.

Weekly examples: [launchd plist](references/transcript-gaps.plist),
[systemd user timer](references/transcript-gaps.timer) and its
[service](references/transcript-gaps.service). These are documentation, not installed
schedules. Replace every `/placeholder/...` path in local copies. The local compare
runner receives batch, whole prompt, optional decisions path and rules checkout as four
arguments; choose its native model invocation locally, and save reports only in the
state directory. Configure scheduler failure reporting locally. A failed comparison
leaves its batch available for a manual rerun. Keep installed schedules untracked.
