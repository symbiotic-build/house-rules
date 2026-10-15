<a id="settings-section"></a>
# Settings

These settings distinguish byte limits from document-count limits.

<a id="log-group-limit"></a>
## Log group byte limit

The log group byte limit bounds encoded bytes in one log group.

### Values

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="log-group-limit-default"></a>default | 4 MiB | specified | [Fixture](#fixture-decision) |
| <a id="log-group-limit-scope"></a>scope | instance | specified | [Fixture](#fixture-decision) |

<a id="commit-capacity"></a>
## Commit capacity

Commit capacity bounds documents in one commit.

### Values

| Key | Value | Status | Basis |
|---|---|---|---|
| <a id="commit-capacity-default"></a>default | 1,024 | provisional | [Fixture](#fixture-decision) |

**Qualification for [default](#commit-capacity-default):**
Qualify the selected capacity before treating it as an operating guarantee.

<a id="call-capacity"></a>
## Call capacity

Call capacity bounds documents in one native call.

Its default uses the [default](#commit-capacity-default)
of [commit capacity](#commit-capacity).
That fact's provisional qualification applies.
This home declares no independent default.

<a id="fixture-decision"></a>
## Decisions

**Choice:** Use this corpus to demonstrate source declarations.

**Authority:** fixture.

**Reason:** It covers homes, literal values, shared defaults and [acceptance](acceptance.md#acceptance) links.

**Rejected alternative:** Maintain independent copies of a shared default.

<a id="open-questions"></a>
## Open questions

None for this fixture.

<a id="reference"></a>
## Reference

The [stale-request scenario](acceptance.md#stale-revision)
demonstrates the revision refusal.
