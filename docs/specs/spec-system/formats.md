<a id="source-format"></a>
# Exact source formats, version 1

This is the declaration and callable interface contract for the shared checker.
Markdown uses CommonMark with pipe tables. JSON rejects duplicate keys and unknown
fields. The [machine-readable contract](../../../skills/spec-writing/references/format-contract.json) must agree with these formats;
the machine-readable profile in [writing rules](../../../rules/writing.md) owns
prose targets. Facts have literal values, without types or unit conversion.

<a id="sources-and-commands"></a>
## Sources and commands

Run `python skills/spec-writing/scripts/spec_docs.py check --root REPOSITORY`.
The sibling runtime and dependency lock travel with the helper; initialization
checks those owning inputs and the installed versions without installing packages.
Commands `generate` and `context` share the same inputs. `--staged` selects the
complete Git index; `--rev REV` selects a commit. They are mutually exclusive.
The default captures working-tree bytes once, including unignored new files.
Tracked Markdown must appear in `docs/DOCUMENTS.json` inventory. Every input is a
regular repository-relative UTF-8 file. Symlinks and path escapes are refused.
No network access occurs. Exit codes are 0 for no errors, 1 for document errors,
and 2 for invocation or input/output failure. Warnings never fail a command.

`--fixture` allows synthetic approval authority `fixture`. Production authorities
are `operator` and `delegated`. `--base REV` enables requirement change reporting. Changed requirements require
linked-test review selectors supplied through `--assignment`.
`context --assignment FILE` reads the assignment below. `--json` emits structured
results. Generation owns only declared files or regions, validates the complete
proposed output, then replaces destinations. A region destination must still match
the selected snapshot, so generation cannot overwrite intervening authored edits. A partial replacement fails visibly;
regeneration repairs the set.

<a id="metadata"></a>
## Metadata

