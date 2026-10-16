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
- Keep the complete introduction together: opening paragraphs, one diagram with its question
  stated before it, its explanation and audience prerequisites. Put the generated overview,
  chapter map and term index after that introduction, before the first following heading.
  Write the manifest purpose as a statement of what the system does. Continue with a tour in plain
  steps, mechanisms, and exact reference in lookup form. Readers can stop after each part.
- Carry one real example from the tour through mechanisms to the reference and acceptance.
  Show its relevant snippet or values where each concept is introduced. Never append the
  example as an opening recap or repeated closing formula. A chapter opening says what
  this chapter adds. Before: "The batch holds two items and returns Full for the third."
  After, in a review chapter: "Assign source ownership and assess what structural checks
  leave to review." When explanation is deferred, name and link it.
- For an outside procedure, summarize what the reader needs in one or two sentences, or
  name it explicitly as a prerequisite in the opening's audience statement. Readers must
  not discover an unexplained prerequisite midway through the document. State the needed
  subset of outside rules locally when the design uses only part of them.
- State the design in its own voice, including converted documents. Keep original-source
  commentary in one provenance section, quote the original explicitly and name it
  unambiguously, such as "the original draft's overview", never "the overview" or "the source".
- When a mechanism or value is unresolved, provisional or unavailable, state that qualification
  before or in the same sentence as its description. A later caveat cannot qualify an earlier
  instruction. Before: "Combine ranked lists with weighted scores. The formula is unresolved."
  After: "The scoring formula is unresolved; the proposed combiner would weight the ranked lists."
- Explain a borrowed behavior before naming its tool or standard as a supporting reference.
  Define necessary technical terms at first use; otherwise use the plain statement.
- Give each repeated distinction or procedure one home and link it elsewhere. Diagnostic
  remedies name the concrete repair for each cause; navigation formats show complete bullets.
- A mechanism chapter covers one coherent part of how the system works that a reader can
  understand on its own, usually several related concepts and their homes. Never split
  chapters by term. Several entity homes may share a chapter, each in its own section.
  A chapter's filename is the slug of its title under the exact source formats.
- Except for decision records below, open every section with its purpose before rules,
  encodings or fields. Within an entity
  home, put a concise definition sentence first: say what the thing is. Explain its purpose
  in the next sentence or paragraph. For example: "A canonical fact is a named literal
  value declared once, in a table at its owner's home." Then explain how it prevents
  conflicting values. The generated entity index uses only that definition sentence.
  Declaration records also explain their purpose. Decision records start with
  Choice and use Reason to explain why; omit formula openings such as "This choice keeps".
- In tours and procedures, keep each step's action and caller-visible result in plain
  words. Start directly with the action and result; omit formula openings such as
  "The author explains". Show the concrete refusal or arithmetic at the step that uses it.
  For arithmetic updates, show the existing value, added amount and order of limiting operations.
  A repair tour starts from a complete supplied corpus instead of making readers assemble
  fragments from later reference chapters. Illustrate abstract rules beside their first use.
  Put exact rows, values and counts in a labelled detail block beneath that step,
  following [rules/writing.md](writing.md#sequences-and-structured-detail).
- Keep setup pins, exact vocabularies and diagnostic lookup tables in reference. Use
  one diagnostic table with each code's severity, meaning, remedy and behavioral test.
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
- Mark each fact Status as specified, provisional, observed or unresolved. Put provenance
  explanations in Basis or adjacent prose. For provisional or unresolved values, link
  their open question in Basis and state applicability before presenting the table.
  An undecided interpretation is not an executable limit.
- Keep each canonical fact's literal value in one home table cell. Other sections link
  directly to that fact. The format contract defines which labels assert values and their
  permitted normalization. Do not infer value types,
  measurement equivalence, ranges or formats from that comparison.
- Keep examples, diagrams and summaries illustrative; they introduce no obligations.
- Generate the overview, document map and entity index from canonical declarations.
  Derived navigation and context remain rebuildable; maintain no second authority.
- Move the entity home when approved design becomes maintained specification. Update its
  index entry and incoming links together; retain no competing current contracts.

<a id="direct-links"></a>
## Direct links

- Link an entity or fact directly to its home at first use in the text of each level-2
  section, whether the home is ahead, behind or in another document. Level-3 and deeper
  subsections share that scope. Later uses stay plain; tables may repeat links.
  Introductory definitions need no self-link. Never put a link inside a heading.
- Give a first-use link a short gloss when its meaning is needed to continue reading.
  Label repository-file links with their repository path. Named-section links use the
  section name. Implementation links append their selector to the path.
- Give literal code, signatures and diagrams direct home links in immediately adjacent
  explanatory prose or an **Entities in this example** paragraph. Prefer the prose
  when it already supplies those links; do not add a duplicate list. Each literal block needs
  its own adjacent links, including before the home. An index, glossary or
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
  matches Implementation selectors against the normal test run's JUnit report. Without reports,
  it runs one batch per runner. Acceptance requires zero missing and failing selectors.
  Inspection and analysis cases name evidence inside the document set or repository.
  Distinguish a planned inspection from a completed inspection with its recorded result.
  Name document-only cases "Inspection:", "Analysis:" or "Demonstration:" with permanent `test-` anchors;
  the general acceptance-case identity does not imply executable verification.
- Keep Status and Basis on every requirement record. When they are identical across records,
  use short fields linking their shared explanation once rather than repeating that explanation.
- Link requirements and acceptance tests reciprocally. Changed requirements and directly
  referenced facts expose affected tests for re-review, including relevant base material.
  Removing a requirement needs a resolving decision reference.
- For a system that keeps durable state, state its system-level and operation-level
  invariants as requirements, each linked to the test that checks it
  ([Test discipline](../prompts/skills/test-discipline.md#systems-that-keep-durable-state)).
- Give each stopping mechanism a failure declaration: trigger, retained or changed state,
  caller-visible result, recovery action or its explicit absence, required actor and
  authority, and verification links. Explain ordinary behavior before failure paths.
  Distinguish unavailable recovery from unspecified recovery behavior; record the latter
  as an unresolved contract with an owner and resolution path.
- Keep unresolved implementation contracts visible. Structural resolution of a decision
  reference does not establish its authority. Approval cannot leave an unresolved contract
  that prevents implementation.

## Agent context

- Give every writer and reviewer the complete repository registry, assigned section
  subtrees, relevant complete entity homes, declared explanatory dependencies, applicable
  profile, decisions and provenance from one immutable snapshot.
- Rewrite links to included source destinations as unique in-pack anchors, with separate
  namespaces for source paths and snapshot labels. Preserve original source fingerprints
  and range sizes; include rewritten bytes in total pack accounting. Leave literal examples
  and destinations outside the selection unchanged.
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
  explanations and scenarios. Regenerate any assignment whose baseline is
  stale from the current snapshot; no rebase verifier exists.
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
- Review each decision diagram or ordered rule against every combination of its conditions.
  State which combinations cannot occur. Distinguish prior qualification, per-launch checks
  and runtime observations; do not claim runtime observations precede launch.
- Review meaning, technical correctness, readability, design and cost, failure and
  recovery, and complete scenarios. Reviewers establish that explanations and tests prove
  the contract; structural success alone does not establish either.
- Review unlinked value restatements and unregistered technical meanings semantically.
  A warning alone proves neither a contradiction nor a reader problem.
