<a id="acceptance-test"></a>
# Acceptance test

An acceptance test makes a requirement assessable through a declared method, inputs and pass condition.

Acceptance-test anchors use `test-` with the same suffix grammar and permanent-identity rules as requirement anchors.
Retirement never permits reuse of a test identity.

Method and evidence follow [rules/specifications.md](../../../rules/specifications.md#requirements-tests-and-recovery).
Static checking resolves executable files using [Markdown declarations](source-formats.md#markdown-declarations).
The selector audit then runs every executable selector and reports pass, missing and failing counts.
For the batcher's inspection case, the linked retained-state evidence explains what the reviewer checks.

Comparing base and candidate snapshots reports new, changed and removed requirements.
The report includes declarations, linked tests from both snapshots and relationship additions or removals.
Changes to directly referenced fact values, Status, Basis or qualifications also select affected requirements.
There are no effective-value chains.

Review assignments include selected tests even when their text did not change.
A removed requirement needs a resolving decision supplied by the work item or task.
The checker resolves references; reviewers establish authority.
The report is derived from sources and Git snapshots.
Store no suspect-link stamps, approval hashes or separate traceability ledger.
Existing review resolution records the disposition.

When a Git-backed base is supplied, checking reads its reachable history and rejects reuse of retired `req-` and `test-` anchors.
Without that base, historical reuse is a reviewer responsibility.
Literal code examples do not reserve identities: the shared Markdown parser recognizes actual declaration headings only.

The bare Git cost is native history selection, tree inventory and blob reads.
The checker reads historical manifests to identify declared documents, then parses each relevant blob once per comparison.
It adds no persistent identity ledger or historical cache; Git remains the history authority.
