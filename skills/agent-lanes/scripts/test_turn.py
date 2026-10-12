import contextlib
import fcntl
import importlib.util
import io
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("turn.py")
spec = importlib.util.spec_from_file_location("turn", SCRIPT)
turn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(turn)


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached")
        time.sleep(0.05)


def gone(pid):
    """True once the process has exited (a zombie waiting for its parent counts as exited)."""
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return state == "" or state.startswith("Z")


class TurnTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # The load gate has its own test; the other tests must not depend on this host's load.
        self.env = dict(os.environ, HOUSE_RULES_LOCK_DIR=str(self.root / "locks"), HOUSE_RULES_MAX_LOAD="100000")
        for key in ("HOUSE_RULES_TURNS", "HOUSE_RULES_JOBS", "HOUSE_RULES_REVIEW_SLOTS", "CARGO_BUILD_JOBS",
                    "CMAKE_BUILD_PARALLEL_LEVEL", "MAKEFLAGS", "RUST_TEST_THREADS"):
            self.env.pop(key, None)

    def turn(self, *args, **kwargs):
        return subprocess.run([sys.executable, str(SCRIPT), *args], env=self.env,
                              capture_output=True, text=True, timeout=10, **kwargs)

    def start(self, *args, stderr=None):
        process = subprocess.Popen([sys.executable, str(SCRIPT), *args], env=self.env, stderr=stderr)
        self.addCleanup(process.kill)
        return process

    def python(self, code):
        return [sys.executable, "-c", code]

    def lock(self, name):
        path = self.root / "locks" / (name + ".lock")
        path.parent.mkdir(exist_ok=True)
        path.touch()
        return path

    def test_second_command_waits_until_the_first_releases_the_lock(self):
        release = self.root / "release"
        log = self.root / "order.log"
        first_code = ("import pathlib, time\n"
                      f"log = open({str(log)!r}, 'a'); log.write('start-1\\n'); log.flush()\n"
                      f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(0.05)\n"
                      "log.write('end-1\\n')\n")
        first = self.start("build", "--", *self.python(first_code))
        wait_for(lambda: log.exists() and "start-1" in log.read_text())
        second_err = self.root / "second.err"
        with second_err.open("w") as err:
            second = self.start("build", "--", *self.python(f"open({str(log)!r}, 'a').write('start-2\\n')"), stderr=err)
            wait_for(lambda: "waiting for the build lock" in second_err.read_text())
            self.assertNotIn("start-2", log.read_text())
            release.touch()
            self.assertEqual(first.wait(timeout=10), 0)
            self.assertEqual(second.wait(timeout=10), 0)
        self.assertEqual(log.read_text().split(), ["start-1", "end-1", "start-2"])

    def test_review_turns_share_a_counted_set_of_slots(self):
        self.env["HOUSE_RULES_REVIEW_SLOTS"] = "2"
        release = self.root / "release"
        started = self.root / "started"
        started.mkdir()
        code = ("import pathlib, sys, time\n"
                f"pathlib.Path({str(started)!r}, sys.argv[1]).touch()\n"
                f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(0.05)\n")
        panels = [self.start("review", "--", sys.executable, "-c", code, n) for n in ("1", "2")]
        wait_for(lambda: len(list(started.iterdir())) == 2)
        third_err = self.root / "third.err"
        with third_err.open("w") as err:
            third = self.start("review", "--", sys.executable, "-c", code, "3", stderr=err)
            wait_for(lambda: "waiting for the review lock" in third_err.read_text())
            self.assertFalse((started / "3").exists())
            release.touch()
            for panel in panels + [third]:
                self.assertEqual(panel.wait(timeout=10), 0)
        self.assertTrue((started / "3").exists())

    def test_build_lock_and_review_slots_are_independent(self):
        with open(self.lock("build"), "rb") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            result = self.turn("review", "--", *self.python("print('ran')"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ran\n")
        self.env["HOUSE_RULES_REVIEW_SLOTS"] = "1"
        with open(self.lock("review-1"), "rb") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            self.assertEqual(self.turn("build", "--", "true").returncode, 0)

    def test_shell_lock_commands_wait_for_the_same_lock(self):
        tool = ["/usr/bin/lockf", "-k", "-t", "0"] if sys.platform == "darwin" else ["flock", "-n"]
        if not shutil.which(tool[0]):
            self.skipTest(f"{tool[0]} is not installed")
        release = self.root / "release"
        started = self.root / "started"
        code = (f"import pathlib, time\npathlib.Path({str(started)!r}).touch()\n"
                f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(0.05)\n")
        holder = self.start("build", "--", *self.python(code))
        wait_for(started.exists)
        lock = self.root / "locks" / "build.lock"
        busy = subprocess.run([*tool, str(lock), "true"], capture_output=True)
        release.touch()
        self.assertEqual(holder.wait(timeout=10), 0)
        free = subprocess.run([*tool, str(lock), "true"], capture_output=True)
        self.assertNotEqual(busy.returncode, 0)
        self.assertEqual(free.returncode, 0, free.stderr)
        self.assertTrue(lock.exists())

    def test_a_turn_inside_a_running_turn_of_the_same_kind_runs_at_once(self):
        inner = [sys.executable, str(SCRIPT), "build", "--", *self.python("print('inner')")]
        result = self.turn("build", "--", *inner)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "inner\n")

    def test_an_inherited_marker_whose_holder_is_gone_takes_the_lock(self):
        # A background job left behind by a finished turn keeps the marker but not the lock.
        finished = subprocess.Popen(["true"])
        finished.wait()
        self.env["HOUSE_RULES_TURNS"] = f"build:{finished.pid}"
        err = self.root / "err"
        with open(self.lock("build"), "rb") as held, err.open("w") as stderr:
            fcntl.flock(held, fcntl.LOCK_EX)
            waiter = self.start("build", "--", "true", stderr=stderr)
            wait_for(lambda: "waiting for the build lock" in err.read_text())
            fcntl.flock(held, fcntl.LOCK_UN)
            self.assertEqual(waiter.wait(timeout=10), 0)

    def test_cancelling_a_turn_signals_the_whole_command_group(self):
        pidfile = self.root / "worker.pid"
        # The worker cleans up for a second after SIGTERM; its shell parent dies at once.
        worker_code = "trap 'sleep 1; exit 0' TERM; while :; do sleep 0.1; done"
        holder = self.start("review", "--", "sh", "-c", f"sh -c \"{worker_code}\" & echo $! > {pidfile}; wait")
        wait_for(lambda: pidfile.exists() and pidfile.read_text().strip())
        worker = int(pidfile.read_text())
        self.addCleanup(lambda: gone(worker) or os.kill(worker, signal.SIGKILL))
        holder.send_signal(signal.SIGTERM)
        holder.wait(timeout=10)
        wait_for(lambda: gone(worker))
        self.assertEqual(self.turn("review", "--", "true").returncode, 0)

    def test_a_waiter_on_a_removed_lock_file_takes_the_new_one(self):
        old = self.lock("build")
        err = self.root / "err"
        with open(old, "rb") as first, err.open("w") as stderr:
            fcntl.flock(first, fcntl.LOCK_EX)
            waiter = self.start("build", "--", "true", stderr=stderr)
            wait_for(lambda: "waiting for the build lock" in err.read_text())
            old.unlink()
            with open(self.lock("build"), "rb") as second:
                fcntl.flock(second, fcntl.LOCK_EX)
                fcntl.flock(first, fcntl.LOCK_UN)
                time.sleep(turn.POLL_SECONDS + 1)
                self.assertIsNone(waiter.poll())
            self.assertEqual(waiter.wait(timeout=10), 0)

    def test_the_load_gate_waits_until_load_falls(self):
        loads = iter([(50.0, 0, 0), (1.0, 0, 0)])
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"HOUSE_RULES_LOCK_DIR": str(self.root / "locks"),
                                          "HOUSE_RULES_MAX_LOAD": "4"}), \
                mock.patch.object(turn.os, "getloadavg", lambda: next(loads)), \
                mock.patch.object(turn.time, "sleep") as sleep, contextlib.redirect_stderr(stderr):
            fd = turn.take_turn("build")
        os.close(fd)
        self.assertIn("load 50.0 is above 4", stderr.getvalue())
        sleep.assert_called_once_with(turn.LOAD_POLL_SECONDS)

    def test_job_limit_caps_caller_values_and_keeps_lower_ones(self):
        code = ("import os, sys\n"
                "print(os.nice(0), *(os.environ[k] for k in ('HOUSE_RULES_JOBS', 'CARGO_BUILD_JOBS', "
                "'CMAKE_BUILD_PARALLEL_LEVEL', 'RUST_TEST_THREADS')), os.environ.get('MAKEFLAGS'), sep='|')\n"
                "sys.exit(3)\n")
        self.env.update(HOUSE_RULES_JOBS="4", CARGO_BUILD_JOBS="16", RUST_TEST_THREADS="1", MAKEFLAGS="-k -j16 -s")
        result = self.turn("build", "--", *self.python(code))
        self.assertEqual(result.returncode, 3, result.stderr)
        niceness, *values = result.stdout.strip().split("|")
        self.assertGreaterEqual(int(niceness), 10)
        # The command's own flags and MAKEFLAGS are the caller's: make gets -j on its command line.
        self.assertEqual(values, ["4", "4", "4", "1", "-k -j16 -s"])

    def test_default_job_limit_is_performance_cores_minus_two(self):
        result = self.turn("--jobs")
        self.assertEqual(result.returncode, 0, result.stderr)
        performance = os.cpu_count()
        if sys.platform == "darwin":
            levels = subprocess.run(["sysctl", "-n", "hw.nperflevels"], capture_output=True, text=True).stdout.strip()
            if levels not in ("", "1"):
                performance = int(subprocess.run(["sysctl", "-n", "hw.perflevel0.logicalcpu"],
                                                 capture_output=True, text=True).stdout)
        else:
            performance -= turn.linux_efficiency_cores()
        self.assertEqual(int(result.stdout), max(1, performance - 2))

    def test_linux_efficiency_cores_are_counted_and_read_errors_stop(self):
        self.assertEqual(turn.count_cpus("16-31\n"), 16)
        self.assertEqual(turn.count_cpus("0,2-3"), 3)
        atom = self.root / "cpus"
        self.assertEqual(turn.linux_efficiency_cores(atom), 0)
        atom.write_text("8-15\n")
        self.assertEqual(turn.linux_efficiency_cores(atom), 8)
        atom.write_text("garbage\n")
        with self.assertRaises(SystemExit):
            turn.linux_efficiency_cores(atom)

    def test_mac_efficiency_core_probe_failures_stop(self):
        def sysctl(answers):
            def run(cmd, **kwargs):
                code, out, err = answers[cmd[-1]]
                return subprocess.CompletedProcess(cmd, code, out, err)
            return run
        unknown = (1, "", "sysctl: unknown oid 'x'")
        cases = [({"hw.nperflevels": unknown}, 0),
                 ({"hw.nperflevels": (0, "2\n", ""), "hw.perflevel1.logicalcpu": (0, "2\n", "")}, 2),
                 ({"hw.nperflevels": (0, "2\n", ""), "hw.perflevel1.logicalcpu": unknown}, SystemExit),
                 ({"hw.nperflevels": (1, "", "sysctl: permission denied")}, SystemExit)]
        for answers, expected in cases:
            with self.subTest(answers=answers), mock.patch.object(turn.subprocess, "run", sysctl(answers)):
                if expected is SystemExit:
                    with self.assertRaises(SystemExit):
                        turn.mac_efficiency_cores()
                else:
                    self.assertEqual(turn.mac_efficiency_cores(), expected)

    def test_a_process_the_command_leaves_running_does_not_keep_the_lock(self):
        pidfile = self.root / "daemon.pid"
        result = self.turn("build", "--", "sh", "-c", f"sleep 30 >/dev/null 2>&1 & echo $! > {pidfile}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.addCleanup(lambda: os.kill(int(pidfile.read_text()), signal.SIGKILL))
        with open(self.lock("build"), "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_unknown_lock_names_and_bad_limits_are_refused(self):
        self.assertEqual(self.turn("bulid", "--", "true").returncode, 2)
        self.assertFalse((self.root / "locks").exists())
        for name in ("HOUSE_RULES_JOBS", "HOUSE_RULES_REVIEW_SLOTS", "HOUSE_RULES_MAX_LOAD"):
            with self.subTest(name=name):
                saved = dict(self.env)
                self.env[name] = "0"
                result = self.turn("review", "--", "true")
                self.env = saved
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(name, result.stderr)


if __name__ == "__main__":
    unittest.main()
