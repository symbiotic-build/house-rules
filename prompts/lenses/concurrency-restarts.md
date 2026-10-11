## Lens: concurrency, restarts and bounds

Look for:
- Two at once: two callers, workers, processes or hosts running the changed code at the
  same time; check-then-act races, lost updates, lock order and deadlock, shared state
  without ownership.
- Crash or restart at each step: for every write, what a crash just before and just
  after it leaves on disk or in remote systems, and whether the next start recovers,
  repeats or skips the step.
- Durability: data reported as saved before it is synced; rename, sync and directory
  sync order; temporary files left behind; recovery that trusts a half-written file.
- Retries and replay: a retried request or replayed event applied twice; idempotency
  keys; side effects (comments, payments, messages) sent twice or never.
- Ordering: events processed out of order; stale reads used to decide a write;
  clocks that move backwards or differ between hosts.
- Bounds: memory, disk, file handles, processes, queue length, retries, timeouts and
  cost that grow without a limit; limits that fail silently instead of visibly.
- Cleanup: resources owned by a failed or cancelled job are released, and cleanup never
  removes another job's resources.

Out of scope (owning lens):
- Wrong results on a single sequential path, authorization and secrets:
  `correctness-security`.
- Fit with the issue, specification and settled decisions: `spec`.
- Simplicity, dead code, duplication and scope: `waste`.
- Document premise and readability: `design-spec`.

@rule house-rules:prompts/util/targeted-lens.md
