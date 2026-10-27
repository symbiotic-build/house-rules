# Review preparer and panel launcher: behaviour reference

Details of `scripts/prepare.py` and `scripts/review-panel.sh`, moved out of the skill so the
loop stays readable. The skill states what to do; this file states exactly how the tools behave.

Review task fields: [review template](review-prompt.md). `scripts/review-panel.sh` runs
  the base resolver once, then `scripts/prepare.py review --base REF --no-fetch --context-only`
  once per model family. Every reviewer in that family compiles the same captured task bytes.
  Preparation failures, reviewer CLI failures, and reports without a
  `VERDICT: APPROVE` or `VERDICT: REQUEST_CHANGES` token anywhere in the report
  (Markdown emphasis is accepted; `scripts/verdict.py` fails closed: any `REQUEST_CHANGES`
  token means `REQUEST_CHANGES`, and `APPROVE` requires every token to agree)
  are recorded in `summary.txt` and make the panel exit nonzero. Unknown configured CLIs
  fail the reviewer; explicitly selected reviewers whose families are unconfigured also fail.
  A checkout that cannot be opened fails before changing outputs. Each run requires a fresh
  panel directory and creates it exclusively. An existing directory is refused without
  changing its reports, prompts, packs or manifests. A base-resolution failure is recorded
  in the new summary. Before any output changes, panel names must match
  `[A-Za-z0-9][A-Za-z0-9._-]*` and the panel directory must resolve strictly beneath the
  configured output root, including through symlinks. Reviewer names must match
  `[a-z0-9-]+` and an existing file stem in `prompts/lenses/`, with no duplicates.
  Structured prompt order: shared review rules, PR/issue context and requirements, then
  the change and lens instructions last. Different lenses
  share the prefix before those final instructions when one task is prepared once and compiled per lens, as the panel does.
  Separate standalone calls share the layout, but live inputs such as new comments can differ between calls.
  Pack and diff retain their existing order, including specification rules after target rules unless an earlier include owns them.
  Structured assembly expands explicit shared includes and mandatory specification rules before lenses, preserving duplicate suppression.
  Structured `--context-only` output ends with the same `# 7. Lens instructions` heading,
  without a lens body. The compiler uses that heading to place the selected lens last,
  after target rules and task context. This also applies when the size guard uses pack for
  the change. The panel retains the compiled lens span in memory until it appends context;
  it does not reread pinned inputs or add manifest fields. Task hashes cover the unchanged
  context bytes, and the pack hash covers the final order.
  The panel compiles context-only tasks with its pinned role, lens and target rules. Requirements
  are indexed as R1, R2, … with source links, most authoritative first: design/spec
  documents, linked issues (title, labels, body), non-bot
  OWNER/MEMBER/COLLABORATOR comments oldest first, then the PR description (author claims).
  Without a PR or issue, range commit messages supply the task. Standalone use accepts
  `--pr`, repeatable `--issue`, `--spec PATH`, `--tests ID,ID`,
  `--test-prefix PREFIX` (default `PT`, the acceptance-test ID prefix, e.g. `PT1`)
  and `--summary FILE`. Use the repository's prefix, such as `--test-prefix AT` for `AT1`.
  Without shared documentation metadata, the selected spec document is included whole, preserving headings and content;
  explicit section selectors are rejected. Test IDs are collected from PR/issue bodies
  and range commit messages and checked within the selected document; they do not
  narrow its content. Spec selection is
  limited to `--spec`, then an existing path in a `Design: <path> [§...]` line, then a
  Markdown path named in PR/issue/commit text, then a Markdown design/spec file edited
  by the change. Design lines outrank ordinary mentions across those sources; otherwise
  the first mention wins (PR, issues, then range commits), and edited candidates use
  lexical path order. Named paths match whole path tokens, including paths extracted
  from host-specific blob/raw/src URLs, never a suffix of a longer path. GitLab subgroup
  routes and optional `www.` hosts are supported. URL refs use the longest matching
  local branch, remote-tracking branch or tag; without a matching ref, only a single
  ref segment is assumed. Unresolved Markdown URLs are reported at the top. Local path
  mentions may start with `./` or `/`. Before reading the selected
  document, `git cat-file -s` checks its size against a 2,000,000-byte limit. Oversized
  documents fail preparation without emitting a prompt; the error names the path,
  byte size and limit. Unsearched tests are not reported as missing.
  There is no document scoring or content scan. Hyphens are part of
  acceptance IDs: `AT1` does not match `AT1-case`. Linked issues come from PR-body
  `Refs/Closes/Fixes/Resolves #N`, `owner/repo#N`, issue URLs and `--issue`.
  GitHub reads use optional `gh`; unavailable automatic sources and unresolved references
  are reported at the top. An explicitly requested PR or issue that cannot be resolved
  is an error. Deleted maintainer accounts retain their comments with an unknown-author
  notice. Null PR and issue bodies are treated as empty. URL userinfo and credential-like
  query values are redacted from warnings, errors and prompts. Mandatory documentation context
  that requires this redaction is refused before publication or dispatch, using the same
  policy from the pinned preparer. Its source bytes and provenance are never rewritten. A later GitHub read failure names the failed source and preserves already
  fetched context. Comments go in whole; the prompt size guard bounds the total.
  Codex defaults to `structured`, others to `pack` (file index and hunk headers);
  `--format diff` omits legacy spec content. `--format` overrides defaults.
  The structured change opens with two lists: the changed files shown whole, and the files
  shown as a diff only with the reason (size, deleted, binary or submodule).
  Each changed text file up to the cap, whether source, test or documentation, is shown
  whole as uncolored `git diff` output with the whole file as context. Each line carries its
  number: the head number for context and added lines, the old number for removed lines.
  Git's mode, file-type and missing-newline lines stay as unnumbered rows. A file is read
  whole only when its size fits the remaining prompt budget. The caller's `GIT_DIFF_OPTS`
  and blank-line setting cannot shorten the context; a file whose numbered rows do not
  rebuild its head text fails preparation instead of being labeled whole.
  Larger, deleted and binary files and submodules are shown as plain `git diff -U3` output.
  Lockfiles are listed only. `--full-file-cap N` sets the per-file character cap
  (default `85000`; nonnegative). A selected spec document that the change shows whole
  appears in the requirements as a pointer to that changed file, so its text appears once,
  and the size guard budgets the pointer. A `generic` reviewer needs the structured change:
  its preparation fails visibly when the change part holds hunk headers only, and in the
  panel only that reviewer fails.
  Diff reads are bounded before prompt construction, using numstat first and streaming
  hunk headers for pack mode. Changed paths use NUL-delimited metadata and byte-preserving
  decoding, then literal Git pathspecs. Non-UTF-8 bytes are displayed as escapes and
  percent-encoded in links; NUL bytes are displayed as escapes. Size checks measure the
  final displayed prompt, including its terminating newline. The panel measures the pinned
  role, lens and target rules with the extracted compiler before context preparation.
  Context preparation reserves the largest compiled character count and task separator
  among selected reviewers in each family. The panel retains these compilations in memory
  until it appends context. The panel checks each complete compiled prompt before dispatch.
  Standalone calls with `--reviewers LENS...` also reserve the largest selected lens in the selected reviewer's family.
  Without that option, standalone calls reserve only their selected lens.
  Codex prompts over 800,000 characters fall back to pack for the change, then trim comments,
  issue bodies and legacy spec documents in that order (largest first within each source type).
  Notices identify every trim. If the prompt still exceeds the limit after all trim
  steps, preparation exits nonzero without emitting a prompt; the error names the limit,
  final size and completed trims. The panel reports this as a preparation failure.
  A check round passes `--since REV`, the last reviewed commit or a commit whose tree is the
  earlier change replayed onto the current merge-base. Part 5 then shows `REV..HEAD` in the
  same layout, and the rule report covers the same range. Part 3 names both ranges. Part 4
  keeps only the maintainer comments and the PR description (commit messages of the fix
  without a PR). Linked issues, specifications and test IDs stay in the checkout and are not
  read. Full preparation appends [the check-round rules](../../../prompts/util/check-round.md)
  to every lens's instructions. An unknown `REV` fails preparation.

