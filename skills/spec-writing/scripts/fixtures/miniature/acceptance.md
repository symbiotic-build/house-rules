<a id="acceptance-section"></a>
# Checking a prepared write

A prepared request can become stale before submission.
This tour follows a refusal before explaining its limits.

**Procedure: demonstrate a stale revision**

1. **Prepare a request.**
   - It expects revision 7.
2. **Complete another write.**
   - The current revision becomes 8.
3. **Submit the prepared request.**
   - The [writer](#writer) performs [acceptance](#acceptance).
   - The [stale-revision requirement](#acceptance-stale-revision)
     defines the refusal.

> **Detail — byte accounting**
>
> The [log group byte limit](settings.md#log-group-limit)
> bounds the encoded group.
> Its [default](settings.md#log-group-limit-default)
> is a separate canonical fact.

<a id="writer"></a>
## Writer

The writer processes write requests.

It performs [acceptance](#acceptance) before allocating numbers.

<a id="acceptance"></a>
## Acceptance

Acceptance checks a prepared write against current state
before allocating numbers and appending it.

A revision check prevents a prepared request from using stale state.

### Relations

| Key | Predicate | Target | Basis |
|---|---|---|---|
| executor | performed-by | [Writer](#writer) | [Fixture](settings.md#fixture-decision) |
| byte-policy | limited-by | [Log group byte limit](settings.md#log-group-limit) | [Fixture](settings.md#fixture-decision) |

<a id="acceptance-stale-revision"></a>
### Requirement: stale-revision

**Actor:** [Writer](#writer).

**Condition:** A request's expected revision differs from the current revision.

**Result:** Return `Conflict` before allocating numbers.

**Verification:** Exercise a stale request and inspect number allocation.

**Tests:** [Stale request](#test-stale-revision).

**Status:** specified.

**Basis:** [Fixture](settings.md#fixture-decision).

<a id="acceptance-stale-failure"></a>
### Failure state: stale request

**Trigger:** The expected revision differs from current state.

**Outcome:** The caller receives `Conflict`.

**Retained state:** This request allocates no number and appends no write.

**Recovery:** Read current state and prepare a new request.

**Authority:** The caller needs ordinary authority for the new request.

**Verification:** [Stale request](#test-stale-revision).

<a id="stale-revision"></a>
### Scenario: stale-revision

**Purpose:** Follow a prepared request through a concurrent change.

**Inputs:** Expected revision 7; current revision 8.

**Expected:** `Conflict`, with no number allocated.

**Requirements:** [Stale-revision requirement](#acceptance-stale-revision).

**Tests:** [Stale request](#test-stale-revision).

<a id="test-stale-revision"></a>
### Acceptance test: stale request

**Method:** test.

**Requirements:** [Stale-revision requirement](#acceptance-stale-revision).

**Inputs:** A request expecting revision 7 and current revision 8.

**Expected:** `Conflict`, unchanged allocation state and no appended write.

**Implementation:** None; this fixture defines the test case.

**Entities in this example:** [Writer](#writer),
[acceptance](#acceptance).
