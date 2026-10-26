## Required review procedure

Your report is incomplete unless it contains the coverage ledger and every inventory of your lens below, and the lead
rejects an incomplete report. A finding does not complete them, and an "Outside lens:" finding does not complete them.
Every check is a static trace of the code and documents: do not deploy or interrupt anything, and do not change files.
Do not execute project code, builds or tests beyond the one targeted test the reviewer role allows in a lane session.
Read-only git, file and search commands are expected.

When part 5 of the review context starts with two lists, files shown whole are there in full, every line numbered,
with their changes marked in place: do not open or print them again; cite their line numbers from part 5. Files shown
as a diff only have 3 lines of context: read their other lines in the checkout. Use the checkout also for unchanged
files, searches and history.

1. **List the obligations.** Number every item of your lens checklist and every inventory below as O1, O2 and so on.
   Work through them in order of consequence: security, data loss and wrong results first.
2. **Find the units and governing requirements.** Start from the changed functions, tests, configuration entries,
   commands and document sections. Add the callers, callees and final consumers that decide a changed case, including
   unchanged ones. Search the unchanged documents, specifications, issues and decisions for every requirement that
   governs those units' outputs, failures, retained state and recovery, and read each governing paragraph in full.
   Inventories cover these changed sites and their governing requirements; anything wider you leave out is
   "unchecked:" with the boundary you stopped at.
3. **Split each obligation into cases.** A case is one input class, failure cause, exit path, entry path, mode,
   resource, setup write, object kind or document section. Different causes, exits, resources and writes are
   different cases even when they share a function or a message.
4. **Trace each case to its final consumer.** Read the code or text with line numbers. Read the implementation that
   produces, serializes or renders a value; a read of the call is not a read of the callee. Decide: a finding, or no
   defect with the line that enforces the required behavior for this case. A line showing that an operation happens
   does not show that its result is correct. A test proves only the cases its fixture and assertions exercise. A
   traced case where the code permits or produces behavior a requirement forbids, such as a forbidden interleaving, a
   lost result or an omitted required output, is a finding; never mark it "no defect".
5. **Keep verification apart from disposition.** Record every missing, partial or contradicted requirement as a
   finding, even when it predates the change, is deferred, is out of the pull request's scope or is tracked in an
   issue; state that disposition in the finding. A finding an earlier triage of this pull request decided is the
   exception: leave it out ([Finding rules](finding-rules.md)). To close a case with a decision, quote the decision's operative
   sentence and apply it only to what it explicitly authorizes. A decision about timing or current availability does
   not remove a requirement.
6. **Compare old and new.** For every changed function, compare its old and new behavior using the removed (-) and
   added (+) lines, and check the callers and consumers that relied on the old behavior.
7. **Continue after a finding.** A finding covers only the cases named in its trigger; a case row may cite a finding
   only when that trigger names the case. Return to the next open case. When a trace shows a wrong result, an omitted
   required output, or behavior outside a stated only, never or always restriction, report that case as its own
   finding with its trigger and consequence, even when tests are also missing. Never fold it into a test-coverage
   follow-up or into a finding about another trigger.
8. **Fill the inventories.** Search the change and the repository for each inventory's rows and record the search in
   an evidence note. An inventory whose search finds nothing in its whole scope, including the dependencies that decide
   a changed case, is one case row with the result "0 hits" and the search in its note. A behavior
   a requirement demands that the change lacks is a finding, even when a search found nothing.
9. **Report what you could not check.** When you suspect a defect in an unchecked case, report it under Follow-ups with
   the missing evidence; it blocks only after a trace shows a real-use trigger. List other unchecked cases on security,
   data-loss or wrong-result paths under Follow-ups as coverage gaps, each naming the missing evidence.

The coverage ledger takes the place of the report format's Coverage section and is the last section of the report: the
obligation table, then the case table, then numbered evidence notes. Keep it even when there are no findings. Every
case, from a checklist item or an inventory, is one row of the case table with an id C1, C2 and so on, except
no-defect cases off security, data-loss and wrong-result paths, which the obligation table lists by id range. Cells
hold a few words: an id, a short case name, a `file:line` and a result. The inventory's own columns, the deciding
line's quote and any trace go in the evidence note the row names; the notes are the one place for longer text.

```text
**Coverage ledger**
| Obligation | Case rows | Results |
|---|---|---|
| O1 Error handling | C1-C4 | B1: C2, C3; unchecked: C4; no defect: C1 |

| Row | Obligation | Case | Traced | Deciding line | Result |
|---|---|---|---|---|---|
| C1 | O1 | Lookup fails before write | src/a.rs:40-52 | a.rs:47, note 1 | no defect |
| C2 | O1 | Write fails after rename | src/a.rs:60-88 | a.rs:81, note 2 | B1 |

1. a.rs:47 `return Err(e)` returns before any write.
2. a.rs:81 `let _ = remove(&tmp)` drops the cleanup error.
```

A case result is one of: a finding label whose trigger names this case; "no defect" with its deciding line;
"unchecked:" with the missing evidence or the boundary; "not reached:" when your lens does not reach this unit, with
the reason; or "0 hits" for an empty inventory search. A row without a code or text line puts "-" in the deciding-line
cell and its reason in the note. An obligation stays incomplete while one of its cases has no result. Keep the ledger
short: no-defect cases that share a deciding line share one row, and only cases on a path where a defect would cause a
security, data-loss or wrong-result failure need a deciding line and a note; list other no-defect cases by id range in
the obligation table.
