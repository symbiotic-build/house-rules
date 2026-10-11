# Writing rules

The reader must understand the text without any other document. They should know what
happened, why it matters and what to do, in that order.

## Self-contained text

- YOU MUST make every message stand alone. Never send the reader to find text elsewhere.
  Examples: "my last message", "the questions above", "as discussed earlier" or "see the PR".
- To mention an earlier question, decision or finding, restate it in full in this message.
  Otherwise, leave it out.
- A count or label ("the 11 questions", "question 4", "9a-1") never replaces the items it
  names.

## Communication rules

- Support claims with evidence.
- Distinguish observed causes from hypotheses.
- Distinguish completed fixes from plans and deployments awaiting verification.

## Language

- One fact per sentence. Prefer short sentences; split one that carries more than one fact.
  Length is never a reason to drop content.
- Active voice, simple tense. Name who does what.
- One term per concept. Define it once at first use, then never use a synonym.
- No unexplained acronyms, internal labels or IDs as a replacement for meaning. An ID may
  follow the plain description, never replace it.
- In newly designed or redesigned internal storage, schemas and protocols, use readable
  words for collection, column, field, row-kind and key-prefix names. A glossary does not
  make an invented abbreviation a readable name. Name a shared slot by its value kind,
  indexing role and position; state a field's mapping to that slot for its record type.
- Preserve exact external API names and identifiers when citing existing code. Explain
  them where needed. Standard terms and symbols defined beside a formula are allowed;
  their use does not permit invented abbreviations in stored names.
- Concrete over abstract: a real name, number, example or before/after, not "the
  mechanism" or "the invariant".
- Keep the source's uncertainty and qualifiers. Never add a cause, frequency or number the
  evidence does not show. Never drop a hedge, exception or consequence that changes what a
  statement means for the reader.
- Required output formats, needed context, tool announcements and approval explanations come
  first. Brevity never removes evidence or content the task needs.
- State what the evidence shows and what it does not show.
- Keep these pairs apart:
  - an observed cause and a hypothesis;
  - a failure in the running system and a risk of a proposed change;
  - a completed fix and a plan or an unverified deployment.
- Report an error as the observed failure, its known cause or "cause unknown", and the next
  diagnostic or fix. Use no alarmist words.
- No filler, no marketing adjectives, no ceremonial openings or closings.

## Format

- Never put long text in a table cell. Use a table only when every cell is a few words.
  Give each option or item its own short section instead.
- Diagrams are Mermaid in files and chat, never ASCII art or indented text trees.
  Orient them vertically, with groups and comparisons stacked rather than side by side.
  Draw unconnected groups as separate diagrams, with text between them; one diagram would
  place them side by side.
- Make every file reference a link that works where the text is read.
- In a file, link another local file with a path relative to the linking file.
- In other text read on the web (issues, PRs, comments, commits, web pages), link files only
  with web links.
- Pin a web link to a commit when it cites evidence.
- Write a PR or issue reference as a Markdown link: `[#52](https://github.com/owner/repo/pull/52)`.
- Prefer lists of five or fewer items.
- Group longer lists only when helpful.
- Preserve sequence, identifiers, and coverage when grouping.

## Claim labels

- Render claim labels as inline code: `FACT`, `ASSUMPTION`, `ESTIMATE`, `ASSESSMENT` or
  `DECISION`. Put punctuation outside the code span, for example `FACT`: the test passed.
- Label claims `FACT`, `ASSUMPTION`, `ESTIMATE`, `ASSESSMENT` or `DECISION`. Quote an
  existing decision; never present a settled operator decision as open, or your own choice
  as settled.
- In evidence narratives, label a paragraph or finding once when its claims have
  the same authority. Keep evidence beside the supported claims. Split the passage or
  mark the changed authority when fact, assessment or uncertainty changes.
- In specifications, state normative behavior directly. Do not prefix ordinary rules,
  definitions or walkthrough steps with claim labels. Mark measurements, designed costs,
  assumptions, estimates and open choices in the block where they occur. Keep their
  sources and limits. Follow a user's requested claim format when one is supplied.
- The sentence-label format for operator question context applies to that context only;
  it is not the format for a specification or an evidence narrative.
- Label a claim `FACT` only after you verified it yourself, in this session, against its primary source.
  The source is code at a named commit, a command you ran, or a log or record you read.
- Put the evidence for a `FACT` inside its sentence.
  Link the claim's key words to the source.
  Or name the file and line, the command, or the quoted output in a few words.
- A claim you remember, infer or read in a summary is never a `FACT`.
  A claim you receive from another agent or an earlier session is never a `FACT`.
  Verify it first, or label it `ASSUMPTION` and name its source.

## Checks before sending

- **Reader test:** read only this text as if no other document exists. The reader can tell
  why it matters, what to choose or do, and what happens next.
  Find every reference to an earlier message, question or document, and restate its content.
- **Language test:** no unexplained acronym or label; every sentence states one fact; no
  option or decision appears before its explanation.
- **Detail test:** every fact the decision or action depends on is present.
  For each limit, stop, failure or change, state what it means for the reader.
  Use the same or the next sentence.
  Include what is changed or unchanged, who acts, and what happens next.
  Cut only what the reader does not need.
