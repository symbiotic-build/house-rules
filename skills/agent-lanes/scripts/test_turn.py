import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).with_name("turn.py")


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached")
        time.sleep(0.05)


class TurnTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, HOUSE_RULES_LOCK_DIR=str(self.root / "locks"))
        for key in ("HOUSE_RULES_TURNS", "HOUSE_RULES_JOBS", "HOUSE_RULES_REVIEW_SLOTS", "CARGO_BUILD_JOBS",
                    "CMAKE_BUILD_PARALLEL_LEVEL", "MAKEFLAGS", "RUST_TEST_THREADS"):
            self.env.pop(key, None)

    def turn(self, *args, **kwargs):
        return subprocess.run([sys.executable, str(SCRIPT), *args], env=self.env,
                              capture_output=True, text=True, timeout=10, **kwargs)

    def python(self, code):
        return [sys.executable, "-c", code]

    def test_second_command_waits_until_the_first_releases_the_lock(self):
        release = self.root / "release"
        log = self.root / "order.log"
        first_code = ("import pathlib, time\n"
                      f"log = open({str(log)!r}, 'a'); log.write('start-1\\n'); log.flush()\n"
                      f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(0.05)\n"
                      "log.write('end-1\\n')\n")
        second_code = f"open({str(log)!r}, 'a').write('start-2\\n')"
        first = subprocess.Popen([sys.executable, str(SCRIPT), "build", "--", *self.python(first_code)],
                                 env=self.env)
        self.addCleanup(first.kill)
        wait_for(lambda: log.exists() and "start-1" in log.read_text())
        second_err = self.root / "second.err"
        with second_err.open("w") as err:
            second = subprocess.Popen([sys.executable, str(SCRIPT), "build", "--", *self.python(second_code)],
                                      env=self.env, stderr=err)
            self.addCleanup(second.kill)
            wait_for(lambda: "waiting for the build lock" in second_err.read_text())
            self.assertNotIn("start-2", log.read_text())
            release.touch()
            self.assertEqual(first.wait(timeout=10), 0)
            self.assertEqual(second.wait(timeout=10), 0)
        self.assertEqual(log.read_text().split(), ["start-1", "end-1", "start-2"])

    def test_build_and_review_locks_are_independent(self):
        with open(self.lock("build"), "rb") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            result = self.turn("review", "--", *self.python("print('ran')"))
        with open(self.lock("review-1"), "rb") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            self.env["HOUSE_RULES_REVIEW_SLOTS"] = "1"
            self.assertEqual(self.turn("build", "--", "true").returncode, 0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ran\n")

    def test_a_turn_inside_a_turn_of_the_same_lock_runs_at_once(self):
        inner = [sys.executable, str(SCRIPT), "build", "--", *self.python("print('inner')")]
        result = self.turn("build", "--", *inner)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "inner\n")

    def test_exit_status_niceness_and_job_limit_reach_the_command(self):
        code = ("import os, sys\n"
                "print(os.nice(0), *(os.environ[k] for k in ('HOUSE_RULES_JOBS', 'CARGO_BUILD_JOBS', "
                "'CMAKE_BUILD_PARALLEL_LEVEL', 'MAKEFLAGS', 'RUST_TEST_THREADS', 'HOUSE_RULES_TURNS')))\n"
                "sys.exit(3)\n")
        self.env["HOUSE_RULES_JOBS"] = "5"
        self.env["RUST_TEST_THREADS"] = "1"
        result = self.turn("build", "--", *self.python(code))
        self.assertEqual(result.returncode, 3, result.stderr)
        niceness, *values = result.stdout.split()
        self.assertGreaterEqual(int(niceness), 10)
        self.assertEqual(values, ["5", "5", "5", "-j5", "1", "build"])

    def test_default_job_limit_is_performance_cores_minus_two(self):
        result = self.turn("--jobs")
        self.assertEqual(result.returncode, 0, result.stderr)
        performance = os.cpu_count()
        if sys.platform == "darwin":
            levels = subprocess.run(["sysctl", "-n", "hw.nperflevels"], capture_output=True, text=True).stdout.strip()
            if levels not in ("", "1"):
                performance = int(subprocess.run(["sysctl", "-n", "hw.perflevel0.logicalcpu"],
                                                 capture_output=True, text=True).stdout)
        elif Path("/sys/devices/cpu_core/cpus").exists() and Path("/sys/devices/cpu_atom/cpus").exists():
            self.skipTest("hybrid Linux host: covered by the cpu_atom parser")
        self.assertEqual(int(result.stdout), max(1, performance - 2))

    def test_review_turns_share_a_counted_set_of_slots(self):
        self.env["HOUSE_RULES_REVIEW_SLOTS"] = "2"
        release = self.root / "release"
        started = self.root / "started"
        started.mkdir()
        code = ("import pathlib, sys, time\n"
                f"pathlib.Path({str(started)!r}, sys.argv[1]).touch()\n"
                f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(0.05)\n")
        panels = []
        for n in ("1", "2"):
            panels.append(subprocess.Popen([sys.executable, str(SCRIPT), "review", "--", sys.executable, "-c", code, n],
                                           env=self.env))
            self.addCleanup(panels[-1].kill)
        wait_for(lambda: len(list(started.iterdir())) == 2)
        third_err = self.root / "third.err"
        with third_err.open("w") as err:
            third = subprocess.Popen([sys.executable, str(SCRIPT), "review", "--", sys.executable, "-c", code, "3"],
                                     env=self.env, stderr=err)
            self.addCleanup(third.kill)
            wait_for(lambda: "waiting for the review lock" in third_err.read_text())
            self.assertFalse((started / "3").exists())
            release.touch()
            for panel in panels + [third]:
                self.assertEqual(panel.wait(timeout=10), 0)
        self.assertTrue((started / "3").exists())

    def test_a_process_the_command_leaves_running_does_not_keep_the_lock(self):
        pidfile = self.root / "daemon.pid"
        result = self.turn("build", "--", "sh", "-c", f"sleep 30 >/dev/null 2>&1 & echo $! > {pidfile}")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.addCleanup(lambda: os.kill(int(pidfile.read_text()), signal.SIGKILL))
        with open(self.lock("build"), "rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_unknown_lock_names_and_bad_job_limits_are_refused(self):
        self.assertEqual(self.turn("bulid", "--", "true").returncode, 2)
        self.assertFalse((self.root / "locks").exists())
        for name in ("HOUSE_RULES_JOBS", "HOUSE_RULES_REVIEW_SLOTS"):
            with self.subTest(name=name):
                env = dict(self.env)
                self.env[name] = "0"
                result = self.turn("review", "--", "true")
                self.env = env
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(name, result.stderr)

    def lock(self, name):
        path = self.root / "locks" / (name + ".lock")
        path.parent.mkdir(exist_ok=True)
        path.touch()
        return path


if __name__ == "__main__":
    unittest.main()
