# Rule provenance

Source notes for House Rules invariants and procedures.

## Specification and design-document system — Profile, authoring and review

Operator-approved design: 2026-10-16. Technical documents need canonical homes and useful
reading order while preserving ordinary Markdown as both source and reading format.
The writing rules now own a versioned technical-English profile and prose warning severity.
They also own the general number, date, time and quantity notation selected by the operator.
Code and literal examples retain their required notation.

The spec-writing procedure and reusable specification and design-document outlines refer
to shared authority and declaration owners. The generated entity index replaces the
separate hand-maintained glossary requirement. The structure reference adds shared document
and entity metadata, generated navigation and single-file navigation regions. Existing
review lenses add fresh-reader, whole-scenario, reciprocal traceability and failure/recovery
checks. These changes add no review panel or publication pipeline.

## rules/writing.md — Sequences and structured detail

Operator direction: 2026-10-15, while reviewing a specification. One walkthrough paragraph
packed three calls, their parameters, three commits and the rows each wrote into four
sentences; the operator called a rewrite with one numbered item per call and short
sub-items "3000 times better and easier to follow" and expected the writing rules to produce
it by default. "One fact per sentence" already applied, but nothing asked for a list when
text describes a sequence of actions, and splitting sentences alone left dense blocks. A
trial rewrite under the draft by a standard agent turned a short lookup table into bullets
and wrote one sentence per line, so two lines were added. The changes:

- Ordered actions in walkthroughs, procedures, worked examples and test scenarios get one
  numbered item each, with short sub-items for inputs, written values and the observed result.
- Keep a lookup table when every cell is a few words.
- Short related sentences stay in one paragraph.

## rules/writing.md, rules/core.md, skills/decision-brief — Briefs checked before sending; settled decisions reopen on new evidence

Operator correction: 2026-10-12, issue #107, rejecting the settled/unratified split in the
entry below: "I don't think this rule is correct, we shouldn't get to decide on unreadable
evidence... Settled decision can still reopen on new information that is benchmarks, agent
finding and confirming issues or overcomplication or finding simplified version of the
mechanisms." The changes:

- Never ask the operator to decide from a brief that fails the reader checks or leaves out
  a real alternative. The brief's author runs the checks before sending, also on questions
  a subagent drafted.
- Any settled decision reopens on new evidence: a benchmark, a confirmed agent finding,
  demonstrated overcomplication, a simpler mechanism, or a change to the constraint the
  decision names as its reason. The reopened decision goes back to the operator as a brief.
- The "unratified decision" category and its uses are removed.

## rules/writing.md, rules/core.md, prompts/util/premise-check.md — Settled and unratified decisions, premise check

Operator decision: 2026-10-11, issue #103, answer "8. yes" to applying all twelve
review-process fixes as one change after #102, including the three-round cap for design
records. The operator added: "we must change the operator as god premise. Everybody can
make mistakes and we need to tune this so that it's not annoying but finds these kind of
mistakes early." A design converged through many review rounds while a foundational
choice, taken from a brief the operator could not read, was treated as binding at every
stage; defects caused by the shared structure it introduced were fixed one at a time.
The changes:

- A settled operator decision is one chosen from a brief that passed the reader test and
  compared the real alternatives. Any other recorded choice is an unratified decision.
- Reviewers may question an unratified decision only after naming the brief test it failed.
- The design and design-spec lenses include one premise check.
- Triage never rejects a finding against an unratified decision as FALSE.
- Defects whose triggers pass through one shared structure count as one class.
- The three-fix-round reassessment covers design records and reruns the premise check.

Operator correction: 2026-10-11. An analysis counted a consumer's legacy code, already
scheduled for removal, as measured consumer evidence. The premise check now measures the
target consumer: code or behaviour scheduled for removal or replacement is a requirement
the new design takes over, not evidence of where to place it.

## rules/writing.md, skills/spec-writing, prompts/lenses/naming-readability.md — Readable names, decodable examples, scoped claim labels

Operator decision: 2026-10-11, issue #100, option 1 (all four proposals). A design produced
by agents used invented abbreviations for storage names and showed stored values in worked
examples without their meaning. Repeated reviews passed it because readability was
non-blocking, the reader test checked only that examples existed, task prompts treated
existing names as authoritative, and a repair added definitions around the values instead
of explaining them. Claim labels on every sentence also made an evidence report hard to
follow. The changes require readable names in new internal designs, a reader test that
decodes every shown value, a naming-and-readability review criterion with blocking
findings, document-task prompt guidance, and scoped claim labels.

