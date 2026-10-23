"""Behavior of the repository checks runner at its command boundary, over temporary Git repositories.

The cases follow the Acceptance chapter of docs/design/194-repository-checks.md. Every House Rules
revision the runner reads comes from a synthetic local clone named by a file:// HOUSE_RULES_URL, so no case
needs a network.
"""
import ast
import fcntl
import importlib.metadata
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("checks.py")
ROOT = SCRIPT.parents[3]
SPEC = ROOT / "skills/spec-writing"
FIXTURE = SPEC / "scripts/fixtures/minimal/docs"
RUNNER = "skills/repository-checks/scripts/checks.py"
OFFLINE = "file:///nonexistent/house-rules"  # an unreachable source stands for a denied network
NO_SPEC = {"spec-docs": {"enabled": False, "reason": "No specifications in this fixture."}}
TIME = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"
FETCHED = r", fetched " + TIME + r"\)"  # the end of a text header after its revision source
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
TOUR_FIX = ("apply the remedy for each code in the spec checker's diagnostic table, "
            "run spec_docs.py generate, stage the result")
DURATION = r"\d+\.\d s"


def base_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "HOUSE_RULES_", "XDG_"))}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="Test",
               GIT_AUTHOR_EMAIL="test@example.invalid", GIT_COMMITTER_NAME="Test",
               GIT_COMMITTER_EMAIL="test@example.invalid")
    return env


