<a id="source-format"></a>
# Source formats

This chapter specifies the encodings that connect authored Markdown, shared metadata and callable tooling. Use it after the mechanisms to construct or inspect a corpus without guessing field names. The [minimal corpus](minimal-corpus.md#minimal-example) supplies complete inputs for capacity `2`, refusal `Full` and assignment `example#main`.

Markdown uses CommonMark with pipe tables. JSON keys are case-sensitive; duplicate and unknown keys are errors. The [skills/spec-writing/references/format-contract.json](../../../skills/spec-writing/references/format-contract.json) contains the same vocabularies as this chapter. The separate prose profile belongs to [rules/writing.md](../../../rules/writing.md).

<a id="sources-and-commands"></a>
## Sources and commands

These commands select which source is checked, projected or delivered to an agent. Invoke the shared helper with its owning runtime inputs; invoking it does not install packages.

```text
python skills/spec-writing/scripts/spec_docs.py check --root REPOSITORY
python skills/spec-writing/scripts/spec_docs.py generate --root REPOSITORY
python skills/spec-writing/scripts/spec_docs.py context --root REPOSITORY --assignment FILE
```

The default captures working-tree Markdown and metadata, including unignored new files. `--staged` reads the complete index. `--rev REV` reads the resolved commit. These last two switches are mutually exclusive. `--base REV` adds a comparison base for requirement changes; a base before adoption can contain neither metadata file, but partial metadata remains invalid.

`--assignment FILE` supplies context selectors, affected-test review input and removal decisions. Context requires that option. `--format-contract FILE` selects an explicit format contract; the normal default belongs to the shared helper. `--json` emits structured output. `--fixture` permits synthetic `fixture` approval authority for teaching and tests only.

Every candidate Markdown file needs an inventory classification. Paths use forward slashes and are repository-relative, with no empty, `.` or `..` components. Source text is UTF-8. Symlinks and nonregular source inputs are refused. Code and asset links use file inventory for existence checks without loading unrelated binary bytes. External URLs receive syntax checks without network access.

The public exit meanings are:

| Status | Meaning |
|---|---|
| `0` | Successful operation |
| `1` | Document or selection errors |
| `2` | Invocation, environment or I/O failure |

Warnings do not change success. Text checking prints each source-addressed finding and final error and warning counts. JSON checking returns `errors`, `warnings` and `ok`, plus `changes` when comparing a base. Each diagnostic has `path`, `line`, `code`, `message` and `severity`. Generation returns the generated path list. Context returns its complete text or, with `--json`, `content`, `size_bytes` and `manifest`.

Generation validates all proposed bytes before replacing any destination. Replacement is atomic per file, not across the whole generated set. Mixed authored destinations must still match captured bytes. An interrupted set requires regeneration; neither checking nor dispatch treats an old output as a successful substitute.

Runtime metadata declares CPython `>=3.11,<3.15`. The owning [skills/spec-writing/scripts/runtime.json](../../../skills/spec-writing/scripts/runtime.json) and [skills/spec-writing/scripts/requirements.lock](../../../skills/spec-writing/scripts/requirements.lock) are checked at initialization. Installed `markdown-it-py` and `mdurl` versions must match the lock. The supported range is a compatibility contract, not a claim that every interpreter has been tested.

<a id="metadata"></a>
## Metadata

Metadata identifies the files and homes that source selection can use. The two version-1 envelopes are exact; arrays can be empty unless their field requires entries.

```json
{"version": 1, "inventory": [], "documents": []}
```

```json
{"version": 1, "entities": {}, "naming_rules": []}
```

The first envelope belongs to [docs/DOCUMENTS.json](../../DOCUMENTS.json). An inventory entry has `path` and `kind`, with optional `reason`; `other` requires a nonempty reason. A document has the required fields shown below. The final `approval`, `gaps` and `unresolved_contracts` fields are optional.

**Entities in this example:** [Scenario](requirements-tests-and-failures.md#scenario).

```json
{
  "id": "example",
  "title": "Bounded batches",
  "status": "draft",
  "purpose": "Show bounded submission and refusal.",
  "audience": "Authors familiar with Markdown.",
  "scope": "One synthetic submission rule.",
  "non_goals": "A production service.",
  "navigation": {"path": "docs/example.md", "region": "example"},
  "sections": [{
    "id": "main", "path": "docs/example.md", "anchor": "example",
    "roles": ["tour", "mechanism", "requirements", "decisions", "questions", "reference", "acceptance"],
    "summary": "Follow submission and inspect its evidence.",
    "prerequisites": [], "explanatory_dependencies": []
  }],
  "scenarios": [],
  "approval": {"authority": "fixture", "decision": "example#decision"},
  "gaps": [],
  "unresolved_contracts": []
}
```

This shape uses the teaching document's identity. `main` is its registered section identity; `example` is the explicit anchor that starts its source subtree. Each `roles` element describes content inside that subtree, in reading order. `summary` tells readers what they can do there. The example's empty prerequisite and dependency arrays make no claim that other material is needed.

`navigation.region`, when present, equals the document identity and selects markers inside an authored source file. Without `region`, `navigation.path` names a whole output under `docs/generated/`. Approval needs an `authority` and a resolving `document#anchor` decision. Production authorities are `operator` and `delegated`; `fixture` requires fixture mode and never authorizes production behavior.

`gaps` names missing roles waived only for a draft. Every retained `unresolved_contracts` selector blocks an approved document. These selectors must resolve. The checker establishes resolution; review establishes whether the decision's authority and content justify approval.

Sections are ordered objects with exactly `id`, `path`, `anchor`, `roles`, `summary`, `prerequisites` and `explanatory_dependencies`. A dependency has exactly `section` and `reason`. Prerequisites and dependency targets use registered `document#section` selectors. [Scenarios](requirements-tests-and-failures.md#scenario) use declaration selectors; a nonempty scenarios array must name existing scenario declarations.

Every chapter opening belongs to a registered subtree. In a multi-file document, the filename equals the first heading's slug plus `.md`. Slugs case-fold words, remove punctuation, join words with hyphens and replace underscores with hyphens. A single-file document keeps its document filename. There is no abbreviation map.

A summary must add a reader outcome beyond its title. `D36` compares case-folded words after removing punctuation and a leading “Understand”, “Learn about”, “Read about” or “Overview of”. A summary with no remaining word beyond the title fails. For more than five sections, `W06` warns when all prerequisites form only a predecessor chain after an empty first list.

`D35` detects an authored sentence of at least eight whitespace-separated words repeated at least three times in one document. It normalizes whitespace. Generated regions, literal blocks, attributed quotations, table cells and declaration fields are excluded. Ordinary detail prose and list paragraphs remain in scope.

The second envelope belongs to [docs/ENTITIES.json](../../ENTITIES.json). Its `entities` object maps stable identities to records with exactly these keys:

```json
{
  "kind": "component",
  "home": {"section": "example#main", "anchor": "batcher"},
  "scope": ["example"],
  "forms": ["batcher"],
  "symbols": [],
  "rejected_forms": []
}
```

The `home` selects the batcher's complete heading subtree. `scope` lists document identities where it may be used and includes the home document. `forms` lists accepted phrases, matched without case distinction; `symbols` lists exact code spellings. An empty `symbols` array declares none. Each rejected form instead has `text`, `replacement` and `reason`, all nonempty strings.

Naming rules check a selected entity kind's accepted forms or symbols. Each record has `id`, `kind`, `field`, `pattern` and `message`. `field` is `forms` or `symbols`; `pattern` is a Python regular expression applied with full-match semantics. Invalid expressions fail visibly, and duplicate rule identities are errors.

The following block supplies every allowed vocabulary and required declaration field. List order matters for the document roles. The `group_separators` characters are comma, underscore, ordinary space, no-break space and narrow no-break space.

**Entities in this example:** [Scenario](requirements-tests-and-failures.md#scenario).

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

A fact's Status is nonempty literal text, rather than a member of `document_statuses`. For example, `specified` qualifies a declared teaching value. Basis is also nonempty and contains a resolving link. No field in this contract introduces a unit or value-type system.

<a id="markdown-declarations"></a>
## Markdown declarations

Markdown declarations make a contract's values and evidence addressable without moving their meaning into metadata. The batcher uses an explicit home anchor followed immediately by its heading and definition.

```markdown
<a id="batcher"></a>
## Batcher

A batcher prevents overfilling by accepting items only while its batch has room.
```

Use an empty `<a id="stable-anchor"></a>` anchor with the intended identity. The source form is `<a id="batcher"></a>`; `name` does not substitute for `id`. Generated regions cannot supply authored homes. The home extends through its heading subtree, and its first definition sentence enters generated navigation and registry output.

Facts use precisely `Key | Value | Status | Basis` columns. Each Key cell contains its key text and exactly one explicit anchor; the row has no other anchor. The fact identity combines owner identity and key, such as `example.batcher#capacity`, while links target the row's `capacity` anchor.

```markdown
| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="capacity"></a>capacity | 2 | specified | [Teaching decision](#decision) |
```

Here `2` counts items admitted to one batch. `specified` states the declaration's qualification, and the teaching decision supplies its basis. A link labelled `capacity`, the owner's heading, an accepted form or an exact symbol is descriptive. Other labels claim a value and must match the cell after normalization. Thus `[3](#capacity)` fails with `D10`.

Normalization removes surrounding space and supported group separators within integer digit runs grouped in threes. Inline Markdown formatting is removed; code-span content remains literal. Decimal points, case, punctuation and other spacing remain significant. There is no expression evaluation, range interpretation or measurement conversion. Keep qualifications beside their home with a direct link to the fact so change reporting can include them.

Relations use precisely `Key | Predicate | Target | Basis` columns. Target contains one direct link to a registered home of a kind permitted for that predicate. Basis contains a link. The vocabulary block specifies the allowed `performed-by`, `protected-by`, `limited-by` and `precedes` targets.

**Entities in this example:** [Acceptance test](requirements-tests-and-failures.md#acceptance-test), [scenario](requirements-tests-and-failures.md#scenario).

Declarations have an immediately preceding explicit anchor and a heading beginning `Requirement:`, `Acceptance test:`, `Failure state:` or `Scenario:`. A permanent `test-` anchor also identifies an acceptance case when its heading omits that prefix. Requirement anchors use `req-` and test anchors use `test-`, followed by nonempty lower-case letters or digits separated by single hyphens. Preserve identities for unchanged obligations and cases.

Required bold fields appear once per declaration heading. Each field occupies a separate paragraph. For example, `**Result:** Return Full without changing the batch.` Requirements link tests through `Tests`; acceptance cases link back through `Requirements`. A failure's `Authority` identifies the recovery actor and authority. Explicitly absent recovery also explains its consequence. Review checks these meanings beyond field presence.

The contract block lists required fields. Acceptance cases may add `Implementation`; [failure declarations](requirements-tests-and-failures.md#failure-declaration) may add `Actor`; scenarios may add `Requirements` and `Tests`. No other declaration fields are accepted. Decisions use separate headings and one `Rejected alternatives` field containing all rejected options and reasons.

Method is `test`, `inspection`, `analysis` or `demonstration`, ignoring case and an optional final period. Exactly Method `test` requires Implementation. Its field contains only plain-text Markdown links separated by comma and whitespace, with no final punctuation.

```markdown
**Implementation:** [tests/test_batches.py::Suite::test_full](../tests/test_batches.py), [tests/test_batches.py::Suite::test_empty](../tests/test_batches.py)
```

In that illustrative field, each label starts with the repository-relative file and appends `::selector`. The resolved relative destination must be that same file, with no scheme, query or fragment. A selector is nonempty and whitespace-free; nested names can contain `::`. Static checking validates the grammar and file existence. The [selector audit](interfaces-and-encodings.md#selector-audit) executes the named Python unittest selectors.

Other methods omit Implementation and include linked evidence such as a review lens or run record. A resolving link is necessary but does not establish adequate evidence. The bounded-batch acceptance case uses inspection of retained state instead of claiming executable batch implementation.

Literal blocks and inline code need adjacent home annotations for their registered uses. The prefix is `**Entities in this example:**`. Each block before a home has its own annotation; one annotation cannot license a later block. These annotations are not declaration fields. First-use scope, forward links and unnumbered headings follow the [Direct links](../../../rules/specifications.md#direct-links).

<a id="navigation"></a>
## Navigation

Navigation markers tell the generator where derived reading material belongs. The bounded-batch example keeps one region inside its existing source file.

```markdown
<!-- spec-docs:navigation document="example" -->
<!-- Generated by spec-docs; edit authored declarations. -->
<!-- /spec-docs:navigation -->
```

The marker pair must occur exactly once in order. Its document identity matches `navigation.region`. Generated content includes overview fields, declared gaps, the ordered section map, prerequisites and scoped entity definitions. Map links select authored destinations, including anchored level-2 headings within each section subtree. The region omits a duplicate entry title.

Place the region after the entry's opening paragraph and introductory Mermaid diagram with its adjacent home annotation. Without that diagram, placement follows the opening paragraph. The generator derives the insertion point from parsed authored content rather than generated headings.

Whole-file destinations live under `docs/generated/`. Their generated-file attributes appear between `# spec-docs:generated` and `# /spec-docs:generated` in `.gitattributes`. Each line uses a quoted repository path followed by `linguist-generated=true`. A source file containing a region is not marked wholly generated.

<a id="callable-core-and-context-assignment"></a>
## Callable core and context assignment

The callable interface lets integrators reuse the parsed model for checking, projection and selection. Import the shared module from its owning scripts directory; a consumer does not copy it into a private implementation.

```python
Snapshot.from_mapping(paths, fixture=False)
Snapshot.from_git(root, staged=False, rev=None, fixture=False)
load_corpus(source, format_contract=None, *, comparison=False)
check(corpus, base=None)
generate_navigation(corpus)
requirement_changes(base, candidate)
select_context(corpus, assignment)
```

`paths` maps repository paths to strings or bytes. Loading parses declared Markdown once. `comparison=True` permits a base with neither metadata file; it does not permit partial metadata or missing metadata in ordinary checking. `check` returns `Diagnostics`, exposing `errors`, `warnings`, `ok` and `to_dict()`. Projection returns proposed path-to-bytes output without writing it.

`requirement_changes` returns a `ChangeReport` whose `to_dict()` contains `changes`. Each change has `id`, `kind` (`new`, `changed` or `removed`), `base`, `candidate`, `tests`, `added_tests`, `removed_tests` and `changed_facts`. [Requirement declarations](requirements-tests-and-failures.md#requirement-declaration) remain full source text. Facts contain their identity plus base and candidate contracts for value, status, basis, basis targets and qualifications.

Set `candidate.base = base` before selection to include comparison evidence and enforce removal decisions and affected-test input. The report compares requirements by their permanent anchors, including moves between documents. It selects tests from both snapshots when a declaration or directly linked fact contract changes. It maintains no persistent suspect-link ledger.

An assignment has required `version` and a nonempty `sections` array. The bounded-batch assignment is `{"version": 1, "sections": ["example#main"]}`. Optional fields are:

| Field | Assignment value |
|---|---|
| [`scenarios`](requirements-tests-and-failures.md#scenario) | Whole-scenario selectors |
| `decisions` | Decision anchor selectors |
| `baseline` | Captured digest or resolved commit |
| `budget_bytes` | Nonnegative integer bytes |
| `review_plan` | Actual reviewer responsibilities |
| `required_test_reviews` | Affected test selectors |
| `removal_decisions` | Removed requirement to decision |
| `label` | `base` or `candidate` |

Each review-plan entry has `responsibilities` and optional `id`. Responsibilities use the contract vocabulary; their union must cover every required responsibility when a plan is supplied. Authoring may omit a plan. Normal review preparation supplies the plan and resolved base; direct compiler review requires `--target-base REV`. It derives required tests, while removal decisions remain explicit input.

`select_context` returns `Context`, exposing byte `content`, `size_bytes`, `manifest`, `diagnostics` and `to_dict()`. The dictionary form decodes content as UTF-8. Invalid selection raises `SpecDocsError` carrying diagnostics. The content contains manifest, [complete registry](agent-context.md#complete-registry), metadata, profile, optional change report and labelled source ranges.

The manifest contains `version`, `tool_version`, `format_version`, `profile_version`, `label`, `baseline`, `source_digest`, `registry_digest`, `input_fingerprints`, `assignment`, `included`, `inclusion_reasons`, `ranges`, `registry_size_bytes`, `metadata_size_bytes`, `profile_size_bytes`, `profile_digest` and `size_bytes`. A comparison adds `base_provenance` with its baseline, registry digest and input fingerprints.

Each range records `label`, `path`, `start`, `end`, `identities`, `reasons`, `digest` and `size_bytes`. Offsets count zero-based lines with an exclusive end; the digest is SHA-256 of that range's UTF-8 bytes. `input_fingerprints` maps metadata and declared source paths to SHA-256 digests. The source digest covers the captured content map, not a hash of every unrelated asset.

The embedded manifest's `size_bytes` equals the complete content length, including itself. The selector reaches that value before testing `budget_bytes`. This budget bounds documentation bytes only; the [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) separately bounds its complete pack. Missing or excessive mandatory input returns an error instead of a prefix of the content.