## Registered specifications

Repositories with `docs/ENTITIES.json` and `docs/DOCUMENTS.json` use the shared
[context selector](../../spec-writing/references/format.md) through the prompt compiler.
Supply `--assignment FILE` to `prompt.py` pack mode, `prepare.py review`, or
`review-panel.sh`. The file uses the format contract's versioned assignment schema and
explicit section selectors. A repository with only one metadata file fails preparation.
For separate reviewer calls, pass the same complete `--reviewers LENS...` list to
`prompt.py` and `prepare.py review`. Both use the panel's reviewer-plan format for
documentation context. Without this option, each call plans only its selected reviewer.
Missing assignments fail in `prompt.py` pack mode, including writer and reader packs.
Without an assignment, `prepare.py review` uses the shared checker's source comparison
to assign every head-registered section changed since the range's merge base.
Existing selection adds tests linked to changed requirements and applicable decisions.
If no registered section changed, it omits the documentation pack and states one line:
`No registered documentation changed in this range.` Explicit assignments keep their behavior outside check rounds.
Invalid sources, unknown selectors and excessive mandatory context
fail before a pack is published. Derived context uses the existing size guards;
an oversized review names its selected sections and fails without truncating documentation.
Use assignment `required_test_reviews` rather than
the legacy `--spec` and `--tests` options for these repositories.

