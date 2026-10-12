#!/usr/bin/env python3
"""Run one heavy command when it is its turn on this machine (rules/delivery.md §Parallel work).

  turn.py build -- <command> [args...]    builds, test suites and benchmarks: one at a time
  turn.py review -- <command> [args...]   review panels: one per free review slot
  turn.py --jobs                          print the job limit for locked commands

Waits for the build lock or a free review slot, then runs the command at nice 10 with the
job limit in HOUSE_RULES_JOBS and in CARGO_BUILD_JOBS, CMAKE_BUILD_PARALLEL_LEVEL, MAKEFLAGS
and RUST_TEST_THREADS unless the caller set them. Releases the lock when the command exits
and returns its exit status. The lock is held by this process only, so a daemon the command
starts does not keep it. A command run inside a turn of the same kind runs at once.

Locks: ${HOUSE_RULES_LOCK_DIR:-~/.cache/house-rules/locks}/build.lock and review-<n>.lock
for n = 1..${HOUSE_RULES_REVIEW_SLOTS:-3}: kernel flocks that `lockf` (macOS) and `flock`
(Linux) on the same file also respect.
Job limit: HOUSE_RULES_JOBS if set, otherwise online cores - efficiency cores - 2, at least 1.
"""
import fcntl
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

NICENESS = 10
POLL_SECONDS = 2


def whole_number(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    if not value.isdigit() or int(value) < 1:
        sys.exit(f"turn: {name} must be a whole number above 0, not {value!r}")
    return int(value)


def efficiency_cores():
    """Online efficiency cores: macOS performance level 1, Linux hybrid `cpu_atom` CPUs."""
    if platform.system() == "Darwin":
        def sysctl(key):
            return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True).stdout.strip()
        return int(sysctl("hw.perflevel1.logicalcpu") or 0) if sysctl("hw.nperflevels") not in ("", "1") else 0
    try:
        listing = Path("/sys/devices/cpu_atom/cpus").read_text().strip()
    except OSError:
        return 0
    count = 0
    for part in filter(None, listing.split(",")):
        low, _, high = part.partition("-")
        count += int(high or low) - int(low) + 1
    return count


def jobs():
    return whole_number("HOUSE_RULES_JOBS", max(1, (os.cpu_count() or 1) - efficiency_cores() - 2))


def open_lock(path):
    # Open an existing lock read-only: a sandbox that forbids writes outside the workspace
    # can still take a flock on it.
    try:
        try:
            return os.open(path, os.O_RDONLY)
        except FileNotFoundError:
            path.parent.mkdir(parents=True, exist_ok=True)
            return os.open(path, os.O_RDONLY | os.O_CREAT, 0o644)
    except OSError as exc:
        sys.exit(f"turn: cannot open the lock {path}: {exc}")


def take_turn(name):
    """Hold the build lock, or the first free review slot, and return its descriptor."""
    root = Path(os.environ.get("HOUSE_RULES_LOCK_DIR") or Path.home() / ".cache/house-rules/locks")
    if name == "build":
        paths = [root / "build.lock"]
    else:
        paths = [root / f"review-{n}.lock" for n in range(1, whole_number("HOUSE_RULES_REVIEW_SLOTS", 3) + 1)]
    fds = [open_lock(path) for path in paths]
    start = None
    while True:
        for path, fd in zip(paths, fds):
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            for other in fds:
                if other != fd:
                    os.close(other)
            if start is not None:
                print(f"turn: got {path.name} after {time.monotonic() - start:.0f} s", file=sys.stderr, flush=True)
            return fd
        if start is None:
            start = time.monotonic()
            where = paths[0] if len(paths) == 1 else f"{len(paths)} review slots in {root}"
            print(f"turn: waiting for the {name} lock ({where})", file=sys.stderr, flush=True)
        if len(paths) == 1:
            fcntl.flock(fds[0], fcntl.LOCK_EX)
            continue
        time.sleep(POLL_SECONDS)


def main(argv):
    if argv == ["--jobs"]:
        print(jobs())
        return 0
    if len(argv) < 3 or argv[0] not in ("build", "review") or argv[1] != "--":
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
    take_turn(name)
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
