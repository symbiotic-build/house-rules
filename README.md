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

## Verify

CI runs two workflows on every push and pull request. Both install the pinned documentation
tooling first.

- [Checks](.github/workflows/checks.yml) checks the report linter's JavaScript syntax. It
  runs the installation sync tests and the transcript extraction tests. It prepares every
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
