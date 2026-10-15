---
name: spec-writing
description: Author and review specifications, design documents and system maps using canonical entity homes, generated navigation, reciprocal acceptance links and fresh-reader review. Use for single-file and multi-file technical documents, including conversion of an existing corpus.
license: MIT
---

# Spec Writing

The reader should understand the system and a mid-level engineer should be able to
implement it without unanswered contract questions. Apply the
[specifications rules](../../rules/specifications.md) for document authority and context,
and the [writing rules](../../rules/writing.md#house-technical-english) for prose.
Declaration syntax belongs to the specification’s [exact source formats](../../docs/specs/spec-system/formats.md#source-format).
Start with the checked [minimal corpus](../../docs/specs/spec-system/example.md#minimal-example).
Lifecycle and approval follow [design-flow](../design-flow/SKILL.md);
placement follows [STRUCTURE.md](../../STRUCTURE.md).

Use the [specification template](templates/specification.md) or
[design-document template](templates/design-document.md) as an outline. Combine roles
when a short document needs fewer sections. Replace template guidance with authored
content and adjust its links to the destination before checking the document.

## Before writing: sweep reality

Inspect the implementation, real consumers, constraints and settled decisions. Verify
inherited claims against primary code and evidence, rather than another document's
summary. Rank conflicting decisions by recency and explicit supersession. On an inherited
codebase, use existing code as evidence for the intended clean system map and specification.

Check proposed names against existing names before introducing them. Review the
[premise check](../../prompts/util/premise-check.md) for foundational choices before
writing and before approval. Use [finding-unknowns](../finding-unknowns/SKILL.md) for
unsettled questions, without reopening a settled choice merely because it is unfamiliar.

<a id="author-the-document"></a>
## Author the document

**Procedure: produce an implementable document**

1. **Review the outline.**
   - Establish the reader, outcome, scope, non-goals and prerequisites.
   - Sketch section purposes and a complete end-to-end scenario.
   - Register a valid draft skeleton: anchored sections with opening prose, explicit role
     gaps, an empty entity index, no incomplete declarations and no dangling scenario selectors.
   - Register each chapter's title anchor so its opening text belongs to the selected subtree.
   - Inventory preserved Markdown inputs and evidence as well as the authored chapters.
   - Leave homes unregistered until their headings and definitions exist.
   - Generate navigation from that valid skeleton; no permissive generation mode is needed.
   - Require successful generation and checking before assigning body sections.
   - Read that navigation before assigning sections.
2. **Establish entity homes.**
   - Inventory concepts and canonical facts against the primary sources.
   - Assign one editor for manifest and entity-index changes in the round.
   - Assign one responsible owner to each entity home.
   - Identify unresolved contracts and their decision owners.
3. **Write the assigned sections.**
   - Use disjoint source assignments and generated context when several authors work.
   - Explain each mechanism's problem and ordinary behavior before its exceptional paths.
   - Add reciprocal requirements and acceptance cases together using the exact source formats.
   - Use one decision heading per choice. Put alternatives in one Rejected alternatives field;
     do not repeat the same bold field label within a declaration or decision.
   - Complete each failure declaration before registering scenarios that refer to it.
   - Propose changes to another owner's facts instead of introducing replacement definitions.
4. **Review the assembled document.**
   - Run the pinned shared tool's structural check and regenerate navigation.
   - Inspect the resulting map, link density and tables as a reader.
   - Review technical meaning, design and cost, failure and recovery, and whole scenarios.
   - Run the fresh-reader procedure below for the readability responsibility.
5. **Integrate accepted resolutions.**
   - Have one fixer integrate the accepted findings.
   - Regenerate affected assignments and include linked tests selected by change impact.
   - Recheck surrounding explanations, scenarios and reading order.
   - Apply the existing design-flow approval boundary.

Use the shared checker from the repository's pinned House Rules revision. Setup and
command arguments follow the format contract. Do not copy the implementation into the
consumer repository. Inspect diagnostics before changing prose: structural errors and
readability warnings have different authority under the specifications and writing rules.

## Explain behavior to readers

Build the reading path under [rules/specifications.md](../../rules/specifications.md#reader-progression):
write the opening and diagram question, generate the map, then write one real tour.
Choose its example before assigning chapters. Extend that same example in each mechanism
chapter and revisit it in the reference and acceptance. Draft one mechanism per chapter.
Read only the map, then only map and tour, to check that each stopping point makes sense.

Write a purpose paragraph before every section's rules or fields, including declarations.
Keep entity-home opening definitions concise because generation copies the whole paragraph.
When touching an explanation owned elsewhere, add a one-line linked handoff naming what is
explained later. Check each first-use gloss against what a reader needs at that point.

For each tour or procedure step, write the action and caller-visible result first.
Move exact payloads beneath that step, for example:

> **Detail — capacity comparison**
>
> The displayed value differs from the table's value; comparison reports `D10`.

Use [rules/writing.md](../../rules/writing.md#sequences-and-structured-detail) for step structure.
Keep schemas and signatures in lookup reference after the mechanisms. Use the executable
fixtures inside this skill when the specification chapters are unavailable; their JSON and
Markdown form a complete checked corpus. Read each fixture file, including adjacent
qualification and literal-example annotations, rather than inventing declaration syntax.
The format reference links the canonical grammar; do not duplicate its policy here.

For every shown stored value, explain what it represents, its unit or code meaning, and
why the action writes, changes or retains it. For arrays, explain element meanings and
which entries correspond. For shared slots, identify the record type and mapped field.
Check these explanations against the schema or protocol. A compact dump does not explain
behavior merely because its encodings have names elsewhere.

Trace a complete scenario across its sections, requirements and tests. For concurrent
behavior, identify branches and synchronization points; consecutive numbering must not
turn concurrency into a serial story. Examine entry, retained state, restart behavior,
exits and public error mappings when reviewing a refusal or stop. Follow the failure
contract in the specifications rules, including an explicit absence of recovery where
that is the design.

Preserve provisional qualifications, observed conditions, exceptions and resolution paths
beside their homes. Check unlinked value restatements manually. A passing link check proves
neither an explanation nor adequate evidence for a value or acceptance test.

<a id="fresh-reader-review"></a>
## Fresh-reader review

**Procedure: test understanding in a fresh context**

1. **Prepare the reader package.**
   - Use the normal context selector from one snapshot.
   - Supply source chapters, generated navigation, complete registry reference and relevant
     linked homes, with the applicable decisions, profile and provenance.
   - Mark registry material outside the reading dependencies as reference material.
   - Exclude authoring conversation, prior findings, coaching and unpublished explanations.
2. **Give a new reader a generic task.**
   - Ask it to explain the system and follow the tour.
   - Use two fresh readers using different models for system acceptance.
   - Ask ten questions: purpose, inputs, authority, reading order, identity, literal equality,
     ordinary result, refusal, recovery, and context selection. Require citations for each.
   - Require zero unanswered questions, guesses or stuck points.
   - Have each reader build a small corpus from the chapters alone. Its first checker run
     must have zero errors; retain that run's output as evidence.
   - Ask it to explain a refusal and its recovery, or the declared absence of either.
   - Require citations for ambiguity, hidden assumptions and places understanding fails.
3. **Assess the answers against the document.**
   - Do not repair missing explanations through code, external sources or author coaching.
   - Distinguish a concrete reader problem from a stylistic preference or counter warning.
   - Check that reference registry material did not conceal a missing explanation.
4. **Refresh the affected document and context.**
   - Integrate accepted findings through the editor and home owners.
   - Regenerate navigation and affected packs, then recheck the changed scenarios.

Use a new agent context for this pass when review is authorized. This procedure may fill
the existing readability responsibility; it does not authorize another review panel.

## Qualify the authoring pipeline

Use normal branch-pinned loaders for a fresh author run from a short feature brief.
Check the new multi-chapter specification against the reader-progression rules, structural
gate and fresh-reader procedure. Separately convert an existing unconverted design and a
deliberately messy document through the conversion procedure. Require the same checks.
Bind run records to the source revision and candidate digest. Inspect every approved design
and operator decision for implemented behavior or an explicit reasoned change. A renderer
has its own specification and linked display tests in its repository; do not claim its
acceptance from the House Rules check. Repair defects in their rule, template, lens or
checker owner and repeat the normal run; never repair generated output by hand.

## Convert existing material

**Procedure: replace an existing naming canon**

1. **Inventory its content.**
   - Account for every row and substantive prose rule.
   - Distinguish names, meanings, rejected forms, patterns, mappings, transitions and decisions.
2. **Move each item to its owner.**
   - Use the format contract for identities, accepted and rejected forms, and field patterns.
   - Move explanations, interface distinctions, states and requirements to complete homes.
   - Keep code-only identifiers with their code owner unless specification readers need them.
   - Preserve rules that cannot be expressed as field patterns as linked requirements.
3. **Check the replacement before removal.**
   - Update metadata, direct links and loaders together.
   - Generate navigation and review boundaries, actors, states and qualifications.
   - Remove superseded material only after the replacement is complete.

Use the same process for single-file documents through the shared metadata and an inline
navigation region. When design intent becomes maintained specification, follow design-flow
closeout and update the home rather than retaining two current contracts.

## Content checks

Check exact type, trait and schema definitions, module layout and integration points
against the implementation sources. Explain their behavior in the walkthrough before
using reference encodings. Review one overview diagram alongside the introductory text
under [writing rules §Format](../../rules/writing.md#format). Describe the system rather
than its editing history. Keep a README as a user guide pointing to the specification,
rather than a second contract.

Compare names across documents, code and user interfaces. Apply the writing rules' naming
requirement and [STRUCTURE.md §Naming rules](../../STRUCTURE.md#naming-rules). Distinguish
categories with different handling assumptions in their types. Check every threshold or
scale against its supporting constraint or measurement. Follow
[design-canon](../design-canon/SKILL.md) for pipeline ordering, truth tiers and configurable
policies. During the final editing pass, consolidate repeated explanations without losing
rules, values, exceptions or concrete examples, then repeat the reader test.

## Duty to critique

Review a supplied specification against evidence and the requested outcome. Follow
[operator-protocol](../operator-protocol/SKILL.md) for critique and decision handling.
During implementation, deliver the approved contract literally. Requirement removals and
mechanism changes follow [design-flow §Design changes](../design-flow/SKILL.md#design-changes).
Propose document deviations for acceptance rather than silently reducing requirements.
