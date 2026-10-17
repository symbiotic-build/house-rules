# Prompt collection

- [skills/](skills/): code-change rules.
- [util/](util/): role-specific pieces used by some roles.
- [shared rules](../rules/): canonical writing, Git and priority-label owners.
- [roles/](roles/): role instructions and includes; a role may include another role.
- [lenses/](lenses/): review focus instructions.

Include one whole file per line:

```text
@rule house-rules:prompts/skills/code-canon.md
```

Skill and utility files never include other files. Includes are repository-relative
whole files, recursively expanded without heading parsing or title stripping.
A missing file fails the build, including a shared owner omitted with `--session`.

From a pinned checkout, run `/usr/bin/python3 skills/pr-ready/scripts/prompt.py`
with a repository-relative file argument, or supply text on stdin. `--list` prints
the files used once in depth-first first-include order, including the entry file
when supplied. Paths outside the repository, section references and cycles fail with exit 2, one stderr line and no stdout.

## Loading paths

The default compile includes [writing rules](../rules/writing.md),
[Git rules](../rules/git.md) and [priority labels](../rules/priority-labels.md).
Warden uses this complete pack without reading a live House Rules checkout.
Warden reviewers use a read-only pull-request copy, contact only the model provider and run no builds or tests.
Continuous integration runs builds and tests. The Warden service posts reviews.

Use `--session` for normal lane sessions:

```sh
python3 -B skills/pr-ready/scripts/prompt.py --session prompts/roles/implementer.md
```

The session index loads the same shared owners plus [session writing rules](../rules/session-writing.md).
The compiler validates and omits all explicit includes under `rules/`.
Role instructions, review lenses and role-specific utility fragments remain included.
The compiled header states the selected loading path.
`--list` reports only files expanded for that path.

Session rules come from the live checkout through the installed House Rules block.
Only the role prompt uses a named commit under the one-step assembly design.
The dispatcher supplies repository rules and the work item's Decisions and Pre-flight sections.

## One-call pack assembly

Dispatchers build every worker prompt from a named commit:

```sh
/usr/bin/python3 skills/pr-ready/scripts/prompt.py --rev <commit> --repo <clone> \
  --role implementer --include prompts/skills/code-canon.md --target <checkout> \
  --session --task <task-file> --task-source <owner/repository#issue> --out <new-run-directory>
```

The task file contains the work item's Decisions and Pre-flight sections.
One call assembles the revision header, role, optional lens, extra includes,
repository rules and literal task files in that order. Repeated `--include` and
`--task` options retain their order. Rule files expand once across the whole pack.
Cycles fail before repeat suppression. Each nonempty part ends with a newline;
parts have one empty line between them. Task include lines remain literal.

For structured review context, the preparer's final `# 7. Lens instructions` heading
selects a different order: revision header, shared role and includes, repository rules,
documentation context, literal tasks, then the expanded lens. Reviewers compiled from
one captured task share the prefix before the lens. The same order applies when the panel appends context to an
in-memory compilation. Lens spans are transient; the manifest schema does not change.
The manifest records the resulting part order and hashes the unchanged task bytes and
the complete reordered pack. Pack and diff context retain the default assembly order.
When compiling reviewers separately, pass the same complete `--reviewers LENS...` list
to each call so registered documentation uses one shared round plan. Separate live
preparations can capture different comments. In structured assembly, explicit shared
includes and mandatory specification rules expand before the lens, keeping them in the shared prefix.
Pack and diff retain specification rules after target rules unless an earlier include owns them.

Pack mode requires `--rev` and exactly one of `--target` or `--no-target`.
Role and lens names match `[a-z0-9-]+`. `--target-rev` defaults to the target's
`HEAD`. House Rules and target files come from Git objects with replacement refs
disabled. Dirty files and the checked-out branch cannot change those inputs.
Each unique requested file uses one native path lookup for mode validation and one
request to a long-lived `git cat-file --batch` process per source repository.
The compiler never enumerates unrelated tree entries. It adds include ordering
and provenance records to those native reads.
The running compiler must match the compiler blob at the selected commit.
To run from another checkout, extract that compiler with
`git --no-replace-objects show <commit>:skills/pr-ready/scripts/prompt.py`
into the run folder and pass `--repo <clone>`.

The target part includes the target's `.agents/rules.md` and then its `AGENTS.md`,
each unchanged when present, read from the selected commit (lead decision L6 in
`docs/design/77-one-step-pack-assembly.md`). Nothing is classified or refused, so no
local requirement can be dropped. When both files are absent, the part says
"Repository rules: this repository has no rules of its own."

`--out` publishes `pack.txt` and `manifest.json` together by one directory rename.
The destination must not exist. The manifest records resolved revisions, blob ids,
input byte counts and hashes, omissions, repeated includes and the exact pack hash.
A `--task-source` immediately follows its task and names a logical input such as
`owner/repository#77`, `resume-note` or the default `inline`; it never names a
machine path. Tasks are hashed after the part-ending newline rule.
Without `--out`, the pack goes to stdout; `--manifest <file>` optionally writes
its manifest. These output options are mutually exclusive. Compilation errors
return exit 2 with one stderr line and no output. A failed stdout write returns
nonzero; callers discard all output, including any manifest, from that run.

Single-file and stdin expansion remain available with or without `--rev`, without
a revision header. Without `--rev` they read the working tree. Existing legacy
`--session` calls remain supported. `--list` reports first-include order.
