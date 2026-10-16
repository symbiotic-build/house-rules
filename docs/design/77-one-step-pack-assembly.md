Status: design only; operator choices recorded on 2026-10-07; implementation pending.

# One-step pack assembly from a named commit

Issue: [#77](https://github.com/symbiotic-sh/house-rules/issues/77).

## Result

A dispatcher builds each worker's prompt with one compiler call. The pack contains the role, lens, extra rule files, target repository rules and task text, in that order. Each rule file is included once. The compiler reads House Rules text from a named commit through Git objects. Uncommitted edits and other branches on disk cannot reach the pack. The acceptance criterion is "uncommitted edits never reach a prompt".

Lane workers run as normal Codex sessions in the operator's Codex home. Lane sessions load the live House Rules foundation through their installed pointer. Their role prompts come from the named commit. The compiler omits shared-rule includes for lane sessions that already load House Rules. Warden reviewers receive those includes in their prompts. A manifest records the role prompt's revision and the hash of the exact pack bytes. The manifest does not claim that a lane session's live foundation came from that revision.

## Terms and paths

- **Compiler:** [skills/pr-ready/scripts/prompt.py](../../skills/pr-ready/scripts/prompt.py), which expands whole-file `@rule house-rules:<path>` includes.
- **Pack:** the complete prompt text the dispatcher sends to a worker.
- **Part:** one input to a pack: a role, lens, extra rule file, target repository rules or task file.
- **Pin:** the named House Rules commit used to build a role prompt.
- **Manifest:** a JSON file beside the pack that records the pack's inputs and SHA-256 hash.
- **Include-once:** expansion of a repository path only at its first include within a compilation.
- **Lane runner:** the operator's scripts outside House Rules that launch local workers.
- **Target:** the repository checkout on which a worker works or performs a review.
- **Loader:** the target's pointer file, which directs a session to the House Rules index and the target's own rules.

House Rules file paths in this document are complete repository-relative paths. A target file has the `<target>/` prefix. The House Rules pointer is `house-rules/AGENTS.md`; the renamed House Rules index is `house-rules/INDEX.md`. Installed pointers use `<codex-home>/AGENTS.md` or `<repository>/AGENTS.md`. The pointer format and index rename belong to the [smaller-core design, issue #73](https://github.com/symbiotic-sh/house-rules/issues/73).

## Pre-flight

The dispatcher supplies the work item's Decisions and Pre-flight sections in the task file. Implementation reads those sections before changing code. Implementation also reads the target repository rules supplied in the pack.

The [role-pack design, issue #74](https://github.com/symbiotic-sh/house-rules/issues/74), owns shared-rule placement and worker instructions. The smaller-core design owns the loader template and index rename. Those designs own pointer text. This compiler includes target rule files unchanged and does not classify their pointer text (lead decision L6).

## Current behavior and evidence

- `FACT` The compiler at commit `9e1815917a4052e030b603350b27b855e6489e67` reads included files from disk, as verified in this run with `git show 9e18159:skills/pr-ready/scripts/prompt.py` ([skills/pr-ready/scripts/prompt.py, lines 37–39](https://github.com/symbiotic-sh/house-rules/blob/9e1815917a4052e030b603350b27b855e6489e67/skills/pr-ready/scripts/prompt.py#L37-L39)).
- `FACT` The compiler at commit `9e1815917a4052e030b603350b27b855e6489e67` expands repeated includes, as verified in this run by its `visit()` implementation ([skills/pr-ready/scripts/prompt.py, lines 16–39](https://github.com/symbiotic-sh/house-rules/blob/9e1815917a4052e030b603350b27b855e6489e67/skills/pr-ready/scripts/prompt.py#L16-L39)).
- `FACT` The compiler at commit `9e1815917a4052e030b603350b27b855e6489e67` accepts a file or standard input and writes expanded text, as verified in this run by its `main()` implementation ([skills/pr-ready/scripts/prompt.py, lines 55–68](https://github.com/symbiotic-sh/house-rules/blob/9e1815917a4052e030b603350b27b855e6489e67/skills/pr-ready/scripts/prompt.py#L55-L68)).

`ASSUMPTION` The [docs/design/77-one-step-pack-assembly.md at commit 38f7eba761ee31f4e73da20d2a42f185321b4567](https://github.com/symbiotic-sh/house-rules/blob/38f7eba761ee31f4e73da20d2a42f185321b4567/docs/design/77-one-step-pack-assembly.md#current-behavior) reports that the lane runner assembled prompts through separate compiler calls and concatenation. That account was not reverified against lane scripts in this run. The design replaces piecewise assembly with one recorded pack.

`DECISION` The operator's 2026-10-07 record says that lane workers use normal sessions instead of an isolated worker home. The role-pack design owns that session setup. The earlier isolated-home test is not the acceptance model for this design.

`ASSUMPTION` The operator's 2026-10-07 record reports that Warden added staging for `rules/` in commit `9f1568b` for [Warden issue #238](https://github.com/symbiotic-sh/warden/issues/238). Warden deployment was not checked in this run. This design does not assume that Warden stages only `prompts/` and `skills/pr-ready/`.

## Design

```mermaid
flowchart TB
  A["Dispatcher: role, lens, extra files, target, tasks, pin, shared-rule mode"] --> C["skills/pr-ready/scripts/prompt.py --rev pin"]
  G["House Rules clone: Git objects at the pin"] --> C
  T["Target checkout: own rules at the target commit"] --> C
  C --> S{"Running compiler matches the pin's copy?"}
  S -- no --> X["Exit 2; no output files"]
  S -- yes --> P["Pack: revision, role, lens, extra files, target rules, tasks"]
  S -- yes --> M["Manifest: inputs, omissions, revisions, pack SHA-256"]
  P --> W["Worker receives the pack unchanged"]
```

### Compiler interface

The compiler keeps single-file and standard-input expansion. The compiler gains a pack mode that requires a named commit.

```text
skills/pr-ready/scripts/prompt.py [--rev COMMIT [--repo DIR]] [--list] [FILE]
skills/pr-ready/scripts/prompt.py --rev COMMIT [--repo DIR] [--list]
    [--role NAME] [--lens NAME] [--include PATH]... [--task FILE [--task-source NAME]]...
    (--target DIR [--target-rev COMMIT] | --no-target)
    [--session] [--out DIR | --manifest FILE]
```

- `--rev COMMIT` reads House Rules files from that commit. Legacy single-file and standard-input expansion can still read the working tree without this option. Dispatchers use `--rev` for every worker prompt, including lane review panels.
- `--repo DIR` names a clone holding the commit. The default is the clone containing the compiler. A separate pinned checkout is unnecessary.
- `--role NAME` selects `prompts/roles/NAME.md`. `--lens NAME` selects `prompts/lenses/NAME.md`. Each name must match `[a-z0-9-]+`.
- `--include PATH` adds a House Rules repository-relative file. Repeated options retain command-line order.
- `--task FILE` adds local task text without expanding it. Repeated options retain command-line order.
- `--task-source NAME` gives the immediately preceding `--task` a logical source identifier, such as `symbiotic-sh/house-rules#77` or a caller-chosen name. It defaults to `inline`. It requires an immediately preceding `--task` and must never contain a machine path (lead decision L1).
- `--target DIR` selects a target Git checkout. `--target-rev COMMIT` selects its rules revision, defaulting to its `HEAD`. `--no-target` declares that the pack has no target. Pack mode requires exactly one target choice.
- `--session` omits includes whose House Rules repository-relative paths are under `rules/`. The dispatcher uses this option only for workers whose normal sessions already load the shared rules. The manifest records each omitted path. Warden and specialists without the foundation receive shared-rule includes by default.
- `--out DIR` publishes `pack.txt` and `manifest.json` together in a new directory. It requires pack mode and the destination must not exist. Without `--out`, pack bytes go to standard output. `--manifest FILE` optionally writes the manifest in standard-output mode and requires `--rev`. The two output options are mutually exclusive.
- An entry file or standard-input text cannot be combined with pack part options. `--session` is a pack-mode option.
- A failure returns exit 2 and one standard-error line. A compilation failure writes no output. In file-output mode, the compiler writes the complete pack and manifest into one temporary sibling directory on the destination filesystem, then publishes them with one directory rename. A failed write or rename publishes neither file. Standard-output mode is best effort: a failed output write exits nonzero, and the caller discards all output, including any manifest, from a nonzero run (lead decision L3).
- The compiler uses only the Python standard library. The compiler supports Python 3.9 through `/usr/bin/python3`.

The shared-rule option is the proposed way for one role file to serve normal lane sessions and Warden reviewers. The [role-pack design, issue #74](https://github.com/symbiotic-sh/house-rules/issues/74), owns which shared rules belong under `rules/`. That design keeps session-only instructions separate from role includes. This compiler omits only explicit shared-rule paths; the compiler does not infer rule meaning from prose.

### Reading from the commit

Every House Rules and target Git revision, tree and blob read must use Git's native `--no-replace-objects` option (or `GIT_NO_REPLACE_OBJECTS=1`). This requirement covers revision resolution, path validation, blob reads, compiler self-check and dispatcher extraction of the pinned compiler. Replacement refs must not change compiled bytes or recorded provenance.

With `--rev`, the compiler resolves `COMMIT^{commit}` once through `git --no-replace-objects rev-parse --verify`. The compiler records the resolved full commit id. It reads only requested paths, feeding `<commit>:<path>` to one long-lived `git --no-replace-objects cat-file --batch` process per source repository as each include is discovered (lead decision L2). It validates each requested path's mode with a path-specific `git --no-replace-objects ls-tree -z <commit> -- <path>` lookup and checks the exact returned path. It never enumerates the whole tree. For K requested paths, native Git supplies K path lookups and one batch process for blob contents; the compiler adds include ordering and manifest records without processing unrelated tree entries.

A valid path names a regular file with mode `100644` or `100755`. A symlink, submodule or directory fails compilation. Empty paths, NUL bytes, section references, absolute paths and `..` components fail compilation. An omitted shared-rule include must still name a valid file at the selected commit. A missing shared rule must not disappear silently.

The compiler never reads the working tree for rule text in commit mode. Uncommitted edits, untracked files and a different checked-out branch cannot change the pack. A missing commit fails visibly. The lane runner does not require a clean checkout or require the clone's `HEAD` to equal the pin.

### Compiler self-check

The compiler compares its running file bytes with `COMMIT:skills/pr-ready/scripts/prompt.py`. A mismatch fails with `prompt: compiler differs from <short id>; run the compiler from that commit`. This check pins the assembly code as well as the rule text.

A dispatcher can run a matching compiler in any clone containing the pin. A dispatcher can also extract `COMMIT:skills/pr-ready/scripts/prompt.py` into the durable run folder using `git --no-replace-objects show COMMIT:skills/pr-ready/scripts/prompt.py` and pass `--repo`. Compiler extraction does not require a separate pinned checkout. The extracted compiler must still pass the self-check.

### Pack layout and include-once

The pack order is:

1. `House Rules revision: <40-hex commit id>`.
2. Role text.
3. Lens text.
4. Extra files in command-line order.
5. Target repository rules, unless `--no-target` is selected.
6. Task files in command-line order.

Only pack mode writes the revision header. Legacy single-file and standard-input expansion remains plain text. The review preparer's existing use of `expand()` remains supported.

Each nonempty part ends with a newline. The compiler adds a newline when the source lacks one. The compiler joins parts with one empty line. Task assembly collects the compiled prefix and nonempty task parts, then joins them once (lead decision L7). An empty part adds no separator. Stable rule text precedes run-specific task text.

A repository path expands only at its first include in one compilation. Later includes of the same path produce no text. The manifest records the skipped repeats. The first occurrence determines the file's position. Cycle detection occurs before repeat suppression, so include-once cannot hide a cycle.

A role that repeats an include remains a source error caught by the role test. Expected repeats occur across parts, such as an extra file already included by a role. `--list` prints included paths once in first-include order. Omitted shared rules do not appear as included files.

### Task text is data

Task text is inserted literally without expansion or editing, apart from the part-ending newline rule. Standalone include lines are allowed and remain literal text; the compiler does not scan tasks to reject them (lead decision L4). The dispatcher supplies lenses and extra rules through compiler options. Task text copied from a work item cannot pull in rule files.

The dispatcher writes the work item's Decisions and Pre-flight sections into the task file. The compiler adds no separate work-item part. A capacity retry for a read-only reviewer restarts the whole review with the unchanged pack and manifest, after checking both hashes. A capacity retry for workers that change files (implementer, fixer) supplies the resume note as a second task file and builds a fresh pack and manifest. Each attempt keeps its own logs and output (lead decision L5).

### Target repository rules

The compiler reads both target rule files from the selected commit through Git with replacement refs disabled, using the requested-path reader described above. Native Git supplies two exact path lookups and at most two blob requests through the target's batch process. The compiler adds ordered headings and per-file provenance; it does not classify House Rules loaders (lead decision L6).

1. Include `<target>/.agents/rules.md` unchanged when present.
2. Include `<target>/AGENTS.md` unchanged when present, after `.agents/rules.md`.
3. When neither file exists, emit `Repository rules: this repository has no rules of its own.`

Only an absent file counts as missing. An invalid file entry, invalid UTF-8 or a read error fails compilation even when the other file exists. No loader wording causes a refusal. A loader with local requirements or a pointer to an absent rules file is included unchanged. This preserves every local requirement without guessing which instructions load House Rules.

Each included target file has its own heading and unchanged content, apart from the part-ending newline rule. This example uses a placeholder target commit and shows both files in order:

```text
Repository rules (<target>/.agents/rules.md at 3f1c2a9b7d04):
<rules file content>

Repository rules (<target>/AGENTS.md at 3f1c2a9b7d04):
<instruction file content>
```

The compiler does not expand includes or follow links inside either file. It does not read `<target>/CLAUDE.md`, `<target>/CONTEXT.md`, `<target>/INDEX.md` or files under `<target>/.claude/rules/` to assemble this part. The smaller-core design owns pointer templates and the index rename; this compiler does not detect those templates.

The [role-pack design, issue #74](https://github.com/symbiotic-sh/house-rules/issues/74), owns instructions for consuming the supplied target rules. Normal lane sessions keep their House Rules loading behavior. Warden reviewers use the supplied prompt and read-only target copy. The earlier instruction forbidding every lane worker from loading House Rules is rejected.

### Manifest

The manifest is one JSON object with sorted keys and a trailing newline. Object ids, byte counts and hashes in this example are placeholders. File paths inside the manifest are repository-relative to their named source; they are not machine paths. A task's `source` is a logical identifier rather than its input file path (lead decision L1).

```json
{
  "compiler": {
    "blob": "<compiler blob id>",
    "path": "skills/pr-ready/scripts/prompt.py"
  },
  "files": [
    {"blob": "<role blob id>", "bytes": 728, "path": "prompts/roles/reviewer.md"},
    {"blob": "<lens blob id>", "bytes": 194, "path": "prompts/lenses/correctness-security.md"}
  ],
  "format": 1,
  "house_rules_revision": "<resolved House Rules commit id>",
  "omitted_shared_rules": ["rules/writing.md"],
  "pack": {"bytes": 1024, "sha256": "<hash of exact pack bytes>"},
  "parts": [
    {"kind": "role", "path": "prompts/roles/reviewer.md"},
    {"kind": "lens", "path": "prompts/lenses/correctness-security.md"},
    {"bytes": 83, "kind": "task", "sha256": "<task hash>", "source": "symbiotic-sh/house-rules#77"}
  ],
  "skipped_repeats": [],
  "target": null
}
```

`files` records included House Rules files in first-include order. Each file entry records its blob id and byte count. `parts` records the requested part order. A skipped repeat records its path and the 1-based part number. `omitted_shared_rules` lists distinct omitted paths in first-encounter order. An empty omission list means all shared-rule includes were expanded.

Task files are local inputs rather than Git blobs. Each task entry records its logical source identifier, byte count and SHA-256 hash, in the existing requested part order. The source is an issue reference, `inline` or a caller-chosen name, never a machine path (lead decision L1). `pack.sha256` hashes the exact output bytes. The pack header contains only the revision because the pack cannot contain its own hash.

The target record contains the selected commit and an ordered `files` list. Each entry records an included file's path, commit, blob id, byte count and SHA-256 hash. Values are placeholders:

```json
{"commit": "<target commit id>", "files": [
  {"blob": "<rules blob id>", "bytes": 1840, "commit": "<target commit id>", "path": ".agents/rules.md", "sha256": "<rules hash>"},
  {"blob": "<instruction blob id>", "bytes": 280, "commit": "<target commit id>", "path": "AGENTS.md", "sha256": "<instruction hash>"}
]}
{"commit": "<target commit id>", "files": []}
```

The list contains only present files, with `.agents/rules.md` before `AGENTS.md`. An empty list records that neither exists. Each `path` is relative to the target repository. The requested repository-rules part is recorded as `{"kind": "target"}`; its file paths are in `target.files`. With `--no-target`, `target` is `null`. The manifest excludes the target's machine directory. It records compiled inputs only and does not record or pin the live session foundation.

### Python interface

`expand()` keeps its existing arguments and gains an optional `source` keyword. Pack assembly uses a separate function in the same compiler module.

```python
class WorkingTree:
    def __init__(self, root: Path): ...

class Commit:
    def __init__(self, repo: Path, rev: str): ...
    revision: str

def expand(text=None, *, file=None, root=ROOT, source=None) -> tuple[str, list[str]]: ...
def build_pack(source, *, role=None, lens=None, includes=(), tasks=(),
               target=None, omit_shared_rules=False) -> tuple[bytes, dict]: ...
```

### Changes in House Rules

- [skills/pr-ready/scripts/prompt.py](../../skills/pr-ready/scripts/prompt.py): add commit reads, compiler self-check, pack mode, include-once, shared-rule omission, target rules, manifest output and atomic output handling.
- [skills/pr-ready/scripts/test_prompt.py](../../skills/pr-ready/scripts/test_prompt.py): replace repeat-expansion expectations with include-once checks; add the tests below.
- [prompts/README.md](../../prompts/README.md): document pack mode, required commit and target choices, shared-rule mode, manifests and failure behavior.
- [skills/pr-ready/SKILL.md](../../skills/pr-ready/SKILL.md): document one compiler call per dispatched worker and task files containing Decisions and Pre-flight sections.
- [skills/pr-ready/references/review-prompt.md](../../skills/pr-ready/references/review-prompt.md): document compiling the fixer role and filled task together from the pin.

[skills/pr-ready/scripts/prepare.py](../../skills/pr-ready/scripts/prepare.py) keeps its existing interface. The existing `expand()` caller remains supported. Shared-rule ownership changes belong to the role-pack design rather than a second set of copies here.

### Changes in the lane runner

The lane runner changes are outside this House Rules change:

1. Build each worker prompt in one pack-mode call using the pin. Replace compiler calls followed by concatenation.
2. Use `--session` for normal lane sessions. Keep the operator's Codex home, skills and guardian escalation path.
3. Pass the role, lens, extra files, target worktree and task files through their compiler options.
4. Send the output pack unchanged. Retain each pack and manifest beside its worker log. Print the pack hash in worker status output.
5. Replace clean-checkout or checked-out-branch requirements with commit availability and the compiler self-check. Retire the separate pinned checkout requirement.
6. Build lane review panels from the same named commit. Replace the live-checkout execution of `<lanes>/main/finalize.sh`'s review-panel entry point with the matching `skills/pr-ready/scripts/review-panel.sh` from the pin. Compile every panel prompt with `--rev`.
7. Replace the legacy canon switch with explicit extra-file includes. Include-once removes overlap with the role. Remove the obsolete comment advertising section references.
8. Supply Decisions and Pre-flight in the task file. A capacity retry for a read-only reviewer restarts the whole review with the unchanged pack and manifest, after checking both hashes. For workers that change files (implementer, fixer), supply a resume note as an additional task file and build a fresh pack and manifest on a capacity retry. Keep each attempt's logs and output.

Lane sessions still load session rules from the live House Rules checkout through the installed block. Only the role prompt is commit-built. Pinning a role prompt does not isolate a normal session from the live foundation.

### Warden adoption

Warden can use the same compiler entry point with its named House Rules commit. Warden builds reviewer packs without `--session`. Warden can then retain manifests for its prompt inputs. Shared rules remain in `rules/`; this design adds no verbatim copies under `prompts/util/`.

The role-pack design owns Warden staging of `rules/` and the corresponding guard update. The matching Warden compiler change is drafted after the lane runner's test run passes on the new assembly. The draft goes to the operator for approval before external writes.

Warden reviewers remain read-only. Warden supplies a read-only PR copy. Reviewers have no network except the model provider and run no builds or tests. Continuous integration runs builds and tests. Warden posts the review on GitHub. Mac lane scripts read the review and start the fixer locally. Pack assembly changes none of those boundaries.

## Rejected alternatives

- **Keep piecewise assembly.** Rejected because piece hashes do not identify the final prompt bytes and do not remove overlap across parts.
- **Fail on every repeated include.** Rejected because an extra rule may already occur in a role; include-once preserves the role's placement.
- **Expand includes in task text.** Rejected because work-item text would share the rule namespace and could place a lens after the task.
- **Copy a commit tree into a separate pinned checkout.** Rejected because Git object reads provide the required pin without another checkout.
- **Compile the working tree after a clean-checkout check.** Rejected because an edit after the check can reach a prompt.
- **Read Git objects but reject dirty checkouts too.** Rejected because harmless working-tree edits cannot affect commit-built prompts.
- **Use a second pack compiler.** Rejected because the existing compiler already owns include expansion.
- **Isolate lane workers and forbid House Rules loading.** Rejected by the operator's choice of normal sessions with the live foundation.
- **Classify or rewrite `<target>/AGENTS.md`.** Rejected by lead decision L6 because repeated classification repairs still missed loading instructions or refused prohibitions. Supplied rules remain unchanged; normal lane sessions load House Rules, and Warden cannot reach a live checkout from its jail.
- **Draft the Warden change immediately or never draft it.** Rejected because the operator chose drafting after the lane runner's successful test run, with approval.

## Size

`ESTIMATE` Commit reads, pack assembly and manifests grow [skills/pr-ready/scripts/prompt.py](../../skills/pr-ready/scripts/prompt.py) from the original small compiler to a few hundred lines. Target rules and shared-rule omission add tests to [skills/pr-ready/scripts/test_prompt.py](../../skills/pr-ready/scripts/test_prompt.py). Exact implementation size is not measured in this design revision.

Pack size depends on the selected role, extra files, target rules and task text. Shared-rule omission reduces normal lane role prompts by the omitted files' bytes. The live session still loads those rules. Include-once removes repeated included text across parts. No numerical token saving is claimed without a measured pack comparison.

## Verification

Implementation tests belong in [skills/pr-ready/scripts/test_prompt.py](../../skills/pr-ready/scripts/test_prompt.py). Each test uses a small local Git fixture with a compiler copy. Each subprocess has a fixed short timeout.

1. Commit-built output stays identical after an included working-tree file changes or the clone checks out another branch. A file present only as an untracked file fails as missing at the pin.
2. The manifest records the resolved House Rules commit. Each included blob matches `git --no-replace-objects rev-parse <commit>:<path>`. The pack hash matches the output bytes.
3. Include-once preserves first-include order across role, lens and extra-file parts. The manifest records repeats. Include cycles still fail.
4. Every role compiles with no repeated includes in both shared-rule modes. Normal-session mode omits `rules/` includes and records the omissions. Default mode includes the shared rules once. An invalid omitted-rule path still fails.
5. A symlink entry, a mismatched compiler, a missing commit, a manifest without `--rev`, or pack mode without `--rev` returns exit 2 with one error line and no outputs.
6. Pack parts and separators match the declared order. Legacy single-file and standard-input output has no revision header. Task bytes and manifest hashes agree with the part-ending newline rule. A standalone include line in a task remains literal and does not read the named rule. Task sources cover an issue reference, a caller-chosen name and the `inline` default; no machine input path reaches the manifest. A bounded regression with nonempty and empty tasks rejects repeated concatenation of the accumulated prefix while preserving bytes and hashes (lead decision L7). Task-file and lane-runner retry instructions distinguish unchanged read-only reviewer inputs from fresh packs for workers that change files (lead decision L5).
7. Target fixtures cover both `.agents/rules.md` and `AGENTS.md` present (included unchanged, in that order), either file alone, neither file, and uncommitted edits to both files. Loader wording, local requirements beside a loader, and a pointer to an absent rules file do not cause refusals or dropped content. Invalid file entries, invalid UTF-8 and read errors fail even when the other file exists. The no-rules result occurs only when both files are absent. The target manifest records the selected commit and each included file's blob, byte count and hash in order. House Rules' own pointer is included alongside its bible without reading `house-rules/INDEX.md`.
8. Pack mode without exactly one target choice fails with exit 2. The compiler tests run under `/usr/bin/python3` with Python 3.9.
9. One bounded replacement-ref case uses small House Rules and target fixtures. Install replacement commits, trees and blobs in turn, including the compiler blob and one selected rule blob in each repository. Extract the compiler with replacements disabled. Compile before and after each replacement; pack bytes, resolved revisions, blob ids and manifest hashes must stay identical. Record Git invocations and check that every revision, tree and blob read, including compiler extraction, uses native replacement protection. Each subprocess has a fixed short timeout.
10. Requested-path reads use one long-lived batch process per source repository and no whole-tree enumeration. A fixture with an unrelated file records Git requests and confirms that only requested paths are read.
11. A compilation failure produces no output. File-output failures while writing either artifact or renaming the directory leave no published destination. Success publishes both files together. An existing destination fails without overwriting it. A standard-output write failure returns nonzero; the caller discards all output from that run.

The lane runner's canary test runs after switching assembly:

- **Dirty edit and branch independence:** edit [prompts/roles/reviewer.md](../../prompts/roles/reviewer.md) without committing in the clone used by the runner. Run a lane review round from the named commit. Every reviewer manifest must name the pinned role blob. The canary text must appear in no pack or worker log. Repeat from another checked-out branch with a matching extracted compiler.
- **Normal session and supplied target rules:** run a worker with the operator's normal Codex home. Confirm that shared-rule paths are omitted from the role prompt. Confirm that the target rules part and every included target blob are recorded. Confirm that the worker retains the live foundation, skills and guardian path. A read of the live House Rules index is expected session behavior rather than a failure.
- **Hash identity and panels:** record the exact bytes sent to each implementer, reviewer, triager, fixer and checker. Compare each hash with its manifest. Every role prompt, including panels launched by `<lanes>/main/finalize.sh`, must name the lane pin. No role prompt may come from the live working tree.

The smaller-core design's separate canary remains separate. This design's canary tests pack assembly and its interface with normal lane sessions. The role-pack design owns shared-rule placement checks.

## Rollout and pins

1. Coordinate the canonical pointer and `house-rules/.agents/rules.md` with the smaller-core design. The House Rules target supplies `.agents/rules.md` and `AGENTS.md` unchanged, without reading its universal index. No loader detection is required (lead decision L6).
2. Land the role-pack shared-rule changes before switching lane prompt assembly. Default compilation must support the canonical files under `rules/`.
3. Land this compiler change and switch the lane runner to one-call assembly at the matching pin. Include target rules and shared-rule omission in that switch. An old compiler rejecting the new options must stop the runner before a worker starts.
4. Run this design's lane canary tests. Retire the separate pinned checkout requirement after the runner uses Git objects and matching compiler code.
5. After the lane runner's test run passes, draft the matching Warden compiler change for operator approval. Warden's existing staging path remains usable while that change is pending.

Legacy single-file expansion remains available to existing callers. Normal sessions continue to use their installed foundation pointers. This design does not prescribe a merge order for unrelated review-skill or specialist work.

## Interfaces with the other designs

- [Smaller core, issue #73](https://github.com/symbiotic-sh/house-rules/issues/73): owns `house-rules/INDEX.md`, global and repository pointers, and its separate canary. This compiler includes target pointer text unchanged and does not detect its shape (lead decision L6).
- [Role packs, issue #74](https://github.com/symbiotic-sh/house-rules/issues/74): owns shared rules under `rules/`, role instructions for normal sessions and Warden, and the Warden staging guard. This design provides shared-rule omission and a manifest of compiled inputs. The dispatcher puts Decisions and Pre-flight in task text.
- [Specialists, issue #75](https://github.com/symbiotic-sh/house-rules/issues/75): owns specialist selection, separate Claude safe-mode processes, supplied skill text and the Model Context Protocol (MCP) test and fallback. Specialist packs use the named commit and include shared rules when the specialist does not load the foundation.
- [Review skill, issue #76](https://github.com/symbiotic-sh/house-rules/issues/76): owns `change-review`, the shared review format, and one reviewer for a plain chat request unless a panel is requested. Dispatched reviewer prompts use the named-commit compiler interface.

## Decisions

- **2026-10-07 — Prompt source:** `DECISION` The operator chose building every prompt from a named House Rules commit through Git objects in any clone containing that commit. Uncommitted edits and other branches on disk cannot reach a prompt. The separate pinned checkout is unnecessary. The choice covers lane review panels.
- **2026-10-07 — Warden timing:** `DECISION` The operator chose drafting the matching Warden change after the lane runner's test run passes on the new assembly. The draft requires operator approval before external writes.
- **2026-10-07 — Lane sessions:** `DECISION` The operator chose normal lane sessions in the operator's Codex home, with House Rules, skills and guardian escalation. The live session foundation remains distinct from the commit-built role prompt. The role-pack design owns session setup.
- **2026-10-07 — Shared-rule delivery:** `DECISION` The operator chose one canonical home under `rules/` for writing, Git and priority-label instructions. One role file must serve normal sessions without repeating their shared rules and Warden reviewers with shared-rule includes. The role-pack design owns file placement; this design supplies the compiler option.
- **2026-10-07 — Index and pointers:** `DECISION` The operator chose renaming the House Rules index to `house-rules/INDEX.md`. Global, managed-repository and House Rules pointer files use the same shape with installation paths adjusted. The smaller-core design owns the rename and pointer text; loader detection is superseded by lead decision L6.

- **2026-10-07 — Warden review boundary:** `DECISION` The operator kept Warden reviewers read-only, with no builds or tests and no network except the model provider. Continuous integration owns builds and tests. Warden posts reviews; Mac lane scripts start local fixers. The role-pack design owns the reviewer setup.
- **2026-10-07 — Lead decision L1, task provenance:** `DECISION` The lead chose a logical task-source identifier, such as `symbiotic-sh/house-rules#77`, `inline` or a caller-chosen name, never a machine path. Keep the existing task order, byte count and hash.
- **2026-10-07 — Lead decision L2, tree reading:** `DECISION` The lead chose reading only requested paths through one long-lived `git cat-file --batch` process, fed `<commit>:<path>` for each include as it is discovered. No whole-tree enumeration.
- **2026-10-07 — Lead decision L3, failure contract:** `DECISION` The lead chose no output on compilation failure. File output publishes the pack and manifest together by writing both into one temporary directory and renaming that directory once. Standard-output mode is best effort: a failed write exits nonzero, and the caller discards any output from a nonzero run.
- **2026-10-07 — Lead decision L4, literal task includes:** `DECISION` The lead allowed literal include lines in tasks. Task text is inserted literally and never expanded. Remove the task scan that rejects standalone include lines and its rejection acceptance case.
- **2026-10-07 — Lead decision L5, capacity retries:** `DECISION` A read-only reviewer's run that fails with a provider-capacity error leaves no work to resume: the review panel's retry restarts the whole review with the unchanged pack and manifest, after checking both hashes. Each attempt keeps its own logs and output, and the summary records the attempt count. The resume note as an additional task file, with a fresh pack and manifest per attempt, applies to dispatched workers that change files (implementer, fixer). This narrows the capacity-retry text in the task-file section and implementation step 8.

- **2026-10-07 — Lead decision L6, no loader classification:** `DECISION` The lead replaced the mixed-loader and older-loader refusal requirements recorded on [issue #77](https://github.com/symbiotic-sh/house-rules/issues/77). Three review rounds each found another loading instruction that escaped detection or a prohibition wrongly refused. Under no-fortification, the classification mechanism should not exist. A House Rules loading line is harmless because lane workers are normal sessions that already load House Rules and Warden reviewers cannot reach a live House Rules checkout from their jail. Include the target's `.agents/rules.md` and `AGENTS.md`, each unchanged when present, from the selected commit and in that order. No loader wording is refused and no local rule is dropped.
- **2026-10-07 — Lead decision L7, task assembly:** `DECISION` The lead chose collecting task parts and joining them once, as recorded on [issue #77](https://github.com/symbiotic-sh/house-rules/issues/77). Re-copying the accumulated pack inside the loop adds copying without additional behavior. Keep task order, literal bytes, separators and manifest hashes.

## Open points

No operator choice remains open for this design.

- **Runtime verification:** close when the compiler implementation and the declared compiler and lane tests pass. Pack assembly remains undeployed until that evidence exists.
- **Warden adoption:** close when the lane runner's successful test evidence is available, the operator approves the matching Warden change, and Warden adopts that change.
