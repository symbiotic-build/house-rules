<a id="addressable-section"></a>
# Addressable section

An addressable section gives readers and assignments a stable destination containing one complete explanation.

Linking scopes follow [rules/specifications.md](../../../rules/specifications.md#direct-links).
For assignment and home extraction, a heading instead selects its complete subtree through the next heading of equal or higher level.
These boundaries serve different operations.

The [document manifest](document-manifest.md#document-manifest) sets reading order.
Source order sets position within each selected section.
A home in another document always counts as ahead of the reader.
Documents have no shared reading order.

Document, section, entity, fact and test identities survive title changes and reordering.
Local destinations use explicit empty `id` anchors.
Unreleased material requires no permanent redirects.
Moving a home changes its index entry and incoming links together.

For example, the nested headings below illustrate both boundaries:

```markdown
## Parent
Parent introduction.
### Child
Child introduction.
## Next
```

A home or assignment at Parent includes Child and stops before Next.
In the linking-policy example, Next starts a new scope; Child shares Parent's scope.
Several child homes may belong to one manifest section, each with its own anchor and definition.
