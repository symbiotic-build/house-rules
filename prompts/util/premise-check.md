## Premise check

Run this check on every foundational choice in a design: a storage layout, an
abstraction layer, a new mechanism, or a size that limits what consumers can store.
A recorded decision does not exempt a choice from this check.

- **Consumers measured.** Name each real consumer. Count its use from its code or data:
  record types, fields per type, field kinds, queries and sizes. A requirement sheet or
  brief that already assumes the choice is not a measurement. Measure the target consumer:
  code or behaviour scheduled for removal or replacement is a requirement the new design
  must take over, not evidence of where the design should place it. Check the consumer's
  roadmap or the operator's decisions before counting it.
- **Fit.** Show the choice against those counts, including the largest consumer case. A
  size that limits consumers is derived from the counts before approval. Calling it
  provisional postpones its value, never its check.
- **Need.** An abstraction layer states the consumer need that the direct design cannot
  meet, with the counts that show it. "Flexibility" or "future types" is not a need.
- **Simpler design.** Name the simplest design that meets the measured needs. When a
  dependency limit drives the choice, include a design that changes the dependency, such
  as a patch to a pinned engine. Keep the layer only when it beats that design on counted
  cost.

A failed check is a design finding under [Cost and design findings](cost-and-design.md).
Report the counts, the simpler design, and the operator decision the choice rests on, if
any. A failed check is new evidence against that decision (writing rules, Claim labels).
