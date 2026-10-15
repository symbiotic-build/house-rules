<a id="checking"></a>
<a id="documentation-checker"></a>
# Documentation checker

The documentation checker finds structural contradictions in one selected set of Markdown and metadata bytes.

Use CommonMark with pipe tables enabled through `markdown-it-py`.
Read parser tokens and source locations instead of implementing another Markdown parser.
Parse each input once per invocation.
One in-memory model supports checking, navigation and context selection.
No persistent database, cache or search index is required.

The source supplies paths and bytes from one [source snapshot](source-snapshot.md#source-snapshot).
Local inputs are regular UTF-8 files within the declared repository input set.
Reject path escapes, symlinks and invalid encoding.
Reject duplicate JSON keys, unknown fields, unsupported versions, duplicate identities and malformed declarations.
Generated regions never supply authored fact values.

Local fragment links resolve to explicit destinations.
External URLs receive syntax checks; network availability is outside the deterministic gate.
Executable expressions, remote includes, automatic linkification, conditional publication and arbitrary paragraph transclusion are excluded.

Commands provide `check`, `generate` and `context`.
Snapshot options select working-tree input, `--staged` or `--rev`.
Conflicting options fail.
Continuous integration checks the complete candidate corpus in one required documentation job.
Local and staged checking use the same pinned tool.

Diagnostics include severity, code, path, source line and explanation.
Their order is deterministic and their number is uncapped.
The tool reports every available error and never skips invalid files to obtain success.
Warnings never change a successful exit status.
Neither continuous integration nor context generation promotes warning counts to errors.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="checker-success"></a>success | 0 | specified | [Source decision](decisions.md#source-decision) |
| <a id="checker-document-errors"></a>document-errors | 1 | specified | [Source decision](decisions.md#source-decision) |
| <a id="checker-invocation-failure"></a>invocation-failure | 2 | specified | [Source decision](decisions.md#source-decision) |

The [success](documentation-checker.md#checker-success) exit means no structural errors.
The [document-errors](documentation-checker.md#checker-document-errors) exit identifies invalid documentation.
The [invocation-failure](documentation-checker.md#checker-invocation-failure) exit identifies an invocation or input/output failure.
The [diagnostic reference](interfaces-and-encodings.md#diagnostics) assigns codes without adding value types or measurement conversion.

<a id="failure-invalid-source"></a>
### Failure state: invalid source or invocation

This refusal explains invalid source or invocation and the actor who can recover.

**Trigger:** A selected input, declaration, target or invocation violates its contract.

**Outcome:** The caller receives diagnostics and the applicable failure exit.

**Retained state:** Checking changes no authored source. Existing output remains available.

**Recovery:** Repair the named source, restore the target or correct the invocation, then check the selected snapshot again.

**Authority:** The source owner edits authored files; the caller chooses valid invocation inputs.

**Verification:** [Checker failures](acceptance-evidence.md#test-checking), [homes](acceptance-evidence.md#test-homes), [literal values](acceptance-evidence.md#test-literals).
