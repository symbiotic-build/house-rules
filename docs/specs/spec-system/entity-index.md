<a id="entity-index"></a>
# Entity index

The entity index prevents naming ambiguity by assigning identities, accepted names and one home to each concept.

Its home path is [docs/ENTITIES.json](../../ENTITIES.json).
Each entry contains `kind`, `home`, `scope`, `forms`, `symbols` and `rejected_forms`.
The `home` object identifies a manifest section and explicit anchor.
The home heading supplies the display name.
Its definition sentence supplies the generated meaning under the [entity-definition rule](../../../rules/specifications.md#reader-progression).
Neither is copied into this authored metadata.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="index-version"></a>version | 1 | specified | [Source decision](decisions.md#source-decision) |
| <a id="index-path"></a>path | docs/ENTITIES.json | specified | [Source decision](decisions.md#source-decision) |

The `scope` array lists every document where an entry applies.
Accepted names and home heading names match whole phrases without regard to case.
Symbols match exactly; matches have word boundaries and no automatic pluralization.

List plural forms explicitly when accepted.
Rejected forms name a replacement and a reason.
Naming rules target structured fields through patterns; they never guess identifiers from prose.

A rule that cannot be a field pattern remains a linked canonical requirement.
Code-only identifiers stay with their code or reference owner unless specification readers need the concept.


Direct-link policy belongs to [rules/specifications.md](../../../rules/specifications.md#direct-links).
For the batcher, linking a glossary entry would hide its refusal contract; the link instead targets the Batcher home.
Literal annotations use the syntax explained later in [Markdown declarations](source-formats.md#markdown-declarations).

The checker does not infer bindings inside arbitrary programming languages.
It recognizes exact symbols and unambiguous registered phrases.
Reviewers identify unregistered concepts and ordinary words with unstated technical meaning.
