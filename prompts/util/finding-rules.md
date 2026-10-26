## Finding rules

A finding blocks only when its trigger is reachable in real use of the product, and the
report cites the code path from the entry point that real use calls to the faulty line.
Real use means the inputs, operations, configuration and environment the product meets
when people or its own services use it as documented, including routine restarts and
deploys of a service. A trigger that depends on behaviour outside the repository (a model
provider, the operating system, the Git host, the network) also cites an observation of
that behaviour: a log, a failed run, an incident record or the system's own documentation
of it. A case that a written requirement or declared boundary names explicitly, such as
"a crash at any step recovers", is real use for that requirement. A probe or test that
builds the triggering state by hand shows the consequence, not that real use reaches it.
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
rejects it as NITPICK, or files it as ISSUE when it is worth tracking.

A finding an earlier triage of the same pull request rejected, filed as an issue or sent
to a lead decision is decided. Nobody raises a decided finding again, in any round or
section.

A security finding names five things: who has less trust, the input they control, the
control that should stop them, what they reach, and the concrete result. Example: an
unauthenticated caller (less trust) sends an order ID (input) to `GET /orders/<id>`; the
handler skips the tenant check in the authorization helper (control); the caller reads
another tenant's order (reach and result). A security report that cannot name all five,
and a missing extra layer where another layer already blocks the attack, are hardening
notes: non-blocking, never Blocking defects.

A lead that depends on a fact outside the repository (a proxy setting, branch protection,
a deployed configuration) is reported with the missing fact named. Triage files it as
ISSUE naming that fact; it is never FALSE, because the repository alone cannot refute it.

A finding about a hard-coded credential cites the file, line and symbol, never the line's
text.
