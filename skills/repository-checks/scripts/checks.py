#!/usr/bin/env python3
"""Run a repository's declared checks before each commit, before each push and in CI.

The contract is docs/design/194-repository-checks.md. This file uses only the
standard library and runs on CPython 3.9 or later.
"""
import argparse
import contextlib
import errno
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUNNER = "skills/repository-checks/scripts/checks.py"
SPEC_SCRIPTS = "skills/spec-writing/scripts"
CONFIG = "house-rules.json"
HOOK_MARKER = "# house-rules:repository-checks:begin"
STAGES = ("pre-commit", "pre-push", "ci")
HOOK_STAGES = ("pre-commit", "pre-push")
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
# An object identity of the consuming repository: SHA-1 or SHA-256, whichever object format it uses.
OBJECT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
DEFAULT_BUDGET = 10
# The URL the installed CI workflow clones House Rules from.
DEFAULT_URL = "https://github.com/symbiotic-build/house-rules"
# `house-rules exec` passes the resolution record of the configuration it read to the runner it starts.
RESOLVED = "HOUSE_RULES_RESOLVED"
IDENTITY = {"GIT_AUTHOR_NAME": "repository checks", "GIT_AUTHOR_EMAIL": "checks@localhost",
            "GIT_COMMITTER_NAME": "repository checks", "GIT_COMMITTER_EMAIL": "checks@localhost"}
# Every Git command of the runner and of its checks reads each commit itself, never a local replacement.
NO_REPLACE = {"GIT_NO_REPLACE_OBJECTS": "1"}
# Variables that bind a Git command to the calling repository; a hook inherits some of them.
LOCAL_GIT_ENV = ("GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_CONFIG", "GIT_CONFIG_COUNT",
                 "GIT_CONFIG_PARAMETERS", "GIT_DIR", "GIT_GRAFT_FILE", "GIT_IMPLICIT_WORK_TREE",
                 "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_OBJECT_DIRECTORY", "GIT_PREFIX",
                 "GIT_REPLACE_REF_BASE", "GIT_SHALLOW_FILE", "GIT_WORK_TREE")
# Every effective definition starts from these values for the fields its layers leave out.
DEFINITION_DEFAULTS = {"enabled": True, "enforced": True, "scope": "tree", "requires": []}
REFUSAL = {"pre-commit": ("Commit refused", "stage the fixes and commit again"),
           "pre-push": ("Push refused", "commit the fixes and push again"),
           "ci": ("Run failed", "commit the fixes and run the checks again")}
LABELS = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "error": "ERROR", "skipped": "SKIP"}


def load_resolver():
    """scripts/house_rules.py of this runner's own House Rules tree, the resolver of every layer and of the
    effective configuration."""
    path = Path(__file__).resolve().parents[3] / "scripts" / "house_rules.py"
    spec = importlib.util.spec_from_file_location("house_rules", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


house_rules = load_resolver()


class Failure(Exception):
    """A configuration or preparation failure: exit 2 with one line naming the cause and its repair.

    The line is "<cause>; <repair>". `reference` names the pushed reference the failure concerns, if any.
    """

    def __init__(self, cause, repair, reference=None):
        super().__init__(f"{cause}; {repair}")
        self.cause, self.repair, self.reference = cause, repair, reference


def runner_command(*args):
    return shlex.join([sys.executable, str(Path(__file__).resolve()), *args])


def git(cwd, *args, env=None, foreign=False, check=True, drop=()):
    environ = dict(os.environ)
    for name in (*LOCAL_GIT_ENV, *drop) if foreign else drop:
        environ.pop(name, None)
    environ.update(env or {}, **NO_REPLACE)
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), env=environ, stdin=subprocess.DEVNULL,
                              capture_output=True)
    except OSError as exc:
        raise Failure(f"cannot run git in {cwd} ({exc.strerror or exc})", "install Git and run again")
    if check and proc.returncode:
        raise Failure(f"git {' '.join(args[:2])} failed ({last_line(proc.stderr)})", "repair the clone and run again")
    return proc


def output_text(data):
    """Git's output as text without its terminating newline; every other character, such as a path's trailing
    space, stays. Bytes that are not UTF-8, such as in a path, survive as surrogate escapes."""
    text = os.fsdecode(data)
    return text[:-1] if text.endswith("\n") else text


def out(cwd, *args, **kwargs):
    return output_text(git(cwd, *args, **kwargs).stdout)


def last_line(data):
    lines = data.decode(errors="replace").strip().splitlines()
    return lines[-1] if lines else "no output"


def find_root():
    proc = git(".", "rev-parse", "--show-toplevel", check=False)
    if proc.returncode:
        raise Failure("not inside a Git working tree", "run the command from a clone")
    return Path(output_text(proc.stdout))


def commit_id(root, rev):
    proc = git(root, "rev-parse", "--verify", "--quiet", rev + "^{commit}", check=False)
    if proc.returncode:
        return None
    return proc.stdout.decode().strip()


def empty_tree(root):
    return out(root, "hash-object", "-t", "tree", os.devnull)


# Snapshot handling -----------------------------------------------------------------------

TEMPORARY_REPAIR = "free space in or repair access to the temporary folder, and run again"


@contextlib.contextmanager
def scratch(what):
    """A temporary folder for `what`, removed when the block ends; one error boundary covers all of it.

    A file system error while creating, using or removing the folder is a preparation failure. A failed removal
    after another failure keeps that failure's cause and repair and adds the removal to the cause.
    """
    try:
        folder = tempfile.mkdtemp()
    except OSError as exc:
        raise Failure(f"cannot create a temporary folder for {what} ({exc})", TEMPORARY_REPAIR)
    failure = None
    try:
        yield Path(folder)
    except Failure as exc:
        failure = exc
    except OSError as exc:
        failure = Failure(f"cannot use the temporary folder {folder} of {what} ({exc})", TEMPORARY_REPAIR)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)  # an interruption: remove what it can, and keep the interruption
        raise
    try:
        shutil.rmtree(folder)
    except OSError as exc:
        if failure is None:
            raise Failure(f"cannot remove the temporary folder {folder} of {what} ({exc})", TEMPORARY_REPAIR)
        raise Failure(f"{failure.cause}; removing the temporary folder {folder} of {what} failed too ({exc})",
                      failure.repair)
    if failure is not None:
        raise failure


def index_tree(root):
    """Write the tree of a copy of the live index; the real index is never written."""
    index = root / out(root, "rev-parse", "--git-path", "index")
    with scratch("the index copy") as folder:
        tree = staged_tree(root, index, folder / "index")
    return tree


def staged_tree(root, index, copy):
    """Copy the index to `copy` and write its tree, refusing unmerged entries."""
    try:
        shutil.copyfile(str(index), str(copy))
    except FileNotFoundError:
        pass  # nothing was ever staged: the copy stays absent and Git reads an empty index
    except OSError as exc:
        raise Failure(f"cannot read the index copy ({exc})",
                      "run the commit again, and repair the clone if the error repeats")
    env = {"GIT_INDEX_FILE": str(copy)}
    unmerged = sorted({line.split("\t", 1)[1] for line in
                       out(root, "ls-files", "-u", env=env).splitlines() if "\t" in line})
    if unmerged:
        raise Failure(f"the index has unmerged entries ({', '.join(unmerged)})",
                      "resolve the conflicts, stage the result and commit again")
    proc = git(root, "write-tree", env=env, check=False)
    if proc.returncode:
        raise Failure(f"cannot write the staged tree ({last_line(proc.stderr)})",
                      "run the commit again, and repair the clone if the error repeats")
    return proc.stdout.decode().strip()


