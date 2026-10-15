<a id="decisions"></a>
# Decisions

These choices bind the system's source, value, toolchain and context contracts.
Their rationale records maintenance trade-offs, not benchmark results.

<a id="source-decision"></a>
### Decision: ordinary Markdown and shared declarations

This choice resolves ordinary Markdown and shared declarations for authors and implementers.

**Choice:** Use ordinary Markdown, shared JSON metadata and one Python checker built on `markdown-it-py`.

**Authority:** Operator-approved design dated 2026-10-16.

**Reason:** Preserve ordinary source reading and direct links while deriving navigation, traceability and context from one source set.

**Rejected alternatives:** A JavaScript-based document runtime adds another runtime without removing registry or selection work. Alternate source and publication systems change the authoring contract. Independent requirement stores duplicate writable authority.

The approved comparison considered Bikeshed for definition links, DITA for maps and applicability,
and ReqView, Doorstop and Sphinx-Needs for requirement traceability.
Those tools supply useful models; none removes this system's snapshot and complete-context selection work.
Adopting their publication or independent requirement stores adds an authority this design does not need.
Vale remains optional for unrelated writing; it is not a required checker dependency.
These are design trade-offs, not measured performance claims.

Borrow identity and disambiguation principles from definition-oriented tools.
Borrow map and applicability principles from modular documentation systems.
Borrow reciprocal test links and change review from requirement tools.
Adopt none of their publication machinery.
No separate terminology executable, exporter or second vocabulary authority is required.
An existing installation may remain where it serves other writing needs.

<a id="literal-decision"></a>
### Decision: literal values

This choice resolves literal values for authors and implementers.

**Choice:** “Fact values are literal text, exactly as the spec writes them in the home table cell.”

**Authority:** Operator selection dated 2026-10-16, decision Q178 = 1.

**Reason:** Check direct restatements without introducing product-specific value interpretation.

**Rejected alternatives:** Typed values, unit vocabularies, range validation, expressions and reference-valued facts introduce another value model. Mathematical equivalence does not replace literal equality.

<a id="toolchain-decision"></a>
### Decision: shared pinned toolchain

This choice resolves shared pinned toolchain for authors and implementers.

**Choice:** The shared tool owns exact wheel versions, hashes and supported Python metadata. Repositories pin its House Rules revision.

**Authority:** Operator-approved design dated 2026-10-16.

**Reason:** Keep checker, helper, parser, profile and format contract aligned across local, continuous integration and extracted use.

**Rejected alternatives:** Repository-specific parser pins and checker copies create independent implementations. Source-build and alternate-parser fallbacks hide failed setup.

<a id="context-decision"></a>
### Decision: complete mandatory context

This choice resolves complete mandatory context for authors and implementers.

**Choice:** Derive compulsory registry and selected complete homes from one immutable snapshot. Refuse missing or excessive input before dispatch.

**Authority:** Operator-approved design dated 2026-10-16.

**Reason:** Preserve shared meaning and provenance without recursive link expansion or silent truncation.

**Rejected alternatives:** Optional registry inclusion, automatic traversal of ordinary links and trimmed specification bodies break the mandatory context contract. Persistent mirrors and approval hashes duplicate source authority.

<a id="writing-decision"></a>
### Decision: defined prose profile

This choice resolves defined prose profile for authors and implementers.

**Choice:** Use versioned controlled-language practices, ISO 80000-1 prose numbers and ISO 8601 dates and times. Keep approximate prose checks non-blocking.

**Authority:** Operator-approved design and number-format selection dated 2026-10-16.

**Reason:** Make expectations explicit without claiming full standard conformance or erasing technical qualifications.

**Rejected alternatives:** An approximate percentage does not define enforceable practices. Blocking length limits can encourage loss of meaning.

<a id="open-questions"></a>
## Open questions

This section identifies contract decisions still needed before implementation.
None remain in the approved design.
Implementation acceptance still requires actual checker, navigation, anchor behavior and real-dispatch evidence.
A passing source check does not replace those tests.

