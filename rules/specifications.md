# Specification rules

Apply these rules to every specification and design document, including single-file
documents. Declaration syntax and literal comparison belong to the
[exact source formats](../docs/specs/spec-system/formats.md#source-format). Authoring procedure
belongs to [spec-writing](../skills/spec-writing/SKILL.md); approval and closeout belong
to [design-flow](../skills/design-flow/SKILL.md).

## Authority and homes

- Declare the reader, purpose, scope, reading order, stable section identities and entity
  homes through the shared document manifest and entity index.
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

## Direct links

- Link an entity or fact directly to its home at first use in each heading's introductory
  section. Each subsection starts a new section for this rule.
- Link every use before its home in manifest reading order. A home in another document
  counts as ahead. After the home appears, later uses in the same section may be plain.
  Defining headings and introductory definitions need no self-link.
- Use adjacent **Entities in this example** links for literal code, signatures and
  diagrams. Repeat them for each literal block before a home. An index, glossary or
  another use site never substitutes for the home.

## Requirements, tests and recovery

- Give each requirement and acceptance test a permanent repository-unique identity,
  independent of its file, heading and wording. Preserve it when moving or revising
  the same obligation or case; never reuse a retired identity. New obligations or
  cases from a split or replacement receive new identities. Keep revision information
  outside the identity in Git history. Requirement anchors start with `req-` and
  acceptance-test anchors with `test-`; suffix syntax belongs to the format contract.
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
  profile and severity.
- Review meaning, technical correctness, readability, design and cost, failure and
  recovery, and complete scenarios. Reviewers establish that explanations and tests prove
  the contract; structural success alone does not establish either.
- Review unlinked value restatements and unregistered technical meanings semantically.
  A warning alone proves neither a contradiction nor a reader problem.