def build_snapshot(root, head, from_index):
    """Return (commit, tree, parent) of one snapshot: a commit, or a new commit of the staged index.

    For an index snapshot, `parent` is the commit HEAD named when the run read it, or None before the first
    commit; HEAD is read once, so the snapshot's parent and its base are the same commit.
    """
    if not from_index:
        commit = commit_id(root, head or "HEAD")
        if commit is None:
            raise Failure(f"unknown revision '{head or 'HEAD'}'", "name an existing commit")
        return commit, out(root, "rev-parse", commit + "^{tree}"), None
    tree = index_tree(root)
    parent = commit_id(root, "HEAD")
    args = ["commit-tree", "--no-gpg-sign", tree, "-m", "repository checks snapshot"]
    if parent:
        args += ["-p", parent]
    return out(root, *args, env=IDENTITY), tree, parent


def select_base(root, stage, base, remote, target):
    if base:
        resolved = commit_id(root, base)
        if resolved is None and base.lower() == empty_tree(root):
            resolved = base.lower()  # a rerun line repeats the empty-tree base the runner chose
        if resolved is None:
            raise Failure(f"unknown base revision '{base}'", "name an existing commit or the empty tree")
        return resolved
    if target["source"] == "index":
        return target["parent"] or empty_tree(root)
    if stage == "pre-push":
        return push_base(root, remote, target["snapshot"], target["remote_commit"])
    return commit_id(root, target["snapshot"] + "^1") or empty_tree(root)


def push_base(root, remote, snapshot, remote_commit):
    """Merge base with the remote commit Git names, else with the remote's default branch, else the empty tree.

    A pushed commit that shares no ancestor with its comparison commit also gets the empty tree.
    """
    compare = commit_id(root, remote_commit) if remote_commit else None
    if compare is None and remote:
        default = git(root, "symbolic-ref", "--quiet", f"refs/remotes/{remote}/HEAD", check=False)
        compare = commit_id(root, output_text(default.stdout)) if default.returncode == 0 else None
    if compare is None:
        return empty_tree(root)
    proc = git(root, "merge-base", snapshot, compare, check=False)
    if proc.returncode == 1:
        return empty_tree(root)
    if proc.returncode:
        raise Failure(f"cannot find the push base of {snapshot[:7]} ({last_line(proc.stderr)})",
                      "repair the clone and push again")
    return proc.stdout.decode().strip()


def pushed_references(data):
    """Parse Git's pre-push lines: local ref, local commit, remote ref, remote commit; zeros mean none.

    Git ends each line with a line feed and separates its fields with one space; only those bytes delimit, so a
    reference name keeps every other character. Names decode losslessly: a byte that is not UTF-8 stays an escape.
    """
    pushes = []
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    for raw in lines:
        parts = [part.decode("utf-8", "surrogateescape") for part in raw.split(b" ")]
        if len(parts) != 4 or not all(OBJECT.fullmatch(p) for p in parts[1::2]):
            line = raw.decode("utf-8", "surrogateescape")
            raise Failure(f"cannot read the pushed reference line {line!r} on standard input",
                          "run the pre-push stage from the pre-push hook block")
        local, remote = (None if set(c) == {"0"} else c for c in parts[1::2])
        pushes.append((parts[2] if parts[0] == "(delete)" else parts[0], local, remote))
    return pushes


GITLINK = b"160000"


def file_paths(listing):
    """Return the paths in `git ls-tree -r -z` or `git ls-files --stage -z` output that hold a file: a regular file or
    a symbolic link. Both put the mode first.

    A submodule's path holds a commit of another repository (a gitlink), so it is a path but no file.
    """
    paths = set()
    for entry in listing.split(b"\0"):
        meta, _, path = entry.partition(b"\t")
        if entry and meta.split()[0] != GITLINK:
            paths.add(os.fsdecode(path))
    return paths


def tree_files(root, rev):
    """Return the paths in the snapshot that hold a file."""
    return file_paths(git(root, "ls-tree", "-r", "-z", "--full-tree", rev).stdout)


def changed_files(root, base, snapshot):
    return {os.fsdecode(p) for p in git(root, "diff-tree", "-r", "-z", "--name-only", "--no-renames", base,
                                        snapshot).stdout.split(b"\0") if p}


# Configuration ---------------------------------------------------------------------------

def glob(pattern):
    """Translate a repository-relative glob: `**/` matches zero or more folders, `*` one segment."""
    result, index = "", 0
    while index < len(pattern):
        if pattern[index:index + 3] == "**/":
            result, index = result + "(?:.*/)?", index + 3
        elif pattern[index:index + 2] == "**":
            result, index = result + ".*", index + 2
        else:
            char = pattern[index]
            result += "[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char)
            index += 1
    return re.compile(result + r"\Z", re.S)


def config_data(root, rev, blobs):
    """The configuration at `rev`, the index when `rev` is empty, or None when no file is at exactly its path."""
    if CONFIG not in blobs:
        return None
    return git(root, "cat-file", "blob", f"{rev}:{CONFIG}").stdout


def staged_data(root):
    """The staged configuration, by the rule `run` uses. A file that the index lists but Git cannot read, such as a
    missing blob or an unmerged entry, is a preparation failure with Git's message, never taken for an absent one."""
    return config_data(root, "", file_paths(git(root, "ls-files", "--stage", "-z", "--", CONFIG).stdout))


INDEX = {"origin": "index", "commit": None}
WORKING_TREE = {"origin": "working tree", "commit": None}
# exec resolved one configuration; a snapshot that resolves its own cannot take exec's override or link along.
PUSH_SELECTION = ("a House Rules override or link selects HEAD's source",
                  "push this branch without it, or push it separately")
INSTALL_SELECTION = ("a House Rules override or link selects the source of another configuration than the staged one",
                     "run the install without it")
CHANGED = ("the configuration changed during the run", "run again")
# `status` reports what the cache holds: the resolver asks no remote, and a branch uses its last answer.
NOT_ASKED = house_rules.Deadline(0, "not asked (status never fetches)")
HANDED = None  # exec's resolution record, read at start


def resolver_failure(failure):
    """The runner's form of a resolver failure, whose one line ends with its repair after the last "; "."""
    cause, _, repair = str(failure).rpartition("; ")
    return Failure(cause, repair) if cause else Failure(str(failure), "repair the cause it names and run again")


def parse(data):
    try:
        return house_rules.repository_config(data)
    except house_rules.Failure as failure:
        raise resolver_failure(failure) from None


def configuration(root, data, origin, stage, selection, deadline=house_rules.NO_DEADLINE):
    """(resolution record, effective configuration) of one configuration, the bytes `data` read from `origin`.

    exec's record serves a configuration that names the same sources and profiles, so a run resolves nothing exec
    resolved. Any other configuration resolves its own layers; exec's override or link cannot follow it there, so
    `selection`, a (cause, repair) pair, stops the run instead. CI applies no global configuration.
    """
    config = parse(data)
    hooks = stage != "ci"
    try:
        record = HANDED if HANDED is not None and same_layers(HANDED, config) else None
        if record is None:
            if HANDED is not None and HANDED["layers"][0]["source"] in ("override", "link"):
                raise Failure(*selection)
            record = house_rules.resolve(str(root), data=data, origin=origin, deadline=deadline, machine=hooks)
        built = house_rules.effective(record, config, str(root), hooks=hooks)
    except house_rules.Failure as failure:
        raise resolver_failure(failure) from None
    checks = []
    for identity, fields in built["checks"].items():
        layer = built["layers_of"][identity]["run"]  # {layer} is the tree of the file that defined the run
        tree = root if layer == "repository" else house_rules.layer_tree(record, layer.split("/")[0])
        checks.append(dict(DEFINITION_DEFAULTS, **fields, id=identity, layer=layer, layer_tree=str(tree)))
    # The record already holds the warnings of its own resolution; the rest are this configuration's.
    warnings = [w[len("warning: "):] for w in built["warnings"] if w not in record["warnings"]]
    return record, {"checks": checks, "budgets": built["budgets"], "settings": built["settings"], "warnings": warnings}


