# Review panels

**Default panel:** one generalist reviewer per model family, in parallel: family A and
family B, plus family C when available. Different families miss different defects, so a
second family finds more than another round from the same one. Reviewer definitions live in
[`prompts/lenses/`](../../../prompts/lenses/); the machine-local config maps each family to a CLI, model
and effort (House Rules keeps model choice out of the repository). Lens family and sandbox
defaults live in `scripts/review-panel.lenses`, one `name family sandbox` per line;
lens files contain only prompt text.

## Optional lenses

Add focused reviewers for changes that warrant them, for example
security on access-control code or durability on storage code: `security`, `durability`,
`performance`, `spec` (a requirement-by-requirement traceability pass) and `waste`. Lens focus
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
claim, and `readable.md` must pass.

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

Launch: `scripts/review-panel.sh <name> <checkout> <base-prompt> [reviewer ...]`
(default reviewers: the generalists of the configured families).
