<a id="shared-contract"></a>
# Documents, homes and values

Readers need one authoritative explanation of each behavior and a direct path to its values. Markdown carries explanations and values; shared metadata identifies their owners and reading order. Metadata points to the Markdown definition and value instead of storing another copy.

<a id="sources-and-reading-order"></a>
## Sources and reading order

Section registration makes a complete chapter selectable. For the teaching document, selector `example#main` points to title anchor `example`, including the opening and nested subsections. The [source document](#source-document) supplies the reading path, while each [addressable section](#addressable-section) gives that path a stable destination. The [document manifest](#document-manifest) records both without copying their explanatory prose.

<a id="source-document"></a>
### Source document

A source document is an ordered technical contract written in one or more Markdown files. It gives its declared audience a path from purpose and ordinary behavior to precise obligations and evidence.

A specification describes maintained behavior. A design also explains the evidence, constraints and alternatives behind a proposed change. Both use the shared metadata, even when every section fits in one file. The bounded-batch teaching document therefore needs no separate glossary or private metadata directory.

The authored introduction explains the system to its readers. The manifest supplies `purpose`, `audience`, `scope` and `non_goals` for the generated Overview that follows that introduction.

The seven required `roles` order the remaining content: `tour`, `mechanism`, `requirements`, `decisions`, `questions`, `reference` and `acceptance`. Short documents may assign adjacent roles to one section. Checking validates the declared order between sections; reviewers inspect the actual content inside combined sections.

An inapplicable role remains present with its reason, such as an Open questions section saying no implementation contract remains unsettled. A draft can instead omit unfinished content and declare its missing role in the manifest, for example `"gaps": ["questions"]`.

Examples, diagrams and summaries explain the contract without adding obligations. For the batcher, showing two accepted items helps explain capacity. The actual refusal obligation belongs to a [requirement declaration](requirements-tests-and-failures.md#requirement-declaration), whose condition and result can be reviewed together.

<a id="addressable-section"></a>
### Addressable section

An addressable section is a named heading subtree with a stable identity and an explicit anchor. It lets a reader or assignment select an explanation together with its nested detail.

A subtree starts at its heading's anchor and ends before the next heading of equal or higher level. A chapter selected by its title includes the chapter opening and all its subsections. Registering only a later subsection would leave the opening outside the selected explanation. In the batch corpus, the assignment `example#main` selects the section named `main` in the document named `example`.

Assignment boundaries select source; level-2 headings separately determine where first-use links restart. The direct-link cases are:

- Link the first use under each level-2 heading, whether its home is ahead, behind or in another document.
- Deeper headings continue that scope; later uses in the same section stay plain.
- Tables may repeat links. Each literal block keeps its own adjacent home links.

Admission and Recovery each first mention the batcher with `[batcher](#batcher)`, wherever its home appears. Validation continues Admission’s first-use tracking. Selecting this title includes all three headings:

```markdown
# Submission
## Admission
The [batcher](#batcher) admits items until the batch fills.
### Validation
The batcher checks each item.
## Recovery
Start another batch with the [batcher](#batcher).
```

Keep headings unnumbered and put links in the surrounding prose, never inside the headings themselves. Give a first-use link a short gloss when the reader needs its meaning to continue. Literal code and diagrams need direct home links in immediately adjacent prose; an **Entities in this example** paragraph is also accepted. An index or another use site cannot replace that destination.

Identities survive title changes, moves and reordered chapters. A renamed chapter receives the filename derived from its title, while its stable explicit anchor can remain. When a home moves, update its metadata and incoming links together. The [source formats](source-formats.md#markdown-declarations) define anchors and filename derivation exactly.

<a id="registered-entity"></a>
### Registered entity

A registered entity is an identified technical thing with one complete Markdown home. Its home lets readers understand the meaning, declared facts and operational behavior together.

Each home has an explicit anchor immediately before its heading. Its first sentence defines the thing; the following prose explains its purpose and behavior. The home includes nested declarations through the next heading of equal or higher level. Several homes can share one chapter without sharing an anchor or competing definitions.

The batcher's home explains what admission does before describing refusal. Its capacity row belongs there because readers need that value to understand when admission stops. A summary elsewhere links back instead of declaring another capacity. Excluded features remain in scope or non-goals text; exclusion alone creates no operational home.

The [entity index](#entity-index) owns identity, kind, accepted and rejected names, scope and home location. Markdown owns meaning, facts and explanation. Generated navigation obtains the display title from the home heading and meaning from its definition sentence alone. Purpose sentences remain in the chapter where they can develop the explanation.

<a id="entity-relations"></a>
### Entity relations

A relation table declares connections between entities. For example, `executor | performed-by | [Writer](#writer) | [Decision](#decision)` says the writer performs the owning mechanism. The [relation predicate table](source-formats.md#relation-predicates) lists allowed predicates and target kinds. A relation can name the component performing admission or a setting that limits it.

Each target must have its own registered home of the permitted kind. The small batch fixture keeps capacity as a fact and needs no extra setting home. Each relation supplies a supported predicate and linked basis. Exact columns and supported kinds belong to [Markdown declarations](source-formats.md#markdown-declarations).

<a id="canonical-fact"></a>
### Canonical fact

A canonical fact is a named literal value declared once in a table at its entity's home. It prevents conflicting values by making every value-bearing link answer to the same cell.

The bounded batch's capacity value is `2`, measured in items admitted to one batch. Its row has a key, literal value, status and linked basis. The explicit anchor belongs in the key cell so a direct link selects that exact declaration. The following excerpt illustrates the row rather than declaring another fact in this specification.

```markdown
| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="capacity"></a>capacity | 2 | specified | [Teaching decision](#decision) |
```

The home retains authority when another passage displays `[3](example.md#capacity)`. The destination resolves, but the displayed value disagrees with the home and produces `D10`. Correcting the displayed value to `2` repairs the link; changing the row would instead change the admission contract. Descriptive links such as `capacity` or `borrowing limit` navigate without asserting a literal. The [label grammar](source-formats.md#markdown-declarations) defines value-bearing labels.

Comparison uses visible literal text after trimming surrounding space and normalizing supported digit-group separators. It neither evaluates expressions nor converts measurements. Thus `1 024` and `1,024` compare alike, while `1.024` keeps its decimal point. Adding `items` inside a link to the capacity row changes the literal; put the unit outside that link. Reviewers check unlinked restatements because the checker cannot infer their intended source.

Status is `specified`, `provisional`, `observed` or `unresolved`; provenance explanations belong in Basis or adjacent prose. Provisional or unresolved rows link their open question in Basis and state applicability before the table. The [minimal corpus](minimal-corpus.md#example-example) shows a candidate capacity that is not an executable limit.

Status and linked basis qualify a value's authority. Put provisional conditions, observed limits, exceptions and resolution paths before the fact table. Qualify a mechanism or value at its first description, before a reader could treat it as implementable. Link that paragraph to the affected row. The tool captures linked qualification prose within the home in the generated registry and change report. For example: `Provisional: [capacity](#capacity) applies only to sequential submissions; concurrency needs an operator decision.`

A second passage displaying the value must state the applicable condition too. For example: `Allow [2](example.md#capacity) items for sequential submissions only.` Add that concurrent submission still needs an operator decision. This preserves both the value link and its limitation.

<a id="document-manifest"></a>
### Document manifest

The document manifest is the shared inventory and reading-order declaration for the repository's specification and design corpus. It tells the checker which Markdown paths are contracts and how each contract should be read.

The authored file is [docs/DOCUMENTS.json](../../DOCUMENTS.json). Its inventory classifies Markdown as specification, design, generated or other. An `other` entry includes a reason, which reviewers check against the file's content. Preserved input and evidence need classification too; otherwise they could escape review merely by living outside the chapter directory.

The metadata version identifies the JSON shape, and the path identifies the shared file authors edit.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="manifest-version"></a>version | 1 | specified | [docs/DOCUMENTS.json](../../DOCUMENTS.json) |
| <a id="manifest-path"></a>path | docs/DOCUMENTS.json | specified | [docs/DOCUMENTS.json](../../DOCUMENTS.json) |

The document entry declares purpose, audience, scope, non-goals and status. Its sections array establishes reading order. Each section supplies a stable identifier, path, anchor, roles, useful summary and prerequisites. A summary says what the reader learns or can do, rather than repeating the title. Prerequisites identify concepts needed to read the section, rather than mechanically naming its predecessor.

Declared explanatory dependencies name another section and explain why its prose is needed. They support complete assignments beyond a list of term definitions. For the batcher, a section about refusal can depend on the admission explanation when knowing capacity alone would not explain retained items. The later [Agent context](agent-context.md#agent-context) chapter explains how selection follows these declarations.

The manifest chooses one navigation destination for each document. A standalone generated file lives under generated documentation; an existing document can instead contain a declared navigation region. The single-file batch example uses that region to keep its map beside its opening. Neither arrangement creates a second authored contract.

<a id="names-homes-and-values"></a>
## Names and home locations

Reusing a name or value should bring readers back to its authority. A [registered entity](#registered-entity) has one complete Markdown home. The [entity index](#entity-index) points to that home and records the accepted names used to find it.

<a id="entity-index"></a>
### Entity index

The entity index is the shared mapping from technical identities and accepted names to their Markdown homes. Edit accepted names and home locations in this file.

The file [docs/ENTITIES.json](../../ENTITIES.json) declares each entry's kind, home, scope, forms, symbols and rejected forms. The home identifies a manifest section and an anchor inside it. Scope lists the documents where the entry applies, including the document containing its home. The home heading and definition are read from Markdown rather than repeated in the JSON. The generated navigation’s “Entity index” is a reading view of those entries, not another authored index.

The index version identifies its JSON shape, while the path identifies the repository's shared naming owner.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="index-version"></a>version | 1 | specified | [docs/ENTITIES.json](../../ENTITIES.json) |
| <a id="index-path"></a>path | docs/ENTITIES.json | specified | [docs/ENTITIES.json](../../ENTITIES.json) |

Accepted phrases and home titles match whole phrases without regard to case. Symbols match exactly. List plural forms explicitly for both phrases and symbols. Naming patterns apply to structured forms or symbols of a declared kind; they do not extract arbitrary identifiers from prose.

Rejected forms supply a replacement and reason. A rejected form matches without regard to case, except one that differs from a registered form or symbol only in letter case. That form matches exactly, so renaming `QUOTA_EXCEEDED` to `quota_exceeded` leaves the corrected spelling accepted.

An accepted form keeps one meaning across chapters, including link labels. For example, reserve `record` for the application object and use `commit-log record` for its encoded log unit. The second concept's index entry lists bare `record` in `rejected_forms`, with replacement `commit-log record` and reason "distinguish the encoded log unit from the application object". A link to the log unit does not make `record` an acceptable label for that second meaning.

For the batcher, an accepted name should lead to the home containing admission and refusal, not to a glossary paraphrase. A rule that cannot be expressed as a field pattern remains a linked requirement. Code-only identifiers stay with their implementation or reference owner unless readers need a separately defined technical meaning.

The checker recognizes declared symbols and unambiguous phrases. It does not infer bindings inside arbitrary programming languages. Reviewers still examine unregistered technical meanings and ambiguous ordinary words; recognition is a structural aid, not a complete account of terminology.

<a id="design-lifecycle"></a>
## Single-file designs and maintained specifications

Moving a proposed contract into maintained specification must leave one current home for each meaning. A single-file design uses the same [document manifest](#document-manifest) and [entity index](#entity-index) as a multi-file specification. Its location and inline navigation need no companion directory or glossary.

Drafts keep missing roles and unresolved contracts visible. A skeleton can generate navigation before homes exist because uncompleted homes remain unregistered. Once the author writes a definition and complete explanation, the editor can register its home. Registering a planned heading as though it were complete would give assignments an empty contract.

Approval records who authorized the document and links the decision. The operator is the repository’s human decision-maker; delegated authority comes from an explicit delegation by that operator. Authority `fixture` is limited to synthetic corpora checked with `--fixture`, which never authorizes production behavior. A working reference proves that a decision can be found, not that its author had approval authority. An approved document cannot retain an unresolved contract that prevents implementation.

Specifications and designs use the approval criteria owned by [skills/design-flow/SKILL.md](../../../skills/design-flow/SKILL.md), quoted here:

> In autonomous mode, a design entirely inside the approved outcome and decision boundaries may be marked `approved` at the base confidence threshold, with evidence recorded and the operator informed.
> Otherwise keep `draft` and ask about the consequential unresolved choice.
> A P0 or P1 design (§2), and any design that decides where canonical data lives, moves or creates a security boundary, or assigns ownership between repositories or modules, is approved only by the operator; delegated authority and confidence thresholds cover the remaining P2/P3 designs.
>
> — [skills/design-flow/SKILL.md](../../../skills/design-flow/SKILL.md), §2

The base confidence threshold is at least 90%, under [rules/core.md](../../../rules/core.md). The [priority labels](../../../rules/priority-labels.md) define P0 through P3. A resolving metadata entry alone cannot grant delegation.

When approved behavior becomes maintained specification, move each [registered entity](#registered-entity) home and update incoming links in the same change. Preserve the identity of the same technical thing. The old design becomes a status-bearing pointer or is removed under closeout rules. For the batcher, the admission explanation and capacity move together so readers cannot find two current refusal contracts.
