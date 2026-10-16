<a id="authoring-and-review"></a>
# Writing and review workflow

Authors use the checked source system to produce explanations that an engineer can implement. This chapter assigns source ownership, separates structural checks from review responsibilities, and describes reader acceptance.

<a id="ownership-and-readable-explanation"></a>
## Ownership and readable explanation

Ownership keeps concurrent authors from defining competing contracts. One editor owns manifest and entity-index changes for the round. Assign one author responsibility for each entity’s defining section. Give each author a disjoint source assignment with generated input. Changes to another owner's facts are proposals to that owner.

Before assigning body sections, create anchored chapter openings and declare missing roles in `gaps`. Leave planned entities out of the index until their definitions are complete. Generate and check that draft map before assigning its chapters.

**Procedure: write an implementable explanation**

1. **Review the outline.** Establish the reader, purpose, scope and coherent chapter tasks.
   The outline gives each assigned chapter a clear reading outcome.
2. **Explain ordinary behavior.** Define each entity beside the continuing example.
   The reader learns its purpose before encountering refusal or recovery.

3. **Complete the contract.** Add reciprocal requirements and acceptance cases together.
   Each stopping path states retained state, caller result, recovery and authority.

4. **Check the source.** Run the pinned structural checker.
   It names invalid declarations and mismatched displays.

5. **Regenerate navigation.** Project the corrected authored declarations.
   The refreshed map can accompany the next assignment.
6. **Review warnings.** State a disposition for every remaining warning group.
   A concrete reader problem requires repair; an appropriate retained passage needs its reason.

Every section opens with its purpose. An entity home's first sentence defines the entity; its following text explains purpose and behavior. The generated index copies that definition sentence alone. Procedures keep the action and caller result in the step, with exact encodings in labelled detail blocks.

<a id="writing-profile"></a>
## Writing profile

A writing profile is the versioned set of advisory prose targets read from the shared writing rules. It gives authors and reviewers common expectations without making word counts a condition of valid technical meaning.

The tool reads the profile from its own House Rules revision's [rules/writing.md](../../../rules/writing.md). The current profile warns above 20 words per procedural sentence, 25 per descriptive sentence and six sentences per descriptive paragraph. These targets remain owned by the linked profile; repositories using the tool maintain no separate limits file.

A long explanation of the batch's retained items can warn without failing checking or pack preparation. The author may shorten it while preserving conditions, exceptions and consequences. If those details need the longer passage, record that disposition. A warning alone establishes neither a contradiction nor a reader failure.

Structural procedure checks remain blocking. A numbered sequence starts with `**Procedure: <title>**` and has at least two numbered actions, each starting with a bold action label. The [procedure example](requirements-tests-and-failures.md#scenario) shows detail blocks beneath actions. Readability review checks whether each action is understandable; the checker does not infer action boundaries reliably from punctuation.

<a id="semantic-review"></a>
## Semantic review

Semantic review is the examination of technical meaning and reader understanding that structural checking cannot establish. It determines whether the declared behavior, evidence and explanations support implementation.

For the bounded batch, review checks that refusal retains the existing items and that starting a new batch is an authorized recovery. It also checks that the acceptance inspection would reveal an accidental mutation. A resolving evidence link alone proves none of those properties.

The review plan covers technical correctness, readability, design and cost, failure and recovery, and complete [scenarios](requirements-tests-and-failures.md#scenario). The [assignment reference](source-formats.md#callable-core-and-context-assignment) gives their exact responsibility labels. One reviewer can cover several responsibilities. Preparation validates the actual plan; it does not launch additional reviewers. Changed requirements bring linked tests into the input even when the test text did not change.

Reviewers cite the incorrect claim or missing explanation and show its consequence. They inspect unlinked value restatements and technical meanings that the registry does not recognize. They also trace concurrency, entry, retained state, restart and public errors where those behaviors exist. Reviewers remain read-only and run no builds, tests or external writes; the preparing service owns execution evidence.

<a id="failure-review"></a>
### Failure state: incomplete review assignment

This refusal exposes missing review coverage before a reviewer receives an incomplete task.

**Trigger:** A supplied plan omits a required responsibility or a changed requirement lacks linked-test review input.

**Outcome:** Preparation fails and names the missing coverage or test selector.

**Retained state:** Authored source and existing findings remain. No additional reviewer starts automatically.

**Recovery:** Correct the assignment and regenerate its input with the approved reviewers.

**Authority:** The lead assigns responsibilities inside the existing resource envelope.

**Verification:** [Context selection](acceptance-evidence.md#test-context), [real authoring and review](acceptance-evidence.md#test-real-use).

<a id="review-and-adoption"></a>
## Review and adoption

Reader review tests whether the document teaches its contract. The [Fresh-reader review](../../../skills/spec-writing/SKILL.md#fresh-reader-review) procedure prepares two fresh readers using different models. They receive the chapters, generated navigation and registry reference without author conversation or coaching. Each answers ten questions with source citations:

- What problem is solved, and for whom? Which inputs are authored and which outputs generated?
- Who owns meanings and values? What is the reading order?
- How are requirements and tests identified? When does a displayed-value link pass or fail?
- What does the caller see on success? What is refused, with what message and retained state?
- How does the caller recover? What agent material is selected, and what prevents dispatch?

Each reader applies the chapters to a small concrete case and retains the first tool run. For this specification, that case is a corpus whose first check has zero errors. Readers rate each chapter “yes”, “with effort” or “no” and quote every troublesome passage. Acceptance requires every chapter “yes”, no unanswered questions, guesses or stuck points, and no unaddressed quote. Repairs require fresh ratings for affected chapters within the approved review plan.

Branch qualification adds the normal authoring and conversion runs described in [real authoring and review](acceptance-evidence.md#test-real-use). It uses the exact candidate commit before merge; it does not expand the review panel.

Conversion accounts for every substantive source rule, table row, qualification and settled decision. Move names and rejected forms into the [entity index](documents-homes-and-values.md#entity-index), and move behavior and declarations into complete homes. Preserve distinctions that cannot be represented as naming patterns through linked requirements. Update loaders, links and metadata together before removing a superseded contract.

Approval eligibility and delegated authority require the opening’s [design-flow prerequisite](../../../skills/design-flow/SKILL.md). Do not resolve a reviewer-marked operator choice by writing an answer into the specification. Branch validation uses real authoring and review entry points before merge; it never hand-repairs a generated pack. A renderer remains a separate consumer with its own specification and display evidence.
