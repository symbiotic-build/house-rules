"""Behavior of the repository checks runner at its command boundary, over temporary Git repositories.

The cases follow the Acceptance chapter of docs/design/194-repository-checks.md. Every House Rules
revision the runner reads comes from a synthetic local clone that each test configuration names by a file:// URL
in its sources, so no case needs a network.
"""
import ast
import fcntl
import hashlib
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
FETCHED = r", cached " + TIME + r"\)"  # the end of a text header after its revision source
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
TOUR_FIX = ("apply the remedy for each code in the spec checker's diagnostic table, "
            "run spec_docs.py generate, stage the result")
DURATION = r"\d+\.\d s"
VERSION = r"      version: (?:\S+@[0-9a-f]{12} ?)+"


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
        self.url, self.ref = house_rules.url, "main"  # the House Rules source the next configure() names
        self.config = None
        self.env = dict(base_env(), HOUSE_RULES_CACHE=str(cache))
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
        config = {"version": 2, "sources": [{"name": "house-rules", "url": self.url, "ref": self.ref}],
                  "checks": checks or {}}
        if budgets:
            config["budgets"] = budgets
        self.write_config(config)

    def write_config(self, config):
        self.config = config
        self.write("house-rules.json", json.dumps(config, indent=2) + "\n")
        self.stage("house-rules.json")

    def reconfigure(self, url=None, ref=None):
        """Stage the last configuration again with another House Rules URL or ref."""
        self.url, self.ref = url or self.url, ref or self.ref
        self.write_config(dict(self.config, sources=[{"name": "house-rules", "url": self.url, "ref": self.ref}]))

    def header(self, revision, source="fetched branch main", url=None):
        """The text header's House Rules part after its revision: where the commit came from and the URL."""
        return re.escape(f"House Rules {revision} ({source} of {url or self.url}") + FETCHED

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
        """Like `snapshot`, and also return the run's House Rules layer."""
        proc, report = self.report(*args, **kwargs)
        (entry,) = report["snapshots"]
        if report["result"] != entry["result"]:
            raise AssertionError(f"run result {report['result']} differs from its one snapshot's: {report}")
        (layer,) = report["layers"]
        return proc, entry, layer

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


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()


def source_folder(cache, url):
    """The cache folder of a source: sources/<SHA-256 of its URL as written>."""
    return Path(cache, "sources", sha256_hex(url))


