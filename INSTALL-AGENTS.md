# Install House Rules with an agent

This is the authoritative installation procedure. House Rules intentionally has no
universal installer script: agent products use different instruction and Skill
locations, those locations evolve, and native Windows may require copies where
Unix-like systems can use symlinks.

The desired result is one permanent House Rules source, preserved operator settings,
portable House Rules Skills, and a machine-local index of optional capabilities.
The source includes PREFERENCES.md: its project defaults are active immediately, with
explicit user and repository overrides. Install project-bootstrap with the other House Rules
skills; do not require users to opt into the default profile.
External products remain responsible for installing, updating, and removing
their own skills, clients, MCP servers, credentials, and other runtime state.

## Prompt for the destination agent

Replace `<HOUSE_RULES_SOURCE>` with the permanent path of your House Rules clone, then
give the destination agent this prompt:

> Install House Rules globally from `<HOUSE_RULES_SOURCE>`. Read its
> INSTALL-AGENTS.md completely and follow it. Keep House Rules in a permanent,
> user-owned location; preserve existing instructions and native settings;
> discover this machine's operating system, agent products, configuration
> homes, and supported Skill locations from the installed versions and current
> vendor documentation. Preview the exact files and links or copies you will
> create, install only for the products present or explicitly requested, and
> verify discovery in fresh sessions. Create the gitignored custom/INDEX.md in House Rules
> for machine-specific capabilities. Let self-installing products own their
> integrations and record only pointers to them. Never copy credentials,
> enrollment identity, caches, or source-machine paths.

## 1. Establish the source and platform

1. Clone House Rules into a permanent user-owned directory (README). Do not overlay an
   existing House Rules directory until local changes have been compared.
2. Identify whether each agent runs natively on macOS, Linux, Windows, or inside
   WSL. Configure the environment that actually runs the agent. A WSL path does
   not configure a Windows-native desktop application.
3. Inspect current vendor documentation and the running product's configuration
   when they disagree. Do not rely on a path remembered from another computer.
4. Keep model selection, permissions, hooks, plugins, MCP configuration,
   credentials, and login state in each product's native configuration.

Current baseline locations are:

| Product | Global instructions | User Skills |
|---|---|---|
| Claude Code | `$CLAUDE_CONFIG_DIR/CLAUDE.md`, default `~/.claude/CLAUDE.md` | `$CLAUDE_CONFIG_DIR/skills/`, default `~/.claude/skills/` |
| Codex | `$CODEX_HOME/AGENTS.md`, default `~/.codex/AGENTS.md` | `~/.agents/skills/` |
| Kimi Code | `$KIMI_CODE_HOME/AGENTS.md`, default `~/.kimi-code/AGENTS.md` | `~/.agents/skills/` (Kimi also scans `$KIMI_CODE_HOME/skills/`; do not install there) |

Verified 2026-09-28 with Claude Code 2.1, Codex CLI 0.153 and Kimi Code 0.41. `~` means
the real home directory of the operating-system user running the agent. Use native
Windows paths for Windows-native agents. Recheck these baselines against current vendor
documentation during installation.

The session-context hook (§3 step 10) goes in each product's native hook file:

| Product | Hook file | Hook output reaches the model |
|---|---|---|
| Claude Code | `$CLAUDE_CONFIG_DIR/settings.json` | Yes, up to 10 000 characters per hook |
| Codex | `$CODEX_HOME/hooks.json` | Yes, after the operator trusts the hook in `/hooks` |
| Kimi Code | None | No: it runs `SessionStart` hooks but discards their output |

Verified 2026-10-19 with Claude Code 2.1.291, Codex CLI 0.159 and Kimi Code 2.1.1. Without
the hook, a session holds only the managed block's instruction to read the rules, and a
session can skip that instruction.

