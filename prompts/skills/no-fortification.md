## No fortification

A cache, budget, retry, index-like row, indirection or reduced test that works around
cost or complexity elsewhere must name the root cause. Fix that cause or cite a recorded
decision accepting the workaround. First ask whether the mechanism should exist; delete
or narrow it before adding another mechanism. A workaround without that evidence blocks
review.

When the same class of defect has already been fixed once, first ask whether the mechanism
should exist: delete or narrow it when that suffices. Then check whether the spec is unclear.
Only then introduce one shared mechanism that makes the class impossible instead of
patching another call site. When a finding targets a mechanism an earlier fix round added,
apply this repair order. Defects whose triggers pass through one shared structure, such as
a shared column pool, are one class even when their symptoms differ.

- Treat the first and second occurrence of the same failure class as potentially valid product or scope discoveries.
- Implementers and fixers: diagnose, fix, and verify them normally when they remain outcome-aligned.
- At the third consecutive occurrence, ask whether previous work advanced a requested acceptance criterion.
- Check whether this remains the cheapest path to the requested outcome.
- Check whether the abstraction or supporting mechanism is wrong.
- Consider simplifying, deleting, deferring, or redesigning it.
- Check whether continuing remains inside the approved resource envelope.
