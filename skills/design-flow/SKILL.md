---
name: design-flow
description: Feature lifecycle — spec/architecture design, lofi/hifi prototyping, spikes, implementation, and closeout (design doc migrates to architecture/spec, the PR merge closes the issue). Use when starting a feature, writing a spec or design doc, prototyping UX, running a spike, or closing a finished feature/PR.
license: MIT
---

# Design Flow

The lifecycle every non-trivial feature moves through. Paths and naming: `STRUCTURE.md` in
the installed House Rules root. Principles behind the gates: skill `design-canon`. Issues,
branches, and PRs: skill `work-tracking`.

```mermaid
flowchart TD
  issue --> design["design (P0/P1: before planned implementation)"]
  design --> prototype["prototype (UX-heavy only)"]
  design --> implement
  prototype --> implement["implement (branch per lane)"]
  implement --> closeout["closeout (docs migrate, PR merge closes the issue)"]
```

## 1. Issue first

Every feature starts as a work item: an issue, or a `<slug>` branch until the host is
reachable (skill `work-tracking` §Offline and sync). The work item owns the feature's
artifacts: its number (or slug) prefixes the design doc and prototype dir, and its
definition links the design doc. No orphan design docs.

## 2. Design / spec (P0/P1: mandatory before planned implementation; urgent P0 containment comes first)

Open with a **blindspot pass + reverse interview** (skill `finding-unknowns`) — surface
the unknowns before writing the spec, not after implementing the wrong one. Then
`docs/design/<issue>-feature-name.md`, frontmatter `status: draft`:

- exact type/trait signatures (real code, not prose), module/crate layout
- integration plan: what existing code changes; config schema if any
- **Key decisions with rejected alternatives** (why) — this section is what survives migration
- end-state first (skill `design-canon` §Decisions)

Gate: apply rules/core.md §Autonomy and its recorded collaboration mode. In autonomous mode,
a design entirely inside the approved outcome and decision boundaries may be marked
`approved` at the base confidence threshold, with evidence recorded and the operator
informed. Otherwise keep `draft` and ask about the consequential unresolved choice.
Record whether approval came from the operator or delegated authority; do not imply
operator review when it did not happen. A P0 or P1 design (§2), and any
design that decides where canonical data lives, moves or creates a security boundary, or
assigns ownership between repositories or modules, is approved only by the operator;
delegated authority and confidence thresholds cover the remaining P2/P3 designs. Urgent P0
containment needs no design approval. Until the operator approves, the design stays
`draft` and its work item stays Blocked on that decision. A design that
contradicts a recorded plan, another design, or another repository's roadmap names the
contradiction and resolves it in the same approval. Boundary: this governs approval of the
design record; implementation inside an approved P0/P1 design follows the normal autonomy
rules. Use [priority labels](../../rules/priority-labels.md).
P2/P3 may skip the doc but still need a plan note in the issue body.

## 3. Prototype (UX-heavy features only)

Use this sequence for work that needs both prototype stages:

1. **System map + micro-specs**: mermaid + md per screen/flow in the design doc
2. **Lofi**: `prototypes/<issue>-feature/lofi/` — flows, wireframes, single-file html sketches
3. **Hifi**: `prototypes/<issue>-feature/hifi/` — the project UI stack (default:
   `PREFERENCES.md`) + mock data; component library before screens (shared sizes/tokens,
   no per-screen one-offs)
4. Operator picks/tweaks on the prototype → decisions recorded back into the design doc

Prototypes exist so decisions happen **before** the engine is wired to a frontend. They are
never the implementation; hifi code may be quarried, not merged wholesale.

## 4. Spikes (technical unknowns)

One question → `prototypes/spikes/YYYY-MM-DD-question/` with `SPIKE.md` (question, method,
verdict). Throwaway by contract: code never lands in `src/`, deps never land in the
product tree. Kill-or-promote: verdict feeds the design doc, then the spike is deletable.
After 30 days without a verdict, review whether the spike is still useful; cleanup follows
rules/core.md §Security.

## 5. Implement

One branch per issue per repository (`STRUCTURE.md`). Acceptance cases and their expected
values come from the spec before code; tests follow
[Test discipline](../../prompts/skills/test-discipline.md). Before a work
package's first code, a design-spec reviewer checks its spec sections against the recorded
decisions. Implementation choices, escalation boundaries and reviewer-marked operator
decisions follow the [worker rules](../../prompts/roles/implementer.md).

- Read the design doc, then the architecture doc, then code before feature work.

## Design changes

Implement the spec literally. When reality requires a deviation, propose the doc change
in the same commit and list it for acceptance; never silently reduce a requirement.
Removing a requirement sentence from a design or spec needs a recorded decision ID.
Flag a spec edit that changes a mechanism to match existing code: it needs a decision,
not an editorial justification. Apply this check to rewrites and shortening as well as
explicit deletions. Finding disposition follows the
[shared review bar](../../prompts/util/review-bar.md).

## 6. Closeout — the PR merge closes the issue

A feature is done when the code shipped AND the paper trail moved. The PR closes the issue
on merge (skill `work-tracking` §The host view) and carries this checklist:

- pre-merge quiz passed on significant work (skill `finding-unknowns`)
- **CI closing check: design doc.** CI checks the design doc status is `implemented` or
  `superseded` (never `draft`/`approved`); shipped sections
  migrated to `docs/architecture/feature.md` (or the repo's `docs/specs/{subsystem}/`);
  design doc shrunk to a pointer or deleted (issue link: `STRUCTURE.md` §Frontmatter
  statuses)
- durable decisions promoted from the issue → the bible
- prototypes: keep hifi if it's the living reference, else delete; spikes killed
- regression tests required by rules/delivery.md §Verification exist and are green
- **CI closing check: final handoff.** CI checks that the final handoff is authored by
  the current owner, mirrored to the issue, and every required section is non-empty
  (`None` when empty; skill `handoff-continuity`)

Merge only when the checklist holds, then delete the branch, remote and local
(`git branch -D` after a squash merge, once its records are mirrored), and remove its
worktree and build directories (skill `agent-lanes` §Lane cleanup).

## Experimentation is a first-class lane

Diagnostic experiments follow `bench-discipline` and live in `runs/` (neutral names) with
findings filed into the owning issue; a campaign (multi-day target push) gets its own
issue + ledger. Experiments never bypass the lifecycle by mutating `src/` directly "just to
test" — levers go behind flags, spikes go to `prototypes/spikes/`, and anything that
survives gets a design doc like everything else.
