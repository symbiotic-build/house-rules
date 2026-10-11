# Review panels

**Default panel: targeted lenses spread over model families.** A full review runs one
reviewer per target lens, in parallel. Several generalists with the same prompt find the
same defects, so a full panel does not run plain generalists. The code targets are:

1. [`correctness-security`](../../../prompts/lenses/correctness-security.md): wrong
   results, invariants, error paths, authorization, secrets, input handling.
2. [`concurrency-restarts`](../../../prompts/lenses/concurrency-restarts.md): concurrent
   callers, crash and restart at each step, retries, replay, durability, bounds.
3. [`spec`](../../../prompts/lenses/spec.md): the change against its issue,
   specification and settled decisions.
4. [`waste`](../../../prompts/lenses/waste.md): simplicity, dead code, duplication,
   speculative mechanisms, scope.

Changes to documents, specifications, rules, prompts or skills add
[`design-spec`](../../../prompts/lenses/design-spec.md), which checks each changed
rule's premise and the reader requirements. A panel limited to three targets uses
[`spec-waste`](../../../prompts/lenses/spec-waste.md) in place of `spec` and `waste`.

Each lens file is a checklist plus an out-of-scope list that names the owning lens, and
includes the [targeted lens](../../../prompts/util/targeted-lens.md) rules: a reviewer
searches only its lens and reports a blocking defect outside it once, marked "Outside
lens:". The triager merges near-duplicates and keeps the owning lens's version.

**Families.** Targets take the configured families in a fixed rotation, so each family
covers different targets: with families A and B, targets 1 and 3 run on one family and
targets 2 and 4 on the other, and `design-spec` continues the rotation. Different
families miss different defects, so a second family finds more than another round from
the same one. When a family cannot run a reviewer (it fails to start, crashes, times out
or returns malformed output), the next family runs the same target in the same round,
and the report names both families. The panel is incomplete only when no family can run
a target; the report then names the target. Merge eligibility for an incomplete panel
follows [pr-ready §4](../SKILL.md#4-merge-and-cleanup).

**Quick review** keeps one generalist (`generalist-a`, `generalist-b`, `generalist-c`
by family), because one reviewer must cover the whole bar.

Reviewer definitions live in [`prompts/lenses/`](../../../prompts/lenses/); the
machine-local config maps each family to a CLI, model and effort (House Rules keeps model
choice out of the repository). Lens family and sandbox defaults live in
`scripts/review-panel.lenses`, one `name family sandbox` per line; the code targets
alternate families there. Lens files contain only prompt text.

## Optional lenses

Add focused reviewers for changes that warrant them, for example
security on access-control code or durability on storage code: `security`, `durability`
and `performance`. They go deeper than the default targets in one area. Lens focus
follows the [shared review bar](../../../prompts/util/review-bar.md). Non-backend changes add
their own reviewers, chosen by the
paths a change touches: `design-spec` for design documents and specifications, `frontend`
for user-interface code, and `ux` for user flows (with screenshots or a preview link when
available).
For design-document and specification reviews, `design-spec` includes the
`naming-readability` criteria. Use the approved panel resources. Give the triager and
document checker the same criteria; accepted fixes are not complete until their examples
pass them. When those criteria change, review the
[acceptance pair](../scripts/testdata/naming-readability/) with one `naming-readability`
reviewer: `unreadable.md` must fail on its value dump and its `xs00` supplier-column
claim. `readable.md` must pass every incident check: its names are readable, the shared
column is mapped for each row kind, the array entries correspond to line rows, and no
value is a compact dump. A clean approval of the whole invented example is not required
(operator decision 2026-10-12, Q15 = 1).

The lead spawns specialists when the operator asks or a finding warrants one. The
[`design`](../../../prompts/lenses/design.md) lens is required for design changes (specs, new
mechanisms or layers), storage/read/search/native paths, a design smell flagged by another
reviewer or the triager, and the daily whole-system audit. It is not required on every PR.

Spec challenges and finding disposition follow the
[shared review bar](../../../prompts/util/review-bar.md). The lead triages each one:
a clarification is proposed in the same PR.
Requirement removals and spec/code drift follow `design-flow` §Design changes.

**Loop:** follow [pr-ready §3](../SKILL.md#3-review-rounds). Merge eligibility is in
[pr-ready §4](../SKILL.md#4-merge-and-cleanup). Track confirmed findings per family;
drop pairings that mostly produce noise.

Launch: `scripts/review-panel.sh <name> <checkout> <base-prompt> [reviewer ...]`.
For a full panel, name the targets: `correctness-security concurrency-restarts spec
waste`, plus `design-spec` for document, rule and prompt changes. Without reviewer
names, the script runs the generalists of the configured families.
