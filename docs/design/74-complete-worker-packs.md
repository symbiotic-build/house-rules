Status: design revised to the operator's decisions of 2026-10-07; implementation pending.

# Complete worker role packs

Design for [#74](https://github.com/symbiotic-sh/house-rules/issues/74), reviewed in
[draft PR #80](https://github.com/symbiotic-sh/house-rules/pull/80).
The operator's recorded answers of 2026-10-07 settle the shared-rule ownership and lane-session choices.
Implementation details below remain proposals where the operator did not specify them.
File paths are repository-relative unless a named repository or tool home qualifies them.

## 1. Result

The five role files serve implementers, fixers, reviewers, triagers and checkers.
Each role file supports two ways of loading House Rules.
A normal lane session loads shared rules and skills through the House Rules index, then receives its role prompt.
A Warden reviewer receives the shared rules in its compiled role prompt.
Both ways use the same rule owners under `rules/`.
No verbatim rule copies are added under `prompts/util/`.

The dispatcher supplies the target repository's rules and the work item's Decisions and Pre-flight sections.
Role instructions identify those supplied parts instead of asking workers to search for rule files.
The checker calls itself CHECKER.
Tests cover shared-rule ownership, both prompt variants and the checker's identity.

## 2. Terms

- **Role pack:** the compiled output of [skills/pr-ready/scripts/prompt.py](../../skills/pr-ready/scripts/prompt.py)
  for a role file under `prompts/roles/`.
- **Shared rule:** a rule every agent needs, with one owner under `rules/`.
  Writing rules, claim labels, Git rules and priority labels are shared rules.
- **Session rule:** a rule for a normal chat session, such as talking to the operator,
  formatting operator questions or running lanes.
  Warden role prompts do not include session-rule files.
- **Open citation:** an instruction to read a rule absent from both the compiled prompt and
  the session's declared House Rules loading path.
- **Repository rules part** and **task part:** the supplied parts defined by the
  [one-step assembly design](https://github.com/symbiotic-sh/house-rules/issues/77).
  The repository rules part holds the target repository's own rules or the line
  “Repository rules: this repository has no rules of its own.”
  The task part holds the work item's Decisions and Pre-flight sections.

## 3. Current behavior verified for this revision

The following observations come from the worktree at commit
`979bc325653c4c2e25367721bd230440d3bd7828`, before this document revision.
Historical lane-load reports from earlier design revisions are not new runtime evidence.

- `FACT` The current compiler reads includes from checkout files, as shown by `path.open()` in
  [skills/pr-ready/scripts/prompt.py at 979bc32](https://github.com/symbiotic-sh/house-rules/blob/979bc325653c4c2e25367721bd230440d3bd7828/skills/pr-ready/scripts/prompt.py).
- `FACT` The implementer prompt forbids loading House Rules in the opening paragraph of
  [prompts/roles/implementer.md at 979bc32](https://github.com/symbiotic-sh/house-rules/blob/979bc325653c4c2e25367721bd230440d3bd7828/prompts/roles/implementer.md).
  `FACT` The implementer prompt also directs the worker to the target repository's instruction file in
  [prompts/roles/implementer.md at 979bc32](https://github.com/symbiotic-sh/house-rules/blob/979bc325653c4c2e25367721bd230440d3bd7828/prompts/roles/implementer.md).
- `FACT` The reviewer prompt permits one targeted test, as stated in
  [prompts/roles/reviewer.md at 979bc32](https://github.com/symbiotic-sh/house-rules/blob/979bc325653c4c2e25367721bd230440d3bd7828/prompts/roles/reviewer.md).
- `FACT` The checker introduces itself as TRIAGER in the first line of
  [prompts/roles/checker.md at 979bc32](https://github.com/symbiotic-sh/house-rules/blob/979bc325653c4c2e25367721bd230440d3bd7828/prompts/roles/checker.md).
- `FACT` The staged-path guard permits only `prompts/` and `skills/pr-ready/`, as shown by
  `test_role_prompts_include_only_files_warden_stages` in
  [skills/pr-ready/scripts/test_prompt.py at 979bc32](https://github.com/symbiotic-sh/house-rules/blob/979bc325653c4c2e25367721bd230440d3bd7828/skills/pr-ready/scripts/test_prompt.py).

`FACT` Priority-label instructions refer readers to the work-tracking skill in
[prompts/util/issue-form.md at 979bc32](https://github.com/symbiotic-sh/house-rules/blob/979bc325653c4c2e25367721bd230440d3bd7828/prompts/util/issue-form.md).
`FACT` The cost-defect definition lives in
[prompts/util/triage-classes.md at 979bc32](https://github.com/symbiotic-sh/house-rules/blob/979bc325653c4c2e25367721bd230440d3bd7828/prompts/util/triage-classes.md).
`ASSESSMENT` Direct includes from shared rule owners remove the need for copied rule fragments and parity tests.

## 4. Design

### 4.1 One owner for shared rules

`DECISION` The operator chose “one place for everything” on 2026-10-07.
Rules every agent needs become separate, clearly organized files under `rules/`.
Sessions and subagents load those files through the House Rules index.
Warden role prompts include those files with `@rule house-rules:rules/<file>.md` lines.

The proposed shared owners are:

- [rules/writing.md](../../rules/writing.md) owns writing rules, including claim labels.
  Warden packs include the claim labels rather than omitting them in favor of a review confidence field.
  A confidence field describes a finding's confidence; a claim label describes the evidence behind a statement.
- The proposed `rules/git.md` owns the Git rules currently in
  [rules/delivery.md §Git](../../rules/delivery.md#git).
  [rules/delivery.md](../../rules/delivery.md) points to that owner instead of repeating its text.
- The proposed `rules/priority-labels.md` owns the P0–P3 definitions.
  [prompts/util/issue-form.md](../../prompts/util/issue-form.md) points to that owner.
  [skills/work-tracking/SKILL.md](../../skills/work-tracking/SKILL.md) and
  [skills/design-flow/SKILL.md](../../skills/design-flow/SKILL.md) point to the same owner instead of defining priority labels again.

Session-only writing and question instructions move to a separate session-rule file.
The proposed name is `rules/session-writing.md`.
The House Rules index loads that file for normal sessions.
Warden role prompts never include that file or lane-running procedures.
The split preserves the shared writing rules and their claim labels in [rules/writing.md](../../rules/writing.md).

The previous proposals for copied Git, writing and priority-label fragments are removed.
No copy registry or copy-parity test is needed.
Shared-rule edits change the canonical owner once.

The index becomes `house-rules/INDEX.md` under the
[smaller-core design](https://github.com/symbiotic-sh/house-rules/issues/73).
The pointer at `house-rules/AGENTS.md` names `house-rules/INDEX.md` and `house-rules/.agents/rules.md`.
The smaller-core design also owns the matching pointer shape in `<target-repository>/AGENTS.md`
and `<codex-home>/AGENTS.md`.
This design uses those pointers; this design does not define a competing loader.

### 4.2 One role file, two loading paths

`DECISION` Lane workers run as normal sessions in the operator's Codex home.
Lane implementers, fixers and reviewers retain the House Rules block, skills and guardian escalation path.
Role prompts add the worker's role instructions to that session.
Role prompts do not forbid those normal sessions from loading House Rules.

The proposed compiler option is `--session`.
The default compile includes shared-rule files for an agent that has no House Rules session loader.
Each default role pack includes all three shared owners from §4.1.
A compile with `--session` omits the shared-rule includes because the session loads their canonical owners.
Both variants read the same role file.
The compiler does not infer the loading path from a tool-home name or filesystem search.
The dispatcher explicitly selects the variant.
The selected loading path is stated in the compiled prompt header.

The option omits only the declared shared-rule includes from §4.1.
The option preserves role instructions, review lenses and role-specific utility fragments.
The compiler rejects a declared shared-rule include whose owner is missing.
The `--list` output reports the files actually expanded for the selected variant.
The revision header still names the commit used for the role prompt.

For the default variant, every rule citation must resolve inside the compiled pack.
For the session variant, a shared-rule citation may resolve through the index's declared loading path.
Neither variant sends the worker to a skill solely to recover missing shared rule text.
The role prompt tells a session worker to use its session rules and the supplied task and repository rules.
The role prompt tells a Warden reviewer that the compiled pack supplies its House Rules.

`DECISION` A lane session's House Rules come from the live checkout through the installed block.
Only the lane role prompt is built from a named commit.
The design does not claim that all lane-session instructions are pinned.
The [one-step assembly design](https://github.com/symbiotic-sh/house-rules/issues/77)
owns reading the named commit from Git objects in any clone.
The one-step assembly design also removes the need for a separate pinned checkout.

### 4.3 Repository and task rules

Role instructions name the repository rules part and the task part before work begins.
The dispatcher writes the work item's Decisions and Pre-flight sections into the task part.
The dispatcher supplies the target repository's own rules through the repository rules part.
No role asks the worker to search the target repository or its parent directories for rule files.

A repository rules part that says the target repository has no rules of its own is complete.
The worker does not report missing rules in that case.
A prompt built with `--no-target` has no repository rules part.
The worker reports that absence once and continues with the supplied task.

A normal session may follow its installed House Rules pointer.
A Warden reviewer uses the supplied pack and does not follow a pointer into a live House Rules checkout.
The previous blanket stay-off fragment is removed from the design.
The [one-step assembly design](https://github.com/symbiotic-sh/house-rules/issues/77)
owns recognizing the pointer shape in `<target-repository>/AGENTS.md` and supplying actual repository rules.
That design must use the pointer shape chosen by the smaller-core design, rather than an obsolete loader template.

### 4.4 Role and fragment changes

[prompts/roles/implementer.md](../../prompts/roles/implementer.md) identifies the loading path and supplied rule parts.
The implementer role cites the canonical Git owner instead of [rules/delivery.md](../../rules/delivery.md).
The implementer role retains its local gate.
The implementer role retains the full local merge gate for repositories without pull-request continuous integration (the no-PR-CI exception).
The implementer role drops the open merge-eligibility pointer because the worker does not merge.
[prompts/util/external-writes.md](../../prompts/util/external-writes.md) continues to reserve external writes for the lead.

[prompts/roles/fixer.md](../../prompts/roles/fixer.md) uses the same Git owner through its implementer include.
The fixer keeps the one-new-commit contract and pushed-history protection.
The fixer inherits shared-rule includes through the implementer role instead of repeating them.
The compiler therefore emits each shared rule once without a new deduplication mechanism.

[prompts/roles/reviewer.md](../../prompts/roles/reviewer.md) includes the shared writing rules for its default compile.
The reviewer role separates Warden's static review from the lane reviewer's existing targeted-test allowance.
The reviewer role preserves the review report contract in [prompts/util/review-report.md](../../prompts/util/review-report.md).

[prompts/roles/triager.md](../../prompts/roles/triager.md) and
[prompts/roles/checker.md](../../prompts/roles/checker.md) include shared writing and priority-label rules for default compiles.
Both roles identify the supplied rule parts.
[prompts/roles/checker.md](../../prompts/roles/checker.md) starts “You are the CHECKER”.
The checker's report format and finding classes remain unchanged.

The cost-defect definition moves from [prompts/util/triage-classes.md](../../prompts/util/triage-classes.md)
to the proposed `prompts/util/cost-defect.md`.
Reviewer, triager and checker role files include that single definition.
[prompts/util/cost-and-design.md](../../prompts/util/cost-and-design.md) points to the new definition owner.
[prompts/util/triage-classes.md](../../prompts/util/triage-classes.md) retains classification and the FIX-NOW exception.

[prompts/util/issue-form.md](../../prompts/util/issue-form.md) replaces its priority-skill pointer with the canonical priority-rule owner.
The issue-form fragment removes the work-tracking source note that supplies no worker instruction.
[prompts/skills/code-canon.md](../../prompts/skills/code-canon.md) removes the design-canon source note after the complete migration rule.
The migration rule itself remains unchanged.

[prompts/README.md](../../prompts/README.md) documents the two loading paths and direct shared-rule includes.
[CHANGELOG-RULES.md](../../CHANGELOG-RULES.md) records the operator's 2026-10-07 choices as provenance.
No rule is copied into [prompts/README.md](../../prompts/README.md) or [CHANGELOG-RULES.md](../../CHANGELOG-RULES.md).

### 4.5 Warden's boundary

`DECISION` Warden reviewers use a read-only copy of the pull request.
Warden reviewers have no network access except to the model provider.
Warden reviewers run no builds or tests.
Continuous integration runs builds and tests.
The Warden service posts the review on GitHub.
The lane scripts on the Mac read that review and start the fixer locally.
Warden's posting responsibility does not grant the reviewer agent permission to make external writes.

The reviewer role's current one-targeted-test allowance does not apply inside Warden.
The default compiled reviewer prompt states Warden's restrictions.
The session variant preserves the lane reviewer's existing allowance.
The session variant does not turn a Warden reviewer into a lane worker.

### 4.6 Implementation tests

The implementation adds targeted regressions to
[skills/pr-ready/scripts/test_prompt.py](../../skills/pr-ready/scripts/test_prompt.py):

- Compile all five roles in both variants and compile each review lens with the reviewer.
  Assert that default packs include each required shared owner exactly once.
  Assert that session packs omit those includes while preserving role and lens instructions.
- Check default-pack citations against expanded files.
  Check session-pack shared citations against the index's declared shared owners.
  Fail on undeclared or missing rule targets.
- Assert that writing rules and claim labels have one owner.
  Assert that Git and priority-label rules have one owner each.
  Assert that Warden packs include no session-only writing or lane-running file.
- Assert that all roles identify the supplied task and repository rules without asking for a rule-file search.
  Assert that the checker starts as CHECKER and does not call itself TRIAGER.
- Assert that Warden reviewer text forbids builds and tests.
  Assert that the session reviewer retains its targeted-test limit.
  Assert that implementer and fixer gate text preserves the no-PR-CI exception.

`test_role_prompts_include_only_files_warden_stages` widens its allowed roots to `rules/`
once Warden's staging change is deployed.
The operator's decision record identifies that change as
[warden#238](https://github.com/symbiotic-sh/warden/pull/238), merged as `9f1568b`.
This revision has not verified Warden's deployment.
The guard does not allow arbitrary repository paths.
The former copy-parity test proposal is deleted because the design adds no copied rule text.

The implementation updates the existing Git-reference, triage-definition and repository-rule tests for the new owners.
The definition test checks that reviewer, triager and checker receive the same cost-defect text once.
The implementation retains requirement-preservation checks and the work-item reading requirement.

## 5. Rejected alternatives

- **Verbatim shared-rule copies under `prompts/util/`:** rejected because the operator chose one canonical home under `rules/`.
- **Shared-rule owners under `prompts/util/`:** rejected because the operator chose shared instruction files under `rules/`.
- **The whole session foundation in every role pack:** rejected because Warden must receive shared rules without session-only instructions.
- **An isolated lane-worker home by default:** rejected because the operator chose normal Codex sessions with House Rules and skills.
- **One blanket loading ban for every worker:** rejected because lane sessions must load House Rules while Warden uses a complete supplied pack.

## 6. Implementation scope

The proposed new shared-rule files are `rules/git.md` and `rules/priority-labels.md`.
The proposed session-only writing file is `rules/session-writing.md`.
The proposed role-specific fragment is `prompts/util/cost-defect.md`.
The shared writing owner remains [rules/writing.md](../../rules/writing.md).
The Git split changes [rules/delivery.md](../../rules/delivery.md).
The shared-rule split updates index loading and existing rule consumers together.
The smaller-core design owns the index rename and installed pointer changes.

The role changes cover all five files under `prompts/roles/`.
The utility changes cover [prompts/util/cost-and-design.md](../../prompts/util/cost-and-design.md),
[prompts/util/triage-classes.md](../../prompts/util/triage-classes.md) and
[prompts/util/issue-form.md](../../prompts/util/issue-form.md).
The source-note change touches [prompts/skills/code-canon.md](../../prompts/skills/code-canon.md).
Documentation changes cover [prompts/README.md](../../prompts/README.md) and
[CHANGELOG-RULES.md](../../CHANGELOG-RULES.md).
Compiler integration and targeted tests touch [skills/pr-ready/scripts/prompt.py](../../skills/pr-ready/scripts/prompt.py)
and [skills/pr-ready/scripts/test_prompt.py](../../skills/pr-ready/scripts/test_prompt.py).
The one-step assembly design owns named-commit building and the caller's variant selection.

The prior copied-fragment size estimates no longer describe this design.
The implementation reports bytes for both compiled variants from the actual compiler output.
The implementation also reports the shared rules loaded by normal sessions.
Those measurements must distinguish the live session rules from the named-commit role prompt.
The design adds no runtime store, index, cache, queue or mirror.

## 7. Verification

These checks are implementation acceptance criteria, not completed results of this document revision.

**Text checks:** run the targeted tests from §4.6 during local implementation.
Continuous integration runs the complete declared suite on the pushed implementation.
The local document-revision gate is [scripts/test_sync.py](../../scripts/test_sync.py).

**Lane canary:** run one implementer, three reviewers, one triager, one fixer and one checker on a small seeded change in normal Codex sessions.
Use the named-commit compiler from the one-step assembly design.
Use the session variant of each role prompt.
Use a disposable fixture for the live session rule checkout; do not edit the operator's installed rules.
Give the fixture's live shared rules a distinct marker from the role-prompt commit.

The lane canary passes when tool logs show the expected session loading path and the named-commit role prompt.
Live House Rules reads are expected for normal sessions.
The lane canary fails if the role prompt contains text from unrelated checkout edits or another branch.
The lane canary also fails if workers search for missing repository rule files.
The checker must call itself CHECKER.
Reviewer, triager and checker outputs must preserve their `VERDICT:` first line.
Implementer and fixer outputs must preserve their final-message contract.

Run triager and checker with a repository rules part that says the target repository has no rules of its own.
Those workers must not report missing rules.
Run a triager with `--no-target`.
That triager must report the absent repository rules part once without searching for rule files.
The fixture pointer at `<test-repository>/AGENTS.md` must use the smaller-core design's chosen pointer shape.

**Warden canary:** use the default role variants after Warden deploys staging for `rules/`.
All required includes must resolve from the qualified commit.
Tool logs must show no reads from the live House Rules checkout and no builds or tests.
The reviewer must retain the read-only and network restrictions from §4.5.
The Warden service's review must be readable by the Mac lane scripts for a local fix round.
Self-reports alone do not prove the loading or isolation behavior.

## 8. Rollout and dependencies

The prior rollout based on temporary copies is removed.
Deployment follows these dependencies:

1. Confirm that Warden has deployed the staging change for `rules/` before enabling direct shared-rule includes there.
   Widen the staged-path guard only with that deployment evidence.
2. Land the shared-rule owners and update their consumers together.
   Coordinate the shared-rule loading list with the smaller-core design's index changes.
   Do not introduce a temporary copied-rule path.
3. Integrate the two compiler variants with the one-step assembly design's named-commit builder.
   The lane runner selects the session variant.
   Warden selects the default complete variant.
4. Run the lane and Warden canaries from §7 before moving the callers to the new role-prompt commit.
   The live lane-session checkout remains a separate source of session instructions.

The [one-step assembly design](https://github.com/symbiotic-sh/house-rules/issues/77)
owns drafting its matching Warden compiler change after the lane-runner test passes and with operator approval.
This design does not create a second Warden rollout or assume that staging deployment proves compiler deployment.

## 9. Interfaces with the other designs

- **[Smaller always-loaded core](https://github.com/symbiotic-sh/house-rules/issues/73):** owns `house-rules/INDEX.md`,
  the pointer files and its own canary.
  This design supplies the shared-rule owners that its index loads.
- **[Specialist subagents](https://github.com/symbiotic-sh/house-rules/issues/75):** owns specialist execution,
  including separate Claude safe-mode processes, skill-text injection and its Model Context Protocol test and fallback.
  Specialist packs use the shared owners without assuming that safe mode loads session skills.
- **[Review skill](https://github.com/symbiotic-sh/house-rules/issues/76):** owns the `change-review` skill,
  the fixed review format, the operator question format and one reviewer by default.
  This design supplies the reviewer role's shared writing rules and claim labels.
- **[One-step assembly](https://github.com/symbiotic-sh/house-rules/issues/77):** owns Git-object prompt building from a named commit,
  revision headers, repository rules assembly and caller integration for the two loading paths.
  Lane review panels use that builder rather than scripts taken from the live checkout.

## 10. Decisions

Each item records the operator's choice on 2026-10-07.

1. **2026-10-07 — One shared home:** writing rules with claim labels, Git rules and priority labels live in separate files under `rules/`.
   Rule text is not copied under `prompts/util/`.
2. **2026-10-07 — Load shared rules for every agent:** sessions and subagents load shared rules through the House Rules index.
   Warden role prompts include the canonical files with `@rule house-rules:rules/<file>.md` lines.
3. **2026-10-07 — Keep session rules separate:** instructions for talking to the operator, formatting questions and running lanes stay in their own files.
   Warden role prompts do not include those files.
4. **2026-10-07 — Normal lane sessions:** lane workers use the operator's normal Codex home with the House Rules block, skills and guardian escalation path.
   One role file serves lane sessions and Warden; lane prompts omit shared-rule includes already supplied by the session.
5. **2026-10-07 — State the pin limit:** lane-session rules come from the live House Rules checkout.
   Only the role prompt is built from a named commit, as defined by the one-step assembly design.
6. **2026-10-07 — Keep Warden read-only:** Warden reviewers use a read-only pull-request copy, contact only the model provider and run no builds or tests.
   Continuous integration runs builds and tests; Warden posts reviews for the Mac lane scripts to read and fix locally.
7. **2026-10-07 — Stage canonical rules:** Warden stages `rules/` from the qualified commit through the change identified as `9f1568b`.
   The House Rules staged-path guard widens to `rules/` once that change is deployed.

Decisions owned by other designs remain the short cross-references in §9.

## 11. Open points

- **Warden staging deployment:** close this point with deployment evidence for `9f1568b`
  and a canary that resolves the direct shared-rule includes from the qualified commit.
  The recorded merge alone does not establish deployment.

The recorded operator answers leave no unanswered operator choice for this design.