A product may run with several configuration homes, for example Codex accounts launched
with different `CODEX_HOME` folders. Find each one: ask the operator and check launchers,
shell aliases and wrapper apps that set the variable. A folder is a Codex home only if it
contains `config.toml` or `auth.json`. Every home gets its own managed block, override
check and receipt. `~/.agents/skills/` is shared by all Codex homes and Kimi: install it
once and remove it only when no configured product still uses House Rules.

## 2. Produce a no-write plan

Before changing anything, report:

- the permanent House Rules source path;
- selected agent products, every configuration home, and their resolved instruction and
  Skill locations;
- every House Rules Skill found at `skills/<name>/SKILL.md`;
- whether each destination will use a directory symlink or a checked copy;
- instruction files that will change and their backup destinations;
- hook files that will change (§3 step 10) and their backup destinations;
- stale entries to remove (§3 steps 5 and 8; §5 helper links), name conflicts, malformed existing blocks,
  or policy that disables instructions or Skills;
- external capabilities already installed and the command or owner responsible
  for each one.

Prefer directory symlinks on platforms and products that support them. Use a
copy when symlinks are unavailable or inappropriate; native Windows needs Developer Mode
or elevation for symlinks. A copied Skill must retain its House Rules source path and
source revision in the installation report so updates do not silently drift.

Never overwrite an unrelated file, directory, or symlink merely because its
name matches a House Rules Skill. A link is owned by House Rules when its target as
written, even if that target no longer exists, is `<root>/skills/<same name>` for the
current source root or a previous root recorded in a receipt. A copy is owned only when
it matches a receipt. Reuse or replace only owned entries; report any other same-name
entry as a conflict.

<a id="install-house-rules-instructions-and-skills"></a>
## 3. Install House Rules instructions and Skills

For each selected product and configuration home:

1. Back up an existing global instruction file before changing it. If the file is a
   symlink, edit its resolved target; never replace the link itself.
2. Add or replace exactly one block delimited by:

   ```text
   <!-- house-rules:begin -->
   <!-- house-rules:end -->
   ```

