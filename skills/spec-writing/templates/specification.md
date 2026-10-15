# Specification template

Use this outline through the [authoring procedure](../SKILL.md#author-the-document).
Replace this guidance and bracketed prompts before approval. Adjust links when copying.
Register the document and its sections through the [format contract](../references/format.md);
that contract owns all declaration syntax. Apply the
[specifications rules](../../../rules/specifications.md) and
[writing profile](../../../rules/writing.md#house-technical-english).

<a id="purpose"></a>
## Purpose and audience

[State the outcome, intended reader and required background.]

<a id="scope"></a>
## Scope and non-goals

[Describe the behavior covered and excluded work.]

<!-- spec-docs:navigation document="document-id" -->
<!-- /spec-docs:navigation -->

<a id="tour"></a>
## Tour

[Introduce the system with a complete story before its mechanisms and reference material.
Explain inputs, state changes, retained values and caller-visible results. Use the writing
rules' labelled procedure for ordered actions. Link the scenario's requirements and tests
through declarations from the format contract.]

<a id="mechanism"></a>
## Mechanism

[Use the entity's real name as this heading and replace this anchor with its stable identity.
Open with its meaning and the problem it solves. Explain ordinary behavior, then applicable
refusal, concurrency, failure and recovery paths. Use direct home links under the
specifications rules. Add canonical facts and relations using the format contract.]

### Requirements

[Add requirement declarations from the format contract. Explain operating conditions,
measurement notation and pass conditions for quality bounds. Allocate permanent,
repository-unique `req-<identity>` anchors under the specification identity rules;
do not derive them from the current file or heading.]

### Failure and recovery

[Add applicable failure declarations from the format contract. Review retained state,
restart behavior, exits and public error mapping. If the mechanism cannot stop or refuse,
explain why.]

<a id="acceptance"></a>
## Acceptance

[Add acceptance declarations from the format contract. Identify inputs, method and pass
conditions; link real implementations when available. Check reciprocal requirement links
and test adequacy. Allocate permanent `test-<identity>` anchors. When linking executable
tests, use the format contract's `Implementation` grammar:
`[tests/test_x.py::test_name](relative/path/to/tests/test_x.py)`; omit the field otherwise.]

<a id="decisions"></a>
## Decisions

[Record choices, authority, evidence and rejected alternatives with reasons. Use the format
contract for resolving decision anchors. Do not treat an author's proposal as operator approval.]

<a id="questions"></a>
## Open questions

[Identify unresolved contracts, their owners and resolution paths. State None with a reason
when no question remains. Approval follows the specifications rules and design-flow.]

<a id="reference"></a>
## Reference

[Place exact interfaces, signatures, settings and errors here. Link canonical homes rather
than copying facts. Keep qualifications and evidence beside the facts they support.]
