<a id="checking"></a>
# Checking, generation and setup

The tools distinguish structural errors from prose warnings.
A successful structural gate proves declarations agree; it does not certify the technical design or its evidence.

<a id="documentation-checker"></a>
## Documentation checker

The documentation checker is the shared Python parser and validator for selected Markdown and metadata bytes.

Use CommonMark with pipe tables enabled through `markdown-it-py`.
Read parser tokens and source locations instead of implementing another Markdown parser.
Parse each input once per invocation.
One in-memory model supports checking, navigation and context selection.
No persistent database, cache or search index is required.

The source supplies paths and bytes from one [source snapshot](context.md#source-snapshot).
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
| <a id="checker-success"></a>success | 0 | specified | [Source decision](reference.md#source-decision) |
| <a id="checker-document-errors"></a>document-errors | 1 | specified | [Source decision](reference.md#source-decision) |
| <a id="checker-invocation-failure"></a>invocation-failure | 2 | specified | [Source decision](reference.md#source-decision) |

The [success](#checker-success) exit means no structural errors.
The [document-errors](#checker-document-errors) exit identifies invalid documentation.
The [invocation-failure](#checker-invocation-failure) exit identifies an invocation or input/output failure.
The [diagnostic reference](reference.md#diagnostics) assigns codes without adding value types or measurement conversion.

<a id="req-checking"></a>
### Requirement: deterministic visible checking

**Actor:** [Documentation checker](#documentation-checker).

**Condition:** The caller selects a corpus and operation.

**Result:** Parse one snapshot, refuse invalid inputs and report deterministic uncapped diagnostics with the declared exit status. Keep warnings non-blocking.

**Verification:** Check malformed inputs, path boundaries, diagnostic order, invocation conflicts and warning-only input.

**Tests:** [Checker failures](acceptance.md#test-checking).

**Status:** specified.

**Basis:** [Source decision](reference.md#source-decision).

<a id="failure-invalid-source"></a>
### Failure state: invalid source or invocation

**Trigger:** A selected input, declaration, target or invocation violates its contract.

**Outcome:** The caller receives diagnostics and the applicable failure exit.

**Retained state:** Checking changes no authored source. Existing output remains available.

**Recovery:** Repair the named source, restore the target or correct the invocation, then check the selected snapshot again.

**Authority:** The source owner edits authored files; the caller chooses valid invocation inputs.

**Verification:** [Checker failures](acceptance.md#test-checking), [homes](acceptance.md#test-homes), [literal values](acceptance.md#test-literals).

<a id="navigation-generation"></a>
## Navigation generation

Navigation generation projects authored purpose, audience, summaries, reading order and entity homes into deterministic Markdown.

The output contains an overview, document map and [entity index](sources.md#entity-index).
Section titles link directly to their destinations.
Generation invents no explanatory claims.
Authored chapters remain the reading source.
The [document manifest](sources.md#document-manifest) selects a standalone file or one region in an existing document.

Validate proposed output before replacing designated files.
Preserve prior output wherever replacement has not occurred if generation fails.
An interruption may leave a partial generated set.
Freshness checking refuses that set; regeneration repairs it from canonical sources.
Dispatch requires a completely checked snapshot.

Freshness checking compares generated bytes with committed output.
Direct edits to generated regions fail that check.
Standalone generated files receive GitHub's generated-file attribute.
Reviewers examine source explanations and whether the generated projection provides useful navigation.
A renderer remains a separate consumer; repair its defects there instead of editing exports.

<a id="req-navigation"></a>
### Requirement: rebuildable navigation

**Actor:** [Documentation checker](#documentation-checker) and generator.

**Condition:** Navigation is generated or checked for freshness.

**Result:** Derive bytes deterministically from valid authored declarations. Validate before replacement and refuse stale or partial output.

**Verification:** Generate twice, change an authored summary and edit generated output directly.

**Tests:** [Navigation and interrupted output](acceptance.md#test-navigation).

**Status:** specified.

**Basis:** [Source decision](reference.md#source-decision).

<a id="failure-navigation"></a>
### Failure state: stale or unwritable navigation

**Trigger:** Generated bytes differ, the destination fails, or an interruption leaves a partial set.

**Outcome:** Freshness or generation fails visibly; dispatch cannot use the unchecked set.

**Retained state:** Canonical sources remain. Unreplaced previous outputs remain; replaced outputs may form a partial set.

**Recovery:** Repair the destination or source and regenerate the complete designated output set.

**Authority:** The editor needs ordinary write authority for the declared output locations.

**Verification:** [Navigation and interrupted output](acceptance.md#test-navigation).

<a id="tool-environment"></a>
## Tool environment

The tool environment is an isolated Python installation using dependencies owned by the shared spec-writing tool.

Repositories pin the House Rules revision containing that tool.
They neither copy the checker nor choose independent parser versions.
Direct dependency input, the exact hash lock and runtime metadata belong to the shared tool.
Select wheels only, without extras or source distributions.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="runtime-version"></a>runtime-version | 1 | specified | [Toolchain decision](reference.md#toolchain-decision) |
| <a id="runtime-implementation"></a>implementation | CPython | specified | [Toolchain decision](reference.md#toolchain-decision) |
| <a id="runtime-python"></a>requires_python | >=3.11,<3.15 | specified | [Toolchain decision](reference.md#toolchain-decision) |
| <a id="parser-version"></a>markdown-it-py | 4.2.0 | specified | [Toolchain decision](reference.md#toolchain-decision) |
| <a id="url-version"></a>mdurl | 0.1.2 | specified | [Toolchain decision](reference.md#toolchain-decision) |
| <a id="parser-hash"></a>parser-wheel-sha256 | 9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a | specified | [Toolchain decision](reference.md#toolchain-decision) |
| <a id="url-hash"></a>url-wheel-sha256 | 84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8 | specified | [Toolchain decision](reference.md#toolchain-decision) |

The supported [requires_python](#runtime-python) range is an implementation support commitment, not completed compatibility evidence.
The wheel hashes identify the selected locked distributions.
Setup checks the interpreter range and installed package versions.
It neither hashes the interpreter or package installer nor keeps interpreter allowlists.
It never upgrades the package installer implicitly.

**Procedure: prepare an isolated tool installation**

1. **Create the environment.**
   - Use a supported interpreter to create a virtual environment.
   - Keep the environment separate from repository runtime dependencies.
2. **Install the unchanged lock.**
   - Use `--require-hashes --only-binary=:all: --no-deps` with the shared lock file.
   - A download, hash or installation failure stops setup.
3. **Check the installation.**
   - Validate the declared runtime and installed versions.
   - Run the package installer's consistency check.
   - Continue only after all checks pass.

Dependency acquisition follows existing package-manager and sandbox boundaries.
No additional dependency-approval question is introduced by this settled toolchain.
There is no fallback parser, source build or stale-output fallback.
No retry loop conceals a setup or output failure.

<a id="req-toolchain"></a>
### Requirement: pinned tool ownership

**Actor:** Tool setup and repository integrator.

**Condition:** The shared tool is installed, invoked or extracted with a [prompt compiler](../../design/76-review-entry-skill.md#prompt-compiler).

**Result:** Use the pinned runtime contract and wheel versions. Keep helper, profile and format contract from the same House Rules revision. Refuse unsupported or inconsistent environments.

**Verification:** Inspect pins and extraction inputs; run supported and mismatched environment cases.

**Tests:** [Toolchain ownership](acceptance.md#test-toolchain).

**Status:** specified.

**Basis:** [Toolchain decision](reference.md#toolchain-decision).

<a id="failure-toolchain"></a>
### Failure state: unsupported [tool environment](#tool-environment)

**Trigger:** Runtime, installed version, dependency acquisition or hash verification fails.

**Outcome:** Setup or invocation stops with the failing check visible.

**Retained state:** The source lock remains authoritative; an incomplete environment does not become a fallback.

**Recovery:** Supply a supported interpreter or repair the isolated environment from the unchanged lock.

**Authority:** The installer needs the package-manager and filesystem authority already required by the environment.

**Verification:** [Toolchain ownership](acceptance.md#test-toolchain).
