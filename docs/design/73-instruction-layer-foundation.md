# House Rules index rename and pointer files

Status: pointer-only design; operator direction recorded on 2026-10-07; implementation verification pending

Issue: [#73](https://github.com/symbiotic-sh/house-rules/issues/73)

## 1. Result

The shared index moves from `<HOUSE_RULES_ROOT>/AGENTS.md` to [<HOUSE_RULES_ROOT>/INDEX.md](../../INDEX.md).
Its content stays unchanged except self-references to its filename.
House Rules' own [<HOUSE_RULES_ROOT>/AGENTS.md](../../AGENTS.md) becomes a pointer to the index.
It points to `<HOUSE_RULES_ROOT>/.agents/rules.md` only if that file exists; this change does not create it.
Global and managed-repository instruction files keep their existing wording and change only the shared index filename.

Every rule file stays always loaded exactly as before.
No rule text moves, and [<HOUSE_RULES_ROOT>/rules/core.md](../../rules/core.md) stays unchanged.
The rename does not change which files load or when.
At session start and after every compaction or reset, agents still read the index and every always-loaded file in full.
Decision 6 withdraws the earlier foundation and recovery changes.

## 2. Terms

`<HOUSE_RULES_ROOT>` means the permanent House Rules checkout.
`<REPOSITORY_ROOT>` means the managed repository's root.
`<fixture root>` means the synthetic checkout used by the sync tests.
Paths name complete locations within those roots.
Links to House Rules files resolve relative to this document.

- **House Rules block:** the managed pointer between `<!-- house-rules:begin -->` and `<!-- house-rules:end -->`.
  [<HOUSE_RULES_ROOT>/INSTALL-AGENTS.md §3](../../INSTALL-AGENTS.md) defines the block.
- **Index:** [<HOUSE_RULES_ROOT>/INDEX.md](../../INDEX.md), which owns shared loading instructions.
- **Always-loaded files:** every rule file under the index's “Always load” heading.
- **Pointer:** a tool or repository instruction file that tells the agent to read the shared index.

## 3. Current behavior

The implementation baseline is [ba1e5b0](https://github.com/symbiotic-sh/house-rules/tree/ba1e5b09199df53a32bc882ec4a8793cdd6b240d).

- The baseline index at `<HOUSE_RULES_ROOT>/AGENTS.md` requires seven rule files in full at session start and after every reset or compaction:
  [baseline index](https://github.com/symbiotic-sh/house-rules/blob/ba1e5b09199df53a32bc882ec4a8793cdd6b240d/AGENTS.md).
  They are `<HOUSE_RULES_ROOT>/rules/core.md`, `<HOUSE_RULES_ROOT>/rules/outcome.md`, `<HOUSE_RULES_ROOT>/rules/delivery.md`,
  `<HOUSE_RULES_ROOT>/rules/writing.md`, `<HOUSE_RULES_ROOT>/rules/git.md`, `<HOUSE_RULES_ROOT>/rules/priority-labels.md`
  and `<HOUSE_RULES_ROOT>/rules/session-writing.md`.
- [<HOUSE_RULES_ROOT>/scripts/sync.py](../../scripts/sync.py) derives the installed block from
  [<HOUSE_RULES_ROOT>/INSTALL-AGENTS.md](../../INSTALL-AGENTS.md), reports drift, and reads the index's always-load list.
  It does not install or repair instruction blocks.
- The installer already knows Claude Code, Codex, Codex override files, Kimi Code and configured extra homes.
  This change preserves those destinations.

## 4. Design

### 4.1 Overview

The House Rules block stays a permanent pointer.
The installer does not copy rule text into tool instructions.
The only runtime change is the index filename and the pointer-only House Rules loader.
All current loading and compaction rules remain in effect.

### 4.5 Index rename and pointer files

Move the index to [<HOUSE_RULES_ROOT>/INDEX.md](../../INDEX.md).
Keep its purpose, precedence, always-load list, skill triggers and relative links unchanged.
Only self-references follow the filename rename.

Global pointers keep the existing block, changing only the index filename:

```markdown
<!-- house-rules:begin -->
# Shared operating foundation (House Rules)

At session start and after every context compaction or reset, read `<HOUSE_RULES_ROOT>/INDEX.md`.
It is the index for collaboration, verification, autonomy, and durable
execution rules. Load the rule files and Skills that its conditions select.
Repository-local rules supply project details and win over shared preferences; all work remains subject to the host's instruction hierarchy
and access controls.

Load only the House Rules Skills relevant to the task. Use
`<HOUSE_RULES_ROOT>/STRUCTURE.md` when deciding artifact paths and naming. Keep
model, permission, MCP, plugin, and hook configuration in the native tool
settings.
<!-- house-rules:end -->
```

The installer resolves `<HOUSE_RULES_ROOT>` to the permanent source path.
House Rules' own pointer uses the same text with repository-relative `INDEX.md` and `STRUCTURE.md` paths.
Managed repositories keep the existing three-line loader:

```markdown
# AGENTS.md
This repository is managed by [House Rules](<House Rules URL>). Read House Rules `INDEX.md` first and follow it.
This repository's own rules are in [.agents/rules.md](.agents/rules.md).
```

A managed repository without its own rules omits the third line.
Do not create a local rules file for this rename.
Committed repository pointers contain no machine paths.

[<HOUSE_RULES_ROOT>/INSTALL-AGENTS.md §3](../../INSTALL-AGENTS.md) and
[<HOUSE_RULES_ROOT>/STRUCTURE.md §Managed repository loader](../../STRUCTURE.md#managed-repository-loader) keep their existing wording with the renamed index.
[<HOUSE_RULES_ROOT>/scripts/sync.py](../../scripts/sync.py) reads `<HOUSE_RULES_ROOT>/INDEX.md`.
It continues to derive the always-load list from that file.

### 4.6 Per-tool delivery

The installer writes the §4.5 shape to every tool home it already supports.
It preserves content outside each managed block.
Sync reports a block pointing to `<HOUSE_RULES_ROOT>/AGENTS.md` as stale.
Later rule edits need no pointer reinstall.

- **Claude Code:** `$CLAUDE_CONFIG_DIR/CLAUDE.md`, defaulting to `~/.claude/CLAUDE.md`.
- **Codex:** `$CODEX_HOME/AGENTS.md`, or `$CODEX_HOME/AGENTS.override.md` when the override exists.
  Every configured Codex home receives the same shape.
- **Kimi Code:** `$KIMI_CODE_HOME/AGENTS.md`.
- **Other products:** existing adapters point to the same shared index.
  Adding Antigravity support belongs to [issue #78](https://github.com/symbiotic-sh/house-rules/issues/78).

Managed repositories' `<REPOSITORY_ROOT>/AGENTS.md` files keep the three-line loader in §4.5.
This implementation does not run the installer against real homes or repositories.

### 4.7 Separate Claude import work

The earlier conditional Claude-import decision is outside this pointer-only change.
This implementation adds no imports, skip-read exception or tool-specific recovery behavior.
The earlier import probe is not part of this design's canary.

### 4.8 References and tests

Update every current reference that means the shared index from AGENTS.md to INDEX.md, preserving the surrounding wording.
References to repository or global pointers keep the corresponding full instruction-file path.
Historical citations name their pinned commit and retain that commit's filename.

- [<HOUSE_RULES_ROOT>/skills/pr-ready/scripts/test_prompt.py](../../skills/pr-ready/scripts/test_prompt.py) reads the renamed index.
  Its existing pins continue to verify the unchanged purpose, precedence, rule inventory, skill triggers and reset-loading sentence.
- [<HOUSE_RULES_ROOT>/scripts/test_sync.py](../../scripts/test_sync.py) uses `<fixture root>/INDEX.md` and the unchanged seven-rule inventory.
  Tests cover stale old index pointers, the renamed index without an old-index fallback, and missing always-loaded files.
- Tests pin the existing global block wording, House Rules' portable pointer, and the managed-repository three-line loader.
  Tests also pin the unchanged sentences around the index rename in PREFERENCES.md and prompts/util/transcript-gaps.md.

## 5. Rejected alternatives

- **Smaller foundation (§4.1–§4.3):** withdrawn by the 2026-10-07 direction in Decision 6; all current rules stay always loaded.
- **Rule moves (§4.2–§4.4):** withdrawn by Decision 6; every rule keeps its current home and text.
- **Trigger-loading outcome and delivery (§4.3–§4.4):** withdrawn by Decision 6; the current always-load list stays unchanged.
- **Bounded re-read and exactly-once recovery (§4.3, former §7):** withdrawn by Decision 6; agents still re-read the index and every always-loaded file in full after each compaction or reset.
- **Size sections and measurement tests (former §3, §6–§7):** withdrawn by Decision 6 and the 2026-10-06 direction in [<HOUSE_RULES_ROOT>/CHANGELOG-RULES.md](../../CHANGELOG-RULES.md); no size targets apply.
- **Inline rule copies:** rejected because copies create another rule owner.
- **Keep the index in `<HOUSE_RULES_ROOT>/AGENTS.md`:** rejected by the recorded index-rename decision.

## 6. Compatibility

Existing pointers to `<HOUSE_RULES_ROOT>/AGENTS.md` encounter the new pointer there.
They can still reach the shared index; sync reports their installed blocks as stale.
The index rename adds no store, cache, projection, queue or migration.
The local-rule file remains optional and is not created by this change.

## 7. Verification

### Text tests

Run the existing sync and prompt tests with the renamed index.
Run all declared workflow checks.
Do not install pointers into real tool homes.

Before the implementation commit, run the dispatcher's one-time coverage gate:

```sh
python3 <COVERAGE_SCRIPT> <HOUSE_RULES_ROOT> ba1e5b0 <worktree>
```

Every printed rule line must differ from its baseline text only by the index rename.
Report any other line as a failure.
This one-time check adds no repository script or stored report.

### Pointer canary

A session reads `<HOUSE_RULES_ROOT>/INDEX.md` through the new pointer and loads every always-loaded file in full.
The canary checks only pointer resolution and the unchanged always-load inventory.
Tool event logs provide the evidence.
It introduces no rule triggers, read-count limit, forced compaction loop or import probe.
Real-home installation and external session runs remain with the lead.

## 8. Rollout and pins

One implementation change contains the index rename, pointers, reference sweep, tests and this design update.
The lead owns installation and external writes.
After installation, new sessions follow the pointers to the shared index.
Rule changes still come from the live House Rules checkout.
The rename does not pin normal session rules to a Git commit.

## 9. Interfaces with the other designs

[Design #74](https://github.com/symbiotic-sh/house-rules/issues/74) owns shared-rule and worker-pack changes.
[Design #75](https://github.com/symbiotic-sh/house-rules/issues/75) owns specialist processes and isolation.
[Design #76](https://github.com/symbiotic-sh/house-rules/issues/76) owns review entry and writing triggers.
[Design #77](https://github.com/symbiotic-sh/house-rules/issues/77) owns prompt assembly from pinned Git objects.
None of those changes belongs to this implementation.

## 10. Decisions

Earlier choices remain recorded below with their disposition under the latest direction.

1. `DECISION` (2026-10-07) Run this design's canary alone, using up to 15 short sessions on existing subscriptions; the remaining canary covers only the pointer change (§7).
2. `DECISION` (2026-10-07) Keep deferred-work tracking and the external-write limit always loaded; their current rule homes stay unchanged.
3. `DECISION` (2026-10-07) Adopt Claude's import separately only after proving live linking, survival across compaction and no hand regeneration; outside this implementation (§4.7).
4. `DECISION` (2026-10-07; pointer wording superseded by Decision 7) Rename the shared index to `<HOUSE_RULES_ROOT>/INDEX.md` and use the same global and repository pointer shape with installation-specific paths.
   House Rules' own `<HOUSE_RULES_ROOT>/AGENTS.md` points to the index and to `<HOUSE_RULES_ROOT>/.agents/rules.md` only if that file exists.
   File references name complete paths.
5. The earlier lead decision requiring exactly-once rule loading is withdrawn by the later operator direction in Decision 6.
6. `DECISION` (operator direction, 2026-10-07): “given the context is 1 million this is retarded we are spending a LOT of time for this and risking breakage”.
   Implement only the index rename and pointer shape.
   Every rule file stays always loaded exactly as today.
   Do not move rule text, shrink `<HOUSE_RULES_ROOT>/rules/core.md`, change loading triggers or change the compaction rule.
   Agents still re-read the index and every always-loaded file in full after every compaction or reset.
   No size target, measurement test or budget applies, following the 2026-10-06 direction in [<HOUSE_RULES_ROOT>/CHANGELOG-RULES.md](../../CHANGELOG-RULES.md).

7. `DECISION` (lead direction, 2026-10-07) Keep the old pointer wording verbatim and change only the index filename.
   Global blocks retain every sentence in the installer template.
   Managed repositories retain the three-line loader in STRUCTURE.md; House Rules' own pointer uses portable relative paths.
   PREFERENCES.md and prompts/util/transcript-gaps.md replace only AGENTS.md with INDEX.md.
   This supersedes Decision 4's common pointer shape and complete-path requirement where they conflict with this wording.

## 11. Open points

No operator design choice remains open for this implementation.
The lead collects the pointer-canary event log before rollout.
