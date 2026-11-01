# House Rules

Opinionated foundations for coding agents. Sensible defaults, fully overridable.

House Rules combines global working rules, project preferences, and focused skills.
Install it once; keep project-specific choices in each repository. Explicit user choices
and established project stacks override its defaults.

## What's included

- [INDEX.md](INDEX.md): the index for shared rule files and task-specific skills.
- [PREFERENCES.md](PREFERENCES.md): Rust for durable native/systems work, TypeScript on
  Node for ordinary backends and scripts, static Svelte for browser UIs, and domain-specific
  alternatives where appropriate. Choose only the components needed.
- [STRUCTURE.md](STRUCTURE.md): default paths and naming for projects using House Rules.
- [prompts/](prompts/README.md): role instructions, code-change rules, review lenses and shared pieces.
- `skills/`: project bootstrap, design, implementation, the PR change loop, upstream
  contributions, experiments, diagnosis, reporting, decision briefs, and work tracking. Load only the
  relevant procedures. The audit-report skill includes an optional structural linter that
  needs Node.js 22 or later; nothing else needs Node.

## Install the rules globally

Clone the repository to a permanent user-owned directory:

```sh
git clone https://github.com/symbiotic-build/house-rules.git ~/house-rules
```

Then give your agent the prompt in [INSTALL-AGENTS.md](INSTALL-AGENTS.md). It preserves existing native
instructions, adds a pointer to House Rules, and installs the skills in each product's
supported location. Where the product supports it, a session hook
([scripts/session_context.py](scripts/session_context.py)) also puts the always-load rules
and the machine-local index into every session. Models, permissions,
plugins, and MCP connections stay in native settings; external integrations remain owned
by their products.

To update, run `python3 ~/house-rules/scripts/sync.py`. [scripts/sync.py](scripts/sync.py)
fast-forwards a clean default-branch checkout. It then reports installation drift in each
agent home. It changes no agent home itself.

Some agents keep their own copies of the skills, and their maintenance can edit them.
`python3 ~/house-rules/scripts/sync.py --check-drift` only reads: it reports each copy that
differs from the checkout's revision, with its diff size. [INSTALL-AGENTS.md](INSTALL-AGENTS.md) §6 lists the
folders it scans and the setting that stops a hosting agent from editing its copies.

