## Local builds and tests

### Release builds

- For Rust (Cargo) builds, use `--release` by default for everything built, executed or measured.
  Include CI checks, Clippy, tests and smoke artifacts.
- Use the development profile only for active debugging (assertions, symbols, tight edit-compile loops) or a named debug-only invariant.

### Local scope

- Run locally only the smallest gate that proves the change.
  Use formatting, a compile check of the packages you changed, and named targeted tests for changed code and new regressions.
- Never run a whole crate's, package's or workspace's test suite locally, except for the no-PR-CI merge gate.
- Never lint a whole crate or workspace locally (for example crate-wide Clippy), except for the no-PR-CI merge gate.
- CI runs the full suite and lint on every push.
- A role may set a narrower scope.
- In a repository without PR CI, the full declared local gate on the pinned toolchain stands in for CI.
  Show that every failure also fails on the base under the same conditions.
- Report each command with pass/fail counts.

### Shared build queue

- On a shared machine, run every build and test command through the machine's one build queue.
  Cargo and every other build tool share this queue.
  A shared machine runs several agents at once, or a person uses it while agents work.
  The queue covers cargo, cmake builds, make, ninja, ctest, benchmarks, and test binaries or scripts run on their own.
- Queue one command at a time.
  Never hold the queue while you edit, read output or wait for CI, a review or the operator.
- Stop waiting when the machine's configured queue wait limit expires, or after 10 minutes where none is set.
  Then report the change as not tested locally, with the exact command you would have run.
  Let CI test it.
