"""Behavior of the repository checks runner at its command boundary, over temporary Git repositories.

The cases follow the Acceptance chapter of docs/design/194-repository-checks.md. Every House Rules
revision the runner reads comes from a synthetic local clone, so no case needs a network.
"""
import ast
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
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("checks.py")
ROOT = SCRIPT.parents[3]
SPEC = ROOT / "skills/spec-writing"
FIXTURE = SPEC / "scripts/fixtures/minimal/docs"
RUNNER = "skills/repository-checks/scripts/checks.py"
OFFLINE = "file:///nonexistent/house-rules"  # an unreachable source stands for a denied network
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
        self.pin = self.commit("House Rules fixture")

    def commit(self, message):
        git(self.path, "add", ".")
        git(self.path, "commit", "-q", "--allow-empty", "-m", message)
        return git(self.path, "rev-parse", "HEAD")


class Repo:
    def __init__(self, folder, house_rules, cache):
        self.path = folder / "repo"
        self.path.mkdir()
        self.pin = house_rules.pin
        self.env = dict(base_env(), HOUSE_RULES_CACHE=str(cache), HOUSE_RULES_CLONE=str(house_rules.path))
        git(self.path, "init", "-q", "-b", "main")
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

    def configure(self, checks=None, budgets=None, pin=None, url=OFFLINE):
        config = {"version": 1, "house_rules": {"revision": pin or self.pin, "url": url}, "checks": checks or {}}
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
        proc, report = self.report(*args, **kwargs)
        (entry,) = report["snapshots"]
        if report["result"] != entry["result"]:
            raise AssertionError(f"run result {report['result']} differs from its one snapshot's: {report}")
        return proc, entry

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
    return dict(run=list(run), stages=list(stages), paths=list(paths), reason="A synthetic repository check.",
                **extra)


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
        lines = text.rstrip("\n").split("\n")
        self.assertEqual(len(lines), len(patterns), text)
        for line, pattern in zip(lines, patterns):
            self.assertRegex(line, r"\A" + pattern + r"\Z")

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
            re.escape(f"repository checks: pre-commit on the staged index, House Rules {self.repo.pin[:7]} (pinned)"),
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
            "short revision": ({}, "abc1234", "house_rules.revision must be a full 40-character commit identity"),
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
        }
        for name, (change, revision, message) in cases.items():
            with self.subTest(name):
                config = {"version": 1, "house_rules": {"revision": revision or self.repo.pin, "url": OFFLINE},
                          "checks": {}}
                config.update(change)
                self.repo.write(".agents/checks.json", json.dumps(config))
                self.repo.stage(".agents/checks.json")
                proc = self.repo.run("run", "--stage", "pre-commit")
                self.assertPreparationFailure(proc, "configuration error in .agents/checks.json: " + message,
                                              "fix the file through a reviewed change")

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

    def test_check_queue_command_starts_each_check(self):
        queue = self.repo.path.parent / "queue"
        queue.write_text('#!/bin/sh\necho "queued: $1"\nexec "$@"\n')
        queue.chmod(0o755)
        self.repo.configure()
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit",
                                        env=dict(self.repo.env, HOUSE_RULES_CHECK_QUEUE=str(queue)))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["checks"][0]["output"], "queued: git\n")


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
        self.assertEqual((proc.returncode, report["result"], report["warnings"]), (0, "pass", []), proc.stderr)
        self.assertEqual({c["id"]: c["output"] for c in report["checks"]}["reader"], "original\n")

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

    def test_budget_warning_when_the_run_exceeds_the_stage_budget(self):
        self.repo.write("tool.sh", "echo ok\n")
        self.repo.stage("tool.sh")
        cases = [("default 10 s budget", None, []),
                 ("configured budget", {"pre-commit": {"seconds": 0.001, "reason": "Synthetic tight budget."}},
                  [r"budget: pre-commit took \d+\.\d s of 0\.001 s; slowest check whitespace"])]
        for name, budgets, expected in cases:
            with self.subTest(name):
                self.repo.configure(budgets=budgets)
                _, report = self.repo.snapshot("run", "--stage", "pre-commit")
                self.assertEqual(len(report["warnings"]), len(expected), report["warnings"])
                for warning, pattern in zip(report["warnings"], expected):
                    self.assertRegex(warning, r"\A" + pattern + r"\Z")


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

    def header(self, ref, commit, base, pin=None):
        return (f"repository checks: pre-push on {ref} at commit {commit[:7]}, base {base[:7]}, "
                f"House Rules {(pin or self.repo.pin)[:7]} (pinned)")

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
        self.assertIn(self.header("refs/heads/feature", sent, self.main) + "\n", proc.stdout)
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
            self.assertEqual((proc.returncode, report), (0, {"version": 1, "stage": "pre-push", "result": "pass",
                                                             "snapshots": []}), proc.stderr)
            proc = self.push(deleted, json_report=False)
            self.assertEqual((proc.returncode, proc.stdout),
                             (0, "nothing to check: the push only deletes references\n"), proc.stderr)

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
        self.assertEqual([(s["reference"], s["snapshot"], s["base"], s["house_rules"], s["result"],
                           {r["id"]: r["status"] for r in s["checks"]}) for s in report["snapshots"]],
                         [("refs/heads/good", good, self.main, self.repo.pin, "pass",
                           {"whitespace": "pass", "changes": "pass"}),
                          ("refs/heads/bad", bad, self.main, self.repo.pin, "fail",
                           {"whitespace": "fail", "changes": "pass"})])
        text = self.push(*lines, json_report=False).stdout.splitlines()
        sections = [i for i, line in enumerate(text) if line.startswith("repository checks:")]
        self.assertEqual([text[i] for i in sections], [self.header("refs/heads/good", good, self.main),
                                                       self.header("refs/heads/bad", bad, self.main)])
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

    def test_pushed_commits_with_different_pins_are_a_preparation_failure(self):
        first = self.repo.pin
        (self.house_rules.path / "MOVED").write_text("revision B\n")
        second = self.house_rules.commit("Move the pin")
        self.repo.git("checkout", "-q", "-b", "old-pin", "main")
        old = self.commit_file("old.txt")
        self.repo.git("checkout", "-q", "-b", "new-pin", "main")
        self.repo.configure(pin=second)
        new = self.commit_file("new.txt")
        proc, report = self.push(self.line("refs/heads/old-pin", old), self.line("refs/heads/new-pin", new))
        self.assertEqual((proc.returncode, report["result"]), (2, "error"), proc.stderr)
        self.assertEqual(report["error"], {
            "reference": "refs/heads/new-pin", "repair": "push them separately",
            "cause": f"the pushed commits pin different House Rules revisions ({first[:7]}, {second[:7]})"})
        self.assertEqual([(s["reference"], s["house_rules"], s["result"]) for s in report["snapshots"]],
                         [("refs/heads/old-pin", first, "pass")])


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
        rerun = shlex.join([sys.executable, str(self.cache / "revisions" / self.repo.pin / RUNNER), "run",
                            "--stage", "pre-commit", "--only", "spec-docs"])
        self.assertLines(proc.stdout, [
            re.escape(f"repository checks: pre-commit on the staged index, House Rules {self.repo.pin[:7]} (pinned)"),
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
        runner = str(self.cache / "revisions" / self.repo.pin / RUNNER)
        for result in (spec, whitespace):
            self.assertGreaterEqual(result.pop("seconds"), 0)
        self.assertEqual(report, {"version": 1, "stage": "pre-commit", "result": "fail", "snapshots": [{
            "reference": None, "source": "index", "house_rules": self.repo.pin,
            "base": head, "snapshot": snapshot, "result": "fail",
            "checks": [
                {"id": "spec-docs", "status": "fail",
                 "command": [str(python), str(self.cache / "revisions" / self.repo.pin /
                                              "skills/spec-writing/scripts/spec_docs.py"),
                             "check", "--root", ".", "--rev", snapshot],
                 "fix": TOUR_FIX, "skip_reason": None,
                 "rerun": shlex.join([sys.executable, runner, "run", "--stage", "pre-commit", "--only", "spec-docs"])},
                {"id": "whitespace", "status": "pass", "output": "", "fix": None, "skip_reason": None,
                 "command": ["git", f"--attr-source={snapshot}", "diff", "--check", head, snapshot],
                 "rerun": shlex.join([sys.executable, runner, "run", "--stage", "pre-commit", "--only",
                                      "whitespace"])}],
            "overrides": [], "warnings": []}]})

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


class PinningTest(RunnerCase):
    def offline(self, cache=None, **extra):
        env = {k: v for k, v in self.repo.env.items() if k != "HOUSE_RULES_CLONE"}
        env.update(extra)
        if cache:
            env["HOUSE_RULES_CACHE"] = str(cache)
        return env

    def test_pin_move_runs_the_pinned_revision_without_network(self):
        first = self.house_rules.pin
        (self.house_rules.path / "MOVED").write_text("revision B\n")
        second = self.house_rules.commit("Move the pin")
        no_spec = {"spec-docs": {"enabled": False, "reason": "No specifications in this fixture."}}
        for pin in (first, second):
            self.repo.configure(no_spec, pin=pin)
            self.assertEqual(self.repo.run("prepare").returncode, 0)
        old_runner = self.cache / "revisions" / first / RUNNER
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit", script=old_runner, env=self.offline())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["house_rules"], second)
        self.assertTrue(report["checks"][0]["rerun"].startswith(
            shlex.join([sys.executable, str(self.cache / "revisions" / second / RUNNER)])), report["checks"][0])

    def test_preparation_failures_exit_2_with_cause_and_repair(self):
        self.repo.configure()
        empty = self.repo.path.parent / "empty-clone"
        git(empty.parent, "init", "-q", str(empty))
        runnerless = self.repo.path.parent / "runnerless"
        git(runnerless.parent, "init", "-q", "-b", "main", str(runnerless))
        git(runnerless, "commit", "-q", "--allow-empty", "-m", "no runner")
        fresh = lambda name: self.repo.path.parent / name
        prepare = shlex.join([sys.executable, str(SCRIPT), "prepare"])
        cases = [
            ("pin missing from the cache, network denied", [], self.offline(fresh("cache-1")), None,
             [f"cannot fetch House Rules {self.repo.pin} from {OFFLINE}", f"run `{prepare}` when online"]),
            ("clone without the pin", [], dict(self.repo.env, HOUSE_RULES_CLONE=str(empty),
                                               HOUSE_RULES_CACHE=str(fresh("cache-2"))), None,
             [f"does not contain House Rules {self.repo.pin}", "fetch it there, or unset HOUSE_RULES_CLONE"]),
            ("pinned revision without a runner", [], dict(self.repo.env, HOUSE_RULES_CLONE=str(runnerless),
                                                          HOUSE_RULES_CACHE=str(fresh("cache-3"))),
             git(runnerless, "rev-parse", "HEAD"), ["has no repository checks runner", "pin a revision that has one"]),
            ("House Rules checkout at another revision", ["--house-rules", str(self.house_rules.path)],
             self.repo.env, "1" * 40, ["is at", "not the pin 1111111", "check out the pinned revision there"]),
        ]
        for name, extra, env, pin, parts in cases:
            with self.subTest(name):
                self.repo.configure(pin=pin)
                self.assertPreparationFailure(self.repo.run("run", "--stage", "pre-commit", *extra, env=env), *parts)

    def test_no_supported_interpreter_for_the_spec_checker_is_a_preparation_failure(self):
        # A pinned spec checker that asks for a CPython no machine has, so the case runs on every image.
        (self.house_rules.path / "skills/spec-writing/scripts/runtime.json").write_text(json.dumps(
            {"version": 1, "implementation": "CPython", "requires_python": ">=3.98,<3.99"}))
        pin = self.house_rules.commit("Require an interpreter that does not exist")
        tools = self.repo.path.parent / "tools"
        tools.mkdir()
        for name in ("git", "tar"):
            os.symlink(shutil.which(name), str(tools / name))
        self.repo.spec()
        self.repo.configure(pin=pin)
        proc = self.repo.run("run", "--stage", "pre-commit", env=dict(self.repo.env, PATH=str(tools)))
        self.assertPreparationFailure(proc, "no supported interpreter for the spec checker",
                                      "install one, then run `", " prepare`")


class StatusTest(RunnerCase):
    def test_status_prints_the_effective_configuration_and_cache_state(self):
        self.repo.spec()
        self.repo.configure({"spec-docs": {"stages": ["pre-push", "ci"], "reason": "Slow corpus."},
                             "lint": check(["git", "--version"], ["ci"])},
                            budgets={"pre-push": {"seconds": 30, "reason": "Large pushes."}})
        prepare = shlex.join([sys.executable, str(SCRIPT), "prepare"])
        configuration = ["pre-commit: whitespace", "pre-push: spec-docs", "ci: whitespace, spec-docs, lint",
                         'override: spec-docs stages: ["pre-push", "ci"]; reason: Slow corpus.',
                         "budget: pre-push 30 s; reason: Large pushes."]
        revision = self.cache / "revisions" / self.repo.pin
        before = self.repo.run("status")
        self.assertEqual(before.stdout.splitlines(), [
            f"repository checks: House Rules {self.repo.pin} (pinned)",
            f"revision: pinned revision {self.repo.pin[:7]} not in the cache (run: {prepare})", *configuration])
        self.assertEqual(self.repo.run("run", "--stage", "ci", "--index", "--only", "whitespace").returncode, 0)
        after = self.repo.run("status").stdout.splitlines()
        self.assertEqual(after[1], f"revision: in the cache at {revision}")
        self.assertRegex(after[2], r"\Aenvironment: spec checker environment not built at " +
                         re.escape(str(self.cache / "environments")) + r"/[0-9a-f]{64} \(run: " +
                         re.escape(prepare) + r"\)\Z")
        self.assertEqual(after[3:], configuration)

    def test_session_status_line(self):
        install = shlex.join([sys.executable, str(SCRIPT), "install"])
        prepare = shlex.join([sys.executable, str(SCRIPT), "prepare"])
        pin = self.repo.pin[:7]
        self.repo.env["HOUSE_RULES_CACHE"] = str(self.repo.path.parent / "session-cache")
        no_spec = {"spec-docs": {"enabled": False, "reason": "No specifications in this fixture."}}

        def hooks():
            for name in ("pre-commit", "pre-push"):
                (self.repo.path / ".git/hooks" / name).write_text(
                    "#!/bin/sh\n# house-rules:repository-checks:begin\n# house-rules:repository-checks:end\n")

        cases = [
            ("unmanaged repository without configuration", lambda: None, ""),
            ("managed repository without configuration", lambda: self.repo.write(".agents/rules.md", "# Rules\n"),
             f"repository checks: not installed; run: {install}\n"),
            ("no hooks and pinned revision missing", lambda: self.repo.configure(no_spec),
             f"repository checks: not ready (House Rules {pin}): no hook block in pre-commit, pre-push "
             f"(run: {install}); pinned revision {pin} not in the cache (run: {prepare})\n"),
            ("hooks installed, revision prepared",
             lambda: (hooks(), self.repo.run("prepare")),
             f"repository checks: ready (House Rules {pin}, hooks installed)\n"),
        ]
        for name, setup, expected in cases:
            with self.subTest(name):
                setup()
                proc = self.repo.run("status", "--session")
                self.assertEqual((proc.returncode, proc.stdout), (0, expected), proc.stderr)


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
