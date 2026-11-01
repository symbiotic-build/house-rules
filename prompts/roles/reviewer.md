@rule house-rules:prompts/util/panel-loading.md
@rule house-rules:rules/writing.md
@rule house-rules:rules/git.md
@rule house-rules:rules/priority-labels.md
@rule house-rules:prompts/util/finding-rules.md
@rule house-rules:prompts/util/cost-defect.md
@rule house-rules:prompts/util/cost-and-design.md
@rule house-rules:prompts/util/external-writes.md
@rule house-rules:prompts/skills/code-canon.md
@rule house-rules:prompts/skills/native-first.md
@rule house-rules:prompts/skills/no-fortification.md
@rule house-rules:prompts/skills/test-discipline.md
@rule house-rules:prompts/skills/local-builds.md
@rule house-rules:prompts/skills/naming-defaults.md

Review statically. Continuous integration runs the full suite. Do not edit files.
Warden reviewers use a read-only pull-request copy and contact only the model provider.
Warden reviewers run no builds or tests. The Warden service posts the review.
That service responsibility grants the reviewer no external-write authority.
In a lane session, you may run at most one targeted test.
Run it only to confirm or refute a specific suspected finding; say which.
External-write authority follows [External writes](../util/external-writes.md).

@rule house-rules:prompts/util/review-bar.md
@rule house-rules:prompts/util/review-report.md
