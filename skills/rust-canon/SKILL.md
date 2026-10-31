---
name: rust-canon
description: Rust implementation defaults and quality gates for workspace layout, dependencies, errors, configuration, and applicable model integrations. Use when writing Rust or scaffolding crates; general project stack selection belongs to project-bootstrap.
license: MIT
---

# Rust Canon

This skill applies after Rust is selected (stack choice: `PREFERENCES.md` in the installed
House Rules root). Its tooling choices are overridable defaults like the rest of House
Rules.

## Workspace

- Cargo workspace, crates prefixed `<product>-<name>`; edition 2024 for new crates.
- `rust-toolchain.toml` pinned and committed in every Rust repo; install Rust with rustup,
  not a system package manager.
- Feature gates for optional subsystems (`sqlite`, `http`, `cli`, `experimental-*`);
  experimental features default OFF and byte-identical when off.
- Minimal dependencies — hand-roll small things before importing heavy deps. Household set: serde, serde_json,
  thiserror, anyhow, chrono, clap (derive), tokio, reqwest, rusqlite, axum, tracing.

## Code rules

- `thiserror` in libraries, `anyhow` in binaries — and never `anyhow` in hot paths.
- Never `unwrap()` in library code (tests only); errors bubble to the caller/operator —
  no fail-open.
- Async on tokio; non-blocking, multi-threaded by default.
- Follow [Local builds](../../prompts/skills/local-builds.md) for build profiles. Reusing compiled outputs across gates: skill `ci-build-optimization`.
- `///` docs on public items.
- Property and sequence tests use `proptest`; fuzzing uses `cargo-fuzz`. When each applies:
  [Test discipline](../../prompts/skills/test-discipline.md#systems-that-keep-durable-state).

## Repo tooling

Where a repo ships build/test scripts (smoke gates, guard scripts), use them instead of
raw commands — they encode repo law (scope checks, pinned flags) that raw cargo silently
violates. Local test scope: [Local builds](../../prompts/skills/local-builds.md). Git itself is used directly;
repo commit/push wrappers are retired.

## Gates

Full CI gate below; local worker scope: [Local builds](../../prompts/skills/local-builds.md).
Reviewer scope: [reviewer role](../../prompts/roles/reviewer.md).
Build profiles follow [Local builds](../../prompts/skills/local-builds.md). The no-PR-CI exception
lives in `pr-ready` §4.

```
cargo fmt --all --check
cargo clippy --release --workspace --all-targets -- -D warnings
cargo test --release --workspace --all-features --no-fail-fast
```

Zero warnings is the bar. The repo's architecture guard scripts, if any, run after
structural changes. Env-mutating tests use `#[serial(env)]`; test data follows
rules/core.md §Security. Fixtures are date-relative (no fixture rot).

## Config layering (default for Rust products)

```
built-in sane defaults → versioned TOML (profiles/presets) → env vars → CLI flags
```

- Per-product config crates — the same kit gets different settings per consuming product.
- Model/provider settings layer general → provider → provider-model (the shared
  configuration crate owns them); no blanket rpm/tpm defaults buried in code.
- Env-var tuning (ad-hoc `MYAPP_*` knobs) is for experiments, not a production artifact —
  promote proven knobs into typed config keys.
- Record config hash in run params; versioned prompts live in config, not code.

## Model stack policy

Apply this section only to components that actually use models; do not add a model stack.

- The settled model stack (embedder + dims, reranker, workhorse LLM, judge — with exact
  reasoning-effort levels per role) lives in the repo bible. Treat it as settled
  (rules/core.md prime rule 10); never substitute.
- Cheap/free-first: the cheapest model that clears the quality bar wins; report cost per
  run; no expensive models outside the approved standing or campaign resource envelope.
- Local inference and cloud egress: skill `design-canon` §Security & sovereignty.
- Inspect the configured credential provider without displaying values; credential
  storage and diagnostic capture follow rules/core.md §Security.

## Storage

Follow `PREFERENCES.md` and the project's selected canonical store. Use `design-canon`
for derived-data boundaries. Preserve shipped data compatibility and recovery needs;
rebuild is appropriate only when the required canonical data and equivalence are known.
