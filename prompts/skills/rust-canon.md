Rust canon, applied together with the code canon. Every pack whose target tracks a
Cargo.toml includes it. The scope lines of the code canon apply here too: disposable code
follows only its "Always" lines.

- No `unwrap()` in library code; tests may use it. Errors reach the caller.
- `thiserror` in libraries, `anyhow` only in binaries and never on hot paths.
- Public items carry `///` docs.
- Async uses tokio; non-blocking and multi-threaded by default.
- Property and sequence tests use `proptest`; fuzzing uses `cargo-fuzz`.
- Experimental Cargo features default off, and output is byte-identical when they are off.
- Where the repository ships build or test scripts, use them instead of raw cargo commands.
- Zero warnings: `cargo fmt --check` and `cargo clippy -- -D warnings` pass on the
  changed crates. Local scope and build profiles follow Local builds.
