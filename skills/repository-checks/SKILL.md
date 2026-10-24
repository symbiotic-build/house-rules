---
name: repository-checks
description: Install and use a repository's deterministic rule checks, which run before each commit, before each push and in CI from one configuration, house-rules.json. Use when installing the checks in a clone, checking whether a clone has them, repairing a missing hook block or setting, or acting on a refused commit or push.
license: MIT
---

# Repository Checks

The [repository checks design](../../docs/design/194-repository-checks.md#repository-checks) is the
contract: the configuration, the hook blocks, the runner commands, the report and the failure states.
The runner is [scripts/checks.py](scripts/checks.py). The hooks and CI start it through
`house-rules exec`, which runs it at the House Rules revision the configuration resolves to.

## Install in one clone

Install once in each clone, and in each linked worktree whose hooks folder is a relative `core.hooksPath`.
The machine needs the `house-rules` command first: `python3 <House Rules checkout>/scripts/house_rules.py install`.
A rerun repairs missing pieces and keeps every choice the repository made.

**Procedure: install repository checks**

1. **Write the configuration:** `house-rules init`, unless the repository has `house-rules.json`.
2. **Review and stage the configuration:** `git add house-rules.json`. The install never lists it.
3. **Install:** `house-rules exec skills/repository-checks/scripts/checks.py install --ci github`.
   - Writes the hook blocks, the `house-rules.command` setting and the GitHub Actions workflow, and
     prepares the spec checker's environment when spec-docs is enabled.
   - Add `--dry-run` first to list each item as `create`, `update`, `unchanged` or `refused`. It writes
     none of them, but `exec` still resolves House Rules and can fill its cache.
   - Resolve each refused hook file with the step its line prints, then install again.
   - The install is the only writer of the hooks folder while it runs: it refuses a hook that changed after it
     read it, but an edit, permission change or link change made during the install itself is outside its
     contract; don't edit hooks while installing.
4. **Stage the install:** `git add` the files its `next: stage the install` line names.
5. **Check everything:** `house-rules exec --origin index skills/repository-checks/scripts/checks.py run --stage ci --index`.
   - Fix failures in existing files before the hooks start refusing commits.
6. **Commit through a PR.** CI runs the same checks on the commit.

Leave out `--ci github` in a repository that uses another CI system; the install then prints the one
command its job runs. [Check installation](../../docs/design/194-repository-checks.md#check-installation)
and [Hook block](../../docs/design/194-repository-checks.md#hook-block) give the details.

When `prepare` or the session line says `house-rules.json` is not staged, review and stage it; do not
run `init` again, which refuses an existing file.

To check a clone, run `house-rules exec --origin index skills/repository-checks/scripts/checks.py status`;
`status` reads the staged configuration, so exec must resolve that one too.
It prints the resolved House Rules revision and the effective checks for each stage. The runner's
`status` never fetches; `exec` around it resolves first and can.

## Integrate a refused hook by hand

A pre-commit framework hook, a hook in another language, or a shell hook whose first line sets an option such
as `-n` stays refused: the install never edits it.

1. **Add the call:** for the framework, add the `repo: local` entry the refusal prints to
   `.pre-commit-config.yaml`. In another hook, call `"$(git config --get house-rules.command)"` with the
   arguments the [hook block](../../docs/design/194-repository-checks.md#hook-block) passes, and exit with
   its status.
2. **Install again:** the rest of the install completes. That hook stays listed as `refused`, and the
   install exits 1; that refusal is expected.
3. **Verify each integrated stage on its own:**
   - pre-commit: stage a file with a trailing space and commit. The hook must refuse the commit with a
     `FAIL  whitespace` line. Unstage the file afterwards.
   - pre-push: push a commit to a local bare repository (`git init --bare /tmp/verify.git`, then
     `git push /tmp/verify.git HEAD:refs/heads/verify`). The hook must print a
     `repository checks: pre-push on …` header; the defaults list no pre-push check, so the header is the
     evidence, and a check the configuration lists at pre-push must run too.

The session line keeps reporting "no hook block" for that hook, because it looks for the block.

## Act on a refused commit or push

The report lists each check with `PASS`, `FAIL`, `WARN`, `ERROR` or `SKIP`. Under each failing check it
prints the check's output, a `fix:` line and a `rerun:` line.

1. **Fix each finding** the failing check's output names, as its `fix:` line says.
2. **Stage the fix**, or commit it before a push.
3. **Rerun that check alone:** run its `rerun:` line, which ends in `--only <check>`.
4. **Commit or push again.**

A line that starts `repository checks:` on standard error, with exit status 2, is a preparation failure:
run the repair after its `;`. A check that is wrong for the repository changes in `house-rules.json`,
with a `reason`, through a reviewed PR. Skipping the hooks follows the
[rule line](../../docs/design/194-repository-checks.md#rule-line). The
[report format](../../docs/design/194-repository-checks.md#report-format) and the
[failure state](../../docs/design/194-repository-checks.md#failure-check-refused) give the details.
