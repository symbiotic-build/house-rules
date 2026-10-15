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

`--assignment FILE` supplies context selectors, affected-test review input and removal decisions. Context requires that option. `--format-contract FILE` selects an explicit format contract; the normal default belongs to the shared helper. `--json` emits structured output. `--fixture` permits synthetic `fixture` approval authority in test fixtures only.

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

<a id="tool-environment"></a>
## Tool environment

The tool environment is an isolated Python installation running the shared documentation tool with its owned dependency pins. It keeps consumer repositories from interpreting the same declarations through independently chosen parsers.

Use these runtime and wheel pins when preparing the shared tool. The [setup procedure](checking-and-navigation.md#tool-setup) explains the steps.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="runtime-version"></a>runtime-version | 1 | specified | [skills/spec-writing/scripts/runtime.json](../../../skills/spec-writing/scripts/runtime.json) |
| <a id="runtime-implementation"></a>implementation | CPython | specified | [skills/spec-writing/scripts/runtime.json](../../../skills/spec-writing/scripts/runtime.json) |
| <a id="runtime-python"></a>requires_python | >=3.11,<3.15 | specified | [skills/spec-writing/scripts/runtime.json](../../../skills/spec-writing/scripts/runtime.json) |
| <a id="parser-version"></a>markdown-it-py | 4.2.0 | specified | [skills/spec-writing/scripts/requirements.lock](../../../skills/spec-writing/scripts/requirements.lock) |
| <a id="url-version"></a>mdurl | 0.1.2 | specified | [skills/spec-writing/scripts/requirements.lock](../../../skills/spec-writing/scripts/requirements.lock) |
| <a id="parser-hash"></a>parser-wheel-sha256 | 9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a | specified | [skills/spec-writing/scripts/requirements.lock](../../../skills/spec-writing/scripts/requirements.lock) |
| <a id="url-hash"></a>url-wheel-sha256 | 84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8 | specified | [skills/spec-writing/scripts/requirements.lock](../../../skills/spec-writing/scripts/requirements.lock) |

The runtime version identifies the metadata format, and the interpreter rows name its implementation and supported version range. The parser package supplies Markdown tokens; its URL dependency supports link parsing. The wheel hashes identify the distributions installed from the lock. Runtime validation checks the supported interpreter range and installed package versions. It does not hash the interpreter or package installer, keep interpreter allowlists or upgrade the installer implicitly.


<a id="metadata"></a>
## Metadata

Metadata identifies the files and homes that source selection can use. The two version-1 envelopes are exact; arrays can be empty unless their field requires entries.

```json
{"version": 1, "inventory": [], "documents": []}
```

```json
{"version": 1, "entities": {}, "naming_rules": []}
```

The first envelope belongs to [docs/DOCUMENTS.json](../../DOCUMENTS.json). An inventory entry has `path` and `kind`, with optional `reason`; `other` requires a nonempty reason. A document has the required fields shown below. The `approval`, `gaps` and `unresolved_contracts` fields are optional. This draft has no approval:

**Entities in this example:** [Scenario](requirements-tests-and-failures.md#scenario).

```json
{
  "id": "example",
  "title": "Bounded batches",
  "status": "draft",
  "purpose": "The batcher accepts items until its batch fills.",
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
  "gaps": [],
  "unresolved_contracts": []
}
```

To approve an eligible completed document under delegated authority, change its status and add the following approval entry:

```json
{"status": "approved", "approval": {"authority": "delegated", "decision": "example#decision"}}
```

The decision must record the actual delegation. Copying this shape does not confer authority.
This shape uses the teaching document's identity.
 `main` is its registered section identity; `example` is the explicit anchor that starts its source subtree. Each `roles` element describes content inside that subtree, in reading order. `summary` tells readers what they can do there.

The example's empty prerequisite and dependency arrays make no claim that other material is needed.

`navigation.region`, when present, equals the document identity and selects markers inside an authored source file. Without `region`, `navigation.path` names a whole output under `docs/generated/`. Approval needs an `authority` and a resolving `document#anchor` decision. Production authorities are `operator` and `delegated`; `fixture` requires fixture mode and never authorizes production behavior.

`gaps` names missing roles waived only for a draft. Every retained `unresolved_contracts` selector blocks an approved document. These selectors must resolve. The checker establishes resolution; review establishes whether the decision's authority and content justify approval.

Sections are ordered objects with exactly `id`, `path`, `anchor`, `roles`, `summary`, `prerequisites` and `explanatory_dependencies`. A dependency has exactly `section` and `reason`. Prerequisites and dependency targets use registered `document#section` selectors. [Scenarios](requirements-tests-and-failures.md#scenario) use declaration selectors; a nonempty scenarios array must name existing scenario declarations.

Every chapter opening belongs to a registered subtree. In a multi-file document, the filename equals the first heading's slug plus `.md`. Slugs case-fold words, remove punctuation, join words with hyphens and replace underscores with hyphens. A single-file document keeps its document filename. There is no abbreviation map.

A summary must add a reader outcome beyond its title. `D36` compares case-folded words after removing punctuation and a leading “Understand”, “Learn about”, “Read about” or “Overview of”. A summary with no remaining word beyond the title fails. For more than five sections, `W06` warns when all prerequisites form only a predecessor chain after an empty first list.

`D35` detects an authored sentence of at least eight whitespace-separated words repeated at least three times in one document. It normalizes whitespace. Generated regions, literal blocks, attributed quotations, table cells and declaration fields are excluded. Ordinary detail prose and list paragraphs remain in scope.

The first envelope may also contain `test_runners`, an ordered array of entries with exactly `pattern` and `command`:

```json
{"test_runners": [{"pattern": "tests/*.spec", "command": ["sh", "tests/run-selector.sh", "{file}", "{selector}"]}]}
```

`pattern` is a case-sensitive repository-relative shell-style glob; `*` can match `/`. Duplicate patterns are invalid.

The first matching entry wins. Without a match, `.py` files use the built-in Python unittest runner; other files count as missing.
An omitted or empty array therefore keeps the built-in default.

`command` is a nonempty argument array executed from the repository root without shell interpretation.
It must contain both `{file}` and `{selector}` placeholders, with no other braces. Substitution preserves each argument, including paths with spaces.

The repository supplies the runner executable and any script it names.
A runner returns `0` for pass, `2` for a missing selector, and any other status for failure.
The [audit reference](interfaces-and-encodings.md#selector-audit) defines runaway handling and outcome counts.

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

These compact tables list the vocabularies and required declaration fields. The [machine-readable contract](../../../skills/spec-writing/references/format-contract.json) supplies the complete JSON reference.
Roles preserve their listed reading order; a design can also use the design-specific roles.

**Entities in this example:** [Scenario](requirements-tests-and-failures.md#scenario).

| Field | Allowed values or required fields |
|---|---|
| `entity_kinds` | `component`, `mechanism`, `setting`, `concept`, `interface`, `state`, `actor`, `data` |
| `inventory_kinds` | `specification`, `design`, `other`, `generated` |
| `document_statuses` | `draft`, `approved`, `implemented`, `superseded` |
| `roles` | `tour`, `mechanism`, `requirements`, `decisions`, `questions`, `reference`, `acceptance` |
| `design_roles` | `evidence`, `constraints`, `alternatives`, `ownership`, `integration`, `rollout`, `work-packages`, `acceptance-evidence` |
| `requirement_fields` | `Actor`, `Condition`, `Result`, `Verification`, `Tests`, `Status`, `Basis` |
| `test_fields` | `Method`, `Requirements`, `Inputs`, `Expected` |
| `failure_fields` | `Trigger`, `Outcome`, `Retained state`, `Recovery`, `Authority`, `Verification` |
| `scenario_fields` | `Purpose`, `Inputs`, `Expected` |
| `review_responsibilities` | `technical`, `readability`, `design/cost`, `failure/recovery`, [`whole-scenario`](requirements-tests-and-failures.md#scenario) |

| Relation predicate | Permitted target kinds |
|---|---|
| `performed-by` | `actor`, `component` |
| `protected-by` | `mechanism`, `component` |
| `limited-by` | `setting` |
| `precedes` | `component`, `mechanism`, `setting`, `concept`, `interface`, `state`, `actor`, `data` |

`group_separators` contains comma, underscore, ordinary space, no-break space and narrow no-break space.

A fact's Status is nonempty literal text, rather than a member of `document_statuses`. For example, `specified` qualifies a declared teaching value. Basis is also nonempty and contains a resolving link. No field in this contract introduces a unit or value-type system.

<a id="markdown-declarations"></a>
## Markdown declarations

Markdown declarations make a contract's values and evidence addressable without moving their meaning into metadata. The batcher uses an explicit home anchor followed immediately by its heading and definition.

```markdown
<a id="batcher"></a>
## Batcher

A batcher prevents overfilling by accepting items only while its batch has room.
```

Use the empty `id` anchor form shown above with the intended identity; `name` does not substitute for `id`. Generated regions cannot supply authored homes. The home extends through its heading subtree, and its first definition sentence enters generated navigation and registry output.

Facts use precisely `Key | Value | Status | Basis` columns. Each Key cell contains its key text and exactly one explicit anchor; the row has no other anchor. The fact identity combines owner identity and key, such as `example.batcher#capacity`, while links target the row's `capacity` anchor.

```markdown
| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="capacity"></a>capacity | 2 | specified | [Teaching decision](#decision) |
```

Here `2` counts items admitted to one batch. `specified` states the declaration's qualification, and the teaching decision supplies its basis. A label is value-bearing only when it contains a digit or consists entirely of one code span. Other labels are descriptive navigation. Compare value-bearing labels exactly after normalization, including labels that also match a registered name. Thus `[3](#capacity)` and ``[`wrong`](#capacity)`` fail with `D10`, while `[borrowing limit](#capacity)` navigates.

Normalization removes surrounding space and supported group separators within integer digit runs grouped in threes. Inline Markdown formatting is removed; code-span content remains literal. Decimal points, case, punctuation and other spacing remain significant. There is no expression evaluation, range interpretation or measurement conversion. Keep qualifications beside their home with a direct link to the fact so change reporting can include them.

Relations use precisely `Key | Predicate | Target | Basis` columns. Target contains one direct link to a registered home of a kind permitted for that predicate. Basis contains a link. The relation table specifies the allowed `performed-by`, `protected-by`, `limited-by` and `precedes` targets.

**Entities in this example:** [Acceptance test](requirements-tests-and-failures.md#acceptance-test), [scenario](requirements-tests-and-failures.md#scenario).

Declarations have an immediately preceding explicit anchor and a heading beginning `Requirement:`, `Acceptance test:`, `Failure state:` or `Scenario:`. A permanent `test-` anchor also identifies an acceptance case when its heading omits that prefix. Requirement anchors use `req-` and test anchors use `test-`, followed by nonempty lower-case letters or digits separated by single hyphens. Preserve identities for unchanged obligations and cases.

Required bold fields appear once per declaration heading. Each field occupies a separate paragraph. For example, `**Result:** Return Full without changing the batch.` Requirements link tests through `Tests`; acceptance cases link back through `Requirements`. A failure's `Authority` identifies the recovery actor and authority. Explicitly absent recovery also explains its consequence. Review checks these meanings beyond field presence.

The vocabulary tables list required fields. Acceptance cases may add `Implementation`; [failure declarations](requirements-tests-and-failures.md#failure-declaration) may add `Actor`; scenarios may add `Requirements` and `Tests`. No other declaration fields are accepted. Decisions use separate headings and one `Rejected alternatives` field containing all rejected options and reasons.

Method is `test`, `inspection`, `analysis` or `demonstration`, ignoring case and an optional final period. Exactly Method `test` requires Implementation. Its field contains only plain-text Markdown links separated by comma and whitespace, with no final punctuation.

```markdown
**Implementation:** [tests/test_batches.py::Suite::test_full](../tests/test_batches.py), [tests/test_batches.py::Suite::test_empty](../tests/test_batches.py)
```

In that illustrative field, each label starts with the repository-relative file and appends `::selector`. The resolved relative destination must be that same file, with no scheme, query or fragment. A selector is nonempty and whitespace-free; nested names can contain `::`. Static checking validates the grammar and file existence. The [selector audit](interfaces-and-encodings.md#selector-audit) executes the named selectors through the repository's declared runner or built-in Python default.

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

The marker pair must occur exactly once in order. Its document identity matches `navigation.region`.

The generator emits a notice, then `## Overview`, the manifest purpose, and bold Audience, Scope and Non-goals paragraphs in that order.
It adds a bold Declared gaps paragraph when needed, preserving the gap array order.

Next comes `## Document map` with its introductory sentence, then section bullets in manifest order.
Each bullet is `[heading](relative-path#anchor) — summary` prefixed by `- `.
Its anchored level-2 headings follow in source order as nested bullets prefixed by two spaces.

A final indented `Prerequisites: ` line lists prerequisite links in their declared array order, separated by comma and space, ending with a period.

The generated [entity index](documents-homes-and-values.md#entity-index) follows under [`## Entity index`](documents-homes-and-values.md#entity-index), with an introductory sentence and one bullet per scoped entity, sorted lexically by entity identity.
Each entity bullet is `[home heading](relative-path#anchor) (` followed by its identity in a code span, then `) — definition sentence`.

Headings and paragraphs have blank lines between them; adjacent bullets do not. Output uses LF newlines and ends with one newline. Map links select authored destinations, including anchored level-2 headings within each section subtree. The region omits a duplicate entry title; a whole-file output begins with the document title as a level-1 heading.

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

`requirement_changes` returns a `ChangeReport` whose `to_dict()` contains `changes`. Each change has `id`, `kind` (`new`, `changed` or `removed`), `base`, `candidate`, `tests`, `added_tests`, `removed_tests` and `changed_facts`. [Requirement declarations](requirements-tests-and-failures.md#requirement-declaration) remain full source text. Facts contain their identity plus base and candidate values, status, basis, linked evidence text and qualifications linked to the fact.

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

`select_context` returns `Context`, exposing byte `content`, `size_bytes`, `manifest`, `diagnostics` and `to_dict()`. The dictionary form decodes content as UTF-8. Invalid selection raises `SpecDocsError` carrying diagnostics. The content contains manifest, [complete registry](agent-context.md#complete-registry), metadata, profile, optional change report and labelled source ranges. Ranges follow snapshot label, document array order, section array order and source line order, after overlap merging.

The manifest contains `version`, `tool_version`, `format_version`, `profile_version`, `label`, `baseline`, `source_digest`, `registry_digest`, `input_fingerprints`, `assignment`, `included`, `inclusion_reasons`, `ranges`, `registry_size_bytes`, `metadata_size_bytes`, `profile_size_bytes`, `profile_digest` and `size_bytes`. A comparison adds `base_provenance` with its baseline, registry digest and input fingerprints.

Each range records `label`, `path`, `start`, `end`, `identities`, `reasons`, `digest` and `size_bytes`. Offsets count zero-based lines with an exclusive end; the digest is SHA-256 of that range's UTF-8 bytes. `input_fingerprints` maps metadata and declared source paths to SHA-256 digests. The source digest covers the captured content map, not a hash of every unrelated asset.

The embedded manifest's `size_bytes` equals the complete content length, including itself. The selector reaches that value before testing `budget_bytes`. This budget bounds documentation bytes only; the [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) separately bounds its complete pack. Missing or excessive mandatory input returns an error instead of a prefix of the content.
