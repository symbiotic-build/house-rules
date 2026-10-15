<a id="sources"></a>
# Sources, homes and declarations

Shared metadata lets readers find one definition without maintaining a second copy of technical meaning.
Markdown remains the source and reading format.
The declarations here use ordinary headings, links, tables and explicit anchors.

<a id="document-manifest"></a>
## Document manifest

The document manifest is the repository's JSON declaration of document inventory, purpose, audience, scope and section reading order.

Its home path is [docs/DOCUMENTS.json](../../DOCUMENTS.json).
Every tracked Markdown file has an inventory classification.
An `other` classification includes a reason.
Reviewers check that a reason does not hide a specification or design document.

The section array defines reading order; identities do not depend on array positions.
Each entry identifies its path, explicit anchor, roles, summary and prerequisites.
Explanatory dependencies identify another section and state why it is needed.
Applicability is document-level in the format [version](#manifest-version).
One section may serve several roles.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="manifest-version"></a>version | 1 | specified | [Source decision](reference.md#source-decision) |
| <a id="manifest-path"></a>path | docs/DOCUMENTS.json | specified | [Source decision](reference.md#source-decision) |

Each document declares one navigation arrangement.
A standalone generated file uses `navigation.path`.
A region in an existing document also sets `navigation.region` to the document identifier.
Navigation belongs under generated documentation or in the declared region of an existing document.
It never creates a competing system map.

Production approval uses `operator` or `delegated` authority and a resolving decision reference.
Only the fixture runner accepts `fixture` authority.
Drafts may retain unresolved contracts.
Approval fails when such a contract prevents implementation.

<a id="require-roles"></a>
### Requirement: complete document roles

**Actor:** [Documentation checker](checking.md#documentation-checker).

**Condition:** A document is checked or submitted for approval.

**Result:** Require purpose, audience, scope, non-goals, tour, mechanisms, requirements, acceptance, decisions, questions and reference. Refuse blocking unresolved contracts at approval.

**Verification:** Check complete, incomplete, draft and approval-blocked declarations.

**Tests:** [Document roles](acceptance.md#test-roles).

**Status:** specified.

**Basis:** [Source decision](reference.md#source-decision).

<a id="entity-index"></a>
## Entity index

The entity index is the repository's JSON authority for concept identities, classification, applicability, names and home locations.

Its home path is [docs/ENTITIES.json](../../ENTITIES.json).
Each entry contains `kind`, `home`, `scope`, `forms`, `symbols` and `rejected_forms`.
The `home` object identifies a manifest section and explicit anchor.
The home heading supplies the display name.
Its first paragraph supplies the meaning.
Neither is copied into this authored metadata.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="index-version"></a>version | 1 | specified | [Source decision](reference.md#source-decision) |
| <a id="index-path"></a>path | docs/ENTITIES.json | specified | [Source decision](reference.md#source-decision) |

The `scope` array lists every document where an entry applies.
Accepted names and exact symbols support recognition.
Rejected forms name a replacement and a reason.
Naming rules target structured fields through patterns; they never guess identifiers from prose.
A rule that cannot be a field pattern remains a linked canonical requirement.
Code-only identifiers stay with their code or reference owner unless specification readers need the concept.

Each [registered entity](overview.md#registered-entity) has one home.
Link its first use in each section directly to that home.
Link every use while its home remains ahead in reading order.
Later uses in the same section may remain plain after the home has appeared.
The defining heading and introductory definition need no self-link.
An index, glossary or another use site does not satisfy a home link.

Literal code, signatures and diagrams use adjacent **Entities in this example** links.
Repeated literal blocks before a home each carry those links.
The checker does not infer bindings inside arbitrary programming languages.
It recognizes exact symbols and unambiguous registered phrases.
Reviewers identify unregistered concepts and ordinary words with unstated technical meaning.

<a id="require-homes"></a>
### Requirement: unique homes and direct links

**Actor:** [Documentation checker](checking.md#documentation-checker).

**Condition:** Registered names, symbols, home declarations or their uses appear in the selected corpus.

**Result:** Require complete unique homes, declared document scope and direct first-use and forward-use links. Refuse rejected forms and structured naming violations.

**Verification:** Check valid uses and mutations of home identity, scope, name, target and reading order.

**Tests:** [Homes and names](acceptance.md#test-homes).

**Status:** specified.

**Basis:** [Source decision](reference.md#source-decision).

<a id="canonical-fact"></a>
## Canonical fact

A canonical fact is a named literal value declared in a table cell at its owning entity's home.

A value table has Key, Value, Status and Basis columns.
Each Key cell contains one empty `id` anchor.
An anchor between rows would interrupt the table.
Keys are qualified by their owner, so several owners may each have `default`.
A collection may own several values.
A setting needs a separate entity only when its explanation or relationships require one.

The Value cell supplies text.
Markdown formatting delimiters are not value characters.
Text inside code spans stays literal; quotes and punctuation remain part of the value.
Words such as `pending`, `null` and `derived` have only their authored meanings.
The tool reserves no value vocabulary.

For linked-value comparison, trim surrounding spaces and remove digit-group separators within grouped digit runs.
Recognize commas, underscores and grouping spaces between groups of three digits.
Preserve every other character, case and internal space.
Do not change decimal punctuation.
Do not parse arrays or maps, reorder keys, evaluate expressions or convert measurements.

A label using the fact's Key or a registered name or symbol of its owner is descriptive navigation.
Name matching follows terminology rules.
Every other label displays a value and must equal the home text under grouping normalization.
Put explanatory words outside a value-bearing link.
Unlinked restatements remain review work.
A prose-numeral warning cannot establish which value a sentence means.

For example, a home value of `1 024` accepts a displayed `1024`.
A displayed `1,024` also passes.
Labels of `1.024`, `1024 items` and `2048` fail.
A home value of `4 MiB` refuses a displayed `4194304 bytes`.
Mathematical equivalence does not satisfy literal equality.
These literals illustrate comparison; they add no operating limits.

Status identifies specified, provisional, observed or unresolved meaning.
Basis links the supporting decision, requirement, measurement or other evidence.
Reviewers establish the evidence's authority and adequacy.
The tool never infers Status from value text.

Keep provisional qualifications beside the home and identify their fact.
Observed values retain evidence and operating conditions.
Unresolved values retain a resolution path.
A registered provisional value is not an operating guarantee.
Shared values use direct links to their one home; no local reference-valued fact, inherited metadata or fallback is created.

<a id="require-literals"></a>
### Requirement: literal equality

**Actor:** [Documentation checker](checking.md#documentation-checker).

**Condition:** A value is declared or a link targets its fact anchor.

**Result:** Require one home anchor in the declaring Key cell and a resolving target. Compare value-bearing labels as literal text under grouping normalization.

**Verification:** Exercise descriptive labels, equal and unequal literals, punctuation, grouping and equivalent measurements.

**Tests:** [Literal values](acceptance.md#test-literals).

**Status:** specified.

**Basis:** [Literal-value decision](reference.md#literal-decision).

<a id="requirement-declaration"></a>
## Requirement declaration

A requirement declaration states an actor, condition, observable result, verification, linked tests, Status and Basis.

Put the condition before the result in normative English.
A quality bound states operating conditions, measure, notation and pass condition.
The technical contract and implementation validate that bound.
Documentation checking does not validate a value's range or format.
Neither a full controlled requirements grammar nor mandatory uppercase keywords are required.

Every declaration links at least one [acceptance test](#acceptance-test).
Both directions must describe the same relationship.
Missing targets, missing relationships and one-sided links fail checking.
Passing these checks establishes structural traceability, not proof quality.
Implementation unit tests do not each require a documentation requirement.

<a id="acceptance-test"></a>
## Acceptance test

An acceptance test declares a verification method, inputs, pass condition and reciprocal requirement links.

Execution, inspection, analysis and qualification campaigns are valid methods.
A design-stage case may exist before executable code.
An optional Implementation link names the real file and selector.
Static checks resolve the file; reviewers confirm that the selector exists and proves the linked [requirement declaration](#requirement-declaration).

Comparing base and candidate snapshots reports new, changed and removed requirements.
The report includes declarations, linked tests from both snapshots and relationship additions or removals.
Changes to directly referenced fact values, Status, Basis or qualifications also select affected requirements.
There are no effective-value chains.

Review assignments include selected tests even when their text did not change.
A removed requirement needs a resolving decision supplied by the work item or task.
The checker resolves references; reviewers establish authority.
The report is derived from sources and Git snapshots.
Store no suspect-link stamps, approval hashes or separate traceability ledger.
Existing review resolution records the disposition.

<a id="require-traceability"></a>
### Requirement: reciprocal and changed-test review

**Actor:** [Documentation checker](checking.md#documentation-checker) and review preparer.

**Condition:** Requirements and tests are checked against an optional base snapshot.

**Result:** Refuse missing or one-sided relationships. Report changed declarations and directly referenced facts with tests from both snapshots. Include affected tests in review input and require decisions for removals.

**Verification:** Mutate declarations, relationships, fact qualifications and requirement presence across two snapshots.

**Tests:** [Traceability and change selection](acceptance.md#test-traceability).

**Status:** specified.

**Basis:** [Source decision](reference.md#source-decision).

<a id="scenario"></a>
## Scenario

A scenario follows concrete inputs, actions and expected results across sections.

It may link [requirement declarations](#requirement-declaration) and [acceptance tests](#acceptance-test).
A tutorial does not become a test merely by describing behavior.
The manifest names whole [scenarios](#scenario) for assignment.
Such assignments include every section containing their actions, requirements and linked tests.

Ordered steps must not silently serialize concurrent behavior.
A concurrent example names branches and synchronization points.
A completed competing action followed by submission is sequential.

<a id="failure-declaration"></a>
## Failure declaration

A failure declaration states how a stopping mechanism affects its caller and what recovery requires.

Every mechanism that stops, refuses or remains blocked declares Trigger, Outcome, Retained state, Recovery, Authority and Verification.
If recovery is unavailable, write **Recovery: none** and explain the consequence.
A non-stopping mechanism says why it cannot refuse.
Do not imply that retry, restart or ordinary writes repair retained invalid state.

The checker requires fields and resolving links.
Reviewers trace entry, retained state, restart behavior and exits.
Public interfaces also receive error-mapping review.
A declared absence of recovery makes a limitation visible; it does not approve the technical design.

<a id="require-failures"></a>
### Requirement: visible recovery contract

**Actor:** [Documentation checker](checking.md#documentation-checker) and semantic reviewer.

**Condition:** A mechanism can stop, refuse or remain blocked.

**Result:** Require a complete [failure declaration](#failure-declaration). Review whether the named actor can repair retained state without invoking the failing operation again.

**Verification:** Inspect complete and incomplete failure fields and trace the documented recovery.

**Tests:** [Failure completeness](acceptance.md#test-failures).

**Status:** specified.

**Basis:** [Source decision](reference.md#source-decision).
