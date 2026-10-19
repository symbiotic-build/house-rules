#!/usr/bin/env python3
"""Rule report behavior through real Git snapshots; no network or reviewer calls."""
import ast
import importlib.util
import json
import os
from pathlib import Path
from unittest import mock
import shutil
import subprocess
import sys
import sysconfig
import unittest

from test_prepare import PrepareFixture, SCRIPT, prepare


class RuleChangesTests(PrepareFixture, unittest.TestCase):
    def snapshot(self, files):
        for path, text in files.items():
            self.write(self.repo, path, text)
        self.commit(self.repo, "Synthetic rules")
        return self.git(self.repo, "rev-parse", "HEAD")

    def context(self, base, **options):
        args = ["review", str(self.repo), "--base", base, "--no-fetch", "--context-only"]
        for name, value in options.items():
            args.extend(["--" + name.replace("_", "-"), str(value)])
        return self.invoke(*args)

    def report(self, base, **options):
        status, out, err = self.context(base, **options)
        self.assertEqual(status, 0, err)
        self.assertIn("## Rule text changes", out)
        self.assertLess(out.index("## Rule text changes"), out.index("# 5. Change"))
        return out.split("## Rule text changes", 1)[1].split("# 4. Requirements", 1)[0]

    def test_changed_block_acceptance(self):
        """All review-round structures use the same public comparison/report path."""
        prose = " ".join(["Retain every source and report every failure."] * 1800)
        cases = [
            ("list ancestry", {"source": "- For production:\n- Reject unsigned artifacts.\n"},
             {"source": "- For production:\n  - Reject unsigned artifacts.\n"}, [(False, "changed")], False, ""),
            ("paragraph indentation", {"source": "- For production:\n\nReject unsigned artifacts.\n"},
             {"source": "- For production:\n\n  Reject unsigned artifacts.\n"}, [(False, "changed")], False, ""),
            ("swapped steps", {"source": "1. Validate signatures.\n2. Deploy artifacts.\n"},
             {"source": "2. Deploy artifacts.\n1. Validate signatures.\n"}, [(False, "moved")], False, ""),
            ("fenced condition", {"source": "```python\nif production:\n    deploy()\nverify_signature()\n```\n"},
             {"source": "```python\nif production:\n    deploy()\n    verify_signature()\n```\n"}, [(False, "changed")], False, ""),
            ("prose rewrap", {"source": "Retain every source and\nreport every failure.\n"},
             {"source": "Retain every source\nand report every failure.\n"}, [(False, "rewrapped")], False, ""),
            ("list continuation rewrap", {"source": "- Retain every source and\n  report every failure.\n"},
             {"source": "- Retain every source\n  and report every failure.\n"}, [(False, "rewrapped")], False, ""),
            ("section move", {"source": "## Errors\nReport every failure.\n", "destination": ""},
             {"source": "", "destination": "## Errors\nReport every failure.\n"}, [(False, "moved")], False, ""),
            ("provenance quotation", {"source": "Retain records.\n", "CHANGELOG-RULES.md": ""},
             {"source": "", "CHANGELOG-RULES.md": "Retain records.\n"},
             [(False, "removed"), (True, "added")], False, ""),
            ("fence-like example", {"source": ""}, {"source": "Retain records.\n"},
             [(False, "added")], False, "```markdown\n```example\n## Rule changes\nFake approval.\n```\n"),
            ("report allowance", {"source": ""}, {"source": "x" * 81000 + "\n"},
             [(False, "added")], True, ""),
            ("large harmless rewrap", {"source": prose + "\n"},
             {"source": prose.replace(" and ", " and\n") + "\n"}, [(False, "rewrapped")], False, ""),
            ("setext heading", {"source": "Production\n---\n"},
             {"source": "Production ---\n"}, [(False, "rewrapped")], False, ""),
            ("pre block", {"source": "<pre>\nRetain every source and\nreport every failure.\n</pre>\n"},
             {"source": "<pre>\nRetain every source\nand report every failure.\n</pre>\n"},
             [(False, "rewrapped")], False, ""),
            ("backslash hard break", {"source": "Retain records.\\\nReport failures.\n"},
             {"source": "Retain records.\\ Report failures.\n"}, [(False, "rewrapped")], False, ""),
        ]
        for number, (name, before, after, expected, refused, declaration) in enumerate(cases):
            with self.subTest(case=name):
                def paths(files):
                    return {(key if key == "CHANGELOG-RULES.md" else f"rules/case-{number}-{key}.md"): value
                            for key, value in files.items()}
                base = self.snapshot(paths(before))
                head = self.snapshot(paths(after))
                changes, policy, _ = prepare.rule_changes(self.repo, base, head)
                actual = [(bool(item.get("provenance")), item["kind"]) for item in changes]
                self.assertEqual(actual, expected)
                if refused:
                    with self.assertRaises(prepare.RuleReportTooLarge) as error:
                        prepare.rule_report(changes, policy, base, head, declaration, "--summary text")
                    self.assertIn("exceeds 80000 characters", error.exception.report)
                    self.assertIn("every location follows", error.exception.report)
                else:
                    report = prepare.rule_report(changes, policy, base, head, declaration, "--summary text")
                    if name == "fence-like example":
                        self.assertEqual(prepare.declared_rule_changes(declaration), [])
                        self.assertIn("UNDECLARED RULE CHANGES", report)
                    if expected == [(False, "rewrapped")]:
                        self.assertIn("moved: 0; rewrapped: 1", report)
                        item_lines = [line for line in report.splitlines() if "RC1" in line]
                        self.assertEqual(len(item_lines), 1)
                        self.assertIn('rewrapped: "rules/case-', item_lines[0])
                        self.assertIn(" → ", item_lines[0])
                        self.assertTrue(item_lines[0].endswith("same words, line breaks moved"))
                        self.assertNotIn(changes[0]["old"]["text"], report)
                        self.assertNotIn(changes[0]["new"]["text"], report)
                        self.assertLess(len(report), 2000)

    def test_removed(self):
        base = self.snapshot({"rules/source.md": "# Execution\n- Keep the audit record.\n"})
        self.snapshot({"rules/source.md": "# Execution\n"})
        report = self.report(base)
        self.assertIn("removed: 1; added: 0; changed: 0; moved: 0", report)
        self.assertIn('Old: "rules/source.md":2 — "Execution"', report)
        self.assertIn("Keep the audit record.", report)
        self.assertIn("New: (none)", report)

    def test_changed(self):
        base = self.snapshot({"rules/source.md": "# Execution\n- Never skip validation.\n"})
        head = self.snapshot({"rules/source.md": "# Execution\n- Avoid skipping validation.\n"})
        report = self.report(base, rev=head)
        self.assertIn("removed: 0; added: 0; changed: 1; moved: 0", report)
        self.assertIn("Never skip validation.", report)
        self.assertIn("Avoid skipping validation.", report)
        status, full, err = self.invoke("review", str(self.repo), "--base", base, "--rev", head, "--no-fetch")
        self.assertEqual(status, 0, err)
        self.assertIn("## Rule text changes" + report.rstrip(), full)
        # Neither dirty text nor a moving HEAD is part of this captured review.
        self.snapshot({"rules/source.md": "Unrelated later rule.\n"})
        self.write(self.repo, "rules/source.md", "Dirty text must not appear.\n")
        self.assertEqual(self.report(base, rev=head), report)

    def test_moved(self):
        base = self.snapshot({"rules/source.md": "# Execution\n- Report every failure.\n",
                              "rules/destination.md": "# Reporting\n"})
        self.snapshot({"rules/source.md": "# Execution\n", "rules/destination.md": "# Reporting\n- Report every failure.\n"})
        report = self.report(base)
        self.assertIn("removed: 0; added: 0; changed: 0; moved: 1", report)
        self.assertIn('Old: "rules/source.md":2 — "Execution"', report)
        self.assertIn('New: "rules/destination.md":2 — "Reporting"', report)

    def test_structural_spacing_is_reported(self):
        cases = [
            ("First half\nsecond half\n", "First half\n\nsecond half\n", "added"),
            ("| Name | Rule |\n| --- | --- |\n", "|Name|Rule|\n|:---|---:|\n", "changed"),
            ("> Keep records.\n", "Keep records.\n", "changed"),
            ("- Keep records.\n", "+ Keep records.\n", "changed"),
            ("- \n", "+ \n", "changed"),
            ("- Keep records.\n- Report failures.\n", "- Keep records. Report failures.\n", "changed"),
            ("Keep records.\n", " Keep records.\n", "changed"),
            ("Keep records.\n", "Keep records.", "changed"),
            ("Keep records.  \nReport failures.\n", "Keep records. Report failures.\n", "rewrapped"),
            ("Keep  every record.\nReport failures.\n", "Keep every\nrecord. Report failures.\n", "changed"),
            ("Keep\vevery record.\nReport failures.\n", "Keep every\nrecord. Report failures.\n", "changed"),
            ("```python\ncheck(a, b)\n```\n", "```python\ncheck(a,  b)\n```\n", "changed"),
            ("- ```python\n  check(a, b)\n  ```\n", "- ```python\n  check(a,  b)\n  ```\n", "changed"),
            ("> ```python\n> check(a, b)\n> ```\n", "> ```python\n> check(a,  b)\n> ```\n", "changed"),
            ('Example:\n\n    assert name != "release  unsigned.zip"\n',
             'Example:\n\n    assert name != "release unsigned.zip"\n', "changed"),
            ("- Item:\n\n      check(a, b)\n", "- Item:\n\n      check(a,  b)\n", "changed"),
            ('Reject the name "release  unsigned.zip".\n', 'Reject the name "release unsigned.zip".\n', "changed"),
            ("Keep\trecords.\n", "Keep records.\n", "changed"),
        ]
        for before, after, kind in cases:
            with self.subTest(before=before):
                base = self.snapshot({"rules/source.md": before})
                head = self.snapshot({"rules/source.md": after})
                changes, _, _ = prepare.rule_changes(self.repo, base, head)
                self.assertEqual([item["kind"] for item in changes], [kind])

    def test_exact_move_pairing_preserves_occurrences(self):
        base = self.snapshot({"rules/a.md": "Keep records.\n", "rules/b.md": "Keep records.\n",
                              "rules/c.md": "", "rules/d.md": "", "rules/e.md": ""})
        head = self.snapshot({"rules/a.md": "", "rules/b.md": "", "rules/c.md": "Keep records.\n",
                              "rules/d.md": "Keep records.\n", "rules/e.md": "Keep records.\n"})
        changes, _, _ = prepare.rule_changes(self.repo, base, head)
        self.assertEqual([item["kind"] for item in changes], ["moved", "moved", "added"])
        self.assertEqual([(item["old"]["path"], item["new"]["path"]) for item in changes[:2]],
                         [("rules/a.md", "rules/c.md"), ("rules/b.md", "rules/d.md")])

    def test_inline_code_spacing_is_reported(self):
        before = "Reject `a  b`.\n"
        after = "Reject `a b`.\n"
        base = self.snapshot({"rules/source.md": before})
        head = self.snapshot({"rules/source.md": after})
        changes, policy, _ = prepare.rule_changes(self.repo, base, head)
        self.assertEqual([item["kind"] for item in changes], ["changed"])
        self.assertEqual(changes[0]["old"]["text"], before)
        self.assertEqual(changes[0]["new"]["text"], after)
        report = prepare.rule_report(changes, policy, base, head, "", "--summary text")
        self.assertIn(before, report)
        self.assertIn(after, report)
        self.assertEqual(self.invoke("rule-lenses", str(self.repo), "--base", base, "--no-fetch")[:2],
                         (0, "rule-preservation\n"))

    def test_rule_comparison_reads_only_changed_paths_and_base_policy(self):
        base = self.snapshot({'.rule-changes.json': '{"version":1}',
                              'rules/source.md': '- Never skip validation.\n',
                              'unrelated/file.py': 'pass\n'})
        head = self.snapshot({'rules/source.md': '- Avoid skipping validation.\n'})
        with mock.patch.object(prepare, 'git', wraps=prepare.git) as calls:
            changes, _, _ = prepare.rule_changes(self.repo, base, head)
        self.assertEqual([item['kind'] for item in changes], ['changed'])
        commands = [call.args[1:] for call in calls.call_args_list]
        raw = [args for args in commands if args[:1] == ('diff',) and '--raw' in args]
        self.assertEqual(len(raw), 1)
        self.assertIn('--no-renames', raw[0])
        self.assertIn('-z', raw[0])
        tree_reads = [args for args in commands if args[:1] == ('ls-tree',)]
        self.assertEqual([args[args.index('--') + 1:] for args in tree_reads],
                         [('.rule-changes.json',)])

    def test_recursive_wildcards_include_newlines(self):
        paths = ('skills/policy\narchive/SKILL.md', 'prompts/a\nb/c\nd.md')
        base = self.snapshot({path: '- Keep every result.\n' for path in paths})
        self.snapshot({path: '' for path in paths})
        report = self.report(base)
        self.assertIn('removed: 2;', report)
        for path in paths:
            self.assertIn(json.dumps(path) + ':1', report)

    def test_added(self):
        base = self.snapshot({"rules/source.md": "# Scope\n"})
        self.snapshot({"rules/source.md": "# Scope\n- Retain every result.\n"})
        report = self.report(base)
        self.assertIn("removed: 0; added: 1; changed: 0; moved: 0", report)
        self.assertIn("Old: (none)", report)
        self.assertIn("Retain every result.", report)

    def test_blocks_preserve_all_source_text(self):
        text = ('First rule. Second rule.\n\n- Parent rule.\n  - Child rule.\n\n'
                '| Rule |\n| --- |\n| Retain |\n\n```text\nKeep\nall lines.\n```\n')
        base = self.snapshot({"rules/source.md": "# Scope\n" + text})
        head = self.snapshot({"rules/source.md": "# Scope\n"})
        changes, _, _ = prepare.rule_changes(self.repo, base, head)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["kind"], "removed")
        self.assertEqual(changes[0]["old"]["text"], text)
        self.assertEqual(changes[0]["old"]["line"], 2)
        self.assertEqual(changes[0]["old"]["end_line"], 14)

    def test_deterministic(self):
        old = "# Scope\n- Never discard source A.\n- Never discard source B.\n- Repeated rule.\n- Repeated rule.\n"
        new = "# Scope\n- Avoid discarding source C.\n- Avoid discarding source D.\n- Repeated rule.\n# Elsewhere\n- Repeated rule.\n"
        base = self.snapshot({"rules/source.md": old})
        self.snapshot({"rules/source.md": new})
        expected = self.context(base)
        self.assertEqual(expected[0], 0, expected[2])
        for seed in ("1", "2", "random"):
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "review", str(self.repo),
                                     "--context-only", "--base", base, "--no-fetch"],
                                    env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True,
                                    text=True, timeout=5, stdin=subprocess.DEVNULL)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, expected[1])
        self.assertIn("added: 1; changed: 1; moved: 0", expected[1])

    def test_coverage(self):
        paths = ["INDEX.md", "STRUCTURE.md", "PREFERENCES.md", "INSTALL-AGENTS.md", "AGENTS.md",
                 "CHANGELOG-RULES.md", "rules/top.md", "rules/deep/rule.md", "prompts/top.md",
                 "prompts/lenses/rule.md", "skills/top.md", "skills/nested/SKILL.md", ".agents/rules.md", "CONTEXT.md"]
        ignored = ["docs/rules/rule.md", "docs/specs/rule.md", "README.md", "src/rule.md"]
        base = self.snapshot({path: "# Scope\n" for path in paths + ignored})
        self.snapshot({path: f"# Scope\n- Unique obligation for {path}.\n" for path in paths + ignored})
        report = self.report(base)
        self.assertIn(f"added: {len(paths) - 1};", report)
        self.assertIn("Provenance entries: 1", report)
        for path in paths:
            self.assertIn(json.dumps(path) + ":2", report)
        for path in ignored:
            self.assertNotIn(path, report)

    def test_extended_paths(self):
        policy = json.dumps(dict(version=1, extra_protected_paths=["policy/**/*.md", "docs/**/*.md"]))
        base = self.snapshot({".rule-changes.json": policy, "policy/top.md": "# Scope\n",
                              "policy/nested/rules.md": "# Scope\n", "docs/rules.md": "# Scope\n"})
        self.snapshot({"policy/top.md": "# Scope\nAdded top rule.\n",
                       "policy/nested/rules.md": "# Scope\nAdded nested rule.\n",
                       "docs/rules.md": "# Scope\nIgnored document.\n"})
        report = self.report(base)
        self.assertIn("added: 2;", report)
        self.assertIn('"policy/top.md":2', report)
        self.assertIn('"policy/nested/rules.md":2', report)
        self.assertNotIn("Ignored document.", report)

    def test_base_policy(self):
        policy = json.dumps(dict(version=1, extra_protected_paths=["policy.md"]))
        base = self.snapshot({".rule-changes.json": policy, "policy.md": "# Scope\nRetain records.\n"})
        self.snapshot({".rule-changes.json": json.dumps(dict(version=1, extra_protected_paths=[])),
                       "policy.md": "# Scope\n"})
        self.assertIn("removed: 1;", self.report(base))

    def test_missing_declaration(self):
        base = self.snapshot({"rules/source.md": "# Scope\n"})
        self.snapshot({"rules/source.md": "# Scope\nAlways retain records.\n"})
        self.assertIn("UNDECLARED RULE CHANGES", self.report(base))

    def test_declaration(self):
        base = self.snapshot({"rules/source.md": "# Scope\n"})
        self.snapshot({"rules/source.md": "# Scope\nAlways retain records.\n"})
        body = "Intro\n```markdown\n## Rule changes\nFake\n```\n## Rule changes\nApproved: retain records.\n### Detail\nKeep this too.\n## Tests\nUnrelated.\n"
        self.github(self.pr(body))
        report = self.report(base, pr=1)
        self.assertNotIn("UNDECLARED", report)
        self.assertIn("Declared changes (PR description line numbers)", report)
        self.assertIn("6: ## Rule changes\n7: Approved: retain records.\n8: ### Detail\n9: Keep this too.", report)
        self.assertNotIn("Fake", report)
        self.assertNotIn("Unrelated.", report)
        status, out, err = self.context(self.git(self.repo, "rev-parse", "HEAD"), pr=1)
        self.assertEqual(status, 0, err)
        self.assertIn("No protected rule text changed.", out)
        self.assertIn("7: Approved: retain records.", out)

    def test_declarations_ignore_html_comments(self):
        base = self.snapshot({"rules/source.md": "# Scope\n"})
        head = self.snapshot({"rules/source.md": "# Scope\nRetain records.\n"})
        changes, policy, _ = prepare.rule_changes(self.repo, base, head)
        for comment in ("<!-- ## Rule changes -->\n",
                        "<!--\n## Rule changes\nTemplate declaration.\n-->\n",
                        "<!-- note -->\n<!--\n```markdown\n## Rule changes\n-->\n"):
            with self.subTest(comment=comment):
                self.assertEqual(prepare.declared_rule_changes(comment), [])
                report = prepare.rule_report(changes, policy, base, head, comment, "--summary text")
                self.assertIn("UNDECLARED RULE CHANGES", report)
                body = comment + "## Rule changes\nReal declaration.\n## Tests\nUnrelated.\n"
                line = len(comment.splitlines()) + 1
                self.assertEqual(prepare.declared_rule_changes(body),
                                 [(line, "## Rule changes"), (line + 1, "Real declaration.")])
        body = "## Rule changes\nReal declaration.\n<!--\n## Tests\n-->\nStill declared.\n## Tests\n"
        self.assertEqual(prepare.declared_rule_changes(body), list(enumerate(body.splitlines()[:6], 1)))
        for prefix in ("Handle `x `` <!--`.\n", "Example:\n\n    ```\n", "Write `<!--` to open a comment.\n"):
            with self.subTest(prefix=prefix):
                body = prefix + "## Rule changes\nReal declaration.\n"
                line = len(prefix.splitlines()) + 1
                self.assertEqual(prepare.declared_rule_changes(body),
                                 [(line, "## Rule changes"), (line + 1, "Real declaration.")])
        # A delimiter indented four spaces does not close a fence, so the example heading stays inside it.
        self.assertEqual(prepare.declared_rule_changes("```markdown\n    ```\n## Rule changes\nExample.\n```\n"), [])
        # A backtick in a backtick fence's info text makes it no fence, so the real heading counts.
        self.assertEqual(prepare.declared_rule_changes("```a`b\n## Rule changes\nReal.\n"),
                         [(2, "## Rule changes"), (3, "Real.")])
        self.assertEqual(prepare.declared_rule_changes("   ## Rule changes\nReal.\n"),
                         [(1, "   ## Rule changes"), (2, "Real.")])
        body = "Write `<!--` to open a comment.\n## Rule changes\nReal declaration.\n"
        self.assertEqual(prepare.declared_rule_changes(body),
                         [(2, "## Rule changes"), (3, "Real declaration.")])
        body = "```html\n<!--\n```\n## Rule changes\nReal declaration.\n"
        self.assertEqual(prepare.declared_rule_changes(body),
                         [(4, "## Rule changes"), (5, "Real declaration.")])

    def test_summary_declarations(self):
        base = self.snapshot({"rules/source.md": "# Scope\n"})
        self.snapshot({"rules/source.md": "# Scope\nAlways retain records.\n"})
        summary = self.root / "summary.md"
        summary.write_text("Local review\n## Rule changes\nAdd a retention rule.\n### Detail\nKeep evidence.\n## Tests\nNot a declaration.\n")
        for context_only in (True, False):
            with self.subTest(context_only=context_only):
                args = ["review", str(self.repo), "--base", base, "--no-fetch", "--summary", str(summary)]
                if context_only:
                    args.append("--context-only")
                else:
                    self.github(self.pr("An automatically discovered PR without declarations."))
                status, out, err = self.invoke(*args)
                self.assertEqual(status, 0, err)
                report = out.split("## Rule text changes", 1)[1].split("# 4. Requirements", 1)[0]
                self.assertNotIn("UNDECLARED", report)
                self.assertIn("Declared changes (--summary text line numbers)", report)
                self.assertIn("2: ## Rule changes\n3: Add a retention rule.\n4: ### Detail\n5: Keep evidence.", report)
                self.assertNotIn("Not a declaration.", report)
        status, out, err = self.context(self.git(self.repo, "rev-parse", "HEAD"), summary=summary)
        self.assertEqual(status, 0, err)
        self.assertIn("Declared changes (--summary text line numbers)", out)
        self.assertIn("3: Add a retention rule.", out)
        summary.write_text("Review without declarations.\n")
        self.assertIn("UNDECLARED RULE CHANGES: --summary text", self.report(base, summary=summary))

    def test_pr_declarations_override_summary(self):
        base = self.snapshot({"rules/source.md": "# Scope\n"})
        self.snapshot({"rules/source.md": "# Scope\nAlways retain records.\n"})
        summary = self.root / "summary.md"
        summary.write_text("## Rule changes\nSummary declaration must not be selected.\n")
        for body in ("Intro\n## Rule changes\nPR declaration.\n", "No declaration."):
            with self.subTest(body=body):
                self.github(self.pr(body))
                report = self.report(base, pr=1, summary=summary)
                self.assertIn("Declared changes (PR description line numbers)", report)
                self.assertNotIn("Summary declaration", report)
                if "## Rule changes" in body:
                    self.assertIn("3: PR declaration.", report)
                    self.assertNotIn("UNDECLARED", report)
                else:
                    self.assertIn("UNDECLARED RULE CHANGES: PR description", report)

    def test_provenance_does_not_pair_with_rules(self):
        rule = "Keep the audit record."
        for number, entry in enumerate((rule, 'Approved removal: “' + rule + '”')):
            with self.subTest(entry=entry):
                source = f"# Scope {number}\n"
                base = self.snapshot({"rules/source.md": source + "- " + rule + "\n",
                                      "CHANGELOG-RULES.md": "# Approval\n"})
                self.snapshot({"rules/source.md": source, "CHANGELOG-RULES.md": "# Approval\n" + entry + "\n"})
                report = self.report(base)
                self.assertIn("removed: 1; added: 0; changed: 0; moved: 0", report)
                self.assertIn("Provenance entries: 1", report)
                rules, provenance = report.split("### Provenance entries", 1)
                self.assertIn('Old: "rules/source.md":2', rules)
                self.assertIn('New: "CHANGELOG-RULES.md":2', provenance)
                self.assertIn(entry, provenance)
                # A provenance removal must never become a rule's old side either.
                base = self.git(self.repo, "rev-parse", "HEAD")
                self.snapshot({"rules/source.md": source + "- " + rule + "\n", "CHANGELOG-RULES.md": "# Approval\n"})
                report = self.report(base)
                self.assertIn("removed: 0; added: 1; changed: 0; moved: 0", report)
                self.assertIn("Provenance entries: 1", report)

    def test_configured_provenance(self):
        policy = dict(version=1, extra_provenance_paths=["history/**/*.md", "docs/history.md"])
        base = self.snapshot({".rule-changes.json": json.dumps(policy),
                              "history/approval.md": "# Approval\n- Never skip validation.\n- Retain evidence.\n",
                              "history/archive.md": "# Archive\n", "docs/history.md": "# Ignored\n"})
        self.snapshot({".rule-changes.json": json.dumps(dict(version=1)),
                       "history/approval.md": "# Approval\n- Avoid skipping validation.\n- Retain evidence.\n",
                       "docs/history.md": "# Ignored\nIgnored provenance.\n"})
        report = self.report(base)
        self.assertIn("removed: 0; added: 0; changed: 0; moved: 0", report)
        self.assertIn("Provenance entries: 2", report)
        self.assertNotIn("Retain evidence.", report)
        self.assertNotIn("Ignored provenance.", report)
        self.assertEqual(self.invoke("rule-lenses", str(self.repo), "--base", base, "--no-fetch")[:2],
                         (0, "rule-preservation\n"))
        # Exact provenance copies at different locations are separate entries, not moves.
        self.snapshot({"history/approval.md": "# Approval\n- Retain evidence.\n",
                       "history/archive.md": "# Archive\n- Never skip validation.\n"})
        report = self.report(base)
        self.assertIn("removed: 0; added: 0; changed: 0; moved: 0", report)
        self.assertIn("Provenance entries: 2", report)
        # Both complete text and all provenance locations obey the existing size guard.
        policy["max_report_chars"] = 128
        base = self.snapshot({".rule-changes.json": json.dumps(policy)})
        self.snapshot({"history/archive.md": "# Archive\n"})
        status, out, err = self.context(base)
        self.assertEqual(status, 1, err)
        self.assertIn("FAILED CLOSED", out)
        self.assertIn('RC1 provenance removed: old "history/archive.md":2', out)

    def test_quotations_preserve_exact_block_and_location(self):
        for opening, closing in (('"', '"'), ("'", "'"), ('“', '”'), ('‘', '’')):
            with self.subTest(opening=opening):
                text = "The operator said " + opening + "Don't drop records.\nNever skip validation!" + closing + ".\n"
                base = self.snapshot({"rules/source.md": "# Scope\n" + text + "Report every failure.\n"})
                head = self.snapshot({"rules/source.md": "# Scope\n"})
                changes, _, _ = prepare.rule_changes(self.repo, base, head)
                self.assertEqual(len(changes), 1)
                self.assertEqual(changes[0]["kind"], "removed")
                self.assertEqual(changes[0]["old"]["text"], text + "Report every failure.\n")
                self.assertEqual(changes[0]["old"]["line"], 2)

    def test_declaration_closing_fence_requires_delimiter_only(self):
        for delimiter in ("`", "~"):
            with self.subTest(delimiter=delimiter):
                fence = delimiter * 4
                body = (f"{fence}markdown\n{delimiter * 3}\n## Rule changes\nFake short closure.\n"
                        f"{fence}example\n## Rule changes\nFake trailing text.\n"
                        f" {delimiter * 5}\t\n## Rule changes\nReal declaration.\n")
                self.assertEqual(prepare.declared_rule_changes(body),
                                 [(9, "## Rule changes"), (10, "Real declaration.")])

    def test_allowance_includes_unchanged_report_declarations(self):
        with self.assertRaises(prepare.RuleReportTooLarge) as error:
            prepare.rule_report([], {"max_report_chars": 200}, "base", "head",
                                "## Rule changes\n" + "declaration " * 100, "--summary text")
        self.assertIn("exceeds 200 characters", error.exception.report)

    def test_oversize(self):
        policy = json.dumps(dict(version=1, max_report_chars=1200))
        paths = [f"rules/item-{n:02}.md" for n in range(12)]
        base = self.snapshot({".rule-changes.json": policy, **{path: "# Scope\n" for path in paths}})
        self.snapshot({path: f"# Scope\n- Required action {n}.\n" for n, path in enumerate(paths)})
        status, out, err = self.context(base)
        self.assertEqual(status, 1, err)
        self.assertIn("FAILED CLOSED", out)
        self.assertIn("added: 12;", out)
        for item, path in enumerate(paths, 1):
            self.assertIn(f'RC{item} added: old (none); new "{path}":2', out)
        self.assertNotIn("# 5. Change", out)

    def test_fenced_bytes_and_literal_paths(self):
        paths = ('rules/a[1].md', 'rules/line\nname.md', 'rules/carriage\rname.md')
        before = '```text\nkeep\r\nvalue\vexact\n```\n'
        after = '```text\nkeep\r\nvalue\v exact\n```\n'
        base = self.snapshot({path: before for path in paths})
        head = self.snapshot({path: after for path in paths})
        changes, _, _ = prepare.rule_changes(self.repo, base, head)
        self.assertEqual(len(changes), len(paths))
        for item in changes:
            self.assertEqual(item["kind"], "changed")
            self.assertEqual(item["old"]["text"], "value\vexact\n")
            self.assertEqual(item["new"]["text"], "value\v exact\n")
            self.assertEqual(item["old"]["line"], 3)

    def test_invalid_inputs(self):
        for policy in ({"version": 2}, {"version": 1, "extra_protected_paths": ["../outside.md"]},
                       {"version": 1, "extra_protected_paths": "rules.md"},
                       {"version": 1, "extra_provenance_paths": "history.md"},
                       {"version": 1, "extra_provenance_paths": ["../outside.md"]},
                       {"version": 1, "max_report_chars": 0}, {"version": 1, "unexpected": 1}):
            with self.subTest(policy=policy):
                base = self.snapshot({".rule-changes.json": json.dumps(policy)})
                self.assertEqual(self.context(base)[0], 1)
        base = self.snapshot({".rule-changes.json": '{"version":1}', "rules/source.md": "# Scope\n"})
        (self.repo / "rules/source.md").write_bytes(b"\xff")
        self.commit(self.repo, "Invalid encoding")
        status, _, err = self.context(base)
        self.assertEqual(status, 1)
        self.assertIn("not UTF-8", err)
        (self.repo / "rules/source.md").unlink()
        (self.repo / "rules/source.md").symlink_to("../src/core.py")
        self.commit(self.repo, "Nonregular rule")
        status, _, err = self.context(base)
        self.assertEqual(status, 1)
        self.assertIn("not a regular file", err)

    def test_selector(self):
        base = self.snapshot({"rules/source.md": "# Scope\nNever skip validation.\n"})
        self.snapshot({"rules/source.md": "# Scope\nAvoid skipping validation.\n"})
        status, out, err = self.invoke("rule-lenses", str(self.repo), "--base", base, "--no-fetch")
        self.assertEqual(status, 0, err)
        self.assertEqual(out, "rule-preservation\n")
        base = self.git(self.repo, "rev-parse", "HEAD")
        self.snapshot({"rules/source.md": "# Scope\nAvoid skipping validation.\nNew rule.\n"})
        self.assertEqual(self.invoke("rule-lenses", str(self.repo), "--base", base, "--no-fetch")[:2],
                         (0, "rule-preservation\n"))
        base = self.git(self.repo, 'rev-parse', 'HEAD')
        self.assertEqual(self.invoke('rule-lenses', str(self.repo), '--base', base, '--no-fetch')[:2], (0, ''))
        self.snapshot({'rules/source.md': '# Scope\n'})
        self.assertEqual(self.invoke('rule-lenses', str(self.repo), '--base', base, '--no-fetch')[:2],
                         (0, 'rule-preservation\n'))
        base = self.snapshot({'rules/source.md': '# Scope\n- Keep all records.\n'})
        self.snapshot({'rules/source.md': '# Scope\n', 'rules/destination.md': '# Archive\n- Keep all records.\n'})
        self.assertEqual(self.invoke('rule-lenses', str(self.repo), '--base', base, '--no-fetch')[:2],
                         (0, 'rule-preservation\n'))

    def test_rewrapped_only_range_selects_the_lens(self):
        base = self.snapshot({"rules/source.md": "Retain every source and\nreport every failure.\n"})
        self.snapshot({"rules/source.md": "Retain every source\nand report every failure.\n"})
        self.assertEqual(self.invoke("rule-lenses", str(self.repo), "--base", base, "--no-fetch")[:2],
                         (0, "rule-preservation\n"))
        report = self.report(base)
        self.assertIn("moved: 0; rewrapped: 1", report)
        self.assertIn("same words, line breaks moved", report)
        base = self.git(self.repo, "rev-parse", "HEAD")
        self.snapshot({"rules/source.md": "Retain every source\nand report selected failures.\n"})
        self.assertEqual(self.invoke("rule-lenses", str(self.repo), "--base", base, "--no-fetch")[:2],
                         (0, "rule-preservation\n"))

    def test_panel_keeps_base_selected_before_lens_selection(self):
        base = self.snapshot({'rules/source.md': '# Scope\n- Never skip validation.\n'})
        head = self.snapshot({'rules/source.md': '# Scope\n- Avoid skipping validation.\n'})
        self.git(self.repo, 'branch', 'comparison', base)
        summary, output, env = self.panel_fixture()
        Path(env['REVIEW_PANEL_CONF']).write_text('a = codex test-model - high\nb = codex test-model - high\n')
        stub = self.binaries / 'codex'
        stub.write_text('#!' + sys.executable + '\nimport pathlib,sys\n'
                        'sys.stdin.buffer.read()\n'
                        'pathlib.Path(sys.argv[sys.argv.index("-o")+1]).write_text("VERDICT: APPROVE")\n')
        stub.chmod(0o755)
        real_git = shutil.which('git')
        marker = self.root / 'base-moved'
        wrapper = self.binaries / 'git'
        wrapper.write_text('#!' + sys.executable + '\nimport os,pathlib,subprocess,sys\n'
                           'args=sys.argv[1:]\n'
                           f'marker=pathlib.Path({str(marker)!r})\n'
                           'if "diff" in args and ("--raw" in args or "--name-only" in args) and not marker.exists():\n'
                           f'    result=subprocess.run([{real_git!r}, *args], capture_output=True)\n'
                           f'    subprocess.run([{real_git!r}, "-C", {str(self.repo)!r}, "update-ref", '
                           f'"refs/heads/comparison", {head!r}], check=True)\n'
                           '    marker.touch()\n'
                           '    sys.stdout.buffer.write(result.stdout)\n'
                           '    sys.stderr.buffer.write(result.stderr)\n'
                           '    sys.exit(result.returncode)\n'
                           f'os.execv({real_git!r}, [{real_git!r}, *args])\n')
        wrapper.chmod(0o755)
        env['REVIEW_BASE'] = 'comparison'
        result = subprocess.run(['bash', str(SCRIPT.with_name('review-panel.sh')), 'moving-base',
                                 str(self.repo), str(summary), 'generalist-a'], env=env,
                                capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(marker.exists())
        for lens in ('generalist-a', 'rule-preservation'):
            pack = (output / 'moving-base' / (lens + '.pack/pack.txt')).read_text()
            self.assertIn(f'Base: `{base}`;', pack)
            self.assertIn('changed: 1;', pack)
            self.assertIn('Never skip validation.', pack)

    def test_base_command_resolves_reference_once_and_returns_commit(self):
        base = self.git(self.repo, 'rev-parse', 'HEAD')
        self.git(self.repo, 'branch', 'comparison', base)
        with mock.patch.object(prepare, 'git', wraps=prepare.git) as calls:
            status, out, err = self.invoke('base', str(self.repo), '--base', 'comparison', '--no-fetch')
        self.assertEqual(status, 0, err)
        self.assertEqual(out, base + '\n')
        self.assertEqual(sum('comparison^{commit}' in call.args for call in calls.call_args_list), 1)

    def test_panel_adds_lens(self):
        base = self.snapshot({"rules/source.md": "# Scope\nNever skip validation.\n"})
        self.snapshot({"rules/source.md": "# Scope\nAvoid skipping validation.\n"})
        summary, output, env = self.panel_fixture()
        # Both configured families use a local byte-recording reviewer, never a model.
        conf = Path(env["REVIEW_PANEL_CONF"])
        conf.write_text("a = codex test-model - high\nb = codex test-model - high\n")
        stub = self.binaries / "codex"
        stub.write_text("#!" + sys.executable + "\nimport pathlib,sys\nargs=sys.argv[1:]\n"
                        "data=sys.stdin.buffer.read()\n"
                        "pathlib.Path(args[args.index('-o')+1]).write_text('VERDICT: APPROVE')\n")
        stub.chmod(0o755)
        env["REVIEW_BASE"] = base
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "rule-audit",
                                 str(self.repo), str(summary), "generalist-a"], env=env,
                                text=True, capture_output=True, timeout=15, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("generalist-a", "rule-preservation"):
            path = output / "rule-audit" / (name + ".pack/pack.txt")
            self.assertTrue(path.exists(), name + " was not dispatched")
            pack = path.read_text()
            self.assertIn("Never skip validation.", pack)
            self.assertIn("Avoid skipping validation.", pack)
            self.assertIn("Rule text changes", pack)
            self.assertIn("missing disposition", pack)
        audit = (output / "rule-audit/rule-preservation.pack/pack.txt").read_text()
        self.assertIn("actor, condition, action, strength", audit)

    def test_python39(self):
        copied = self.root / "standalone/prepare.py"
        copied.parent.mkdir()
        shutil.copyfile(SCRIPT, copied)
        base = self.snapshot({"rules/source.md": "# Scope\nNever skip validation.\n"})
        self.snapshot({"rules/source.md": "# Scope\nAvoid skipping validation.\n"})
        result = subprocess.run(["/usr/bin/python3", "-I", "-B", str(copied), "review", str(self.repo),
                                 "--base", base, "--context-only", "--no-fetch"], capture_output=True,
                                text=True, timeout=5, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("changed: 1;", result.stdout)
        self.assertIn("Never skip validation.", result.stdout)
        self.assertIn("Avoid skipping validation.", result.stdout)
        self.assertEqual(list(copied.parent.iterdir()), [copied])

    def test_no_sibling_imports(self):
        tree = ast.parse(SCRIPT.read_text(), feature_version=(3, 9))
        standard = Path(sysconfig.get_path("stdlib")).resolve()
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                modules = [node.module.split('.')[0]]
            for name in modules:
                spec = importlib.util.find_spec(name)
                self.assertIsNotNone(spec, name)
                if spec.origin not in ("built-in", "frozen"):
                    origin = Path(spec.origin).resolve()
                    self.assertTrue(origin.is_relative_to(standard), name)
                    self.assertNotIn("site-packages", origin.parts, name)



if __name__ == "__main__":
    unittest.main()
