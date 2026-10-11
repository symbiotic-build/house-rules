---
name: spec-writing
description: How to write specs, design docs, and system maps that pass the "buildable by a mid-level engineer without questions" bar — shape, worked examples, decision records, naming, and the reality-sweep that precedes writing. Use when writing or reviewing any spec, design doc, system map, or architecture document.
license: MIT
---

# Spec Writing

The acceptance test for every spec: **a mid-level engineer could implement the system
from it without asking questions.** The document must explain the product and its implementation boundaries. Lifecycle: skill `design-flow`; placement: `STRUCTURE.md`.

## Before writing: sweep reality

- Inspect the current implementation, its real consumers and constraints before writing. Use a multi-agent sweep for
  cross-cutting work when delegation is permitted and fits the campaign resource
  envelope. Otherwise perform the authoritative source sweep with the primary agent and
  propose additional review if beneficial. Verify inherited claims against canonical code
  (file:line), not against other documents.
- Check for superseded decisions before re-deciding. Rank conflicting sources by recency and supersession.
- On inherited/messy codebases, derive the clean system map + spec from the old code as
  *reference*, then classify components easy/hard to rewrite, then build.

## Shape (every doc)

- **TL;DR first.** Verdict/summary up front, detail below.
- **Worked examples are mandatory**: real inputs → how they're validated/transformed →
  what's stored. Multiple examples beat prose every time.
- **Exact signatures, not descriptions**: real type/trait/schema definitions, module
  layout, integration points. Keep exact definitions in the reference material and
  explain their behavior in the walkthrough. Code alone does not explain a stored value.
- **Diagrams**: format follows [rules/writing.md §Format](../../rules/writing.md#format) (doc tiers:
  skill `design-canon` §Docs).
- **Authoritative framing**: decisions are stated as decisions ("X does Y via Z"), with
  a Decisions section recording each choice AND its rejected alternatives with why.
  Tentative framing ("we could maybe...") is for the open-questions list only.
- **No development history**: docs describe the system, not the editing history.

## Readable by people

Buildable is not enough: people read specs to understand, review and decide.

- **Reading order**: what it is (one paragraph and one diagram) → one walkthrough of a real
  example from start to finish → setup and use → the rules → reference (schemas, event and
  error tables, acceptance tests).
- **Why before rules**: each section opens with a short paragraph on the problem it solves,
  then states its rules.
- **One idea per paragraph**, sections short enough to read in one sitting, and one concrete
  example next to each concept rather than only in an appendix.
- **Plain terms**: define every term at first use and in a glossary; no unexplained acronyms
  or internal labels; ask for concrete things, not abstractions. Explain terms in the
  behavior they describe. Do not add a local glossary merely to explain invented names;
  apply rules/writing.md's naming requirement instead.
- **Tables for lookup, prose for understanding**: behaviour is not buried in table cells.
- **Label authority**: decisions, assumptions, estimates and open questions are marked as such.
- **Reader test**: read each section alone, pretending the rest is unavailable. A new engineer
  must be able to say what problem it solves, what the rule is and when it applies. If not,
  rewrite the explanation or split the section. For every worked example, explain each
  shown stored value: what it represents and any unit or code meaning. Explain why the
  step writes, changes or keeps those values and what the caller observes. For arrays,
  state the element meanings and
  which entries correspond. For shared slots, name the record type and mapped field.
  A compact dump fails when the reader must decode it from a glossary or another section.
  Use a name/value/meaning listing or equally clear prose. A reference table may repeat
  exact encodings after the walkthrough explains them.
- **Check explanations against the source**: verify every new meaning and reason against
  the schema or protocol. Preserve qualifications and exceptions. A successful link,
  heading or content-preservation check is not a successful reader test.
- **Preserve meaning when rewriting**: move exact values to annotated listings when needed.
  Reword or consolidate repeated text without losing a rule, value or exception. Verify
  the resulting explanation; do not require the old value-dump sentence to stay intact.
- **Polish after review**: review rounds add patches. Before merge, one pass restructures the
  text, removes repetition and reruns the reader test.
- **README**: a one-page user guide (what it does, how to use it, where the spec is), not a
  second spec.

## Naming (spec work is naming work)

- Names are isomorphic across docs, code, and UI — one concept, one name, everywhere.
- Grep for collisions before introducing any name; a locally-good name that collides
  with an existing concept is rejected.
- No unexplained shorthands anywhere; disambiguate lookalikes (`STRUCTURE.md` §Naming
  rules).
- Split categories that carry different handling assumptions (e.g. *malformed* vs
  *suspicious* input — wildly different security posture) into distinct named types.

## Content standards

- **Pipeline-order invariants and truth tiers** are explicit in the spec: the ordered
  list of what runs before what, and which tier each consumer sees (skill `design-canon`).
- **Parameters derived, not asserted**: every threshold/size/scale in a spec traces to a
  constraint or measurement; a magic constant is a bug until justified.
- **Premise check**: run the [premise check](../../prompts/util/premise-check.md) on every
  foundational choice before writing and again before approval.
- **Every policy configurable** (skill `design-canon` §Decisions).

## Duty to critique

Review a supplied spec against evidence and the requested outcome; critique per skill
`operator-protocol` §Collaboration. When implementing, deliver the spec literally — if
it says scores/metadata/IDs, never substitute a cruder proxy.
If the specified mechanism seems wrong mid-build, escalate per skill `operator-protocol`
§Decisions when the change is outside the approved decision boundary; otherwise record
the deviation per skill `design-flow` §5. Requirement removals and spec edits that match
existing code follow `design-flow` §Design changes; critique these rather than ratifying
the implementation in the spec. Never silently implement a reduced version.
