## Check round

This review round checks a fix. Earlier rounds reviewed the whole change against its requirements. The earlier findings
list what they left open and what they rejected, with reasons. The fix is the pull request's own change since the last
reviewed head: `git diff <fix base>..HEAD`. Part 5 of the review context shows it when the context has a part 5. The
whole change, the requirements and all other code stay in the checkout as reference, not as the review task.

1. **Verify the open findings.** Take every finding the earlier findings list as open and every blocking item of your
   own earlier report. Check each against the code at HEAD and quote the evidence. List each in your report's findings
   check as RESOLVED or NOT, with that evidence; a reviewer adds a "**Findings check · <count>**" section after
   Blocking. A still-open finding keeps its earlier class: when it blocked and your lens owns it or your earlier report
   holds it, list it under Blocking again with the current evidence. A Low finding stays non-blocking.
2. **Review only the fix.** Apply your procedure and inventories to the fix and the code it touches: the callers,
   callees and consumers of the changed code. Report the defects the fix introduces. Raise no new finding outside the
   fix: a defect there waits for a later full round or an issue. Branch-history findings follow
   [Triage classes](triage-classes.md).
   Apply the same classes as round 1. Never ask for changes that grow the pull request beyond the accepted fixes.
3. **Never raise a decided finding again** ([Finding rules](finding-rules.md)). When the fix rewrote the code a decided
   finding cites, report only a defect that the new code itself introduces, as a finding about the fix.

Your coverage ledger and inventories cover the fix only.
