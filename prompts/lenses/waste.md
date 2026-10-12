## Lens: simplicity and waste

Waste is a blocking class of the review bar. Look for:
- Code, configuration, tests or documents that no current consumer needs: dead code,
  unused options, speculative abstractions and extension points.
- A mechanism where a simpler one meets the same requirement: a new layer, cache, queue,
  state file or retry loop where the existing one, a native feature or deletion would
  do. Name the simpler version.
- Duplication: a second way to do something the codebase already does, copied logic,
  and repeated checks of the same condition.
- Tests that guard no real behavior or defect: tautological, duplicate, or asserting
  implementation details.
- Scope creep: drive-by refactors, renames or formatting outside the PR's issue.
- Documentation longer than the fact it carries, or the same rule stated in two places.
- Repairs that add guards around a mechanism instead of fixing or removing it.

Out of scope (owning lens):
- Whether the code is correct or secure: `correctness-security`.
- Concurrency, restarts, durability and bounds: `concurrency-restarts`.
- Whether the requirements are met: `spec`.
- Document premise and readability: `design-spec`.

@rule house-rules:prompts/util/targeted-lens.md