The compiler's manifest contains a `documentation` record with the selector's manifest,
exact UTF-8 byte count, tool-input fingerprints and advisory warnings. The pack includes
the byte report and the selector's complete output. Mandatory context follows
[specification rules](../../../rules/specifications.md#agent-context). It remains present
in every preparer format and is reserved before optional requirement bodies or diffs.
The compiler's optional `--budget-bytes N` bounds the complete pack, including rules and
literal tasks; later `append_tasks` calls enforce that same limit. Supply the available
dispatch budget after reserving response space. Assignment byte limits separately bound
the documentation context. The existing complete-prompt character guard still runs.

Commit-built compilers read the checker, runtime contract, dependency lock, format
contract and writing profile from their House Rules pin. Standalone preparation uses
its tool checkout's matching files. The panel extracts both compiler and preparer from
the pin and selects documentation once before preparing optional task context. It keeps
documentation provenance in the compiled manifest. No live helper fallback is used.
The staging check therefore copies `skills/spec-writing/` alongside the existing tool
set and checks a real documentation fixture and an extracted compiler.

Use the specification tool's supported Python environment as described in its format
contract. When `prepare.py review` runs on Python 3.9 or 3.10 with registered documentation,
set `REVIEW_PYTHON` to that environment's Python executable. The preparer delegates to it;
an unsupported environment fails visibly without installing dependencies. When the shared
checker cannot run (Python below 3.11 without `REVIEW_PYTHON`, `skills/spec-writing` not
staged beside the preparer, or its pinned dependencies missing) and no `--assignment` is
given, the review proceeds without the documentation pack and states why in the prompt;
with `--assignment`, a full review fails visibly. A [check round](../../../docs/specs/spec-system/decisions-and-open-questions.md#check-round-decision) (`--since`)
prepares no documentation context, ignores `--assignment` and needs no checker.
The panel accepts `REVIEW_PYTHON` for that interpreter and
`REVIEW_SPEC_ASSIGNMENT` as an alternative to `--assignment`. These options select
existing tooling and input; they install no dependencies or model configuration.
