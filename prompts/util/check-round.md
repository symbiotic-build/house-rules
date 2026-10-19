## Check round

This review round checks a fix. Earlier rounds reviewed the whole change against its requirements. The earlier findings
list what they left open and what they rejected, with reasons. The fix is the pull request's own change since the last
reviewed head: `git diff <fix base>..HEAD`. Part 5 of the review context shows it when the context has a part 5. The
whole change, the requirements and all other code stay in the checkout as reference, not as the review task.

1. **Verify the open findings.** Take every finding the earlier findings list as open and every blocking item of your
   own earlier report. Check each against the code at HEAD and quote the evidence. List each in your report's findings
   check as RESOLVED or NOT, with that evidence; a reviewer adds a "**Findings check · <count>**" section after
   Blocking. A finding that is still open keeps blocking: when your lens owns it or your earlier report holds it, list
   it under Blocking again with the current evidence.
2. **Review only the fix.** Apply your procedure and inventories to the fix and the code it touches: the callers,
   callees and consumers of the changed code. Report the defects the fix introduces or exposes. Outside the fix, report
   only correctness, security or data-loss defects. Branch-history findings follow [Triage classes](triage-classes.md).
   Apply the same classes as round 1. Never ask for changes that grow the pull request beyond the accepted fixes.
3. **Keep rejected findings rejected.** A finding an earlier triage rejected stays rejected unless the fix changed the
   code it cites or you have new evidence. Then say what changed.

Your coverage ledger and inventories cover the fix only.