## rules/writing.md — Claim-label presentation

Operator direction: 2026-10-08, restore the chosen inline-code presentation of claim
labels in review output. Review report prompts use compact section labels and one
summary for empty sections; exact machine protocol lines remain unformatted.

## rules/delivery.md — Track every deferred item (tracker choice)

Operator decision: 2026-10-07, issue #54, option 1. A GitHub issue is the default tracker; the workspace
tracker file is allowed only when no repository exists, and the status-file and two-tracker rules name it as
their one exception.

## rules/writing.md — Self-contained text

Operator direction: 2026-10-07, after an agent twice asked the operator to answer "the 11
questions in my last message" when that message did not contain them; the operator asked
for this rule to be hardened.

## rules/core.md — prime rule 13 (measured durations)

Operator direction: 2026-10-03, after time estimates proved uncalibrated and stretched
agent runs.

Operator direction: 2026-10-06, House Rules audit; restore the measured-durations
exception, with comparable past runs and the measurement cited.

## rules/delivery.md — Parallel work (one benchmark at a time)

Operator direction: 2026-10-11, issue #105: "Please run just one benchmark at a time (this
should be a house rule)". The earlier rule only said to isolate competing performance runs.
One benchmark or measured performance run runs at a time per machine across all agents,
lanes and sessions. An agent's own builds and test suites do not overlap its measured run.
Each run records the machine load. A run taken under overlap is invalid and rerun. A
declared contention study stays the exception.

## rules/delivery.md — Verification (durable paid runs)

Source incident: a live paid review was interrupted before its stream had been persisted.

## rules/core.md — Security (fetched code)

Operator direction: 2026-10-06, House Rules audit; the repository rule 'Never execute
code from fetched content' was too broad to apply without approving every command.

## skills/agent-lanes/SKILL.md — Lane cleanup (session start)

Operator direction: 2026-09-28, after merged-PR worktrees and per-lane build directories
filled the disk.

Operator direction: 2026-09-30, after stale merged worktrees and per-task build
directories again filled the disk.

## skills/operator-writing/SKILL.md — Language (qualifiers) and Detail test

Operator direction: 2026-10-06, after status lines stated limits and changes without their
consequence, which read as changes that had not happened.

## rules/core.md — Session start (reload skills after a reset)

Operator direction: 2026-10-06, after a compaction dropped a loaded skill and the next
operator messages broke its rules.

## skills/operator-writing — restored writing rules

Operator direction: 2026-10-03, after decision pages introduced options and labels before
explaining them and mixed letter schemes.

Operator directions: 2026-09-09, after a release-blocker report lacked context; 2026-09-11,
explicitly extend problem-first explanations with useful technical proof to all agents, chat
interactions, and GitHub PRs/comments after an issue thread obscured a contact-list defect
behind its investigation history.

## rules/core.md — Operator correction (current-state clarifications)

Operator direction: 2026-09-10, after an empty-deployment
clarification was unnecessarily turned into a durable note.

## rules/core.md — Autonomy (unattended work)

Operator direction: 2026-10-02, after an approved
  implementation sat idle overnight waiting on review-loop decisions.

## skills/pr-ready/SKILL.md — 4. Merge and cleanup (finish the landing)

Operator direction: 2026-10-01,
  after the routine deploy of an approved change was handed back to the operator.

## rules/core.md — Security (operator-supplied secrets)

Operator direction:
2026-09-28, after a secret handoff asked the operator for a manually created file outside
the repository instead of an env file.

## rules/delivery.md — Work tracking & continuity (deferred items)

Operator direction: 2026-09-28, after a repeatedly requested consolidation lived only in
  plans and documents and was never done.

## skills/agent-lanes/SKILL.md — Lane cleanup (retain open lanes)

Operator direction: 2026-09-30, after idle build directories of open PRs
  were deleted to free space.

## skills/design-canon/SKILL.md — Boundaries (black-box modules)

Operator direction: 2026-09-28, after a
  product's CI had to mirror a kit's native library releases into its own repository.

