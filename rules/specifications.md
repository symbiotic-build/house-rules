# Specification rules

Apply these rules to every specification and design document, including single-file
documents. Declaration syntax and literal comparison belong to the
[exact source formats](../docs/specs/spec-system/source-formats.md#source-format). Authoring procedure
belongs to [spec-writing](../skills/spec-writing/SKILL.md); approval and closeout belong
to [design-flow](../skills/design-flow/SKILL.md).

<a id="reader-progression"></a>
## Reader progression

- Order document roles as purpose, audience, scope and non-goals; tour; mechanisms;
  requirements; decisions with rejected alternatives; open questions; reference; acceptance.
  Every role is present or explicitly inapplicable with a reason. Short documents may
  combine adjacent roles in one section while preserving that order within it.
- Start with the map: an opening paragraph, one diagram with its question stated before
  it, then generated overview, chapter map and term index. Continue with a tour in plain
  steps, mechanisms, and exact reference in lookup form. Readers can stop after each part.
- Carry one real example from the tour through mechanisms to the reference and acceptance.
  Show its relevant snippet or values where each concept is introduced. Never append the
  example as a repeated closing formula. When explanation is deferred, name and link it.
- A mechanism chapter covers one coherent part of how the system works that a reader can
  understand on its own, usually several related concepts and their homes. Never split
  chapters by term. Several entity homes may share a chapter, each in its own section.
  A chapter's filename is the slug of its title under the exact source formats.
- Open every section with its purpose before rules, encodings or fields. Within an entity
  home, put a concise definition sentence first: say what the thing is. Explain its purpose
  in the next sentence or paragraph. For example: "A canonical fact is a named literal
  value declared once, in a table at its owner's home." Then explain how it prevents
  conflicting values. The generated entity index uses only that definition sentence.
  Declaration records also explain their purpose.
- In tours and procedures, keep each step's action and caller-visible result in plain
  words. Put exact rows, values and counts in a labelled detail block beneath that step,
  following [rules/writing.md](writing.md#sequences-and-structured-detail).
- Keep normative requirement records separate from illustrative explanation and examples.

<a id="authority-and-homes"></a>
## Authority and homes

- Declare the reader, purpose, scope, reading order, stable section identities and entity
  homes through the shared document manifest and entity index. Classify every candidate
  Markdown path, including preserved inputs and evidence. Each chapter's opening text
  belongs to a registered section subtree.
- Give each entity one complete home containing its meaning and canonical declarations.
  The entity index owns identity, classification, accepted and rejected forms, and home
  location. The Markdown home owns meaning, facts and operational explanation.
- Keep each canonical fact's literal value in one home table cell. Other sections link
  directly to that fact. Linked values match the home text after the format contract's
  surrounding-space and digit-group-separator normalization. Do not infer value types,
  measurement equivalence, ranges or formats from that comparison.
- Keep examples, diagrams and summaries illustrative; they introduce no obligations.
- Generate the overview, document map and entity index from canonical declarations.
  Derived navigation and context remain rebuildable; maintain no second authority.
- Move the entity home when approved design becomes maintained specification. Update its
  index entry and incoming links together; retain no competing current contracts.

<a id="direct-links"></a>
## Direct links

- Link an entity or fact directly to its home at first use in the text of each level-2
  section. Level-3 and deeper subsections share that scope; tables may repeat links.
- Link every use before its home in manifest reading order. A home in another document
  counts as ahead. After the home appears, later uses in the same section may be plain.
  Introductory definitions need no self-link. Never put a link inside a heading.
- Give a first-use link a short gloss when its meaning is needed to continue reading.
  Label repository-file links with their repository path. Named-section links use the
  section name. Implementation links append their selector to the path.
- Use adjacent **Entities in this example** links for literal code, signatures and
  diagrams. Repeat them for each literal block before a home. An index, glossary or
  another use site never substitutes for the home.

<a id="section-names"></a>
## Section names

- Use unnumbered headings in specifications and design documents. Refer to a section or
  decision by its linked name, never by a hand-typed number.

<a id="requirements-tests-and-recovery"></a>
## Requirements, tests and recovery

- Give each requirement and acceptance test a permanent repository-unique identity,
  independent of its file, heading and wording. Preserve it when moving or revising
  the same obligation or case; never reuse a retired identity. New obligations or
  cases from a split or replacement receive new identities. Keep revision information
  outside the identity in Git history. When a base snapshot is supplied, compare candidate
  anchors against its reachable history to reject reuse of deleted identities. Without
  a Git-backed base, reviewers check historical reuse. Requirement anchors start with `req-` and
  acceptance-test anchors with `test-`; suffix syntax belongs to the format contract.
- A test with Method `test` names executable selectors in its Implementation field.
  A test with Method `inspection`, `analysis` or `demonstration` instead links evidence
  (a review lens or run record) and has no Implementation field. The selector audit
  executes every Implementation selector; acceptance requires zero missing and failing ones.
- Link requirements and acceptance tests reciprocally. Changed requirements and directly
  referenced facts expose affected tests for re-review, including relevant base material.
  Removing a requirement needs a resolving decision reference.
- Give each stopping mechanism a failure declaration: trigger, retained or changed state,
  caller-visible result, recovery action or its explicit absence, required actor and
  authority, and verification links. Explain ordinary behavior before failure paths.
- Keep unresolved implementation contracts visible. Structural resolution of a decision
  reference does not establish its authority. Approval cannot leave an unresolved contract
  that prevents implementation.

## Agent context

- Give every writer and reviewer the complete repository registry, assigned section
  subtrees, relevant complete entity homes, declared explanatory dependencies, applicable
  profile, decisions and provenance from one immutable snapshot.
- Select assignments explicitly. Unknown selectors and missing scope fail preparation;
  they never mean all homes. Expand declared explanatory dependencies transitively and
  deduplicate cycles and overlapping source ranges. Ordinary links inside included homes
  do not recursively expand context.
- Include every action, requirement and linked test section for a whole-scenario
  assignment. Mark unrelated registry entries as reference material for fresh readers;
  registry content cannot excuse a missing explanation in the reading material.
- Report exact UTF-8 bytes, identities, inclusion reasons, fingerprints, registry digest,
  baseline, and tool and profile versions. Label base and candidate material separately.
  Read commits from the selected commit, staged checks from the complete index, and
  authoring packs from captured working-tree bytes.
- Reserve mandatory context before optional material. The dispatcher accounts for rules,
  task and response allowance within its configured budget. Missing, stale or excessive
  mandatory context stops preparation before dispatch. Never truncate it. Narrow the
  assignment or remove unjustified dependencies; changing resources when the compulsory
  registry alone cannot fit requires an operator decision.
- Rebuild packs when registry or home digests change. Affected authors recheck surrounding
  explanations and scenarios. Other assignments need a current-baseline pack or a
  mechanically verified rebase.
- Use the pinned shared checker and selector through the existing prompt compiler.
  Extracted compilers use their matching helper, profile and format contract, never an
  unrelated live checkout. Review services prepare and check packs; reviewers stay
  read-only and run no builds, tests or external writes.

## Checks and review

- Block structural errors with the shared checker over the complete candidate corpus.
  Follow [writing rules](writing.md#house-technical-english) for prose-check policy,
  profile and severity. Review every remaining warning group with a stated disposition.
- Keep every emitted diagnostic's meaning and remedy in the diagnostic reference, with
  behavioral regression evidence for every active code. Run the repository's declared gates.
- Review meaning, technical correctness, readability, design and cost, failure and
  recovery, and complete scenarios. Reviewers establish that explanations and tests prove
  the contract; structural success alone does not establish either.
- Review unlinked value restatements and unregistered technical meanings semantically.
  A warning alone proves neither a contradiction nor a reader problem.
