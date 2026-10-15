<a id="sources"></a>
<a id="document-manifest"></a>
# Document manifest

The document manifest guides readers through the declared purpose, scope and section order of each document.

Its home path is [docs/DOCUMENTS.json](../../DOCUMENTS.json).
Every tracked Markdown file has an inventory classification.
An `other` classification includes a reason.
Reviewers check that a reason does not hide a specification or design document.

The section array defines reading order; identities do not depend on array positions.
Each entry identifies its path, explicit anchor, roles, summary and prerequisites.
Explanatory dependencies identify another section and state why it is needed.
Applicability is document-level in the format [version](sources.md#manifest-version).
One section may serve several roles.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="manifest-version"></a>version | 1 | specified | [Source decision](decisions.md#source-decision) |
| <a id="manifest-path"></a>path | docs/DOCUMENTS.json | specified | [Source decision](decisions.md#source-decision) |

Each document declares one navigation arrangement.
A standalone generated file uses `navigation.path`.
A region in an existing document also sets `navigation.region` to the document identifier.
Navigation belongs under generated documentation or in the declared region of an existing document.
It never creates a competing system map.

Production approval uses `operator` or `delegated` authority and a resolving decision reference.
Only `--fixture` accepts `fixture` authority for synthetic teaching and test corpora.
It approves only the teaching contract, never production behavior.
The [complete example](example.md#minimal-example) demonstrates this distinction.
Drafts may retain unresolved contracts.
Approval fails when such a contract prevents implementation.


In the bounded-batch example, the manifest selects `docs/example.md` and its declared reading order.
The exact files are explained later in [Minimal corpus](example.md#minimal-example).
