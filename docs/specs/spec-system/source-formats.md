<a id="source-format"></a>
# Source formats

This chapter specifies the encodings that connect authored Markdown, shared metadata and callable tooling. Use it after the mechanisms to construct or inspect a corpus without guessing field names. The [minimal corpus](minimal-corpus.md#minimal-example) supplies complete copyable inputs.

Markdown uses CommonMark with pipe tables. JSON keys are case-sensitive; duplicate and unknown keys are errors. The [skills/spec-writing/references/format-contract.json](../../../skills/spec-writing/references/format-contract.json) contains the same vocabularies as this chapter. The separate prose profile belongs to [rules/writing.md](../../../rules/writing.md).

<a id="sources-and-commands"></a>
## Sources and commands

These commands select which source is checked, used for navigation or delivered to an agent. Invoke the shared helper with its owning runtime inputs; invoking it does not install packages.

```text
python skills/spec-writing/scripts/spec_docs.py link --root REPOSITORY
python skills/spec-writing/scripts/spec_docs.py check --root REPOSITORY
python skills/spec-writing/scripts/spec_docs.py generate --root REPOSITORY
python skills/spec-writing/scripts/spec_docs.py context --root REPOSITORY --assignment FILE
```

The default captures working-tree Markdown and metadata, including unignored new files. `--staged` reads the complete index. `--rev REV` reads the resolved commit. These last two switches are mutually exclusive. `--base REV` adds a comparison base for requirement changes; a base before adoption can contain neither metadata file, but partial metadata remains invalid.

`link` writes only to the captured working tree. It refuses `--staged`, `--rev`, `--base` and `--assignment`. Its insertions and remaining diagnostics follow the [direct-link behavior](checking-and-navigation.md#documentation-checker). Run `link` before `check`, then regenerate stale navigation.

`link --prune-repeats` also converts repeated accepted-form links from documents written under the older linking rule. Other commands refuse `--prune-repeats`. The direct-link behavior defines its scope and exclusions; replacement safety is unchanged.

`--assignment FILE` supplies context selectors, affected-test review input and removal decisions. Context requires that option. `--format-contract FILE` selects an explicit format contract; the normal default belongs to the shared helper. `--json` emits structured output. `--fixture` permits synthetic `fixture` approval authority in test fixtures only.

Every candidate Markdown file needs an inventory classification. Paths use forward slashes and are repository-relative, with no empty, `.` or `..` components. Source text is UTF-8. Symlinks and nonregular source inputs are refused. Code and asset links use file inventory for existence checks without loading unrelated binary bytes. External URLs receive syntax checks without network access.

The public exit meanings are:

| Status | Meaning |
|---|---|
| `0` | Successful operation |
| `1` | Document or selection errors |
| `2` | Invocation, environment or I/O failure |

Warnings do not change success. Text checking prints each source-addressed finding and final error and warning counts. JSON checking returns `errors`, `warnings` and `ok`, plus `changes` when comparing a base. Each diagnostic has `path`, `line`, `code`, `message` and `severity`. Generation returns the generated path list.

Linking returns `linked` paths plus `errors`, `warnings` and `ok`; text output reports changed paths and remaining diagnostics. Remaining errors produce exit `1` after safe insertions; invocation or I/O failures produce exit `2`. Context returns its complete text or, with `--json`, `content`, `size_bytes` and `manifest`.

[Navigation generation](checking-and-navigation.md#navigation-generation) validates authored inputs without requiring old output to be fresh, then validates all proposed bytes before replacing any destination. Replacement is atomic per file, not across the whole generated set. Every authored destination must still match captured bytes. Linking uses the same validation and replacement path, permits existing errors and refuses newly introduced errors. A stale generated region requires regeneration. An interrupted set requires regeneration; neither checking nor dispatch treats an old output as a successful substitute.

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

<a id="house-rules-revision"></a>
### House Rules revision

The caller supplies the House Rules revision outside corpus metadata. Record its full resolved Git commit ID in the consuming repository's existing tool configuration or the invocation's retained run inputs. There is no required pin filename or additional corpus file. Neither shared metadata envelope accepts a revision field.

Invoke the helper from the checkout at that commit, with its matching runtime, lock, format contract and [writing profile](writing-and-review-workflow.md#writing-profile). The [prompt compiler](../../design/77-one-step-pack-assembly.md) receives the same commit as its `--rev` argument and reads its matching helper. The documentation tool's own `--rev` instead selects a commit in the consuming repository; it does not select House Rules. Changing the House Rules pin requires selecting and preparing the matching installation again.

<a id="metadata"></a>
## Metadata

Metadata identifies the files and homes that source selection can use. The two version-1 envelopes below show required keys; the first also accepts optional `test_runners`. Arrays can be empty unless their field requires entries.

```json
{"version": 1, "inventory": [], "documents": []}
```

```json
{"version": 1, "entities": {}, "naming_rules": []}
```

The first envelope belongs to [docs/DOCUMENTS.json](../../DOCUMENTS.json). An inventory entry has `path` and `kind`, with optional `reason`; `other` requires a nonempty reason. A document has the required fields shown below. The `approval`, `gaps` and `unresolved_contracts` fields are optional. Omitting `gaps` or `unresolved_contracts` is equivalent to an empty array; omitting `approval` records no approval. The draft below has no approval and registers no separate [scenarios](requirements-tests-and-failures.md#scenario):

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

In the full document entry above, `main` is the section identity and `example` is the anchor starting its complete heading subtree. Each `roles` element declares a content category inside that subtree, in reading order. `summary` states the reader's outcome. Empty prerequisite and dependency arrays request no additional material.

The [approval boundary](documents-homes-and-values.md#design-lifecycle) determines who may approve the document. For an eligible completed document, change status and add its approval entry:

```json
{"status": "approved", "approval": {"authority": "delegated", "decision": "example#decision"}}
```

The linked decision must record the actual delegation; copying this entry grants no authority.

`navigation.region`, when present, equals the document identity and selects markers inside an authored source file. Without `region`, `navigation.path` names a whole output under `docs/generated/`. Approval needs an `authority` and a resolving `document#anchor` decision. Production authorities are `operator` and `delegated`; `fixture` requires fixture mode and never authorizes production behavior.

`gaps` names missing roles waived only for a draft. Every retained `unresolved_contracts` selector blocks an approved document. These selectors must resolve. The checker establishes resolution; review establishes whether the decision's authority and content justify approval.

Sections are ordered objects with exactly `id`, `path`, `anchor`, `roles`, `summary`, `prerequisites` and `explanatory_dependencies`. A dependency has exactly `section` and `reason`. Prerequisites and dependency targets use registered `document#section` selectors. [Scenarios](requirements-tests-and-failures.md#scenario) use `document#anchor` declaration selectors. Every listed declaration must exist; for example:

```json
{"scenarios": ["example#scenario-refusal"]}
```

Every chapter opening belongs to a registered subtree. In a multi-file document, the filename equals the first heading's slug plus `.md`. Slugs case-fold words, remove punctuation, join words with hyphens and replace underscores with hyphens. Derive the filename directly from the title without abbreviating words. A single-file document keeps its document filename.

A summary must add a reader outcome beyond its title. `D36` compares case-folded words after removing punctuation and a leading “Understand”, “Learn about”, “Read about” or “Overview of”. A summary with no remaining word beyond the title fails. For more than five sections, `W06` warns when all prerequisites form only a predecessor chain after an empty first list.

`D35` detects an authored sentence of at least eight whitespace-separated words repeated at least three times in one document. It normalizes whitespace. Generated regions, literal blocks, attributed quotations, table cells and declaration fields are excluded. Ordinary detail prose and list paragraphs remain in scope.

The first envelope may also contain `test_runners`, an ordered array. Each entry requires `pattern` and `kind`, where kind is `unittest` or `junit`. Optional fields are `reports`, `testcase` and `batch`:

```json
{"test_runners": [{"pattern": "tests/*.test.ts", "kind": "junit", "reports": ["reports/vitest.xml"], "testcase": {"classname": "{file}", "name": "{selector}"}, "batch": ["node", "tests/run-cited.mjs", "--report", "{report}", "{selectors}"]}]}
```

`pattern` is a case-sensitive repository-relative shell-style glob; `*` can match `/`. Duplicate patterns are invalid. The first matching entry wins. Unmatched `.py` files use Python unittest; unmatched other files count as missing. An omitted or empty array keeps that default.

`reports` is a nonempty array of root-relative report paths or globs. The `junit` kind requires `testcase`, a nonempty object whose keys are JUnit attributes `file`, `classname` or `name`. Its string values collectively contain both `{file}` and `{selector}` and no other braces.

Matching compares every declared attribute exactly after substitution. A `file` attribute also accepts a leading `./`. The example maps Vitest's classname to the repository-relative file and name to the full `describe > test name`. Repositories whose reporter uses different attributes declare that mapping instead. The `unittest` kind uses the built-in mapping and does not accept `testcase` or `batch`.

`batch` is a nonempty argument array executed once from the repository root without shell interpretation. A standalone `{selectors}` expands into one argument per unique full `file::selector` citation, in first-citation order. `{report}` substitutes an absolute temporary JUnit output path.

Both placeholders are required and no other braces are allowed. The repository supplies the executable and adapter that accepts these arguments. Exit zero admits the report; other statuses fail the entire batch. The [audit reference](interfaces-and-encodings.md#selector-audit) defines matching, error remedies and runaway handling.

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

The `home` selects the batcher's complete heading subtree. `scope` lists document identities where it may be used and includes the home document. `forms` lists accepted phrases, matched without case distinction; `symbols` lists exact code spellings. An empty `symbols` array declares none.

Each rejected form instead has `text`, `replacement` and `reason`, all nonempty strings.

Naming rules check a selected entity kind's accepted forms or symbols. Each record has `id`, `kind`, `field`, `pattern` and `message`. `field` is `forms` or `symbols`; `pattern` is a Python regular expression applied with full-match semantics. Invalid expressions fail visibly, and duplicate rule identities are errors.

These compact tables list the vocabularies and required declaration fields. The [machine-readable contract](../../../skills/spec-writing/references/format-contract.json) supplies the JSON vocabularies. Write Choice, Authority, Reason and Rejected alternatives in Markdown; do not add a metadata key for them. Reviewers check their meaning.

The seven required roles preserve their listed order. Design-specific roles may interleave anywhere without changing the relative order of those seven roles. For example, `mechanism`, `ownership`, `integration`, `requirements`, `decisions`, `alternatives`, `questions`, `rollout`, `work-packages`, `reference`, `acceptance`, `acceptance-evidence` is a valid continuation after `tour`. The table includes scenario fields.

| Field | Allowed values or required fields |
|---|---|
| `entity_kinds` | `component`, `mechanism`, `setting`, `concept`, `interface`, `state`, `actor`, `data` |
| `inventory_kinds` | `specification`, `design`, `other`, `generated` |
| `document_statuses` | `draft`, `approved`, `implemented`, `superseded` |
| `fact_statuses` | `specified`, `provisional`, `observed`, `unresolved` |
| `roles` | `tour`, `mechanism`, `requirements`, `decisions`, `questions`, `reference`, `acceptance` |
| `design_roles` | `evidence`, `constraints`, `alternatives`, `ownership`, `integration`, `rollout`, `work-packages`, `acceptance-evidence` |
| `requirement_fields` | `Actor`, `Condition`, `Result`, `Verification`, `Tests`, `Status`, `Basis` |
| `test_fields` | `Method`, `Requirements`, `Inputs`, `Expected` |
| `failure_fields` | `Trigger`, `Outcome`, `Retained state`, `Recovery`, `Authority`, `Verification` |
| `scenario_fields` | `Purpose`, `Inputs`, `Expected` |
| Decision fields | `Choice`, `Authority`, `Reason`, `Rejected alternatives` |
| `review_responsibilities` | `technical`, `readability`, `design/cost`, `failure/recovery`, [`whole-scenario`](requirements-tests-and-failures.md#scenario) |

<a id="relation-predicates"></a>
The relation predicate table limits each connection to the listed target kinds.

| Relation predicate | Permitted target kinds |
|---|---|
| `performed-by` | `actor`, `component` |
| `protected-by` | `mechanism`, `component` |
| `limited-by` | `setting` |
| `precedes` | `component`, `mechanism`, `setting`, `concept`, `interface`, `state`, `actor`, `data` |

`group_separators` contains comma, underscore, ordinary space, no-break space and narrow no-break space.

A fact’s Status must belong to `fact_statuses`: `specified`, `provisional`, `observed` or `unresolved`. Put provenance explanations in Basis or adjacent prose. Provisional and unresolved rows link their open question in Basis; state applicability before the table. For example, `specified` qualifies a declared teaching value. Basis is also nonempty and contains a resolving link. No field in this contract introduces a unit or value-type system.

<a id="markdown-declarations"></a>
## Markdown declarations

Markdown declarations make a contract's values and evidence addressable without moving their meaning into metadata. The batcher uses an explicit home anchor followed immediately by its heading and definition.

Literal blocks and inline code need direct home links for registered uses in an immediately adjacent paragraph. Natural explanatory prose works; `**Entities in this example:**` is an optional label for the same links. Each block needs its own adjacent links; unrelated intervening prose prevents reuse. Quote-only blank lines count as blank inside a blockquote. These annotations are not declaration fields. First-use scope and unnumbered headings follow the [Direct links](../../../rules/specifications.md#direct-links).

```markdown
<a id="batcher"></a>
## Batcher

A batcher prevents overfilling by accepting items only while its batch has room.
```

Use the empty `id` anchor form shown above with the intended identity; `name` does not substitute for `id`. Generated regions cannot supply authored homes. The home extends through its heading subtree, and its first definition sentence enters generated navigation and registry output. If that sentence mentions another registered term, give it the required direct home link. Generated definitions contain visible text only; source links are checked before generation.

Facts use precisely `Key | Value | Status | Basis` columns. Each Key cell contains its key text and exactly one explicit anchor; the row has no other anchor. The fact identity combines owner identity and key, such as `example.batcher#capacity`, while links target the row's `capacity` anchor.

```markdown
| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="capacity"></a>capacity | 2 | specified | [Teaching decision](#decision) |
```

Here `2` counts items admitted to one batch. `specified` states the declaration's qualification, and the teaching decision supplies its basis. A label is value-bearing only when it contains a digit or consists entirely of one code span. Other labels are descriptive navigation. Compare value-bearing labels exactly after normalization, including labels that also match a registered name. Thus `[3](#capacity)` and ``[`wrong`](#capacity)`` fail with `D10`, while `[borrowing limit](#capacity)` navigates.

Normalization removes surrounding space and supported group separators within integer digit runs grouped in threes. Inline Markdown formatting is removed; code-span content remains literal. Decimal points, case, punctuation and other spacing remain significant. There is no expression evaluation, range interpretation or measurement conversion. Keep qualifications beside their home with a direct link to the fact so change reporting can include them.

Relations use precisely `Key | Predicate | Target | Basis` columns. Target contains one direct link to a registered home of a kind permitted for that predicate. Basis contains a link. The relation table specifies the allowed `performed-by`, `protected-by`, `limited-by` and `precedes` targets.

An [acceptance test](requirements-tests-and-failures.md#acceptance-test) records evidence for an obligation; a [scenario](requirements-tests-and-failures.md#scenario) traces related actions. Both use the declaration encoding below.

Declarations have an immediately preceding explicit anchor and a heading beginning `Requirement:`, `Acceptance test:`, `Failure state:` or `Scenario:`. A permanent `test-` anchor also identifies an acceptance case when its heading omits the `Acceptance test:` prefix, such as `Inspection: full batch`. Requirement anchors use `req-` and test anchors use `test-`, followed by nonempty lower-case letters or digits separated by single hyphens. Preserve identities for unchanged obligations and cases.

Failure-state and [scenario](requirements-tests-and-failures.md#scenario) anchors need only be nonempty unique explicit anchors; the prefixes shown in examples are conventions, not required syntax.

The parser ignores blockquoted `Detail — label` blocks when collecting declaration fields, including bold labels within them. Those blocks remain explanatory prose subject to ordinary link and writing checks.

Required bold fields appear once per declaration heading. Each field occupies a separate paragraph. For example, `**Result:** Return Full without changing the batch.` Requirements link tests through `Tests`; acceptance cases link back through `Requirements`. A failure's `Authority` identifies the recovery actor and authority. Explicitly absent recovery also explains its consequence. Review checks these meanings beyond field presence.

The vocabulary tables list required fields. Acceptance cases may add `Implementation`; [failure declarations](requirements-tests-and-failures.md#failure-declaration) may add `Actor`; scenarios may add `Requirements` and `Tests`. No other declaration fields are accepted. Decisions use separate anchored headings, such as `## Decisions` for one choice or `### Decision: <title>` for each of several choices. Each supplies Choice, Authority, Reason and one Rejected alternatives field containing all rejected options and reasons. These are authoring requirements; the checker resolves decision anchors but does not classify decisions as declaration records.

Method is `test`, `inspection`, `analysis` or `demonstration`, ignoring case and an optional final period. Exactly Method `test` requires Implementation. Its field contains only plain-text Markdown links separated by comma and whitespace, with no final punctuation.

```markdown
**Implementation:** [tests/test_batches.py::Suite::test_full](../tests/test_batches.py), [tests/test_batches.py::Suite::test_empty](../tests/test_batches.py)
```

In that illustrative field, each label starts with the repository-relative file and appends `::selector`. The resolved relative destination must be that same file, with no scheme, query or fragment. A selector is nonempty with no leading or trailing whitespace; nested names can contain `::`, and framework test names may contain spaces. Static checking validates the grammar and file existence. The [selector audit](interfaces-and-encodings.md#selector-audit) matches reported cases or batches the named selectors through the repository's declared runner or built-in Python default.

Other methods omit Implementation and place linked evidence in an ordinary, unbolded paragraph after Expected. For example: `Evidence: [retained-state inspection](#failure-full).` Do not write `**Evidence:**`: that is an unknown declaration field. Evidence links target material inside the document set or repository. Label an unperformed inspection as planned; a completed inspection links its recorded observations. Evidence adequacy follows the [acceptance evidence distinction](acceptance-evidence.md#acceptance).

An Actor field may link its own home even after its defining paragraph has satisfied first use. The minimal example does this for clarity; it is not an extra self-link requirement.

<a id="navigation"></a>
## Navigation

Navigation markers tell the generator where derived reading material belongs. The bounded-batch example keeps one region inside its existing source file.

```markdown
<!-- spec-docs:navigation document="example" -->
<!-- Generated by spec-docs; edit authored declarations. -->
<!-- /spec-docs:navigation -->
```

The marker pair must occur exactly once in order as top-level HTML comments. Fenced, inline-code and quoted marker examples are literal content. Its document identity matches `navigation.region`.

The first generated line is `<!-- Generated by spec-docs; edit authored declarations. -->`, followed by a blank line. Next come `## Overview`, the manifest purpose, then bold Audience, Scope and Non-goals paragraphs. A bold Declared gaps paragraph follows when needed, preserving array order.

Under `## Document map`, the exact introductory sentence is `Use this map to choose the next explanation to read.` Section bullets follow manifest order. Each includes its heading link and summary. Anchored level-2 headings follow as nested bullets, indented two spaces. For a nonempty prerequisite array, a final `Prerequisites: ` line is indented two spaces. It lists links in array order, separated by comma and space, ending with a period. An empty array omits that line entirely.

The generated [entity index](documents-homes-and-values.md#entity-index) uses this heading:

```markdown
## Entity index
```

The exact introductory sentence is `Each technical term below links to its defining Markdown section.` Bullets follow lexical entity-identity order. These are complete examples of map and entity bullets:

```markdown
- [Bounded batches](example.md#example) — Follow submission and inspect its evidence.
  - [Batcher](example.md#batcher)

- [Batcher](example.md#batcher) (`example.batcher`) — A batcher prevents overfilling by accepting items only while its batch has room.
```

Link paths are relative to the directory containing the navigation file. Paths and fragments use percent encoding for spaces and other reserved characters. The generator uses that same path-and-fragment format for both inline regions and whole-file navigation, even when the destination is the containing file. An inline region in `docs/example.md` therefore links to `example.md#batcher`, rather than `#batcher`. Authored prose may use fragment-only links; generated navigation keeps the uniform format above.

Headings and paragraphs have blank lines between them; adjacent bullets do not. Generated body output uses LF newlines and ends with one newline. No blank line separates the final entity bullet from the closing region marker. The region omits a duplicate entry title; a whole-file output begins with the document title as a level-1 heading.

Place the region after the complete introduction, before the first following authored heading and its anchor. Introduction content includes all opening paragraphs, the diagram, its explanation and prerequisites. The generator finds this boundary from parsed authored content, ignoring headings in the old generated region.

Whole-file destinations live under `docs/generated/`. Their generated-file attributes appear between `# spec-docs:generated` and `# /spec-docs:generated` in `.gitattributes`. Each line uses a quoted repository path followed by `linguist-generated=true`. A source file containing a region is not marked wholly generated.

<a id="callable-core-and-context-assignment"></a>
## Callable core and context assignment

The callable interface lets integrators reuse the parsed model for checking, [navigation generation](checking-and-navigation.md#navigation-generation) and selection. Import the shared module from its owning scripts directory; a consumer does not copy it into a private implementation.

```python
Snapshot.from_mapping(paths, fixture=False)
Snapshot.from_git(root, staged=False, rev=None, fixture=False)
load_corpus(source, format_contract=None, *, comparison=False)
check(corpus, base=None)
generate_navigation(corpus)
link_missing(corpus, prune_repeats=False)
requirement_changes(base, candidate)
changed_sections(base, candidate)
select_context(corpus, assignment)
```

`paths` maps repository paths to strings or bytes. Loading parses declared Markdown once. `comparison=True` permits a base with neither metadata file; it does not permit partial metadata or missing metadata in ordinary checking. `check` returns `Diagnostics`, exposing `errors`, `warnings`, `ok` and `to_dict()`. Navigation generation returns proposed path-to-bytes output without writing it.

`link_missing` likewise returns only source paths with proposed linking changes. Its default inserts missing direct links; an already-linked corpus returns an empty mapping. With `prune_repeats=True`, insertion precedes repeat pruning in memory. An already-converted corpus returns an empty mapping. The command validates these proposed bytes through the same replacement path.

`requirement_changes` returns a `ChangeReport` whose `to_dict()` contains `changes`. Each change has `id`, `kind` (`new`, `changed` or `removed`), `base`, `candidate`, `tests`, `added_tests`, `removed_tests` and `changed_facts`. [Requirement declarations](requirements-tests-and-failures.md#requirement-declaration) remain full source text. Facts contain their identity plus base and candidate values, status, basis, linked evidence text and qualifications linked to the fact.

`changed_sections` returns sorted candidate section selectors whose complete source subtrees differ from the base section with the same identity. New sections are included. Line-number shifts alone do not change a subtree. Only sections registered in the candidate manifest are eligible.

Capture and load both snapshots before attaching the comparison base and selecting input:

**Procedure: prepare comparison context**

1. **Load the base snapshot.**

   ```python
   base = load_corpus(Snapshot.from_git(root, rev="HEAD"), comparison=True)
   ```

   - Reads the selected commit; comparison mode permits a base with neither metadata file.
2. **Load the candidate snapshot.**

   ```python
   candidate = load_corpus(Snapshot.from_git(root))
   ```

   - Captures the working tree and parses its declared Markdown.
3. **Attach the comparison base.**

   ```python
   candidate.base = base
   ```

   - Selection can now include separately labelled base evidence.
4. **Construct the assignment.**

   ```python
   assignment = {"version": 1, "sections": ["example#main"],
                 "required_test_reviews": ["example#test-capacity"]}
   ```

   - Names the complete section and the affected test to review.
5. **Select the reading material.**

   ```python
   context = select_context(candidate, assignment)
   ```

   - Returns the mandatory context with its comparison evidence and byte accounting.

This includes comparison evidence and enforces removal decisions and affected-test input. Add every affected test and any removal decisions reported by `requirement_changes(base, candidate)`. The report compares requirements by their permanent anchors, including moves between documents. It selects tests from both snapshots when a declaration or directly linked fact contract changes. It maintains no persistent suspect-link ledger.

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

`removal_decisions` is an object mapping each removed requirement's **base-document-qualified** selector to a decision selector in the candidate.
The key uses the base document identity plus `#` and the permanent requirement anchor; it is neither a bare anchor nor a filename.
The value uses the candidate document identity plus `#` and the decision anchor.
For example, when removing `req-capacity` from base document `example`, supply:

```json
{
  "version": 1,
  "sections": ["example#main"],
  "required_test_reviews": ["example#test-capacity"],
  "removal_decisions": {"example#req-capacity": "example#remove-capacity"}
}
```

In this hypothetical change, the base document `example` contains `req-capacity` and its linked case `test-capacity`.
The candidate keeps document `example` and replaces the obligation with this proposed decision:

```markdown
<a id="remove-capacity"></a>
### Decision: remove the capacity obligation

**Choice:** Remove `req-capacity`; retain `test-capacity` from the base as review input.

**Authority:** Illustrative proposal requiring the document owner's approval.

**Reason:** This hypothetical candidate removes bounded admission from its scope.

**Rejected alternatives:** Keeping the obligation would require bounded admission to remain in scope.
```

The affected test selector above must resolve in the base or candidate.
If the requirement's old document no longer exists, the key still uses its base document identity; the decision value names its candidate document.
The checker resolves the decision's structure; reviewers assess its authority.

Each review-plan entry has `responsibilities` and optional `id`. Responsibilities use the contract vocabulary; their union must cover every required responsibility when a plan is supplied. Authoring may omit a plan. Normal review preparation supplies the plan and resolved base; direct compiler review requires `--target-base REV`. It derives required tests, while removal decisions remain explicit input.

Only `prepare.py review` derives a missing assignment. It compares the merge base and reviewed head with `changed_sections`, using the head's [document manifest](documents-homes-and-values.md#document-manifest). Nonempty results become version-1 `sections`; existing selection adds affected tests from both snapshots and applicable decisions. Empty results produce no documentation pack and one line: `No registered documentation changed in this range.` Explicit `--assignment` behavior is unchanged outside check rounds. Direct `prompt.py` writer and reader packs still require explicit assignments. Derived context retains the existing byte accounting and size guards; oversized preparation fails with the selected section names instead of truncating documentation.

A check round (`prepare.py review --since <commit>`) prepares no documentation context, even with `--assignment`. Its rule report and diff compare against that last reviewed commit. Reviewers read registered documents in the checkout.

`select_context` returns `Context`, exposing byte `content`, `size_bytes`, `manifest`, `diagnostics` and `to_dict()`. The dictionary form decodes content as UTF-8. Invalid selection raises `SpecDocsError` carrying diagnostics. The content contains manifest, [complete registry](agent-context.md#complete-registry), metadata, profile, optional change report and labelled source ranges. Ranges follow snapshot label, document array order, section array order and source line order, after overlap merging.

The manifest contains `version`, `tool_version`, `format_version`, `profile_version`, `label`, `baseline`, `source_digest`, `registry_digest`, `input_fingerprints`, `assignment`, `included`, `inclusion_reasons`, `ranges`, `registry_size_bytes`, `metadata_size_bytes`, `profile_size_bytes`, `profile_digest` and `size_bytes`. A comparison adds `base_provenance` with its baseline, registry digest and input fingerprints.

Each range records `label`, `path`, `start`, `end`, `identities`, `reasons`, `digest` and `size_bytes`. Offsets count zero-based lines with an exclusive end; the digest is SHA-256 of that range's UTF-8 bytes. `input_fingerprints` maps metadata and declared source paths to SHA-256 digests. The source digest covers the captured content map, not a hash of every unrelated asset.

Included explicit anchors become `pack-N-anchor`, where `N` is the zero-based ordinal of each distinct snapshot-label/source-path pair in emitted range order. Links to those included anchors become fragments. Literal examples and destinations outside the selected ranges remain unchanged. Range digests and sizes describe original source bytes; the complete pack count includes rewritten bytes.

The embedded manifest's `size_bytes` equals the complete content length, including itself. Before testing `budget_bytes`, the selector serializes the pack until its final byte length equals the embedded count. This budget bounds documentation bytes only; the [prompt compiler](../../design/77-one-step-pack-assembly.md) separately bounds its complete pack. Missing or excessive mandatory input returns an error instead of a prefix of the content.
