#!/usr/bin/env python3
"""Exercise the watcher command against a fake gh executable; never use the network."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import watch_prs


SCRIPT = Path(__file__).with_name("watch_prs.py")
REPO = "example/project"
PR = f"{REPO}#7"


def pr(**changes):
    value = {"state": "OPEN", "headRefOid": "a" * 40, "mergeable": "MERGEABLE",
             "statusCheckRollup": [{"name": "rust", "status": "IN_PROGRESS", "conclusion": ""}]}
    value.update(changes)
    return value


def comment(body, login="review-bot[bot]"):
    return {"user": {"login": login}, "body": body}


class ProgressFilterTest(unittest.TestCase):
    def test_only_running_review_and_check_transitions_are_progress(self):
        # Expected behavior comes from the task's six required cases.
        cases = [
            ({"review": ["**State: reviewing**", "**State: triaging**"]}, True),
            ({"review": ["**State: triaging**", "**State: changes requested**"]}, False),
            ({"checks": [["rust=SUCCESS"], ["rust=IN_PROGRESS"]]}, True),
            ({"checks": [["rust=IN_PROGRESS"], ["rust=SUCCESS"]]}, False),
            ({"head": ["old", "new"], "checks": [[], ["rust=IN_PROGRESS"]]}, False),
            ({"mergeable": ["MERGEABLE", "CONFLICTING"]}, False),
            ({"checks": [["rust=SUCCESS"], []]}, False),
        ]
        for diff, expected in cases:
            with self.subTest(diff=diff):
                self.assertEqual(watch_prs.progress_only(diff), expected)

    def test_only_explicit_owner_repository_and_positive_number_are_accepted(self):
        for reference, expected in [
            ("example/project#7", ("example/project", 7)),
            ("other-owner/project.name_2#123", ("other-owner/project.name_2", 123)),
        ]:
            with self.subTest(reference=reference):
                self.assertEqual(watch_prs.parse_pr(reference), expected)
        for reference in ["project#7", "7", "example/project", "example/project#",
                          "/project#7", "example/#7", "example/project#0",
                          "example/project#-1", "example/project#1.2", "example/project#1#2",
                          "example/project#01", "example/project#x", "example/../project#7",
                          "example/..#7", "https://example/project#7", " example/project#7"]:
            with self.subTest(reference=reference):
                with self.assertRaisesRegex(argparse.ArgumentTypeError, "owner/repo#number"):
                    watch_prs.parse_pr(reference)


class WatchCommandTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "registry"
        self.scenario = self.root / "scenario.json"
        self.counts = self.root / "counts.json"
        self.trace = self.root / "trace.jsonl"
        self.env = dict(os.environ, AUTONOMY_HOME=str(self.home),
                        WATCH_TEST_ROOT=str(self.root),
                        PATH=str(self.root) + os.pathsep + os.environ.get("PATH", ""))
        fake = self.root / "gh"
        fake.write_text(f"#!{sys.executable}\n" + '''
import json
import os
from pathlib import Path
import sys

root = Path(os.environ["WATCH_TEST_ROOT"])
args = sys.argv[1:]
with (root / "trace.jsonl").open("a") as trace:
    trace.write(json.dumps(args) + "\\n")
scenarios = json.loads((root / "scenario.json").read_text())
counts_file = root / "counts.json"
counts = json.loads(counts_file.read_text()) if counts_file.exists() else {}
if args[:2] == ["pr", "view"]:
    repo = args[args.index("-R") + 1]
    index = counts.get(repo, 0)
    counts[repo] = index + 1
    counts_file.write_text(json.dumps(counts))
elif args[0] == "api":
    repo = "/".join(args[1].split("/")[1:3])
    index = counts[repo] - 1
else:
    sys.exit("unexpected gh arguments: " + repr(args))
sequence = scenarios[repo]
entry = sequence[min(index, len(sequence) - 1)]
if "error" in entry:
    print(entry["error"], file=sys.stderr)
    sys.exit(1)
if args[0] == "api":
    if "--paginate" not in args or "--slurp" not in args:
        sys.exit("comment pages must not be truncated")
    print(json.dumps(entry.get("pages", [])))
else:
    print(json.dumps(entry["pr"]))
''')
        fake.chmod(0o755)

    def command(self, *arguments):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *arguments],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            env=self.env, timeout=10,
        )

    def watch(self, entries, *arguments, others=None):
        self.scenario.write_text(json.dumps({REPO: entries, **(others or {})}))
        return self.command("run", "--session", "test-session", "--pr", PR,
                            "--interval", "0.001", "--heartbeat", "2", *arguments)

    def assert_change(self, result, diff):
        self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
        self.assertEqual(result.stdout, f"{PR} changed: {json.dumps(diff)}\n")
        self.assertEqual(list((self.home / "watchers").glob("*.json")), [])

    def test_running_checks_are_ignored_until_a_finished_result(self):
        success = pr(statusCheckRollup=[{"name": "rust", "conclusion": "SUCCESS"}])
        failure = pr(statusCheckRollup=[{"name": "rust", "conclusion": "FAILURE"}])
        result = self.watch([{"pr": success}, {"pr": pr()}, {"pr": failure}])
        self.assert_change(result, {"checks": [["rust=IN_PROGRESS"], ["rust=FAILURE"]]})

    def test_each_finished_check_wakes_the_session(self):
        for conclusion in ("SUCCESS", "FAILURE", "CANCELLED", "NEUTRAL", "TIMED_OUT", "SKIPPED"):
            with self.subTest(conclusion=conclusion):
                self.counts.unlink(missing_ok=True)
                result = self.watch([
                    {"pr": pr()},
                    {"pr": pr(statusCheckRollup=[{"name": "rust", "conclusion": conclusion}])},
                ])
                self.assert_change(result, {"checks": [["rust=IN_PROGRESS"], [f"rust={conclusion}"]]})

    def test_head_merge_and_conflict_changes_wake_the_session(self):
        # The head differs after the first seven characters, which must not hide it.
        for field, old, new in [("headRefOid", "a" * 40, "a" * 39 + "b"),
                                ("state", "OPEN", "MERGED"),
                                ("mergeable", "MERGEABLE", "CONFLICTING")]:
            with self.subTest(field=field):
                self.counts.unlink(missing_ok=True)
                result = self.watch([{"pr": pr()}, {"pr": pr(**{field: new})}])
                self.assert_change(result, {"head" if field == "headRefOid" else field: [old, new]})

    def test_review_progress_is_ignored_until_result_on_a_later_comment_page(self):
        reviewing = "**State: reviewing**"
        triaging = "**State: triaging**"
        result_body = "**State: changes requested**\n" + "detail " * 100
        entries = [{"pr": pr(), "pages": [[comment(body, "someone-else")], [comment(body)]]}
                   for body in (reviewing, triaging, result_body)]
        self.assert_change(self.watch(entries, "--bot-login", "review-bot[bot]"),
                           {"review": [triaging, result_body]})

    def test_all_reports_progress_changes(self):
        bodies = ["**State: reviewing**", "**State: triaging**"]
        entries = [{"pr": pr(), "pages": [[comment(body)]]} for body in bodies]
        self.assert_change(self.watch(entries, "--all", "--bot-login", "review-bot[bot]"),
                           {"review": bodies})

    def test_no_bot_option_reads_only_pull_request_status(self):
        result = self.watch([{"pr": pr()}, {"pr": pr(state="MERGED")}])
        self.assert_change(result, {"state": ["OPEN", "MERGED"]})
        calls = [json.loads(line) for line in self.trace.read_text().splitlines()]
        self.assertEqual([call[:2] for call in calls], [["pr", "view"], ["pr", "view"]])

    def test_heartbeat_reports_current_state_without_waiting_for_poll_interval(self):
        self.scenario.write_text(json.dumps({REPO: [{"pr": pr()}]}))
        result = self.command("run", "--session", "heartbeat", "--pr", PR,
                              "--heartbeat", "0.01", "--interval", "90")
        expected = {"state": "OPEN", "head": "a" * 40,
                    "mergeable": "MERGEABLE", "checks": ["rust=IN_PROGRESS"]}
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout, "heartbeat: no result change in 0.01 s. Current state:\n"
                         f"  {PR}: {json.dumps(expected)}\n")
        self.assertEqual(list((self.home / "watchers").glob("*.json")), [])

    def test_three_failed_reads_exit_two_and_report_each_failure(self):
        result = self.watch([{"error": "synthetic read failure"}])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.splitlines(), [
            f"{PR}: read failed (synthetic read failure); attempt {number}" for number in (1, 2, 3)
        ])
        self.assertEqual(result.stdout, "watch_prs.py: stopped after 3 failed reads in a row "
                         f"({PR}: synthetic read failure)\n")
        self.assertEqual(json.loads(self.counts.read_text()), {REPO: 3})
        self.assertEqual(list((self.home / "watchers").glob("*.json")), [])

    def test_a_successful_read_resets_consecutive_failures(self):
        failure = {"error": "synthetic read failure"}
        result = self.watch([failure, failure, {"pr": pr()}, failure, failure, failure])
        self.assertEqual(result.returncode, 2)
        self.assertEqual([line.rsplit(" ", 1)[1] for line in result.stderr.splitlines()],
                         ["1", "2", "1", "2", "3"])
        self.assertEqual(json.loads(self.counts.read_text()), {REPO: 6})
        self.assertIn("stopped after 3 failed reads", result.stdout)

    def test_healthy_pull_request_does_not_hide_another_requests_failed_reads(self):
        result = self.watch([{"error": "synthetic read failure"}],
                            "--pr", "other/project#8", others={"other/project": [{"pr": pr()}]})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(self.counts.read_text()), {REPO: 3, "other/project": 2})
        self.assertIn(f"({PR}: synthetic read failure)", result.stdout)

    def test_invalid_references_fail_visibly_before_reading_or_registering(self):
        result = self.command("run", "--session", "invalid", "--pr", "project#7")
        self.assertEqual(result.returncode, 2)
        self.assertIn("expected owner/repo#number", result.stderr)
        self.assertFalse(self.trace.exists())
        self.assertFalse(self.home.exists())

    def test_open_done_and_status_use_the_overridden_registry(self):
        result = self.command("open", "--session", "session-a", "--note", "waiting for checks")
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "open work registered for session-a\n", ""))
        status = self.command("status")
        prefix, entry = status.stdout.strip().split(" ", 3)[:3], status.stdout.strip().split(" ", 3)[3]
        self.assertEqual((status.returncode, status.stderr, prefix), (0, "", ["open", "session:", "session-a"]))
        self.assertEqual(json.loads(entry), {"session": "session-a", "open": True,
                         "since": json.loads(entry)["since"], "note": "waiting for checks"})
        result = self.command("done", "--session", "session-a")
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "no open work registered for session-a\n", ""))
        status = self.command("status")
        self.assertEqual((status.returncode, status.stdout, status.stderr),
                         (0, "no registered open sessions or watchers\n", ""))


if __name__ == "__main__":
    unittest.main()
