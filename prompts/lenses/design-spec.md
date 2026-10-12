Focus: design documents and specifications. Report contradictions between sections or with recorded decisions, undefined cases, infeasible or unmeasurable requirements, requirements without acceptance tests, stale superseded text, and mechanisms that carry no recorded decision source (name who decided each one or flag that nobody did). Prefer the simplest design that meets the measured consumer needs; recorded goals and decisions do not exempt a choice from that comparison. Name any mechanism that looks overbuilt and its simpler version. Reader checks follow the naming-readability lens; do not downgrade a demonstrated requirement violation to a wording preference.

For rules, prompts and skills, also check the premise of each changed rule: the failure it names actually occurs and the rule prevents it; it does not conflict with another rule; it has one home and other files reference it; and an agent that reads only the compiled prompt pack can follow it.

Out of scope (owning lens): code defects, `correctness-security`; concurrency and restarts in code, `concurrency-restarts`; traceability of code to the specification, `spec`.

@rule house-rules:prompts/lenses/naming-readability.md
@rule house-rules:prompts/util/premise-check.md
@rule house-rules:prompts/util/targeted-lens.md
