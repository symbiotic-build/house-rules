<a id="reference"></a>
# Reference, decisions and adoption

The declaration reference supplies exact encodings.
This chapter records the system's interfaces, diagnostic meanings and settled choices.
It contains no product-specific contracts.

<a id="interfaces"></a>
## Interfaces and encodings

The [source format](../../../skills/spec-writing/references/format.md) owns JSON fields, Markdown declaration syntax and callable input shapes.
Its [versioned contract](../../../skills/spec-writing/references/format-contract.json) owns field vocabularies, entity kinds, relationship targets and review responsibilities.
Templates reference those contracts instead of becoming another authority.
There is no unit configuration or value-type system.

The [documentation checker](checking.md#documentation-checker) provides this callable core:

```python
load_corpus(source, format_contract) -> Corpus
check(corpus, base=None) -> Diagnostics
generate_navigation(corpus) -> dict[str, bytes]
select_context(corpus, assignment) -> Context
requirement_changes(base, candidate) -> ChangeReport
```

**Entities in this example:** [documentation checker](checking.md#documentation-checker),
[source snapshot](context.md#source-snapshot), [context pack](context.md#context-pack).

The source argument supplies paths and bytes from one [source snapshot](context.md#source-snapshot).
The base argument is an optional separate selection for change review.
Navigation returns proposed path-to-byte outputs.
Context selection returns complete content and provenance.
Requirement comparison returns a derived change report.
No call adds persistent state.

Relationship tables use Key, Predicate, Target and Basis columns.
Initial predicates are `performed-by`, `protected-by`, `limited-by` and `precedes`.
The [versioned contract](../../../skills/spec-writing/references/format-contract.json) defines supported target kinds.
The order relation states required sequence; it establishes neither concurrency nor synchronization.
There is no separate value-assertion table.

<a id="writing-profile"></a>
## Writing profile

The writing profile is the versioned set of controlled-language practices owned by [writing rules](../../../rules/writing.md).

The checker reads the machine-readable block in that owner.
There is no second handwritten limits file.
The profile claims no full controlled-English standard conformance.
It excludes a full specialist dictionary, universal part-of-speech checks, full verb restrictions and industry-specific safety notices.

Use one approved name per technical concept.
Explain the problem and ordinary behavior before refusal, concurrency, failure and recovery.
Preserve conditions, exceptions, uncertainty and consequences.
Never shorten an explanation only to clear a counter.
Simultaneous actions may share an instruction when separating them would change behavior.

Visible prose supplies word counts.
Whitespace separates words; identifiers and hyphenated tokens each count as one.
Separate numbers and measurement words count separately.
Markup and link destinations do not count.
Parenthetical prose counts normally.

Sentence endings are `.`, `?` or `!` followed by whitespace or block end.
Decimals and code-span punctuation do not split sentences.
A colon introducing a vertical list ends its introduction.

Exclude code blocks, exact signatures, declaration encodings and attributed quotations from prose counts.
Keep surrounding explanations in scope.
Sentence and paragraph targets produce warnings only.
Long cells, approximate voice checks and suspected multi-action sentences also produce warnings.
Reviewers establish whether instructions contain independent, ordered or simultaneous actions.

Numbered actions need a preceding **Procedure: descriptive label** and at least two direct actions.
A single action is a sentence.
Descriptive enumerations use bullets or compact tables.
Operator decision options follow the House Rules question format and are exempt.
Detail blocks use ordinary blockquotes for information.
Required instructions stay beside the action that needs them.

Prose numbers follow ISO 80000-1 grouping with spaces and a decimal dot.
Dates and times follow ISO 8601 with a zone and the 24-hour clock.
A space separates quantities from unit symbols.
Use a plain grouping space in Markdown; a renderer may substitute a narrow no-break space.
Code, identifiers, configuration, data and literal examples retain their language's notation.
These formatting checks warn and never block.

<a id="require-profile"></a>
### Requirement: structural procedures and advisory prose checks

**Actor:** [Documentation checker](checking.md#documentation-checker) and readability reviewer.

**Condition:** Authored prose or numbered actions are checked.

**Result:** Read the shared machine-readable profile. Enforce procedure structure; keep approximate language, length and numeral checks advisory. Preserve qualifications during review.

**Verification:** Check valid procedures, single-item lists, operator options and warning-only prose.

**Tests:** [Prose checks](acceptance.md#test-profile).

**Status:** specified.

**Basis:** [Writing decision](#writing-decision).

<a id="diagnostics"></a>
## Diagnostic reference

The [documentation checker](checking.md#documentation-checker) reports structural failures through these templates.
Diagnostic codes identify failure classes; they do not certify technical validity.

```text
D01 tracked Markdown file is not classified: <path>
D02 unsupported version, unknown field or malformed declaration: <detail>
D03 duplicate identity '<id>'; first at <location>
D04 entity '<id>' has no complete, unique home
D05 source '<path>' is outside the declared input set: <reason>
D06 target '<target>' does not resolve
D07 entity '<id>' is used outside its declared document scope
D08 fact '<id>' needs exactly one home anchor in its declaring row
D10 value link for '<fact>' differs: home <home-text>, link <link-text>
D11 requirement '<id>' has no linked acceptance test
D12 use of '<id>' needs a direct home link: <first-use|forward-use|wrong-target>
D13 rejected form '<text>'; use '<replacement>'
D14 symbol '<symbol>' violates naming rule '<id>'
D15 required document role '<role>' is missing or incomplete
D16 prerequisite '<section>' appears later without a direct forward link
D17 generated navigation differs: regenerate '<output>'
D18 numbered list requires a labelled procedure with at least two actions
D21 approval is blocked by unresolved contract '<id>'
D22 removed requirement '<id>' needs a resolving decision reference
D23 pack omits mandatory context '<id>'
D24 pack baseline differs from assignment baseline
D25 mandatory pack requires <size>; available budget is <limit>
D26 review plan lacks required coverage '<responsibility>'
D27 cannot <operation> '<input>': <reason>
D28 acceptance test '<id>' has no linked requirement
D29 requirement/test link '<requirement>' <-> '<test>' is not reciprocal
D30 failure declaration '<id>' lacks '<field>'
D31 changed requirement '<id>' lacks linked-test review input '<test>'
```

**Entities in this example:** [documentation checker](checking.md#documentation-checker),
[acceptance test](sources.md#acceptance-test), [context pack](context.md#context-pack),
[requirement declaration](sources.md#requirement-declaration),
[failure declaration](sources.md#failure-declaration).

Codes `D09`, `D19` and `D20` are retired.
There is no value-reference evaluator or typed-value diagnostic.
Malformed declaration checks cover duplicate JSON keys and invalid naming patterns, not value content.
Exact symbols and unambiguous registered phrases receive blocking terminology checks.
Ambiguous ordinary-word matches warn.
Procedure checks inspect structure, not action meaning inferred from punctuation.

| Code | Warning |
|---|---|
| W01 | Sentence exceeds target |
| W02 | Paragraph exceeds target |
| W03 | Possible fact restatement |
| W04 | Possible technical use |
| W05 | Possible profile violation |

A prose numeral warning is only a cheap scan.
It neither identifies an intended fact nor proves disagreement.
Unlinked textual restatements can remain undetected mechanically.
Warnings accompany readability assignments.
A demonstrated contradiction or missing explanation is a review finding; a warning alone is not.

Test ranges become explicit links to each intended test.
The checker does not infer several existing targets from a range notation.
History values are comparable only when their links identify the same fact.

<a id="decisions"></a>
## Decisions

These choices bind the system's source, value, toolchain and context contracts.
Their rationale records maintenance trade-offs, not benchmark results.

<a id="source-decision"></a>
### Decision: ordinary Markdown and shared declarations

**Choice:** Use ordinary Markdown, shared JSON metadata and one Python checker built on `markdown-it-py`.

**Authority:** Operator-approved design dated 2026-10-16.

**Reason:** Preserve ordinary source reading and direct links while deriving navigation, traceability and context from one source set.

**Rejected alternatives:** A JavaScript-based document runtime adds another runtime without removing registry or selection work. Alternate source and publication systems change the authoring contract. Independent requirement stores duplicate writable authority.

Borrow identity and disambiguation principles from definition-oriented tools.
Borrow map and applicability principles from modular documentation systems.
Borrow reciprocal test links and change review from requirement tools.
Adopt none of their publication machinery.
No separate terminology executable, exporter or second vocabulary authority is required.
An existing installation may remain where it serves other writing needs.

<a id="literal-decision"></a>
### Decision: literal values

**Choice:** “Fact values are literal text, exactly as the spec writes them in the home table cell.”

**Authority:** Operator selection dated 2026-10-16, decision Q178 = 1.

**Reason:** Check direct restatements without introducing product-specific value interpretation.

**Rejected alternatives:** Typed values, unit vocabularies, range validation, expressions and reference-valued facts introduce another value model. Mathematical equivalence does not replace literal equality.

<a id="toolchain-decision"></a>
### Decision: shared pinned toolchain

**Choice:** The shared tool owns exact wheel versions, hashes and supported Python metadata. Repositories pin its House Rules revision.

**Authority:** Operator-approved design dated 2026-10-16.

**Reason:** Keep checker, helper, parser, profile and format contract aligned across local, continuous integration and extracted use.

**Rejected alternatives:** Repository-specific parser pins and checker copies create independent implementations. Source-build and alternate-parser fallbacks hide failed setup.

<a id="context-decision"></a>
### Decision: complete mandatory context

**Choice:** Derive compulsory registry and selected complete homes from one immutable snapshot. Refuse missing or excessive input before dispatch.

**Authority:** Operator-approved design dated 2026-10-16.

**Reason:** Preserve shared meaning and provenance without recursive link expansion or silent truncation.

**Rejected alternatives:** Optional registry inclusion, automatic traversal of ordinary links and trimmed specification bodies break the mandatory context contract. Persistent mirrors and approval hashes duplicate source authority.

<a id="writing-decision"></a>
### Decision: defined prose profile

**Choice:** Use versioned controlled-language practices, ISO 80000-1 prose numbers and ISO 8601 dates and times. Keep approximate prose checks non-blocking.

**Authority:** Operator-approved design and number-format selection dated 2026-10-16.

**Reason:** Make expectations explicit without claiming full standard conformance or erasing technical qualifications.

**Rejected alternatives:** An approximate percentage does not define enforceable practices. Blocking length limits can encourage loss of meaning.

<a id="open-questions"></a>
## Open questions

None in the approved design.
Implementation acceptance still requires actual checker, navigation, anchor behavior and real-dispatch evidence.
A passing source check does not replace those tests.

<a id="adoption"></a>
## Adoption and ownership

Existing naming material may contain technical contracts beyond preferred words.
Inventory each row and substantive prose rule before replacing it.
Preferred names become headings and accepted forms.
Meanings become home introductions.

Rejected synonyms become rejected forms.
Naming patterns become structured rules.
Interface mappings remain explanation; states and transitions become requirements.
Historical decisions become decision references.

Preserve boundaries, actors, states and interface distinctions.
A name-only index is insufficient.

Conversion completes atomically before the repository enables its required gate.

**Procedure: convert a repository**

1. **Inventory the existing contract.**
   - Record names, meanings, settings, relationships, requirements and acceptance cases.
2. **Establish homes and metadata.**
   - Preserve qualifications and settled decisions.
3. **Update links and loaders.**
   - Point each use at its current authority.
4. **Generate navigation and context.**
   - Check the assembled source and required input.
5. **Remove superseded material.**
   - Review the replacement before enabling the gate.
   - Git preserves history; add no permanent legacy reader.
Product contract decisions remain with their owners.
Do not invent concepts to justify stale text.
Preserve provisional, observed, required and unresolved meanings.

Writing rules own profile and procedure invariants.
Specifications rules own authority, homes, linking and context invariants.
The format reference owns syntax and literal comparison.
The authoring skill owns authoring and reader procedures.
Design lifecycle skills own outline, approval and closeout.

The [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) and review preparer own context integration.
Review lenses own meaning and whole-[scenario](sources.md#scenario) examination.
The structure reference owns paths; the index and changelog own loading and adoption rationale.
The generated [entity index](sources.md#entity-index) replaces a separate hand-maintained glossary.

Branch validation uses ordinary authoring and review entry points with the exact branch revision.
Do not merge merely to make the environment load branch rules.

**Procedure: validate branch use**

1. **Prepare the pinned implementation.**
   - Include checker, profile, templates and pack integration.
2. **Run authoring assignments.**
   - Exercise single-file and multi-file sources through normal loaders.
3. **Run review assignments.**
   - Check mandatory input, fresh-reader understanding and whole-scenario coverage.
4. **Inspect source and run evidence.**
   - Check meaning preservation, link density and table retention.
   - Record defects and false positives in existing output.
   - Repair owning mechanisms instead of hand-repairing packs or exports.
5. **Review the resulting branch.**
   - Present required continuous integration and real-run evidence before merge.
   - A separate renderer may consume checked output after this pipeline passes.

<a id="require-adoption"></a>
### Requirement: faithful conversion and branch use

**Actor:** Repository editor and lead.

**Condition:** Existing specifications or naming material adopt this system.

**Result:** Preserve technical distinctions, qualifications and settled decisions. Replace duplicate current contracts atomically and validate branch rules through normal authoring and review paths before merge.

**Verification:** Compare source inventory with resulting homes and inspect real branch-run evidence.

**Tests:** [Real authoring and review](acceptance.md#test-real-use).

**Status:** specified.

**Basis:** [Source decision](#source-decision), [context decision](#context-decision).