def same_layers(record, config):
    return (record["profiles"] == config["profiles"] and [(layer["name"], layer["url"], layer["ref"])
            for layer in record["layers"]] == [(s["name"], s["url"], s["ref"]) for s in config["sources"]])


def handed(value):
    """exec's resolution record, or None."""
    try:
        record = json.loads(value or "null")
    except ValueError:
        return None
    if isinstance(record, dict) and record.get("version") == 1 and isinstance(record.get("layers"), list) \
            and record["layers"]:
        return record
    return None


# Cache -----------------------------------------------------------------------------------

def cache_failure(exc):
    return Failure(f"cannot write the House Rules cache at {house_rules.cache_root()} ({exc})",
                   "make that folder writable, or set HOUSE_RULES_CACHE to a writable folder, and run again")


def partial(folder):
    folder.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=".partial-", dir=str(folder)))


def place(temporary, final, complete):
    """Rename a built entry into place; when another process won the race, keep its copy."""
    try:
        os.rename(str(temporary), str(final))
    except OSError:
        if not complete(final):
            raise
        shutil.rmtree(str(temporary))
    return final


def label(layer):
    """How the session line names where a layer's commit came from and its URL, with when the remote answered."""
    if layer["source"] == "link":
        return f"link of {layer['url']}"
    named = f"{layer['ref_kind']} {layer['ref']}"
    what = {"fetched": named, "reused": named, "offline": named, "pinned": "commit",
            "override": "HOUSE_RULES_REVISION"}[layer["source"]]
    when = f", cached {layer['fetched']}" if layer["fetched"] else ""
    return f"{layer['source']} {what} of {layer['url']}{when}"


def runtime_interpreter(tree):
    """Choose the interpreter for the spec checker from its runtime file: this one, else the newest on PATH."""
    path = tree / SPEC_SCRIPTS / "runtime.json"
    try:
        runtime = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise Failure(f"cannot read the spec checker's runtime file {path} ({exc})",
                      f"run `{runner_command('prepare')}` again")
    bounds = re.fullmatch(r">=(\d+)\.(\d+),<(\d+)\.(\d+)", str(runtime.get("requires_python")))
    if runtime.get("implementation") != "CPython" or not bounds or bounds[1] != bounds[3]:
        raise Failure(f"unsupported runtime file {path}",
                      "report to the House Rules maintainers that its runner and spec checker disagree")
    major, low, high = int(bounds[1]), int(bounds[2]), int(bounds[4])
    if sys.implementation.name == "cpython" and sys.version_info[0] == major and low <= sys.version_info[1] < high:
        return sys.executable, f"{major}.{sys.version_info[1]}"
    for minor in range(high - 1, low - 1, -1):
        found = shutil.which(f"python{major}.{minor}")
        if found:
            return found, f"{major}.{minor}"
    raise Failure(f"no supported interpreter for the spec checker: it needs CPython {runtime['requires_python']} "
                  "on PATH", f"install one, then run `{runner_command('prepare')}`")


def environment(tree, with_lock=False):
    """Return (interpreter, environment folder); the folder name digests the lock and interpreter version.

    With `with_lock`, also return the lock's bytes, read once: the environment is built from exactly the bytes its
    name digests, even when the file changes meanwhile, as in a linked checkout.
    """
    python, version = runtime_interpreter(tree)
    lock = tree / SPEC_SCRIPTS / "requirements.lock"
    try:
        data = lock.read_bytes()
    except OSError as exc:
        raise Failure(f"cannot read {lock} ({exc})", f"run `{runner_command('prepare')}` again")
    digest = hashlib.sha256(data + b"\0CPython " + version.encode()).hexdigest()
    folder = house_rules.cache_root() / "environments" / digest
    return (python, folder, data) if with_lock else (python, folder)


# A push fetches House Rules and builds its environment itself, so pushing again online repairs either.
PUSH_AGAIN = "push again when online; the push fetches House Rules and builds its environment itself"


def prepare_environment(tree, offline_repair=None):
    python, final, data = environment(tree, with_lock=True)
    if (final / "bin" / "python").exists():
        return final / "bin" / "python"
    try:
        temporary = partial(final.parent)
        lock = temporary / "requirements.lock"  # inside the private folder, so nothing else can change it
        lock.write_bytes(data)
        # -I: inherited Python settings, such as PYTHONPATH, cannot replace venv or pip.
        for step, command in (("venv", [python, "-I", "-m", "venv", str(temporary)]),
                              ("pip", [str(temporary / "bin" / "python"), "-I", "-m", "pip", "install", "--quiet",
                                       "--disable-pip-version-check", "--require-hashes", "--only-binary=:all:",
                                       "--no-deps", "-r", str(lock)])):
            proc = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL)
            if proc.returncode:
                raise Failure(f"cannot build the spec checker's environment ({step} exited {proc.returncode}: "
                              f"{last_line(proc.stderr + proc.stdout)})",
                              offline_repair or f"run `{runner_command('prepare')}` when online")
        return place(temporary, final, lambda path: (path / "bin" / "python").exists()) / "bin" / "python"
    except OSError as exc:
        raise cache_failure(exc)


def environment_problem(config, tree):
    """Say what is missing when an enabled check needs the spec checker's environment and it is not built."""
    if not any(c["enabled"] and uses(c, "python") for c in config["checks"]):
        return None
    _, folder = environment(tree)
    if (folder / "bin" / "python").exists():
        return None
    return f"spec checker environment not built at {folder} (run: {runner_command('prepare')})"


def uses(check, name):
    return any("{" + name + "}" in arg for arg in check["run"])


# Commands ----------------------------------------------------------------------------------

def command_run(args):
    snapshots = []
    error, nothing = None, None
    try:
        nothing = check_stage(args, snapshots)
    except Failure as exc:
        error = exc
    result = "error" if error else "fail" if any(s["result"] == "fail" for s in snapshots) else "pass"
    report = {"version": 4, "stage": args.stage, "result": result, "snapshots": snapshots}
    if error:
        report["error"] = {"reference": error.reference, "cause": error.cause, "repair": error.repair}
    if args.json:
        print(json.dumps(report))  # ASCII only: a path byte that is not UTF-8 stays a lossless escape
    elif nothing:
        print(f"nothing to check: {nothing}")
    elif snapshots:
        print(render(report))
    if error:
        sys.stdout.flush()
        print(f"repository checks: {error}", file=sys.stderr)
    return {"pass": 0, "fail": 1, "error": 2}[result]


def check_stage(args, snapshots):
    """Check each snapshot of the stage in turn, appending its entry; return why there is nothing to check, or None.

    Each snapshot resolves the layers its own configuration names; within the run, a branch of one source is asked
    for once, so snapshots that list it use the same commit. A preparation failure stops the run; the snapshots
    checked before it stay in `snapshots`.
    """
    root = find_root()
    from_index = args.index or (args.stage == "pre-commit" and not args.head)
    if args.remote and args.stage != "pre-push":
        raise Failure("--remote applies only to --stage pre-push", "drop --remote")
    # At pre-push Git names each pushed commit on standard input; each one is its own snapshot.
    pushing = args.stage == "pre-push" and not (args.head or args.index)
    stdin = sys.stdin.buffer.read() if pushing else None
    items = [(None, args.head, None)]
    if pushing:
        items = pushed_references(stdin)
        if not items:
            return "the push sends no references"
        items = [item for item in items if item[1] is not None]  # a deletion has nothing to check
        if not items:
            return "the push only deletes references"
    selection = PUSH_SELECTION if pushing else CHANGED
    for ref, head, remote_commit in items:
        try:
            if pushing:
                pushed, head = head, commit_id(root, head)
                if head is None:
                    raise Failure(f"the pushed reference {ref} points at {pushed[:7]}, which resolves to no commit",
                                  "change the reference, or push it without the hook's check under the rule line")
            target = snapshot_target(root, ref, head, from_index, remote_commit)
            if target["data"] is None:
                snapshots.append(unadopted(target))
            else:
                origin = INDEX if from_index else {"origin": "commit", "commit": target["snapshot"]}
                record, config = configuration(root, target["data"], origin, args.stage, selection)
                known = [c["id"] for c in config["checks"]]
                for name in args.only or ():
                    if name not in known:
                        raise Failure(f"unknown check '{name}' in --only", f"name one of {', '.join(known)}")
                snapshots.append(check_snapshot(root, args, target, record, config, pushing))
            if from_index and index_tree(root) != target["tree"]:
                raise Failure("the staged index changed during the run, so the checks did not see the content Git "
                              "would commit", "review what was staged and commit again")
        except Failure as exc:
            exc.reference = ref
            raise
    return None