def branch_record(cache, url, ref="main"):
    """The cache's record of the commit last resolved for one source and branch."""
    return source_folder(cache, url) / "branches" / (sha256_hex(ref) + ".json")


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
            re.escape("repository checks: pre-commit on the staged index, ") + self.repo.header(self.repo.main),
            "PASS  whitespace   " + DURATION,
            VERSION,
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
            "unsupported version": ({"version": 3}, None, "unsupported version 3; this runner reads version 2"),
            "version 1": ({"version": 1}, None, "unsupported version 1; this runner reads version 2"),
            "house_rules field of an earlier design": (
                {"house_rules": {"revision": "1" * 40, "url": OFFLINE}}, None, "the file has unknown field house_rules"),
            "no sources": ({"sources": None}, None, "the file lacks sources"),
            "a second source layer": (
                {"sources": [{"name": "house-rules", "url": OFFLINE, "ref": "main"},
                             {"name": "team-rules", "url": OFFLINE, "ref": "main"}]},
                "remove the extra entry from sources in house-rules.json",
                "house-rules: house-rules.json: custom source layers are not supported by this runner yet (#217)"),
            "a first layer that is not House Rules": (
                {"sources": [{"name": "team-rules", "url": OFFLINE, "ref": "main"}]}, None,
                'sources[0].name must be "house-rules": the first layer is House Rules'),
            "a ref that is no branch name": (
                {"sources": [{"name": "house-rules", "url": OFFLINE, "ref": "bad..ref"}]}, None,
                "sources[0].ref must be a branch name or a full commit identity of 40 hexadecimal digits, "
                "not 'bad..ref'"),
            "a ref that check-ref-format --branch refuses": (
                {"sources": [{"name": "house-rules", "url": OFFLINE, "ref": "HEAD"}]}, None,
                "sources[0].ref must be a branch name or a full commit identity of 40 hexadecimal digits, "
                "not 'HEAD'"),
            "a 64-digit commit ref, which would need a SHA-256 source": (
                {"sources": [{"name": "house-rules", "url": OFFLINE, "ref": "3" * 64}]},
                "use the source's SHA-1 commit or a branch, through a reviewed change",
                "sources[0].ref names a 64-digit commit; SHA-256 sources are not supported yet"),
            "a URL with a user name and password": (
                {"sources": [{"name": "house-rules", "url": "https://user:secret@host.invalid/x", "ref": "main"}]},
                "use a Git credential helper", "the House Rules URL in house-rules.json carries credentials"),
            "an https URL with a user name": (
                {"sources": [{"name": "house-rules", "url": "https://user@host.invalid/x", "ref": "main"}]},
                "use a Git credential helper", "the House Rules URL in house-rules.json carries credentials"),
            "an http URL with a user name": (
                {"sources": [{"name": "house-rules", "url": "http://user@host.invalid/x", "ref": "main"}]},
                "use a Git credential helper", "the House Rules URL in house-rules.json carries credentials"),
            "an ssh URL with a password": (
                {"sources": [{"name": "house-rules", "url": "ssh://git:secret@host.invalid/x", "ref": "main"}]},
                "use a Git credential helper", "the House Rules URL in house-rules.json carries credentials"),
            "a git_settings field, which this runner does not read": (
                {"git_settings": {"core.whitespace": {"value": "-blank-at-eol", "reason": "x"}}}, None,
                "the file has unknown field git_settings"),
            "entry that sets enforced": ({"checks": {"whitespace": {"enforced": False, "reason": "x"}}}, None,
                                         "checks.whitespace has unknown field enforced"),
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
                "the file holds text that cannot be printed or passed to a program"),
            "reason that cannot be printed": (
                {"checks": {"whitespace": {"enabled": False, "reason": "off \udbff"}}}, None,
                "the file holds text that cannot be printed or passed to a program"),
            "NUL character in a check identity": ({"checks": {"li\0nt": check(["lint", "{snapshot}"], ["ci"])}}, None,
                                                  "checks has an identity with a NUL character: li\\x00nt"),
            "repository check without fix": (
                {"checks": {"lint": {k: v for k, v in check(["lint"], ["ci"]).items() if k != "fix"}}}, None,
                "checks.lint lacks fix"),
        }
        for name, (change, repair, message) in cases.items():
            with self.subTest(name):
                config = {"version": 2, "sources": [{"name": "house-rules", "url": self.repo.url, "ref": "main"}],
                          "checks": {}}
                config.update(change)
                config = {k: v for k, v in config.items() if v is not None}
                self.repo.write("house-rules.json", json.dumps(config))
                self.repo.stage("house-rules.json")
                proc = self.repo.run("run", "--stage", "pre-commit")
                expected = message if message.startswith(("house-rules: ", "the House Rules URL")) else (
                    "configuration error in house-rules.json: " + message)
                self.assertPreparationFailure(proc, expected, repair or "fix the file through a reviewed change")

    def test_text_that_cannot_be_printed_is_refused_and_never_shown(self):
        self.repo.url = "https://example.invalid/house-rules"
        self.repo.configure(dict(NO_SPEC, lint=check(["lint", "private-marker \ud800", "{snapshot}"], ["ci"])))
        cause = "configuration error in house-rules.json: the file holds text that cannot be printed or passed to a program"
        text = self.repo.run("run", "--stage", "pre-commit")
        proc, report = self.repo.report("run", "--stage", "pre-commit")
        self.assertEqual((text.returncode, text.stderr), (2, f"repository checks: {cause}; fix the file through a "
                                                             "reviewed change\n"))
        self.assertEqual((proc.returncode, report["error"]["cause"]), (2, cause))
        for output in (text.stdout, text.stderr, proc.stdout, proc.stderr):
            self.assertNotIn("private-marker", output)

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

    def test_working_tree_check_sees_the_checkout(self):
        reader = check(["sh", "-c", "git status --porcelain; echo done"], ["ci"])  # no {snapshot}: CI only
        self.repo.configure(dict(NO_SPEC, tree=reader))
        self.repo.write("notes.txt", "notes\n")
        self.repo.stage("notes.txt")
        self.repo.commit()
        proc, entry = self.repo.snapshot("run", "--stage", "ci", "--head", "HEAD", "--only", "tree")
        self.assertEqual((proc.returncode, entry["checks"][0]["output"]), (0, "done\n"), proc.stderr)
        self.repo.write("notes.txt", "changed\n")  # the check reads the checkout's files and index
        proc, entry = self.repo.snapshot("run", "--stage", "ci", "--head", "HEAD", "--only", "tree")
        self.assertEqual((proc.returncode, entry["checks"][0]["output"]), (0, " M notes.txt\ndone\n"), proc.stderr)

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

    def test_check_queue_command_runs_without_personal_git_configuration(self):
        queue = self.repo.path.parent / "queue"
        queue.write_text('#!/bin/sh\necho "queue sees: $(git config --get user.name || echo no name)"\nexec "$@"\n')
        queue.chmod(0o755)
        name = check(["sh", "-c", 'git config --get user.name || echo "check sees: no name"', "{snapshot}"],
                     ["pre-commit"])
        self.repo.configure(dict(NO_SPEC, name=name))
        personal = self.repo.path.parent / "global-config"
        personal.write_text("[user]\n\tname = Personal User\n")
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit", "--only", "name", env=dict(
            self.repo.env, HOUSE_RULES_CHECK_QUEUE=str(queue), GIT_CONFIG_GLOBAL=str(personal)))
        self.assertEqual((proc.returncode, report["checks"][0]["output"]),
                         (0, "queue sees: no name\ncheck sees: no name\n"), proc.stderr)

    def test_program_on_a_relative_path_entry_is_versioned_from_the_repository_root(self):
        self.repo.write("bin/lint", "#!/bin/sh\necho linted\n")
        (self.repo.path / "bin/lint").chmod(0o755)
        self.repo.write("sub/file.txt", "text\n")
        self.repo.stage("bin/lint", "sub/file.txt")
        self.repo.configure({"lint": check(["lint", "{snapshot}"], ["pre-commit"])})
        env = dict(self.repo.env, PATH=f"bin{os.pathsep}{os.environ['PATH']}")
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit", "--only", "lint", cwd=self.repo.path / "sub",
                                          env=env)
        lint = {c["id"]: c for c in report["checks"]}["lint"]
        program = os.path.join(self.repo.root, "bin", "lint")
        self.assertEqual((proc.returncode, lint["status"], lint["output"], lint["version"]),
                         (0, "pass", "linted\n", [{"path": program, "sha256": sha256(program)}]), proc.stderr)

    def test_check_whose_version_file_cannot_be_read_is_an_error_and_the_others_run(self):
        if os.geteuid() == 0:
            self.skipTest("the superuser reads every file")
        self.repo.write("tools/lint.sh", "echo linted\n")
        script = self.repo.path / "tools/lint.sh"
        script.chmod(0)
        self.addCleanup(script.chmod, 0o644)
        self.repo.configure({"first": check(["sh", "-c", "echo first finding; exit 1", "{snapshot}"], ["pre-commit"]),
                             "lint": check(["sh", "tools/lint.sh", "{snapshot}"], ["pre-commit"])})
        proc, entry = self.repo.snapshot("run", "--stage", "pre-commit")
        results = {c["id"]: c for c in entry["checks"]}
        self.assertEqual((proc.returncode, entry["result"], results["first"]["status"], results["whitespace"]["status"]),
                         (1, "fail", "fail", "pass"), proc.stderr)
        self.assertEqual((results["lint"]["status"], results["lint"]["output"]),
                         ("error", "version unreadable: tools/lint.sh (Permission denied)\n"))
        text = self.repo.run("run", "--stage", "pre-commit")
        self.assertEqual(text.returncode, 1, text.stderr)
        self.assertIn("\nERROR lint         ", text.stdout)
        self.assertIn("\n      version unreadable: tools/lint.sh (Permission denied)\n", text.stdout)

    def test_check_whose_version_file_is_in_a_folder_that_cannot_be_searched_is_an_error(self):
        if os.geteuid() == 0:
            self.skipTest("the superuser searches every folder")
        self.repo.write("tools/locked/lint.sh", "echo linted\n")
        folder = self.repo.path / "tools/locked"
        folder.chmod(0o600)  # readable listing, but no search permission: no lookup of the script can succeed
        self.addCleanup(folder.chmod, 0o755)
        self.repo.configure({"lint": check(["sh", "tools/locked/lint.sh", "{snapshot}"], ["pre-commit"])})
        proc, entry = self.repo.snapshot("run", "--stage", "pre-commit", "--only", "lint")
        lint = entry["checks"][0]
        self.assertEqual((proc.returncode, lint["status"], lint["output"]),
                         (1, "error", "version unreadable: tools/locked/lint.sh (Permission denied)\n"), proc.stderr)

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
        self.repo.configure(dict(NO_SPEC, printer=check(["sh", "-c", "printf '\\303\\251\\n'", "{snapshot}"],
                                                        ["pre-commit"])))
        self.assertEqual(self.repo.run("prepare").returncode, 0)
        resolved = self.cache / "revisions" / self.repo.main / RUNNER
        text = subprocess.run([sys.executable, "-B", str(resolved), "run", "--stage", "pre-commit", "--only",
                               "printer"], cwd=str(self.repo.path), env=dict(self.repo.env, PYTHONIOENCODING="latin-1"),
                              capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        self.assertIn(b"\nPASS  printer ", text.stdout)
        self.assertIn(b"\n      \xc3\xa9\noverride: ", text.stdout)

    def test_checks_run_isolated_from_the_clones_git_configuration(self):
        """Personal, system and inherited Git configuration and the personal attributes file change no result; the
        clone's own .git/config still applies."""
        self.repo.write(".gitattributes", "*.txt diff=notes\n")  # a named diff driver the caller could make binary
        self.repo.stage(".gitattributes")
        name = check(["sh", "-c", 'git config --get user.name; echo "exit $?"', "{snapshot}"], ["ci"])
        self.repo.configure(dict(NO_SPEC, name=name))
        base = self.repo.commit()
        self.repo.write("notes.txt", "trailing \n")
        self.repo.stage("notes.txt")
        added = self.repo.commit()
        self.repo.git("mv", "notes.txt", "moved.txt")
        renamed = self.repo.commit()  # only a rename: with Git's default rename detection, no line is added
        runs = [(added, base), (renamed, added)]

        def results(env):
            reports = [self.repo.snapshot("run", "--stage", "ci", "--head", head, "--base", base, env=env)[1]
                       for head, base in runs]
            name_output = {c["id"]: c for c in reports[1]["checks"]}["name"]["output"]
            return [statuses(r)["whitespace"] for r in reports], name_output

        clean = results(self.repo.env)
        outside = self.repo.path.parent / "outside"
        (outside / "git").mkdir(parents=True)
        settings = ("[core]\n\twhitespace = -blank-at-eol\n[diff]\n\trenames = false\n"
                    "[diff \"notes\"]\n\tbinary = true\n[user]\n\tname = Outside User\n")
        for name in ("global", "system"):
            (outside / name).write_text(settings)
        (outside / "git/attributes").write_text("* -whitespace\n")  # read by default unless core.attributesFile is set
        env = {k: v for k, v in self.repo.env.items() if k != "GIT_CONFIG_NOSYSTEM"}
        # Configuration a caller passes in the environment, as `git -c` and GIT_CONFIG_COUNT do, is dropped too.
        configured = results(dict(env, GIT_CONFIG_GLOBAL=str(outside / "global"),
                                  GIT_CONFIG_SYSTEM=str(outside / "system"), XDG_CONFIG_HOME=str(outside),
                                  GIT_CONFIG_COUNT="1",
                                  GIT_CONFIG_KEY_0="core.whitespace", GIT_CONFIG_VALUE_0="-blank-at-eol",
                                  GIT_CONFIG_PARAMETERS="'diff.renames'='false'"))
        self.assertEqual(clean, (["fail", "pass"], "exit 1\n"))
        self.assertEqual(configured, clean)
        for setting, value in (("user.name", "Clone User"), ("core.whitespace", "-blank-at-eol")):
            self.repo.git("config", setting, value)  # the clone's own configuration still applies
        self.assertEqual(results(self.repo.env), (["pass", "pass"], "Clone User\nexit 0\n"))


class SnapshotTest(RunnerCase):
    def test_file_staged_during_the_run_stops_with_preparation_failure(self):
        stager = "printf 'late\\n' > late.txt && git --git-dir=.git --work-tree=. add late.txt"  # another process
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
            "stage-other": check(["sh", "-c", "printf 'other\\n' > f.txt && git --git-dir=.git --work-tree=. add f.txt",
                                  "{snapshot}"], ["pre-commit"]),
            "reader": check(["git", "show", "{snapshot}:f.txt"], ["pre-commit"]),
            "restore": check(["sh", "-c", "printf 'original\\n' > f.txt && git --git-dir=.git --work-tree=. add f.txt",
                              "{snapshot}"], ["pre-commit"]),
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
        self.assertEqual((report["layers"], [(s["base"], s["result"]) for s in report["snapshots"]]),
                         ([], [(None, "pass")]))

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

    def test_sha256_repository_is_checked(self):
        probe = subprocess.run(["git", "init", "-q", "--object-format=sha256", str(self.repo.path.parent / "probe")],
                               capture_output=True, stdin=subprocess.DEVNULL, env=base_env())
        if probe.returncode:
            self.skipTest("the installed Git cannot create a SHA-256 repository")
        self.repo = Repo(Path(tempfile.mkdtemp(dir=str(self.folder))), self.house_rules, self.cache,
                         object_format="sha256")
        self.repo.write("notes.txt", "trailing \n")
        self.repo.stage("notes.txt")
        self.repo.configure(NO_SPEC)
        proc, report = self.repo.snapshot("run", "--stage", "pre-commit")
        self.assertEqual((proc.returncode, len(report["snapshot"]), statuses(report)["whitespace"]), (1, 64, "fail"),
                         proc.stderr)

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
             "pre-commit", ("skipped", "no matching file", "")),
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
             ("skipped", "no matching file", "")),
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
             "no matching file"),
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
        return (re.escape(f"repository checks: pre-push on {ref} at commit {commit[:7]}, base {base[:7]}, ")
                + self.repo.header(self.repo.main))

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
            self.assertEqual((proc.returncode, report), (0, {"version": 3, "stage": "pre-push", "result": "pass",
                                                             "layers": [], "warnings": [],
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

    def test_pushed_commits_that_name_different_sources_stop_the_run(self):
        self.repo.git("checkout", "-q", "-b", "first", "main")
        first = self.commit_file("first.txt")
        self.repo.git("checkout", "-q", "-b", "second", "main")
        self.repo.reconfigure(ref="variant-elsewhere")
        second = self.commit_file("second.txt")
        proc, report = self.push(self.line("refs/heads/first", first), self.line("refs/heads/second", second))
        self.assertEqual((proc.returncode, report["result"]), (2, "error"), proc.stderr)
        self.assertEqual([s["reference"] for s in report["snapshots"]], ["refs/heads/first"])
        self.assertEqual(report["error"], {"reference": "refs/heads/second", "repair": "push them separately",
                                           "cause": "the pushed commits declare different House Rules sources"})

    def test_empty_push_input_checks_nothing(self):
        proc, report = self.push()
        self.assertEqual((proc.returncode, report), (0, {"version": 3, "stage": "pre-push", "result": "pass",
                                                         "layers": [], "warnings": [], "snapshots": []}),
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
        self.repo.reconfigure(url=OFFLINE)
        sent = self.commit_file("feature.txt")
        env = dict(self.repo.env, HOUSE_RULES_CACHE=str(self.repo.path.parent / "offline"))
        proc, report = self.repo.report("run", "--stage", "pre-push", "--remote", "origin",
                                        input=self.line("refs/heads/feature", sent), env=env)
        self.assertEqual((proc.returncode, report["error"]["reference"], report["error"]["repair"]),
                         (2, "refs/heads/feature",
                          "push again when online; the push fetches House Rules and builds its environment itself"),
                         proc.stderr)
        self.assertTrue(report["error"]["cause"].startswith(f"cannot fetch House Rules main from {OFFLINE} ("),
                        report["error"])

    def test_unwritable_cache_is_a_preparation_failure_that_keeps_earlier_snapshots(self):
        self.repo.git("checkout", "-q", "-b", "plain", "main")
        self.repo.git("rm", "-q", "house-rules.json")
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
        self.assertEqual([layer["revision"] for layer in report["layers"]], [self.repo.main])
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
            re.escape("repository checks: pre-commit on the staged index, ") + self.repo.header(self.repo.main),
            "FAIL  spec-docs    " + DURATION,
            VERSION,
            re.escape("      spec-docs: error D13 docs/example.md:") + r"\d+" + re.escape(
                ": rejected form for entity 'example.batcher'; use its registered replacement"),
            re.escape("      spec-docs: 1 error, 0 warnings"),
            re.escape("      fix: " + TOUR_FIX),
            re.escape("      rerun: " + rerun),
            "PASS  whitespace   " + DURATION,
            VERSION,
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
        fetched = report["layers"][0].pop("fetched")
        self.assertRegex(fetched, r"\A" + TIME + r"\Z")
        for warning in report["snapshots"][0].pop("warnings"):  # only a budget warning, which depends on load
            self.assertTrue(warning.startswith("budget: pre-commit took "), warning)
        self.assertEqual(report, {"version": 3, "stage": "pre-commit", "result": "fail",
                                  "layers": [{"name": "house-rules", "url": self.repo.url, "ref": "main",
                                              "revision": self.repo.main, "source": "fetched"}], "warnings": [],
                                  "snapshots": [{
            "reference": None, "source": "index", "base": head, "snapshot": snapshot, "result": "fail",
            "checks": [
                {"id": "spec-docs", "layer": "house-rules", "status": "fail",
                 "command": [str(python), "-I", checker, "check", "--root", ".", "--rev", snapshot],
                 "version": [{"path": str(python), "sha256": sha256(python)},
                             {"path": checker, "sha256": sha256(checker)}],
                 "fix": TOUR_FIX, "skip_reason": None,
                 "rerun": shlex.join([sys.executable, runner, "run", "--stage", "pre-commit", "--only", "spec-docs"])},
                {"id": "whitespace", "layer": "house-rules", "status": "pass", "output": "", "fix": None,
                 "skip_reason": None,
                 "command": ["git", f"--attr-source={snapshot}", "diff", "--check", head, snapshot],
                 "version": [{"path": shutil.which("git"), "sha256": sha256(shutil.which("git"))}],
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
        self.assertLines(proc.stdout, [r"repository checks: .*", "PASS  spec-docs    " + DURATION, VERSION,
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
    """Every run resolves its House Rules layer once; HOUSE_RULES_REVISION overrides it for one run."""
    IMPOSSIBLE_RUNTIME = {"skills/spec-writing/scripts/runtime.json":
                          json.dumps({"version": 1, "implementation": "CPython", "requires_python": ">=3.98,<3.99"})}

    def own_house_rules(self):
        """A House Rules fixture of this case alone, so moving its main changes no other case."""
        house_rules = HouseRules(Path(tempfile.mkdtemp(dir=str(self.folder))))
        self.repo.url = house_rules.url  # the next configure() names it
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
        self.assertEqual((proc.returncode, first["revision"], first["source"]), (0, house_rules.main, "fetched"),
                         proc.stderr)
        (house_rules.path / "MOVED").write_text("main moved\n")
        moved = house_rules.commit("Move main")
        earlier = cache / "revisions" / house_rules.main / RUNNER  # a hook set up while the earlier main was current
        proc, entry, second = self.repo.checked("run", "--stage", "pre-commit", script=earlier)
        self.assertEqual((proc.returncode, second["revision"], second["source"]), (0, moved, "fetched"), proc.stderr)
        self.assertTrue(entry["checks"][0]["rerun"].startswith(
            shlex.join([sys.executable, str(cache / "revisions" / moved / RUNNER)])), entry["checks"][0])

    def test_offline_run_uses_the_cached_main_with_a_warning(self):
        self.fresh_cache("cached-main")
        self.repo.configure(NO_SPEC)
        proc, _, online = self.repo.checked("run", "--stage", "pre-commit")
        self.assertEqual((proc.returncode, online["source"]), (0, "fetched"), proc.stderr)
        error = "fatal: unable to access the House Rules URL: Could not resolve host"
        fail = f"echo {shlex.quote(error)} >&2; exit 128"
        offline = lambda: dict(self.repo.env, PATH=self.racing_git("ls-remote", fail))
        proc, report = self.repo.report("run", "--stage", "pre-commit", env=offline())
        self.assertEqual((proc.returncode, report["result"], report["layers"]),
                         (0, "pass", [dict(online, source="offline")]), proc.stderr)
        warning = (f"cannot fetch House Rules main from {self.house_rules.url} ({error}); using the main last fetched, "
                   f"{self.repo.main}, fetched {online['fetched']}")
        self.assertEqual(report["warnings"], [warning])
        text = self.repo.run("run", "--stage", "pre-commit", env=offline()).stdout.splitlines()
        self.assertEqual(text[0], "repository checks: pre-commit on the staged index, House Rules "
                                  f"{self.repo.main} (offline branch main of {self.repo.url}, "
                                  f"cached {online['fetched']})")
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
            f"HOUSE_RULES_REVISION of {self.repo.url}, cached {house_rules['fetched']})") + "$")
        proc, _, later = self.repo.checked("run", "--stage", "ci", "--head", "HEAD")  # nothing kept the override
        self.assertEqual((proc.returncode, later["revision"], later["source"]), (0, self.repo.main, "fetched"),
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
        self.assertEqual(report["overrides"], [{"id": "extra", "layer": "repository",
                                                "reason": "Not needed in this fixture.", "change": "enabled: false"}])
        status = self.repo.run("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual([line for line in status.stdout.splitlines() if line.startswith(("pre-", "ci:", "override:"))],
                         ["pre-commit: whitespace, spec-docs", "pre-push: whitespace", "ci: whitespace, spec-docs",
                          "override: extra enabled: false (repository); reason: Not needed in this fixture."])

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
            re.escape("repository checks: pre-commit on the staged index, ")
            + self.repo.header(revision, "override HOUSE_RULES_REVISION"),
            "WARN  draft        " + DURATION, VERSION, re.escape("      draft finding"),
            re.escape("      fix: Fix the draft finding."), r"      rerun: .* --only draft",
            "PASS  whitespace   " + DURATION, VERSION,
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

    def test_queued_check_whose_program_is_missing_is_an_error_even_when_not_enforced(self):
        missing = ["no-such-program-for-checks", "{snapshot}"]
        draft = ('    "draft": {"enabled": True, "enforced": False, "scope": "tree", "stages": ["pre-commit", "ci"], '
                 f'"paths": ["**"], "requires": [], "run": {json.dumps(missing)}, "fix": "Fix the draft finding."}},\n')
        revision = self.house_rules.runner_variant("Add a check whose program is missing",
                                                   [("BUILTINS = {\n", "BUILTINS = {\n" + draft)])
        queue = self.repo.path.parent / "queue"
        queue.write_text('#!/bin/sh\nexec "$@"\n')
        queue.chmod(0o755)
        self.repo.configure({"lint": check(missing, ["pre-commit"])})
        env = dict(self.repo.env, HOUSE_RULES_REVISION=revision, HOUSE_RULES_CHECK_QUEUE=str(queue))
        proc, entry = self.repo.snapshot("run", "--stage", "pre-commit", env=env)
        results = {c["id"]: c for c in entry["checks"]}
        self.assertEqual((proc.returncode, entry["result"]), (1, "fail"), proc.stderr)
        for name in ("draft", "lint"):
            self.assertEqual((results[name]["status"], results[name]["output"]),
                             ("error", "cannot start 'no-such-program-for-checks': No such file or directory\n"))

    def lookup(self, prepare, entries, expected):
        """Run `lint` with PATH `entries` after `prepare`; assert it ran `ran/lint` and the version names `expected`."""
        self.repo.write("ran/lint", "#!/bin/sh\necho working\n")
        (self.repo.path / "ran/lint").chmod(0o755)
        prepare()
        self.repo.configure({"lint": check(["lint", "{snapshot}"], ["pre-commit"])})
        env = dict(self.repo.env, PATH=os.pathsep.join([*entries, os.environ["PATH"]]))
        proc, entry = self.repo.snapshot("run", "--stage", "pre-commit", "--only", "lint", env=env)
        lint = entry["checks"][0]
        program = os.path.join(self.repo.root, expected)
        self.assertEqual((proc.returncode, lint["status"], lint["output"], lint["version"]),
                         (0, "pass", "working\n", [{"path": program, "sha256": sha256(program)}]), proc.stderr)

    def test_version_names_the_first_candidate_when_the_start_passes_it(self):
        # The start passes a script whose first line names a missing interpreter; the version names it all the same.
        def broken():
            self.repo.write("first/lint", "#!/nonexistent/interpreter\n")
            (self.repo.path / "first/lint").chmod(0o755)
        self.lookup(broken, ["first", "ran"], "first/lint")

    def test_program_lookup_skips_a_path_entry_that_is_no_folder(self):
        self.lookup(lambda: self.repo.write("plain", "a file, not a folder\n"), ["plain", "ran"], "ran/lint")

    def test_program_lookup_skips_an_unreadable_candidate_that_is_not_executable(self):
        if os.geteuid() == 0:
            self.skipTest("the superuser reads every file")

        def unreadable():
            self.repo.write("first/lint", "not a program\n")
            (self.repo.path / "first/lint").chmod(0)
            self.addCleanup((self.repo.path / "first/lint").chmod, 0o644)
        self.lookup(unreadable, ["first", "ran"], "ran/lint")

    def test_program_lookup_resolves_parent_folders_through_links(self):
        # link/.. is the folder that holds the link's target, not the repository root as lexical normalization says.
        def linked():
            self.repo.write("deep/target/keep", "\n")
            os.symlink("deep/target", str(self.repo.path / "link"))
            self.repo.write("deep/ran/lint", "#!/bin/sh\necho working\n")
            (self.repo.path / "deep/ran/lint").chmod(0o755)
            (self.repo.path / "ran/lint").write_text("#!/bin/sh\necho wrong program; exit 1\n")
        self.lookup(linked, ["link/../ran"], "link/../ran/lint")

    def test_versions_name_each_program_and_script_but_not_file_inputs(self):
        self.repo.write("tools/lint.sh", 'echo "linted $1"\n')
        self.repo.write("notes.txt", "notes\n")
        self.repo.stage("tools/lint.sh", "notes.txt")
        self.repo.configure({
            "lint": check(["sh", "tools/lint.sh", "{snapshot}"], ["pre-commit"]),
            "list": check(["sh", "tools/lint.sh", "{snapshot}", "{files}"], ["pre-commit"], ["*.txt"], scope="files")})
        proc, entry = self.repo.snapshot("run", "--stage", "pre-commit")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        results = {c["id"]: c for c in entry["checks"]}
        shell, program = shutil.which("sh"), shutil.which("git")
        script = {"path": "tools/lint.sh", "sha256": sha256(self.repo.path / "tools/lint.sh")}
        self.assertEqual(results["lint"]["version"], [{"path": shell, "sha256": sha256(shell)}, script])
        self.assertEqual(results["list"]["command"][-1], "notes.txt")  # an input, so not part of the version
        self.assertEqual(results["list"]["version"], [{"path": shell, "sha256": sha256(shell)}, script])
        self.assertEqual(results["whitespace"]["version"], [{"path": program, "sha256": sha256(program)}])
        self.assertIsNone(results["spec-docs"]["version"])  # skipped, so it ran no program
        text = self.repo.run("run", "--stage", "pre-commit").stdout.splitlines()
        line = f"      version: {shell}@{sha256(shell)[:12]} tools/lint.sh@{script['sha256'][:12]}"
        self.assertEqual(text.count(line), 2, text)

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
        self.assertEqual((proc.returncode, resolved["revision"], resolved["source"]), (0, self.repo.main, "fetched"),
                         proc.stderr)
        self.assertTrue((cache / "revisions" / self.repo.main / RUNNER).is_file())

    def test_main_and_override_are_fetched_with_depth_1(self):
        # Each fetch's own repository is deleted afterwards, so a Git wrapper reports its history right after the fetch.
        house_rules = self.own_house_rules()
        older = house_rules.commit("A commit with a parent")
        newer = house_rules.commit("Main with history")
        cache = self.fresh_cache("depth-cache")
        log = self.repo.path.parent / "fetches.log"
        folders = self.repo.path.parent / "fetch-folders.log"
        wrapper = self.repo.path.parent / "depth-git"
        wrapper.mkdir()
        (wrapper / "git").write_text(
            f"#!/bin/sh\nREAL={shlex.quote(shutil.which('git'))}\n"
            'case " $* " in *" fetch "*) "$REAL" "$@" || exit $?\n'
            f'  {{ "$REAL" rev-parse --is-shallow-repository; "$REAL" rev-list --all --count; }} >> {shlex.quote(str(log))}'
            f'\n  dirname "$(pwd -P)" >> {shlex.quote(str(folders))}'
            "\n  exit 0;; esac\nexec \"$REAL\" \"$@\"\n")
        (wrapper / "git").chmod(0o755)
        env = dict(self.repo.env, PATH=f"{wrapper}{os.pathsep}{os.environ['PATH']}")
        self.repo.configure(NO_SPEC)
        for revision, extra in ((newer, {}), (older, {"HOUSE_RULES_REVISION": older})):
            proc, _, resolved = self.repo.checked("run", "--stage", "pre-commit", env=dict(env, **extra))
            self.assertEqual((proc.returncode, resolved["revision"]), (0, revision), proc.stderr)
        self.assertEqual(log.read_text().split(), ["true", "1", "true", "1"])
        # Each fetch's repository is a temporary folder in its source's folder, not in the cache root.
        self.assertEqual(folders.read_text().splitlines(), [str(source_folder(cache, house_rules.url))] * 2)

    def test_remote_helper_address_is_refused_and_never_shown(self):
        cause = "the House Rules URL in house-rules.json uses Git's <transport>:: form, which this runner does not accept"
        self.repo.configure(NO_SPEC)
        for url in ("https::https://marker-user:marker-token@host.invalid/rules", "ext::sh -c marker-token"):
            with self.subTest(url):
                self.repo.reconfigure(url=url)
                text = self.repo.run("run", "--stage", "pre-commit")
                proc, report = self.repo.report("run", "--stage", "pre-commit")
                self.assertEqual((text.returncode, text.stdout, text.stderr),
                                 (2, "", f"repository checks: {cause}; use a plain URL and a Git credential helper\n"))
                self.assertEqual((proc.returncode, report["error"]["cause"]), (2, cause))
                for output in (text.stdout, text.stderr, proc.stdout, proc.stderr):
                    self.assertNotIn("marker-token", output)

    def test_ssh_login_without_a_password_is_allowed(self):
        self.repo.configure(NO_SPEC)
        for url in ("ssh://git@host.invalid/house-rules", "git@host.invalid:house-rules.git", "ssh://[::1]/house-rules"):
            with self.subTest(url):
                self.repo.reconfigure(url=url)
                path = self.racing_git("ls-remote", "echo 'fatal: offline' >&2; exit 128")  # no network
                proc = self.repo.run("run", "--stage", "pre-commit", env=dict(
                    self.repo.env, PATH=path, HOUSE_RULES_CACHE=str(Path(tempfile.mkdtemp(dir=str(self.folder))))))
                self.assertPreparationFailure(proc, f"cannot fetch House Rules main from {url} (fatal: offline)")

    def test_house_rules_url_that_cannot_be_parsed_is_a_preparation_failure_that_shows_none_of_it(self):
        cases = [("fullwidth solidus", "https://tokenuser:s3cr3tpass@example\uff0finvalid/house-rules"),
                 ("fullwidth colon", "https://tokenuser:s3cr3tpass@example\uff1ainvalid/house-rules"),
                 ("unmatched bracket", "https://tokenuser:s3cr3tpass@[::1/house-rules")]
        for name, url in cases:
            with self.subTest(name):
                self.repo.url = url
                self.repo.configure(NO_SPEC)
                text = self.repo.run("run", "--stage", "pre-commit")
                proc, report = self.repo.report("run", "--stage", "pre-commit")
                self.assertEqual((text.returncode, text.stdout, text.stderr), (2, "", "repository checks: the House "
                                 "Rules URL in house-rules.json cannot be parsed; correct it\n"))
                self.assertEqual((proc.returncode, report["error"]),
                                 (2, {"reference": None, "repair": "correct it",
                                      "cause": "the House Rules URL in house-rules.json cannot be parsed"}))
                for output in (proc.stdout, proc.stderr):
                    self.assertNotIn("s3cr3tpass", output)
                    self.assertNotIn("tokenuser", output)

    def test_ref_names_a_branch_or_a_commit_and_the_report_logs_the_layer(self):
        commit = self.house_rules.variant("A commit that a ref names", {"MARK": "commit ref\n"})
        branch = "variant-" + commit[:12]  # variant() leaves this branch at the commit
        self.repo.configure(NO_SPEC)
        for name, ref, source in (("branch", branch, "fetched"), ("commit", commit, "pinned")):
            with self.subTest(name):
                self.repo.reconfigure(ref=ref)
                proc, entry, layer = self.repo.checked("run", "--stage", "pre-commit")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual({k: v for k, v in layer.items() if k != "fetched"},
                                 {"name": "house-rules", "url": self.repo.url, "ref": ref, "revision": commit,
                                  "source": source})
                self.assertRegex(layer["fetched"], r"\A" + TIME + r"\Z")
                if source == "pinned":  # the time the commit was first placed, not its folder's modification time
                    folder = self.cache / "revisions" / commit
                    self.assertEqual(layer["fetched"] + "\n", Path(str(folder) + ".fetched").read_text())
                    os.utime(str(folder), (0, 0))
                    self.assertEqual(self.repo.checked("run", "--stage", "pre-commit")[2]["fetched"], layer["fetched"])
                self.assertTrue(entry["checks"][0]["rerun"].startswith(
                    shlex.join([sys.executable, str(self.cache / "revisions" / commit / RUNNER)])))
                text = self.repo.run("run", "--stage", "pre-commit").stdout.splitlines()
                label = f"fetched branch {branch}" if source == "fetched" else "pinned commit"
                self.assertRegex(text[0], r"\Arepository checks: pre-commit on the staged index, "
                                 + self.repo.header(commit, label) + r"\Z")

    def test_house_rules_entry_without_url_uses_the_house_rules_url(self):
        log = self.repo.path.parent / "ls-remote.log"
        self.repo.write_config({"version": 2, "sources": [{"name": "house-rules", "ref": "main"}],
                                "checks": NO_SPEC})
        # Git is asked for the default URL; the wrapper answers as an unreachable host would, so no network is used.
        path = self.racing_git("ls-remote", f'printf "%s\\n" "$@" > {shlex.quote(str(log))}; '
                                            "echo 'fatal: offline' >&2; exit 128")
        proc, report = self.repo.report("run", "--stage", "pre-commit", env=dict(
            self.repo.env, PATH=path, HOUSE_RULES_CACHE=str(self.repo.path.parent / "default-url-cache")))
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("https://github.com/symbiotic-build/house-rules", log.read_text().splitlines())
        self.assertEqual(report["error"]["cause"], "cannot fetch House Rules main from "
                                                   "https://github.com/symbiotic-build/house-rules (fatal: offline)")

    def test_failed_fetch_keeps_the_previous_branch_record_and_its_commit(self):
        house_rules = self.own_house_rules()
        cache = self.fresh_cache("kept-record-cache")
        self.repo.configure(NO_SPEC)
        proc, _, first = self.repo.checked("run", "--stage", "pre-commit")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        record = branch_record(cache, house_rules.url).read_text()
        (house_rules.path / "MOVED").write_text("main moved\n")
        moved = house_rules.commit("Move main")
        path = self.racing_git("fetch", "echo 'fatal: the fetch was interrupted' >&2; exit 128")  # ls-remote names B
        proc, _, layer = self.repo.checked("run", "--stage", "pre-commit", env=dict(self.repo.env, PATH=path))
        self.assertEqual((proc.returncode, layer["revision"], layer["source"]), (0, first["revision"], "offline"),
                         proc.stderr)
        self.assertEqual(branch_record(cache, house_rules.url).read_text(), record)
        self.assertFalse((cache / "revisions" / moved).exists())

    def test_cache_keeps_each_source_and_branch_apart_under_bounded_names(self):
        cache = self.fresh_cache("layout-cache")
        base = Path(tempfile.mkdtemp(dir=str(self.folder)))
        rules, nested = base / "rules", base / "rules/lock/x"  # the second source's path runs through the first's
        urls = {rules: "file://" + str(rules), nested: "file://" + str(nested)}
        branches = ("release", "release.json/topic", "b" * 251)  # a record file name of 256 bytes once
        for path in (rules, nested):
            git(base, "clone", "-q", str(self.house_rules.path), str(path))
            for branch in branches[:2]:
                git(path, "branch", branch, "main")
            # A 251-byte name has no room for Git's .lock file as a loose reference, so it is written packed.
            git(path, "pack-refs", "--all")
            packed = path / ".git/packed-refs"
            header, *entries = packed.read_text().rstrip("\n").split("\n")  # a name may hold U+2028
            entries.append(f"{self.house_rules.main} refs/heads/{branches[2]}")
            packed.write_text("\n".join([header, *sorted(entries, key=lambda e: e.split(" ", 1)[1])]) + "\n")
        self.repo.configure(NO_SPEC)
        layers = {}
        for path in (rules, nested):
            for branch in branches:
                with self.subTest(source=path.name, branch=branch[:20]):
                    self.repo.reconfigure(url=urls[path], ref=branch)
                    proc, _, layer = self.repo.checked("run", "--stage", "pre-commit")
                    self.assertEqual((proc.returncode, layer["revision"], layer["source"]),
                                     (0, self.house_rules.main, "fetched"), proc.stderr)
                    layers[path, branch] = layer
        self.assertEqual(sorted(p.name for p in (cache / "sources").iterdir()),
                         sorted(sha256_hex(urls[p]) for p in (rules, nested)))
        for path in (rules, nested):
            url = urls[path]
            folder = source_folder(cache, url)
            self.assertEqual(sorted(p.name for p in (folder / "branches").iterdir()),
                             sorted(sha256_hex(b) + ".json" for b in branches))
            for branch in branches:
                self.assertEqual(json.loads(branch_record(cache, url, branch).read_text()),
                                 {"url": url, "branch": branch, "revision": self.house_rules.main,
                                  "fetched": layers[path, branch]["fetched"]})

    def test_tree_without_its_fetch_time_is_ready(self):
        cache = self.fresh_cache("readiness-cache")
        self.repo.ref = self.house_rules.main
        self.repo.configure(NO_SPEC)
        self.assertEqual(self.repo.run("prepare").returncode, 0)
        tree = cache / "revisions" / self.house_rules.main
        Path(str(tree) + ".fetched").unlink()  # as a tree placed before its time was written
        path = self.racing_git("fetch", "echo 'fatal: no fetch expected' >&2; exit 128")
        proc, _, layer = self.repo.checked("run", "--stage", "pre-commit", env=dict(self.repo.env, PATH=path))
        self.assertEqual((proc.returncode, layer["source"]), (0, "pinned"), proc.stderr)
        self.assertEqual(layer["fetched"], time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(tree.stat().st_mtime)))

    def test_branch_whose_name_holds_a_unicode_line_separator_resolves(self):
        branch = "release\u2028next"
        git(self.house_rules.path, "branch", branch, "main")
        self.fresh_cache("separator-cache")
        self.repo.ref = branch
        self.repo.configure(NO_SPEC)
        proc, _, layer = self.repo.checked("run", "--stage", "pre-commit")
        self.assertEqual((proc.returncode, layer["ref"], layer["revision"], layer["source"]),
                         (0, branch, self.house_rules.main, "fetched"), proc.stderr)

    def test_configuration_staged_during_the_handover_stops_prepare(self):
        self.repo.configure(NO_SPEC)
        other = self.repo.path.parent / "other-source.json"
        other.write_text(json.dumps(dict(self.repo.config, sources=[{"name": "house-rules", "url": OFFLINE,
                                                                      "ref": "main"}])))
        config = self.repo.path / "house-rules.json"
        # Another process stages a configuration of another source after prepare read the first one.
        stager = (f'cp {shlex.quote(str(other))} {shlex.quote(str(config))} && '
                  f'"$REAL" -C {shlex.quote(str(self.repo.path))} add house-rules.json')
        proc = self.repo.run("prepare", env=dict(self.repo.env, PATH=self.racing_git("ls-remote", stager)))
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr),
                         (2, "", "repository checks: the configuration changed during the run; run again\n"))

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
            ("offline before main was ever fetched", OFFLINE, "main", {"HOUSE_RULES_CACHE": fresh("cache-1")},
             [f"repository checks: cannot fetch House Rules main from {OFFLINE} (", "); run again when online\n"]),
            ("main without a runner", "file://" + str(runnerless), "main", {"HOUSE_RULES_CACHE": fresh("cache-2")},
             [f"House Rules {git(runnerless, 'rev-parse', 'HEAD')} has no repository checks runner",
              "set sources in house-rules.json to a House Rules repository and ref that have one"]),
            ("invalid override", self.house_rules.url, "main", {"HOUSE_RULES_REVISION": "abc1234"},
             ["HOUSE_RULES_REVISION 'abc1234' is not a full 40-character commit identity",
              "set it to a full commit identity, or unset it to run at the ref house-rules.json names"]),
            ("override that the URL lacks", self.house_rules.url, "main", {"HOUSE_RULES_REVISION": "1" * 40},
             [f"cannot fetch House Rules {'1' * 40} from {self.house_rules.url} (",
              "run again when online, or set HOUSE_RULES_REVISION to a commit that exists there"]),
            ("commit ref that the URL lacks", self.house_rules.url, "2" * 40, {"HOUSE_RULES_CACHE": fresh("cache-3")},
             [f"cannot fetch House Rules {'2' * 40} from {self.house_rules.url} (",
              "run again when online, or set the ref in house-rules.json to a commit that exists there"]),
            ("branch that the URL lacks", self.house_rules.url, "no-such-branch",
             {"HOUSE_RULES_CACHE": fresh("cache-4")},
             [f"cannot fetch House Rules no-such-branch from {self.house_rules.url} (the repository has no "
              "no-such-branch branch); run again when online"]),
        ]
        for name, url, ref, extra, parts in cases:
            with self.subTest(name):
                self.repo.reconfigure(url=url, ref=ref)
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
                         'override: spec-docs stages: ["pre-push", "ci"] (repository); reason: Slow corpus.',
                         "override: budgets.pre-push seconds: 30 (repository); reason: Large pushes."]
        revision = cache / "revisions" / self.repo.main
        before = self.repo.run("status")
        self.assertEqual(before.stdout.splitlines(), [
            f"repository checks: House Rules main not fetched yet (run: {prepare})",
            "checks: unavailable until House Rules is prepared, because its runner defines the effective set "
            f"(run: {prepare})"])
        self.assertEqual(self.repo.run("run", "--stage", "ci", "--index", "--only", "whitespace").returncode, 0)
        fetched = json.loads(branch_record(cache, self.repo.url).read_text())["fetched"]
        after = self.repo.run("status").stdout.splitlines()  # printed by the resolved runner, from its own built-ins
        self.assertEqual(after[:2], [
            f"repository checks: House Rules {self.repo.main} (offline branch main of {self.repo.url}, "
            f"cached {fetched})",
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

        prepared = re.escape(f"House Rules {main}, offline branch main of {self.repo.url}, cached ") + TIME
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
