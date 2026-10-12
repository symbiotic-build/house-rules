#!/usr/bin/env python3
"""Run one heavy command when it is its turn on this machine (rules/delivery.md §Parallel work).

  turn.py build -- <command> [args...]    builds, test suites and benchmarks: one at a time
  turn.py review -- <command> [args...]   review panels: one per free review slot
  turn.py --jobs                          print the job limit for locked commands

Waits for the build lock or a free review slot, and while the one-minute load average is
above ${HOUSE_RULES_MAX_LOAD:-the online core count}. Then runs the command at nice 10 in its own process group, with
the job limit in HOUSE_RULES_JOBS, CARGO_BUILD_JOBS, CMAKE_BUILD_PARALLEL_LEVEL,
RUST_TEST_THREADS and a final MAKEFLAGS -j; a lower value the caller set stays. Releases
the lock when the command exits and returns its exit status. SIGHUP, SIGINT and SIGTERM go
to the whole process group, and the lock is kept until that group has exited. Only this process holds the lock, so a daemon the command
leaves running does not keep it. A turn started inside a running turn of the same kind runs
at once.

Locks: ${HOUSE_RULES_LOCK_DIR:-~/.local/state/house-rules/locks}/build.lock and
review-<n>.lock for n = 1..${HOUSE_RULES_REVIEW_SLOTS:-3}: kernel flocks that `lockf -k`
(macOS) and `flock` (Linux) on the same file also respect. Never remove these files.
Job limit: HOUSE_RULES_JOBS if set, otherwise online cores - efficiency cores - 2, at least 1.
"""
import fcntl
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time

NICENESS = 10
POLL_SECONDS = 2
LOAD_POLL_SECONDS = 30
STOP_SECONDS = 10
JOB_VARIABLES = ("CARGO_BUILD_JOBS", "CMAKE_BUILD_PARALLEL_LEVEL", "RUST_TEST_THREADS")


