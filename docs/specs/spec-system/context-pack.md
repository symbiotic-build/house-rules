<a id="context"></a>
<a id="context-pack"></a>
# Context pack

A context pack gives an assigned agent the complete mandatory explanations from one selected source version.

Every writer and reviewer receives the [complete registry](complete-registry.md#complete-registry), assigned sections, relevant complete homes, declared dependencies, applicable profile, decisions and provenance.
A home includes its entire heading subtree.
The [document manifest](document-manifest.md#document-manifest) declares explanatory dependencies on sections and gives each a reason.
A home uses its containing section's dependencies.

**Procedure: assemble mandatory context**

1. **Capture the source.**

   > **Detail — selection**
   >
   > Use one immutable [source snapshot](source-snapshot.md#source-snapshot).
   > Assemble the [complete registry](complete-registry.md#complete-registry).
2. **Resolve explicit selectors.**

   > **Detail — selection**
   >
   > Select assigned sections or a whole [scenario](scenario.md#scenario).
   > Unknown selectors fail preparation.
   > Missing scope never silently selects all homes.
3. **Expand declared dependencies.**

   > **Detail — selection**
   >
   > Follow them transitively.
   > Deduplicate cycles.
4. **Collect relevant homes.**

   > **Detail — selection**
   >
   > Find entities owned or used in selected sections through declarations, links and recognized registered uses.
   > Include their complete source ranges.
   > Ordinary links inside an included home do not recursively expand selection.
5. **Emit the input.**

   > **Detail — selection**
   >
   > Include each source range once.
   > Record identities, exact UTF-8 byte counts and inclusion reasons.
   > Include applicable decisions and the [writing profile](writing-profile.md#writing-profile).

A whole-[scenario](scenario.md#scenario) assignment includes every section containing its actions, requirements and linked tests.
Further home expansion requires a declared dependency with a reason.
An ordinary link cannot turn into an unbounded traversal.

The tool counts exact UTF-8 bytes for mandatory documentation input.
The [dispatcher](../../design/75-subagent-profiles.md#dispatcher) applies its configured model budget, including rules, task and response allowance.

Mandatory input is never truncated.
An excessive pack stops before dispatch.
Narrow the assignment or remove an unjustified dependency to recover.
The [complete registry](complete-registry.md#complete-registry) remains compulsory.
If it alone cannot fit, the operator must choose a different execution resource.

Extend the existing [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler) ([skills/pr-ready/scripts/prompt.py](../../../skills/pr-ready/scripts/prompt.py)) with one documentation-context call.
Reserve its complete output before optional context.
The launcher and review service use the same selector.

An extracted compiler includes its matching helper, profile and format contract from the pinned House Rules revision.
It never imports a helper from an unrelated live checkout.
The review service prepares and checks packs.
Reviewers remain read-only and run no builds, tests or external writes.

<a id="failure-context"></a>
### Failure state: invalid or excessive assignment

This refusal explains invalid or excessive assignment and the actor who can recover.

**Trigger:** A selector is unknown, mandatory context is missing, the baseline is stale or the configured budget is insufficient.

**Outcome:** Preparation stops before dispatch and reports the selector, missing input, baseline mismatch or required size.

**Retained state:** Canonical sources and previous packs remain; no previous pack silently substitutes for the failed selection.

**Recovery:** Correct selectors or narrow the assignment, repair dependencies, or rebuild from the selected baseline. If the compulsory registry alone exceeds the budget, obtain an operator resource decision.

**Authority:** The editor may narrow assignments inside scope. The operator authorizes a changed execution resource when required.

**Verification:** [Context selection](acceptance-evidence.md#test-context), [snapshot isolation](acceptance-evidence.md#test-snapshots).

The assignment schema is explained later in [Callable core and context assignment](source-formats.md#callable-core-and-context-assignment).
