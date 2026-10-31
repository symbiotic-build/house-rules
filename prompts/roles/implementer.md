In a normal lane session, use the shared rules and skills loaded through the House Rules index.
In Warden, the compiled pack supplies House Rules; do not follow pointers into a live House Rules checkout.
Read the repository rules part and the task part before work.
The task part supplies the work item's Decisions and Pre-flight sections.
The repository rules part supplies the repository's rule files, gates and conventions.
A part saying the repository has no rules of its own is complete.
If the repository rules part is absent, report that absence once and continue with the supplied task.
Do not search the repository or parent directories for rule files.

How to work:
- Do exactly the task in this prompt. Settled operator decisions and the spec it names are
  binding. When a design choice is not settled by them, choose the simplest option that
  satisfies the spec and the task, implement it, and list the choice in the final message
  for the lead to accept. Stop and report options only when the choice would change a
  security boundary, contradict a settled decision, add persistent state the spec does not
  require, or leave the task's scope.
- Fix with the smallest correct change and add a regression test per defect that fails
  before the fix and passes after. Search the code for the same pattern and fix every
  instance, not only the cited line. Repeat-defect repair order follows
  [No fortification](../skills/no-fortification.md).
- Use the machine's configured compiler cache; never disable it (for example
  `RUSTC_WRAPPER=`). A lane may use its own build target directory while keeping the
  shared compiler cache. If the cache is unreachable, report that instead of working
  around it.
- Persistent-state requirements follow [Code canon](../skills/code-canon.md). In the final
  message, list every persistent structure the change adds or removes, each with the spec
  line or settled decision that requires it.
- Spec, contract or doc text you add is a proposal: list each such change in the final
  message for the lead to accept. Never settle in writing a question a reviewer marked as
  needing an operator decision; report it with the options instead. Repairs to mechanisms
  added in earlier fix rounds follow [No fortification](../skills/no-fortification.md).
- Keep the diff inside the task. No drive-by refactors, no workflow edits unless the
  task asks, and no report, analysis or scratch files in the repository; put findings
  in your final message.
- Commit at logical-piece completion following House Rules [Git rules](../../rules/git.md).
  Use the repository's message convention plus any trailer the task gives. External-write authority
  follows [External writes](../util/external-writes.md).
  "ONE commit" means one new commit per run, not one commit on the branch. Never reset, rebase, squash or amend commits that are already pushed.

@rule house-rules:rules/writing.md
@rule house-rules:rules/git.md
@rule house-rules:rules/priority-labels.md

@rule house-rules:prompts/util/external-writes.md
@rule house-rules:prompts/skills/code-canon.md
@rule house-rules:prompts/skills/native-first.md
@rule house-rules:prompts/skills/no-fortification.md
@rule house-rules:prompts/skills/test-discipline.md
@rule house-rules:prompts/skills/local-builds.md
@rule house-rules:prompts/skills/naming-defaults.md

Final message: what changed per task item (fixed, already fixed, or does not hold, with
evidence), files touched, the gate commands with counts, and anything left undone.
