Focus: whether a new technical reader can understand the design or specification from the document alone.
Apply the naming requirement in the writing rules: newly designed or redesigned internal storage, schema and protocol names use readable words, and a glossary does not make an invented abbreviation a readable name.
Apply the reader test to each section: read it alone, as if the rest of the document were unavailable. A new engineer must be able to say what problem it solves, what the rule is and when it applies. Flag sections that fail it (missing why, example or term definition), buried behaviour and missing structure.
Review every worked example and schema naming family. For each stored value an example shows, the text explains what it represents, any unit or code meaning, why the step writes, changes or keeps it, and what the caller observes. For arrays, it states the element meanings and which entries correspond. For shared slots, it names the record type and the mapped field. A compact dump fails when the reader must decode it from a glossary or another section.
Check newly added explanations against the schema or protocol, including their qualifications and exceptions. A passing link, heading or content-preservation check is not a passing reader test.
For each finding, show the concrete passage and what the reader cannot explain. Report violations of these requirements as document requirement defects. Cosmetic preferences that pass the reader test remain non-blocking. Do not accept a glossary elsewhere as closure.

Fresh-reader packages follow the [canonical reader procedure](../../skills/spec-writing/SKILL.md#fresh-reader-review).
Identify what this reader cannot explain about the tour, refusal or recovery from the supplied document.
In addition to the questions and concrete exercise in the document's domain, rate every chapter "followed on first
read: yes / with effort / no". Quote every choppy, abstract, formulaic or repeated passage.
Use the canonical procedure's rating meanings: "with effort" requires re-reading or
looking elsewhere to understand. Record other wording issues as polish notes.
The pass bar is every chapter "yes" from every reader, with no quoted passage unaddressed
and every polish note fixed or answered with a reason.

Check that each paragraph develops one point through connected sentences and that each
abstract rule has its concrete case. Before: "Examples add no obligations. Summaries are
illustrative. Links resolve to homes." After: "The fifth item exceeds the batch capacity
of four. The example shows its refusal. That refusal illustrates the capacity requirement;
it adds no new obligation." Unrelated assertions belong in a list.

Apply the writing profile's warning severity. A long sentence, long paragraph or other
heuristic warning alone is not a defect. Identify the demonstrated reader problem and its
consequence. Preserve conditions, exceptions, uncertainty and consequences when suggesting
shorter wording. Check that provisional facts retain qualifications, observed facts retain
evidence and operating conditions, and unresolved facts retain their resolution paths.
Check the reader-progression qualification rule at the first description of each mechanism
or value. Flag an unresolved formula, provisional limit or unavailable behavior presented
as implementable before a later caveat.
Check unlinked restatements and ordinary words given unstated technical meanings; a
successful literal-value link check does not establish those meanings.
Check each registered accepted form for a single meaning across chapters and link labels.
When a second concept borrows the bare form, require a distinct term and index guidance
rejecting that bare form for the second concept. Check the sentence's intended meaning,
not only whether its link resolves.

Check every public name against the naming conventions the writing rules require: types,
fields, error types and error reasons, settings, events and commands. A kind of public name
with no declared convention is a finding. A name that breaks its declared convention is a
finding. One concept spelled two ways anywhere in the document set is a finding, even when
each chapter is consistent on its own; include code spans, tables and examples. Check the
parts no naming pattern expresses, such as word order, by reading. A clean checker run
does not establish that names follow their conventions.

@rule house-rules:rules/specifications.md

Check that identifier and filename links reach their specific defining subsection or row,
rather than a broad component home when a more precise definition exists.
Require the fresh-reader and normal authoring/conversion run evidence from the canonical procedure;
a fixed published fixture does not establish reader construction or pipeline quality.
