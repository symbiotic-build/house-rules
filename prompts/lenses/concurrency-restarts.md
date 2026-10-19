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
@rule house-rules:prompts/util/review-procedure.md

### Inventories for concurrency, restarts and bounds

1. **Shared-input table.** One row per read of a file, configuration, reference or remote object reachable from the
   changed dispatch or loop. Columns: whether every consumer uses one captured value or re-reads a mutable source, and
   for each re-read an interleaving in which the source changes between consumers.
2. **Check-to-use table.** One row per check that gates a write, dispatch, stop or admission. Columns: every writer of
   the checked state (including a live, healthy second owner), temporary versus terminal meanings, and what keeps the
   check true until use.
3. **Side-effect eligibility table.** For each external side effect (publication, notification, approval, deletion)
   permitted during failure, retry or recovery: one row per cause that can reach its gate, including causes that share
   a marker, flag, status or error wrapper. Columns: cause, the prohibition or permission that governs it, the evidence
   available at the gate, and behavior after restart when only retained state remains. The deciding line shows
   positive evidence that this cause is permitted; a shared marker, a flag that a marker exists or a generic error does
   not.
4. **Failure-origin table.** One row per fallible stage reachable through each changed retry, replacement or recovery
   chain, including unchanged callees: selection, preparation, reservation, execution, output capture, persistence,
   restoration, cleanup, parsing, validation and publication. Columns: producer and line, work already completed,
   category at the handler, handler action, and the final caller-visible result. Trace a successful external
   operation followed by each host-side failure, and a setup failure followed by a later successful alternative.
   Logging an error, or keeping an earlier failure, does not deliver the new cause to the caller; a guard for one
   category does not cover the others.
5. **Retained-state table.** One row per identity, assignment, exclusion, counter or result copied into a later attempt
   or cycle. Trace two cycles with changed conditions: the original resource fails and an alternative succeeds; then
   the alternative fails while the original is available again. Derive the complete candidate set of the second cycle,
   combine newly selected work with what was retained, and count actual dispatches per logical item to find
   duplicates.
6. **Interruption trace.** For every multi-step durable operation and recovery path, trace on paper a stop after each
   step, including before the first durable record and after each replacement write; then the restart through the
   normal entry point and a second stop during recovery. Recovery never reports success after a failed cleanup, never
   destroys another owner's state, and invalidates results derived from replaced inputs.
7. **Bounds table.** One row per resource the change uses: memory, disk, file handles, processes, queue length,
   retries, timeouts, fan-out and scans. Columns: owner, and worst case at the minimum, default and maximum supported
   settings and the largest accepted input. A limit must not permanently block required progress;
   a limit or stop that a requirement demands is not a bounds defect. Repeated work on unchanged input belongs to waste.
