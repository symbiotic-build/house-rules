---
status: draft
---

# Design-document template

Use this outline through [design-flow](../../design-flow/SKILL.md) and the
[authoring procedure](../SKILL.md#author-the-document). Replace this guidance and bracketed
prompts before approval. Adjust links when copying. Register the document and its sections
through the [format contract](../references/format.md), which owns declaration syntax.
Apply the [specifications rules](../../../rules/specifications.md) and
[writing profile](../../../rules/writing.md#house-technical-english).

<a id="purpose"></a>
## Purpose and audience

[State the requested outcome, intended reader and prerequisites. Lead with the proposed
result and explain the problem it addresses.]

<a id="scope"></a>
## Scope and non-goals

[Name covered behavior and excluded work.]

<a id="evidence"></a>
## Current evidence and constraints

[Show current behavior and consumers from primary evidence. Separate observations,
assumptions, designed costs and measurements using the writing rules' claim labels.]

<!-- spec-docs:navigation document="document-id" -->
<!-- /spec-docs:navigation -->

<a id="tour"></a>
## Tour

[Follow a concrete end-to-end scenario. Explain shown values and the reason for each
write, change or retained value. Use labelled procedures for ordered actions. Describe
concurrent branches and synchronization points when applicable. Link declarations through
the format contract.]

<a id="mechanism"></a>
## Proposed mechanism

[Replace this heading and anchor with the entity's name and stable identity. Start with its
meaning and problem, then ordinary behavior. Cover applicable refusal, concurrency,
failure and recovery. Add canonical facts, relationships and requirements through the
format contract. Explain operating conditions and pass conditions for quality bounds.]

[Allocate permanent, repository-unique `req-<identity>` anchors under the specification
identity rules; do not derive them from the current file or heading.]

### Failure and recovery

[Add applicable declarations through the format contract. Trace retained state, restart,
exits and public error mappings. If the mechanism cannot stop or refuse, explain why.]

<a id="ownership"></a>
## Ownership and integration

[Name owners and affected boundaries. Explain changes to existing components and their
integration. Link exact interfaces and configuration to their reference homes.]

<a id="decisions"></a>
## Decisions and alternatives

[Record each choice, authority, evidence and rejected alternatives with reasons. Use the
format contract for decision anchors. Distinguish proposed choices from approved decisions.]

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

<a id="acceptance"></a>
## Acceptance evidence

[Add acceptance declarations through the format contract. Identify method, inputs, pass
condition and evidence, with reciprocal requirement links. Distinguish planned verification
from observed results. Allocate permanent `test-<identity>` anchors. When linking executable
tests, use the format contract's `Implementation` grammar:
`[tests/test_x.py::test_name](relative/path/to/tests/test_x.py)`; omit the field otherwise.]

<a id="reference"></a>
## Reference

[Keep exact schemas, signatures, module layouts, configuration and errors here. Reuse
canonical fact links; retain qualifications and their evidence beside the owning facts.]
