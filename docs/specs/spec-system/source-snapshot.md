<a id="source-snapshot"></a>
# Source snapshot

A source snapshot prevents mixed-version checks by capturing one immutable set of repository paths and bytes.

Commit review reads the selected commit.
Staged checking reads the complete Git index.
Authoring captures immutable working-tree bytes.
These modes never mix content.
An unstaged repair cannot hide a broken staged corpus.
Dirty files cannot affect a commit-built pack.

The existing pack manifest records revision or digest, input fingerprints, registry digest, tool and profile versions, assignment and inclusion reasons.
Base and candidate material carry separate labels.
Do not add another provenance store.

A changed registry or home invalidates packs from its earlier digest.
Explicit uses, recognized uses and dependencies identify affected assignments.
Changed requirements also select their linked tests.

Affected authors receive regenerated inputs and changed declarations.
They recheck surrounding explanations and complete [scenarios](scenario.md#scenario).
Other assignments receive a newly selected current-baseline pack.

No documentation rebase verifier is implemented; regeneration is the supported path.
