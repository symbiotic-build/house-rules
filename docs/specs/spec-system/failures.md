<a id="failure-declaration"></a>
# Failure declaration

A failure declaration helps callers recover by explaining a refusal, retained state and required authority.

Every mechanism that stops, refuses or remains blocked declares Trigger, Outcome, Retained state, Recovery, Authority and Verification.
If recovery is unavailable, write **Recovery: none** and explain the consequence.
A non-stopping mechanism says why it cannot refuse.
Do not imply that retry, restart or ordinary writes repair retained invalid state.

The checker requires fields and resolving links.
Reviewers trace entry, retained state, restart behavior and exits.
Public interfaces also receive error-mapping review.
A declared absence of recovery makes a limitation visible; it does not approve the technical design.


In the bounded-batch example, the caller can submit the refused item in a new batch; the old batch remains intact.
The exact files are explained later in [Minimal corpus](example.md#minimal-example).
