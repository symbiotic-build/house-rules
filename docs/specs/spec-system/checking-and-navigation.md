<a id="checking-and-navigation"></a>
# Checking and navigation

Checking exposes invalid source before generation turns its declarations into navigation. For the bounded batch, checking reports `D10` when a link displays `3` while capacity is `2`. After the author repairs that label, generation can rebuild the map from the corrected contract.

<a id="toolchain-and-inputs"></a>
## Toolchain and input boundaries

Reproducible checking needs a fixed parser and fixed input bytes. The [tool environment](#tool-environment) fixes parser behavior, and the [source snapshot](#source-snapshot) fixes repository content for the operation. A successful invocation therefore cannot borrow an unstaged repair or a different parser to conceal invalid selected input.

<a id="tool-environment"></a>
### Tool environment

The tool environment is an isolated Python installation running the shared documentation tool with its owned dependency pins. It keeps consumer repositories from interpreting the same declarations through independently chosen parsers.

Each consumer pins the House Rules revision containing the tool. The shared owner supplies direct dependency input, the hash lock, runtime metadata, format contract and prose profile. Consumers use those matching inputs rather than copying the implementation or maintaining local parser versions. In particular, the batch corpus and its `example#main` assignment use the same parser when checked directly or prepared for an agent.

The runtime contract names the supported interpreter, while the lock identifies the selected parser wheels. These values describe support and installation requirements; they do not claim completed execution on every supported interpreter.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="runtime-version"></a>runtime-version | 1 | specified | [skills/spec-writing/scripts/runtime.json](../../../skills/spec-writing/scripts/runtime.json) |
| <a id="runtime-implementation"></a>implementation | CPython | specified | [skills/spec-writing/scripts/runtime.json](../../../skills/spec-writing/scripts/runtime.json) |
| <a id="runtime-python"></a>requires_python | >=3.11,<3.15 | specified | [skills/spec-writing/scripts/runtime.json](../../../skills/spec-writing/scripts/runtime.json) |
| <a id="parser-version"></a>markdown-it-py | 4.2.0 | specified | [skills/spec-writing/scripts/requirements.lock](../../../skills/spec-writing/scripts/requirements.lock) |
| <a id="url-version"></a>mdurl | 0.1.2 | specified | [skills/spec-writing/scripts/requirements.lock](../../../skills/spec-writing/scripts/requirements.lock) |
| <a id="parser-hash"></a>parser-wheel-sha256 | 9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a | specified | [skills/spec-writing/scripts/requirements.lock](../../../skills/spec-writing/scripts/requirements.lock) |
| <a id="url-hash"></a>url-wheel-sha256 | 84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8 | specified | [skills/spec-writing/scripts/requirements.lock](../../../skills/spec-writing/scripts/requirements.lock) |

The runtime version identifies the metadata format, and the interpreter rows name its implementation and supported version range. The parser package supplies Markdown tokens; its URL dependency supports link parsing. The wheel hashes identify the distributions installed from the lock. Runtime validation checks the supported interpreter range and installed package versions. It does not hash the interpreter or package installer, keep interpreter allowlists or upgrade the installer implicitly.

**Procedure: prepare the shared tool environment**

1. **Create an isolated environment.** Use a supported interpreter so repository dependencies cannot replace the parser.

   > **Detail — interpreter**
   >
   > The [requires_python](#runtime-python) row defines the supported range. The environment remains separate from the consumer's runtime dependencies.

2. **Install the unchanged lock.** A failed download, wheel hash or installation stops setup.

   > **Detail — locked installation**
   >
   > Installation uses `--require-hashes --only-binary=:all: --no-deps` with [skills/spec-writing/scripts/requirements.lock](../../../skills/spec-writing/scripts/requirements.lock). Installation excludes source distributions and extras.

3. **Validate the installation.** Continue only after runtime validation and the installer's consistency check pass.

   > **Detail — validation**
   >
   > Runtime validation compares the interpreter and installed package versions against the shared inputs. The package installer's consistency check detects incompatible installed dependencies.

<a id="failure-toolchain"></a>
#### Failure state: unsupported tool environment

This refusal prevents an unsupported installation from selecting a fallback parser.

**Trigger:** The interpreter, installed dependency versions, acquisition or wheel-hash validation fails.

**Outcome:** Setup or invocation stops and exposes the failed check.

**Retained state:** The shared lock remains authoritative; existing source and output remain available.

**Recovery:** Repair the isolated environment from the unchanged lock or supply a supported interpreter.

**Authority:** The installer needs the ordinary package-manager and filesystem authority for that environment.

**Verification:** [Toolchain ownership](acceptance-evidence.md#test-toolchain).

<a id="source-snapshot"></a>
### Source snapshot

A source snapshot is a captured set of repository paths, input bytes and source problems used by one documentation operation. It keeps checking and agent preparation tied to the selected content after capture.

A commit selection reads the named commit's tree and blobs. A staged selection reads the complete index, including unchanged entries. Authoring reads captured working-tree bytes, including eligible untracked paths. Conflicting snapshot switches fail instead of combining modes. Thus a corrected working-tree capacity label cannot hide a staged label that still displays `3`.

The tool inventories paths through Git and loads Markdown, shared metadata and mixed generated attributes as bytes. Code and asset links use the inventory for existence and regular-file checks; unrelated binaries are not loaded. Local content inputs must be regular UTF-8 files within repository boundaries. Missing inputs, invalid encoding, symlinks, unmerged index entries and path escapes remain visible failures.

Capture fixes the bytes used by later parsing and selection. It does not make sequential working-tree reads a filesystem transaction. Commit or staged selection supplies the corresponding Git snapshot when that distinction matters. Subsequent edits do not alter already captured content.

The existing assignment output records revision or digest, input fingerprints, registry digest, tool and profile versions, assignment identities and inclusion reasons. Base and candidate material have separate labels. A changed registry or home makes earlier packs stale; affected authors receive regenerated input and recheck their surrounding explanation. The later [Agent context](agent-context.md#agent-context) chapter owns selection and byte-budget behavior.

<a id="checking-and-replacement"></a>
## Checking and replacement

Validation must succeed before generated navigation can replace existing output. The [documentation checker](#documentation-checker) examines the complete selected corpus. [Navigation generation](#navigation-generation) then projects valid declarations into rebuildable Markdown.

<a id="documentation-checker"></a>
### Documentation checker

The documentation checker is the shared parser and validator for specification Markdown and metadata from one selected snapshot. It detects structural errors before invalid declarations can become generated navigation or mandatory agent input.

The parser uses CommonMark with pipe tables enabled. It supplies tokens and source locations rather than requiring a second Markdown parser. Authored documents are parsed into one in-memory corpus used by checking, navigation and context selection. This model earns its cost by making all three operations interpret the same declarations; it adds no persistent database, cache or search index.

For the batcher, a link to the capacity row can resolve while its displayed value remains wrong. Literal comparison reports `D10` for `3` against `2`, with the source path and line. A descriptive capacity link only navigates; it does not claim another literal. The [canonical fact](documents-homes-and-values.md#canonical-fact) home explains the comparison's limits.

Validation rejects duplicate JSON keys, unknown fields, unsupported versions, duplicate identities and malformed declarations. It also checks home completeness, scope, direct links and reciprocal requirement/test relationships. Local fragments need explicit destinations. External URLs receive syntax checks without network access, so a structural pass does not establish remote availability.

Generated regions do not supply authored facts. Remote includes, expression evaluation, arbitrary paragraph transclusion, automatic linkification and conditional publication are outside the supported input model. Exact declaration shapes belong to [Source formats](source-formats.md#source-format), after these behavioral explanations.

The commands are `check`, `generate` and `context`. Local and staged checks use the same pinned tool as the repository's documentation gate. That gate checks the complete candidate corpus. The existing review preparation uses the shared selector rather than constructing a separate interpretation of registered documents.

Diagnostics identify severity, code, path, line and explanation. They are deduplicated and deterministically ordered without a count cap. Checking reports every available finding; malformed environment or input can stop processing before further findings are available. Warning counts never turn a valid structural result into failure.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="checker-success"></a>success | 0 | specified | [skills/spec-writing/scripts/spec_docs.py::main](../../../skills/spec-writing/scripts/spec_docs.py) |
| <a id="checker-document-errors"></a>document-errors | 1 | specified | [skills/spec-writing/scripts/spec_docs.py::main](../../../skills/spec-writing/scripts/spec_docs.py) |
| <a id="checker-invocation-failure"></a>invocation-failure | 2 | specified | [skills/spec-writing/scripts/spec_docs.py::main](../../../skills/spec-writing/scripts/spec_docs.py) |

The [success](#checker-success) exit means that no structural error remains. [Document-errors](#checker-document-errors) identifies an invalid corpus. [Invocation-failure](#checker-invocation-failure) identifies failures such as an unsupported runtime or unavailable input/output; the diagnostic explains the cause. The [diagnostic reference](interfaces-and-encodings.md#diagnostics) supplies each code's remedy.

Prose heuristics follow the profile in [rules/writing.md](../../../rules/writing.md). They warn about sentence length, paragraph length and selected presentation patterns. Reviewers give remaining warning groups a disposition and judge actual reader problems. A warning neither proves a contradiction nor justifies discarding conditions or exceptions to shorten the prose.

<a id="failure-invalid-source"></a>
#### Failure state: invalid source or invocation

This refusal exposes invalid selected material so the owner can repair its source.

**Trigger:** Selected input, declarations, link targets or invocation arguments violate their contracts.

**Outcome:** The caller receives diagnostics and the applicable failure exit; generation cannot accept the invalid corpus.

**Retained state:** Checking changes no authored source or existing output.

**Recovery:** Repair the named source or target, or correct the invocation, and check the intended snapshot again.

**Authority:** The source owner edits the contract; the caller selects valid invocation inputs.

**Verification:** [Checker failures](acceptance-evidence.md#test-checking), [literal values](acceptance-evidence.md#test-literals).

<a id="navigation-generation"></a>
### Navigation generation

Navigation generation is the deterministic projection of declared document metadata and entity homes into reading aids. It gives readers an overview, a document map and an index of meanings without adding authored claims.

The [document manifest](documents-homes-and-values.md#document-manifest) chooses the destination and reading order. The map links section titles and nested level-2 headings to their source anchors, with summaries and prerequisites. The generated view of the [entity index](documents-homes-and-values.md#entity-index) displays each home heading and definition sentence. For the batcher, readers can reach admission and its capacity row rather than relying on an exported paraphrase.

A standalone output uses a declared path under generated documentation. An inline output replaces one marked region in an authored document. The region appears after the entry opening and any introductory diagram with its adjacent entity links. Standalone generated files receive the generated-file attribute through [generated attributes](source-formats.md#navigation); mixed authored documents retain their normal treatment.

**Procedure: replace navigation from valid sources**

1. **Validate the selected corpus.** Structural errors stop generation before any replacement.

   > **Detail — input validation**
   >
   > The author must correct the batch's wrong capacity label before generation can project a valid map. Prose warnings remain advisory.

2. **Validate all proposed output.** Reparse the resulting candidate so invalid replacement bytes cannot enter the output set.

   > **Detail — candidate validation**
   >
   > Authored source and proposed generated bytes form the candidate used for this check. Its generated regions must also satisfy freshness.

3. **Replace designated files.** Each successful replacement exposes complete bytes for that file.

   > **Detail — replacement boundary**
   >
   > The writer processes files in sorted path order through temporary files beside their destinations and atomic per-file replacement. This is not an atomic replacement of the whole set. Mixed authored destinations and generated attributes must still match the captured bytes before replacement. The writer checks destination components again for symlinks.

Freshness compares projected bytes with output in the selected snapshot. A direct edit to generated text, outdated navigation or an interrupted partial set fails this comparison. Repair the canonical source or destination, then regenerate the complete output set. Mandatory agent input requires a checked snapshot; existing stale output cannot serve as a fallback.

Reviewers examine whether the generated map helps readers find the authored explanations. A renderer remains a separate consumer with its own display contract and evidence. Repair renderer defects at that owner rather than editing generated exports.

<a id="failure-navigation"></a>
#### Failure state: stale or unwritable navigation

This refusal keeps a stale or partly replaced output set from passing as current navigation.

**Trigger:** Projected bytes differ, a destination cannot be replaced, a mixed authored destination changed after capture, or generation stops partway through the set.

**Outcome:** Freshness or generation fails visibly; mandatory agent input cannot use the unchecked set.

**Retained state:** Canonical sources remain. Unreplaced outputs retain their previous bytes, while earlier replacements may leave a partial set.

**Recovery:** Repair the source or destination problem and regenerate the complete designated set from current input.

**Authority:** The editor needs ordinary filesystem write authority for the declared destinations.

**Verification:** [Navigation and interrupted output](acceptance-evidence.md#test-navigation).
