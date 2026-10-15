<a id="reference"></a>
<a id="interfaces"></a>
# Interfaces and encodings

The [exact source formats](source-formats.md#source-format) define every JSON shape, Markdown declaration, navigation marker and callable input.
The [skills/spec-writing/references/format-contract.json](../../../skills/spec-writing/references/format-contract.json) must agree with that chapter.
The [complete minimal corpus](minimal-corpus.md#minimal-example) is checked as a real fixture.
There is no unit configuration or value-type system.

<a id="diagnostics"></a>
## Diagnostic reference

The [documentation checker](documentation-checker.md#documentation-checker) reports structural failures through these templates.
Diagnostic codes identify failure classes; they do not certify technical validity.

| Code | Meaning | Fix |
|---|---|---|
| D01 | Unclassified Markdown | Classify the file |
| D02 | Malformed declaration | Use the declared shape |
| D03 | Duplicate or retired identity | Allocate a fresh identity |
| D04 | Incomplete entity home | Restore heading and meaning |
| D05 | Invalid input boundary | Use regular repository inputs |
| D06 | Unresolved target | Repair the direct destination |
| D07 | Entity outside scope | Correct scope or usage |
| D08 | Invalid fact anchor | Anchor the Key cell once |
| D10 | Literal mismatch | Match the home text |
| D11 | Requirement without test | Link an acceptance case |
| D12 | Missing direct home link | Link the intended home |
| D13 | Rejected name | Use the registered replacement |
| D14 | Structured naming violation | Follow the declared pattern |
| D15 | Missing or misordered role | Repair the role and order |
| D16 | Forward prerequisite | Add its direct handoff |
| D17 | Stale navigation | Regenerate from valid sources |
| D18 | Invalid ordered procedure | Label two ordered actions |
| D21 | Approval blocked | Resolve the blocking contract |
| D22 | Unexplained requirement removal | Supply its decision reference |
| D24 | Stale baseline | Regenerate current-baseline input |
| D25 | Mandatory input exceeds budget | Narrow the assignment |
| D26 | Missing review responsibility | Repair the review plan |
| D27 | Invocation or I/O failure | Repair the reported input |
| D28 | Test without requirement | Link its requirement |
| D29 | One-sided trace link | Repair both directions |
| D30 | Incomplete recovery declaration | Complete fields and verification link |
| D31 | Missing changed-test input | Select every affected test |
| D32 | Numbered heading | Use an unnumbered title |
| D33 | Linked heading | Move links into prose |
| D34 | Chapter filename mismatch | Use the title slug |
| D35 | Repeated sentence | Explain at concept introduction |
| D36 | Title-only summary | State the reader outcome |

**Entities in this example:** [documentation checker](documentation-checker.md#documentation-checker),
[acceptance test](acceptance-test.md#acceptance-test), [context pack](context-pack.md#context-pack),
[requirement declaration](requirement-declaration.md#requirement-declaration),
[failure declaration](failure-declaration.md#failure-declaration).

Codes `D09`, `D19`, `D20` and `D23` are retired.
Warning `W03` is retired.
There is no value-reference evaluator or typed-value diagnostic.

Malformed declaration checks cover duplicate JSON keys and invalid naming patterns, not value content.
Exact symbols and unambiguous registered phrases receive blocking terminology checks.
Ambiguous ordinary-word matches warn.

Procedure checks inspect structure, not action meaning inferred from punctuation.


| Code | Meaning | Disposition |
|---|---|---|
| W01 | Long sentence | Shorten or explain retention |
| W02 | Long paragraph | Split or explain retention |
| W04 | Ambiguous technical use | Review the intended meaning |
| W05 | Possible profile violation | Inspect; retain exact literals |
| W06 | Predecessor-only prerequisites | Review conceptual dependencies |


Unlinked value restatements require [semantic review](semantic-review.md#semantic-review).
Warnings accompany readability assignments.
A demonstrated contradiction or missing explanation is a review finding; a warning alone is not.

Test ranges become explicit links to each intended test.
The checker does not infer several existing targets from a range notation.
History values are comparable only when their links identify the same fact.


<a id="selector-audit"></a>
## Selector audit

This audit turns the batch example's executable evidence links into observable test results.
Run `python skills/spec-writing/scripts/audit_selectors.py --root REPOSITORY` after the static check.
It lists each acceptance identity and linked requirements, then executes every Implementation selector.

Python unittest files use `Class::test_method` selectors; unsupported files and missing selectors are visible failures.
Each result includes runtime.
The final line reports passed, missing and failing counts.

A test process exceeding `--timeout-seconds` fails visibly.
This versioned tool interface defaults that configurable runaway ceiling to 30 seconds.
The current system declares no executable evidence in other test frameworks.
Non-executable inspection evidence is reviewed through its linked lens or run record.


<a id="continuing-example-reference"></a>
## Bounded-batch lookup

This lookup reconnects each part of the tour to its exact reference.

| Need | Reference |
|---|---|
| Authored files | [Minimal corpus](minimal-corpus.md#minimal-example) |
| Capacity declaration | [Markdown declarations](source-formats.md#markdown-declarations) |
| Wrong label | [D10](#diagnostics) |
| Assigned input | [Callable assignment](source-formats.md#callable-core-and-context-assignment) |
| Executable evidence | [Literal values](acceptance-evidence.md#test-literals) |

The full-batch inspection in the minimal corpus is intentionally non-executable.
Its evidence names the retained-state refusal; the independent-repository regression executes the [documentation checker](documentation-checker.md#documentation-checker) against those exact files.
