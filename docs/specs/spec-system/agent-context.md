<a id="agent-context"></a>
# Agent context

An assignment gives a writer or reviewer the source needed to explain one part of the system. Selection combines compulsory repository reference material with complete explanations from one captured version. For the bounded batch, `example#main` selects the chapter containing capacity `2`, the `Full` refusal and its recovery. A link displaying `3` instead of the declared capacity prevents preparation with `D10`.

<a id="complete-registry"></a>
## Complete registry

The complete registry is a generated record of every [registered entity](documents-homes-and-values.md#registered-entity), its definition, home, names and literal facts in the selected corpus. It gives every assigned agent the same repository vocabulary, including entities outside its selected reading material.

The registry combines the [entity index](documents-homes-and-values.md#entity-index) with definitions and declarations from Markdown homes. Each entry includes identity, kind, scope, accepted forms, symbols, rejected forms, source location and the first definition sentence. Its facts retain their values, Status, Basis and qualifications. The [minimal corpus](minimal-corpus.md#example-entities) therefore contributes `example.batcher` and its capacity even when another section is assigned.

The registry is mandatory; selection does not reduce it to the entities mentioned in the assignment. The [dispatcher](../../design/75-subagent-profiles.md#dispatcher) marks unrelated entries as reference material for a fresh reader. Reference material cannot supply a missing explanation in the chapters being reviewed. The registry is rebuilt from authored sources; it requires no separate database or maintained mirror.

<a id="context-pack"></a>
## Context pack

A context pack is the complete mandatory documentation input selected for an assignment from one immutable snapshot. It lets an agent read its assigned explanations with their dependencies and provenance.

For the bounded batch, the smallest assignment has this encoding. `version` identifies the assignment format, and the one `sections` element names the registered section, not a filename or inferred topic.

```json
{"version": 1, "sections": ["example#main"]}
```

The pack includes the [complete registry](#complete-registry), both metadata files, the applicable [writing profile](writing-and-review-workflow.md#writing-profile) and selected source ranges. Applicable decisions enter through explicit selectors, approval metadata or requirement-removal references. The selector does not infer additional decisions from arbitrary links.

<a id="snapshot-and-selection"></a>
## Snapshot and selection

Selection provides complete explanations without turning every source link into another inclusion request. The caller chooses captured working-tree bytes, the complete Git index or a commit. Operations then share that captured input; an unstaged repair cannot change an index check.

**Procedure: select the bounded-batch explanation**

1. **Capture the input.** Read one snapshot and assemble its metadata and registry.
   The captured source remains the basis for this pack.

   > **Detail — snapshot labels**
   > A commit baseline is its resolved commit identity. Other snapshots use the digest of their captured content.
   > Candidate material and comparison-base material retain separate labels.
2. **Resolve the assignment.** Select `example#main` with any requested decisions or [scenarios](requirements-tests-and-failures.md#scenario).
   Unknown selectors stop selection instead of selecting every home.

   > **Detail — scenario scope**
   > Whole-scenario input includes sections containing actions, requirements and linked tests.
   > Put the scenario's actions in those sections; the selector does not infer an action graph from prose.
3. **Expand declared dependencies.** Include each explanatory dependency transitively.
   Cycles and repeated requests add no duplicate source bytes.

   > **Detail — dependency meaning**
   > Each dependency identifies the section whose explanation the assignment needs.
   > Reading prerequisites guide navigation; they are not automatic context dependencies.
4. **Include relevant homes.** Add complete homes for entities owned or used in the selected material.
   The batcher's home carries its capacity, obligation and refusal together.

   > **Detail — selection boundary**
   > Uses include recognized registered names and direct links to homes or their facts.
   > If an added home's section declares a dependency, include that dependency too.
   > Ordinary links inside that added home do not recursively add further homes.
5. **Merge the ranges.** Emit overlapping or adjacent ranges once per path and snapshot label.
   Order them by document, manifest section and source line; retain every identity and inclusion reason.

For example, an assigned submission section uses the batcher home. That home's section declares a dependency on a recovery explanation.
The pack includes recovery. An ordinary link from the added home to an unrelated glossary does not add that glossary's source.

| Connection | Included source |
|---|---|
| Assignment to submission | Submission section |
| Submission uses batcher | Complete batcher home |
| Home declares recovery dependency | Recovery section |
| Home links ordinary glossary | No further source |

A comparison also includes the requirement change report and selected linked tests from the base and candidate. The [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) derives affected test selectors from both snapshots. A removal decision remains explicit assignment input; a resolving link establishes existence, not decision authority.

<a id="dispatch-and-invalidation"></a>
## Dispatch and invalidation

Preparation checks that the selected input is complete and fits before any agent starts. The shared [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) loads the helper, runtime metadata, dependency lock, format contract and profile from its selected House Rules revision. An extracted compiler carries those matching inputs.

The selector reports exact UTF-8 bytes, including its embedded manifest. Provenance records the baseline, source and registry digests, profile digest, input fingerprints, versions, assignment, included identities and range reasons. Range offsets are zero-based with an exclusive end; displayed source labels use one-based lines. These records let the [dispatcher](../../design/75-subagent-profiles.md#dispatcher) detect which captured input an agent received.

The assignment's `budget_bytes` bounds the documentation content. The compiler's separate byte budget bounds its assembled rules, documentation and task. The [dispatcher](../../design/75-subagent-profiles.md#dispatcher) reserves response allowance within its execution budget before assigning optional material. None of these limits authorizes truncating mandatory documentation.

For example, a documentation pack uses `6 000` bytes against an assignment limit of `8 000` bytes.
Adding rules and task uses another `4 000` bytes, so the compiler compares `10 000` bytes against its `12 000` byte limit.
Suppose the [dispatcher](../../design/75-subagent-profiles.md#dispatcher) converts those bytes to `2 500` input tokens and reserves `1 500` response tokens.
Against `5 000` execution tokens, it has `1 000` tokens left for optional material.
These illustrative limits use different accounting units; no byte-to-token conversion is assumed by the selector.

When registry or home bytes change, rebuild affected packs and recheck their surrounding explanations and [scenarios](requirements-tests-and-failures.md#scenario). A stale assignment baseline requires regeneration from the current snapshot. A new pack may contain different bytes even when its human-readable assignment name stays the same.

<a id="failure-context"></a>
### Failure state: invalid or excessive assignment

This refusal prevents dispatch with unresolved, stale or oversized mandatory input.

**Trigger:** Invalid selectors or source declarations, a stale baseline, missing mandatory input, incomplete review coverage or a byte budget smaller than the complete pack.

**Outcome:** Preparation returns the diagnostic and stops before dispatch. A budget error reports required and available bytes.

**Retained state:** Authored sources remain unchanged. An earlier pack is not substituted for the refused selection.

**Recovery:** Repair the input or selectors, regenerate stale assignments, or narrow the assignment and remove unjustified dependencies. If the compulsory registry alone cannot fit, obtain an operator resource decision.

**Authority:** The editor can repair declarations and narrow an assignment within its scope. The operator decides a changed execution resource.

**Verification:** [Context selection](acceptance-evidence.md#test-context), [snapshot isolation](acceptance-evidence.md#test-snapshots), [review coverage](acceptance-evidence.md#test-real-use).

The [callable and assignment reference](source-formats.md#callable-core-and-context-assignment) supplies exact keys and result fields.
