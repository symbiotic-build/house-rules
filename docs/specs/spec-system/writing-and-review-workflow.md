<a id="authoring-and-review"></a>
# Writing and review workflow

Authors use the checked source system to produce explanations that an engineer can implement. One editor coordinates shared metadata while home owners explain coherent behavior in disjoint chapters. The bounded-batch assignment carries capacity `2`, refusal `Full` and recovery through writing and review; a structural pass alone cannot prove their meaning.

<a id="ownership-and-readable-explanation"></a>
## Ownership and readable explanation

Ownership keeps concurrent authors from defining competing contracts. One editor owns manifest and entity-index changes for the round. Each entity has one home owner, and every author receives a disjoint source assignment with generated input. Changes to another owner's facts are proposals to that owner.

A valid draft map precedes body assignments. Its anchored openings, explicit role gaps and unregistered incomplete homes let generation succeed before definitions exist.

**Procedure: write an implementable explanation**

1. **Review the outline.** Establish the reader, purpose, scope and coherent chapter tasks.
   The outline gives each assigned chapter a clear reading outcome.
2. **Explain ordinary behavior.** Define each entity beside the continuing example.
   The reader learns its purpose before encountering refusal or recovery.

   > **Detail — batch admission**
   > The capacity declaration explains when the batch fills.
   > `Full` refuses the extra item while existing items remain.
3. **Complete the contract.** Add reciprocal requirements and acceptance cases together.
   Each stopping path states retained state, caller result, recovery and authority.

   > **Detail — recovery**
   > The submitting caller can start a new batch.
   > Review establishes whether that action is possible, beyond checking that the field exists.
4. **Check the source.** Run the pinned structural checker.
   It names invalid declarations and mismatched displays.

   > **Detail — literal repair**
   > A link displaying `3` against capacity `2` produces `D10`.
   > The author repairs the label in source before generation.
5. **Regenerate navigation.** Project the corrected authored declarations.
   The refreshed map can accompany the next assignment.
6. **Review warnings.** State a disposition for every remaining warning group.
   A concrete reader problem requires repair; an appropriate retained passage needs its reason.

Every section opens with its purpose. An entity home's first sentence defines the entity; its following text explains purpose and behavior. The generated index copies that definition sentence alone. Procedures keep the action and caller result in the step, with exact encodings in labelled detail blocks.

<a id="writing-profile"></a>
## Writing profile

A writing profile is the versioned set of advisory prose targets read from the shared writing rules. It gives authors and reviewers common expectations without making word counts a condition of valid technical meaning.

The tool reads the profile from its own House Rules revision's [rules/writing.md](../../../rules/writing.md). The profile names its version and warning severity, with separate targets for procedural sentences, descriptive sentences and paragraph length. No consumer maintains a second limits file.

A long explanation of the batch's retained items can warn without failing checking or pack preparation. The author may shorten it while preserving conditions, exceptions and consequences. If those details need the longer passage, record that disposition. A warning alone establishes neither a contradiction nor a reader failure.

Structural procedure checks remain blocking. A numbered sequence needs the labelled procedure form and at least two actions. Readability review checks whether each action is understandable; the checker does not infer action boundaries reliably from punctuation.

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

Qualification tests the normal authoring pipeline before the branch is merged. The [Fresh-reader review](../../../skills/spec-writing/SKILL.md#fresh-reader-review) owns the reader procedure: two readers using different models answer ten questions, build independent corpora and rate every chapter. It requires zero unanswered questions, guesses or stuck points, zero errors on each corpus’s first check, and “yes” for every chapter. Readers quote troublesome passages; accepted findings receive repairs and fresh ratings. That procedure can fill the existing readability responsibility without authorizing a larger panel.

Pipeline qualification also runs a fresh author from a short feature brief using branch-pinned normal loaders. It separately converts an existing unconverted design and a deliberately messy document. The resulting multi-chapter source passes structural checking and the fresh-reader procedure. Bind the run record to its source revision and candidate digest; inspect approved decisions for implemented behavior or an explicit reasoned change.

Conversion accounts for every substantive source rule, table row, qualification and settled decision. Move names and rejected forms into the [entity index](documents-homes-and-values.md#entity-index), and move behavior and declarations into complete homes. Preserve distinctions that cannot be represented as naming patterns through linked requirements. Update loaders, links and metadata together before removing a superseded contract.

Approval follows [skills/design-flow/SKILL.md](../../../skills/design-flow/SKILL.md). Do not resolve a reviewer-marked operator choice by writing an answer into the specification. Branch validation uses real authoring and review entry points before merge; it never hand-repairs a generated pack. A renderer remains a separate consumer with its own specification and display evidence.