def whole_number(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    if not value.isdigit() or int(value) < 1:
        sys.exit(f"turn: {name} must be a whole number above 0, not {value!r}")
    return int(value)


def count_cpus(listing):
    """Count the CPUs in a Linux CPU list such as '0-7,16'."""
    count = 0
    for part in filter(None, listing.strip().split(",")):
        low, _, high = part.partition("-")
        count += int(high or low) - int(low) + 1
    return count


def linux_efficiency_cores(atom=Path("/sys/devices/cpu_atom/cpus")):
    """Hybrid Intel CPUs list their efficiency cores here; other machines have no such file."""
    try:
        return count_cpus(atom.read_text())
    except FileNotFoundError:
        return 0
    except (OSError, ValueError) as exc:
        sys.exit(f"turn: cannot read efficiency cores from {atom}: {exc}; set HOUSE_RULES_JOBS")


def mac_efficiency_cores():
    def sysctl(key, unknown_ok=False):
        result = subprocess.run(["sysctl", "-n", key], capture_output=True, text=True)
        value = result.stdout.strip()
        if result.returncode and unknown_ok and "unknown oid" in result.stderr:
            return None
        if result.returncode or not value.isdigit():
            sys.exit(f"turn: sysctl {key} failed: {result.stderr.strip() or value!r}; set HOUSE_RULES_JOBS")
        return int(value)
    # Intel Macs have no performance levels: the oid is unknown and every core counts.
    levels = sysctl("hw.nperflevels", unknown_ok=True)
    return sysctl("hw.perflevel1.logicalcpu") if levels and levels > 1 else 0


def jobs():
    if "HOUSE_RULES_JOBS" in os.environ:
        return whole_number("HOUSE_RULES_JOBS", None)
    efficiency = mac_efficiency_cores() if platform.system() == "Darwin" else linux_efficiency_cores()
    return max(1, (os.cpu_count() or 1) - efficiency - 2)


def ancestors():
    """Process IDs of this process's parents, nearest first."""
    found, pid = [], os.getppid()
    while pid > 1:
        found.append(pid)
        out = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        pid = int(out) if out.isdigit() else 0
    return found


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


def still_names(path, fd):
    """True when the path still names the locked file (it was not removed and recreated)."""
    try:
        here, there = os.stat(path), os.fstat(fd)
    except FileNotFoundError:
        return False
    return (here.st_dev, here.st_ino) == (there.st_dev, there.st_ino)


def take_turn(name):
    """Hold the build lock, or the first free review slot, while load allows; return its descriptor."""
    root = Path(os.environ.get("HOUSE_RULES_LOCK_DIR") or Path.home() / ".local/state/house-rules/locks")
    if name == "build":
        paths = [root / "build.lock"]
    else:
        paths = [root / f"review-{n}.lock" for n in range(1, whole_number("HOUSE_RULES_REVIEW_SLOTS", 3) + 1)]
    cores = whole_number("HOUSE_RULES_MAX_LOAD", os.cpu_count() or 1)
    start = None
    while True:
        fds = [open_lock(path) for path in paths]
        held = None
        for path, fd in zip(paths, fds):
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            if still_names(path, fd):
                held = fd
                break
            fcntl.flock(fd, fcntl.LOCK_UN)
        for fd in fds:
            if fd != held:
                os.close(fd)
        if held is not None:
            load = os.getloadavg()[0]
            if load <= cores:
                if start is not None:
                    print(f"turn: got the {name} lock after {time.monotonic() - start:.0f} s", file=sys.stderr, flush=True)
                return held
            os.close(held)
            print(f"turn: load {load:.1f} is above {cores}; waiting before the {name} job", file=sys.stderr, flush=True)
            start = start or time.monotonic()
            time.sleep(LOAD_POLL_SECONDS)
            continue
        if start is None:
            start = time.monotonic()
            where = paths[0] if len(paths) == 1 else f"{len(paths)} review slots in {root}"
            print(f"turn: waiting for the {name} lock ({where})", file=sys.stderr, flush=True)
        time.sleep(POLL_SECONDS)


def job_environment(limit):
    env = dict(os.environ, HOUSE_RULES_JOBS=str(limit))
    for key in JOB_VARIABLES:
        value = env.get(key, "")
        env[key] = str(min(int(value), limit)) if value.isdigit() and int(value) > 0 else str(limit)
    # GNU make uses the last job option, so a final -j<n> decides; a lower caller count stays.
    flags = env.get("MAKEFLAGS", "")
    counts = re.findall(r"(?:^|\s)(?:-j\s*|--jobs=)(\d+)", flags)
    count = min(int(counts[-1]), limit) if counts else limit
    env["MAKEFLAGS"] = (flags + " -j" + str(count)).strip()
    return env


def main(argv):
    if argv == ["--jobs"]:
        print(jobs())
        return 0
    if len(argv) < 3 or argv[0] not in ("build", "review") or argv[1] != "--":
        print(__doc__.split("\n\n")[1].rstrip(), file=sys.stderr)
        return 2
    name, command = argv[0], argv[2:]
    turns = os.environ.get("HOUSE_RULES_TURNS", "").split()
    holders = {int(pid) for entry in turns for kind, _, pid in [entry.partition(":")] if kind == name and pid.isdigit()}
    if holders & set(ancestors()):
        try:
            os.execvp(command[0], command)
        except OSError as exc:
            sys.exit(f"turn: cannot run {command[0]}: {exc}")
    limit = jobs()
    take_turn(name)
    env = job_environment(limit)
    env["HOUSE_RULES_TURNS"] = " ".join(turns + [f"{name}:{os.getpid()}"])
    # The lock descriptor is not inheritable (Python's default), so only this process holds it.
    try:
        child = subprocess.Popen(command, env=env, start_new_session=True,
                                 preexec_fn=lambda: os.nice(max(0, NICENESS - os.nice(0))))
    except OSError as exc:
        sys.exit(f"turn: cannot run {command[0]}: {exc}")

    cancelled = []

    def stop_group(number):
        try:
            os.killpg(child.pid, number)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def cancel(number, frame):
        cancelled.append(number)
        stop_group(number)
    for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, cancel)
    status = child.wait()
    if status < 0 or cancelled:
        # Cancelled or killed: the rest of the group exits before the lock is released.
        if not cancelled:
            stop_group(signal.SIGTERM)
        deadline = time.monotonic() + STOP_SECONDS
        while stop_group(0):
            if time.monotonic() > deadline:
                stop_group(signal.SIGKILL)
            time.sleep(0.1)
    return 128 - status if status < 0 else status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