3. Inside that block, instruct the agent to read the permanent House Rules
   `INDEX.md` at session start and after every context compaction or reset, load its
   required rule files and only relevant House Rules Skills, use `STRUCTURE.md` for
   artifact placement, and keep native product configuration
   outside House Rules. Use resolved absolute paths from this computer. Install this
   exact adapter text, replacing `<HOUSE_RULES_ROOT>` with the permanent absolute
   path:

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

   Then read `<HOUSE_RULES_ROOT>/custom/INDEX.md` when it exists. It is this
   computer's local index: installed tools and the operator's local policies,
   such as which model and tool run workers. Its policies apply to every session
   on this computer; repository rules still win where they conflict.
   <!-- house-rules:end -->
   ```
4. Older installations use the project's earlier names: `<!-- forge:begin -->` /
   `<!-- forge:end -->` or `<!-- groundwork:begin -->` / `<!-- groundwork:end -->`.
   Back up and migrate that block in place to the House Rules markers; never append a
   second block. Count all three marker families together: a file with more than one
   block, or with incomplete or reversed markers, is a conflict requiring inspection;
   do not guess. Preserve all content outside the managed block.
5. Put the installed block only in each product's global instruction file. Claude Code
   also loads `AGENTS.md` and `CLAUDE.md` from the parent folders of its working directory, so a
   House Rules, Forge or Groundwork block in `~/AGENTS.md`, `~/CLAUDE.md` or a
   workspace parent folder loads a second copy. Search those locations; back up and
   remove such a block instead of migrating it.
   Preserve `<HOUSE_RULES_ROOT>/AGENTS.md`, the canonical repository pointer,
   even when the House Rules checkout is a parent folder.
6. Preserve human-authored existing rules in place unless the operator chooses a merge.
   For consolidation, first copy them to a machine-local
   `custom/external-rules/<tool>.md`, excluding third-party managed blocks. Review the
   proposed text and duplicates, then replace only that agreed original content with
   an explicit instruction to read the external file at session start. Keep tool-specific
   rules separate when their meanings differ. Record ownership and a backup in the receipt.
   This is an ordinary referenced file, not a new native instruction-discovery feature.
   Never move another product's managed block out of the file it updates.
7. Codex loads `$CODEX_HOME/AGENTS.override.md` instead of `AGENTS.md` when it exists.
   If an override file is present in a home, place the block there; otherwise the House
   Rules block is never read. Delete or rename an override only with operator approval
   and a backup.
8. Install each House Rules Skill into `~/.agents/skills/` for Codex and Kimi. Then
   check the other folders those products scan — `$CODEX_HOME/skills/` in every Codex
   home and `$KIMI_CODE_HOME/skills/` — for entries with a House Rules Skill name.
   Codex reads `$CODEX_HOME/skills/` first and keeps the first Skill of each name, so a
   stale entry there hides the new one. Record each owned entry (ownership rule in §2)
   in the receipt, then remove it. Report other same-name entries as conflicts. Never
   touch `$CODEX_HOME/skills/.system/`. Owned entries for Skills House Rules has removed,
   such as `task-protocol`, are stale in every Skill folder: record and remove them the
   same way.
9. Install the same House Rules Skills into Claude Code's native user Skill
   directory. A symlink may point directly to the House Rules source; otherwise copy
   the complete Skill directory.
10. Register the session-context hook in every Claude Code and Codex home (§1 hook table).
    At every new, resumed, cleared and compacted session it prints `INDEX.md`, the rule files
    the index lists under "Always load", the operator-writing Skill and `custom/INDEX.md`.
    Run the installer with a Python 3.9 or later interpreter that agent sessions can run:

    ```sh
    "<PYTHON3>" "<HOUSE_RULES_ROOT>/scripts/sync.py" --install-hooks
    ```

    For each hook file it removes every earlier House Rules entry, adds the current one and
    keeps every other entry and setting. An earlier entry runs `scripts/session_context.py`
    under the current or a previous root, or runs a script a receipt lists under
    `replaced_hooks`, such as an older hand-made context hook. The installer backs up a
    changed file beside it, replaces it atomically, prints each file it writes, and leaves a
    file that already holds the current entry unchanged. The entry runs the installer's
    interpreter by its absolute path and names the root as passed to `--root`, so a stable
    link to a moving checkout stays valid. Claude Code gets one hook per part, because it
    caps each hook's output at 10 000 characters; Codex gets one hook; Kimi Code gets none.
    `scripts/session_context.py hooks <product> <root>` prints the entry without writing it.
    The command is quoted for a POSIX shell: on native Windows, run it in the product's hook
    shell first, and report it as a conflict when it fails. Codex skips a new hook until the
    operator trusts it in `/hooks`; record that as a pending operator action in
    `custom/INDEX.md`. Record each hook file and its backup in the receipt.

    The hook and `scripts/sync.py` report two capacity errors. A section too long for one
    part is split under more headings by the owner of its file: the operator for
    `custom/INDEX.md`, a House Rules change for tracked files. More parts than hooks needs
    a House Rules change that raises `SLOTS` in `scripts/session_context.py`; after it,
    run the installer again.
11. Do not install anything from `custom/` as though House Rules owned it. Follow the
    ownership recorded in `custom/INDEX.md`.

Writes should be staged in the destination directory and atomically renamed
where the host supports it. If a multi-file operation fails, preserve backups,
report the partial state exactly, and either roll it back or finish it before
claiming installation success.

Do not copy the shared base into each repository. Existing repository copies are a
migration case: compare their universal section to its known source revision, preserve
local edits and decisions, and remove only the verified duplicate section after review.
Unknown or conflicting content remains until reconciled. The global source owns shared
rules; repository files own local rules.

## 4. Maintain the machine-local custom index

Create `custom/INDEX.md` under the permanent House Rules directory when it does not
exist. The entire `custom/` directory is gitignored because it describes one
machine's tools, paths, accounts, and verification state. Start from
`CUSTOM-INDEX.example.md`.

Sessions find this index through the managed block (§3 step 3), which tells them to
read it after `INDEX.md`, and through the session-context hook (§3 step 10), which
prints it. Nothing else in the tracked House Rules files points to it, so a machine
without the current block and hook may never load its local policies. When the index is
missing, the hook prints an error line in its place. After changing the block template,
update every installed block (§5 verifies them).

The index's "Local policies" section holds operator rules that apply to this
computer only, because they name local tools, paths or accounts. Example: which
model and wrapper run worker agents. Each entry states the rule in one or two
sentences, the operator's direction date, and where the full record is. Longer
policy text goes in its own file under `custom/`, linked from that section.
Never put credentials in either.

Keep one durable installation receipt per product home in `custom/installations/` (JSON
or a small Markdown table) and list the receipts in `custom/INDEX.md`. Record the source
root and any previous roots, the source revision (`git rev-parse HEAD`), native instruction file, managed block, optional external-rule file,
every link/copy destination, installed content hashes, backup locations, and
filesystem/runtime verification. Do not record secrets. The receipt is
the ownership evidence used for update and removal.

The index records optional Skills, plugins, MCP clients, browsers, and related
capabilities. For each entry record:

- capability name and kind;
- owning product or project;
- canonical installed path or native registry;
- install/update/uninstall authority;
- products that discover it;
- last verification date and result;
- any remaining login or consent requirement, without secrets.

Store a locally authored Skill under `custom/skills/<name>/` only when no
external product owns its lifecycle. Link or copy it into the necessary native
locations and record those projections in the index.

A self-installing product is different: keep its files in its own canonical
location and add only an index pointer. Such a product owns its runtime, any shared
Skill it installs (for example under `~/.agents/skills/`), native client adapters, MCP
registration, credentials, updates, repair, and removal. House Rules must not vendor a
snapshot of it or pin its release state.

Configure review panels (skill `pr-ready`): run
`skills/pr-ready/scripts/review-panel-models.py --init`. It writes
`custom/review-panel.conf` with one model family per installed agent CLI (Codex, Grok,
Kimi), choosing each CLI's recommended model from its local model list; edit tiers or
models there. The panel launcher rechecks on every run and reports newer models in a
configured family; `--list` shows what each CLI offers.

## 5. Verify actual discovery

Filesystem verification:

- every rule file under `rules/` named by the index exists;
- every House Rules Skill destination resolves to the intended source or matches the
  checked source bytes;
- every instruction file contains exactly one House Rules block (counting old `forge:`
  and `groundwork:` markers too) and retains its surrounding operator content;
- every Claude Code and Codex hook file holds exactly the §3 step 10 entry and retains
  its other entries;
- no other scanned Skill folder or parent-folder instruction file holds a stale House
  Rules, Forge or Groundwork entry, or an entry for a removed House Rules Skill;
- no owned link or alias to a removed helper remains;
- no custom or externally managed capability was copied into House Rules ownership;
- `custom/INDEX.md` points to paths that exist and identifies their real owner.

Tools:

- The rules and Skills need no runtime. Only the optional report linter
  (`skills/audit-report-authoring/scripts/lint-report-set.mjs`) needs Node.js 22 or later;
  check for it only when that Skill is used, and do not install it silently.
- Work tracking uses the Git host's CLI (skill `work-tracking`); on GitHub, `gh` with the
  `project` token scope. Record a missing scope as a pending operator action in
  `custom/INDEX.md`.
- Links or aliases to the removed helpers `bin/task` and `bin/house-rules.mjs` are
  obsolete. Identify them from the installation receipt and remove only House Rules-owned
  ones. Do not claim a bare `task` or `house-rules` command is ours without verifying its
  resolution.
- Resolve shared references such as STRUCTURE.md from the permanent House Rules source.

Runtime verification:

Run global-installation discovery verification from a neutral working directory
outside any repository. Check that neither it nor any parent folder contains
instruction files such as `AGENTS.md` or `CLAUDE.md`.

1. Prefer discovery views that make no model call. For Codex, run
   `CODEX_HOME=<home> codex debug prompt-input` for every home: the output must contain
   exactly one `Shared operating foundation (House Rules)` heading, list each House Rules
   Skill once, and contain no Forge or Groundwork text. For Claude Code, check `/memory`
   in a fresh session. Claude Code drops HTML comments from loaded instructions, so check
   the heading rather than the markers. For Codex, check that `/hooks` lists the House
   Rules hook as trusted.
2. Where no such view exists, or the operator asks for it, start a fresh session with a
   read-only prompt, for example: “Identify the loaded House Rules base path and available
   skills, then explain which rules apply to this simple question without creating a
   work item.” These are model runs: start them only when the operator has authorized that
   cost, and treat the model's self-description as supporting evidence. For the
   session-context hook, run Claude Code with `-p --output-format stream-json --verbose`:
   each `hook_response` event holds one part's output. Check that parts 1 to N each
   arrive once, that each starts with its `House Rules part N of M` label, and that the
   `custom/INDEX.md` section is present.
3. If the report linter is in use, run it on a disposable fixture; never create
   verification issues in a real project.
4. Verify each external capability through its owner's supported status or
   doctor command. Do not treat a file's presence as runtime verification.

Report filesystem and runtime verification separately.

## 6. Update and remove

`custom/` holds this machine's index, receipts, backups and any external rules, inside the
source folder. Never use a temporary folder such as a downloads folder or a package-manager
cache as the source.

Use the Python 3.9 or later standard-library sync script from the permanent checkout:

```sh
python3 "<HOUSE_RULES_ROOT>/scripts/sync.py"  # update checkout and report installation drift
```

On a clean default-branch checkout, the script fetches the default branch and runs
`git merge --ff-only --no-overwrite-ignore <fetched-revision>` when there are remote
updates and no local commits ahead of the remote. The merge uses the captured fetched
revision and aborts if incoming tracked paths would overwrite ignored local files.
Dirty, detached, non-default, ahead and diverged checkouts are reported and never updated.
It then checks that every rule file the index lists under "Always load" exists,
then every configured home's managed block, missing or stale Skill links, owned links to
removed Skills, and same-name entries in the other scanned Skill folders. It checks that
every Claude Code and Codex home holds exactly the §3 step 10 hook entry, run by an existing
interpreter, and that the injected rules fit the hook's parts. Git and
filesystem errors reach the caller. Findings collected before a verification error are
retained, and the summary identifies incomplete coverage. Exit codes are 0 for no
findings, 1 for reported drift or conflicts, and 2 for an error.

The scheduled run reports drift; an agent repairs it by following §3, including the
no-write plan in §2 and the verification in §5. A missing or stale hook is repaired with
`--install-hooks` (§3 step 10), which writes hook files and their backups and nothing else.
Without that option the script does not modify instruction files, hook files, Skill entries,
backups, receipts or the custom index. It never starts agent sessions. Runtime discovery remains the separate check in §5.

Only present product homes are selected from the baseline locations in §1, respecting
`CLAUDE_CONFIG_DIR`, `CODEX_HOME` and `KIMI_CODE_HOME` when set; explicit environment
homes must be existing absolute directories. An existing default
Codex directory without `config.toml` or `auth.json` is an error. Extra homes go in
the gitignored `custom/sync.env`, one assignment per home; repeat keys for several
homes. Values are absolute paths parsed with POSIX shell quoting, with `#` comments
allowed. Use single quotes for paths containing backslashes, including Windows drive
and UNC paths; unquoted or double-quoted backslashes can be consumed as escapes.
The script parses these assignments as data; it never executes shell code or expands
variables. Extra homes must exist, and extra Codex homes must meet §1's identification
rule. Without this file, only the baseline homes are checked.

