---
status: draft
---

# Design-document template

Use this outline through [design-flow](../../design-flow/SKILL.md) and the
[authoring procedure](../SKILL.md#author-the-document). Replace this guidance and bracketed
prompts before approval. Adjust links when copying. Register the document and its sections
through the [exact source formats](../../../docs/specs/spec-system/formats.md#source-format), which owns declaration syntax.
Apply the [specifications rules](../../../rules/specifications.md) and
[writing profile](../../../rules/writing.md#house-technical-english).

[What question does this system's overview diagram answer? Replace this line with that question.]

```mermaid
flowchart TD
    A["Input"] --> B["System"]
    B --> C["Caller-visible result"]
```

[Add adjacent home links for terms in the diagram.]

<!-- spec-docs:navigation document="document-id" -->
<!-- /spec-docs:navigation -->

[Put purpose, audience, scope and non-goals in the manifest; generate this region immediately
following the authored opening paragraph. State the diagram's question before the diagram.
The map is followed by tour, mechanisms, requirements, decisions, open questions, reference,
then acceptance. Combine adjacent roles only; preserve their internal order.]

<a id="tour"></a>
## Tour

[State the problem this story solves. Carry this same example through mechanisms,
reference and acceptance. Keep action/result steps plain; put exact values below each step
in a `> **Detail — label**` block. Name each deferred explanation in one linked line.]

[Follow a concrete end-to-end scenario. Explain shown values and the reason for each
write, change or retained value. Use labelled procedures for ordered actions. Describe
concurrent branches and synchronization points when applicable. Link declarations through
the format contract.]

<a id="mechanism"></a>
## Proposed mechanism

[Give this mechanism its own chapter. Open every section, including declaration records,
with its purpose. Define a home in one concise sentence before expanding its behavior.]

[Replace this heading and anchor with the entity's name and stable identity. Start with its
meaning and problem, then ordinary behavior. Cover applicable refusal, concurrency,
failure and recovery. Add canonical facts, relationships and requirements through the
format contract. Explain operating conditions and pass conditions for quality bounds.]

### Failure and recovery

[Add applicable declarations through the format contract. Trace retained state, restart,
exits and public error mappings. If the mechanism cannot stop or refuse, explain why.]

<a id="ownership"></a>
## Ownership and integration

[Name owners and affected boundaries. Explain changes to existing components and their
integration. Link exact interfaces and configuration to their reference homes.]

<a id="requirements"></a>
## Requirements

[Explain which observable obligations make the proposed mechanisms implementable.
Add the exact requirement declarations, reciprocal tests and failure-verification links.]

[Allocate permanent, repository-unique `req-<identity>` anchors under the specification
identity rules; do not derive them from the current file or heading.]

<a id="decisions"></a>
## Decisions and alternatives

[Record each choice, authority, evidence and rejected alternatives with reasons. Use the
format contract for decision anchors. Distinguish proposed choices from approved decisions.]

[Use one heading per decision and each field once: **Choice:**, **Authority:**,
**Reason:** and **Rejected alternatives:**. Put all rejected options and their reasons
in that one field, rather than repeating the label.]

<a id="questions"></a>
## Open questions

[Identify unresolved contracts, decision owners and resolution paths. Use None with a
reason when empty. Apply the existing design-flow approval boundary.]

<a id="rollout"></a>
## Rollout

[Explain adoption, replacement and recovery within the approved scope. Follow design-flow
closeout when intent becomes maintained specification.]

<a id="work"></a>
## Work packages

[Split implementation into concrete deliverables with owners, dependencies and gates.]

<a id="reference"></a>
## Reference

[Revisit the tour example in lookup form; link its exact files, diagnostics and selectors.]

[Keep exact schemas, signatures, module layouts, configuration and errors here. Reuse
canonical fact links; retain qualifications and their evidence beside the owning facts.]

<a id="acceptance"></a>
## Acceptance evidence

[Add acceptance declarations through the format contract. Identify method, inputs, pass
condition and evidence, with reciprocal requirement links. Method `test` requires executable
Implementation selectors; inspection, analysis and demonstration link review/run evidence
and omit Implementation. Distinguish planned verification
from observed results. Allocate permanent `test-<identity>` anchors. When linking executable
tests, use the format contract's `Implementation` grammar:
`[tests/test_x.py::test_name](relative/path/to/tests/test_x.py)`; omit the field otherwise.]
