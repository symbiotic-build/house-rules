## Lens: simplicity and waste

Waste is a blocking class of the review bar. Look for:
- Code, configuration, tests or documents that no current consumer needs: dead code,
  unused options, speculative abstractions and extension points.
- A mechanism where a simpler one meets the same requirement: a new layer, cache, queue,
  state file or retry loop where the existing one, a native feature or deletion would
  do. Name the simpler version.
- Duplication: a second way to do something the codebase already does, copied logic,
  and repeated checks of the same condition.
- Tests that guard no real behavior or defect: tautological, duplicate, asserting
  implementation details, or breaking another rule of
  [Test discipline](../skills/test-discipline.md).
- Scope creep: drive-by refactors, renames or formatting outside the PR's issue.
- Documentation longer than the fact it carries, or the same rule stated in two places.
- Repairs that add guards around a mechanism instead of fixing or removing it.

Out of scope (owning lens):
- Whether the code is correct or secure: `correctness-security`.
- Concurrency, restarts, durability and bounds: `concurrency-restarts`.
- Whether the requirements are met: `spec`.
- Document premise and readability: `design-spec`.

@rule house-rules:prompts/util/targeted-lens.md
@rule house-rules:prompts/util/review-procedure.md

### Inventories for simplicity and waste

1. **Test table.** One row per added or changed test, never one row for a group or a file; this table is exempt from
   the ledger's row and range compaction. For a test file shown as a diff only, open it in the checkout to identify
   each added or changed test around the diff hunks. Columns: the behavior its name claims, the production entry point
   it actually calls, the assertion target, one broken implementation the assertion must reject (predicted
   statically), and any test-discipline check it fails, such as duplicate coverage, assertions on private
   implementation details, wording assertions on source, rule, prompt, style or workflow files, a mock of an owned
   module, an assertion any output satisfies, or no failing result in the pull request's test report where the test
   discipline requires one. Each failed check is a finding.
2. **Setup-write table.** One row per setup write, including writes in fixtures and case loops. Columns: target and
   value version, the first reader of that version, and any overwrite or deletion before it. A reader of the
   replacement contents is not a consumer of the earlier write.
3. **Mechanism table.** One row per new mechanism, stored structure, configuration key or abstraction. Columns: current
   consumer, the requirement that needs it, the existing or native alternative, and what would remain with it.
4. **Work table.** One row per added loop, retry, scan, copy, remote call and retained buffer: total work at the
   largest accepted input, and repeated work on unchanged input.
5. **Large-file table.** Size is a signal, not a limit. For each changed file over about 85 000 characters (about
   34 000 tokens), one row: whether it holds several separable responsibilities (distinct features, types or subsystems
   that share little state). If it does, report a Follow-up that names the split along those responsibilities; report
   it as Blocking only when this change adds a new separable responsibility to an already large file instead of a new
   module. Never propose a split that creates files holding a single function, separates tightly coupled code, or only
   gets a file under a size. Judge test files on their own: a large test file is fine when it covers one module or
   feature; propose splitting it by tested module or feature, and only when it covers several.
6. **Duplication and removal table.** For each removed behavior: its configuration, validation, defaults,
   serialization, documentation and tests, each removed or located. For each rule, example or ordering the change adds:
   any other statement of the same content in the repository, compared by the sentences each consumer receives after
   includes are expanded, not by file path or purpose label.