```sh
CODEX_HOME="<EXTRA_CODEX_HOME>"
CODEX_HOME="<ANOTHER_CODEX_HOME>"
CLAUDE_CONFIG_DIR="<EXTRA_CLAUDE_HOME>"
KIMI_CODE_HOME="<EXTRA_KIMI_HOME>"
```

For native Windows homes, preserve backslashes with single quotes:

```sh
CODEX_HOME='C:\Users\example\.codex-extra'
CODEX_HOME='\\server\share\.codex-extra'
```

Verification honors Codex's override file and follows instruction symlinks. The
managed block must equal the exact §3 template. Malformed or multiple blocks and
unrelated same-name entries are reported for inspection. Links are expected only in
§1's designated folders; owned shadowing entries are reported in the other scanned
folders. `$CODEX_HOME/skills/.system/` is excluded.

Link ownership follows §2. The script reads `source_root` and `previous_roots` (absolute
path strings) from machine-readable JSON installation receipts in
`custom/installations/` to recognize links and hooks of earlier source roots, and
`replaced_hooks` (absolute script paths) to recognize older hand-made context hooks, which it
reports as drift and `--install-hooks` removes. It does not read
run history. Other receipt formats and checked copies require manual inspection by
an agent following §3. A copied Skill is reported as a same-name conflict because the
script checks for links; it does not replace it. Symlinked Skills pick up source changes
immediately. No ownership is inferred from a matching name or from following an
unrelated link.