def snapshot_target(root, ref, head, from_index, remote_commit):
    snapshot, tree, parent = build_snapshot(root, head, from_index)
    blobs = tree_files(root, snapshot)
    return {"ref": ref, "snapshot": snapshot, "tree": tree, "parent": parent, "blobs": blobs,
            "remote_commit": remote_commit, "source": "index" if from_index else "commit",
            "data": config_data(root, snapshot, blobs)}


def snapshot_entry(target, record, config, base, result, checks, warnings):
    return {"reference": target["ref"], "source": target["source"], "base": base, "snapshot": target["snapshot"],
            "result": result, "resolution": record, "settings": config["settings"] if config else [],
            "checks": checks, "warnings": warnings}


def unadopted(target):
    return snapshot_entry(target, None, None, None, "pass", [],
                          [f"no {CONFIG} in this snapshot; repository checks are not adopted here"])


def check_snapshot(root, args, target, record, config, pushing):
    """Run the selected checks of one snapshot; every check reads only that snapshot's commit."""
    snapshot, from_index = target["snapshot"], target["source"] == "index"
    base = select_base(root, args.stage, args.base, args.remote, target)
    changed = changed_files(root, base, snapshot) if args.stage in HOOK_STAGES else None
    rerun = ["run", "--stage", args.stage]
    for flag, value in (("--remote", args.remote), ("--head", snapshot if pushing else args.head),
                        ("--base", base if pushing else args.base)):
        rerun += [flag, value] if value else []
    rerun += ["--index"] if args.index else []
    plan = []
    for check in config["checks"]:
        if args.only and check["id"] not in args.only:
            continue
        if args.stage not in check["stages"]:
            if args.only:
                plan.append((check, f"not configured for {args.stage}", None))
            continue
        plan.append((check, *select(check, args.stage, from_index, target, changed)))
    running = [check for check, reason, _ in plan if reason is None]
    tree = house_rules.layer_tree(record)
    values = {"base": base, "snapshot": snapshot, "house_rules": str(tree), "python": None, "layer": None}
    if any(uses(check, "python") for check in running):
        values["python"] = str(prepare_environment(tree, PUSH_AGAIN if pushing else None))
    if any(arg.startswith("--attr-source") for check in running for arg in check["run"]):
        if git(root, f"--attr-source={snapshot}", "rev-parse", "--git-dir", check=False).returncode:
            raise Failure(f"the installed Git ({out(root, '--version')}) cannot read attributes from a commit "
                          "(--attr-source)", "install a Git that supports it")

    started, results = time.monotonic(), []
    env = check_environment(args.stage, base, snapshot)
    for check, reason, inputs in plan:
        result = {"id": check["id"], "layer": check["layer"], "status": "skipped", "seconds": None,
                  "command": None, "version": None, "output": "", "fix": None,
                  "rerun": runner_command(*rerun, "--only", check["id"]), "skip_reason": reason}
        if reason is None:
            command, version_arguments = expand(check["run"], dict(values, layer=check["layer_tree"]), inputs)
            begin = time.monotonic()
            status, output, version = start_check(command, version_arguments, root, env)
            # A failing check that House Rules does not enforce yet warns and leaves its snapshot passing.
            status = status or ("pass" if output[0] == 0 else "fail" if check["enforced"] else "warn")
            result.update(status=status, seconds=round(time.monotonic() - begin, 3), command=command,
                          version=version, output=output[1], fix=check["fix"] if status != "pass" else None)
        results.append(result)
    total = time.monotonic() - started
    ran = [r for r in results if r["status"] != "skipped"]
    warnings = list(config["warnings"])
    budget = config["budgets"].get(args.stage, {}).get("seconds") or (
        DEFAULT_BUDGET if args.stage == "pre-commit" else None)
    if budget is not None and total > budget:
        slowest = max(ran, key=lambda r: r["seconds"])["id"] if ran else None
        warnings.append(f"budget: {args.stage} took {total:.1f} s of {budget:g} s"
                        + (f"; slowest check {slowest}" if slowest else ""))
    order = {"error": 0, "fail": 1, "warn": 2, "pass": 3, "skipped": 4}
    results.sort(key=lambda r: order[r["status"]])
    outcome = "fail" if any(r["status"] in ("fail", "error") for r in ran) else "pass"
    return snapshot_entry(target, record, config, base, outcome, results, warnings)


def select(check, stage, from_index, target, changed):
    """Return (skip reason or None, inputs for a files-scope check).

    Inputs are paths that hold a file in the snapshot, a regular file or a symbolic link; a submodule is never one.
    """
    blobs = target["blobs"]
    if not check["enabled"]:
        return "disabled" + (f": {check['reason']}" if check.get("reason") else ""), None
    if from_index and not uses(check, "snapshot"):
        return "reads the working tree; runs in CI on the commit", None
    # A required file is a regular file or a symbolic link; a folder or a submodule of that name is none.
    missing = [p for p in check["requires"] if p not in blobs]
    if missing:
        return "requires " + ", ".join(missing), None
    patterns = [glob(p) for p in check["paths"]]
    matches = lambda names: sorted(n for n in names if any(p.match(n) for p in patterns))
    if changed is None:
        inputs = matches(blobs)
        if check["scope"] == "files" and not inputs:
            return "no matching file", None
        return None, inputs
    selected = matches(changed)
    if not selected:
        return ("no staged input" if stage == "pre-commit" else "no changed input"), None
    inputs = [n for n in selected if n in blobs]
    if check["scope"] == "files" and not inputs:  # the changed paths were deleted, or are submodules
        return "no matching file", None
    return None, inputs


# Every check reads Git without personal or system configuration and without the system attributes file.
CHECK_GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1", **NO_REPLACE}


