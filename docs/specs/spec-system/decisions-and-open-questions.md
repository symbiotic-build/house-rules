<a id="decisions"></a>
# Decisions and open questions

These choices explain why the system keeps authored Markdown and shared metadata authoritative. They bind implementation and review; the alternatives record design trade-offs rather than measured performance. The bounded-batch example uses the chosen declarations to express capacity `2`, check a wrong displayed `3` and prepare `example#main`.

<a id="settled-choices"></a>
## Settled choices and alternatives

The following records preserve the decisions that determine source authority, checking and agent input. Each choice has its own heading so its authority and rejected alternatives remain unambiguous.

<a id="source-decision"></a>
### Decision: Markdown source with shared metadata

This choice keeps a contract readable in its authored form while supporting derived navigation and checks.

**Choice:** Author ordinary Markdown with pipe tables, shared JSON metadata and one Python checker using `markdown-it-py`.

**Authority:** Operator-approved source-format decision dated 2026-10-16.

**Reason:** Markdown homes hold explanations and values. Metadata connects their identities and reading order without requiring another authoring environment.

**Rejected alternatives:** Markdoc adds a JavaScript runtime while leaving registry and context selection work. AsciiDoc and Antora change the source format. MyST, Sphinx and Sphinx-Needs change the authoring and publication contract. A separate requirement store adds writable authority that these declarations do not need.

The design borrows definition identity and disambiguation from Bikeshed, and maps and reuse principles from DITA. It borrows explicit applicability from independently identified information modules. These ideas inform source organization without adopting their publication machinery.

Doorstop and StrictDoc supply the design's named comparison for reciprocal requirement–test links and change-impact review. This system derives those relationships from Markdown and Git snapshots. The choice does not assert that either compared tool requires exclusively non-Markdown authoring. It rejects adding another requirement store for this system's needs.

Vale is not a required dependency. An existing installation can serve other writing needs, but it does not replace home resolution, literal comparison or snapshot selection. The design adds no terminology exporter or second vocabulary authority.

<a id="literal-decision"></a>
### Decision: literal fact values

This choice makes a linked restatement checkable without interpreting a product's value model.

**Choice:** Treat a fact's Value cell as literal text. Normalize only surrounding space and the declared digit-group separators.

**Authority:** Operator selection of literal fact values, dated 2026-10-16.

**Reason:** The batch's capacity link must display the declared `2`; a resolving link displaying `3` is still wrong.

**Rejected alternatives:** Typed facts, unit conversion, expressions, ranges and reference-valued facts introduce semantic evaluation. Mathematical equivalence cannot substitute for matching the authored literal.

<a id="toolchain-decision"></a>
### Decision: one pinned shared tool

This choice keeps local, automated and extracted use on the same parsing contract.

**Choice:** Let the shared tool own the runtime range, exact dependency versions and wheel hashes. Consumers select its House Rules revision.

**Authority:** Operator-approved design dated 2026-10-16.

**Reason:** The helper, profile and format contract must agree when the [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) prepares documentation input.

**Rejected alternatives:** Consumer-specific parser versions and checker copies create independent implementations. Alternate-parser and source-build fallbacks conceal failed setup instead of repairing the owning environment.

<a id="context-decision"></a>
### Decision: complete mandatory input

This choice gives agents shared meanings without following every source link recursively.

**Choice:** Include the complete repository registry and selected complete explanations from one snapshot. Refuse invalid, stale or excessive mandatory input before dispatch.

**Authority:** Operator-approved context decision and subsequent stale-assignment regeneration ruling, dated 2026-10-16.

**Reason:** `example#main` must contain the batcher's refusal and recovery with its capacity, rather than a trimmed fragment that changes the reader's understanding.

**Rejected alternatives:** Optional registry inclusion, recursive traversal of ordinary home links and truncated source bodies break completeness or selection boundaries. A verified rebase is not available. Persistent mirrors and approval hashes duplicate existing authority.

<a id="writing-decision"></a>
### Decision: explicit advisory prose targets

This choice supports readable explanations while retaining necessary technical qualifications.

**Choice:** Use the versioned profile in the shared writing rules. Apply ISO 80000-1 prose number formatting and ISO 8601 dates and times; keep approximate prose checks advisory.

**Authority:** Operator-approved design and number-format selection dated 2026-10-16.

**Reason:** Named practices and warning targets can guide review without pretending that a counter proves readability or standards conformance.

**Rejected alternatives:** An approximate conformance percentage leaves practices undefined. Blocking sentence limits can reward deletion of conditions, uncertainty or consequences.

<a id="delivery-decision"></a>
### Decision: qualify the branch before merge

This choice establishes real use before adopting changes to the shared instruction system.

**Choice:** Run normal authoring and review paths with an exact branch revision before merge. Keep renderer acceptance in its owning repository.

**Authority:** Operator decision to validate branch-pinned real use before merge, dated 2026-10-16.

**Reason:** A branch override can exercise new rules and tools without merging them merely to create a test environment.

**Rejected alternatives:** Merging before qualification makes adoption part of the experiment. Hand-repairing generated packs hides defects in their source owners. Passing House Rules checks cannot establish another tool's display behavior.

<a id="open-questions"></a>
## Open questions

No implementation choice remains open in this contract. The settled choices above govern source authority and tool behavior; the [source formats](source-formats.md#source-format) define current encodings. The [writing and review workflow](writing-and-review-workflow.md#authoring-and-review) explains how to qualify their use.

Acceptance still needs actual run evidence. A declared selector, linked review lens or planned reader procedure is not a completed result. If review finds a source disagreement beyond the recorded rulings, the lead records its evidence and responsible decision owner before accepting a resolution.
