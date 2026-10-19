---
name: pr-ready
description: The repeated change loop — local fast gate, push, CI as the full gate, review rounds, merge and cleanup. Use before pushing or marking a PR ready, when writing or running a review round (human or agent reviewer), when fixing review findings, and when merging a PR.
license: MIT
---

# PR Ready

One loop per change: local gate → push → CI → review round → fix → … → merge → cleanup.
Verification invariant: rules/delivery.md §Verification. Local work follows
[`prompts/roles/implementer.md`](../../prompts/roles/implementer.md); reviewer test scope is in
[`prompts/roles/reviewer.md`](../../prompts/roles/reviewer.md).

## 1. Local gate (implementer or fixer)

- Dispatch each worker through one named-commit pack call:
  `/usr/bin/python3 skills/pr-ready/scripts/prompt.py --rev <commit> --repo <clone> --role <role> --target <checkout> --task <task-file> --task-source <logical-id> --out <new-run-directory>`.
  The task file contains the work item's Decisions and Pre-flight sections.
  Use `--no-target` only when there is no target. Add lenses and extra rules through
  `--lens` and `--include`; add resume notes through another `--task`.
  Use `--session` for normal lane sessions that load the live foundation.
  Retain the complete pack and manifest and send the pack bytes unchanged.
  The [compiler contract](../../prompts/README.md#one-call-pack-assembly) covers
  Git object reads, matching compiler extraction, repository loaders and failures.
- For document work, identify the reader and document kind in the task. Include
  `skills/spec-writing/SKILL.md` for design/specification authors only. Give reviewers,
  triagers and document checkers `--lens naming-readability` (or `design-spec`, which
  includes it); the review service stages only `prompts/`, `rules/` and `skills/pr-ready/`.
  Include the applicable writing rules through the selected loading path. Supply one
  representative approved passage when available. Make the task's acceptance criterion
  the naming and reader requirements, not a count of definitions, headings or retained
  expressions. Exact schema names in an input document are not a naming exception.
  Give document triagers the same acceptance requirements as reviewers. For a document
  readability repair, give its checker the complete rewritten section and worked example,
  so it can verify meaning and newly added explanations as well as preservation.
  Keep acceptance checks inside the authorized document scope and review resources.

- Prompts are lists of whole files from the [prompt collection](../../prompts/README.md).
  Expand an implementer, fixer, reviewer, triager or checker role with
  `/usr/bin/python3 skills/pr-ready/scripts/prompt.py prompts/roles/<role>.md`
  from a pinned checkout, or pass a list of `@rule house-rules:<path>` lines on stdin.
  Includes are recursive whole files; missing files, paths outside the checkout,
  section references and cycles fail the build. `--list` prints included paths.
  Dispatchers generate prompts from these source files; never maintain local copies.
- In a task part, list settled decisions with their source. List a decision that new
  evidence reopened (rules/writing.md §Claim labels) separately as open, with that evidence.
  Never override the [triage classes](../../prompts/util/triage-classes.md) for findings
  against decisions. Give a design review the measured consumer counts its premise check
  needs, or a first step that collects them.
- Run `scripts/prepare.py fix <checkout> --reviews <files...>` before fixing, or
  `scripts/prepare.py pr <checkout>` before preparing a PR (Python 3.9+). It fetches the base and
  checks ownership with `upstream-contribution/scripts/repo-ownership.sh`. For external
  repositories or unknown ownership it reports the ownership status and how many commits
  the branch is behind, and leaves the update method to the operator; `--update` forces
  a base merge. Only confirmed owned repositories merge by default, never rebase, and
  stop on conflicts. It prints
  context and changed files grouped as source/test/docs, pointing to the repository's
  declared gates; it neither derives nor runs stack-specific test commands. `--base REF`
  overrides remote default detection. An explicit local base requires no fetch. Failed remote discovery
  uses the cached remote-tracking default branch; a failed fetch keeps the selected
  cached base. Both report stale context and skip merging even with `--update`.
  `--no-fetch --base REF` uses an already resolved base without fetching and still merges
  on owned repositories or with `--update`. Git and gh run non-interactively.
- Use the repository's declared gates (its `AGENTS.md` and the rules file it points to,
  or the CI workflow when none are declared) in CI's build profile. Rust: skill `rust-canon` §Gates.
- Apply the local test scope in [`prompts/roles/implementer.md`](../../prompts/roles/implementer.md).
  Widen targeted checks to dependents when a shared type, trait, schema or public contract
  changes; toolchain, lockfile and build-script matrices belong to CI.