def check_environment(stage, base, snapshot):
    """The environment of a check: the runner's own, without variables that bind Git to another repository or pass
    it configuration, plus CHECK_GIT_ENV and the CHECK_ values.

    Git finds the clone's own Git directory from the repository root, the check's working folder. The runner passes
    core.attributesFile=/dev/null as the one GIT_CONFIG_COUNT entry, so Git reads no personal attributes file such
    as ~/.config/git/attributes, which it reads by default even without a global configuration.
    """
    env = {k: v for k, v in os.environ.items()
           if k not in LOCAL_GIT_ENV and not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    env.update(CHECK_GIT_ENV, CHECK_STAGE=stage, CHECK_BASE=base, CHECK_SNAPSHOT=snapshot, GIT_CONFIG_COUNT="1",
               GIT_CONFIG_KEY_0="core.attributesFile", GIT_CONFIG_VALUE_0=os.devnull)
    return env


def start_check(command, version_arguments, root, env):
    """Read the check's version, then run its command, inside the build queue when the machine declares one.

    Returns (status or None, (exit status, output), version). The status is "error" when the program was not found,
    a version file cannot be read, or the program or queue could not start; None when the command ran, and then its
    exit status decides the result. Through a queue, the queue's exit status is the command's. The queue command runs
    with the check's environment. `subprocess` restores the default signal dispositions, so a check that SIGPIPE ends
    fails.
    """
    program = find_program(command[0], root, env)
    if program is None:
        return "error", (None, f"cannot start {command[0]!r}: No such file or directory\n"), []
    version = []
    for path in [program] + [command[i] for i in version_arguments if i]:
        try:
            if path is program or version_input(root, path):
                version.append({"path": path, "sha256": digest(root, path)})
        except OSError as exc:  # the check does not run: its version would leave out a file that ran
            return "error", (None, f"version unreadable: {path} ({exc.strerror or exc})\n"), version
    queue = os.environ.get("HOUSE_RULES_CHECK_QUEUE")
    try:
        proc = subprocess.run([queue, *command] if queue else command, cwd=str(root), env=env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as exc:
        return "error", (None, f"cannot start {(queue or command[0])!r}: {exc.strerror or exc}\n"), version
    return None, (proc.returncode, proc.stdout.decode(errors="surrogateescape")), version


def find_program(name, root, env):
    """The program the command's start will run, as far as a lookup before the start can tell, or None.

    A name with a slash is taken from the repository root. Otherwise it is the first PATH entry that holds `name` as an
    executable regular file; a relative entry counts from the repository root and is joined, never normalized, so
    `link/../bin` resolves through the file system as the start does. Only a regular file counts, so a named pipe is
    never read for the version. The start can still pass a candidate, such as a script whose first line names a
    missing interpreter; the version then names the first candidate.
    """
    def regular(path):
        try:
            return stat.S_ISREG(os.stat(os.path.join(str(root), path)).st_mode)
        except OSError:
            return False
    if "/" in name:  # the start itself reports a file it cannot run, such as one without execute permission
        return name if regular(name) else None
    for entry in os.get_exec_path(env):  # split before joining, so a separator in the root splits nothing
        candidate = os.path.join(str(root), entry, name)
        if regular(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def version_input(root, argument):
    """Whether a command argument names a version file: a regular file, as one file-status lookup finds it.

    A path that does not exist, or is too long to be one, such as a long `sh -c` script, is no version file. Any
    other lookup error, such as a folder the runner cannot search, raises OSError.
    """
    try:
        mode = os.stat(os.path.join(str(root), argument)).st_mode
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.ENAMETOOLONG):
            return False
        raise
    return stat.S_ISREG(mode)


def digest(root, path):
    """The SHA-256 of a version file, read immediately before its command is handed to the queue or started."""
    hasher = hashlib.sha256()
    with open(os.path.join(str(root), path), "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def expand(run, values, inputs):
    """Return (the command, the positions of its arguments that can name a version file).

    `{files}` arguments are the check's inputs, not its version, so their positions are left out.
    """
    command, positions = [], []
    for arg in run:
        if arg == "{files}":
            command += inputs
        else:
            positions.append(len(command))
            command.append(PLACEHOLDER.sub(lambda m: values[m.group(1)], arg))
    return command, positions


def check_lines(results):
    lines = []
    for result in results:
        detail = result["skip_reason"] if result["status"] == "skipped" else f"{result['seconds']:.1f} s"
        lines.append(f"{LABELS[result['status']]:<6}{result['id']:<12} {detail}")
        if result["version"]:
            items = [f"{shlex.quote(item['path'])}@{item['sha256'][:12]}" for item in result["version"]]
            lines.append("      version: " + " ".join(items))
        lines += indented(result["output"])
        if result["status"] in ("fail", "warn", "error"):
            if result["fix"]:
                lines.append("      fix: " + result["fix"])
            lines.append("      rerun: " + result["rerun"])
    return lines


def indented(output):
    """The output's lines, each after six spaces; only line feeds separate lines, and nothing else changes.

    The line feed that ends the output ends its last line; output without one still ends its last line.
    """
    lines = output.split("\n")
    if lines[-1] == "":
        lines.pop()
    return ["      " + line for line in lines]


def render(report):
    """The text report: per snapshot its header, the layers it resolved, its checks, its settings and warnings."""
    lines, checks = [], []
    for entry in report["snapshots"]:
        where = ("the staged index" if entry["source"] == "index" else f"commit {entry['snapshot'][:7]}")
        if entry["reference"]:
            where = f"{entry['reference']} at {where}"
        if entry["base"] is None:  # no configuration in this snapshot
            lines.append(f"repository checks: {report['stage']} on {where}: no {CONFIG}; "
                         "repository checks are not adopted here")
            continue
        lines.append(f"repository checks: {report['stage']} on {where}"
                     + (f", base {entry['base'][:7]}" if report["stage"] == "pre-push" else ""))
        lines += house_rules.describe(entry["resolution"], warnings=False)
        lines += check_lines(entry["checks"])
        lines += settings_lines(entry["settings"])
        lines += entry["resolution"]["warnings"]  # each already starts with "warning: "
        lines += ["warning: " + w for w in entry["warnings"]]
        checks += entry["checks"]
    if not checks or "error" in report:
        return "\n".join(lines)
    ran = [r for r in checks if r["status"] != "skipped"]
    failed = [r for r in ran if r["status"] in ("fail", "error")]
    warned = [r for r in ran if r["status"] == "warn"]
    refused, next_step = REFUSAL[report["stage"]]
    skipped = len(checks) - len(ran)
    if failed:
        lines.append(f"{refused}: {len(failed)} of {len(ran)} checks failed. Fix the findings, {next_step}.")
    elif warned:
        lines.append(f"No enforced check failed; {len(warned)} of {len(ran)} selected checks warned, "
                     "because House Rules does not enforce them yet" + (f"; {skipped} skipped." if skipped else "."))
    elif ran:
        lines.append(f"All {len(ran)} selected check{'s' if len(ran) > 1 else ''} passed"
                     + (f"; {skipped} skipped." if skipped else "."))
    else:
        lines.append(f"No check ran; {skipped} skipped.")
    return "\n".join(lines)


def settings_lines(settings):
    """Every effective value a later layer changed, with the layer that set it and its reason."""
    return ["settings:", *house_rules.describe_settings(settings)] if settings else []


def command_prepare(args):
    root = find_root()
    data = staged_data(root)
    if data is None:
        raise Failure(f"no {CONFIG} in the index", unstaged_repair(root, f"run `{CHECKS_INSTALL}`"))
    record, config = configuration(root, data, INDEX, None, CHANGED)
    tree = house_rules.layer_tree(record)
    print("\n".join(house_rules.describe(record)))
    print(f"repository checks: House Rules {record['layers'][0]['revision']} ready at {tree}")
    if any(c["enabled"] and uses(c, "python") for c in config["checks"]):
        print(f"repository checks: spec checker environment ready at {prepare_environment(tree).parent.parent}")
    return 0


def command_status(args):
    if args.session:
        try:
            line = session_line()
        except Failure as exc:
            line = f"repository checks: {exc}"
        if line:
            print(line)
        return 0
    root = find_root()
    data = staged_data(root)
    if data is None:
        print(f"repository checks: no {CONFIG} in the index; this repository has not adopted repository checks")
        return 0
    parse(data)  # a configuration error stops status, as it stops a run
    prepare = runner_command("prepare")
    try:
        record, config = configuration(root, data, INDEX, None, CHANGED, NOT_ASKED)
    except Failure as exc:
        print(f"repository checks: {exc.cause} (run: {prepare})")
        print(f"checks: unavailable until the layers are in the cache (run: {prepare})")
        return 0
    tree = house_rules.layer_tree(record)
    print("\n".join(house_rules.describe(record)))
    print(f"revision: in the cache at {tree}")
    if any(c["enabled"] and uses(c, "python") for c in config["checks"]):
        print("environment: " + (environment_problem(config, tree) or f"in the cache at {environment(tree)[1]}"))
    for stage in STAGES:
        names = [c["id"] + ("" if c["enforced"] else " (warning only)") for c in config["checks"]
                 if c["enabled"] and stage in c["stages"]]
        print(f"{stage}: {', '.join(names) or 'none'}")
    for line in settings_lines(config["settings"]):
        print(line)
    return 0


def session_line():
    proc = git(".", "rev-parse", "--show-toplevel", check=False)
    if proc.returncode:
        return None
    root = Path(output_text(proc.stdout))
    data = staged_data(root)
    if data is None:
        if (root / ".agents" / "rules.md").is_file():
            return f"repository checks: not installed; {unstaged_repair(root, f'run: {CHECKS_INSTALL}')}"
        return None
    parse(data)  # a configuration error is the line, as status prints it
    try:
        record, config = configuration(root, data, INDEX, None, CHANGED, NOT_ASKED)
        problem = environment_problem(config, house_rules.layer_tree(record))
    except Failure as exc:
        record, problem = None, f"{exc.cause} (run: {runner_command('prepare')})"
    hooks = root / out(root, "rev-parse", "--git-path", "hooks")
    missing = [name for name in HOOK_STAGES if not has_block(hooks / name)]
    # Git ignores a hook file that is not executable, so its block never runs.
    ignored = [name for name in HOOK_STAGES if name not in missing and not os.access(str(hooks / name), os.X_OK)]
    problems = [f"no hook block in {', '.join(missing)} (run: {runner_command('install')})"] if missing else []
    if ignored:
        problems.append(f"hook file {', '.join(ignored)} not executable "
                        f"(run: {shlex.join(['chmod', '+x', *(str(hooks / name) for name in ignored)])})")
    problems += [problem] if problem else []
    layer = record["layers"][0] if record else None
    where = f"House Rules {layer['revision'][:7]}, {label(layer)}" if layer else ""
    if problems:
        return "repository checks: not ready" + (f" ({where})" if where else "") + ": " + "; ".join(problems)
    return f"repository checks: ready ({where}, hooks installed)"


def unstaged_repair(root, then):
    """What to do when the index holds no configuration: stage the file that is there, or write one first."""
    if (root / CONFIG).is_file():
        return f"review {CONFIG} and stage it (git add {CONFIG}), then {then}"
    return f"run `house-rules init`, review and stage {CONFIG} (git add {CONFIG}), then {then}"


def has_block(path):
    try:
        return HOOK_MARKER in path.read_text(errors="replace").splitlines()
    except OSError:
        return False


# Install ---------------------------------------------------------------------------------

HOOK_END = "# house-rules:repository-checks:end"
COMMAND_SETTING = "house-rules.command"  # the clone setting: the absolute path of the installed house-rules command
COMMAND_INSTALL = "python3 <House Rules checkout>/scripts/house_rules.py install"
CHECKS_INSTALL = f"house-rules exec {RUNNER} install"  # the install of this clone, through the house-rules command
WORKFLOW = ".github/workflows/repository-checks.yml"
# The pre-commit framework writes both lines into every hook file it installs.
FRAMEWORK_SIGNS = ("File generated by pre-commit: https://pre-commit.com", "ID: 138fd403232d2ddd5efb44317e38bf03")
# The first lines of a hook the install edits: a plain shell, with no option that could stop the block running.
SHELL_LINES = ("#!/bin/sh", "#!/bin/bash", "#!/usr/bin/env sh", "#!/usr/bin/env bash")
PLAIN_SHELL_REPAIR = "call your existing hook from a plain shell hook"
CI_COMMAND = (f"python .tmp/house-rules/scripts/house_rules.py exec --rev <commit> {RUNNER} run --stage ci "
              "--base <PR base or previous commit> --head <commit>")
PREFLIGHT = ["house-rules", "exec", "--origin", "index", RUNNER, "run", "--stage", "ci", "--index"]
INSPECT_REPAIR = "repair access to it, then run install again"
# The run step fetches a base that the checkout lacks, such as the tip a force push replaced, with the job's
# read-only token in the environment rather than on a command line.
RUNNER_STEP = f"""      - name: Run repository checks
        env:
          BASE: ${{{{ github.event.pull_request.base.sha || github.event.before }}}}
          TOKEN: ${{{{ github.token }}}}
        run: |
          set --
          case "$BASE" in ""|0000000000000000000000000000000000000000) ;; *) set -- --base "$BASE" ;; esac
          if [ $# -gt 0 ] && ! git cat-file -e "$BASE^{{commit}}" 2>/dev/null; then
            auth=$(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\\n')
            GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.extraheader GIT_CONFIG_VALUE_0="AUTHORIZATION: basic $auth" \\
              git fetch --quiet --no-tags origin "$BASE" ||
              {{ echo "repository checks: cannot fetch the base commit $BASE from origin" >&2; exit 1; }}
          fi
          unset TOKEN auth
          python .tmp/house-rules/scripts/house_rules.py exec --rev "$GITHUB_SHA" {RUNNER} run --stage ci "$@" --head "$GITHUB_SHA"
"""
WORKFLOW_TEMPLATE = f"""name: Repository checks

on: [push, pull_request]

permissions:
  contents: read

jobs:
  repository-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: actions/setup-python@v6
        with:
          python-version: '3.13'
      - name: Clone House Rules
        run: git clone --depth 1 {DEFAULT_URL} .tmp/house-rules
""" + RUNNER_STEP


def exec_command(stage):
    """The house-rules exec command line of the `stage` hook block, after the command's path."""
    if stage == "pre-commit":
        return f"exec --origin index {RUNNER} run --stage pre-commit"
    return f'exec --rev HEAD {RUNNER} run --stage pre-push --remote "$1"'


def hook_block(stage):
    """The marked lines the install puts into the `stage` hook file, as the hook block section shows them."""
    lines = [HOOK_MARKER,
             f"cmd=$(git config --get {COMMAND_SETTING}) || cmd=",
             'if [ ! -f "$cmd" ] || [ ! -x "$cmd" ]; then',
             f'  echo "repository checks: {COMMAND_SETTING} names no executable file; run: {COMMAND_INSTALL}, '
             f'then {CHECKS_INSTALL}" >&2',
             "  exit 1",
             "fi"]
    if stage == "pre-commit":
        lines.append(f'"$cmd" {exec_command(stage)} || exit $?')
    else:
        # `rc`, not `status`, which zsh reserves.
        lines += [
            'refs=$(mktemp) || { echo "repository checks: cannot create a temporary file; push refused" >&2; exit 1; }',
            'cat > "$refs" || { echo "repository checks: cannot save the pushed references; push refused" >&2; '
            'rm -f "$refs"; exit 1; }',
            f'"$cmd" {exec_command(stage)} < "$refs" || {{ rc=$?; rm -f "$refs"; exit $rc; }}',
            'exec < "$refs" || { echo "repository checks: cannot reopen the pushed references; push refused" >&2; '
            'rm -f "$refs"; exit 1; }',
            'rm -f "$refs"']
    return [line + "\n" for line in lines + [HOOK_END]]


def framework_entry(stage):
    """The pre-commit framework's `repo: local` entry that calls the runner at `stage`.

    At pre-push the framework reads Git's reference lines itself and passes one pushed reference in variables: the
    local and remote names, the pushed commit and the comparison commit. The entry writes them back as one reference
    line, so the runner chooses the push base as it does for Git's own lines. Without a comparison commit, as for a
    branch with no earlier history on the remote, the remote commit is zeros of the commit's length.
    """
    command = f'"$(git config --get {COMMAND_SETTING})"'
    if stage == "pre-commit":
        script = f"{command} exec --origin index {RUNNER} run --stage pre-commit"
    else:
        script = ('zero=$(printf %s "$PRE_COMMIT_TO_REF" | tr 0-9a-f 0); printf "%s %s %s %s\\n" '
                  '"${PRE_COMMIT_LOCAL_BRANCH:-HEAD}" "$PRE_COMMIT_TO_REF" "$PRE_COMMIT_REMOTE_BRANCH" '
                  f'"${{PRE_COMMIT_FROM_REF:-$zero}}" | {command} exec --rev HEAD {RUNNER} run --stage pre-push '
                  '--remote "$PRE_COMMIT_REMOTE_NAME"')
    return ["- repo: local",
            "  hooks:",
            f"    - id: repository-checks-{stage}",
            "      name: repository checks",
            f"      entry: sh -c '{script}'",
            "      language: system",
            "      pass_filenames: false",
            "      always_run: true",
            f"      stages: [{stage}]"]


@contextlib.contextmanager
def inspecting(what):
    """One boundary for the install's file system reads: an error names `what`, its cause and the repair."""
    try:
        yield
    except OSError as exc:
        raise Failure(f"cannot read {what} ({exc.strerror or exc})", INSPECT_REPAIR) from None


def publish(path, data, mode, label, expected=None):
    """Write `data` to `path` with `mode`, through a private temporary file beside it, so no reader sees a partial
    file.

    With `expected` None the file must be absent: the complete temporary file is linked to `path`, which fails when
    a file is there, so a file another writer created after the plan read the folder is never overwritten. Otherwise
    the file must still hold `expected`, the bytes the plan read, and the temporary file replaces it. Only the
    temporary file is ever removed.
    """
    repair = "repair access to it, then run install again"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".house-rules-", dir=str(path.parent))
    except OSError as exc:
        raise Failure(f"cannot write {label} ({exc.strerror or exc})", repair) from None
    cause = None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
        if expected is None:
            try:
                os.link(temporary, str(path))
            except FileExistsError:
                cause = (f"{label} appeared after the install read its folder", "review it, then run install again")
        else:
            try:
                current = path.read_bytes()
            except OSError as exc:
                cause = (f"cannot read {label} again ({exc.strerror or exc})", repair)
            else:
                if current != expected:
                    cause = (f"{label} changed after the install read it", "review the change, then run install again")
                else:
                    os.replace(temporary, str(path))
                    temporary = None
    except OSError as exc:
        cause = (f"cannot write {label} ({exc.strerror or exc})", repair)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    if temporary is not None:  # published by a link, or never published
        try:
            os.unlink(temporary)
        except OSError as removal:
            first = cause or (f"cannot remove the temporary file of {label}", repair)
            raise Failure(f"{first[0]}; removing {temporary} failed too ({removal.strerror or removal})"
                          if cause else f"{first[0]} {temporary} ({removal.strerror or removal})", first[1]) from None
    if cause:
        raise Failure(*cause)


class Installation:
    """The items one install lists, and the writes it performs for them."""

    WIDTH = 10

    def __init__(self, root):
        self.root, self.items, self.writes, self.repository_files = root, [], [], []
        git_dirs = [out(root, "rev-parse", "--absolute-git-dir"), out(root, "rev-parse", "--git-common-dir")]
        self.git_dirs = [(root / folder).resolve() for folder in git_dirs]

    def add(self, action, label, path=None, write=None, detail=()):
        self.items.append((action, label, list(detail)))
        if write and action in ("create", "update"):
            self.writes.append(write)
            if path is not None and self.in_repository(path):
                self.repository_files.append(self.show(Path(os.path.realpath(str(path)))))  # a link's target

    def in_repository(self, path):
        path = Path(os.path.realpath(str(path)))
        inside = lambda folder: path == folder or folder in path.parents
        return inside(Path(os.path.realpath(str(self.root)))) and not any(inside(folder) for folder in self.git_dirs)

    def show(self, path):
        """The path relative to the repository root when it is inside it, judged by its name alone: nothing is
        resolved, so a link keeps its own name and a looping link cannot fail the label."""
        full = os.path.abspath(str(path))
        relative = os.path.relpath(full, str(self.root))
        return full if relative == ".." or relative.startswith("../") else relative

    def lines(self):
        for action, label, detail in self.items:
            yield f"{action:<{self.WIDTH}} {label}"
            for line in detail:
                yield " " * (self.WIDTH + 1) + line


SPECIAL_OPEN_ERRORS = {errno.ENXIO, errno.ENODEV, errno.EOPNOTSUPP, errno.ENOTSUP}


class ReadFailure(OSError):
    """An error while reading a regular file that opened, as opposed to an error finding or opening it."""


def read_regular(path):
    """(The bytes, the mode) of the file at `path`, opened once without blocking and judged by that open file, so a
    named pipe or a device swapped in meanwhile is never read: (None, mode) for anything but a regular file. A
    missing file raises FileNotFoundError."""
    try:
        descriptor = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK)
    except OSError as exc:
        if exc.errno in SPECIAL_OPEN_ERRORS:  # a socket or a device without a driver cannot be opened as a file
            return None, None
        raise
    try:
        mode = os.fstat(descriptor).st_mode
        if not stat.S_ISREG(mode):
            return None, mode
        try:
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                return stream.read(), mode
        except OSError as exc:
            raise ReadFailure(exc.errno, exc.strerror) from None
    finally:
        os.close(descriptor)


def install_hook(plan, path, target, shared):
    """Add the hook block to one hook file, or refuse a file the install cannot edit safely.

    `target` is the file `path` resolves to through the file system, and `shared` whether the other hook file
    resolves to it too. Only a regular file is read, and only a hook whose first line is one of SHELL_LINES is
    edited: any other first line, a shell option among them, could keep the block from running.
    """
    stage, label = path.name, plan.show(path)
    if shared:
        plan.add("refused", f"{label}: pre-commit and pre-push are the same file, {target}",
                 detail=["give each hook its own file, then run install again"])
        return
    block = hook_block(stage)
    try:
        data, mode = read_regular(target)
    except FileNotFoundError:  # no file, or a link to none: the block goes into a new file at the link's target
        data = ("#!/bin/sh\n" + "".join(block)).encode()
        plan.add("create", label, path, lambda: publish(target, data, 0o755, label))
        return
    except (PermissionError, ReadFailure) as exc:  # any other error, such as a looping link, stops the install
        plan.add("refused", f"{label}: cannot read it ({exc.strerror or exc})", detail=[INSPECT_REPAIR])
        return
    if data is None:
        plan.add("refused", f"{label}: {target} is not a regular file",
                 detail=["replace it with a hook script, then run install again"])
        return
    if not os.access(str(target), os.X_OK):
        plan.add("refused", f"{label}: not executable, so Git ignores it; making it executable also starts its own code",
                 detail=[f"to run it and add the block: chmod +x {shlex.quote(str(path))}, then run install again"])
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is not None and any(sign in text for sign in FRAMEWORK_SIGNS):
        plan.add("refused", f"{label}: written by the pre-commit framework; add this entry to its configuration "
                            "(.pre-commit-config.yaml) under repos:", detail=framework_entry(stage))
        return
    first = data.split(b"\n", 1)[0]  # a carriage return stays: the kernel would take it as part of the shell's name
    if text is None or "\0" in text or first.decode("utf-8", "backslashreplace") not in SHELL_LINES:
        shown = first[:60].decode("utf-8", "backslashreplace") + ("…" if len(first) > 60 else "")
        plan.add("refused", f"{label}: its first line is {shown!r}, not a plain shell line", detail=[PLAIN_SHELL_REPAIR])
        return
    lines = text.splitlines(keepends=True)
    begins = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == HOOK_MARKER]
    ends = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == HOOK_END]
    mode &= 0o7777
    if begins or ends:
        if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
            plan.add("refused", f"{label}: its repository-checks markers are incomplete or repeated; "
                                "remove the block by hand, then run install again")
            return
        new = "".join(lines[:begins[0]] + block + lines[ends[0] + 1:]).encode()
        plan.add("unchanged" if new == data else "update", label, path,
                 lambda: publish(target, new, mode, label, expected=data))
        return
    head = lines[0] if lines[0].endswith("\n") else lines[0] + "\n"
    new = "".join([head] + block + lines[1:]).encode()
    plan.add("update", label, path, lambda: publish(target, new, mode, label, expected=data))


