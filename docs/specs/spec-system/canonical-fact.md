<a id="canonical-fact"></a>
# Canonical fact

A canonical fact is a named literal value declared once, in a table at its owner's home.
Declaring it once prevents conflicting values.

In the bounded-batch example, the capacity row supplies the value used by a displayed link.
Changing a link's text changes what the reader sees; it does not change that row's authority.
The wrong label in the tour therefore fails even though its destination exists.
A key label instead helps the reader navigate to the row without displaying a second value.

The checker compares literal text after digit grouping normalization.
It never decides whether two measurements mean the same quantity.
For example, adding the word `items` inside a value-bearing link changes its literal text and fails comparison.
The word belongs outside that link.
Unlinked restatements still need review because the tool cannot know which fact they mean.

The [minimal corpus](minimal-corpus.md#minimal-example) shows the same capacity row and its refusal case.
Exact table columns, comparison rules and qualification syntax are explained later in
[Markdown declarations](source-formats.md#markdown-declarations).
Authority and evidence obligations belong to [rules/specifications.md](../../../rules/specifications.md#authority-and-homes).