def git(cwd, *args, env=None):
    proc = subprocess.run(["git", *args], cwd=str(cwd), env=env or base_env(), capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    if proc.returncode:
        raise AssertionError(f"git {' '.join(args)}: {proc.stderr}")
    return proc.stdout.strip()


def spec_environment_reason():
    """Return why the spec-docs cases cannot run under this interpreter, or None when they can."""
    runtime = json.loads((SPEC / "scripts/runtime.json").read_text())
    bounds = [int(v) for v in re.findall(r"\d+", runtime["requires_python"])]
    supported = (bounds[0], bounds[1]) <= sys.version_info[:2] < (bounds[2], bounds[3])
    pins = re.findall(r"^([a-zA-Z0-9_-]+)==(\S+)", (SPEC / "scripts/requirements.lock").read_text(), re.M)
    try:
        installed = all(importlib.metadata.version(name) == version for name, version in pins)
    except importlib.metadata.PackageNotFoundError:
        installed = False
    if supported and installed and sys.prefix != sys.base_prefix:
        return None
    return ("spec-docs cases need the spec checker's environment as the test interpreter; "
            "run the tests with .tmp/spec-docs-env/bin/python")


def python39():
    for candidate in (shutil.which("python3.9"), "/usr/bin/python3"):
        if candidate and os.path.exists(candidate):
            proc = subprocess.run([candidate, "-c", "import sys; print(sys.version_info[:2] == (3, 9))"],
                                  capture_output=True, text=True, stdin=subprocess.DEVNULL)
            if proc.stdout.strip() == "True":
                return candidate
    return None


class HouseRules:
    """A synthetic House Rules clone holding the runner under test and the spec checker."""

    def __init__(self, folder):
        self.path = folder / "house-rules"
        shutil.copytree(str(SPEC), str(self.path / "skills/spec-writing"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.path / "rules").mkdir()
        shutil.copyfile(str(ROOT / "rules/writing.md"), str(self.path / "rules/writing.md"))
        (self.path / RUNNER).parent.mkdir(parents=True)
        shutil.copyfile(str(SCRIPT), str(self.path / RUNNER))
        git(self.path, "init", "-q", "-b", "main")
        self.main = self.commit("House Rules fixture")
        self.url = "file://" + str(self.path)

    def commit(self, message):
        git(self.path, "add", ".")
        git(self.path, "commit", "-q", "--allow-empty", "-m", message)
        return git(self.path, "rev-parse", "HEAD")

    def variant(self, message, files):
        """Commit a revision with `files` (path: new text) changed on its own branch; main stays; return it."""
        git(self.path, "checkout", "-q", "--detach")
        for name, content in files.items():
            (self.path / name).write_text(content)
        revision = self.commit(message)
        git(self.path, "branch", "variant-" + revision[:12])
        git(self.path, "checkout", "-q", "main")
        return revision

    def runner_variant(self, message, changes):
        """A variant whose runner has each (old, new) text replaced once."""
        source = (self.path / RUNNER).read_text()
        for old, new in changes:
            if source.count(old) != 1:
                raise AssertionError(f"{old!r} occurs {source.count(old)} times in the runner")
            source = source.replace(old, new)
        return self.variant(message, {RUNNER: source})


class Repo:
    def __init__(self, folder, house_rules, cache, name="repo", object_format=None):
        self.path = folder / name
        self.path.mkdir()
        self.main = house_rules.main
        self.env = dict(base_env(), HOUSE_RULES_CACHE=str(cache), HOUSE_RULES_URL=house_rules.url)
        git(self.path, "init", "-q", "-b", "main", *([f"--object-format={object_format}"] if object_format else []))
        self.root = git(self.path, "rev-parse", "--show-toplevel")

    def git(self, *args):
        return git(self.path, *args, env=self.env)

    def write(self, name, content):
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def stage(self, *names):
        self.git("add", "--", *names)

    def commit(self, message="change"):
        self.git("commit", "-q", "--no-verify", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def configure(self, checks=None, budgets=None):
        config = {"version": 1, "checks": checks or {}}
        if budgets:
            config["budgets"] = budgets
        self.write(".agents/checks.json", json.dumps(config, indent=2) + "\n")
        self.stage(".agents/checks.json")

    def spec(self, rejected=None, symbols=None, naming=None):
        """The spec checker's minimal fixture, with optional rejected form, entity symbols and naming rule."""
        shutil.copytree(str(FIXTURE), str(self.path / "docs"), dirs_exist_ok=True)
        path = self.path / "docs/ENTITIES.json"
        index = json.loads(path.read_text())
        entity = index["entities"]["example.batcher"]
        if rejected:
            entity["rejected_forms"] = [{"text": rejected, "replacement": "batcher", "reason": "One term."}]
        if symbols:
            entity["symbols"] = symbols
        if naming:
            index["naming_rules"] = [naming]
        path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
        self.stage("docs")

    def sentence(self, text):
        """Add one sentence after the batcher's definition in the fixture specification."""
        path = self.path / "docs/example.md"
        definition = "A batcher prevents overfilling by accepting items only while its batch has room.\n\n"
        content = path.read_text()
        start = content.index(definition, content.index('<a id="batcher">'))
        path.write_text(content[:start + len(definition)] + text + "\n\n" + content[start + len(definition):])

    def run(self, *args, script=SCRIPT, python=None, env=None, cwd=None, input=None):
        return subprocess.run([python or sys.executable, "-B", str(script), *args], cwd=str(cwd or self.path),
                              env=env or self.env, capture_output=True, text=True,
                              input=input, stdin=None if input is not None else subprocess.DEVNULL)

    def report(self, *args, **kwargs):
        proc = self.run(*args, "--json", **kwargs)
        try:
            return proc, json.loads(proc.stdout)
        except ValueError:
            raise AssertionError(f"no JSON report (exit {proc.returncode}): {proc.stdout}{proc.stderr}")

    def snapshot(self, *args, **kwargs):
        """Run a stage that checks one snapshot; return the process and that snapshot's report entry."""
        proc, entry, _ = self.checked(*args, **kwargs)
        return proc, entry

    def checked(self, *args, **kwargs):
        """Like `snapshot`, and also return the run's House Rules revision object."""
        proc, report = self.report(*args, **kwargs)
        (entry,) = report["snapshots"]
        if report["result"] != entry["result"]:
            raise AssertionError(f"run result {report['result']} differs from its one snapshot's: {report}")
        return proc, entry, report["house_rules"]

    def hook(self):
        path = self.path / ".git/hooks/pre-commit"
        path.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -I {shlex.quote(str(SCRIPT))} "
                        "run --stage pre-commit\n")
        path.chmod(0o755)

    def state(self):
        """Everything a run must leave unchanged: staged entries, references, stash and working tree."""
        files = {p.relative_to(self.path).as_posix(): p.read_bytes() for p in self.path.rglob("*")
                 if p.is_file() and ".git" not in p.relative_to(self.path).parts}
        return (self.git("ls-files", "--stage"), self.git("for-each-ref"),
                self.git("stash", "list"), files)


def statuses(report):
    return {c["id"]: c["status"] for c in report["checks"]}


def check(run, stages, paths=("**",), **extra):
    entry = dict(run=list(run), stages=list(stages), paths=list(paths), fix="Fix the synthetic finding.",
                 reason="A synthetic repository check.")
    entry.update(extra)
    return entry


class RunnerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = Path(tempfile.mkdtemp()).resolve()
        cls.addClassCleanup(shutil.rmtree, str(cls.folder))
        cls.house_rules = HouseRules(cls.folder)
        cls.cache = cls.folder / "cache"

    def setUp(self):
        self.repo = Repo(Path(tempfile.mkdtemp(dir=str(self.folder))), self.house_rules, self.cache)

    def seed_environment(self):
        """Give the cache the spec checker's environment from this interpreter's prepared one."""
        reason = spec_environment_reason()
        if reason:
            self.skipTest(reason)
        self.assertEqual(self.repo.run("run", "--stage", "ci", "--index", "--only", "whitespace").returncode, 0)
        match = re.search(r"environment not built at (.+?) \(run:", self.repo.run("status").stdout)
        if match:
            Path(match[1]).parent.mkdir(parents=True, exist_ok=True)
            os.symlink(sys.prefix, match[1])

    def assertLines(self, text, patterns):
        """Match each line; a budget warning depends on the machine's load, and its own test covers it."""
        lines = [line for line in text.rstrip("\n").split("\n") if not line.startswith("warning: budget: ")]
        self.assertEqual(len(lines), len(patterns), text)
        for line, pattern in zip(lines, patterns):
            self.assertRegex(line, r"\A" + pattern + r"\Z")

    def racing_git(self, command, action):
        """Return a PATH whose git runs `action`, a shell line, once before its first `git ... <command> ...`.

        It stands in for another process that acts while the runner works; `$REAL` is the real Git.
        """
        folder = Path(tempfile.mkdtemp(dir=str(self.repo.path.parent)))
        marker = shlex.quote(str(folder / "acted"))
        (folder / "git").write_text(f"#!/bin/sh\nREAL={shlex.quote(shutil.which('git'))}\n"
                                    f'case " $* " in *" {command} "*) if [ ! -e {marker} ]; then\n'
                                    f"  : > {marker}\n  {action}\nfi;; esac\n" 'exec "$REAL" "$@"\n')
        (folder / "git").chmod(0o755)
        return f"{folder}{os.pathsep}{os.environ['PATH']}"

    def assertPreparationFailure(self, proc, *parts):
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(len(proc.stderr.splitlines()), 1, proc.stderr)
        for part in parts:
            self.assertIn(part, proc.stderr)


class DefaultsTest(RunnerCase):
    def test_no_specifications_runs_whitespace_and_skips_spec_docs(self):
        self.repo.write("tool.sh", "echo ok\n")
        self.repo.stage("tool.sh")
        self.repo.configure()
        proc = self.repo.run("run", "--stage", "pre-commit")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertLines(proc.stdout, [
            re.escape(f"repository checks: pre-commit on the staged index, House Rules {self.repo.main} (main")
            + FETCHED,
            "PASS  whitespace   " + DURATION,
            re.escape("SKIP  spec-docs    requires docs/DOCUMENTS.json"),
            re.escape("All 1 selected check passed; 1 skipped."),
        ])
        _, report = self.repo.snapshot("run", "--stage", "pre-commit")
        self.assertEqual((report["base"], report["overrides"], report["result"]), (EMPTY_TREE, [], "pass"))

    def test_whitespace_reads_attributes_from_the_snapshot(self):
        self.repo.configure()
        self.repo.commit()
        self.repo.write("notes.txt", "trailing \n")
        self.repo.stage("notes.txt")
        self.repo.write(".gitattributes", "* -whitespace\n")  # unstaged: must not turn the check off
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit")
        self.assertEqual(proc.returncode, 1)
        whitespace = report["checks"][0]
        self.assertEqual((whitespace["id"], whitespace["status"]), ("whitespace", "fail"))
        self.assertIn("notes.txt:1: trailing whitespace.", whitespace["output"])

    def test_configuration_errors_stop_the_run_with_exit_2(self):
        snapshotless = check(["eslint", "{files}"], ["pre-commit", "ci"], ["src/**/*.ts"], scope="files")
        cases = {
            "unknown top-level field": ({"extra": 1}, None, "the file has unknown field extra"),
            "unknown entry field": ({"checks": {"whitespace": {"colour": "red", "reason": "x"}}}, None,
                                    "checks.whitespace has unknown field colour"),
            "unsupported version": ({"version": 2}, None, "unsupported version 2"),
            "house_rules field of an earlier design": (
                {"house_rules": {"revision": "1" * 40, "url": OFFLINE}}, None,
                "remove house_rules: checks always run at House Rules main"),
            "entry that sets enforced": ({"checks": {"whitespace": {"enforced": False, "reason": "x"}}}, None,
                                         "checks.whitespace.enforced is set by House Rules, not by the "
                                         "configuration; to turn the check off, set enabled: false with a reason"),
            "unknown placeholder": ({"checks": {"lint": check(["lint", "{snap}"], ["ci"])}}, None,
                                    "checks.lint.run uses unknown placeholder {snap}"),
            "changed default without reason": ({"checks": {"whitespace": {"enabled": False}}}, None,
                                               "checks.whitespace changes enabled without a reason"),
            "repository check without reason": (
                {"checks": {"lint": {k: v for k, v in check(["lint"], ["ci"]).items() if k != "reason"}}}, None,
                "checks.lint lacks reason"),
            "hook stage without snapshot": ({"checks": {"lint": snapshotless}}, None,
                                            "checks.lint lists pre-commit but its run has no {snapshot}"),
            "budget without positive seconds": ({"budgets": {"pre-commit": {"seconds": 0, "reason": "x"}}}, None,
                                                "budgets.pre-commit.seconds must be a positive number"),
            "NUL character in an argument": ({"checks": {"lint": check(["lint", "a\0b", "{snapshot}"], ["ci"])}},
                                             None, "checks.lint.run has an argument with a NUL character"),
            "files scope without a whole {files} argument": (
                {"checks": {"lint": check(["lint", "{snapshot}"], ["ci"], scope="files")}}, None,
                "checks.lint has scope files but its run has no whole {files} argument"),
            "argument that cannot be passed to a program": (
                {"checks": {"lint": check(["lint", "\ud800", "{snapshot}"], ["ci"])}}, None,
                "the file holds text that cannot be printed or passed to a program: \\ud800"),
            "reason that cannot be printed": (
                {"checks": {"whitespace": {"enabled": False, "reason": "off \udbff"}}}, None,
                "the file holds text that cannot be printed or passed to a program: off \\udbff"),
            "NUL character in a check identity": ({"checks": {"li\0nt": check(["lint", "{snapshot}"], ["ci"])}}, None,
                                                  "checks has an identity with a NUL character: li\\x00nt"),
            "repository check without fix": (
                {"checks": {"lint": {k: v for k, v in check(["lint"], ["ci"]).items() if k != "fix"}}}, None,
                "checks.lint lacks fix"),
        }
        for name, (change, _, message) in cases.items():
            with self.subTest(name):
                config = {"version": 1, "checks": {}}
                config.update(change)
                self.repo.write(".agents/checks.json", json.dumps(config))
                self.repo.stage(".agents/checks.json")
                proc = self.repo.run("run", "--stage", "pre-commit")
                self.assertPreparationFailure(proc, "configuration error in .agents/checks.json: " + message,
                                              "fix the file through a reviewed change")

    def test_git_replacement_objects_do_not_change_the_checked_commit(self):
        self.repo.configure()
        self.repo.write("notes.txt", "trailing \n")
        self.repo.stage("notes.txt")
        checked = self.repo.commit()
        self.repo.git("checkout", "-q", "--orphan", "stand-in")
        self.repo.git("rm", "-q", "-r", "--cached", ".")
        stand_in = self.repo.commit("a stand-in without configuration or files")
        self.repo.git("replace", checked, stand_in)  # a local replacement Git would otherwise read for `checked`
        proc, report, house_rules = self.repo.checked("run", "--stage", "ci", "--head", checked)
        self.assertEqual((proc.returncode, report["snapshot"], house_rules["revision"]), (1, checked, self.repo.main),
                         proc.stdout + proc.stderr)
        whitespace = {c["id"]: c for c in report["checks"]}["whitespace"]
        self.assertIn("notes.txt:1: trailing whitespace.", whitespace["output"])

    def test_tracked_path_that_is_not_utf8_stays_checkable(self):
        name = os.fsdecode(b"caf\xff.txt")
        content = self.repo.path.parent / "content.txt"
        content.write_text("text\n")
        blob = self.repo.git("hash-object", "-w", str(content))
        # Staged in Git only, because some file systems refuse such a name.
        self.repo.git("update-index", "--add", "--cacheinfo", f"100644,{blob},{name}")
        lister = 'for f; do git cat-file -e "$0:$f" || exit 1; printf "%s\\n" "$f"; done'
        self.repo.configure({"names": check(["sh", "-c", lister, "{snapshot}", "{files}"], ["ci"], ["*.txt"],
                                            scope="files")})
        self.repo.commit()
        # A UTF-8 locale makes Python's streams strict; under the C locale they would escape such bytes by themselves.
        text = subprocess.run([sys.executable, "-B", str(SCRIPT), "run", "--stage", "ci", "--head", "HEAD"],
                              cwd=str(self.repo.path), env=dict(self.repo.env, LC_ALL="en_US.UTF-8"),
                              capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        self.assertIn(b"PASS  names        ", text.stdout)
        self.assertIn(b"\n      caf\xff.txt\n", text.stdout)
        proc, report = self.repo.snapshot("run", "--stage", "ci", "--head", "HEAD")
        names = {c["id"]: c for c in report["checks"]}["names"]
        self.assertEqual((proc.returncode, names["status"], names["command"][-1:], names["output"]),
                         (0, "pass", [name], name + "\n"), proc.stderr)

    def test_check_command_contract(self):
        probe = 'pwd; echo "$CHECK_STAGE $CHECK_BASE $CHECK_SNAPSHOT $0"; cat'
        self.repo.configure({"probe": check(["sh", "-c", probe, "{snapshot}"], ["pre-commit"])})
        self.repo.write("sub/file.txt", "text\n")
        self.repo.stage("sub/file.txt")
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit", "--only", "probe",
                                        cwd=self.repo.path / "sub", input="leaked standard input\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["checks"][0]["output"],
                         f"{self.repo.root}\npre-commit {report['base']} {report['snapshot']} {report['snapshot']}\n")

    def test_check_whose_program_is_missing_is_an_error_and_fails_the_run(self):
        self.repo.configure({"lint": check(["no-such-program-for-checks", "{snapshot}"], ["pre-commit"])})
        proc, report = self.repo.report("run", "--stage", "pre-commit")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        (snapshot,) = report["snapshots"]
        lint = {c["id"]: c for c in snapshot["checks"]}["lint"]
        self.assertEqual((report["result"], snapshot["result"], lint["status"], lint["output"]),
                         ("fail", "fail", "error",
                          "cannot start 'no-such-program-for-checks': No such file or directory\n"))

    def test_repository_whose_path_ends_in_a_space_is_checked(self):
        repo = Repo(Path(tempfile.mkdtemp(dir=str(self.folder))), self.house_rules, self.cache, name="repo ")
        repo.write("notes.txt", "trailing \n")
        repo.stage("notes.txt")
        repo.configure()
        proc, report = repo.snapshot("run", "--stage", "pre-commit")
        whitespace = {c["id"]: c for c in report["checks"]}["whitespace"]
        self.assertEqual((proc.returncode, whitespace["status"]), (1, "fail"), proc.stderr)
        self.assertIn("notes.txt:1: trailing whitespace.", whitespace["output"])

    def test_argument_with_a_filename_byte_reaches_the_check(self):
        name = os.fsdecode(b"caf\xff")  # a surrogate escape, as Python holds a filename byte that is not UTF-8
        printer = [sys.executable, "-c", "import os, sys; print(os.fsencode(sys.argv[1]).hex())", name, "{snapshot}"]
        self.repo.configure({"bytes": check(printer, ["pre-commit"])})
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit", "--only", "bytes")
        self.assertEqual((proc.returncode, report["checks"][0]["output"]), (0, "636166ff\n"), proc.stderr)

    def test_text_report_keeps_check_output_byte_for_byte(self):
        printer = check(["sh", "-c", "printf 'a\\rb\\r\\nc\\fd\\n\\n\\n'", "{snapshot}"], ["pre-commit"])
        self.repo.configure({"printer": printer})
        text = subprocess.run([sys.executable, "-B", str(SCRIPT), "run", "--stage", "pre-commit", "--only", "printer"],
                              cwd=str(self.repo.path), env=self.repo.env, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        self.assertIn(b"\n      a\rb\r\n      c\x0cd\n      \n      \nAll 1 selected check passed.\n", text.stdout)
        _, report = self.repo.snapshot("run", "--stage", "pre-commit", "--only", "printer")
        self.assertEqual(report["checks"][0]["output"], "a\rb\r\nc\x0cd\n\n\n")

    def test_text_report_keeps_output_bytes_under_another_output_encoding(self):
        # A direct run of the cached runner, without -I, inherits PYTHONIOENCODING; the report's bytes stay.
        self.repo.configure({"printer": check(["sh", "-c", "printf '\\303\\251\\n'", "{snapshot}"], ["pre-commit"])})
        self.assertEqual(self.repo.run("prepare").returncode, 0)
        resolved = self.cache / "revisions" / self.repo.main / RUNNER
        text = subprocess.run([sys.executable, "-B", str(resolved), "run", "--stage", "pre-commit", "--only",
                               "printer"], cwd=str(self.repo.path), env=dict(self.repo.env, PYTHONIOENCODING="latin-1"),
                              capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        self.assertIn(b"\n      \xc3\xa9\nAll 1 selected check passed.\n", text.stdout)

    def test_whitespace_ignores_the_clones_core_whitespace(self):
        self.repo.git("config", "core.whitespace", "-blank-at-eol")  # would hide trailing spaces from git diff --check
        self.repo.configure()
        self.repo.write("notes.txt", "trailing \n")
        self.repo.stage("notes.txt")
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit")
        whitespace = {c["id"]: c for c in report["checks"]}["whitespace"]
        self.assertEqual((proc.returncode, whitespace["status"]), (1, "fail"), proc.stderr)
        self.assertIn("notes.txt:1: trailing whitespace.", whitespace["output"])


class SnapshotTest(RunnerCase):
    def test_file_staged_during_the_run_stops_with_preparation_failure(self):
        stager = "printf 'late\\n' > late.txt && git add late.txt"
        self.repo.configure({"stager": check(["sh", "-c", stager, "{snapshot}"], ["pre-commit"])})
        proc, report = self.repo.report("run", "--stage", "pre-commit")
        self.assertEqual((proc.returncode, report["result"]), (2, "error"), proc.stderr)
        self.assertEqual(report["error"], {
            "reference": None, "repair": "review what was staged and commit again",
            "cause": "the staged index changed during the run, so the checks did not see the content Git would commit"})
        self.assertEqual([s["result"] for s in report["snapshots"]], ["pass"])
        self.assertEqual(proc.stderr.splitlines(), [f"repository checks: {report['error']['cause']}; "
                                                    f"{report['error']['repair']}"])

    def test_file_staged_and_restored_during_the_run_keeps_the_snapshot_result(self):
        self.repo.write("f.txt", "original\n")
        self.repo.stage("f.txt")
        self.repo.configure({
            "stage-other": check(["sh", "-c", "printf 'other\\n' > f.txt && git add f.txt", "{snapshot}"],
                                 ["pre-commit"]),
            "reader": check(["git", "show", "{snapshot}:f.txt"], ["pre-commit"]),
            "restore": check(["sh", "-c", "printf 'original\\n' > f.txt && git add f.txt", "{snapshot}"],
                             ["pre-commit"]),
        })
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit")
        self.assertEqual((proc.returncode, report["result"]), (0, "pass"), proc.stderr)
        self.assertEqual({c["id"]: c["output"] for c in report["checks"]}["reader"], "original\n")

    def test_file_staged_during_an_unadopted_run_stops_with_preparation_failure(self):
        # Another session stages a file after the snapshot was built, while the run reads the snapshot's files.
        path = self.racing_git("ls-tree", "printf 'late\\n' > late.txt && \"$REAL\" add late.txt || exit 1")
        proc, report = self.repo.report("run", "--stage", "pre-commit", env=dict(self.repo.env, PATH=path))
        self.assertEqual((proc.returncode, report["result"]), (2, "error"), proc.stderr)
        self.assertEqual(report["error"]["cause"], "the staged index changed during the run, so the checks did not "
                                                   "see the content Git would commit")
        self.assertEqual((report["house_rules"], [(s["base"], s["result"]) for s in report["snapshots"]]),
                         (None, [(None, "pass")]))

    def test_pre_commit_reads_head_once_for_parent_and_base(self):
        self.repo.configure({"changes": check(["git", "diff", "--name-only", "{base}", "{snapshot}"], ["pre-commit"],
                                              scope="diff")})
        self.repo.write("f.txt", "one\n")
        self.repo.stage("f.txt")
        first = self.repo.commit()
        self.repo.write("f.txt", "two\n")
        self.repo.stage("f.txt")
        twin = self.repo.commit()  # its tree equals what stays staged after the reset
        self.repo.git("reset", "-q", "--soft", first)
        self.assertEqual(self.repo.run("prepare").returncode, 0)
        # Another session moves HEAD to the twin after the snapshot was built.
        path = self.racing_git("ls-tree", f'"$REAL" update-ref HEAD {twin} || exit 1')
        resolved = self.cache / "revisions" / self.repo.main / RUNNER  # the resolved runner: no handover rereads HEAD
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit", script=resolved,
                                          env=dict(self.repo.env, PATH=path))
        self.assertEqual(self.repo.git("rev-parse", "HEAD"), twin)
        self.assertEqual((proc.returncode, report["base"], self.repo.git("rev-parse", report["snapshot"] + "^1")),
                         (0, first, first), proc.stderr)
        self.assertEqual({c["id"]: c for c in report["checks"]}["changes"]["output"], "f.txt\n")

    def test_file_staged_during_the_handover_stops_with_preparation_failure(self):
        # Another session stages a file while the installed runner resolves House Rules, before it hands over.
        self.repo.configure(NO_SPEC)
        repo = shlex.quote(str(self.repo.path))
        path = self.racing_git("ls-remote", f"printf 'late\\n' > {repo}/late.txt && \"$REAL\" -C {repo} add late.txt "
                                            "|| exit 1")
        proc, report = self.repo.report("run", "--stage", "pre-commit", env=dict(self.repo.env, PATH=path))
        self.assertEqual((proc.returncode, report["result"]), (2, "error"), proc.stderr)
        self.assertEqual(report["error"]["cause"], "the staged index changed during the run, so the checks did not "
                                                   "see the content Git would commit")
        self.assertEqual([s["result"] for s in report["snapshots"]], ["pass"])
        self.assertEqual(self.repo.git("ls-tree", "--name-only", report["snapshots"][0]["snapshot"], "late.txt"), "")

    def test_file_staged_during_the_handover_of_a_sha256_repository_stops_with_preparation_failure(self):
        probe = subprocess.run(["git", "init", "-q", "--object-format=sha256", str(self.repo.path.parent / "probe")],
                               capture_output=True, stdin=subprocess.DEVNULL, env=base_env())
        if probe.returncode:
            self.skipTest("the installed Git cannot create a SHA-256 repository")
        self.repo = Repo(Path(tempfile.mkdtemp(dir=str(self.folder))), self.house_rules, self.cache,
                         object_format="sha256")
        self.repo.configure(NO_SPEC)
        repo = shlex.quote(str(self.repo.path))
        path = self.racing_git("ls-remote", f"printf 'late\\n' > {repo}/late.txt && \"$REAL\" -C {repo} add late.txt "
                                            "|| exit 1")
        proc, report = self.repo.report("run", "--stage", "pre-commit", env=dict(self.repo.env, PATH=path))
        self.assertEqual((proc.returncode, report["result"]), (2, "error"), proc.stderr)
        self.assertEqual(report["error"]["cause"], "the staged index changed during the run, so the checks did not "
                                                   "see the content Git would commit")
        (snapshot,) = report["snapshots"]
        self.assertEqual(len(snapshot["snapshot"]), 64)
        self.assertEqual(self.repo.git("ls-tree", "--name-only", snapshot["snapshot"], "late.txt"), "")

    def test_index_copy_folder_that_cannot_be_removed_is_a_preparation_failure(self):
        if os.geteuid() == 0:
            self.skipTest("the superuser removes every file")
        self.repo.configure(NO_SPEC)
        cases = [
            ("removal fails", "", r"cannot remove the temporary folder {tmp}/\S+ of the index copy \(.+\)",
             "free space in or repair access to the temporary folder, and run again"),
            ("writing the tree fails, then the removal", "; echo 'fatal: synthetic write failure' >&2; exit 128",
             r"cannot write the staged tree \(fatal: synthetic write failure\); removing the temporary folder "
             r"{tmp}/\S+ of the index copy failed too \(.+\)",
             "run the commit again, and repair the clone if the error repeats"),
        ]
        for name, then, cause, repair in cases:
            with self.subTest(name):
                tmp = Path(tempfile.mkdtemp(dir=str(self.repo.path.parent)))
                self.addCleanup(os.chmod, str(tmp), 0o700)
                # The index copy's folder is made in TMPDIR; once TMPDIR forbids removals, it cannot be removed.
                path = self.racing_git("write-tree", f"chmod 500 {shlex.quote(str(tmp))}{then}")
                proc, report = self.repo.report("run", "--stage", "pre-commit",
                                                env=dict(self.repo.env, PATH=path, TMPDIR=str(tmp)))
                self.assertEqual((proc.returncode, report["result"], report["snapshots"]), (2, "error", []),
                                 proc.stderr)
                self.assertRegex(report["error"]["cause"], r"\A" + cause.format(tmp=re.escape(str(tmp))) + r"\Z")
                self.assertEqual(report["error"]["repair"], repair)

    def test_head_moved_during_the_handover_keeps_the_base(self):
        self.repo.configure({"changes": check(["git", "diff", "--name-only", "{base}", "{snapshot}"], ["pre-commit"],
                                              scope="diff")})
        self.repo.write("f.txt", "one\n")
        self.repo.stage("f.txt")
        first = self.repo.commit()
        self.repo.write("f.txt", "two\n")
        self.repo.stage("f.txt")
        twin = self.repo.commit()  # its tree equals what stays staged after the reset
        self.repo.git("reset", "-q", "--soft", first)
        # Another session moves HEAD to the twin while the installed runner resolves House Rules.
        path = self.racing_git("ls-remote", f'"$REAL" -C {shlex.quote(str(self.repo.path))} update-ref HEAD {twin} '
                                            "|| exit 1")
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit", env=dict(self.repo.env, PATH=path))
        self.assertEqual(self.repo.git("rev-parse", "HEAD"), twin)
        self.assertEqual((proc.returncode, report["base"], self.repo.git("rev-parse", report["snapshot"] + "^1")),
                         (0, first, first), proc.stderr)
        self.assertEqual({c["id"]: c for c in report["checks"]}["changes"]["output"], "f.txt\n")

    def test_unmerged_index_and_old_git_are_preparation_failures(self):
        self.repo.configure()
        self.repo.write("f.txt", "base\n")
        self.repo.stage("f.txt")
        self.repo.commit()
        fake = self.repo.path.parent / "old-git"
        fake.mkdir()
        (fake / "git").write_text('#!/bin/sh\ncase "$1" in --attr-source=*) echo "unknown option: $1" >&2; '
                                  f'exit 129;; esac\nexec {shlex.quote(shutil.which("git"))} "$@"\n')
        (fake / "git").chmod(0o755)
        self.repo.write("f.txt", "changed\n")
        self.repo.stage("f.txt")
        old_git = self.repo.run("run", "--stage", "pre-commit",
                                env=dict(self.repo.env, PATH=f"{fake}{os.pathsep}{os.environ['PATH']}"))
        self.assertPreparationFailure(old_git, "cannot read attributes from a commit (--attr-source)",
                                      "install a Git that supports it")
        self.repo.commit()
        self.repo.git("checkout", "-q", "-b", "side", "HEAD~1")
        self.repo.write("f.txt", "side\n")
        self.repo.stage("f.txt")
        self.repo.commit()
        subprocess.run(["git", "merge", "-q", "main"], cwd=str(self.repo.path), env=self.repo.env,
                       capture_output=True, stdin=subprocess.DEVNULL)
        unmerged = self.repo.run("run", "--stage", "pre-commit")
        self.assertPreparationFailure(unmerged, "the index has unmerged entries (f.txt)",
                                      "resolve the conflicts, stage the result and commit again")


class SelectionTest(RunnerCase):
    LIST = ["git", "ls-tree", "--name-only", "{snapshot}", "--", "{files}"]

    def test_files_check_selects_staged_inputs_by_stage(self):
        self.repo.configure({"ts": check(self.LIST, ["pre-commit", "ci"], ["src/**/*.ts"], scope="files")})
        self.repo.write("src/a.ts", "a\n")
        self.repo.write("src/lib/c.ts", "c\n")
        self.repo.write("tool.py", "x = 1\n")
        self.repo.stage("src", "tool.py")
        self.repo.commit()
        steps = [
            ("stages only a .py file", lambda: self.repo.write("tool.py", "x = 2\n"), ["tool.py"],
             "pre-commit", ("skipped", "no staged input", "")),
            ("stages a .ts file", lambda: self.repo.write("src/lib/b.ts", "b\n"), ["src/lib/b.ts"],
             "pre-commit", ("pass", None, "src/lib/b.ts\n")),
            ("deletes a .ts file", lambda: (self.repo.path / "src/a.ts").unlink(), ["src/a.ts"],
             "pre-commit", ("skipped", "only deleted inputs", "")),
            ("CI on a commit that stages only a .py file", lambda: self.repo.write("tool.py", "x = 3\n"),
             ["tool.py"], "ci", ("pass", None, "src/lib/b.ts\nsrc/lib/c.ts\n")),
        ]
        for name, edit, names, stage, expected in steps:
            with self.subTest(name):
                edit()
                self.repo.stage(*names)
                if stage == "ci":
                    self.repo.commit()
                head = ["--head", "HEAD"] if stage == "ci" else []
                proc, report = self.repo.snapshot("run", "--stage", stage, *head)
                result = {c["id"]: c for c in report["checks"]}["ts"]
                self.assertEqual((result["status"], result["skip_reason"], result["output"]), expected, proc.stderr)
                self.repo.commit()

    def test_required_file_is_not_satisfied_by_a_folder(self):
        self.repo.configure({"probe": check(["git", "rev-parse", "{snapshot}"], ["pre-commit"],
                                            requires=["marker.txt"])})
        self.repo.write("marker.txt/inner.txt", "a folder named like the required file\n")
        self.repo.stage("marker.txt")
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit")
        probe = {c["id"]: c for c in report["checks"]}["probe"]
        self.assertEqual((proc.returncode, probe["status"], probe["skip_reason"]),
                         (0, "skipped", "requires marker.txt"), proc.stderr)

    def test_required_file_is_not_satisfied_by_a_submodule(self):
        self.repo.configure({"probe": check(["git", "rev-parse", "{snapshot}"], ["pre-commit"], requires=["marker"])})
        named = self.repo.commit("a commit the submodule entry names")
        self.repo.git("update-index", "--add", "--cacheinfo", f"160000,{named},marker")  # a gitlink, no file
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit")
        probe = {c["id"]: c for c in report["checks"]}["probe"]
        self.assertEqual((proc.returncode, probe["status"], probe["skip_reason"]),
                         (0, "skipped", "requires marker"), proc.stderr)

    def test_files_check_never_receives_a_submodule(self):
        reader = 'for f; do git cat-file -e "$0:$f" || exit 1; printf "%s\\n" "$f"; done'
        self.repo.configure({"blobs": check(["sh", "-c", reader, "{snapshot}", "{files}"], ["pre-commit", "ci"],
                                            ["lib/**", "vendor"], scope="files")})
        self.repo.write("lib/a.txt", "a\n")
        self.repo.stage("lib/a.txt")
        first = self.repo.commit()
        second = self.repo.commit("another commit for the submodule entry to name")
        steps = [
            ("pre-commit with a submodule and a file staged", ["lib/b.txt"], first, ["--stage", "pre-commit"],
             ("pass", None, "lib/b.txt\n")),
            ("CI on the commit", [], None, ["--stage", "ci", "--head", "HEAD"],
             ("pass", None, "lib/a.txt\nlib/b.txt\n")),
            ("pre-commit with only the submodule staged", [], second, ["--stage", "pre-commit"],
             ("skipped", "no matching input", "")),
        ]
        for name, files, gitlink, args, expected in steps:
            with self.subTest(name):
                for file in files:
                    self.repo.write(file, file + "\n")
                    self.repo.stage(file)
                if gitlink:  # a gitlink: the path holds a commit of another repository, no file
                    self.repo.git("update-index", "--add", "--cacheinfo", f"160000,{gitlink},vendor")
                proc, report = self.repo.snapshot("run", *args)
                result = {c["id"]: c for c in report["checks"]}["blobs"]
                self.assertEqual((result["status"], result["skip_reason"], result["output"]), expected, proc.stderr)
                if args[1] == "pre-commit" and files:
                    self.repo.commit()

    def test_skip_reasons_at_each_stage(self):
        self.repo.configure({
            "whitespace": {"enabled": False, "reason": "Whitespace is checked elsewhere."},
            "ts": check(self.LIST, ["pre-push", "ci"], ["src/**/*.ts"], scope="files"),
            "late": check(["git", "show", "-s", "{snapshot}"], ["ci"])})
        self.repo.write("tool.py", "x = 1\n")
        self.repo.stage("tool.py")
        first = self.repo.commit()
        self.repo.write("tool.py", "x = 2\n")
        self.repo.stage("tool.py")
        second = self.repo.commit()
        cases = [
            ("disabled check", ["--stage", "pre-commit"], None, "whitespace",
             "disabled: Whitespace is checked elsewhere."),
            ("CI files check without a matching file", ["--stage", "ci", "--head", "HEAD"], None, "ts",
             "no matching input"),
            ("push that changes no input", ["--stage", "pre-push"],
             f"refs/heads/main {second} refs/heads/main {first}\n", "ts", "no changed input"),
            ("--only names a check of another stage", ["--stage", "pre-commit", "--only", "late"], None, "late",
             "not configured for pre-commit"),
        ]
        for name, args, lines, identity, reason in cases:
            with self.subTest(name):
                proc, report = self.repo.snapshot("run", *args, input=lines)
                result = {c["id"]: c for c in report["checks"]}[identity]
                self.assertEqual((proc.returncode, result["status"], result["skip_reason"]), (0, "skipped", reason),
                                 proc.stderr)

    def test_budget_warning_when_the_run_exceeds_the_stage_budget(self):
        # Each check sleeps past its budget, so every case warns however loaded the machine is.
        cases = [("configured budget", 0.3, {"pre-commit": {"seconds": 0.05, "reason": "Synthetic tight budget."}},
                  r"budget: pre-commit took \d+\.\d s of 0\.05 s; slowest check sleeper"),
                 ("default 10 s budget", 10.3, None,
                  r"budget: pre-commit took \d+\.\d s of 10 s; slowest check sleeper")]
        for name, seconds, budgets, pattern in cases:
            with self.subTest(name):
                self.repo.configure({"sleeper": check(["sh", "-c", f"sleep {seconds}", "{snapshot}"], ["pre-commit"])},
                                    budgets=budgets)
                proc, report = self.repo.snapshot("run", "--stage", "pre-commit", "--only", "sleeper")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(len(report["warnings"]), 1, report["warnings"])
                self.assertRegex(report["warnings"][0], r"\A" + pattern + r"\Z")


class PushTest(RunnerCase):
    """Pre-push reads Git's pushed reference lines; each pushed commit is its own snapshot."""
    ZERO = "0" * 40

    def setUp(self):
        super().setUp()
        self.remote = self.repo.path.parent / "remote.git"
        git(self.remote.parent, "init", "-q", "--bare", str(self.remote))
        self.repo.configure({
            "whitespace": {"stages": ["pre-commit", "pre-push", "ci"], "reason": "Pushes check whitespace too."},
            "changes": check(["git", "diff", "--name-only", "{base}", "{snapshot}"], ["pre-push"], scope="diff")})
        self.main = self.commit_file("README.md")
        self.repo.git("remote", "add", "origin", str(self.remote))
        self.repo.git("push", "-q", "origin", "main")
        self.repo.git("remote", "set-head", "origin", "main")

    def commit_file(self, name, content=None):
        self.repo.write(name, content or name + "\n")
        self.repo.stage(name)
        return self.repo.commit()

    def line(self, ref, local, remote=None):
        return f"{ref} {local or self.ZERO} {ref} {remote or self.ZERO}\n"

    def push(self, *lines, remote="origin", json_report=True):
        args = ["run", "--stage", "pre-push", *(["--remote", remote] if remote else [])]
        if json_report:
            return self.repo.report(*args, input="".join(lines))
        return self.repo.run(*args, input="".join(lines))

    @staticmethod
    def changes(commit):
        return {c["id"]: c for c in commit["checks"]}["changes"]["output"]

    def header(self, ref, commit, base):
        """The pattern of one pushed snapshot's text header."""
        return re.escape(f"repository checks: pre-push on {ref} at commit {commit[:7]}, base {base[:7]}, "
                         f"House Rules {self.repo.main} (main") + FETCHED

    def test_push_base_is_chosen_per_pushed_commit(self):
        def new_branch():
            self.repo.git("checkout", "-q", "-b", "feature", "main")
            sent = self.commit_file("feature.txt")
            return [self.line("refs/heads/feature", sent)], "origin", "feature.txt\n", sent

        def update_of_a_pushed_branch():
            pushed = self.repo.git("rev-parse", "feature")
            self.repo.git("push", "-q", "origin", "feature")
            sent = self.commit_file("second.txt")
            return [self.line("refs/heads/feature", sent, pushed)], "origin", "second.txt\n", sent

        def rebased_branch():
            self.repo.git("checkout", "-q", "-b", "topic", "main")
            self.commit_file("topic.txt")
            self.repo.git("checkout", "-q", "main")
            self.commit_file("other.txt")
            self.repo.git("push", "-q", "origin", "main")
            self.repo.git("checkout", "-q", "topic")
            self.repo.git("rebase", "-q", "origin/main")
            sent = self.repo.git("rev-parse", "HEAD")
            return [self.line("refs/heads/topic", sent)], "origin", "topic.txt\n", sent

        def annotated_tag():
            sent = self.commit_file("tagged.txt")
            self.repo.git("tag", "-a", "v1", "-m", "Release one", sent)
            tag = self.repo.git("rev-parse", "v1")
            return [self.line("refs/tags/v1", tag)], "origin", "tagged.txt\ntopic.txt\n", sent

        def orphan_branch():
            self.repo.git("checkout", "-q", "--orphan", "lonely")
            sent = self.commit_file("lonely.txt")
            every_file = self.repo.git("ls-tree", "-r", "--name-only", sent) + "\n"
            return [self.line("refs/heads/lonely", sent, self.main)], "origin", every_file, sent

        def no_remote_default_branch():
            sent = self.commit_file("solo.txt")
            every_file = self.repo.git("ls-tree", "-r", "--name-only", sent) + "\n"
            return [self.line("refs/heads/lonely", sent)], None, every_file, sent

        for setup in (new_branch, update_of_a_pushed_branch, rebased_branch, annotated_tag, orphan_branch,
                      no_remote_default_branch):
            with self.subTest(setup.__name__):
                lines, remote, expected, sent = setup()
                proc, report = self.push(*lines, remote=remote)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                (snapshot,) = report["snapshots"]
                self.assertEqual((snapshot["snapshot"], self.changes(snapshot)), (sent, expected))

    def test_commit_made_during_the_push_is_not_checked(self):
        hook = self.repo.path / ".git/hooks/pre-push"
        hook.write_text(
            "#!/bin/sh\n"
            "printf 'late\\n' > late.txt && git add late.txt && git commit -q -m late\n"  # another session commits
            'refs=$(mktemp) || exit 1\ncat > "$refs" || { rm -f "$refs"; exit 1; }\n'
            f'{shlex.quote(sys.executable)} -I {shlex.quote(str(SCRIPT))} run --stage pre-push --remote "$1" '
            '< "$refs" || { status=$?; rm -f "$refs"; exit $status; }\n'
            'exec < "$refs" || { rm -f "$refs"; exit 1; }\nrm -f "$refs"\n')
        hook.chmod(0o755)
        self.repo.git("checkout", "-q", "-b", "feature")
        sent = self.commit_file("feature.txt")
        proc = subprocess.run(["git", "push", "-q", "origin", "feature"], cwd=str(self.repo.path), env=self.repo.env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotEqual(self.repo.git("rev-parse", "HEAD"), sent)
        self.assertRegex(proc.stdout, "(?m)^" + self.header("refs/heads/feature", sent, self.main) + "$")
        self.assertIn("\n      feature.txt\n", proc.stdout)
        self.assertNotIn("late.txt", proc.stdout)

    def test_deleted_reference_is_skipped(self):
        self.repo.git("push", "-q", "origin", "main:old")
        deleted = f"(delete) {self.ZERO} refs/heads/old {self.repo.git('rev-parse', 'origin/old')}\n"
        with self.subTest("deletion beside a pushed branch"):
            self.repo.git("checkout", "-q", "-b", "feature")
            sent = self.commit_file("feature.txt")
            proc, report = self.push(deleted, self.line("refs/heads/feature", sent))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual([(s["reference"], s["snapshot"], self.changes(s)) for s in report["snapshots"]],
                             [("refs/heads/feature", sent, "feature.txt\n")])
        with self.subTest("deletion-only push"):
            proc, report = self.push(deleted)
            self.assertEqual((proc.returncode, report), (0, {"version": 2, "stage": "pre-push", "result": "pass",
                                                             "house_rules": None, "warnings": [],
                                                             "snapshots": []}), proc.stderr)
            proc = self.push(deleted, json_report=False)
            self.assertEqual((proc.returncode, proc.stdout),
                             (0, "nothing to check: the push only deletes references\n"), proc.stderr)

    def test_reference_names_with_unicode_spaces_and_separators_are_checked(self):
        for name in ("refs/heads/no\u00a0break", "refs/heads/line\u2028separator"):
            with self.subTest(name.encode("unicode_escape").decode()):
                git(self.repo.path, "check-ref-format", name)  # a valid reference name
                self.repo.git("checkout", "-q", "-B", "feature", "main")
                sent = self.commit_file("feature.txt")
                proc, report = self.push(self.line(name, sent))
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual([(s["reference"], s["snapshot"], s["result"]) for s in report["snapshots"]],
                                 [(name, sent, "pass")])

    def test_empty_push_input_checks_nothing(self):
        proc, report = self.push()
        self.assertEqual((proc.returncode, report), (0, {"version": 2, "stage": "pre-push", "result": "pass",
                                                         "house_rules": None, "warnings": [], "snapshots": []}),
                         proc.stderr)
        proc = self.push(json_report=False)
        self.assertEqual((proc.returncode, proc.stdout), (0, "nothing to check: the push sends no references\n"),
                         proc.stderr)

    def test_printed_rerun_with_an_empty_tree_base_reruns_the_check(self):
        self.repo.git("checkout", "-q", "--orphan", "lonely")
        sent = self.commit_file("lonely.txt", "trailing \n")
        proc, report = self.push(self.line("refs/heads/lonely", sent))
        (snapshot,) = report["snapshots"]
        self.assertEqual((proc.returncode, snapshot["base"]), (1, EMPTY_TREE), proc.stderr)
        rerun = {c["id"]: c for c in snapshot["checks"]}["whitespace"]["rerun"]
        self.assertIn(f"--head {sent} --base {EMPTY_TREE}", rerun)
        again = subprocess.run(shlex.split(rerun), cwd=str(self.repo.path), env=self.repo.env, capture_output=True,
                               text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(again.returncode, 1, again.stdout + again.stderr)
        self.assertIn("lonely.txt:1: trailing whitespace.", again.stdout)

    def test_offline_push_without_a_fetched_main_is_repaired_by_pushing_again(self):
        self.repo.git("checkout", "-q", "-b", "feature")
        sent = self.commit_file("feature.txt")
        env = dict(self.repo.env, HOUSE_RULES_URL=OFFLINE, HOUSE_RULES_CACHE=str(self.repo.path.parent / "offline"))
        proc, report = self.repo.report("run", "--stage", "pre-push", "--remote", "origin",
                                        input=self.line("refs/heads/feature", sent), env=env)
        self.assertEqual((proc.returncode, report["error"]["reference"], report["error"]["repair"]),
                         (2, "refs/heads/feature",
                          "push again when online; the push fetches House Rules main and builds its environment "
                          "itself"),
                         proc.stderr)
        self.assertTrue(report["error"]["cause"].startswith(f"cannot fetch House Rules main from {OFFLINE} ("),
                        report["error"])

    def test_unwritable_cache_is_a_preparation_failure_that_keeps_earlier_snapshots(self):
        self.repo.git("checkout", "-q", "-b", "plain", "main")
        self.repo.git("rm", "-q", ".agents/checks.json")
        plain = self.repo.commit("drop the configuration")
        self.repo.git("checkout", "-q", "-b", "adopted", "main")
        adopted = self.commit_file("adopted.txt")
        blocker = self.repo.path.parent / "not-a-folder"
        blocker.write_text("a file where the cache folder should be\n")
        lines = self.line("refs/heads/plain", plain) + self.line("refs/heads/adopted", adopted)
        proc, report = self.repo.report("run", "--stage", "pre-push", "--remote", "origin", input=lines,
                                        env=dict(self.repo.env, HOUSE_RULES_CACHE=str(blocker / "cache")))
        self.assertEqual((proc.returncode, report["result"]), (2, "error"), proc.stderr)
        self.assertEqual([(s["reference"], s["snapshot"], s["result"]) for s in report["snapshots"]],
                         [("refs/heads/plain", plain, "pass")])
        error = report["error"]
        self.assertEqual(error["reference"], "refs/heads/adopted")
        self.assertTrue(error["cause"].startswith(f"cannot write the House Rules cache at {blocker / 'cache'} ("),
                        error)
        self.assertEqual(error["repair"],
                         "make that folder writable, or set HOUSE_RULES_CACHE to a writable folder, and run again")
        self.assertEqual(proc.stderr.splitlines(), [f"repository checks: {error['cause']}; {error['repair']}"])

    def test_preparation_failure_inside_a_pushed_snapshot_names_its_reference(self):
        revision = self.house_rules.variant("Require an interpreter that does not exist", {
            "skills/spec-writing/scripts/runtime.json":
                json.dumps({"version": 1, "implementation": "CPython", "requires_python": ">=3.98,<3.99"})})
        self.repo.env["HOUSE_RULES_REVISION"] = revision
        self.repo.git("checkout", "-q", "-b", "plain", "main")
        self.repo.configure({"spec-docs": {"stages": ["pre-commit", "pre-push", "ci"],
                                           "reason": "Pushes check specifications too."}})
        plain = self.repo.commit()
        self.repo.git("checkout", "-q", "-b", "specs")
        self.repo.spec()  # spec-docs now applies, and its environment cannot be prepared
        specs = self.repo.commit()
        proc, report = self.push(self.line("refs/heads/plain", plain), self.line("refs/heads/specs", specs))
        self.assertEqual((proc.returncode, report["result"]), (2, "error"), proc.stderr)
        self.assertEqual([(s["reference"], s["snapshot"], s["result"]) for s in report["snapshots"]],
                         [("refs/heads/plain", plain, "pass")])
        self.assertEqual(report["error"]["reference"], "refs/heads/specs")
        self.assertTrue(report["error"]["cause"].startswith("no supported interpreter for the spec checker"),
                        report["error"])

    def test_pushed_tag_of_a_tree_is_a_preparation_failure(self):
        self.repo.git("tag", "-a", "tree-tag", "-m", "A tagged tree", "HEAD^{tree}")
        proc = self.push(self.line("refs/tags/tree-tag", self.repo.git("rev-parse", "tree-tag")), json_report=False)
        self.assertPreparationFailure(proc, "the pushed reference refs/tags/tree-tag points at",
                                      "resolves to no commit", "change the reference")

    def test_push_of_a_branch_other_than_the_checked_out_one_is_checked(self):
        self.repo.git("checkout", "-q", "-b", "other")
        other = self.commit_file("other.txt")
        self.repo.git("checkout", "-q", "main")
        proc, report = self.push(self.line("refs/heads/other", other))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        (snapshot,) = report["snapshots"]
        self.assertEqual((snapshot["reference"], snapshot["snapshot"], self.changes(snapshot)),
                         ("refs/heads/other", other, "other.txt\n"))

    def test_push_of_two_branches_reports_both_snapshots_and_fails_when_one_fails(self):
        self.repo.git("checkout", "-q", "-b", "good", "main")
        good = self.commit_file("good.txt")
        self.repo.git("checkout", "-q", "-b", "bad", "main")
        bad = self.commit_file("bad.txt", "trailing \n")
        lines = [self.line("refs/heads/good", good), self.line("refs/heads/bad", bad)]
        proc, report = self.push(*lines)
        self.assertEqual((proc.returncode, report["result"]), (1, "fail"))
        self.assertEqual(report["house_rules"]["revision"], self.repo.main)
        self.assertEqual([(s["reference"], s["snapshot"], s["base"], s["result"],
                           {r["id"]: r["status"] for r in s["checks"]}) for s in report["snapshots"]],
                         [("refs/heads/good", good, self.main, "pass", {"whitespace": "pass", "changes": "pass"}),
                          ("refs/heads/bad", bad, self.main, "fail", {"whitespace": "fail", "changes": "pass"})])
        text = self.push(*lines, json_report=False).stdout.splitlines()
        sections = [i for i, line in enumerate(text) if line.startswith("repository checks:")]
        self.assertEqual(len(sections), 2, text)
        for line, ref, commit in zip([text[i] for i in sections], ("refs/heads/good", "refs/heads/bad"), (good, bad)):
            self.assertRegex(line, r"\A" + self.header(ref, commit, self.main) + r"\Z")
        self.assertEqual(text[sections[1] + 1][:16], "FAIL  whitespace")
        self.assertEqual(text[-1], "Push refused: 1 of 4 checks failed. "
                                   "Fix the findings, commit the fixes and push again.")
        rerun = report["snapshots"][1]["checks"][0]["rerun"]
        self.assertIn(f"--head {bad} --base {self.main}", rerun)
        again = subprocess.run(shlex.split(rerun), cwd=str(self.repo.path), env=self.repo.env, capture_output=True,
                               text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(again.returncode, 1, again.stderr)
        self.assertIn("bad.txt:1: trailing whitespace.", again.stdout)

    def test_passing_branch_pushed_with_a_tag_of_a_tree_is_a_preparation_failure(self):
        self.repo.git("checkout", "-q", "-b", "feature")
        sent = self.commit_file("feature.txt")
        self.repo.git("tag", "-a", "tree-tag", "-m", "A tagged tree", "HEAD^{tree}")
        tag = self.repo.git("rev-parse", "tree-tag")
        proc, report = self.push(self.line("refs/heads/feature", sent), self.line("refs/tags/tree-tag", tag))
        self.assertEqual((proc.returncode, report["result"]), (2, "error"), proc.stderr)
        self.assertEqual(report["error"], {
            "reference": "refs/tags/tree-tag",
            "cause": f"the pushed reference refs/tags/tree-tag points at {tag[:7]}, which resolves to no commit",
            "repair": "change the reference, or push it without the hook's check under the rule line"})
        self.assertEqual([(s["reference"], s["snapshot"], s["result"]) for s in report["snapshots"]],
                         [("refs/heads/feature", sent, "pass")])


class SpecDocsTest(RunnerCase):
    def tour_commit_refused(self):
        """The tour: a registered specification whose staged edit uses a rejected form."""
        self.repo.spec(rejected="batch machine")
        self.repo.configure()
        self.repo.commit()
        self.seed_environment()
        self.repo.sentence("The batch machine is fast.")
        self.repo.stage("docs/example.md")
        path = self.repo.path / "docs/example.md"
        path.write_text(path.read_text().replace("batch machine", "batcher"))  # unstaged correction

    def test_refused_commit_reports_like_the_tour_and_changes_nothing(self):
        self.tour_commit_refused()
        self.repo.hook()
        before, head = self.repo.state(), self.repo.git("rev-parse", "HEAD")
        proc = subprocess.run(["git", "commit", "-q", "-m", "uses a rejected form"], cwd=str(self.repo.path),
                              env=self.repo.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              stdin=subprocess.DEVNULL)
        self.assertNotEqual(proc.returncode, 0)
        rerun = shlex.join([sys.executable, str(self.cache / "revisions" / self.repo.main / RUNNER), "run",
                            "--stage", "pre-commit", "--only", "spec-docs"])
        self.assertLines(proc.stdout, [
            re.escape(f"repository checks: pre-commit on the staged index, House Rules {self.repo.main} (main")
            + FETCHED,
            "FAIL  spec-docs    " + DURATION,
            re.escape("      spec-docs: error D13 docs/example.md:") + r"\d+" + re.escape(
                ": rejected form for entity 'example.batcher'; use its registered replacement"),
            re.escape("      spec-docs: 1 error, 0 warnings"),
            re.escape("      fix: " + TOUR_FIX),
            re.escape("      rerun: " + rerun),
            "PASS  whitespace   " + DURATION,
            re.escape("Commit refused: 1 of 2 checks failed. Fix the findings, stage the fixes and commit again."),
        ])
        self.assertEqual((self.repo.state(), self.repo.git("rev-parse", "HEAD")), (before, head))

    def test_refused_commit_json_report(self):
        self.tour_commit_refused()
        proc, report = self.repo.report("run", "--stage", "pre-commit")
        self.assertEqual(proc.returncode, 1)
        head, snapshot = self.repo.git("rev-parse", "HEAD"), report["snapshots"][0]["snapshot"]
        self.assertEqual(self.repo.git("diff", "--cached", "--name-only", snapshot), "")
        spec, whitespace = report["snapshots"][0]["checks"]
        python = Path(spec["command"][0])
        self.assertEqual(python.parent.parent.parent, self.cache / "environments")
        self.assertRegex(spec.pop("output"), r"\Aspec-docs: error D13 docs/example\.md:\d+: rejected form for "
                         r"entity 'example\.batcher'; use its registered replacement\n"
                         r"spec-docs: 1 error, 0 warnings\n\Z")
        runner = str(self.cache / "revisions" / self.repo.main / RUNNER)
        checker = str(self.cache / "revisions" / self.repo.main / "skills/spec-writing/scripts/spec_docs.py")
        for result in (spec, whitespace):
            self.assertGreaterEqual(result.pop("seconds"), 0)
        fetched = report["house_rules"].pop("fetched")
        self.assertRegex(fetched, r"\A" + TIME + r"\Z")
        for warning in report["snapshots"][0].pop("warnings"):  # only a budget warning, which depends on load
            self.assertTrue(warning.startswith("budget: pre-commit took "), warning)
        self.assertEqual(report, {"version": 2, "stage": "pre-commit", "result": "fail",
                                  "house_rules": {"revision": self.repo.main, "source": "main"}, "warnings": [],
                                  "snapshots": [{
            "reference": None, "source": "index", "base": head, "snapshot": snapshot, "result": "fail",
            "checks": [
                {"id": "spec-docs", "status": "fail",
                 "command": [str(python), "-I", checker, "check", "--root", ".", "--rev", snapshot],
                 "fix": TOUR_FIX, "skip_reason": None,
                 "rerun": shlex.join([sys.executable, runner, "run", "--stage", "pre-commit", "--only", "spec-docs"])},
                {"id": "whitespace", "status": "pass", "output": "", "fix": None, "skip_reason": None,
                 "command": ["git", "-c", "core.whitespace=blank-at-eol,space-before-tab,blank-at-eof",
                             f"--attr-source={snapshot}", "diff", "--check", head, snapshot],
                 "rerun": shlex.join([sys.executable, runner, "run", "--stage", "pre-commit", "--only",
                                      "whitespace"])}],
            "overrides": []}]})

    def test_printed_rerun_runs_only_that_check_and_passes_after_the_fix(self):
        self.tour_commit_refused()
        _, report = self.repo.snapshot("run", "--stage", "pre-commit")
        self.repo.stage("docs/example.md")
        proc = subprocess.run(shlex.split(report["checks"][0]["rerun"]), cwd=str(self.repo.path),
                              env=self.repo.env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertLines(proc.stdout, [r"repository checks: .*", "PASS  spec-docs    " + DURATION,
                                       re.escape("      spec-docs: 0 errors, 0 warnings"),
                                       re.escape("All 1 selected check passed.")])

    def test_default_install_preflight_and_hook_match_ci(self):
        self.repo.spec(rejected="batch machine")
        self.repo.configure({"lint": check(["git", "--version"], ["ci"])})
        self.seed_environment()
        proc, preflight = self.repo.snapshot("run", "--stage", "ci", "--index")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(statuses(preflight), {"whitespace": "pass", "spec-docs": "pass", "lint": "skipped"})
        self.assertEqual(preflight["checks"][-1]["skip_reason"], "reads the working tree; runs in CI on the commit")
        self.repo.commit()
        self.repo.sentence("The batch machine is fast.")
        self.repo.stage("docs/example.md")
        _, hook = self.repo.snapshot("run", "--stage", "pre-commit")
        self.repo.commit()
        _, ci = self.repo.snapshot("run", "--stage", "ci", "--head", "HEAD")
        self.assertEqual(statuses(hook), {"spec-docs": "fail", "whitespace": "pass"})
        self.assertEqual(statuses(ci), dict(statuses(hook), lint="pass"))

    def test_naming_override_with_a_stub_linter(self):
        naming = {"id": "component-symbol", "kind": "component", "field": "symbols",
                  "pattern": "[a-z]+(?:[A-Z][a-z0-9]*)*", "message": "Component symbols are lower camel case."}
        self.repo.spec(symbols=["max_upload_bytes"], naming=naming)
        stub = [sys.executable, "-c", "import sys; print('\\n'.join(sys.argv[1:]))", "{files}"]
        self.repo.configure({"code-names": check(stub, ["ci"], ["src/**/*.ts"], scope="files",
                                                 fix="Rename to the convention in .agents/rules.md.")})
        for name in ("src/a.ts", "src/lib/b.ts", "src/readme.md"):
            self.repo.write(name, "export const maxUploadBytes = 1;\n")
            self.repo.stage(name)
        self.repo.commit()
        self.seed_environment()
        proc, report = self.repo.snapshot("run", "--stage", "ci", "--head", "HEAD")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        results = {c["id"]: c for c in report["checks"]}
        self.assertEqual(results["code-names"]["output"], "src/a.ts\nsrc/lib/b.ts\n")
        self.assertIn("error D14 docs/ENTITIES.json", results["spec-docs"]["output"])
        self.assertIn("violating naming rule 'component-symbol'", results["spec-docs"]["output"])


    def planted(self, modules):
        """A folder of Python packages named `modules`, each of which fails as soon as it runs; return its path."""
        folder = Path(tempfile.mkdtemp(dir=str(self.repo.path.parent)))
        for name in modules:
            (folder / name).mkdir()
            failing = f"import sys\nprint('planted {name}', file=sys.stderr)\nsys.exit(3)\n"
            (folder / name / "__init__.py").write_text(failing)
        return folder

    def test_spec_checker_ignores_inherited_python_settings(self):
        self.repo.spec()
        self.repo.configure()
        self.seed_environment()
        env = dict(self.repo.env, PYTHONPATH=str(self.planted(["markdown_it"])))
        proc, report = self.repo.snapshot("run", "--stage", "ci", "--index", "--only", "spec-docs", env=env)
        spec = report["checks"][0]
        self.assertEqual((proc.returncode, spec["status"]), (0, "pass"), spec["output"])

    def test_environment_preparation_ignores_inherited_python_settings(self):
        reason = spec_environment_reason()
        if reason:
            self.skipTest(reason)
        self.repo.spec()
        self.repo.configure()
        # Without an index pip cannot install, so a run that ignores the planted modules stops at pip.
        env = dict(self.repo.env, PYTHONPATH=str(self.planted(["venv", "pip"])), PIP_NO_INDEX="1",
                   PIP_CONFIG_FILE=os.devnull, HOUSE_RULES_CACHE=str(self.repo.path.parent / "isolated-cache"))
        proc, report = self.repo.report("run", "--stage", "ci", "--index", "--only", "spec-docs", env=env)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        cause = report["error"]["cause"]
        self.assertTrue(cause.startswith("cannot build the spec checker's environment (pip exited "), cause)
        self.assertNotIn("planted", cause)


class RevisionTest(RunnerCase):
    """Every run resolves House Rules main once; HOUSE_RULES_REVISION overrides it for one run."""
    IMPOSSIBLE_RUNTIME = {"skills/spec-writing/scripts/runtime.json":
                          json.dumps({"version": 1, "implementation": "CPython", "requires_python": ">=3.98,<3.99"})}

    def own_house_rules(self):
        """A House Rules fixture of this case alone, so moving its main changes no other case."""
        house_rules = HouseRules(Path(tempfile.mkdtemp(dir=str(self.folder))))
        self.repo.env["HOUSE_RULES_URL"] = house_rules.url
        return house_rules

    def fresh_cache(self, name):
        cache = self.repo.path.parent / name
        self.repo.env["HOUSE_RULES_CACHE"] = str(cache)
        return cache

    def test_main_moved_since_the_last_run_is_used(self):
        house_rules = self.own_house_rules()
        cache = self.fresh_cache("moving-cache")
        self.repo.configure(NO_SPEC)
        proc, _, first = self.repo.checked("run", "--stage", "pre-commit")
        self.assertEqual((proc.returncode, first["revision"], first["source"]), (0, house_rules.main, "main"),
                         proc.stderr)
        (house_rules.path / "MOVED").write_text("main moved\n")
        moved = house_rules.commit("Move main")
        earlier = cache / "revisions" / house_rules.main / RUNNER  # a hook set up while the earlier main was current
        proc, entry, second = self.repo.checked("run", "--stage", "pre-commit", script=earlier)
        self.assertEqual((proc.returncode, second["revision"], second["source"]), (0, moved, "main"), proc.stderr)
        self.assertTrue(entry["checks"][0]["rerun"].startswith(
            shlex.join([sys.executable, str(cache / "revisions" / moved / RUNNER)])), entry["checks"][0])

    def test_offline_run_uses_the_cached_main_with_a_warning(self):
        self.fresh_cache("cached-main")
        self.repo.configure(NO_SPEC)
        proc, _, online = self.repo.checked("run", "--stage", "pre-commit")
        self.assertEqual((proc.returncode, online["source"]), (0, "main"), proc.stderr)
        error = "fatal: unable to access the House Rules URL: Could not resolve host"
        fail = f"echo {shlex.quote(error)} >&2; exit 128"
        offline = lambda: dict(self.repo.env, PATH=self.racing_git("ls-remote", fail))
        proc, report = self.repo.report("run", "--stage", "pre-commit", env=offline())
        self.assertEqual((proc.returncode, report["result"], report["house_rules"]),
                         (0, "pass", dict(online, source="cached main")), proc.stderr)
        warning = (f"cannot fetch House Rules main from {self.house_rules.url} ({error}); using the main last fetched, "
                   f"{self.repo.main}, fetched {online['fetched']}")
        self.assertEqual(report["warnings"], [warning])
        text = self.repo.run("run", "--stage", "pre-commit", env=offline()).stdout.splitlines()
        self.assertEqual(text[0], "repository checks: pre-commit on the staged index, "
                                  f"House Rules {self.repo.main} (cached main, fetched {online['fetched']})")
        self.assertEqual(text[-2:], ["warning: " + warning, "All 1 selected check passed; 1 skipped."])

    def test_override_runs_that_revision_for_one_run_and_marks_the_report(self):
        revision = self.house_rules.variant("An earlier revision under test", {"MARK": "variant\n"})
        self.repo.configure(NO_SPEC)
        env = dict(self.repo.env, HOUSE_RULES_REVISION=revision)
        proc, entry, house_rules = self.repo.checked("run", "--stage", "pre-commit", env=env)
        self.assertEqual((proc.returncode, house_rules["revision"], house_rules["source"]), (0, revision, "override"),
                         proc.stderr)
        self.assertRegex(house_rules["fetched"], r"\A" + TIME + r"\Z")
        self.assertTrue(entry["checks"][0]["rerun"].startswith(
            shlex.join([sys.executable, str(self.cache / "revisions" / revision / RUNNER)])), entry["checks"][0])
        self.repo.hook()
        hooked = subprocess.run(["git", "commit", "-q", "-m", "through the hook"], cwd=str(self.repo.path), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(hooked.returncode, 0, hooked.stdout)
        self.assertRegex(hooked.stdout, "(?m)^" + re.escape(
            f"repository checks: pre-commit on the staged index, House Rules {revision} (override "
            f"HOUSE_RULES_REVISION, fetched {house_rules['fetched']})") + "$")
        proc, _, later = self.repo.checked("run", "--stage", "ci", "--head", "HEAD")  # nothing kept the override
        self.assertEqual((proc.returncode, later["revision"], later["source"]), (0, self.repo.main, "main"),
                         proc.stderr)

    def test_resolved_runner_judges_entries_against_its_own_built_ins(self):
        """Revision B adds a built-in and lists whitespace at pre-push; the configuration fits only B."""
        extra = ('    "extra": {"enabled": True, "enforced": True, "scope": "tree", "stages": ["pre-commit", "ci"], '
                 '"paths": ["**"], "requires": [], "run": ["git", "show", "-s", "{snapshot}"], "fix": "Fix it."},\n')
        second = self.house_rules.runner_variant("Change the built-ins", [
            ("BUILTINS = {\n", "BUILTINS = {\n" + extra),
            ('"scope": "diff", "stages": ["pre-commit", "ci"]',
             '"scope": "diff", "stages": ["pre-commit", "pre-push", "ci"]')])
        self.repo.env["HOUSE_RULES_REVISION"] = second
        self.repo.configure({"whitespace": {"stages": ["pre-commit", "pre-push", "ci"]},  # B's default: no reason
                             "extra": {"enabled": False, "reason": "Not needed in this fixture."}})
        proc, report, house_rules = self.repo.checked("run", "--stage", "pre-commit")  # started as the tested runner
        self.assertEqual((proc.returncode, house_rules["revision"]), (0, second), proc.stderr)
        self.assertEqual([(c["id"], c["status"], c["skip_reason"]) for c in report["checks"]],
                         [("whitespace", "pass", None), ("extra", "skipped", "disabled: Not needed in this fixture."),
                          ("spec-docs", "skipped", "requires docs/DOCUMENTS.json")])
        self.assertEqual(report["overrides"], [{"id": "extra", "reason": "Not needed in this fixture.",
                                                "change": "enabled: false"}])
        status = self.repo.run("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual([line for line in status.stdout.splitlines() if line.startswith(("pre-", "ci:", "override:"))],
                         ["pre-commit: whitespace, spec-docs", "pre-push: whitespace", "ci: whitespace, spec-docs",
                          "override: extra enabled: false; reason: Not needed in this fixture."])

    def test_unenforced_built_in_that_fails_warns_and_its_snapshot_passes(self):
        draft = ('    "draft": {"enabled": True, "enforced": False, "scope": "tree", "stages": ["pre-commit", "ci"], '
                 '"paths": ["**"], "requires": [], "run": ["sh", "-c", "echo draft finding; exit 1", "{snapshot}"], '
                 '"fix": "Fix the draft finding."},\n')
        revision = self.house_rules.runner_variant("Add a check that warns first",
                                                   [("BUILTINS = {\n", "BUILTINS = {\n" + draft)])
        self.repo.env["HOUSE_RULES_REVISION"] = revision
        self.repo.configure()
        proc, entry = self.repo.snapshot("run", "--stage", "pre-commit")
        self.assertEqual((proc.returncode, entry["result"]), (0, "pass"), proc.stderr)
        result = {c["id"]: c for c in entry["checks"]}["draft"]
        self.assertEqual((result["status"], result["output"], result["fix"]),
                         ("warn", "draft finding\n", "Fix the draft finding."))
        text = self.repo.run("run", "--stage", "pre-commit")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertLines(text.stdout, [
            re.escape("repository checks: pre-commit on the staged index, "
                      f"House Rules {revision} (override HOUSE_RULES_REVISION") + FETCHED,
            "WARN  draft        " + DURATION, re.escape("      draft finding"),
            re.escape("      fix: Fix the draft finding."), r"      rerun: .* --only draft",
            "PASS  whitespace   " + DURATION,
            re.escape("SKIP  spec-docs    requires docs/DOCUMENTS.json"),
            re.escape("No enforced check failed; 1 of 2 selected checks warned, because House Rules does not "
                      "enforce them yet; 1 skipped.")])
        stages = [line for line in self.repo.run("status").stdout.splitlines() if line.startswith("pre-commit:")]
        self.assertEqual(stages, ["pre-commit: draft (warning only), whitespace, spec-docs"])

    def test_built_in_that_omits_enforced_is_enforced(self):
        plain = ('    "plain": {"enabled": True, "scope": "tree", "stages": ["pre-commit", "ci"], "paths": ["**"], '
                 '"requires": [], "run": ["sh", "-c", "echo plain finding; exit 1", "{snapshot}"], '
                 '"fix": "Fix the plain finding."},\n')
        revision = self.house_rules.runner_variant("Add a built-in without enforced",
                                                   [("BUILTINS = {\n", "BUILTINS = {\n" + plain)])
        self.repo.env["HOUSE_RULES_REVISION"] = revision
        self.repo.configure()
        proc, entry = self.repo.snapshot("run", "--stage", "pre-commit")
        self.assertEqual((proc.returncode, entry["result"], statuses(entry)["plain"]), (1, "fail", "fail"), proc.stderr)
        status = self.repo.run("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("pre-commit: plain, whitespace, spec-docs", status.stdout.splitlines())

    def test_check_that_a_signal_ends_is_not_a_pass(self):
        self.repo.configure({"piped": check(["sh", "-c", "kill -s PIPE $$; echo survived", "{snapshot}"],
                                            ["pre-commit"])})
        proc, entry = self.repo.snapshot("run", "--stage", "pre-commit", "--only", "piped")
        piped = entry["checks"][0]
        self.assertEqual((proc.returncode, piped["status"], piped["output"]), (1, "fail", ""), proc.stderr)

    def test_interrupted_fetch_does_not_block_the_next_run(self):
        # The fetch stops as an interrupted one does: its lock file stays in the repository it fetched into.
        path = self.racing_git("fetch", ': > shallow.lock; echo "fatal: the fetch was interrupted" >&2; exit 128')
        cache = self.fresh_cache("interrupted-cache")
        self.repo.configure(NO_SPEC)
        interrupted = self.repo.run("run", "--stage", "pre-commit", env=dict(self.repo.env, PATH=path))
        self.assertPreparationFailure(interrupted, "cannot fetch House Rules main from",
                                      "fatal: the fetch was interrupted", "run again when online")
        proc, _, resolved = self.repo.checked("run", "--stage", "pre-commit")
        self.assertEqual((proc.returncode, resolved["revision"], resolved["source"]), (0, self.repo.main, "main"),
                         proc.stderr)
        self.assertTrue((cache / "revisions" / self.repo.main / RUNNER).is_file())

    def test_main_lock_is_held_from_asking_for_main_to_its_record(self):
        # The run pauses inside its last Git command before the record, the extraction of main; meanwhile the
        # lock must be taken, so no other run can ask for main, and the record must not exist yet.
        folder = Path(tempfile.mkdtemp(dir=str(self.repo.path.parent)))
        paused, go = folder / "paused", folder / "go"
        pause = (f": > {shlex.quote(str(paused))}; i=0; until [ -e {shlex.quote(str(go))} ]; do sleep 0.1; "
                 "i=$((i+1)); [ $i -lt 600 ] || exit 1; done")
        cache = self.fresh_cache("locked-cache")
        self.repo.configure(NO_SPEC)
        run = subprocess.Popen([sys.executable, "-B", str(SCRIPT), "run", "--stage", "pre-commit", "--json"],
                               cwd=str(self.repo.path), env=dict(self.repo.env, PATH=self.racing_git("archive", pause)),
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(600):
                if paused.exists() or run.poll() is not None:
                    break
                time.sleep(0.1)
            self.assertTrue(paused.exists(), run.poll())
            self.assertFalse((cache / "main.json").exists())
            descriptor = os.open(str(cache / "main.lock"), os.O_RDWR)
            try:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(descriptor)
        finally:
            go.write_text("")
            stdout, stderr = run.communicate()
        self.assertEqual(run.returncode, 0, stderr)
        self.assertEqual(json.loads((cache / "main.json").read_text())["revision"], self.repo.main)

    def test_offline_run_uses_the_latest_fetch_even_after_a_clock_rollback(self):
        house_rules = self.own_house_rules()
        cache = self.fresh_cache("rollback-cache")
        self.repo.configure(NO_SPEC)
        offline = lambda: dict(self.repo.env, PATH=self.racing_git("ls-remote", "echo 'fatal: offline' >&2; exit 128"))
        steps = [("fetch A", None, house_rules.main, "main"), ("offline after A", offline, house_rules.main, "cached main")]
        for name, env, revision, source in steps:
            with self.subTest(name):
                proc, _, resolved = self.repo.checked("run", "--stage", "pre-commit", env=env and env())
                self.assertEqual((proc.returncode, resolved["revision"], resolved["source"]), (0, revision, source),
                                 proc.stderr)
        record = json.loads((cache / "main.json").read_text())
        (cache / "main.json").write_text(json.dumps(dict(record, fetched="2999-01-01T00:00:00Z")))  # clock ran ahead
        (house_rules.path / "MOVED").write_text("main moved\n")
        moved = house_rules.commit("Move main")
        for name, env, revision, source in [("fetch B, timed before A", None, moved, "main"),
                                            ("offline after B", offline, moved, "cached main")]:
            with self.subTest(name):
                proc, _, resolved = self.repo.checked("run", "--stage", "pre-commit", env=env and env())
                self.assertEqual((proc.returncode, resolved["revision"], resolved["source"]), (0, revision, source),
                                 proc.stderr)

    def test_main_and_override_are_fetched_with_depth_1(self):
        # Each fetch's own repository is deleted afterwards, so a Git wrapper reports its history right after the fetch.
        house_rules = self.own_house_rules()
        older = house_rules.commit("A commit with a parent")
        newer = house_rules.commit("Main with history")
        self.fresh_cache("depth-cache")
        log = self.repo.path.parent / "fetches.log"
        wrapper = self.repo.path.parent / "depth-git"
        wrapper.mkdir()
        (wrapper / "git").write_text(
            f"#!/bin/sh\nREAL={shlex.quote(shutil.which('git'))}\n"
            'case " $* " in *" fetch "*) "$REAL" "$@" || exit $?\n'
            f'  {{ "$REAL" rev-parse --is-shallow-repository; "$REAL" rev-list --all --count; }} >> {shlex.quote(str(log))}'
            "\n  exit 0;; esac\nexec \"$REAL\" \"$@\"\n")
        (wrapper / "git").chmod(0o755)
        env = dict(self.repo.env, PATH=f"{wrapper}{os.pathsep}{os.environ['PATH']}")
        self.repo.configure(NO_SPEC)
        for revision, extra in ((newer, {}), (older, {"HOUSE_RULES_REVISION": older})):
            proc, _, resolved = self.repo.checked("run", "--stage", "pre-commit", env=dict(env, **extra))
            self.assertEqual((proc.returncode, resolved["revision"]), (0, revision), proc.stderr)
        self.assertEqual(log.read_text().split(), ["true", "1", "true", "1"])

    def test_failed_removal_of_a_fetch_repository_is_a_preparation_failure(self):
        if os.geteuid() == 0:
            self.skipTest("the superuser removes every file")
        cache = self.fresh_cache("cleanup-cache")
        self.addCleanup(lambda: [os.chmod(folder, 0o755) for folder, _, _ in os.walk(str(cache))])
        # The fetch succeeds, and leaves a file in a folder whose mode forbids removing it.
        path = self.racing_git("fetch", "mkdir locked && : > locked/file && chmod 500 locked || exit 1")
        self.repo.configure(NO_SPEC)
        proc = self.repo.run("run", "--stage", "pre-commit", env=dict(self.repo.env, PATH=path))
        self.assertPreparationFailure(proc, f"cannot write the House Rules cache at {cache} (",
                                      "make that folder writable")

    def test_preparation_failure_survives_a_failed_cleanup(self):
        if os.geteuid() == 0:
            self.skipTest("the superuser removes every file")
        runnerless = self.repo.path.parent / "runnerless"
        git(runnerless.parent, "init", "-q", "-b", "main", str(runnerless))
        git(runnerless, "commit", "-q", "--allow-empty", "-m", "no runner")
        cache = self.fresh_cache("double-failure-cache")
        self.addCleanup(lambda: [os.chmod(folder, 0o755) for folder, _, _ in os.walk(str(cache))])
        path = self.racing_git("fetch", "mkdir locked && : > locked/file && chmod 500 locked || exit 1")
        self.repo.configure(NO_SPEC)
        proc, report = self.repo.report("run", "--stage", "pre-commit", env=dict(
            self.repo.env, PATH=path, HOUSE_RULES_URL="file://" + str(runnerless)))
        self.assertEqual(proc.returncode, 2, proc.stderr)
        cause = report["error"]["cause"]
        self.assertTrue(cause.startswith(f"House Rules {git(runnerless, 'rev-parse', 'HEAD')} has no repository "
                                         "checks runner"), cause)
        self.assertIn("; removing the temporary repository ", cause)
        self.assertEqual(report["error"]["repair"], "set HOUSE_RULES_URL to a House Rules repository whose main has "
                                                    "one, or HOUSE_RULES_REVISION to a revision that has one")

    def test_failed_fetch_survives_a_failed_cleanup(self):
        """Each failed fetch whose repository cannot be removed keeps the repair of the run that fetched."""
        if os.geteuid() == 0:
            self.skipTest("the superuser removes every file")
        self.repo.configure(NO_SPEC)
        pushed = self.repo.commit()
        override = "2" * 40
        cases = [
            ("main at pre-commit", ["--stage", "pre-commit"], None, {},
             f"cannot fetch House Rules main from {self.house_rules.url} (", "run again when online"),
            ("override that the URL lacks", ["--stage", "pre-commit"], None, {"HOUSE_RULES_REVISION": override},
             f"cannot fetch House Rules {override} from {self.house_rules.url} (",
             "run again when online, or set HOUSE_RULES_REVISION to a commit that exists there"),
            ("main at pre-push", ["--stage", "pre-push"], f"refs/heads/main {pushed} refs/heads/main {'0' * 40}\n",
             {}, f"cannot fetch House Rules main from {self.house_rules.url} (",
             "push again when online; the push fetches House Rules main and builds its environment itself"),
        ]
        for number, (name, args, lines, extra, start, repair) in enumerate(cases):
            with self.subTest(name):
                cache = self.fresh_cache(f"fetch-and-cleanup-cache-{number}")
                self.addCleanup(lambda cache=cache: [os.chmod(f, 0o755) for f, _, _ in os.walk(str(cache))])
                # The fetch fails, and leaves a file in a folder whose mode forbids removing it.
                path = self.racing_git("fetch", "mkdir locked && : > locked/file && chmod 500 locked; "
                                                "echo 'fatal: the remote hung up' >&2; exit 128")
                proc, report = self.repo.report("run", *args, input=lines,
                                                env=dict(self.repo.env, PATH=path, **extra))
                self.assertEqual(proc.returncode, 2, proc.stderr)
                cause = report["error"]["cause"]
                self.assertTrue(cause.startswith(start), cause)
                self.assertIn("(fatal: the remote hung up); removing the temporary repository ", cause)
                self.assertEqual(report["error"]["repair"], repair)
        with self.subTest("main at pre-commit with an earlier main in the cache"):
            house_rules = self.own_house_rules()
            cache = self.fresh_cache("fetch-and-cleanup-cache-cached")
            self.addCleanup(lambda: [os.chmod(f, 0o755) for f, _, _ in os.walk(str(cache))])
            self.assertEqual(self.repo.run("prepare").returncode, 0)
            (house_rules.path / "MOVED").write_text("main moved\n")
            house_rules.commit("Move main")
            path = self.racing_git("fetch", "mkdir locked && : > locked/file && chmod 500 locked; "
                                            "echo 'fatal: the remote hung up' >&2; exit 128")
            proc, report = self.repo.report("run", "--stage", "pre-commit", env=dict(self.repo.env, PATH=path))
            self.assertEqual((proc.returncode, report["error"]["repair"]), (2, "run again when online"), proc.stderr)
            self.assertIn("(fatal: the remote hung up); removing the temporary repository ", report["error"]["cause"])

    def test_url_authentication_is_never_printed(self):
        url, shown = "https://tokenuser:s3cr3tpass@127.0.0.1:9/house-rules", "https://127.0.0.1:9/house-rules"
        # Git's error repeats the URL and its user name; the runner must print neither the user name nor the password.
        error = f"fatal: unable to access '{url}/': user tokenuser was refused"
        fail = f"echo {shlex.quote(error)} >&2; exit 128"
        override = "3" * 40
        cases = [("main", "ls-remote", {}, f"cannot fetch House Rules main from {shown} ("),
                 ("override", "fetch", {"HOUSE_RULES_REVISION": override},
                  f"cannot fetch House Rules {override} from {shown} (")]
        self.repo.configure(NO_SPEC)
        for name, command, extra, start in cases:
            with self.subTest(name):
                env = lambda: dict(self.repo.env, HOUSE_RULES_URL=url, PATH=self.racing_git(command, fail),
                                   HOUSE_RULES_CACHE=str(Path(tempfile.mkdtemp(dir=str(self.repo.path.parent)))),
                                   **extra)
                text = self.repo.run("run", "--stage", "pre-commit", env=env())
                proc, report = self.repo.report("run", "--stage", "pre-commit", env=env())
                self.assertEqual((text.returncode, proc.returncode), (2, 2), text.stderr + proc.stderr)
                self.assertEqual(report["error"]["cause"],
                                 f"{start}fatal: unable to access '{shown}/': user *** was refused)")
                for output in (text.stdout, text.stderr, proc.stdout, proc.stderr):
                    self.assertNotIn("s3cr3tpass", output)
                    self.assertNotIn("tokenuser", output)
                self.assertIn(start, text.stderr)

    def test_failure_cause_and_repair_stay_separate_when_a_path_holds_a_separator(self):
        revision = self.house_rules.variant("Require an interpreter that does not exist", self.IMPOSSIBLE_RUNTIME)
        cache = self.fresh_cache("house; cache")
        self.repo.spec()
        self.repo.configure()
        proc, report = self.repo.report("run", "--stage", "pre-commit",
                                        env=dict(self.repo.env, HOUSE_RULES_REVISION=revision))
        self.assertEqual(proc.returncode, 2, proc.stderr)
        prepare = shlex.join([sys.executable, str(cache / "revisions" / revision / RUNNER), "prepare"])
        self.assertEqual(report["error"]["repair"], f"install one, then run `{prepare}`")  # quoted: it holds "; "
        self.assertEqual(report["error"]["cause"],
                         "no supported interpreter for the spec checker: it needs CPython >=3.98,<3.99 on PATH")

    def test_missing_tar_is_a_preparation_failure(self):
        tools = self.repo.path.parent / "tools"
        tools.mkdir()
        os.symlink(shutil.which("git"), str(tools / "git"))
        self.repo.configure()
        proc = self.repo.run("run", "--stage", "pre-commit", env=dict(
            self.repo.env, PATH=str(tools), HOUSE_RULES_CACHE=str(self.repo.path.parent / "tarless-cache")))
        self.assertPreparationFailure(proc, f"cannot start tar to extract House Rules {self.repo.main}",
                                      "install tar and run again")

    def test_preparation_failures_exit_2_with_cause_and_repair(self):
        self.repo.configure()
        runnerless = self.repo.path.parent / "runnerless"
        git(runnerless.parent, "init", "-q", "-b", "main", str(runnerless))
        git(runnerless, "commit", "-q", "--allow-empty", "-m", "no runner")
        fresh = lambda name: str(self.repo.path.parent / name)
        cases = [
            ("offline before main was ever fetched",
             {"HOUSE_RULES_URL": OFFLINE, "HOUSE_RULES_CACHE": fresh("cache-1")},
             [f"repository checks: cannot fetch House Rules main from {OFFLINE} (", "); run again when online\n"]),
            ("main without a runner", {"HOUSE_RULES_URL": "file://" + str(runnerless),
                                       "HOUSE_RULES_CACHE": fresh("cache-2")},
             [f"House Rules {git(runnerless, 'rev-parse', 'HEAD')} has no repository checks runner",
              "set HOUSE_RULES_URL to a House Rules repository whose main has one"]),
            ("invalid override", {"HOUSE_RULES_REVISION": "abc1234"},
             ["HOUSE_RULES_REVISION 'abc1234' is not a full 40-character commit identity",
              "set it to a full commit identity, or unset it to run at House Rules main"]),
            ("override that the URL lacks", {"HOUSE_RULES_REVISION": "1" * 40},
             [f"cannot fetch House Rules {'1' * 40} from {self.house_rules.url} (",
              "run again when online, or set HOUSE_RULES_REVISION to a commit that exists there"]),
        ]
        for name, extra, parts in cases:
            with self.subTest(name):
                self.assertPreparationFailure(self.repo.run("run", "--stage", "pre-commit",
                                                            env=dict(self.repo.env, **extra)), *parts)

    def test_no_supported_interpreter_for_the_spec_checker_is_a_preparation_failure(self):
        # A spec checker that asks for a CPython no machine has, so the case runs on every image.
        revision = self.house_rules.variant("Require an interpreter that does not exist", self.IMPOSSIBLE_RUNTIME)
        tools = self.repo.path.parent / "tools"
        tools.mkdir()
        for name in ("git", "tar"):
            os.symlink(shutil.which(name), str(tools / name))
        self.repo.spec()
        self.repo.configure()
        proc = self.repo.run("run", "--stage", "pre-commit",
                             env=dict(self.repo.env, PATH=str(tools), HOUSE_RULES_REVISION=revision))
        self.assertPreparationFailure(proc, "no supported interpreter for the spec checker",
                                      "install one, then run `", " prepare`")


class StatusTest(RunnerCase):
    def test_status_prints_the_effective_configuration_and_cache_state(self):
        cache = self.repo.path.parent / "status-cache"
        self.repo.env["HOUSE_RULES_CACHE"] = str(cache)
        self.repo.spec()
        self.repo.configure({"spec-docs": {"stages": ["pre-push", "ci"], "reason": "Slow corpus."},
                             "lint": check(["git", "--version"], ["ci"])},
                            budgets={"pre-push": {"seconds": 30, "reason": "Large pushes."}})
        prepare = shlex.join([sys.executable, str(SCRIPT), "prepare"])
        configuration = ["pre-commit: whitespace", "pre-push: spec-docs", "ci: whitespace, spec-docs, lint",
                         'override: spec-docs stages: ["pre-push", "ci"]; reason: Slow corpus.',
                         "budget: pre-push 30 s; reason: Large pushes."]
        revision = cache / "revisions" / self.repo.main
        before = self.repo.run("status")
        self.assertEqual(before.stdout.splitlines(), [
            f"repository checks: House Rules main not fetched yet (run: {prepare})",
            "checks: unavailable until House Rules is prepared, because its runner defines the effective set "
            f"(run: {prepare})"])
        self.assertEqual(self.repo.run("run", "--stage", "ci", "--index", "--only", "whitespace").returncode, 0)
        fetched = json.loads((cache / "main.json").read_text())["fetched"]
        after = self.repo.run("status").stdout.splitlines()  # printed by the resolved runner, from its own built-ins
        self.assertEqual(after[:2], [
            f"repository checks: House Rules {self.repo.main} (cached main, fetched {fetched})",
            f"revision: in the cache at {revision}"])
        self.assertRegex(after[2], r"\Aenvironment: spec checker environment not built at " +
                         re.escape(str(cache / "environments")) + r"/[0-9a-f]{64} \(run: " +
                         re.escape(shlex.join([sys.executable, str(revision / RUNNER), "prepare"])) + r"\)\Z")
        self.assertEqual(after[3:], configuration)

    def test_session_status_line(self):
        install = shlex.join([sys.executable, str(SCRIPT), "install"])
        prepare = shlex.join([sys.executable, str(SCRIPT), "prepare"])
        main = self.repo.main[:7]
        self.repo.env["HOUSE_RULES_CACHE"] = str(self.repo.path.parent / "session-cache")
        hooks = Path(self.repo.root) / ".git/hooks"

        def install_hooks(mode):
            for name in ("pre-commit", "pre-push"):
                (hooks / name).write_text(
                    "#!/bin/sh\n# house-rules:repository-checks:begin\n# house-rules:repository-checks:end\n")
                (hooks / name).chmod(mode)

        prepared = re.escape(f"House Rules {main}, main fetched ") + TIME
        cases = [
            ("unmanaged repository without configuration", lambda: None, ""),
            ("managed repository without configuration", lambda: self.repo.write(".agents/rules.md", "# Rules\n"),
             re.escape(f"repository checks: not installed; run: {install}\n")),
            ("no hooks and main not fetched yet", lambda: self.repo.configure(NO_SPEC),
             re.escape(f"repository checks: not ready: no hook block in pre-commit, pre-push (run: {install}); "
                       f"House Rules main not fetched yet (run: {prepare})\n")),
            ("hooks installed, main prepared", lambda: (install_hooks(0o755), self.repo.run("prepare")),
             re.escape("repository checks: ready (") + prepared + re.escape(", hooks installed)\n")),
            ("hook files not executable, so Git ignores them", lambda: install_hooks(0o644),
             re.escape("repository checks: not ready (") + prepared + re.escape(
                 f"): hook file pre-commit, pre-push not executable "
                 f"(run: chmod +x {hooks / 'pre-commit'} {hooks / 'pre-push'})\n")),
        ]
        for name, setup, expected in cases:
            with self.subTest(name):
                setup()
                proc = self.repo.run("status", "--session")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertRegex(proc.stdout, r"\A" + expected + r"\Z")


class PortabilityTest(unittest.TestCase):
    def test_runner_imports_only_the_standard_library(self):
        tree = ast.parse(SCRIPT.read_text(), feature_version=(3, 9))
        standard = Path(sysconfig.get_path("stdlib")).resolve()
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                modules = [node.module.split(".")[0]]
            for name in modules:
                spec = importlib.util.find_spec(name)
                self.assertIsNotNone(spec, name)
                if spec.origin not in ("built-in", "frozen"):
                    origin = Path(spec.origin).resolve()
                    self.assertTrue(origin.is_relative_to(standard), name)
                    self.assertNotIn("site-packages", origin.parts, name)

    def test_runner_runs_under_python_3_9(self):
        python = python39()
        if python is None:
            self.skipTest("no Python 3.9 interpreter is installed")
        folder = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, str(folder))
        repo = Repo(folder, HouseRules(folder), folder / "cache")
        repo.write("tool.sh", "echo ok\n")
        repo.stage("tool.sh")
        repo.configure()
        proc = repo.run("run", "--stage", "pre-commit", python=python)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines()[-1], "All 1 selected check passed; 1 skipped.")


if __name__ == "__main__":
    unittest.main()