def install_setting(plan, root, name, value):
    """List the clone setting; only Git's status for a missing key, 1, means it is not set yet."""
    proc = git(root, "config", "--local", "--get", name, check=False)
    if proc.returncode not in (0, 1):
        raise Failure(f"cannot read the setting {name} ({last_line(proc.stderr)})",
                      "repair the clone's Git configuration, then run install again")
    current = output_text(proc.stdout) if proc.returncode == 0 else None
    action = "create" if current is None else "unchanged" if current == value else "update"
    plan.add(action, f"setting {name} {value}", write=lambda: git(root, "config", "--local", name, value))
    # With extensions.worktreeConfig, a worktree's own value wins over the clone's, and the hooks read that one.
    proc = git(root, "config", "--show-scope", "--get", name, check=False)
    if proc.returncode not in (0, 1):
        raise Failure(f"cannot read the setting {name} ({last_line(proc.stderr)})",
                      "repair the clone's Git configuration, then run install again")
    scope, _, effective = output_text(proc.stdout).partition("\t")
    if proc.returncode == 0 and scope == "worktree":
        plan.add("unchanged" if effective == value else "update", f"setting {name} {value} (this worktree's own)",
                 write=lambda: git(root, "config", "--worktree", name, value))


def install_workflow(plan, root, ci):
    """Add the GitHub Actions workflow when the repository uses them; return whether it does."""
    path = root / WORKFLOW
    if not (ci == "github" or (root / ".github/workflows").is_dir()):
        return False
    if not os.path.lexists(str(path)):
        data = WORKFLOW_TEMPLATE.encode()
        plan.add("create", WORKFLOW, path, lambda: publish(path, data, 0o644, WORKFLOW))
        return True
    data, _ = read_regular(path)
    if data is None:
        plan.add("refused", f"{WORKFLOW}: not a regular file",
                 detail=["replace it with a workflow file, or remove it, then run install again"])
    elif RUNNER_STEP in data.decode("utf-8", "replace"):
        plan.add("unchanged", WORKFLOW)
    else:
        plan.add("unchanged", WORKFLOW, detail=[
            "its runner step differs from the current template; keep it, or replace it with:",
            *RUNNER_STEP.rstrip("\n").splitlines()])
    return True


