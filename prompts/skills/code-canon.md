Canon the change must follow, in any language. Every line applies to code that stays: product
code, shared tools and kept internal tools. Disposable code is a spike or prototype that the task
declares throwaway and that never lands in the product tree; it follows only the lines under
"Always".

Always:
- Fail visible: nothing is silently skipped, dropped, capped, truncated or degraded;
  errors reach the caller; no fail-open paths. Root causes, not suppression: a retry,
  sleep, catch-all or widened tolerance that hides a symptom is blocking.
- Never remove or downgrade a security or architecture boundary as a workaround. A
  boundary is one the spec, threat model or shipped runtime declares; a reviewer concern
  is not one by label alone. Credentials never appear in code, tests, fixtures or logs.
- Settled operator decisions bind; the writing rules name the new evidence that reopens
  one under Claim labels. If the code follows one you think is wrong, reviewers report it
  under Spec issues with "operator decision needed"; other roles report it in the final
  message's Open questions section with the same label; do not block on it. That
  non-blocking path covers disagreement without new evidence. New evidence against a settled
  decision, including a failed premise check that shows it, is a design finding under the review bar's Cost and
  design findings.
- Claims such as "measured", "verified" or "bounded" point at the test, benchmark or code
  that shows them.

Code that stays:
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

Performance-sensitive code that stays:
- A performance rewrite states the measured baseline and the required improvement as
  acceptance criteria.
- Keep typed values and existing numeric identities through computation and
  serialization. Convert to presentation text only at an output boundary that needs it.
  A generic value tree, or text built only to sort, compare or identify records, needs a
  measured reason.
- Read, decode or parse each input once per run. A pass that decodes the same input
  again needs a measured reason.
- Make parallel results deterministic by merging each worker's results in input order.
  Never add a serial pass over the same input to fix numbering or order in advance.
- A change whose own measurement shows it slower, or larger in memory, is reverted or
  explained before the next change builds on it.
- Before replacing a large representation, identify shared payloads that materially
  control cost. Preserve useful sharing and measure distinct payloads, references and
  encoded bytes separately. Faster writing does not excuse an unexplained storage or
  memory regression. Do not add sharing machinery for duplication cheaper to keep.
- Before using a serialization API per record on a high-volume path, inspect its pinned
  implementation for allocation, copying, flushing and finalization. Keep buffering and
  completion with the stream owner unless the format or required per-record durability
  dictates otherwise. Confirm suspected costs with a focused profile or measurement.
