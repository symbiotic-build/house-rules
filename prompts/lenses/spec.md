## Lens: specification and requirements fit

Trace the change against its requirements: the linked issue, the referenced
specification sections, the PR description, maintainer comments and settled decisions.

Look for:
- Each requirement and acceptance test: cite where the change implements it and which
  test proves it. Report every requirement that is missing, partial, contradicted or
  claimed without a test, and name its section or issue item.
- Claims in the PR description, commit messages or documentation that the code does
  not do.
- Behavior the requirements do not ask for, presented as required.
- Contradictions with a settled decision or an earlier specification section; quote
  both texts.
- Documentation, configuration examples and help text that no longer match the code.
- Specification problems: silent, contradictory, infeasible or unmeasurable
  requirements. Report them under Spec issues; they block only when the code faithfully
  implements a wrong requirement.

Out of scope (owning lens):
- Defects inside a correctly specified path: `correctness-security` and
  `concurrency-restarts`.
- Whether a required mechanism could be simpler: `waste`.
- Document premise and readability: `design-spec`.

@rule house-rules:prompts/util/targeted-lens.md