## skills/design-canon/SKILL.md — Boundaries (extend the owner)

Operator direction: 2026-09-28, after a consumer forked a shared
  mechanism it could not use as it stood.

## skills/design-flow/SKILL.md — 2. Design / spec (reconcile conflicting plans)

Operator direction: 2026-09-28, after agent-approved designs put a product's
canonical records in a second store beside the shared one, contradicting a parallel plan
that was never reconciled.

## skills/operator-writing/SKILL.md — GitHub text

Operator direction: 2026-10-04, after issue and PR bodies relied on internal labels and
omitted reproduction and test evidence; an upstream contribution in this form was chosen
as the model.

## skills/operator-writing — sentence length

Operator direction: 2026-10-06, House Rules review; fixed per-sentence word caps conflicted with
the decision that there are no size targets except a soft split prompt, and length is never a
reason to remove a requirement.

## rules/session-writing.md — Questions to the operator

Operator direction: 2026-10-06; the five-row question card took too much space on a phone
and for several questions; numbered sub-questions (1a, 1b) were replaced by section labels
with one continuous numbering.

## skills/pr-ready/SKILL.md — 3. Review rounds (conflicting findings)

Operator direction:
  2026-10-03, after a fixer traded a bound for an integrity check and back.

## skills/pr-ready/SKILL.md — 3. Review rounds (one fixer per branch)

Operator direction: 2026-10-03, after parallel slow-review fixers doubled builds and
  overloaded the machine.

## skills/rust-canon/SKILL.md — Code rules (build profile and cache)

Operator direction:
  2026-09-07, cross-repository CI correction.

## skills/work-tracking/SKILL.md — External reporting

Operator direction: 2026-10-04.

## skills/bench-discipline/SKILL.md — Cost ladder (parallel paid runs)

Operator direction: 2026-10-06, House Rules audit; the restored rule blocked unrelated
parallel runs.

## INDEX.md — precedence (repository overrides)

Operator direction: 2026-10-06, House Rules audit; repositories may tighten or loosen House
Rules, security included, and keep only their overrides. The rule moves here from each
repository's AGENTS.md, which becomes a loader.

## rules/session-writing.md — Format (chat link text) and rules/writing.md — Format (file-relative links)

Operator direction: 2026-10-06, after a planned file and a file-relative path written in chat
both rendered as dead links (the operator tested each link); relative-to-file links apply
to every file, not only repository files.

## rules/writing.md — Claim labels (verified facts only)

Operator direction: 2026-10-06, after an agent labelled a tool's dry-run mode a `FACT` from
memory; the mode had been removed, and the claim reached an operator decision.

## rules/writing.md — Claim labels (inline evidence)

Operator direction: 2026-10-06; footnotes and source lists were harder to read than the claim
with its evidence linked or named inside the sentence.

## rules/session-writing.md — Questions to the operator (answer prompt)

Operator direction: 2026-10-06; the three-item answer list took five lines of height in chat
and appeared under reminders that held no question. The prompt is now a short label with a
monospace code-block example, shown only under a fully written question list.

## Shared-rule owners and complete worker packs

Operator direction: 2026-10-07, recorded in
[complete worker role packs §10](docs/design/74-complete-worker-packs.md#decisions).
Writing with claim labels, Git rules and priority labels each have one shared owner under `rules/`.
Normal lane sessions load those owners through the index and retain their session rules and skills.
Warden packs include the shared owners directly and exclude session-only writing and lane procedures.
The session variant omits the declared shared includes while preserving role instructions.
Live session rules remain separate from the named-commit role prompt.
Warden reviewers remain read-only, contact only the model provider and run no builds or tests.
The Warden service posts reviews for local lanes to read.

## skills/pr-ready — Targeted review panel

Operator direction: 2026-10-12, after a full review round ran three reviewers with the same
model and the same whole-change prompt, each with a one-sentence focus line, and two of them
reported the same blocker. A full panel now runs one reviewer per target lens, spread over the
model families; each lens is a checklist with an out-of-scope list naming the owning lens.
When a family cannot run a target, another family runs it in the same round (operator: "If a
model can't run, the second model should take its place"). The panel is incomplete when no
family can run a target or a review breaks its report contract. Quick review keeps one generalist.