def configuration_data(root):
    """(The configuration the install works with, its origin): the working tree's file, as `house-rules exec` reads
    it, else the staged one, else (None, None)."""
    with inspecting(CONFIG):
        path = root / CONFIG
        if path.is_file():
            return path.read_bytes(), "working tree"
    data = staged_data(root)
    return data, "index" if data is not None else None


def selected_command(found):
    """The command PATH selected, made absolute without collapsing `..`: a `..` after a link steps out of the
    link's target, as the lookup did, so collapsing it could name another file."""
    return found if os.path.isabs(found) else os.path.join(os.getcwd(), found)


def command_install(args):
    root = find_root()
    data, origin = configuration_data(root)
    if data is None:
        raise Failure(f"no {CONFIG} in this repository", "run `house-rules init` first")
    found = shutil.which("house-rules")
    if found is None:
        raise Failure("the house-rules command is not on PATH", f"run `{COMMAND_INSTALL}` first")
    tree = config = None
    if not args.dry_run:
        # The install prepares what the hooks' first run needs. Without a working tree file, exec resolved another
        # configuration than the staged one the install reads: its record serves only when it names the same layers.
        record, config = configuration(root, data, INDEX if origin == "index" else WORKING_TREE, None,
                                       INSTALL_SELECTION if origin == "index" else CHANGED)
        tree = house_rules.layer_tree(record)
    plan = Installation(root)
    with inspecting("the hooks folder"):
        hooks = root / out(root, "rev-parse", "--git-path", "hooks")
        paths = {stage: hooks / stage for stage in HOOK_STAGES}
        targets = {stage: Path(os.path.realpath(str(path))) for stage, path in paths.items()}
    shared = targets["pre-commit"] == targets["pre-push"]
    for stage in HOOK_STAGES:
        with inspecting(plan.show(paths[stage])):
            install_hook(plan, paths[stage], targets[stage], shared)
    install_setting(plan, root, COMMAND_SETTING, selected_command(found))
    with inspecting(WORKFLOW):
        has_workflow = install_workflow(plan, root, args.ci)
    environment_line = None
    if config is not None and any(c["enabled"] and uses(c, "python") for c in config["checks"]):
        environment_line = f"environment: spec checker environment ready at {prepare_environment(tree).parent.parent}"
    if not args.dry_run:
        for write in plan.writes:
            write()
    print("repository checks: install preview; nothing is written" if args.dry_run else "repository checks: install")
    for line in plan.lines():
        print(line)
    if environment_line:
        print(environment_line)
    if not has_workflow:
        print("ci: no .github/workflows/ here; for another CI system the job clones House Rules into "
              f".tmp/house-rules and runs: {CI_COMMAND}")
    if plan.repository_files:
        print("next: stage the install: " + shlex.join(["git", "add", "--", *plan.repository_files]))
    print("next: check everything before the hooks refuse commits: " + shlex.join(PREFLIGHT))
    return 1 if any(action == "refused" for action, _, _ in plan.items) else 0