- Report the exact commands, filters and pass/fail counts.

- Follow rules/delivery.md §Verification for iteration gates and renewal of invalidated verification evidence.

<a id="push-and-ci"></a>
## 2. Push and CI

- Write the PR body, review comments, replies and commit messages in the forms of skill
  `operator-writing` §GitHub text. A review-round commit states each fixed finding as
  before → now and cites no file outside the repository.
- Open PRs as drafts (`gh pr create --draft`) while work is in progress; mark them ready
  (`gh pr ready`) only once the local gate passes. Ready means "review this": a server-side
  review gate reviews each new head of a ready PR and ignores drafts. Draft status does
  not change the complete-fix push rule in rules/git.md.
- Push; wait for CI to finish green on the exact head commit.
- On a CI failure, reproduce only the failing tests locally. Before attributing a failure
  to the change, compare it against the default branch under the same conditions.

- Follow rules/delivery.md §Verification for CI review, failure routing and the expected-long-run exception.

## 3. Review rounds

**Where reviews run.** If the repository has a server-side review gate (a review app
running in CI), pushing triggers the review. Otherwise the agent runs the panel locally.
Required reviews are defined only in §4. Adversarial verification scope and the single-pass
rule: rules/delivery.md §Parallel work.
External repositories always get local review rounds (skill `upstream-contribution`).

