<a id="tool-environment"></a>
# Tool environment

The tool environment prevents parser drift by isolating the shared tool and its pinned Python dependencies.

Repositories pin the House Rules revision containing that tool.
They neither copy the checker nor choose independent parser versions.
Direct dependency input, the exact hash lock and runtime metadata belong to the shared tool.
Select wheels only, without extras or source distributions.

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="runtime-version"></a>runtime-version | 1 | specified | [Toolchain decision](decisions.md#toolchain-decision) |
| <a id="runtime-implementation"></a>implementation | CPython | specified | [Toolchain decision](decisions.md#toolchain-decision) |
| <a id="runtime-python"></a>requires_python | >=3.11,<3.15 | specified | [Toolchain decision](decisions.md#toolchain-decision) |
| <a id="parser-version"></a>markdown-it-py | 4.2.0 | specified | [Toolchain decision](decisions.md#toolchain-decision) |
| <a id="url-version"></a>mdurl | 0.1.2 | specified | [Toolchain decision](decisions.md#toolchain-decision) |
| <a id="parser-hash"></a>parser-wheel-sha256 | 9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a | specified | [Toolchain decision](decisions.md#toolchain-decision) |
| <a id="url-hash"></a>url-wheel-sha256 | 84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8 | specified | [Toolchain decision](decisions.md#toolchain-decision) |

The supported [requires_python](environment.md#runtime-python) range is an implementation support commitment, not completed compatibility evidence.
The wheel hashes identify the selected locked distributions.
Setup checks the interpreter range and installed package versions.
It neither hashes the interpreter or package installer nor keeps interpreter allowlists.
It never upgrades the package installer implicitly.

**Procedure: prepare an isolated tool installation**

1. **Create the environment.**

   > **Detail — installation**
   >
   > Use a supported interpreter to create a virtual environment.
   > Keep the environment separate from repository runtime dependencies.
2. **Install the unchanged lock.**

   > **Detail — installation**
   >
   > Use `--require-hashes --only-binary=:all: --no-deps` with the shared lock file.
   > A download, hash or installation failure stops setup.
3. **Check the installation.**

   > **Detail — installation**
   >
   > Validate the declared runtime and installed versions.
   > Run the package installer's consistency check.
   > Continue only after all checks pass.

Dependency acquisition follows existing package-manager and sandbox boundaries.
No additional dependency-approval question is introduced by this settled toolchain.
There is no fallback parser, source build or stale-output fallback.
No retry loop conceals a setup or output failure.

<a id="failure-toolchain"></a>
### Failure state: unsupported tool environment

This refusal explains unsupported tool environment and the actor who can recover.

**Trigger:** Runtime, installed version, dependency acquisition or hash verification fails.

**Outcome:** Setup or invocation stops with the failing check visible.

**Retained state:** The source lock remains authoritative; an incomplete environment does not become a fallback.

**Recovery:** Supply a supported interpreter or repair the isolated environment from the unchanged lock.

**Authority:** The installer needs the package-manager and filesystem authority already required by the environment.

**Verification:** [Toolchain ownership](acceptance.md#test-toolchain).


In the bounded-batch example, the same pinned parser checks the files when they live in an independent repository.
The exact files are explained later in [Minimal corpus](example.md#minimal-example).
