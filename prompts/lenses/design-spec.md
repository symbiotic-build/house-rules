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
