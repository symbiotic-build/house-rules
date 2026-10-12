#!/usr/bin/env python3
"""Run one heavy command when it is its turn on this machine (rules/delivery.md §Parallel work).

  turn.py build -- <command> [args...]    builds, test suites and benchmarks
  turn.py review -- <command> [args...]   review panels
  turn.py --jobs                          print the job limit for locked commands

Waits for the machine-wide lock, then runs the command at nice 10 with the job limit in
HOUSE_RULES_JOBS and in CARGO_BUILD_JOBS, CMAKE_BUILD_PARALLEL_LEVEL, MAKEFLAGS and
RUST_TEST_THREADS unless the caller set them. Releases the lock when the command exits and
returns its exit status. The lock is held by this process only, so a daemon the command
starts does not keep it. A command run inside a turn of the same lock runs at once.

Locks: ${HOUSE_RULES_LOCK_DIR:-~/.cache/house-rules/locks}/<name>.lock, a kernel flock that
`lockf` (macOS) and `flock` (Linux) on the same file also respect.
Job limit: HOUSE_RULES_JOBS if set, otherwise online cores - 2, at least 1.
"""
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

LOCKS = ("build", "review")
NICENESS = 10


def jobs():
    value = os.environ.get("HOUSE_RULES_JOBS")
    if value is not None:
        if not value.isdigit() or int(value) < 1:
            sys.exit(f"turn: HOUSE_RULES_JOBS must be a whole number above 0, not {value!r}")
        return int(value)
    return max(1, (os.cpu_count() or 1) - 2)


def lock_file(name):
    root = Path(os.environ.get("HOUSE_RULES_LOCK_DIR") or Path.home() / ".cache/house-rules/locks")
    path = root / (name + ".lock")
    # Open an existing lock read-only: a sandbox that forbids writes outside the workspace
    # can still take a flock on it.
    try:
        try:
            return path, os.open(path, os.O_RDONLY)
        except FileNotFoundError:
            root.mkdir(parents=True, exist_ok=True)
            return path, os.open(path, os.O_RDONLY | os.O_CREAT, 0o644)
    except OSError as exc:
        sys.exit(f"turn: cannot open the {name} lock {path}: {exc}")


def main(argv):
    if argv == ["--jobs"]:
        print(jobs())
        return 0
    if len(argv) < 3 or argv[0] not in LOCKS or argv[1] != "--":
        print(__doc__.split("\n\n")[1].rstrip(), file=sys.stderr)
        return 2
    name, command = argv[0], argv[2:]
    held = os.environ.get("HOUSE_RULES_TURNS", "").split()
    if name in held:
        try:
            os.execvp(command[0], command)
        except OSError as exc:
            sys.exit(f"turn: cannot run {command[0]}: {exc}")
    limit = str(jobs())
    path, fd = lock_file(name)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"turn: waiting for the {name} lock ({path})", file=sys.stderr, flush=True)
        start = time.monotonic()
        fcntl.flock(fd, fcntl.LOCK_EX)
        print(f"turn: got the {name} lock after {time.monotonic() - start:.0f} s", file=sys.stderr, flush=True)
    env = dict(os.environ, HOUSE_RULES_TURNS=" ".join(held + [name]), HOUSE_RULES_JOBS=limit)
    for key, value in (("CARGO_BUILD_JOBS", limit), ("CMAKE_BUILD_PARALLEL_LEVEL", limit),
                       ("MAKEFLAGS", "-j" + limit), ("RUST_TEST_THREADS", limit)):
        env.setdefault(key, value)
    # The lock descriptor is not inheritable (Python's default), so only this process holds it.
    try:
        child = subprocess.Popen(command, env=env,
                                 preexec_fn=lambda: os.nice(max(0, NICENESS - os.nice(0))))
    except OSError as exc:
        sys.exit(f"turn: cannot run {command[0]}: {exc}")
    for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda number, frame: child.send_signal(number))
    status = child.wait()
    return 128 - status if status < 0 else status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
