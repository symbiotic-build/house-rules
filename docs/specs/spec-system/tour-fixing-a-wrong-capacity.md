<a id="tour"></a>
# Tour: fixing a wrong capacity

This tour shows how an author turns a bounded-batch contract into checked reading material for review. A deliberately wrong link reveals which source owns the capacity. Repairing that link leaves the batch's behavior intact and lets the author rebuild navigation and prepare the complete assignment.

The [minimal corpus](minimal-corpus.md#minimal-example) supplies the exact three authored files. `Full` is the teaching service's refusal; `D10` is the documentation diagnostic for a wrong displayed value.

<a id="capacity-repair"></a>
## The capacity correction

Create the three source files, introduce one wrong value link, and repair the reported error.

The command examples use `python` from the pinned House Rules repository's [tool environment](source-formats.md#tool-environment). Their placeholder roots denote the House Rules checkout and an independent example repository with Git initialized. The [toolchain explanation](checking-and-navigation.md#toolchain-and-inputs) supplies setup details.

**Procedure: author, break and repair the bounded-batch contract**

1. **Register the source.** Copy the [manifest input](minimal-corpus.md#example-documents) and create its title and opening in `docs/example.md`.

   > **Detail — source registration**
   >
   > The [document manifest](documents-homes-and-values.md#document-manifest) registers document `example` and section `main` at title anchor `example`.
   > The selector `example#main` names that title's complete subtree.
   > Keep [docs/ENTITIES.json](../../ENTITIES.json) empty until the component's definition exists; the [entity index](documents-homes-and-values.md#entity-index) records completed homes.
   > Complete the remaining content below before generating from this full manifest.

2. **Write the batcher's home.** The author gives readers one place to learn what the component does and find its capacity.

   > **Detail — definition and capacity**
   >
   > The example source uses heading anchor `batcher` for the complete explanation.
   > Its [canonical fact](documents-homes-and-values.md#canonical-fact), a named literal kept in one home table, is the capacity:
   >
   > ```markdown
   > | Key | Value | Status | Basis |
   > |---|---|---|---|
   > | <a id="capacity"></a>capacity | 2 | specified | [Teaching decision](#decision) |
   > ```
   >
   > The value `2` counts items in one batch.
   > Status `specified` identifies it as the teaching contract's chosen value.
   > The linked decision explains that teaching basis; it is not a measurement or production approval.
   >

3. **Complete the refusal contract and its evidence.** The author explains what happens to a submitted item when the batch is full.

   > **Detail — obligation, refusal and inspection**
   >
   > The [requirement declaration](requirements-tests-and-failures.md#requirement-declaration) states the obligation; the [failure declaration](requirements-tests-and-failures.md#failure-declaration) records retained state and recovery. The [acceptance test](requirements-tests-and-failures.md#acceptance-test) links back to the obligation. Write these declarations:
   >
   > ```markdown
   > <a id="req-capacity"></a>
   > ### Requirement: refuse a full batch
   >
   > This obligation preserves existing items when a caller exceeds the batch capacity.
   >
   > **Actor:** [Batcher](#batcher).
   >
   > **Condition:** A submitted item would exceed [2](#capacity) items.
   >
   > **Result:** Return `Full` without changing the batch.
   >
   > **Verification:** Inspect the batch after refusal.
   >
   > **Tests:** [Full batch](#test-capacity).
   >
   > **Status:** specified.
   >
   > **Basis:** [Teaching decision](#decision).
   >
   > <a id="failure-full"></a>
   > ### Failure state: full batch
   >
   > This refusal tells the caller how to submit an item after the batch fills.
   >
   > **Trigger:** Submission would exceed [2](#capacity) items.
   >
   > **Outcome:** The caller receives `Full`.
   >
   > **Retained state:** Existing items remain unchanged.
   >
   > **Recovery:** Submit the item in a new batch.
   >
   > **Authority:** The submitting caller may start a new batch.
   >
   > **Verification:** [Full batch](#test-capacity).
   >
   > <a id="test-capacity"></a>
   > ## Acceptance test: full batch
   >
   > This inspection checks that refusal preserves the existing items.
   >
   > **Method:** inspection.
   >
   > **Requirements:** [Capacity refusal](#req-capacity).
   >
   > **Inputs:** A full batch and one additional item.
   >
   > **Expected:** `Full` and the same retained items.
   >
   > Evidence: [retained-state inspection](#failure-full).
   > ```
   >
   > Copy the decision, question statement and reference from the [Markdown input](minimal-corpus.md#example-example) as well.

4. **Register the completed home.** The author binds the component's name to the explanation that now exists.

   > **Detail — identity and location**
   >
   > The [entity index](documents-homes-and-values.md#entity-index) adds `example.batcher` with kind `component` and accepted form `batcher`.
   > Its home pairs section `example#main` with anchor `batcher`.
   > The section selects the title and all headings beneath it. The home anchor identifies the definition within that selection.
   >
   > Scope `example` makes that name applicable in this document.
   > Empty symbol and rejected-form lists add no alternate names.
   > The [exact entity entry](minimal-corpus.md#example-entities) shows the complete JSON.
   >
   > The complete example remains a draft without approval. Its decision records a proposal; the [approval reference](source-formats.md#metadata) explains the approval fields.

5. **Generate navigation.** The shared tool produces a map and an index from the valid sources.

   > **Detail — first generated map**
   >
   > ```sh
   > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py generate --root /path/to/example
   > ```
   >
   > The output replaces the example's declared navigation region.
   > Its map links to the batcher explanation, and its entity entry displays the definition sentence.
   > [Navigation generation](checking-and-navigation.md#navigation-generation) explains validation and replacement.

6. **Introduce the wrong displayed value.** The author changes one link label, making the prose disagree with its destination.

   > **Detail — deliberate mutation**
   >
   > In the [batcher example](../../../skills/spec-writing/scripts/fixtures/minimal/docs/example.md#batcher), replace the label `2` with `3` in this line:
   >
   > ```markdown
   > Submit up to [3](#capacity); a full batch retains its items on refusal.
   > ```
   >
   > Keep the capacity table unchanged.
   > The displayed `3` is the deliberate defect, not a proposed capacity change.
   >

7. **Check the mutated source.** The author receives a diagnostic identifying the conflicting value link.

   > **Detail — visible documentation error**
   >
   > ```sh
   > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py check --root /path/to/example
   > ```
   >
   > The [documentation checker](checking-and-navigation.md#documentation-checker) reports `D10` at the mutated line and exits with status `1`.
   > The diagnostic identifies `example.batcher#capacity`, home text `2` and link text `3`.
   > Checking changes no source or generated output.
   > Generation also refuses this invalid input before replacing navigation.
   > The [diagnostic reference](interfaces-and-encodings.md#diagnostics) explains the value-mismatch remedy.

8. **Correct the link label.** The author restores agreement with the chosen capacity without changing the contract.

   > **Detail — source repair**
   >
   > Restore the [batcher example](../../../skills/spec-writing/scripts/fixtures/minimal/docs/example.md#batcher) line:
   >
   > ```markdown
   > Submit up to [2](#capacity); a full batch retains its items on refusal.
   > ```
   >
   > Only the displayed label changed.
   >

9. **Regenerate navigation.** The tool accepts the repaired source and replaces the declared navigation region.

   > **Detail — rebuild from the same authority**
   >
   > ```sh
   > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py generate --root /path/to/example
   > ```
   >
   > The command exits with status `0` and reports the file whose navigation region it replaced.
   > Correcting only a link label does not change the declared map or entity definition.
   > Regeneration therefore preserves their content while rebuilding it from the repaired source.

10. **Check the repaired corpus.** The author receives a successful structural result for the complete example.

    > **Detail — repair result**
    >
    > ```sh
    > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py check --root /path/to/example
    > ```
    >
    > The checked fixture returns `0 errors, 0 warnings` and exit status `0`.
    > Interpret that result under the [acceptance evidence distinction](acceptance-evidence.md#acceptance).

11. **Select complete reading material.** The author assigns the example section, and the tool returns its checked source with the mandatory reference material.

    > **Detail — assignment and selection**
    >
    > The assignment file outside the example corpus contains:
    >
    > ```json
    > {"version": 1, "sections": ["example#main"]}
    > ```
    >
    > Version `1` selects the supported assignment format.
    > The sole `sections` entry identifies the complete registered subtree, rather than a line excerpt.
    >
    > ```sh
    > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py context --root /path/to/example --assignment /path/to/assignment.json
    > ```
    >
    > The resulting [context pack](agent-context.md#context-pack) includes the example's complete source subtree and batcher home without repeating overlapping ranges.
    > It also contains the [complete registry](agent-context.md#complete-registry), metadata and the teaching decision within the selected chapter.
    > The [writing profile](writing-and-review-workflow.md#writing-profile) supplies the shared prose-check policy.
    > Its manifest reports exact UTF-8 byte counts and fingerprints for the captured input.
    > The [agent-context chapter](agent-context.md#snapshot-and-selection) explains selection and snapshot boundaries.
    >

12. **Review the refusal and repair.** Reviewers use the complete explanation to assess whether the author has described the behavior and evidence adequately.

    > **Detail — questions that checking leaves to review**
    >
    > A reviewer checks that `Full` means the new item was refused and the existing items remain unchanged.
    > The reviewer also checks who can start a new batch and whether the inspection proves the retained-state obligation.
    > [Semantic review](writing-and-review-workflow.md#semantic-review) supplies that responsibility beyond structural checking.


Selection has its own visible refusals. An assignment using `example#missing` reports `D06`, because no registered section has that selector. An otherwise valid assignment with `budget_bytes` set to `1` reports `D25`, because one byte cannot hold the mandatory material. Neither result returns a shortened [context pack](agent-context.md#context-pack); the author corrects the selector or narrows a legitimate assignment before preparing it again.

The [documents, homes and values chapter](documents-homes-and-values.md#shared-contract) next explains how the authored sources make that agreement checkable. The [requirements, tests and failures chapter](requirements-tests-and-failures.md#behavior-and-change) explains how the refusal connects to its evidence.
