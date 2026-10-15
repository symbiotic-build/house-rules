---
name: operator-writing
description: Write every operator-facing text — chat replies, status, briefs, reports, PR text, issue comments — in controlled English with an explanation-first structure, so a reader who knows nothing else understands it. Use for all operator communication; decisions additionally follow skill decision-brief.
license: MIT
---

# Operator Writing

This skill applies the versioned House technical English profile in
[rules/writing.md](../../rules/writing.md#house-technical-english), an explanation-first
structure and a reader test.

Follow [rules/writing.md](../../rules/writing.md) for general writing rules.

<a id="communication-rules"></a>
## Communication rules

- Follow `operator-writing` for every operator-facing text’s structure, language, options, Mermaid diagrams, and reader test.
- Use `decision-brief` for decisions and explanations.
- Do not invent operator homework.
- Do not ask permission to continue authorized work.

## Structure

Lead with the result or the action the reader must take. Then explain in this order, using
only the parts the message needs:

1. **What this is:** the project, module or situation, in one or two sentences.
2. **Terms:** every term the rest uses, defined in plain words.
3. **Example:** one concrete, real example, step by step.
4. **Facts:** what exists or happened, each with its evidence link.
5. **Problem:** what breaks or is missing, shown in the example.
6. **Change or options:** what changed, or the options, numbered 1, 2, 3.
7. **Recommendation and next step:** one prominent recommendation, with its trade-offs when it
   has any, and who acts next. Keep any order the operator asked for.

Rules:

- Never mention a decision, sub-decision, option or label before the text has explained
  it. A summary line at the top may state a result; it never introduces an unexplained
  label.
- Number options with one scheme only (Option 1, 2, 3), with no gaps, and define every
  option where options are listed.
- One diagram at most per topic. Never place two diagrams without text between them.
  Diagram format follows [rules/writing.md §Format](../../rules/writing.md#format).
- Short chat replies use the same order in compressed form: result → why → what is next.
  Omit empty parts; do not add parts the message does not need.
- Put commands, paths and snippets before optional explanation.
- Order explanations by consequence, not by the order the work happened. Omit empty template
  sections, long activity logs and repeated caveats.
- Number steps that must happen in order. Keep each step small. Use only the steps needed.
  This order is for the reader. It does not limit authorized parallel work.
- Answer numbered questions in the same order, with the same numbers.
- Stay on the requested topic. Keep optional findings separate. Report blockers and material
  risks at once.
- When work closes or is replaced, state what was delivered, what was already done and what
  replaced it. Link the remaining work.
- Keep old evidence below a labeled current summary. Old "unresolved" notes must not
  contradict the current status.
- Keep the requested outcome and material blockers visible.
- State the next action and its owner in messages.
- Highlight operator-owned actions with bold text or a heading.

### Checks before sending

Example: not "Fix rounds are capped at three." but "A pull request gets at most three fix rounds.
  After that, the lead simplifies or splits the change within approved authority.
  Routine work continues. Changes outside approved authority require your decision."

Decisions use skill `decision-brief` for their full content; this skill sets how all of it
is written.

## GitHub text

Issues, PR bodies, review comments, replies to review and commit messages use the forms in
[references/github-text.md](references/github-text.md).

## Questions to the operator

Follow [session writing rules](../../rules/session-writing.md#questions-to-the-operator).
