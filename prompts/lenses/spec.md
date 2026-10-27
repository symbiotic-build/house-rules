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
@rule house-rules:prompts/util/review-procedure.md

### Inventories for specification fit

1. **Criterion table.** One row per acceptance criterion, requirement and documented guarantee governing the changed
   behavior, including those the pull request defers or assigns elsewhere. Columns: requirement location,
   implementation location or "absent", proving test or "none", supported modes, effective command with wrappers and
   defaults expanded, and finding label. An absent or partial requirement has a finding label even when its
   disposition is deferred or tracked; one an earlier triage of this pull request decided gets "decided" instead
   ([Finding rules](../util/finding-rules.md)). For selection by optional inputs, one row per reachable subset, compared with
   the subsets validated in advance.
2. **Statement table.** Search the unchanged and changed documents for every promise and prohibition governing the
   changed behavior, including sentences with must, never, only, every, until or required. Read each whole paragraph.
   Columns: location, conditions, and kept, contradicted or superseded. "Superseded" cites the decision's operative
   sentence and its scope; the new behavior or the author's description never authorizes it.
3. **Exit-obligation table.** For every affected entry point: one row per normal completion, incomplete completion,
   fatal error and early return, including propagation operators and helpers that exit the caller. Columns: the
   outputs, diagnostics and finalization the contract requires, whether each runs before that exit, and which error
   reaches the caller. Diagnostics promised for every attempt must run before an error propagates. A summary of
   completeness is required work minus successful results, including work that ended before any result record.
4. **Output-invariant table.** For every requirement that outputs stay equal, shared, isolated or independent of an
   input: one row per entry path and per input that can vary (caller identity, selected policy, optional input,
   metadata). Compare two configurations that differ only in that input, through serialization and rendering, to the
   first difference. Include plans, assignments, provenance and manifests written into a shared part. A common value
   one entry path supplies does not cover another path that builds its own. A hash of the whole output is not that
   comparison.
5. **Diagnostic-claim table.** One row per changed status, warning, error or summary that asserts a cause, completion,
   exhaustion or recovery. Trace each reachable outcome class to it and check every factual clause of the message.
6. **Refusal and recovery table.** One row per refusal, retained blocking state and recovery prerequisite. Columns:
   trigger, retained state, recovery actor, the supported command or procedure and its location, and verification.
   Trace from the normal entry point with the blocker still present; a test fixture that removes the blocker first
   does not prove recovery. A missing recovery that a requirement demands is a finding; one the requirements declare
   unavailable is checked against the stated consequence.