For a daily schedule, adapt one of these examples locally. Replace every placeholder
with an absolute path, XML-escape plist values, and keep the installed schedule and
logs outside tracked files. These examples are documentation, not installed jobs.

macOS launchd, saved locally as `~/Library/LaunchAgents/org.house-rules.sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>org.house-rules.sync</string>
  <key>ProgramArguments</key><array>
    <string>PYTHON3_PATH</string>
    <string>HOUSE_RULES_ROOT/scripts/sync.py</string>
  </array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>9</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>LOG_DIRECTORY/house-rules-sync.log</string>
  <key>StandardErrorPath</key><string>LOG_DIRECTORY/house-rules-sync.err</string>
</dict></plist>
```

For twice daily, replace `StartCalendarInterval`'s dict with an array of two dicts,
using hours 9 and 21 and minute 0. Create the log directory first.

Linux systemd user service, saved locally as
`~/.config/systemd/user/house-rules-sync.service`:

```ini
[Unit]
Description=Update and verify House Rules installations

[Service]
Type=oneshot
ExecStart="<PYTHON3_PATH>" "<HOUSE_RULES_ROOT>/scripts/sync.py"
```

Companion `~/.config/systemd/user/house-rules-sync.timer`:

```ini
[Unit]
Description=Check House Rules daily

[Timer]
OnCalendar=*-*-* 09:00:00
Unit=house-rules-sync.service

[Install]
WantedBy=timers.target
```

For twice daily, add `OnCalendar=*-*-* 21:00:00`. The user journal retains output,
including nonzero results; do not configure the service to treat findings as success.

If the source folder moves, update every managed block and owned link, search instruction
files and repository `AGENTS.md` files for the old root path, and record the old root in
the receipts.

To remove House Rules:

1. Replace each native pointer to `custom/external-rules/<tool>.md` with that file's
   current content, after comparing it with the backup.
2. Delete only owned links (ownership rule in §2, including broken links) and copies
   proven to match a receipt.
3. Remove only the managed House Rules blocks from global instruction files, and only the
   House Rules session-context entry from hook files. Restore a backup only after
   comparing newer operator changes.
4. Copy `custom/` elsewhere if the operator wants its backups and receipts, then delete
   the source folder.

For an external capability listed in `custom/INDEX.md`, use its owner's update
or uninstall workflow. Removing its index entry does not uninstall it, and
deleting its files manually is not a substitute for its lifecycle command.
