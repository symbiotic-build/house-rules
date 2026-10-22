## Finding rules

A security finding names five things: who has less trust, the input they control, the
control that should stop them, what they reach, and the concrete result. Example: an
unauthenticated caller (less trust) sends an order ID (input) to `GET /orders/<id>`; the
handler skips the tenant check in the authorization helper (control); the caller reads
another tenant's order (reach and result). A missing extra layer, where another layer
already blocks the attack, is a hardening note: non-blocking, never a Blocking defect.

A lead that depends on a fact outside the repository (a proxy setting, branch protection,
a deployed configuration) is reported with the missing fact named. Triage files it as
ISSUE naming that fact; it is never FALSE, because the repository alone cannot refute it.

A finding about a hard-coded credential cites the file, line and symbol, never the line's
text.
