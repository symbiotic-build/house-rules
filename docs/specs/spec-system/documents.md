<a id="source-document"></a>
# Source document

A source document gives readers one ordered explanation of a technical contract across Markdown files.

A single-file design stays in its normal location.
It uses the repository's shared metadata and one generated navigation region.
It needs no private directory, companion glossary or exclusion file.

A specification explains maintained behavior.
A design document also supplies current evidence, constraints, alternatives, ownership, integration, rollout, work packages and acceptance evidence.
When design intent becomes maintained specification, move the current home instead of retaining two contracts.
Retained pointers follow the existing [skills/design-flow/SKILL.md](../../../skills/design-flow/SKILL.md).

The reading sequence is tour, mechanisms, requirements, decisions, open questions, reference, then acceptance.
The generated opening gives purpose, audience, scope and non-goals before that sequence.
A short document can combine adjacent roles in one section, preserving their internal order.

Purpose, audience, scope and non-goals explain the reader's task and prerequisites.
An inapplicable role says “None” and explains why.
A draft may expose gaps; approval refuses an unresolved contract that prevents implementation.

The [role requirement](requirements.md#req-roles) makes these declarations checkable.



In the bounded-batch example, the single document explains submission, refusal and the evidence for that behavior.
The exact files are explained later in [Minimal corpus](example.md#minimal-example).
