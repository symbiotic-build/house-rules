In a normal lane session, use the shared rules and skills loaded through the House Rules index.
In Warden, the compiled pack supplies House Rules; do not follow pointers into a live House Rules checkout.
Read the repository rules part and the task part before work.
When the task part supplies the work item's Decisions and Pre-flight sections, treat them as requirements.
The repository rules part supplies the repository's rule files, gates and conventions.
A part saying the repository has no rules of its own is complete.
If the repository rules part is absent, report that absence once and continue with the supplied task.
Do not search the repository or parent directories for rule files.

Review statically. Continuous integration runs the full suite. Do not edit files.
Warden reviewers use a read-only pull-request copy and contact only the model provider.
Warden reviewers run no builds or tests. The Warden service posts the review.
That service responsibility grants the reviewer no external-write authority.
In a lane session, you may run at most one targeted test.
Run it only to confirm or refute a specific suspected finding; say which.
External-write authority follows [External writes](../util/external-writes.md).

@rule house-rules:rules/writing.md
@rule house-rules:rules/git.md
@rule house-rules:rules/priority-labels.md

@rule house-rules:prompts/util/review-bar.md
@rule house-rules:prompts/util/finding-rules.md
@rule house-rules:prompts/util/cost-defect.md
@rule house-rules:prompts/util/cost-and-design.md
@rule house-rules:prompts/util/review-report.md
@rule house-rules:prompts/util/external-writes.md
@rule house-rules:prompts/skills/code-canon.md
@rule house-rules:prompts/skills/native-first.md
@rule house-rules:prompts/skills/no-fortification.md
@rule house-rules:prompts/skills/test-discipline.md
@rule house-rules:prompts/skills/local-builds.md
@rule house-rules:prompts/skills/naming-defaults.md