def main(argv=None):
    global HANDED
    argv = sys.argv[1:] if argv is None else argv
    HANDED = handed(os.environ.pop(RESOLVED, None))  # popped, so no check inherits it
    house_rules.ANSWERS = {}  # one answer per branch or tag for this run, exec's first
    if HANDED is not None:
        house_rules.remember(HANDED)
    for stream in (sys.stdout, sys.stderr):
        # UTF-8 with surrogate escapes reverses how the runner decodes output and paths, so every byte prints as
        # it came, whatever output encoding the interpreter inherited, such as from PYTHONIOENCODING.
        stream.reconfigure(encoding="utf-8", errors="surrogateescape")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run the checks of one stage")
    run.add_argument("--stage", required=True, choices=STAGES)
    run.add_argument("--base")
    snapshot = run.add_mutually_exclusive_group()
    snapshot.add_argument("--head")
    snapshot.add_argument("--index", action="store_true")
    run.add_argument("--only", action="append", metavar="ID")
    run.add_argument("--remote", help="the pushed remote; pre-push then reads Git's pushed reference lines")
    run.add_argument("--json", action="store_true")
    install = commands.add_parser("install", help="write the hook blocks, the clone setting and the CI workflow")
    install.add_argument("--dry-run", action="store_true", help="list each item and write nothing")
    install.add_argument("--ci", choices=("github",), help="write the GitHub Actions workflow without .github/workflows/")
    commands.add_parser("prepare", help="fetch the House Rules layer and build its environment in the cache")
    status = commands.add_parser("status", help="print the effective configuration and cache state")
    status.add_argument("--session", action="store_true")
    args = parser.parse_args(argv)
    try:
        return {"run": command_run, "install": command_install, "prepare": command_prepare,
                "status": command_status}[args.command](args)
    except Failure as exc:
        print(f"repository checks: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
