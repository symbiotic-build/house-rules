# Session writing rules

## Format

- Size work per [rules/core.md prime rule 13](core.md#prime-rules).

- Operator documents (briefs, status, ledgers, reports) are Markdown files. Do not author
  them as HTML; an HTML rendering, if ever needed, is generated from the Markdown.
- In chat, show a local file's absolute path as the link text.
- In chat, set the link target to the file's path from the session root, so the client can
  open it.
- In chat, also give the web link when the reader may need the reviewed version.
- Send a file that no link can open with the client's file-sending tool, when it has one.
- In chat, the client turns every written path into a link counted from the session root.
  Write a path in chat only as an absolute path or as a path from the session root.
- Name a file that does not exist yet in words, not as a path.

## Questions to the operator

Numbered question headings apply only to operator-facing questions, never to specifications
or design documents. Those documents use unnumbered open-question sections.

Questions the operator must answer come after the explanation.
Use [rules/writing.md §Claim labels](writing.md#claim-labels). Example:

````markdown
## Warden

### 1\. What should Warden do with a review request in an unmanaged repository?
`FACT` Five repositories are unmanaged. `FACT` Today Warden ignores the request and nobody sees why. `ASSESSMENT` A silent skip looks like an outage.\
Either option also applies to repositories added later.

1. **One comment saying the repository is not managed by House Rules (recommended).**
2. A silent skip, visible only in Warden's host log.

### 2\. Send the error text from the failed App install?
`FACT` GitHub opened the organization settings page instead of the install page. `FACT` Warden's host log has no entry from that time. `ASSESSMENT` The error is probably visible only in the browser.\
Without the text, the cause stays a guess between a missing permission and a wrong link.

## House Rules

### 3\. Merge [#52](https://github.com/jak-pan/house-rules/pull/52), the writing-rules PR?
`FACT` An earlier cleanup removed several writing rules without an operator decision; it puts them back. `FACT` It changes only the operator-writing skill and the rules changelog.\
Agents on this machine use the rules from their next session; Warden and the lanes get them only after their House Rules pins move.

**Answer like so:**
```text
 1. 1
 2. explain how the install link could be wrong
 3. ok
```
````

- Write each topic as a level-2 heading.
- Write each question as a level-3 heading.
- Start each question heading with its number, typed and escaped: `### 1\.`.
- Number questions across topics: 1, 2, 3. Never use 1a or 1b.
- Below the heading, give enough context that the operator can answer from the question
  alone. Add a link or a short code excerpt when the answer depends on it.
- Keep the context brief: a few sentences, never a wall of text.
- Start each context sentence with the flag `FACT` or `ASSESSMENT` in inline code.
- Write all context sentences on one source line. Do not wrap it.
- Add one line on what happens after the answer, only when the reader cannot infer it.
- When that line follows, end the context line with a backslash, so it renders as a line
  break.
- Write the options of a choice as a numbered list. Never nest it.
- Give each option what changes and its side effect.
- Recommend exactly one option. Write its whole line in bold and end it with "(recommended)".
- Do not write the word "Option" in option text.
- When the answer is text, name the text in the question title, for example "Send the
  error text …?".
- Put no reply line, answer box, quote or table in the questions.
- End a fully written question list with the bold line "Answer like so:".
- Below it, give a three-line example in a `text` code block.
  Indent each line by one space.
  The lines show an option number, a request for more context and `ok`.
- Show the answer prompt only under a fully written question list, never as a reminder of
  earlier questions.
- Treat an answer that asks for more context as a new question: explain, then ask again.
- Never ask the operator about work the agent's own team must do (tests, replays,
  verification). List it as an internal task.
