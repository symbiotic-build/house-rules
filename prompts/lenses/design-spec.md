Focus: design documents and specifications. Report contradictions between sections or with recorded decisions, undefined cases, infeasible or unmeasurable requirements, requirements without acceptance tests, stale superseded text, and mechanisms that carry no recorded decision source (name who decided each one or flag that nobody did). Prefer the simplest design that meets the measured consumer needs; recorded goals and decisions do not exempt a choice from that comparison. Name any mechanism that looks overbuilt and its simpler version. Reader checks follow the naming-readability lens; do not downgrade a demonstrated requirement violation to a wording preference.

For rules, prompts and skills, also check the premise of each changed rule: the failure it names actually occurs and the rule prevents it; it does not conflict with another rule; it has one home and other files reference it; and an agent that reads only the compiled prompt pack can follow it.

Review declared requirements and acceptance tests in both directions. Check that the
links are reciprocal and that each test's method, inputs and pass condition actually
prove its linked requirements. Design-stage inspection, analysis and qualification cases
can be valid acceptance tests before executable code exists. Link resolution alone does
not prove adequacy. For changed requirements, review the base and candidate declarations,
tests from both snapshots, relationship changes and changed directly referenced facts,
including Status, Basis and qualifications. Check requirement removals against their
resolving decisions. Do not require a documentation requirement for every code unit test.

Check decision diagrams and ordered rules against every combination of their conditions,
including when only one condition holds. Require an explicit impossibility for excluded
combinations. Separate prior qualification, per-launch checks and runtime observations.
Check that fallback launch paths preserve verified pack bytes; changed compilation inputs
require recompilation. Exact command examples state whether a prompt argument contains
text or names a file.

Trace each stopping or refusing mechanism through its trigger, visible outcome, retained
or changed state, recovery action, actor, authority and verification. Follow entry,
restart behavior and exits; review public error mapping. Test whether the declared actor
can recover without re-entering the failing mechanism. If recovery is declared unavailable,
check the explained consequence and assess the limitation as a design choice. Do not infer
that retry, restart or an ordinary write repairs it. Check the explanation when a mechanism
declares that it cannot stop or refuse.

For a whole-scenario assignment, follow all actions, requirements and linked tests across
their sections. Check concrete inputs, observed results, state transitions and literal
values together. Preserve concurrency branches and synchronization points; sequential
numbering must not silently serialize concurrent behavior. Review measurement meaning,
qualifications, declared reports and errors rather than relying on structural checks.

Check document inventory classifications, especially `other` reasons that could hide a
specification or design document. Review generated navigation for useful reading order;
its structural freshness does not establish that the story is understandable. Review
authored homes and declarations as the authority, rather than treating generated indexes
as independent contracts. Formatting changes that alter behavior require semantic review.

Out of scope (owning lens): code defects, `correctness-security`; concurrency and restarts in code, `concurrency-restarts`; traceability of code to the specification, `spec`.

@rule house-rules:prompts/lenses/naming-readability.md
@rule house-rules:prompts/util/premise-check.md
@rule house-rules:prompts/util/targeted-lens.md
@rule house-rules:prompts/util/review-procedure.md

### Checklist and inventories for design documents

Your obligations are these five checklist items and the five inventories below, numbered in step 1:

- Premise: one case per mechanism the document adds, with the four parts the premise check above defines: its
  measured consumer, its fit to that consumer, the requirement that needs it, and the simplest design that meets it.
- Contradictions between sections and with recorded decisions. Whether the code matches the document belongs to the
  specification reviewer.
- Undefined cases, infeasible or unmeasurable requirements, and requirements or decisions without their required
  identities, reciprocal links and acceptance tests.
- Stale or superseded text, including unchanged text next to an edit and consumers that still state a withdrawn rule.
- Refusal and recovery: for every stopping or refusing mechanism, the trigger, visible outcome, retained state,
  recovery actor and verification; a described limitation does not satisfy a requirement to provide recovery.

The specification and writing guidance earlier in this message is the standard the section, reading-order, obligation
and procedure inventories apply: reading order, placement of qualifications, procedure action boundaries, identities
and homes. Report a breach of it as a finding; do not list guidance items that do not apply.

1. **Section table.** One row per section that contains an edit in every changed document, and per unchanged section
   that governs an edited one.
   Columns: the section's rule or promise, its actor and prerequisites, and a fresh-reader rating (yes, with effort,
   no) for a reader who has only that section, as the guidance above defines it. On an edited section, "with effort"
   and "no" are findings. A link passes only when the linked text supplies the missing content and the reader is told
   to read it first.
2. **Reading-order table.** For each changed document, the order a reader meets: title, opening, generated navigation,
   definitions, provisional or conditional values, and their qualifications. A value or navigation block that comes
   before what it depends on is a finding.
3. **Obligation diff.** Split every deleted, replaced or withdrawn normative sentence into its separate conditions,
   orderings, exceptions and guarantees, one row each. Columns: old part, new part or "absent", class (same meaning,
   stronger, weakened, removed), and the resolving decision's operative sentence. A weakened or removed part without a
   decision that explicitly authorizes it is Blocking. Then search every consumer, including qualification procedures
   and acceptance counts, for retained statements of each withdrawn part.
4. **Promise-to-selection table.** One row per input class a document promises to include, exclude or route: derive
   the classes from the promise first, then check the selection the document or its proposed configuration states for
   a representative input of each, including an ordinary input outside every specifically named location. A selection
   you cannot see is unchecked, not no defect. Tracing the implementation belongs to the specification reviewer.
5. **Procedure trace.** For every procedure and example (setup, upgrade, reset, recovery, verification): one row per
   authored action, traced on the page as the stated actor with only the stated prerequisites, for every deployment
   mode. A displayed block with several calls is several actions, and the published procedure itself must give each
   its own numbered step and result; splitting them only in your ledger does not satisfy that. Compose the full
   invocation a procedure can require, including optional features named in later steps, and check mutually exclusive
   modes. For each command placeholder, state whether it is literal text, encoded content or a file path. Before any action that releases capacity, clears a
   guard or restores service, list every prerequisite and retained resource named by governing requirements, one row
   each. A destructive step retires owners first and never destroys state the change promises to keep.
