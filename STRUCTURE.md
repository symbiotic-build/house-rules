# STRUCTURE — Canonical Paths & Naming (all repos)

One reference for where every artifact lives and what it's called. Lifecycle rules: skill
`design-flow`. Issues, branches, handoffs, and the board: skill `work-tracking`.

## Layout

Follow [rules/delivery.md §Layout](rules/delivery.md#layout) for layout invariants.

```
repo/
├── AGENTS.md                      # managed-repository loader; unmanaged repos keep normal instructions
├── .agents/rules.md               # the bible: repository rules, settled decisions, execution choices
├── CONTEXT.md                     # project purpose, acceptance, stack, overrides with reasons
├── CLAUDE.md                      # pointer to AGENTS.md; preserve tool-manager-owned content
├── .claude/rules/<name>.md        # optional, Claude-only: path-scoped rules (frontmatter paths:)
├── docs/
│   ├── DOCUMENTS.json             # shared document manifest and tracked Markdown inventory
│   ├── ENTITIES.json              # shared entity identities, names, scope and home locations
│   ├── generated/                 # rebuildable Markdown navigation, never canonical facts
│   ├── SYSTEM-MAP.md              # ONE high-level system map (skill design-canon §Docs)
│   ├── design/                    # INTENT — approved future design
│   │   └── <issue>-feature-name.md #  owning issue number; statuses: see below
│   ├── architecture/              # SHIPPED behavior
│   │   └── feature-name.md        #   no issue number — durable name
│   ├── specs/                     # product/subsystem specs (where repo uses spec layout)
│   │   └── {subsystem}/{subsystem}-spec.md
│   └── reports/
│       └── YYYY-MM-DD-topic.md    # dated (audits, reviews; a multi-file set is a
│                                  #   YYYY-MM-DD-topic/ dir); immutable once released —
│                                  #   corrections go in a new dated report or a labeled erratum
├── prototypes/
│   ├── <issue>-feature-name/
│   │   ├── lofi/                  # md + mermaid flows, single-file html sketches
│   │   └── hifi/                  # project UI stack (PREFERENCES.md default) + mock data
│   └── spikes/
│       └── YYYY-MM-DD-question/   # throwaway code answering ONE question
│           └── SPIKE.md           #   question / method / verdict / date — kill-or-promote
├── runs/                          # benchmark/eval artifacts (gitignored unless promoted)
│   └── {system}/{benchmark}/{limit}/{run_name}/  # neutral condition names, run-params.json
├── records/                       # curated promoted runs (same shape as runs/)
├── skills/<name>/SKILL.md         # repo-local skills; check before writing shell pipelines
├── scripts/                       # ci guards, smoke gates, build/test helpers
├── RUNBOOK.md                     # operational knowledge: run, recover, rotate — not architecture
├── .debug-session/                # gitignored: logs, screenshots, debug reports
└── .tmp/                          # gitignored: scratch; lane targets only without a worktree
```

## Specification and design-document artifacts

Use the shared metadata paths shown above for both single-file and multi-file documents.
Keep authored chapters in their normal specification or design locations. Generated
navigation belongs under `docs/generated/` or in one declared region of an existing
document, including the repository's single system map. A single-file design uses its
existing file's navigation region; it needs no private directory or companion glossary.

The complete registry and selected agent context are transient tool outputs, not maintained
repository stores. Follow [specifications rules](rules/specifications.md) for authority and
the [exact source formats](docs/specs/spec-system/source-formats.md#source-format) for declarations.
The reusable outlines live in [spec-writing templates](skills/spec-writing/templates/):
`specification.md` and `design-document.md`.

<a id="managed-repository-loader"></a>
## Managed repository loader

A managed repository uses exactly this `AGENTS.md`:

```markdown
# AGENTS.md
This repository is managed by [House Rules](<House Rules URL>). Read House Rules `INDEX.md` first and follow it.
This repository's own rules are in [.agents/rules.md](.agents/rules.md).
```

Tool files (`CLAUDE.md`, `GEMINI.md`, `.cursorrules`,
`.github/copilot-instructions.md`) contain only a pointer to `AGENTS.md`, apart from
content a tool manager writes and owns.
A managed repository without its own rules omits the third line.
An unmanaged repository keeps a normal `AGENTS.md`; House Rules does not govern it.

## Naming rules

| Thing | Rule | Example |
|---|---|---|
| Design doc | `docs/design/<issue>-kebab.md` — carries the owning issue number | `docs/design/42-rerank-stage2.md` |
| Architecture doc | `docs/architecture/kebab.md` — durable, no id | `docs/architecture/rerank-pipeline.md` |
| Report | `docs/reports/YYYY-MM-DD-topic.md` | `2026-07-06-knob-audit.md` |
| Branch | `<issue>-<slug>`, or `<slug>` until the issue exists; holds the item's Git record (skill `work-tracking`) | `42-rerank-stage2` |
| Run name | neutral benchmark condition, never debugging history | `candidate-answer-thinking` |
| Spike | `prototypes/spikes/YYYY-MM-DD-question/` | `2026-07-06-fts-vs-vector-speed/` |
| Legacy ledger | `tasks/`, `NEXT.md`, or `HANDOVER-YYYY-MM-DD.md` — un-migrated repos only (skill `work-tracking` §Migration) | `HANDOVER-2026-07-06.md` |
| Commit | `type(scope): description` | `feat(recall): stage2 rerank` |
| Crates | `<product>-<domain>` | `acme-intake` |

General: kebab-case for directories and slugs; UPPERCASE for fixed canonical file names
(`AGENTS.md`, `SPIKE.md`, `RUNBOOK.md`); English only; names say what things do (no
defaults in names; disambiguate lookalikes, `captured_at` ≠ `ingested_at` ≠
`observed_at`); rename confusing names the moment they're noticed.

## Temp storage — three classes, one rule

Work products never live in system `/tmp`: it's outside git, outside backups, outside the project's data
boundary, shared across projects, and the OS purges it (reboot + periodic cleanup) — which
silently violates "checkpoint everything". In-repo gitignored dirs keep artifacts
inspectable, deliberately prunable, and inside the project's backup boundary.

| Class | Where | Lifecycle |
|---|---|---|
| Evidence — screenshots, debug logs, run reports you will open | `.debug-session/` | retain per the project's retention policy (none recorded: rules/core.md §Security); issue closure alone does not authorize deletion |
| Machine scratch — build targets, caches, never opened by a human | `.tmp/` | remove only under rules/core.md §Security ownership, reproducibility, and active-process checks |
| Tool-provided session scratchpads (agent-harness temp dirs) | wherever the tool puts them | ephemeral by definition — copy anything worth keeping into the repo before session end; never host worktrees or lane state |
| Agent worktrees and lane state — task worktrees, lane scripts, prompts, review results, logs | durable workspace paths: `<workspace>/worktrees/<repo>/<branch>` and a lane folder beside it | never in `/tmp` or a session scratchpad; a worktree is removed when its PR merges |

The two-dir split is a retention policy, not taxonomy — evidence and scratch have different
deletion rules, so they get different homes. Exception: a shared out-of-repo cache
(e.g. `~/.cache/<tool>`) is fine for rebuildable artifacts that are expensive to recreate
and safe to lose.

## Frontmatter statuses

- Design doc: `draft → approved → implemented | superseded` (implemented = shipped
  sections migrated to architecture/spec, doc shrinks to a pointer that keeps its
  `status:` frontmatter (keep the issue's design link) or is deleted (remove the link);
  superseded = replaced by a newer design)
- Spike: `open → promoted | killed` (in SPIKE.md verdict; review and cleanup: skill
  `design-flow` §Spikes)