All keys below are exact and case-sensitive. No unlisted key is allowed.
Every `version` is the integer `1`, not a string or Boolean.
Text fields are nonempty strings. Arrays may be empty unless stated otherwise.
Paths are repository-relative regular UTF-8 inputs without `.` or `..` components.
The complete [minimal corpus](example.md#minimal-example) instantiates the required shapes.

The JSON envelopes are:

```json
{"version": 1, "inventory": [], "documents": []}
```

```json
{"version": 1, "entities": {}, "naming_rules": []}
```


`docs/ENTITIES.json` has `version: 1`, `entities` (an identity-keyed object), and
`naming_rules` (an array). Each entity has `kind`, `home` with `section` and `anchor`,
`scope` (document identities), `forms`, `symbols`, and `rejected_forms`. Each
rejected form has `text`, `replacement`, and `reason`. A naming rule has `id`,
`kind`, `field` (`forms` or `symbols`), `pattern` (Python regular expression), and
`message`. Forms and home heading names match whole phrases without regard to case; symbols match exactly.
A word character cannot adjoin a matched phrase. No pluralization or stemming occurs; list each accepted form explicitly.
Colliding phrases produce review warnings. A symbol collision is an identity error.

`docs/DOCUMENTS.json` has `version: 1`, `inventory`, and `documents`. Inventory
entries have `path` and `kind`; kind `other` also requires `reason`. Documents have
`id`, `title`, `status`, `purpose`, `audience`, `scope`, `non_goals`, `navigation`,
`sections`, and `scenarios`. Approved documents require `approval` with `authority`
and `decision`. A navigation object has `path` and optionally `region`. A section
has `id`, `path`, `anchor`, `roles`, `summary`, `prerequisites`, and
`explanatory_dependencies`; each dependency has `section` and a nonempty `reason`.
A section selector is `document#section`. An anchor selector `document#anchor`
resolves declarations and decisions. [Scenario](sources.md#scenario) entries use anchor selectors.
Optional document `unresolved_contracts` is an array of anchor selectors; an
approved document cannot retain one. Draft missing roles may declare `gaps`, an
array of role names. A gap is visible in navigation and does not authorize approval.

**Entities in this example:** [Scenario](sources.md#scenario).

Required roles are in the format contract. Purpose, audience, scope and non-goals
are manifest fields. Roles apply to nonempty section subtrees. A design inventory
entry additionally requires the design roles. An inapplicable role contains `None`
and an explanation in its source. The checker validates presence; review validates
adequacy and whether a role really is inapplicable.


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

**Entities in this example:** [Scenario](sources.md#scenario).

This shape illustrates optional fields; its reference and decision targets must be supplied in a real corpus.
`navigation.region` is optional; omit it only for a whole file under `docs/generated/`.
Approval authorities are `operator` and `delegated`; `fixture` is accepted only with `--fixture` for synthetic teaching or test data.
Fixture authority approves the example contract only and confers no production authority.
`gaps` is a list of role names that waives missing roles only for a draft.
`unresolved_contracts` lists anchor selectors; approval rejects any retained entry.
The `sections`, `scenarios`, `prerequisites`, `scope`, `forms`, and `symbols` values are arrays.
Sections are ordered; prerequisites and dependencies use `document#section` selectors.
[Scenario](sources.md#scenario), decision and unresolved-contract selectors use `document#anchor`.

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

`field` is `forms` or `symbols`. `pattern` is a Python regular expression applied with full-match semantics.
`kind` selects the entity kind to check. An invalid pattern is an input error.
The machine-readable vocabularies below list every allowed classification, status, role, entity kind, predicate target kind, required declaration field and review responsibility.
A fact's `Status` is nonempty literal text; examples use `specified`, `provisional`, `observed` and `unresolved`, without introducing a value-type system.
Declaration `Method`, `Status` and `Basis` values are nonempty prose, with links required where declared below.

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
    "acceptance",
    "decisions",
    "questions",
    "reference"
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

**Entities in this example:** [Scenario](sources.md#scenario).

<a id="markdown-declarations"></a>
## Markdown declarations

An empty `<a id="stable-anchor"></a>` immediately precedes each home heading.
The first paragraph defines the entity. The home includes its whole heading
subtree. Heading titles and meanings enter the generated [complete registry](context.md#complete-registry).
Generated regions cannot provide declarations. Each heading starts a new first-use
scope, independently of subtree extraction for assignment.

A `Key | Value | Status | Basis` table declares facts in its containing entity
home. Each Key cell contains exactly one explicit anchor and its key text. Fact
identities are `entity-identity#key`; destinations use the row anchor. Markdown
formatting is removed from cell text; code-span text remains literal. Trim outer
spaces and remove commas, underscores or grouping spaces only in digit runs
with groups of three. Preserve decimals, punctuation, case and other spacing.
A fact link whose label equals its key or an accepted form, symbol or heading name
of its owner is descriptive. Every other label must equal the literal home value
under that normalization. Status and Basis are nonempty; Basis contains a link.
Qualifications remain adjacent prose referring directly to the fact.

`Key | Predicate | Target | Basis` tables declare relations. Predicates and target
kinds are listed in the format contract. Target and Basis contain direct links.
Requirement, test, failure and [scenario](sources.md#scenario) headings start respectively with
`Requirement:`, `Acceptance test:`, `Failure state:`, and `Scenario:`. They have an
explicit anchor and bold field paragraphs, for example `**Actor:** [Writer](#writer)`.
Required field names are listed in the contract. Tests and requirements declare
reciprocal links through their Tests and Requirements fields. Failure Authority
names the recovery actor and authority. `Recovery: none` includes the consequence
in the field or adjacent explanation. Review checks those meanings.

**Entities in this example:** [Acceptance test](sources.md#acceptance-test), [Scenario](sources.md#scenario).

Only acceptance cases may add `Implementation`; [failure declarations](sources.md#failure-declaration) may add `Actor`.
[Scenarios](sources.md#scenario) may add `Requirements` and `Tests` links.
No other declaration field is allowed.
Adjacent **Entities in this example** annotations apply to each literal block and are not declaration fields.

Requirement anchors use `req-<identity>` and acceptance-test anchors use
`test-<identity>`. The suffix is nonempty lower-case kebab case: letters or digits
separated by single hyphens. The complete anchor is the permanent identity under
[specification identity rules](../../../rules/specifications.md),
unique across the repository's specification and design corpus, including retired
declarations. It is independent of file, heading and wording; never reuse it after
retirement. Git history carries revisions outside the identity. A heading describes
the obligation or case; its text need not match the anchor suffix.

The optional acceptance-test `Implementation` field has exactly this grammar:
one or more Markdown links, separated by a comma and whitespace, with no other prose
or terminal punctuation. Each plain-text link label is `repository-file::selector`.
The file is repository-relative and must match the link's resolved destination.
The destination is a relative path to that file, with no URL scheme, query or fragment.
The selector is a nonempty whitespace-free test name; it may include `::` for nesting.
For example, from a document one directory below the repository root:

```markdown
**Implementation:** [tests/test_x.py::test_rejects_stale](../tests/test_x.py), [tests/test_x.py::Suite::test_accepts_current](../tests/test_x.py)
```

The checker validates this grammar and resolves every file against the selected
snapshot. It retains the selector in the parsed field for the later spec-to-code
pass; it does not establish that the named test exists or passes. Omit the field
when no executable test is linked; explain planned evidence in ordinary prose.

Literal blocks, signatures, diagrams and code spans use adjacent
`**Entities in this example:**` direct home links when they contain registered
symbols or phrases. Each separate literal block before a home needs its own
annotation. Literal languages are not parsed for bindings. Definitions and their
introductory paragraphs need no self-links. Prose first uses and every forward use
link directly to the entity home or one of its facts.

Procedure structure and prose counting follow the [writing rules](../../../rules/writing.md).
They are not separate format policies.

<a id="navigation"></a>
## Navigation

Each document gets one output containing its overview, ordered document map, and
[entity index](sources.md#entity-index). A region goes immediately after the entry title and opening paragraph.
The map lists every chapter and links each level-2 heading in its registered subtree.
Each mapped heading has an explicit anchor. A region does not repeat the entry title. It projects authored title, purpose, audience, scope, non-goals,
section summaries, prerequisites and entity meanings. Links point to source.
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

Import `spec_docs` from the scripts directory. `Snapshot.from_git(root, staged=False,
rev=None)` captures one source; `Snapshot.from_mapping(paths, fixture=False)` is
useful for integration and fixtures. `load_corpus(source, format_contract=None, comparison=False)`
parses each authored Markdown source once. The keyword `comparison=True` permits an empty pre-adoption base with neither metadata file; partial metadata still fails. Ordinary checking never permits missing metadata. `check(corpus, base=None)` returns
`Diagnostics` with `errors`, `warnings`, `ok`, and `to_dict()`.
`generate_navigation(corpus)` returns repository-relative paths to bytes.
`requirement_changes(base, candidate)` returns a `ChangeReport` with `changes` and
`to_dict()`. Set `candidate.base = base` to check removal decisions and test-review
inputs during selection and include labelled base test ranges and changed declarations.
`select_context(corpus, assignment)` returns `Context` with `content`
(bytes), `size_bytes`, `manifest`, and `to_dict()`. Invalid selections raise
`SpecDocsError` with diagnostics. Context selection requires a checked snapshot.

Assignment JSON has `version: 1` and nonempty `sections` (explicit selectors).
Optional fields are `scenarios` (whole-[scenario](sources.md#scenario) selectors), `decisions` (anchor
selectors), `baseline` (snapshot digest or commit revision), `budget_bytes`,
`review_plan`, `required_test_reviews`, `removal_decisions`,
and `label` (`base` or `candidate`). Every removal decision maps a removed
requirement selector to a resolving decision selector. Review-plan entries have
`responsibilities`, an array of contract responsibility names. A single entry may
cover several responsibilities. `required_test_reviews` lists selected test
selectors from change reporting; their complete ranges are mandatory.

**Entities in this example:** [Scenario](sources.md#scenario).

The single `budget_bytes` field bounds documentation context bytes.
The [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) separately bounds the complete pack, including rules and task text.
Authoring assignments may omit a review plan.
Review [dispatchers](../../design/75-subagent-profiles.md#dispatcher) supply the responsibilities of their actual reviewers and validate full coverage.
Normal review preparation passes the already-resolved base revision to the selector.
Direct review compiler calls require `--target-base REV`.
It derives required test selectors from the base/candidate change report.
Removal decisions remain explicit assignment input from the work item.

The output contains the [complete registry](context.md#complete-registry), unique assigned ranges, transitive
explanatory dependencies, relevant complete homes, metadata, profile, decisions,
and provenance. Ranges overlap by source lines and are merged, with all inclusion
reasons retained. Ordinary links in an added home never recursively add homes.
Its containing section's declared dependencies do expand. The registry contains
all entities, names, meanings, homes, facts, statuses and bases, even outside the
assignment. The manifest records input fingerprints, snapshot and registry
digests, tool/format/profile versions, labels, assignment and reasons. Size is
exact UTF-8 bytes of `content`; the manifest is embedded in that content. Budget
refusal never truncates. The returned manifest size is the same byte count.

Changes to requirement fields or directly linked facts (including Status, Basis,
and adjacent fact qualifications) select tests from both snapshots. Removed
requirements need a resolving decision supplied by the work item through
`removal_decisions`. Declarations and changed facts remain separately labelled
base and candidate. There is no stored traceability ledger.
