#!/usr/bin/env python3
"""Exercise the watcher command against a fake gh executable; never use the network."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import watch_prs


SCRIPT = Path(__file__).with_name("watch_prs.py")
REPO = "example/project"
PR = f"{REPO}#7"


def pr(**changes):
    value = {"state": "OPEN", "headRefOid": "a" * 40, "mergeable": "MERGEABLE",
             "statusCheckRollup": [{"name": "rust", "status": "IN_PROGRESS", "conclusion": ""}],
             "reviews": []}
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
import time
import select
import re

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
elif args[:2] == ["api", "graphql"]:
    fields = dict(arg.split("=", 1) for arg in args if "=" in arg)
    repo = fields["owner"] + "/" + fields["name"]
    index = counts[repo] - 1
elif args[0] == "api":
    repo = "/".join(args[1].split("/")[1:3])
    index = counts[repo] - 1
else:
    sys.exit("unexpected gh arguments: " + repr(args))
sequence = scenarios[repo]
entry = sequence[min(index, len(sequence) - 1)]
if entry.get("wait_for_baseline"):
    with (root / "release").open() as release:
        if not select.select([release], [], [], 2)[0]:
            sys.exit("baseline was not flushed")
        release.readline()
time.sleep(entry.get("comment_delay" if args[0] == "api" else "delay", 0))
if "error" in entry:
    print(entry["error"], file=sys.stderr)
    sys.exit(1)
if args[:2] == ["api", "graphql"]:
    if not re.search(r"\\blast\\s*:\\s*100\\b", fields["query"]):
        sys.exit("expected native reverse comment pagination")
    pages = entry.get("pages", []) or [[]]
    page = int(fields["before"]) - 1 if "before" in fields else len(pages) - 1
    with (root / "pages-read.jsonl").open("a") as trace:
        trace.write(json.dumps(page) + "\\n")
    print(json.dumps({"data": {"repository": {"pullRequest": {"comments": {
        "nodes": [{"author": c["user"], "body": c["body"]} for c in pages[page]],
        "pageInfo": {"hasPreviousPage": page > 0, "startCursor": str(page)},
    }}}}}))
elif args[0] == "api":
    with (root / "pages-read.jsonl").open("a") as trace:
        for page in range(len(entry.get("pages", []))):
            trace.write(json.dumps(page) + "\\n")
    if "--paginate" not in args or "--slurp" not in args:
        sys.exit("comment pages must not be truncated")
    print(json.dumps(entry.get("pages", [])))
else:
    fields = args[args.index("--json") + 1].split(",")
    print(json.dumps({field: entry["pr"][field] for field in fields}))
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
        lines = result.stdout.splitlines()
        self.assertEqual(lines[-1], f"{PR} changed: {json.dumps(diff)}")
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith(f"baseline recorded: {PR}: "))
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
                              "--heartbeat", "0.2", "--interval", "90")
        expected = {"state": "OPEN", "head": "a" * 40,
                    "mergeable": "MERGEABLE", "checks": ["rust=IN_PROGRESS"], "reviews": []}
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout, f"baseline recorded: {PR}: {json.dumps(expected)}\n"
                         "heartbeat: no result change in 0.2 s. Current state:\n"
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

    def test_submitted_reviews_wake_the_session(self):
        for state in ("APPROVED", "CHANGES_REQUESTED"):
            with self.subTest(state=state):
                self.counts.unlink(missing_ok=True)
                review = {"id": "review-1", "state": state,
                          "submittedAt": "2026-10-21T12:00:00Z"}
                self.assert_change(self.watch([
                    {"pr": pr()}, {"pr": pr(reviews=[review])},
                ]), {"reviews": [[], [review]]})

    def test_removed_failure_wakes_even_when_another_check_starts(self):
        before = pr(statusCheckRollup=[{"name": "lint", "conclusion": "FAILURE"},
                                      {"name": "unit", "status": "QUEUED"}])
        after = pr(statusCheckRollup=[{"name": "unit", "status": "IN_PROGRESS"}])
        self.assert_change(self.watch([{"pr": before}, {"pr": after}]),
                           {"checks": [["lint=FAILURE", "unit=QUEUED"], ["unit=IN_PROGRESS"]]})

    def test_newest_matching_bot_comment_stops_history_reads(self):
        pages = [[comment("old", "someone-else")] * 100 for _ in range(3)]
        pages.append([comment("**State: approved**")])
        result = self.watch([{"pr": pr(), "pages": pages}],
                            "--bot-login", "review-bot[bot]", "--heartbeat", "0.3",
                            "--interval", "90")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertIn('"review": "**State: approved**"', result.stdout)
        self.assertEqual((self.root / "pages-read.jsonl").read_text().splitlines(), ["3"])

    def test_bot_lookup_searches_older_pages_and_handles_absent_authors(self):
        # Newest matching body wins; deleted authors do not abort the search.
        pages = [[comment("**State: approved**"), comment("**State: changes requested**")],
                 [{"user": None, "body": "deleted author"}]]
        result = self.watch([{"pr": pr(), "pages": pages}],
                            "--bot-login", "review-bot[bot]", "--heartbeat", "0.3",
                            "--interval", "90")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertIn('"review": "**State: changes requested**"', result.stdout)
        self.assertEqual((self.root / "pages-read.jsonl").read_text().splitlines(), ["1", "0"])

    def test_heartbeat_bounds_slow_reads_and_stops_before_the_next_request(self):
        for delay, comment_delay, bot in ((1, 0, []),
                                          (0.1, 1, ["--bot-login", "review-bot[bot]"])):
            with self.subTest(delay=delay, comment_delay=comment_delay):
                self.counts.unlink(missing_ok=True)
                self.trace.unlink(missing_ok=True)
                start = time.monotonic()
                self.scenario.write_text(json.dumps({
                    REPO: [{"pr": pr(), "delay": delay, "comment_delay": comment_delay}],
                    "other/project": [{"pr": pr()}],
                }))
                wrapper = r'''import json, os, runpy, subprocess, sys
from pathlib import Path
original = subprocess.run
def read(*args, **kwargs):
    with (Path(os.environ["WATCH_TEST_ROOT"]) / "timeouts.jsonl").open("a") as output:
        output.write(json.dumps(kwargs["timeout"]) + "\n")
    return original(*args, **kwargs)
subprocess.run = read
runpy.run_path(sys.argv.pop(1), run_name="__main__")
'''
                timeouts_file = self.root / "timeouts.jsonl"
                timeouts_file.unlink(missing_ok=True)
                result = subprocess.run([sys.executable, "-B", "-c", wrapper, str(SCRIPT),
                                         "run", "--session", "slow", "--pr", PR,
                                         "--pr", "other/project#8", *bot, "--heartbeat", "0.3"],
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True, env=self.env, timeout=5)
                elapsed = time.monotonic() - start
                self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
                self.assertIn("heartbeat: no result change in 0.3 s.", result.stdout)
                self.assertLess(elapsed, 0.9, "read timeouts must share the heartbeat budget")
                self.assertEqual(json.loads(self.counts.read_text()), {REPO: 1})
                timeouts = [json.loads(line) for line in timeouts_file.read_text().splitlines()]
                self.assertLessEqual(timeouts[0], 0.3)
                if bot:
                    self.assertEqual(len(timeouts), 2)
                    self.assertLess(timeouts[1], timeouts[0] - 0.1)
                self.assertEqual(list((self.home / "watchers").glob("*.json")), [])

    def test_baseline_is_flushed_before_the_next_read(self):
        self.scenario.write_text(json.dumps({REPO: [
            {"pr": pr()}, {"pr": pr(state="MERGED"), "wait_for_baseline": True},
        ]}))
        # The fake's second response needs a signal sent only after the handshake.
        os.mkfifo(self.root / "release")
        process = subprocess.Popen([sys.executable, "-B", str(SCRIPT), "run", "--session", "handshake",
                                    "--pr", PR, "--interval", "0.001", "--heartbeat", "3"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        # Opening the FIFO read/write avoids blocking the parent before the baseline arrives.
        descriptor = os.open(self.root / "release", os.O_RDWR | os.O_NONBLOCK)
        self.addCleanup(os.close, descriptor)
        line = process.stdout.readline()
        os.write(descriptor, b"continue\n")
        output, error = process.communicate(timeout=5)
        expected = {"state": "OPEN", "head": "a" * 40, "mergeable": "MERGEABLE",
                    "checks": ["rust=IN_PROGRESS"], "reviews": []}
        self.assertEqual(line, f"baseline recorded: {PR}: {json.dumps(expected)}\n")
        self.assertEqual((process.returncode, error), (0, ""), output)
        self.assertEqual(output, f'{PR} changed: {{"state": ["OPEN", "MERGED"]}}\n')

    def test_registration_is_invisible_until_publication(self):
        self.scenario.write_text(json.dumps({REPO: [{"pr": pr()}]}))
        # Pause the real filesystem writer after opening its file, before any content.
        wrapper = r'''import io, os, runpy, sys
from pathlib import Path
original = io.open
def pause(file, mode="r", *args, **kwargs):
    stream = original(file, mode, *args, **kwargs)
    if (isinstance(file, (str, os.PathLike)) and "w" in mode
            and {Path(file).parent.name, Path(file).name} & {"sessions", "watchers"}):
        print("write paused", flush=True)
        sys.stdin.readline()
    return stream
io.open = pause
runpy.run_path(sys.argv.pop(1), run_name="__main__")
'''
        for arguments in (("open", "--session", "atomic"),
                          ("run", "--session", "atomic", "--pr", PR, "--heartbeat", "0.2")):
            with self.subTest(command=arguments[0]):
                process = subprocess.Popen([sys.executable, "-B", "-c", wrapper, str(SCRIPT), *arguments],
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True, env=self.env)
                self.addCleanup(lambda p=process: p.poll() is None and p.kill())
                self.assertEqual(process.stdout.readline(), "write paused\n")
                during = self.command("status")
                output, error = process.communicate("continue\n", timeout=5)
                self.assertEqual((during.returncode, during.stdout, during.stderr),
                                 (0, "no registered open sessions or watchers\n", ""))
                self.assertEqual((process.returncode, error), (0, ""), output)
                if arguments[0] == "open":
                    published = self.command("status")
                    entry = json.loads(published.stdout.split(" ", 3)[3])
                    self.assertEqual((published.returncode, published.stderr, entry),
                                     (0, "", {"session": "atomic", "open": True,
                                              "since": entry["since"], "note": ""}))
                    self.command("done", "--session", "atomic")

    def test_status_skips_a_registration_removed_after_enumeration(self):
        for session in ("a", "b"):
            self.command("open", "--session", session)
        wrapper = r'''import runpy, sys
from pathlib import Path
original = Path.read_text
def removed(path, *args, **kwargs):
    if path.name == "a.json":
        path.unlink()
    return original(path, *args, **kwargs)
Path.read_text = removed
runpy.run_path(sys.argv.pop(1), run_name="__main__")
'''
        result = subprocess.run([sys.executable, "-B", "-c", wrapper, str(SCRIPT), "status"],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, env=self.env, timeout=5)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        raw = result.stdout.strip().split(" ", 3)[3]
        entry = json.loads(raw)
        self.assertEqual(result.stdout, f"open session: b {json.dumps(entry)}\n")
        self.assertEqual(entry, {"session": "b", "open": True, "since": entry["since"], "note": ""})

    def test_detached_run_refuses_orphan_and_session_leader(self):
        for orphan in (True, False):
            with self.subTest(orphan=orphan):
                change = "os.getppid = lambda: 1; " if orphan else ""
                wrapper = "import os, runpy, sys; " + change + "runpy.run_path(sys.argv.pop(1), run_name='__main__')"
                result = subprocess.run([sys.executable, "-B", "-c", wrapper, str(SCRIPT), "run",
                                         "--session", "detached", "--pr", PR, "--heartbeat", "0.2"],
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True, env=self.env, timeout=5,
                                        start_new_session=not orphan)
                self.assertEqual(result.returncode, 2)
                self.assertIn("attached harness background job", result.stderr)
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
