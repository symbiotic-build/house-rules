<a id="source-format"></a>
# Source formats

This is the declaration and callable interface contract for the shared checker.
Markdown uses CommonMark with pipe tables. JSON rejects duplicate keys and unknown
fields. The [skills/spec-writing/references/format-contract.json](../../../skills/spec-writing/references/format-contract.json) must agree with these formats;
the machine-readable profile in [rules/writing.md](../../../rules/writing.md) owns
prose targets. Facts have literal values, without types or unit conversion.

<a id="sources-and-commands"></a>
## Sources and commands

These interfaces let callers check, regenerate or select the bounded-batch example from a chosen snapshot.

Run `python skills/spec-writing/scripts/spec_docs.py check --root REPOSITORY`.
The sibling runtime and dependency lock travel with the helper; initialization
checks those owning inputs and the installed versions without installing packages.
Commands `generate` and `context` share the same inputs.

`--staged` selects the
complete Git index; `--rev REV` selects a commit.
They are mutually exclusive.
The default captures working-tree bytes once, including unignored new files.

Tracked Markdown must appear in `docs/DOCUMENTS.json` inventory.
Every input is a
regular repository-relative UTF-8 file.
Symlinks and path escapes are refused.

No network access occurs.
Exit codes are [success](documentation-checker.md#checker-success), [document-errors](documentation-checker.md#checker-document-errors),
and [invocation-failure](documentation-checker.md#checker-invocation-failure).
Warnings never fail a command.


`--fixture` allows synthetic approval authority `fixture`.
Production authorities
are `operator` and `delegated`.
`--base REV` enables requirement change reporting.

Changed requirements require
linked-test review selectors supplied through `--assignment`.
`context --assignment FILE` reads the assignment below.
`--json` emits structured
results.

Generation owns only declared files or regions, validates the complete
proposed output, then replaces destinations.
A region destination must still match
the selected snapshot, so generation cannot overwrite intervening authored edits.
A partial replacement fails visibly;
regeneration repairs the set.


<a id="metadata"></a>
## Metadata

These shapes let authors register the bounded-batch files without guessing required keys.

All keys below are exact and case-sensitive.
No unlisted key is allowed.
Every `version` is the integer `1`, not a string or Boolean.

Text fields are nonempty strings.
Arrays may be empty unless stated otherwise.
Paths are repository-relative regular UTF-8 inputs without `.` or `..` components.

The complete [minimal corpus](minimal-corpus.md#minimal-example) instantiates the required shapes.


The JSON envelopes are:

```json
{"version": 1, "inventory": [], "documents": []}
```

```json
{"version": 1, "entities": {}, "naming_rules": []}
```


[docs/ENTITIES.json](../../ENTITIES.json) uses an identity-keyed `entities` object and a `naming_rules` array.
[docs/DOCUMENTS.json](../../DOCUMENTS.json) uses `inventory` and ordered `documents` arrays.
The complete shapes below define their keys; the contract block defines allowed vocabularies.
The contract block's ordered `roles` array defines the reading sequence checked by `D15`.

Section roles may share a position only when adjacent roles are combined in one section.
The section array places the tour before mechanisms, and acceptance after reference.
Every authored heading and paragraph belongs to a registered section subtree, including each chapter's opening.

For a multi-file document, each chapter filename is the slug of its first heading plus
`.md`.
A slug uses lowercase words separated by hyphens, with punctuation removed and underscores
replaced by hyphens. For example, "Batch admission" becomes `batch-admission.md`.
There is no short-name mapping. Single-file documents retain their document filename.
A mismatch is error `D34`.

A section summary states what the reader learns or can do there.
"Batch admission" might use "Determine whether a batch fits and what a refusal retains".
Error `D36` rejects summaries with no word beyond the title.
Comparison ignores case and punctuation and removes a leading "Understand", "Learn about",
"Read about" or "Overview of".

Prerequisites list only chapters whose concepts the section cannot be read without.
For more than five sections, warning `W06` flags an empty first prerequisite list followed
entirely by single-predecessor lists. Review actual conceptual dependencies.

Error `D35` rejects any sentence of at least eight whitespace-separated words that occurs
three or more times within a document's chapters, after whitespace normalization.
It checks authored paragraph prose, including lists and ordinary detail blocks, but excludes
generated regions, literal blocks, attributed quotations, table cells and declaration fields.
Reuse the continuing example at each concept's introduction instead of a closing formula.

Register a chapter's title anchor to include that opening; registering only its later level-2 sections leaves the opening unassigned.
Reader progression follows [rules/specifications.md](../../../rules/specifications.md#reader-progression).


Each inventory entry is `{"path": "docs/example.md", "kind": "specification"}`;
`reason` is the only optional key and is required for `other`.
Each document has this shape (the last three keys are optional):

```json
{
  "id": "example", "title": "Example", "status": "draft",
  "purpose": "Explain one contract.", "audience": "Authors.",
  "scope": "One example.", "non_goals": "Production behavior.",
  "navigation": {"path": "docs/example.md", "region": "example"},
  "sections": [{
    "id": "main", "path": "docs/example.md", "anchor": "example",
    "roles": ["tour"], "summary": "Follow the example.",
    "prerequisites": [],
    "explanatory_dependencies": [{"section": "example#reference", "reason": "Explains the fields."}]
  }],
  "scenarios": [],
  "approval": {"authority": "operator", "decision": "example#decision"},
  "gaps": ["mechanism"], "unresolved_contracts": ["example#pending"]
}
```

**Entities in this example:** [Scenario](scenario.md#scenario).

This shape illustrates optional fields; its reference and decision targets must be supplied in a real corpus.
`navigation.region` is optional; omit it only for a whole file under `docs/generated/`.
Approval authorities are `operator` and `delegated`; `fixture` is accepted only with `--fixture` for synthetic teaching or test data.

Fixture authority approves the example contract only and confers no production authority.
`gaps` is a list of role names that waives missing roles only for a draft.
`unresolved_contracts` lists anchor selectors; approval rejects any retained entry.

The `sections`, `scenarios`, `prerequisites`, `scope`, `forms`, and `symbols` values are arrays.
Sections are ordered; prerequisites and dependencies use `document#section` selectors.
[Scenario](scenario.md#scenario), decision and unresolved-contract selectors use `document#anchor`.

**Entities in this example:** [Scenario](scenario.md#scenario).


Each identity-keyed entity has exactly this shape:

```json
{
  "kind": "component",
  "home": {"section": "example#main", "anchor": "batcher"},
  "scope": ["example"], "forms": ["batcher"], "symbols": ["Batcher"],
  "rejected_forms": [{"text": "batch gate", "replacement": "batcher", "reason": "Use one name."}]
}
```

The `naming_rules` array contains objects with exactly these keys:

```json
{"id": "component-symbol", "kind": "component", "field": "symbols", "pattern": "^[A-Z][a-zA-Z0-9]*$", "message": "Use a capitalized symbol."}
```

`field` is `forms` or `symbols`.
`pattern` is a Python regular expression applied with full-match semantics.
`kind` selects the entity kind to check.

An invalid pattern is an input error.
The machine-readable vocabularies below list every allowed classification, status, role, entity kind, predicate target kind, required declaration field and review responsibility.
A fact's `Status` is nonempty literal text; examples use `specified`, `provisional`, `observed` and `unresolved`, without introducing a value-type system.

Declaration Method is `test`, `inspection`, `analysis` or `demonstration`.
Status and Basis are nonempty prose.
The declaration rules below identify required links.


```json format-contract
{
  "version": 1,
  "entity_kinds": [
    "component",
    "mechanism",
    "setting",
    "concept",
    "interface",
    "state",
    "actor",
    "data"
  ],
  "inventory_kinds": [
    "specification",
    "design",
    "other",
    "generated"
  ],
  "document_statuses": [
    "draft",
    "approved",
    "implemented",
    "superseded"
  ],
  "roles": [
    "tour",
    "mechanism",
    "requirements",
    "decisions",
    "questions",
    "reference",
    "acceptance"
  ],
  "design_roles": [
    "evidence",
    "constraints",
    "alternatives",
    "ownership",
    "integration",
    "rollout",
    "work-packages",
    "acceptance-evidence"
  ],
  "relationship_targets": {
    "performed-by": [
      "actor",
      "component"
    ],
    "protected-by": [
      "mechanism",
      "component"
    ],
    "limited-by": [
      "setting"
    ],
    "precedes": [
      "component",
      "mechanism",
      "setting",
      "concept",
      "interface",
      "state",
      "actor",
      "data"
    ]
  },
  "requirement_fields": [
    "Actor",
    "Condition",
    "Result",
    "Verification",
    "Tests",
    "Status",
    "Basis"
  ],
  "test_fields": [
    "Method",
    "Requirements",
    "Inputs",
    "Expected"
  ],
  "failure_fields": [
    "Trigger",
    "Outcome",
    "Retained state",
    "Recovery",
    "Authority",
    "Verification"
  ],
  "scenario_fields": [
    "Purpose",
    "Inputs",
    "Expected"
  ],
  "review_responsibilities": [
    "technical",
    "readability",
    "design/cost",
    "failure/recovery",
    "whole-scenario"
  ],
  "group_separators": [
    ",",
    "_",
    " ",
    " ",
    " "
  ]
}
```

**Entities in this example:** [Scenario](scenario.md#scenario).

<a id="markdown-declarations"></a>
## Markdown declarations

These encodings make the batcher's homes, facts and evidence addressable by the checker.

An empty `<a id="stable-anchor"></a>` immediately precedes each home heading.
The opening follows the [entity-definition rule](../../../rules/specifications.md#reader-progression).
The home includes its whole heading
subtree.

Heading titles and meanings enter the generated [complete registry](complete-registry.md#complete-registry).
Generated regions cannot provide declarations.
Linking and heading policy belongs to [rules/specifications.md](../../../rules/specifications.md#direct-links).

For an exact repository-file label, write [INDEX.md](../../../INDEX.md).
Named-section links instead use the section name.
Implementation labels append their selector.


A `Key | Value | Status | Basis` table declares facts in its containing entity
home.
Each Key cell contains exactly one explicit anchor and its key text.
Fact
identities are `entity-identity#key`; destinations use the row anchor.

Markdown
formatting is removed from cell text; code-span text remains literal.
Trim outer
spaces and remove commas, underscores or grouping spaces only in digit runs
with groups of three.
Preserve decimals, punctuation, case and other spacing.

A fact link whose label equals its key or an accepted form, symbol or heading name
of its owner is descriptive.
Every other label must equal the literal home value
under that normalization.
Status and Basis are nonempty; Basis contains a link.

Qualifications remain adjacent prose referring directly to the fact.
For example:


```markdown
**Qualification for [capacity](#capacity):** Confirm this provisional value before deployment.
```

`Key | Predicate | Target | Basis` tables declare relations.
Predicates and target
kinds are listed in the format contract.
Target and Basis contain direct links.

Requirement, failure and [scenario](scenario.md#scenario) headings start respectively with
`Requirement:`, `Failure state:`, and `Scenario:`.
An acceptance case is identified by its permanent `test-` anchor; its heading may omit `Acceptance test:`.
A bold field label appears once per declaration or decision heading.
One Rejected alternatives field contains all options and their reasons.
Declarations have an
explicit anchor and bold field paragraphs, for example `**Actor:** [Batcher](#batcher)`.

**Entities in this example:** [Scenario](scenario.md#scenario), [Acceptance test](acceptance-test.md#acceptance-test).

A scenario uses `### Scenario: capacity repair` and an immediately preceding explicit anchor.
Its Purpose, Inputs and Expected fields describe the story; Requirements and Tests link its evidence.
Required field names are listed in the contract.

**Entities in this example:** [Scenario](scenario.md#scenario).

Tests and requirements declare
reciprocal links through their Tests and Requirements fields.
Failure Authority
names the recovery actor and authority.
`Recovery: none` includes the consequence
in the field or adjacent explanation.

Review checks those meanings.


**Entities in this example:** [Acceptance test](acceptance-test.md#acceptance-test), [Scenario](scenario.md#scenario).

Only acceptance cases may add `Implementation`; [failure declarations](failure-declaration.md#failure-declaration) may add `Actor`.
[Scenarios](scenario.md#scenario) may add `Requirements` and `Tests` links.
No other declaration field is allowed.
Adjacent **Entities in this example** annotations apply to each literal block and are not declaration fields.

Requirement anchors use `req-<identity>` and acceptance-test anchors use
`test-<identity>`. The suffix is nonempty lower-case kebab case: letters or digits
separated by single hyphens. Identity permanence and historical verification belong to [rules/specifications.md](../../../rules/specifications.md#requirements-tests-and-recovery).

Method `test` requires an `Implementation` field containing Markdown links.
Separate links with a comma and whitespace.
Add no other prose or terminal punctuation.
Each plain-text link label is `repository-file::selector`.

The file is repository-relative and must match the link's resolved destination.
The destination is a relative path to that file, with no URL scheme, query or fragment.

The selector is a nonempty whitespace-free test name; it may include `::` for nesting.
For example, from a document one directory below the repository root:

```markdown
**Implementation:** [tests/test_batches.py::Suite::test_full](../tests/test_batches.py), [tests/test_batches.py::Suite::test_empty](../tests/test_batches.py)
```

The checker validates this grammar and resolves every file against the selected
snapshot. It retains the selector in the parsed field for the later spec-to-code
pass. Run `audit_selectors.py --root REPOSITORY` to establish whether each named test exists and passes. Omit the field
for Method `inspection`, `analysis` or `demonstration`; name the review lens or run record in a linked evidence paragraph.
The selector audit executes Python unittest selectors, including `Class::test_method`; unsupported executable files fail visibly.

Literal-example annotations have the exact prefix `**Entities in this example:**` followed by direct home links.
For example: `**Entities in this example:** [Batcher](#batcher)`.

Procedure structure and prose counting follow the [rules/writing.md](../../../rules/writing.md).
They are not separate format policies.

<a id="navigation"></a>
## Navigation

These markers identify the exact output region that readers can rebuild from the example.

Each document gets one output containing its overview, ordered document map, and
[entity index](entity-index.md#entity-index).
A region follows the entry opening and its overview diagram with adjacent home annotations.
Without an introductory diagram, it follows the opening paragraph.
The map lists every chapter and links each level-2 heading in its registered subtree.

Each mapped heading has an explicit anchor.
A region does not repeat the entry title.
It projects authored title, purpose, audience, scope, non-goals,
section summaries, prerequisites and entity meanings.

Links point to source.
Single-file output is enclosed by exactly one pair of markers:


```markdown
<!-- spec-docs:navigation document="document-id" -->
Generated Markdown.
<!-- /spec-docs:navigation -->
```

The navigation object names that existing file and uses `region: "document-id"`.
Whole-file outputs live under `docs/generated/`. The generator also projects
`linguist-generated=true` entries in a `.gitattributes` region delimited by
`# spec-docs:generated` and `# /spec-docs:generated` on separate lines. Source
files containing a generated region are not marked wholly generated.

<a id="callable-core-and-context-assignment"></a>
## Callable core and context assignment

These calls let an integrator prepare the same example without launching another command-line parser.

Import `spec_docs` from the scripts directory.
`Snapshot.from_git(root, staged=False,
rev=None)` captures one source; `Snapshot.from_mapping(paths, fixture=False)` is
useful for integration and fixtures.
`load_corpus(source, format_contract=None, comparison=False)`
parses each authored Markdown source once.

The keyword `comparison=True` permits an empty pre-adoption base with neither metadata file; partial metadata still fails.
Ordinary checking never permits missing metadata.
`check(corpus, base=None)` returns
`Diagnostics` with `errors`, `warnings`, `ok`, and `to_dict()`.

`generate_navigation(corpus)` returns repository-relative paths to bytes.
`requirement_changes(base, candidate)` returns a `ChangeReport` with `changes` and
`to_dict()`.
Set `candidate.base = base` to check removal decisions and test-review
inputs during selection and include labelled base test ranges and changed declarations.

`select_context(corpus, assignment)` returns `Context` with `content`
(bytes), `size_bytes`, `manifest`, and `to_dict()`.
Invalid selections raise
`SpecDocsError` with diagnostics.
Context selection requires a checked snapshot.


Assignment JSON has `version: 1` and nonempty `sections` (explicit selectors).
Optional fields are `scenarios` (whole-[scenario](scenario.md#scenario) selectors), `decisions` (anchor
selectors), `baseline` (snapshot digest or commit revision), `budget_bytes`,
`review_plan`, `required_test_reviews`, `removal_decisions`,
and `label` (`base` or `candidate`). Every removal decision maps a removed
requirement selector to a resolving decision selector. Review-plan entries have
`responsibilities`, an array of contract responsibility names. A single entry may
cover several responsibilities. `required_test_reviews` lists selected test
selectors from change reporting; their complete ranges are mandatory.

**Entities in this example:** [Scenario](scenario.md#scenario).

The single `budget_bytes` field bounds documentation context bytes.
The [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) separately bounds the complete pack, including rules and task text.
Authoring assignments may omit a review plan.

Review [dispatchers](../../design/75-subagent-profiles.md#dispatcher) supply the responsibilities of their actual reviewers and validate full coverage.
Normal review preparation passes the already-resolved base revision to the selector.
Direct review compiler calls require `--target-base REV`.

It derives required test selectors from the base/candidate change report.
Removal decisions remain explicit assignment input from the work item.


The output contains the [complete registry](complete-registry.md#complete-registry), unique assigned ranges, transitive
explanatory dependencies, relevant complete homes, metadata, profile, decisions,
and provenance.
Ranges overlap by source lines and are merged, with all inclusion
reasons retained.
Ordinary links in an added home never recursively add homes.

Its containing section's declared dependencies do expand.
The registry contains
all entities, names, meanings, homes, facts, statuses and bases, even outside the
assignment.
The manifest records input fingerprints, snapshot and registry
digests, tool/format/profile versions, labels, assignment and reasons.

Size is
exact UTF-8 bytes of `content`; the manifest is embedded in that content.
Budget
refusal never truncates.
The returned manifest size is the same byte count.


Changes to requirement fields or directly linked facts (including Status, Basis,
and adjacent fact qualifications) select tests from both snapshots. Removed
requirements need a resolving decision supplied by the work item through
`removal_decisions`. Declarations and changed facts remain separately labelled
base and candidate. There is no stored traceability ledger.
