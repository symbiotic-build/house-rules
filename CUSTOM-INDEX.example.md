# Machine-local capability index

Copy this file to `custom/INDEX.md` during installation. The destination is
gitignored and belongs to one machine; never put credentials, tokens, private
enrollment material, or copied account configuration in it.

## Host

| Field | Value |
|---|---|
| Operating environment | `<macOS, Linux, Windows, or WSL>` |
| House Rules source | `<absolute path>` |
| Updated | `<YYYY-MM-DD>` |

## Local policies

Operator rules for this computer only. Sessions read them through the managed block
(INSTALL-AGENTS.md §4). Delete the example row if there are none.

| Policy | Rule | Direction date | Full record |
|---|---|---|---|
| Worker model | `<e.g. workers run as <tool> <model> through <absolute wrapper path>; other subagents need operator approval>` | `<YYYY-MM-DD>` | `<custom/<file>.md or decision log path>` |

## House Rules installation receipts

One receipt per product home, in `custom/installations/`.

| Receipt | Product and home | Source revision | Date |
|---|---|---|---|
| `<file>` | `<e.g. Codex, ~/.codex>` | `<git rev-parse HEAD>` | `<YYYY-MM-DD>` |

## Capabilities

Delete example rows for capabilities that are not installed.

| Capability | Kind | Owner | Canonical location | Lifecycle command or authority | Discovered by | Last verification |
|---|---|---|---|---|---|---|
| `<self-installing tool>` | Skill + client + MCP | `<its vendor>` | `~/.agents/skills/<name>` plus native client registrations | the vendor's supported install/update/uninstall workflow | `<actual agents>` | `<date and result>` |
| `<name>` | `<Skill, plugin, MCP, browser, or other>` | `<owning product/project or local>` | `<resolved path or native registry>` | `<supported command or responsible owner>` | `<actual agents>` | `<date and result>` |

## Local Skills

Only Skills with no external lifecycle owner belong under
`custom/skills/<name>/`. Record every native symlink or copy here so it can be
updated or removed without guessing.

| Skill | Source | Native projections | Installation mode | Last verification |
|---|---|---|---|---|
| `<name>` | `<absolute custom/skills path>` | `<resolved agent paths>` | `<symlink or copy>` | `<date and result>` |

## Pending operator actions

- `<login, exact consent, or unresolved ownership conflict; never include a secret>`
