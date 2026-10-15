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
The pass bar is every chapter "yes" from every reader, with no quoted passage unaddressed.

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
Check unlinked restatements and ordinary words given unstated technical meanings; a
successful literal-value link check does not establish those meanings.

@rule house-rules:rules/specifications.md

Check the concrete reading path in rules/specifications.md: map with a stated diagram
question, plain tour, coherent mechanism chapters, then lookup reference. Reject a split
into one chapter per term; check title-slug filenames and useful summaries. Check actual
conceptual prerequisites rather than a predecessor chain. Follow the same
example through all four parts and acceptance. Check skippable labelled detail blocks,
purpose-first section openings (including declaration records), definition-first entity
homes with purpose following, explicit linked deferrals and
first-use glosses. Check role order against the manifest and templates. Require the
fresh-reader and normal authoring/conversion run evidence from the canonical procedure;
a fixed published fixture does not establish reader construction or pipeline quality.
