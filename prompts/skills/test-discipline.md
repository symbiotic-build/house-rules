## Test discipline

On a shared machine, every build and test command goes through the machine's build queue:
call cargo, cmake, make, ninja and ctest by name, and run a test binary or script as
`build-queue <command>`.

Single tests finish in seconds and never run long. Remove a known looping or hanging
test at once, keep its defect tracked, and replace it with a small, explicitly bounded
test. Stop a command holding the shared build queue after a few minutes without CPU
progress and after a fixed overall hold limit; configure those limits in the build runner.

Every guard and every test logs its triggers and outcomes:
real findings or defects caught, false positives or flaky failures, waivers with decision
IDs, and runtime. Use existing run/test output and tracker records rather than a second
source of truth. The lead reviews these records daily at first, then every 3 days, pruning
or narrowing guards and tests that do not earn their cost.
Scale tests move, never vanish: record the replacement test and where it runs,
preserving the scale and behavior it proves.
