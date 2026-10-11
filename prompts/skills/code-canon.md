Canon the change must follow:
- Fail visible: nothing is silently skipped, dropped, capped, truncated or degraded;
  errors reach the caller; no fail-open paths. Root causes, not suppression: a retry,
  sleep, catch-all or widened tolerance that hides a symptom is blocking.
- Never remove or downgrade a security or architecture boundary as a workaround. A
  boundary is one the spec, threat model or shipped runtime declares; a reviewer concern
  is not one by label alone. Credentials never appear in code, tests, fixtures or logs.
- Settled operator decisions bind; the writing rules define settled under Claim labels. If
  the code follows one you think is wrong, reviewers report it under Spec issues with
  "operator decision needed"; other roles report it in the final message's Open questions
  section with the same label; do not block on it. An unratified decision binds no review:
  judge the choice on its merits, and name the brief test it failed.
- Simplicity: one mechanism per concept; duplicates are merged; a shared owner is
  extended, never forked into a local copy; every structure has a defensible reason.
- Delete unreleased dead paths; rebuild pre-release internal formats and current live data, without migrations or legacy readers; product schema migrations may be a feature.
- Policies that could vary are versioned config with spec-stated defaults, not constants.
- Derived indexes and caches are rebuildable from the canonical store and never become a
  second source of truth.
- Add no persistent structure (stored state, field, index, projection, cache, queue, mirror)
  the spec or task does not require. Prefer deriving from the source of truth over
  maintaining a second copy of it. New persistent state needs a spec
  line or settled decision that requires it; state that only duplicates the source of
  truth is waste. Ask "why does this exist?" before "how do we keep it in sync?".
- Ordering invariants the code depends on are written down.
- Structured fields (ids, timestamps, typed values) over parsing meaning from text.
- Claims such as "measured", "verified" or "bounded" point at the test, benchmark or code
  that shows them.
- Rust: no `unwrap()` in library code; `thiserror` in libraries, `anyhow` only in binaries
  and never on hot paths; public items carry `///` docs.
