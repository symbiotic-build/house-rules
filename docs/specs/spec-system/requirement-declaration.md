<a id="requirement-declaration"></a>
# Requirement declaration

A requirement declaration makes an obligation verifiable by naming its actor, condition, result and linked tests.

Put the condition before the result in normative English.
A quality bound states operating conditions, measure, notation and pass condition.
The technical contract and implementation validate that bound.
Documentation checking does not validate a value's range or format.
Neither a full controlled requirements grammar nor mandatory uppercase keywords are required.

Every declaration links at least one [acceptance test](acceptance-test.md#acceptance-test).
Both directions must describe the same relationship.
Missing targets, missing relationships and one-sided links fail checking.
Passing these checks establishes structural traceability, not proof quality.
Implementation unit tests do not each require a documentation requirement.

Requirement anchors use `req-` followed by nonempty lower-case letters or digits separated by single hyphens.
The complete anchor is permanent and unique across the repository's specification and design corpus.
Preserve it when moving or revising the same obligation; never reuse a retired identity.
New obligations from a split or replacement receive new identities.
