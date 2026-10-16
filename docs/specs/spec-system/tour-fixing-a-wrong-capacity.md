<a id="tour"></a>
# Tour: fixing a wrong capacity

This tour follows a displayed capacity through a visible error, correction and review. It starts from the complete bounded-batch example so readers can follow the repair without assembling an unfinished contract.

`Full` is the example component's refusal; `D10` identifies a documentation link whose displayed value differs from its home. The commands use `python` from the pinned [tool environment](source-formats.md#tool-environment). Their placeholder roots name the House Rules checkout and a separate example repository with Git initialized.

<a id="capacity-repair"></a>
## The capacity correction

Copy the complete example, change one displayed value and follow the diagnostic back to its authority.

**Procedure: break and repair the bounded-batch contract**

1. **Copy the complete example.** The three files supply a complete draft with links to its definition, refusal and planned inspection.

   > **Detail — starting files**
   >
   > Copy the [manifest input](minimal-corpus.md#example-documents), [entity input](minimal-corpus.md#example-entities) and [Markdown input](minimal-corpus.md#example-example) into the example repository.
   > Their destinations are `docs/DOCUMENTS.json`, `docs/ENTITIES.json` and `docs/example.md`.
   > Copy the complete files together.

2. **Find the capacity's authority.** The component's home declares how many items one batch admits.

   > **Detail — definition and value**
   >
   > The [batcher home](../../../skills/spec-writing/scripts/fixtures/minimal/docs/example.md#batcher) defines the component and its refusal behavior.
   > The home declares its operative capacity once. Its candidate capacity remains unadopted pending the linked question:
   >
   > ```markdown
   > | Key | Value | Status | Basis |
   > |---|---|---|---|
   > | <a id="capacity"></a>capacity | 2 | specified | [Teaching decision](#decision) |
   > | <a id="candidate-capacity"></a>candidate-capacity | 3 | provisional | [Capacity trial](#questions) |
   > ```
   >
   > The value counts admitted items in one batch. Status states the value’s qualification; Basis links its decision.
   > The candidate row is provisional and does not change that operative value.

3. **Inspect the name binding.** The metadata points to that existing explanation rather than copying its meaning.

   > **Detail — complete entity record**
   >
   > The [entity index](documents-homes-and-values.md#entity-index) contains this entry:
   >
   > ```json
   > {
   >   "example.batcher": {
   >     "kind": "component",
   >     "home": {"section": "example#main", "anchor": "batcher"},
   >     "scope": ["example"],
   >     "forms": ["batcher"],
   >     "symbols": [],
   >     "rejected_forms": []
   >   }
   > }
   > ```
   >
   > The home selects the definition within the complete chapter. Scope makes the accepted name applicable in this document.

4. **Complete missing links.** The tool leaves this already-linked example unchanged.

   > **Detail — mechanical linking**
   >
   > ```sh
   > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py link --root /path/to/example
   > ```
   >
   > The command inserts only missing direct links for unambiguous accepted names in body text.
   > It preserves headings, code and existing links. Authors resolve uses it cannot safely link.
   > The later [checking explanation](checking-and-navigation.md#documentation-checker) describes replacement safety.

5. **Generate navigation.** The tool validates the draft and produces its map and term index.

   > **Detail — generated output**
   >
   > ```sh
   > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py generate --root /path/to/example
   > ```
   >
   > The command reports the replaced navigation destination. The map links to the batcher's explanation and displays its definition sentence.

6. **Change only the displayed value.** The link now disagrees with the capacity it targets.

   > **Detail — deliberate mutation**
   >
   > In the [batcher example](../../../skills/spec-writing/scripts/fixtures/minimal/docs/example.md#batcher), change the display label to the following:
   >
   > ```markdown
   > Submit up to [3](#capacity); a full batch retains its items on refusal.
   > ```
   >
   > Keep the capacity table unchanged. This introduces a documentation defect, not a proposed contract change.

7. **Check the mutation.** The diagnostic names the conflicting link and leaves all files intact.

   > **Detail — visible error**
   >
   > ```sh
   > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py check --root /path/to/example
   > ```
   >
   > The [documentation checker](checking-and-navigation.md#documentation-checker) reports `D10` with the link’s location and the canonical row’s location.
   > It tells the reader to align the link label with the canonical value.
   > It exits with status `1`. Generation also refuses that invalid source before replacing navigation.

8. **Restore the displayed value.** Agreement returns without changing what the batch admits or retains.

   > **Detail — repaired link**
   >
   > Restore this line in the [batcher example](../../../skills/spec-writing/scripts/fixtures/minimal/docs/example.md#batcher):
   >
   > ```markdown
   > Submit up to [2](#capacity); a full batch retains its items on refusal.
   > ```

9. **Regenerate navigation.** The repaired source produces a current map.

   > **Detail — rebuild**
   >
   > ```sh
   > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py generate --root /path/to/example
   > ```

10. **Check the repair.** The repaired corpus passes structural validation.

    > **Detail — repair result**
    >
    > ```sh
    > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py check --root /path/to/example
    > ```
    >
    > The fixture returns `0 errors, 0 warnings` and exit status `0`.
    > This checks documentation structure; it does not execute the described service or establish reader understanding.
    > A declared inspection is a plan until the inspector records actual observations.

11. **Write the assignment.** The assignment names the complete chapter to review.

    > **Detail — assignment**
    >
    > Write this assignment file outside the example corpus:
    >
    > ```json
    > {"version": 1, "sections": ["example#main"]}
    > ```
    >
    > The version selects the assignment format. The section selector names the complete chapter, including its nested declarations.

12. **Select reading material.** The tool returns the complete explanation and mandatory reference material for review.

    > **Detail — selected input**
    >
    > ```sh
    > python /path/to/house-rules/skills/spec-writing/scripts/spec_docs.py context --root /path/to/example --assignment /path/to/assignment.json
    > ```
    >
    > The [context pack](agent-context.md#context-pack) includes that source once, the [complete registry](agent-context.md#complete-registry), metadata and [writing profile](writing-and-review-workflow.md#writing-profile).
    > Its manifest identifies the captured input and counts the pack's UTF-8 bytes.

13. **Review the refusal.** A reviewer assesses what structural checking cannot prove.

    > **Detail — inspection questions**
    >
    > Does `Full` mean the new item was refused with existing items unchanged?
    > May the submitting caller start a new batch?
    > Would the planned inspection reveal an accidental mutation?
    > The later [semantic review](writing-and-review-workflow.md#semantic-review) section explains that responsibility.

Selection also refuses invalid assignments. Selector `example#missing` reports `D06` because no registered section has that identity. A one-byte `budget_bytes` limit reports `D25` because it cannot hold the mandatory material. Neither refusal returns a shortened context pack; the caller repairs the assignment before trying again.

Next, [Documents, homes and values](documents-homes-and-values.md#shared-contract) explains how those authored sources make agreement checkable.
