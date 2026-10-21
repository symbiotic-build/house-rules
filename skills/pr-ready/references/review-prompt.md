# Review prompt template

Fill the angle-bracketed fields; delete lines that do not apply.

```text
Review <PR link or branch> in this checkout; diff `git diff <base>...HEAD`.
<First round: "Review the whole change." | Later round, a check round: "Previous review: <path>.
Fix base: <last reviewed head>." Prepare it with `prepare.py review --since <last reviewed head>`;
the check-round rules are prompts/util/check-round.md.>
Scope: <modules/directories>. Spec: <document and sections>; read the module README.
Blocking review against the shared reviewer pack, focused on: <the invariants that matter for this
change, e.g. authorization on every path, crash/replay, bounded cost>.
```

## Fix prompt template

For a dispatched fixer, save the filled template and the work item's Decisions and
Pre-flight sections in one task file. Compile it with the role in one call:

```sh
/usr/bin/python3 skills/pr-ready/scripts/prompt.py --rev <commit> --repo <clone> \
  --role fixer --target <checkout> --session --task <filled-task> \
  --task-source <owner/repository#issue> --out <new-run-directory>
```

The normal session loads its live foundation; the role and repository rules are
commit-built. Retain the pack and manifest. Send the pack unchanged.

For legacy single-file expansion:

Expand the [fixer role](../../../prompts/roles/fixer.md) with `scripts/prompt.py` before this template.

```text
<PR>, branch <branch>, this checkout. Accepted findings: <path> — read fully. Follow the fixer role
for scope and the worker pack for implementation: <one line per accepted item>.
Merge the default branch first if it moved (merge, no rebase).
Local gate: apply the worker pack and the repository's declared gates.
Commit message conventions: <conventions>. Delivery override: <task-specific override, if any>.
```