**Review bar.** [`prompts/util/review-bar.md`](../../prompts/util/review-bar.md) holds the bar;
the [reviewer role](../../prompts/roles/reviewer.md) includes the review
canon: correctness and security, cost and design, code quality, waste as a blocking class, and
the House Rules a reviewer enforces. Default reviewer packs include the shared rules.
Packs compiled with `--session` receive shared rules through the live House Rules index.
Specialist dispatch follows
[Optional lenses](references/review-lenses.md#optional-lenses).

- Give the reviewer the spec sections, previous review and round task as needed
  ([review template](references/review-prompt.md)). `scripts/review-panel.sh` builds each
  reviewer's prompt with `scripts/prepare.py review`. The structured format places shared
  review rules, PR and issue context and requirements before the change, which shows each
  changed text file whole with numbered lines up to a size cap. Lens instructions come last
  to preserve a shared prefix.
  Pack and diff retain their existing layouts. A reviewer without a verdict, a preparation
  failure or a CLI failure fails the panel. The panel requires `--rev <commit>`
  or `REVIEW_HOUSE_RULES_REV`; `--repo <clone>` or `REVIEW_HOUSE_RULES_REPO`
  selects the clone. It extracts the matching compiler and lens configuration with
  replacement refs disabled. `prepare.py review --context-only` emits task context;
  the compiler assembles role, lens, target rules and that task in one pack call.
  `--session` selects the normal-session loading path. Exact behaviour, limits and safety rules:
  [preparer reference](references/preparer.md).
- **Quick review** (`scripts/quick-review.sh`): one reviewer from family a, for small,
  well-understood changes: fix-diff check-backs after a full round, docs and configuration
  edits, CI and build fixes, small refactors. Never for a first review of a feature, access
  control, confidentiality, durability, storage, security-sensitive paths or new mechanisms.
  It refuses changes above 300 changed lines by default; a blocker or spec issue it raises
  sends the change back to the full panel after the fix. For an eligible change its approval
  completes review under §4; check-backs verify fixes under that section's merge
  exception.
- Run the targeted panel: one reviewer per target lens, spread over the model families,
  adding specialist lenses where warranted ([review panels](references/review-lenses.md)).
  Except for eligible quick reviews, the
  full panel reviews the first and final heads, and fixes to shared mechanisms or large
  diffs, subject to the own-blocker merge exception in §4; check-backs in between may be
  quick reviews. The project may require two clean rounds for security-critical changes.
  Test scope:
  [`prompts/roles/reviewer.md`](../../prompts/roles/reviewer.md).
- The fixer follows the [fixer role](../../prompts/roles/fixer.md) for accepted scope and
  the [worker pack](../../prompts/roles/implementer.md) for implementation, with commit
  cadence from rules/git.md.
  The next review names that commit or those commits and marks each prior blocker RESOLVED
  or NOT. A fixer never approves its own fix.
- Finding disposition follows the [shared review bar](../../prompts/util/review-bar.md).
  Unsettled implementation choices follow the [worker pack](../../prompts/roles/implementer.md).
- **Hosted review bots.** Review threads from bots the host runs on the PR (for example
  GitHub Copilot) are reviewer input for the next fix round, judged by the same bar. Before
  merging, the lead replies to each with the fix or the reason it is not one, and resolves it.
- **Review reassessment.** After three fix rounds on one PR or design record, stop for a
  lead decision to simplify or split; first rerun the
  [premise check](../../prompts/util/premise-check.md) and record why; at most three
  fix rounds run per PR. Follow-ups are
  tracked before merging and never hold
  the merge; finding disposition follows the
  [shared review bar](../../prompts/util/review-bar.md).
  A slower reviewer's findings on an older head feed the next fix round; its fixer
  never pushes onto a head that moved. Merge eligibility has one home: §4.
- **Repeat defects.** Use the repair order in
  [No fortification](../../prompts/skills/no-fortification.md); the general third-occurrence checkpoint
  remains rules/outcome.md §Three-occurrence reassessment.
- **No idle gaps.** A fix run pushes and starts its review in the same job; a review that
  needs a fix starts the fix in the same job. The lead intervenes only for decisions.
- **Conflicting findings: analyze before fixing.** When reviewers' findings pull against
  each other (fixing one reopens or contradicts another), stop patching. Dispatch a
  read-only analyzer with both reports, the code, the spec and the settled decisions. It
  starts from first principles: what the mechanism is for, what the spec actually
  requires (quoted), and which findings are requirements versus a reviewer's assumption.
  Only then does it compare mechanisms and recommend one. The next fix implements that
  recommendation; a genuine spec gap goes to the operator.
- **One fixer per branch; every review feeds it.** A branch never has two fixers at once
  (parallel fixers duplicate builds and conflict). Every finished review, from any
  reviewer at any speed, joins the branch's fix queue. When the fixer is idle, the
  queued reports start the next fix round at once (a follow-up trigger). A report that
  arrives while the fixer is still early in its round (before its first full build)
  restarts that round from its working tree with every report; later ones wait for the
  next round. The fixer verifies each queued finding against the
  current head and reports which no longer hold.
- **Slow reviewers never block.** The fix round starts as soon as the reports in hand
  need one; a slower reviewer keeps reviewing its snapshot in the background, and its
  report becomes queued input. At the final head the slow reviewer still reviews, but
  only the diff since its last reviewed head. Merge eligibility: §4.

- **Current base before the final round.** Merge the default branch into the PR branch
  before its final review, so the reviewed head is what CI and the merge see.

## 4. Merge and cleanup

- **Required reviews** are the configured server-side review (Warden where used) when
  it covers the deliverable; otherwise, the lane's review. Additional reviews explicitly
  required by the project's approved review plan remain required, including both the lane
  and server-side reviews for the recorded comparison trial.
- Merge only when the required reviews approve the exact head with no Blocking items;
  an earlier approved head whose later commits only fix those reviewers' own blockers
  and pass a quick check-back may merge. CI must be green on the final head, and the
  closeout checklist must hold (`design-flow` §6).
  The no-PR-CI exception follows the [worker pack](../../prompts/roles/implementer.md).
  When a required reviewer model family is unavailable, the operator decides how to
  proceed; the missed review runs after that family returns. Pin the head
  (`gh pr merge <n> --match-head-commit <sha>`) in the repository's merge style. No
  auto-merge unless the operator asked.
- **Rule changes travel in the merge commit (House Rules repository).** A House Rules pull
  request that changes rule text merges with its Rule changes section as the merge commit
  body. Run the steps in order and stop at the first failure:
  1. **Fetch the body:** `gh pr view <n> --json body --jq .body > body.md`.
  2. **Extract the section:** `python3 skills/pr-ready/scripts/rules_changelog.py --section < body.md > section.md`.
     It exits 1 when the body has no Rule changes section.
  3. **Merge:** `gh pr merge <n> --merge --match-head-commit <sha> --body-file section.md`.

  [rules_changelog.py](scripts/rules_changelog.py) prints the rules changelog from those merge
  commits; `--check` lists rule-changing merges that lack the section. Other repositories keep
  their own merge style.
- Then update the tracking item, delete the branch, and remove the lane (skill
  `agent-lanes` §Lane cleanup).

- When all reviewer families approve, CI passes, and deployment is documented routine procedure, finish landing.
- Merge within rules/git.md delivery authority, deploy, verify after deployment, then report changes.
- Do not hand routine landing steps to the operator.
