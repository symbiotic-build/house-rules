## Test discipline

A test exists to fail when behavior that a user or a contract depends on breaks, and to
stay green when it does not. Write the tests that do that and no others.

### Every test

- **Behavior at the boundary users use:** the command, public function, file format,
  rendered page or protocol. Never assert private helpers, call counts or internal data
  shapes. Persisted state includes the stored structures the system relies on after a
  restart, such as index entries or column-family contents; assert them when no public
  result can show the defect. *Check:* every assertion names output, persisted state or
  a protocol message.
- **Expected values from the spec, issue or stated intent,** written before running the
  code. Never paste current output in as the expectation; a test that records current
  behavior before a refactor says so in its name. *Check:* each expected value traces to
  its source.
- **Shown failing once.** A regression test fails on the commit before its fix. The
  regression report names the defect and the failing result. *Check:* the report carries both.
- **One behavior per test,** named as condition and outcome; variants go in one
  table-driven test. *Check:* a failure names the behavior that broke.
- **Assert the whole relevant result once.** No assertion that only checks "no error",
  truthiness or a count any output satisfies, unless that is the complete success result,
  such as a validator that returns nothing and raises on invalid input. *Check:* a
  realistic wrong result fails it.
- **No wording tests.** Never read source, rule, prompt, style or workflow files to assert
  their wording, including which commands a workflow runs. Tests over repository files are
  right when they check structure that a loader or tool consumes: links resolve, every
  configured item exists, include graphs, files have the format their loader parses,
  generated files equal their generator's output. Approved rule text is protected by the
  rule-change report and its mandatory review disposition, not by tests. *Check:* no test
  asserts sentences or phrases found in a repository text file.
- **Remove what guards nothing.** A test stays only when it guards behavior that a user
  relies on, a published interface or format, or a requirement in an approved spec or
  operator decision. It must also prove something no other test proves. A test that fails
  either check is deleted, not repaired.
- **Remove unneeded guards with their tests.** When a test guards a mechanism with no
  concrete, plausible trigger, delete the mechanism and its test in the same change. Never
  leave the mechanism untested.
- **Repair only real requirements.** Repair applies only to a test that guards a real
  requirement but asserts it weakly.
- **Cited tests move with their spec.** Remove or rename a test that a spec cites only in
  the same change as the spec edit; the selector audit is part of the gate. *Check:* the
  audit reports no missing selector.
- **Real collaborators for owned code:** real files, Git, databases and browsers. Replace
  only slow, nondeterministic, paid or external systems, at the process boundary,
  preferably with a fake. *Check:* no mock of a module in the same repository.
- **UI tests assert what a reader perceives:** visibility, contrast, focus, geometry and
  accessible names and roles, plus screenshot inspection under delivery rules. Never
  assert class names, exact markup or copied style values unless they are the contract,
  such as anchor ids or escaping a spec requires. *Check:* breaking what the reader sees
  fails the test; a restyle that keeps it passes.
- **A dedicated browser, started where it can run:** automated tests, UI checks and screenshots use a
  dedicated headless browser, such as Chrome for Testing or Playwright's headless shell,
  never the operator's own browser application or profile. Never start a browser inside a sandbox that stops it
  from starting. *Check:* the browser path is not an installed desktop browser.
- **Deterministic and independent:** any order, in parallel, no fixed sleeps; wait on a
  completion signal. Fix a flaky test or quarantine it with an owner and a date; never
  retry it silently. *Check:* the suite passes shuffled and in parallel.
- **Fast:** single tests finish in seconds. Share expensive read-only setup per file;
  cost matches what the test proves. Overall limits are runaway guards only.
- **No new test is a valid answer** for documentation, renames and configuration that
  changes no behavior; the report says "No new test:" and why. Test count and coverage
  are never targets.
- **Never weaken a failing test to make it pass.** Loosening an assertion, widening a
  tolerance, skipping or rewriting the expectation needs the reason the old expectation
  was wrong; a failing invariant is never weakened.

### Systems that keep durable state

Storage engines, indexes, queues, ledgers and similar systems apply each requirement in
this section only as far as the component's declared failure model needs it. The
repository's rules name the parts in this class.

- **Invariants in the spec.** The spec author states system-level and operation-level
  invariants as requirements, each naming the failure it prevents and linked to the test
  that checks it. State what the system must keep, not every property the code could have.
- **Violations are defects, and the suite stays green.** A violation that writing or
  testing the invariants finds in current code is fixed in the same change, or filed as a
  tracked defect whose test carries an expected-failure marker citing the issue. Without
  tracker access, the report gives the lead the issue text. Never leave a known failure in
  the suite.
- **Property and sequence tests.** Pure logic gets property tests over generated valid
  inputs. Stateful components get sequence tests that apply generated operation sequences
  and check every invariant after each step. Debug and test builds also assert cheap
  invariants at run time. Failing inputs are saved and replayed. The normal suite runs a
  small fixed case count with a recorded seed, within the suite's time budget; larger
  counts run on a schedule.
- **Real or containerized dependencies** for integration and invariant checks.
- **Independent roles.** An adversarial review pass on another model family lists
  missing invariants and operation sequences that would break the stated ones; the
  author decides. An agent other than the implementer writes the invariant tests from
  the spec.

Code that parses untrusted input or exposes a network protocol also gets a threat model in
the spec and coverage-guided fuzzing of its entry points; every crash found becomes a
regression test.

### Upkeep

Remove a known looping or hanging test at once, keep its defect tracked, and replace it
with a small, explicitly bounded test. Stop a command holding the shared build queue after
a few minutes without CPU progress and after a fixed overall hold limit; configure those
limits in the build runner.

Every guard and every test logs its triggers and outcomes: real findings or defects
caught, false positives or flaky failures, waivers with decision IDs, and runtime. Use
existing run and test output and tracker records rather than a second source of truth.
The lead reviews these records daily at first, then every 3 days, pruning or narrowing
guards and tests that do not earn their cost. Scale tests move, never vanish: record the
replacement test and where it runs, preserving the scale and behavior it proves.
