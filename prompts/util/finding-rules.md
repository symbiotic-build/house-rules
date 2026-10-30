## Finding rules

A finding blocks only when its trigger is reachable in real use of the product, and the
report cites the code path from the entry point that real use calls to the faulty line.
Real use means the inputs, operations, configuration and environment the product meets
when people or its own services use it as documented, including routine restarts and
deploys of a service. A trigger that depends on behaviour outside the repository (a model
provider, the operating system, the Git host, the network) also cites an observation of
that behaviour: a log, a failed run, an incident record or the system's own documentation
of it. A case that a written requirement or declared boundary names explicitly is real
use only when that text names a real trigger: who or what produces the state in real use.
It counts only while the code still matches that requirement. Specifications and design
documents can be out of date; a guarantee the code no longer implements is not evidence.
A probe or test that builds the triggering state by hand shows the consequence, not that
real use reaches it.
"Real use can produce this state" is a claim, not evidence: it needs the code path in the
current product that produces the state, or an observation of it. When the context shows
that real use does not hold the triggering state, for example a deployment record without
it, the trigger is hypothetical.

The rule applies to every kind of finding. A documentation, procedure or design finding
that rests on a failure scenario needs that scenario's real-use trigger; a design finding
about the mechanism itself needs none.

These never block, whatever their consequence:

- a trigger that needs a condition nobody showed happens in real use: a manual edit of
  stored state, state the product never writes, a narrow timing window, a
  misconfiguration, or an attacker the threat model does not declare;
- hardening and defence in depth: an extra layer, check, retry or guarantee that no
  written requirement states;
- "could happen if": a consequence that depends on a future change or an unobserved event.

Reviewers report such an item under Follow-ups with the missing evidence named. Triage
rejects it as NITPICK. An issue is filed only when the operator asks for one.

A finding an earlier triage of the same pull request rejected, filed as an issue or sent
to a lead decision is decided. Nobody raises a decided finding again, in any round or
section: reviewers leave it out of findings checks, inventories and reports, and triage
lists a reviewer's repeat of it once under Rejected as decided. This exception overrides
every rule that asks to report deferred, tracked or earlier blocking findings.

A security finding names five things: who has less trust, the input they control, the
control that should stop them, what they reach, and the concrete result. Example: an
unauthenticated caller (less trust) sends an order ID (input) to `GET /orders/<id>`; the
handler skips the tenant check in the authorization helper (control); the caller reads
another tenant's order (reach and result). A security report that cannot name all five,
and a missing extra layer where another layer already blocks the attack, are hardening
notes: non-blocking, never Blocking defects.

A lead that depends on a fact outside the repository (a proxy setting, branch protection,
a deployed configuration) is reported with the missing fact named. Apply the real-use
test and disposition above; the repository alone cannot refute the outside fact.

A finding about a hard-coded credential cites the file, line and symbol, never the line's
text.

## Severity

The audit rating stage runs after triage and returns one rating per kept finding.
Auditors and audit triage do not assign severity levels.

For security findings, the audit rating stage writes a Common Vulnerability Scoring System
(CVSS) v4.0 base vector with a reason.
For that audit vector, include all Base metrics and no Threat, Environmental or Supplemental metrics.
The audit host validates the vector and computes its score and level.
In the audit rating stage, the model never writes a security finding's score or level.
The audit host uses these score bands:

| Score | Level |
|---|---|
| 9.0–10.0 | critical |
| 7.0–8.9 | high |
| 4.0–6.9 | medium |
| 0.1–3.9 | low |
| 0.0 | note |

For design and correctness findings, the audit rating stage chooses a level from this rubric.
Apply the real-use test above before choosing a level from the consequence and who meets it.
A slowdown counts only when measured or observed in real use.

- **critical:** The defect loses or corrupts data, or stops the product, for all users in
  real use. No workaround exists.
- **high:** The defect loses or corrupts data for some users or operations, or blocks a
  main workflow. It also covers a defect that makes a main workflow too slow to use in real use.
  Wrong results qualify unless a less common path has a usable workaround.
- **medium:** The defect gives wrong results on a less common path, or makes a main
  workflow unreliable. A usable workaround exists.
  It also covers a defect that makes a main workflow noticeably slower, and it still completes.
- **low:** The defect has a small effect users can see on an edge case in real use,
  including a defect that slows an edge case.
- **note:** The finding has no effect users can see in real use today, such as a missing
  test, missing documentation or a structural concern.
