## Guard upkeep

Each rule has one home. Prompts reference it with
`@rule house-rules:<path>`; the prompt builder resolves and includes the
whole file at build time. Prompts never keep copied rule text. A missing file
fails the run visibly. Product targets stay in the repository's spec; private extensions
stay in `custom/`.

Use deterministic checks first for facts code can establish. Agent reviewers judge design
fit, root causes and spec intent. Test logging, pruning and testing constraints:
[prompts/skills/test-discipline.md §Test discipline](../../../prompts/skills/test-discipline.md). Review-round reassessment:
[pr-ready §3](../SKILL.md#3-review-rounds).

There are no fixed caps on blocking findings or filed issues. The triager decides by
severity and deduplication; all critical findings block. Capacity never skips or degrades
a guard. Only token exhaustion stops guard work, and it goes to the operator with the
unfinished work identified. This does not waive safety controls or operator stop requests.
One exception: an audit unit that makes no progress in two consecutive waves is deferred
until the next run ([Daily whole-system audit](#daily-whole-system-audit), step 4).

## Daily whole-system audit

Run an independent whole-system audit daily per repository through the audit scheduler
(for example Warden), using that repository's scope file. Examine the whole system from
first principles, including native capabilities, layers and their costs, fortification,
and spec/code drift; include the design lens in every daily run. A missing scope file is
a visible failure, never an excuse to skip the audit. The audit changes nothing in the
audited repository.

**Procedure: one audit run**

1. **Map the system:** one agent writes the threat model and the coverage list
   ([audit-map role](../../../prompts/roles/audit-map.md)). A coverage unit is one
   subsystem and focus; for the security focus, one subsystem and trust boundary.
2. **Check the accounting:** code, not a model, checks that every top-level file and
   directory belongs to a unit of each selected focus or is set aside with a reason
   (vendored, generated or documentation). A gap fails the run before any auditor starts.
3. **Audit in waves:** one auditor per open unit
   ([auditor role](../../../prompts/roles/auditor.md)) records checked line ranges with
   cited deciding lines. An auditor may ask for a reproduction; it runs only in a separate
   sandbox with no network except loopback, no credentials and a disposable copy.
4. **Check the gaps:** after each wave, one agent
   ([gap-check role](../../../prompts/roles/audit-gap-check.md)) reopens units whose rows
   lack cited evidence. Open units return to the next wave of the same run. A unit with no
   progress in two consecutive waves is deferred with "no progress"; the others continue,
   and the next run audits deferred units again after planned and stale ones. The audit
   report shows each deferred unit with what its auditors tried and what blocked them (job
   failures, unreadable files, the gap check's reasons), so someone can repair the cause.
5. **Triage and publish:** the [audit triager](../../../prompts/roles/audit-triager.md)
   merges and verifies findings; the service publishes them.

Later runs continue the coverage list. A checked unit becomes stale when a file in its
paths or dependencies, its focus instructions, or a threat-model entry of its boundaries
changed; stale and unchecked units run first. When nothing is open, a requested run
records "covered" and makes no model call.

Apply [Guard upkeep](#guard-upkeep) for filing policy. The triager deduplicates findings
by fingerprint against tracked findings. Comment on a known finding only when
materially new evidence changes it. The audit opens no PRs; it reports findings for the
lead to adjudicate and assign. Findings stay where the scheduler's configuration puts
them, for example a private results repository, so unfixed findings are never public.
