<a id="decisions"></a>
# Decisions and open questions

These choices explain why the system keeps authored Markdown and shared metadata authoritative. They bind implementation and review; the alternatives record design trade-offs rather than measured performance.

<a id="settled-choices"></a>
## Settled choices and alternatives

The following records preserve the decisions that determine source authority, checking and agent input. Each choice has its own heading so its authority and rejected alternatives remain unambiguous.

<a id="source-decision"></a>
### Decision: Markdown source with shared metadata


**Choice:** Author ordinary Markdown with pipe tables, shared JSON metadata and one Python checker using `markdown-it-py`.

**Authority:** Operator-approved source-format decision dated 2026-10-16.

**Reason:** Markdown homes hold explanations and values. Metadata connects their identities and reading order without requiring another authoring environment.

**Rejected alternatives:** Markdoc adds a JavaScript runtime while leaving registry and context selection work. AsciiDoc and Antora change the source format. MyST, Sphinx and Sphinx-Needs change the authoring and publication contract. A separate requirement store adds writable authority that these declarations do not need.

<a id="literal-decision"></a>
### Decision: literal fact values


**Choice:** Treat a fact's Value cell as literal text. Normalize only surrounding space and the declared digit-group separators.

**Authority:** Operator selection of literal fact values, dated 2026-10-16.

**Reason:** The batch's capacity link must display the declared `2`; a resolving link displaying `3` is still wrong.

**Rejected alternatives:** Typed facts, unit conversion, expressions, ranges and reference-valued facts introduce semantic evaluation. Mathematical equivalence cannot substitute for matching the authored literal.

<a id="toolchain-decision"></a>
### Decision: one pinned shared tool


**Choice:** Let the shared tool own the runtime range, exact dependency versions and wheel hashes. Consumers select its House Rules revision.

**Authority:** Operator-approved design dated 2026-10-16.

**Reason:** The helper, profile and format contract must agree when the [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) prepares documentation input.

**Rejected alternatives:** Consumer-specific parser versions and checker copies create independent implementations. Alternate-parser and source-build fallbacks conceal failed setup instead of repairing the owning environment.

<a id="context-decision"></a>
### Decision: complete mandatory input


**Choice:** Include the complete repository registry and selected complete explanations from one snapshot. Refuse invalid, stale or excessive mandatory input before dispatch.

**Authority:** Operator-approved context decision and subsequent stale-assignment regeneration ruling, dated 2026-10-16.

**Reason:** `example#main` must contain the batcher's refusal and recovery with its capacity, rather than a trimmed fragment that changes the reader's understanding.

**Rejected alternatives:** Optional registry inclusion, recursive traversal of ordinary home links and truncated source bodies break completeness or selection boundaries. Changing an old pack’s baseline without rebuilding it cannot establish that its dependencies still match the new snapshot; regenerate the pack instead. Persistent mirrors and approval hashes duplicate existing authority.

<a id="writing-decision"></a>
### Decision: explicit advisory prose targets


**Choice:** Use the versioned profile in the shared writing rules. Group prose digits in threes with spaces and use a decimal dot, for example `1 234.5` (ISO 80000-1). Write dates as `2026-10-16`, times as `14:05 UTC`, and timestamps as `2026-10-16 14:05 UTC` (ISO 8601). Keep approximate prose checks advisory.

**Authority:** Operator-approved design and number-format selection dated 2026-10-16.

**Reason:** Named practices and warning targets can guide review without pretending that a counter proves readability or standards conformance.

**Rejected alternatives:** An approximate conformance percentage leaves practices undefined. Blocking sentence limits can reward deletion of conditions, uncertainty or consequences.

<a id="delivery-decision"></a>
### Decision: qualify the branch before merge


**Choice:** Run normal authoring and review paths with an exact branch revision before merge. Keep renderer acceptance in its owning repository.

**Authority:** Operator decision to run normal authoring and review at the exact candidate commit before merge, dated 2026-10-16.

**Reason:** A branch override can exercise new rules and tools without merging them merely to create a test environment.

**Rejected alternatives:** Merging before qualification makes adoption part of the experiment. Hand-repairing generated packs hides defects in their source owners. Passing House Rules checks cannot establish another tool's display behavior.

<a id="open-questions"></a>
## Open questions

No implementation choice remains open in this contract. The settled choices above govern source authority and tool behavior; the [source formats](source-formats.md#source-format) define current encodings. The [writing and review workflow](writing-and-review-workflow.md#authoring-and-review) explains how to qualify their use.

Acceptance follows the [evidence distinction](acceptance-evidence.md#acceptance). If review finds a source disagreement beyond the recorded rulings, the lead records its evidence and responsible decision owner before accepting a resolution.