Do not copy the shared base into every project. In managed repositories, `AGENTS.md`
is the [loader](STRUCTURE.md#managed-repository-loader); `.agents/rules.md` and `CONTEXT.md`
hold local decisions. The `project-bootstrap` skill applies defaults automatically and
asks only about consequential unknowns. An override can be as simple as “This project
uses Python and FastAPI; retain that stack.”

## Track work

By default, work is recorded in Git: claims, handoffs, and experiment attempts are
commits on each item's work branch, so tracking works offline. When the Git host is
reachable, they are mirrored to issues on its project board. The
[work-tracking](skills/work-tracking/SKILL.md) skill covers claims, handoffs, offline
sync, branches, and pull requests; on GitHub, agents use `gh` with the `project` token
scope.

## Record and undo rule changes

[rules_ledger.py](scripts/rules_ledger.py) keeps one installation's change ledger:
`ledger.jsonl` in `$XDG_STATE_HOME/house-rules`, by default `~/.local/state/house-rules`.
Each record names the time, the actor kind (`human`, `agent` or `service`), the file, the
content hashes before and after, the reason and the source pull request. The contents are
stored by hash beside the ledger, so any record can be undone.

```sh
python3 scripts/rules_ledger.py write rules/core.md --actor agent --reason "why" --pr "#52" < new-core.md
python3 scripts/rules_ledger.py list
python3 scripts/rules_ledger.py rollback <id>
```

`write` replaces the file and appends its record. `rollback` restores the record's before
content and appends a rollback record, which can itself be rolled back.
`rules_changelog.py --ledger` records each rule file that a merged pull request changed, once
per commit and file; [pr-ready](skills/pr-ready/SKILL.md) §4 runs it after each merge.
The tests run in a temporary home: `python3 -B -m unittest scripts/test_rules_ledger.py`.

## Check messages and commands

Four scripts in [scripts/checks/](scripts/checks) check a rule mechanically before an agent
sends a message or runs a command. Each reads a path, or standard input when the path is
absent or `-`, and prints one JSON object per finding. Each exits 0 on pass, 2 on fail and
1 when the input cannot be read. They need only a Python interpreter.

```sh
python3 scripts/checks/question_format.py message.md
python3 scripts/checks/report_check.py --plan campaign.json message.md
python3 scripts/checks/blocker_classify.py failures.jsonl
echo 'cargo test --workspace' | python3 scripts/checks/build_command.py
```

[question_format.py](scripts/checks/question_format.py) checks the questions of an operator
message against [rules/session-writing.md §Questions to the
operator](rules/session-writing.md#questions-to-the-operator). A question is a numbered level-3
heading under a level-2 topic, with its number escaped (`### 1\.`) and unique across the
message; numbers count on from the first question, so a follow-up keeps its question's number.
Each context sentence starts with `FACT` or `ASSESSMENT`, on one source line; when that line
ends with a backslash, the next line may say what happens after the answer. Any other prose
line before the first list counts as context too, so it fails. A choice has one flat numbered
option list with exactly one whole-bold line ending in "(recommended)". The list ends with
**Answer like so:** and a three-line `text` example after the last question, showing an option
number, a request for more context and `ok`. The request line starts with a request word
("explain", "show", "more", "why"), after an optional "please" or "could you"; a statement that
opens with a question word ("what we need is clear") is a known pass. A bullet choice fails, and
so does a question asked in prose outside a question heading. A message without questions passes.
Whether a question asks the operator to do the team's own work (tests, replays, verification) is
left to the writer and to review: the check does not judge it, because who does the work cannot
be told from the words of a title.

[report_check.py](scripts/checks/report_check.py) checks a report against
[rules/writing.md §Claim labels](rules/writing.md#claim-labels) and §Checks before sending. Every
`FACT` sentence names its source: a link, a path, a quote, or a code span that holds a path or
two or more words, such as a command with its arguments. The check cannot tell a command from a
formatted value, so it has two known limits: a one-word command (`` `uptime` ``) is not a
source, and a multi-word value (`` `in progress` ``) is. Cite a one-word command with an
argument, its output path or a link. A label
covers the later sentences of its paragraph or list item, and each of them needs a source too. A claim
taken from another agent's report ("the import lane found …") is labelled `ASSUMPTION`. No
sentence sends the reader elsewhere ("see above", "my last message"). When the report names an
operator-only blocker, the bold opening span of its first line names each class it names; a
level-1 title above it is skipped. Two blockers of one class, such as two empty balances, count
as one. With `--plan`, every field the plan requires appears as a heading or a bold label.

[blocker_classify.py](scripts/checks/blocker_classify.py) classifies failure records or a
text. The input is a JSON object, a JSON array, JSON lines or plain text. It reads `category`
and `reason` (also nested in `failure`, or wrapped in `record`, as a job record holds them),
`status`, `code`, `provider_message`, `text`, and `provider`, `route` or `family` for the name
in the action text; other fields are ignored. Text wins over the code and the status, because
a provider can wrap an empty balance in a throttle or an account gate in a policy refusal.
Operator-only text rules come first across all text fields, so an ordinary failure in one field
cannot hide a blocker in another. A status counts only from the `status` field, never as a number inside text.
Each result gives `class`, `operator_only` and `action`, the exact step to take. The
operator-only classes are `credential`, `account`, `balance`, `quota`, `permission` and
`protected_asset`; the others are `rate_limit`, `timeout`, `policy_refusal`, `provider_error`,
`network`, `job_failure`, `unknown` (a record no rule matches) and `none` (a text that names no
failure). The exit status is 2 when any input is operator-only.

[build_command.py](scripts/checks/build_command.py) checks a shell command against the local
build scope and the release-profile rule of
[Local builds](prompts/skills/local-builds.md). It refuses `cargo test` or `cargo nextest
run` without a package and a test-name filter (a harness option value such as `--test-threads 4`
is not a filter), `cargo clippy` without a package and exactly one target, a cargo build without
`--release`, and any profile other than a release profile or the debugging profile
(`--profile debugging`, renamed with `--debug-profile`). The default name needs a
`[profile.debugging]` in the repository's Cargo manifest; a repository that debugs on the
development profile passes `--debug-profile dev`. It also refuses `ctest` without a test
selection and the `test` and `check` targets of `make`, `ninja` and `cmake --build`. It splits
the text at unquoted separators, joins backslash line continuations and ignores redirections.
Help, version, listing and dry-run calls pass. A repository
without pull-request CI runs its full local gate under `pr-ready` §4 without this check.

The checks read Markdown and JSON text and import no shared types. Their names match the
shared decision and campaign schemas where those define the same thing: the context labels
`FACT` and `ASSESSMENT` are the schema's `fact` and `assessment`; a level-2 topic is a
question's `topic`; the line after the backslash is its `afterAnswer`; `--plan` reads a
campaign record's `constraints` whose `rule` has `kind` `required_report_field` and a `field`.
The tests use synthetic examples only:
`python3 -B -m unittest discover -s scripts/checks -p 'test_*.py'`.


### Build-command hook

[build_hook.py](scripts/checks/build_hook.py) runs `build_command.py` on each shell call of
Claude Code and Codex, as their `PreToolUse` hook. `scripts/sync.py --install-hooks` registers it
([INSTALL-AGENTS.md §3 step 10](INSTALL-AGENTS.md#3-install-house-rules-instructions-and-skills)).
The hook input arrives on standard input, and the product is the only argument:

```sh
echo '{"tool_name": "Bash", "tool_input": {"command": "cargo test --workspace"}}' |
  python3 -I scripts/checks/build_hook.py claude   # exit 2: refused before it runs
```

The hook takes one of four decisions for each command:

- **Refused:** `cargo test`, `cargo nextest run` or `cargo clippy` with no `-p`/`--package`, or
  with `--workspace` or `--all`. The command does not run. The agent gets the reason and a
  targeted command to run instead.
- **Warned:** every other `build_command.py` finding, such as a missing test-name filter, no
  single clippy target, a debug build, `make test` or `ctest` without a selector. The command
  runs, and the hook logs the finding's rule name.
- **Unsure:** text the parser cannot read exactly, because the shell expands it or feeds it in:
  a here-document or here-string, a parameter expansion (`$NAME`, `${NAME}`, `$@`), command or
  process substitution, backticks, a command run by `eval` or `xargs`, a compound command (one
  that starts with a reserved word such as `if`, `then`, `do` or `{`), or a command that does not
  parse. `eval` and `xargs` count only as the program a command runs, so `cargo test --workspace
  eval`, with `eval` as a test filter, is still refused. The command runs, even when it would otherwise be refused.
  The hook logs it when the text names a checked program (`cargo`, `ctest`, `make`, `ninja`,
  `cmake`).
- **Allowed:** every other command runs and is not logged.

The log is `build-hook.jsonl` in `$XDG_STATE_HOME/house-rules/`, or in
`~/.local/state/house-rules/` without that variable. `BUILD_HOOK_LOG` in `custom/sync.env` moves
it ([INSTALL-AGENTS.md §6](INSTALL-AGENTS.md#6-update-and-remove)). Each decision writes one JSON
line per rule, with `time`, `harness`, `session_id` (when the input has one), `cwd`, `decision`,
`rule` and `command`. Before the command is written, the value of each `NAME=value` assignment
and the argument after each flag named like `token`, `key`, `secret` or `password` become
`<redacted>`. Redaction reads whole shell words, with quotes and escapes, and the scripts
quoted inside them, such as a `bash -c` script. An unclosed quote redacts the rest of the
command. A command holding a substitution (`$(`, backticks, `${`, `<(` or `>(`) is logged as
`<redacted>` as a whole; its line still has the decision and rule. A log that cannot be written changes no decision; the hook says so on standard error.

To count false refusals, list the refusals and judge each command:

```sh
jq -c 'select(.decision == "refused") | {time, harness, rule, command}' ~/.local/state/house-rules/build-hook.jsonl
```

A refusal is false when its command would not have run tests or clippy across every crate,
for example when the parser misread an argument. `BUILD_HOOK=off`
in `custom/sync.env` turns the hook off. Codex runs a new hook only after the operator trusts
it in `/hooks`; the installer prints a `TRUST:` line for each one.

## Verify

CI runs two workflows on every push and pull request. Both install the pinned documentation
tooling first.

- [Checks](.github/workflows/checks.yml) checks the report linter's JavaScript syntax. It
  runs the installation sync tests, the change ledger tests, the message and command check
  tests and the transcript extraction tests. It prepares every
  role and lens as the review service does, and tests that staging check.
- [Specification documents](.github/workflows/spec-docs.yml) checks the supported runtime
  and pins. It runs the documentation checker tests and the pr-ready script tests. It
  checks the complete documentation corpus and audits every declared test selector.

The tests use temporary Git repositories and stub CLIs. They make no network or model calls.
The linter step is a syntax smoke check, not proof of the linter's behavior.

Run the tests for changed scripts before committing. The first two commands set up the
pinned tooling once:

```sh
python3 -m venv .tmp/spec-docs-env
.tmp/spec-docs-env/bin/python -m pip install --require-hashes --only-binary=:all: --no-deps -r skills/spec-writing/scripts/requirements.lock
PYTHONDONTWRITEBYTECODE=1 .tmp/spec-docs-env/bin/python -m unittest discover -s skills/pr-ready/scripts
PYTHONDONTWRITEBYTECODE=1 .tmp/spec-docs-env/bin/python -m unittest discover -s scripts
.tmp/spec-docs-env/bin/python -B scripts/check_review_staging.py
.tmp/spec-docs-env/bin/python -B skills/spec-writing/scripts/spec_docs.py check --root .
bash -n skills/pr-ready/scripts/review-panel.sh
```

Test other changed skill scripts the same way, for example with
`discover -s skills/spec-writing/scripts`. Projects using House Rules keep their own tests.

Approved changes to House Rules land on `main`; never leave one parked on a side branch and
report it as done. Commit with the maintainer's GitHub noreply identity and UTC timestamps
(`TZ=UTC git commit`).

A pull request that changes rule text explains each change in its Rule changes section.
The merge commit carries that section ([pr-ready](skills/pr-ready/SKILL.md) §4).
[rules_changelog.py](skills/pr-ready/scripts/rules_changelog.py) prints the rules changelog
from those merge commits. [CHANGELOG-RULES.md](CHANGELOG-RULES.md) is the frozen archive of
earlier entries.

Attribution is in [NOTICE.md](NOTICE.md); the license is [MIT](LICENSE).

## About

House Rules is built by [Symbiotic Labs](https://symbiotic.build).
