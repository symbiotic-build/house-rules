## Lens: rule preservation

Audit the Rule text changes section in the task context using this procedure.
The shared [review bar](../util/review-bar.md) owns mandatory dispositions and Blocking conditions.

1. Read the report totals, every item and its old/new locations. Read the declared Rule
   changes from the report's selected source (PR body or `--summary`) beside it.
   Items are Git changed blocks: `removed`, `added`, `changed`, exact-copy `moved` or `rewrapped`.
   Audit every rule within a block, including changed order and indentation.
   Provenance entries remain separate approval evidence. A failed-closed report cannot support approval.
2. For each item, read old and new text in their complete source sections at the reported
   base and head. For `rewrapped`, open the diff at those locations and confirm the line-break
   move preserved heading, code, list, quote, table and hard-break structure.
   Its compact report omits old/new text; it still needs a disposition like every item. List the rule's actor, condition, action, strength words
   (`never`, `always`, `must`, `only`), numbers, exceptions, scope and cross-references.
   State absent elements explicitly. Compare each element; do not infer preservation
   from lexical similarity, a shorter sentence or the preparer's class.
3. Classify the effect as same, narrower, broader, weaker, stronger, removed, moved or new.
   For a move, confirm its destination retains every element, including inherited scope
   and exceptions. Search the existing rule homes to establish whether removed text
   survives elsewhere; an apparent move must not conceal text now missing everywhere.
   For a new rule, check conflicts and duplicates against existing homes: one home per rule.
4. Reconcile detected items with declared changes. Cite the exact selected-source line or
   recorded decision for every approved change. A declaration is an author claim;
   verify that it supplies approval for the actual effect. A removal or weakening needs
   operator approval on record (the operator's dated words quoted in the selected declaration
   source, or an entry in the frozen `CHANGELOG-RULES.md` archive); an author's declaration does not approve it. Flag undeclared items and
   declarations that conceal a removal or weakening.
5. Output one table row per report item: location, class, effect, disposition, evidence.
   The evidence identifies changed elements or explains why every element survives.
   Use the disposition vocabulary and Blocking conditions in the shared review bar.
   Follow the table with Blocking items. Check every report identity has exactly one row.

Out of scope (owning lens):
- Runtime correctness and security: `correctness-security`.
- Concurrency, restarts and durability: `concurrency-restarts`.
- General requirement coverage: `spec`.
- Document premise and readability: `design-spec`.
- Implementation waste: `waste`.

@rule house-rules:prompts/util/targeted-lens.md
