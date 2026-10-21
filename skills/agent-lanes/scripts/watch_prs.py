#!/usr/bin/env python3
"""Watch pull requests from an attached harness background job.

Exit 0 with a change report or heartbeat, or 2 after three consecutive failed
reads of a pull request. Re-arm the job after each wake. Requires the gh CLI.
Use open/done to register session work, and status to inspect the local registry.
AUTONOMY_HOME overrides the default registry at ~/.agent-lanes/watch.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


TRANSIENT_STATES = ("preparing", "reviewing", "triaging", "queued", "publishing")
TRANSIENT_CHECKS = {"IN_PROGRESS", "QUEUED", "PENDING", "EXPECTED", "WAITING"}


def gh(*args):
    result = subprocess.run(
        ["gh", *args], stdin=subprocess.DEVNULL, capture_output=True,
        text=True, timeout=60,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "gh failed").strip())
    return result.stdout


def parse_pr(text):
    """Accept only an explicit owner/repo#positive-number reference."""
    match = re.fullmatch(r"([A-Za-z0-9-]+/[A-Za-z0-9_.-]+)#([1-9][0-9]*)", text)
    if not match or match[1].split("/")[1] in {".", ".."}:
        raise argparse.ArgumentTypeError(
            f"invalid pull request {text!r}; expected owner/repo#number (number > 0)"
        )
    return match[1], int(match[2])


def snapshot(repo, number, bot_login=None):
    pr = json.loads(gh(
        "pr", "view", str(number), "-R", repo, "--json",
        "state,headRefOid,mergeable,statusCheckRollup",
    ))
    checks = sorted(
        f"{check.get('name') or check['context']}="
        f"{check.get('conclusion') or check.get('state') or check['status']}"
        for check in pr.get("statusCheckRollup") or []
    )
    result = {
        "state": pr["state"], "head": pr["headRefOid"],
        "mergeable": pr["mergeable"], "checks": checks,
    }
    if bot_login:
        pages = json.loads(gh(
            "api", f"repos/{repo}/issues/{number}/comments?per_page=100",
            "--paginate", "--slurp",
        ))
        comments = [comment for page in pages for comment in page
                    if comment["user"]["login"] == bot_login]
        result["review"] = comments[-1]["body"] if comments else ""
    return result


def progress_only(diff):
    """Return whether every change is a running review or check transition."""
    if set(diff) - {"review", "checks"}:
        return False
    if "review" in diff:
        state = re.search(r"^\s*\**State:\**\s*(\w+)", diff["review"][1], re.I | re.M)
        if not state or state[1].lower() not in TRANSIENT_STATES:
            return False
    if "checks" in diff:
        old, new = map(set, diff["checks"])
        # A vanished check is a status change, not evidence of ongoing progress.
        if not new - old or any(
            check.rsplit("=", 1)[-1] not in TRANSIENT_CHECKS for check in new - old
        ):
            return False
    return True


def live(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def run(args, home):
    watchers = home / "watchers"
    watchers.mkdir(parents=True, exist_ok=True)
    registration = watchers / f"{args.session}-{os.getpid()}.json"
    registration.write_text(json.dumps({
        "session": args.session, "pid": os.getpid(),
        "prs": [f"{repo}#{number}" for repo, number in args.pr],
        "started": time.time(),
    }))
    base, errors = {}, {}
    start = time.monotonic()
    try:
        while True:
            changes = []
            for repo, number in args.pr:
                key = f"{repo}#{number}"
                try:
                    current = snapshot(repo, number, args.bot_login)
                except (OSError, RuntimeError, ValueError, KeyError, TypeError,
                        subprocess.TimeoutExpired) as error:
                    errors[key] = errors.get(key, 0) + 1
                    print(f"{key}: read failed ({error}); attempt {errors[key]}",
                          file=sys.stderr, flush=True)
                    if errors[key] >= 3:
                        print(f"watch_prs.py: stopped after 3 failed reads in a row "
                              f"({key}: {error})", flush=True)
                        return 2
                    continue
                errors[key] = 0
                if key in base and current != base[key]:
                    diff = {field: [base[key][field], value]
                            for field, value in current.items() if value != base[key][field]}
                    if args.all or not progress_only(diff):
                        changes.append(f"{key} changed: {json.dumps(diff)}")
                base[key] = current
            if changes:
                print("\n".join(changes), flush=True)
                return 0
            remaining = args.heartbeat - (time.monotonic() - start)
            if remaining <= 0:
                print(f"heartbeat: no result change in {args.heartbeat:g} s. Current state:")
                for key, value in base.items():
                    print(f"  {key}: {json.dumps(value)}")
                return 0
            time.sleep(min(args.interval, remaining))
    finally:
        registration.unlink(missing_ok=True)


def mark(args, home, is_open):
    sessions = home / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    registration = sessions / f"{args.session}.json"
    if is_open:
        registration.write_text(json.dumps({
            "session": args.session, "open": True, "since": time.time(),
            "note": args.note or "",
        }))
        print(f"open work registered for {args.session}")
    else:
        registration.unlink(missing_ok=True)
        print(f"no open work registered for {args.session}")
    return 0


def status(home):
    found = False
    for directory, label in ((home / "sessions", "open session"),
                             (home / "watchers", "watcher")):
        for registration in sorted(directory.glob("*.json")):
            entry = json.loads(registration.read_text())
            alive = "" if "pid" not in entry else (" alive" if live(entry["pid"]) else " DEAD")
            print(f"{label}: {registration.stem}{alive} {json.dumps(entry)}")
            found = True
    if not found:
        print("no registered open sessions or watchers")
    return 0


def positive_seconds(text):
    value = float(text)
    if not 0 < value < float("inf"):
        raise argparse.ArgumentTypeError("expected a finite number of seconds > 0")
    return value


def session_id(text):
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", text):
        raise argparse.ArgumentTypeError("session must use letters, numbers, underscores, dots or hyphens")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    watch = commands.add_parser("run")
    watch.add_argument("--session", required=True, type=session_id)
    watch.add_argument("--pr", action="append", required=True, type=parse_pr)
    watch.add_argument("--bot-login", help="include the latest status comment by this author")
    watch.add_argument("--interval", type=positive_seconds, default=90)
    watch.add_argument("--heartbeat", type=positive_seconds, default=1800)
    watch.add_argument("--all", action="store_true", help="also wake on progress-only changes")
    for name in ("open", "done"):
        command = commands.add_parser(name)
        command.add_argument("--session", required=True, type=session_id)
        command.add_argument("--note")
    commands.add_parser("status")
    args = parser.parse_args()
    home = Path(os.environ.get("AUTONOMY_HOME", Path.home() / ".agent-lanes" / "watch"))
    try:
        if args.command == "run":
            return run(args, home)
        if args.command in {"open", "done"}:
            return mark(args, home, args.command == "open")
        return status(home)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"watch_prs.py: stopped ({error})", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("watch_prs.py: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
