#!/usr/bin/env python3
"""Run a repository's declared checks before each commit, before each push and in CI.

The contract is docs/design/194-repository-checks.md. This file uses only the
standard library and runs on CPython 3.9 or later.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

RUNNER = "skills/repository-checks/scripts/checks.py"
SPEC_SCRIPTS = "skills/spec-writing/scripts"
CONFIG = "house-rules.json"
CONFIG_VERSION = 2
# The untracked file in the working tree that may change only budgets, never whether a check passes.
LOCAL_CONFIG = "house-rules.local.json"
HOUSE_RULES = "house-rules"  # the name of the House Rules source layer
HOOK_MARKER = "# house-rules:repository-checks:begin"
STAGES = ("pre-commit", "pre-push", "ci")
HOOK_STAGES = ("pre-commit", "pre-push")
SCOPES = ("tree", "files", "diff")
FIELDS = ("enabled", "run", "stages", "scope", "paths", "requires", "fix", "reason")
PLACEHOLDERS = ("files", "base", "snapshot", "house_rules", "python")
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
# A House Rules revision, and a commit ref of a source layer: a full SHA-1 commit identity. Any other ref is a branch
# name, except 64 hexadecimal digits, a SHA-256 commit identity, which this runner refuses.
COMMIT = re.compile(r"[0-9a-fA-F]{40}")
SHA256_COMMIT = re.compile(r"[0-9a-fA-F]{64}")
# An object identity of the consuming repository: SHA-1 or SHA-256, whichever object format it uses.
OBJECT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
DEFAULT_BUDGET = 10
# The URL of the House Rules layer when its entry names none; the install writes the branch main beside it.
DEFAULT_URL = "https://github.com/symbiotic-build/house-rules"
DEFAULT_SOURCE = {"name": HOUSE_RULES, "ref": "main"}
# The most entries `sources` may list.
MAX_SOURCES = 32
# A Git setting name: section.key or section.subsection.key, as git-config defines them.
GIT_SETTING = re.compile(r"[A-Za-z0-9-]+(?:\.[^\n\0]+)?\.[A-Za-z][A-Za-z0-9-]*")
# A Git setting the runner passes to every check itself; no configuration may change it.
RUNNER_GIT_SETTINGS = ("core.attributesfile",)
# A House Rules fetch fails on lack of progress, never on elapsed time: below 1 byte/s for 30 s over HTTP.
PROGRESS = ("-c", "http.lowSpeedLimit=1", "-c", "http.lowSpeedTime=30")
# The handing runner passes the run's resolved House Rules revision to the runner it starts,
RESOLVED = "HOUSE_RULES_RESOLVED"
# and the snapshot it built before resolving, so the started runner checks that same snapshot.
SNAPSHOT = "HOUSE_RULES_SNAPSHOT"
# Where a layer's commit came from: its branch fetched now, its branch as last resolved (offline), a commit ref
# (pinned), or the HOUSE_RULES_REVISION test override.
SOURCES = ("fetched", "offline", "pinned", "override")
IDENTITY = {"GIT_AUTHOR_NAME": "repository checks", "GIT_AUTHOR_EMAIL": "checks@localhost",
            "GIT_COMMITTER_NAME": "repository checks", "GIT_COMMITTER_EMAIL": "checks@localhost"}
# Every Git command of the runner and of its checks reads each commit itself, never a local replacement.
NO_REPLACE = {"GIT_NO_REPLACE_OBJECTS": "1"}
# Variables that bind a Git command to the calling repository; a hook inherits some of them.
LOCAL_GIT_ENV = ("GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_CONFIG", "GIT_CONFIG_COUNT",
                 "GIT_CONFIG_PARAMETERS", "GIT_DIR", "GIT_GRAFT_FILE", "GIT_IMPLICIT_WORK_TREE",
                 "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_OBJECT_DIRECTORY", "GIT_PREFIX",
                 "GIT_REPLACE_REF_BASE", "GIT_SHALLOW_FILE", "GIT_WORK_TREE")
BUILTINS = {
    "whitespace": {
        "enabled": True, "enforced": True, "scope": "diff", "stages": ["pre-commit", "ci"], "paths": ["**"],
        "requires": [],
        "run": ["git", "--attr-source={snapshot}", "diff", "--check", "{base}", "{snapshot}"],
        "fix": "remove the whitespace errors the output lists, stage the result"},
    "spec-docs": {
        "enabled": True, "enforced": True, "scope": "tree", "stages": ["pre-commit", "ci"], "paths": ["**"],
        "requires": ["docs/DOCUMENTS.json"],
        # -I: inherited Python settings, such as PYTHONPATH, cannot replace the environment's parser.
        "run": ["{python}", "-I", "{house_rules}/" + SPEC_SCRIPTS + "/spec_docs.py", "check", "--root", ".",
                "--rev", "{snapshot}"],
        "fix": "apply the remedy for each code in the spec checker's diagnostic table, "
               "run spec_docs.py generate, stage the result"},
}
# Every effective definition, built-in or repository, starts from these values for the fields it omits.
DEFINITION_DEFAULTS = {"enabled": True, "enforced": True, "scope": "tree", "requires": []}
REPOSITORY_REQUIRED = ("run", "stages", "paths", "fix", "reason")
REFUSAL = {"pre-commit": ("Commit refused", "stage the fixes and commit again"),
           "pre-push": ("Push refused", "commit the fixes and push again"),
           "ci": ("Run failed", "commit the fixes and run the checks again")}
LABELS = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "error": "ERROR", "skipped": "SKIP"}


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


def build_snapshot(root, head, from_index, handed=None):
    """Return (commit, tree, parent) of one snapshot: a commit, or a new commit of the staged index.

    For an index snapshot, `parent` is the commit HEAD named when the run read it, or None before the first
    commit; HEAD is read once, so the snapshot's parent and its base are the same commit. `handed` is the
    snapshot the handing runner built before it resolved House Rules; it is used as it is, never built again.
    """
    if handed:
        snapshot, tree, parent = handed["snapshot"], handed["tree"], handed["parent"]
        if (commit_id(root, snapshot) != snapshot or out(root, "rev-parse", snapshot + "^{tree}") != tree
                or (from_index and commit_id(root, snapshot + "^1") != parent)):
            raise Failure(f"the handing runner passed snapshot {snapshot[:7]}, which this clone does not hold as "
                          "passed", "run again")
        return snapshot, tree, parent
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


def tree_files(root, rev):
    """Return (every path in the snapshot, the paths that hold a file: a regular file or a symbolic link).

    A submodule's path holds a commit of another repository (a gitlink), so it is a path but no file.
    """
    files, blobs = set(), set()
    for entry in git(root, "ls-tree", "-r", "-z", "--full-tree", rev).stdout.split(b"\0"):
        if entry:
            meta, _, path = entry.partition(b"\t")
            files.add(os.fsdecode(path))
            if meta.split()[1] == b"blob":
                blobs.add(os.fsdecode(path))
    return files, blobs


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


def config_error(message):
    return Failure(f"configuration error in {CONFIG}: {message}", "fix the file through a reviewed change")


def text(value):
    return isinstance(value, str) and bool(value.strip())


def relative_path(value):
    return (text(value) and not value.startswith("/") and "\\" not in value and "\0" not in value
            and not any(part in ("", ".", "..") for part in value.split("/")))


def fields(value, where, required, optional):
    if not isinstance(value, dict):
        raise config_error(f"{where} must be an object")
    missing = [k for k in required if k not in value]
    unknown = [k for k in value if k not in required and k not in optional]
    if missing:
        raise config_error(f"{where} lacks {', '.join(missing)}")
    if unknown:
        raise config_error(f"{where} has unknown field {', '.join(unknown)}")


def check_entry(where, entry):
    def strings(key, check=text, empty=False):
        value = entry[key]
        if not isinstance(value, list) or not (value or empty) or not all(check(v) for v in value):
            raise config_error(f"{where}.{key} must be a {'' if empty else 'nonempty '}list of "
                               + ("paths" if check is relative_path else "text"))
    if "enabled" in entry and not isinstance(entry["enabled"], bool):
        raise config_error(f"{where}.enabled must be true or false")
    if "run" in entry:
        if (not isinstance(entry["run"], list) or not entry["run"]
                or not all(isinstance(v, str) for v in entry["run"])):
            raise config_error(f"{where}.run must be a nonempty list of arguments")
        if any("\0" in v for v in entry["run"]):
            raise config_error(f"{where}.run has an argument with a NUL character")
    if "stages" in entry:
        strings("stages", lambda v: v in STAGES)
        if len(set(entry["stages"])) != len(entry["stages"]):
            raise config_error(f"{where}.stages lists a stage twice")
    if "scope" in entry and entry["scope"] not in SCOPES:
        raise config_error(f"{where}.scope must be one of {', '.join(SCOPES)}")
    if "paths" in entry:
        strings("paths", relative_path)
    if "requires" in entry:
        strings("requires", relative_path, empty=True)
    for key in ("fix", "reason"):
        if key in entry and not text(entry[key]):
            raise config_error(f"{where}.{key} must be nonempty text")


def check_definition(where, definition):
    names = [name for arg in definition["run"] for name in PLACEHOLDER.findall(arg)]
    unknown = [name for name in names if name not in PLACEHOLDERS]
    if unknown:
        raise config_error(f"{where}.run uses unknown placeholder {{{unknown[0]}}}")
    if "files" in names and (definition["scope"] != "files"
                             or any("{files}" in arg and arg != "{files}" for arg in definition["run"])):
        raise config_error(f"{where}.run may use {{files}} only as a whole argument of a files-scope check")
    if definition["scope"] == "files" and "{files}" not in definition["run"]:
        raise config_error(f"{where} has scope files but its run has no whole {{files}} argument")
    hooks = [s for s in definition["stages"] if s in HOOK_STAGES]
    if hooks and "snapshot" not in names:
        raise config_error(f"{where} lists {hooks[0]} but its run has no {{snapshot}}; "
                           "a hook stage needs a check that reads the snapshot, otherwise list only ci")


def unencodable(value, where=""):
    """Yield the field path of every string in a parsed JSON value that the file system encoding cannot encode.

    A surrogate escape of a file name byte encodes; an unpaired surrogate from a JSON escape does not, and would
    crash the text report or process start. A path names fields and list positions, never the rejected text, which
    can hold a password; a field name that cannot be encoded is named by the object that holds it.
    """
    if isinstance(value, str):
        try:
            os.fsencode(value)
        except UnicodeEncodeError:
            yield where or "the file"
    elif isinstance(value, dict):
        for key, item in value.items():
            if next(unencodable(key), None) is not None:
                yield f"a field name in {where or 'the file'}"
                continue
            yield from unencodable(item, f"{where}.{key}" if where else key)
    elif isinstance(value, list):
        for number, item in enumerate(value):
            yield from unencodable(item, f"{where}[{number}]")


def printable(document, error):
    """Refuse a document that holds text the runner could not print or pass to a program."""
    where = next(unencodable(document), None)
    if where is not None:
        raise error(f"{where} holds text that cannot be printed or passed to a program")


def load_document(data):
    """Parse the file and validate what every runner reads before the handover: `version` and `sources`.

    Returns (the document, its House Rules source layer {"name", "url", "ref"}). A `house_rules` field, the pin of
    an earlier design, is refused here too. Only the runner at the run's resolved House Rules revision judges the
    rest (`effective_checks`).
    """
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise config_error(f"not valid JSON ({exc})")
    if not isinstance(document, dict):
        raise config_error("the file must be an object")
    if "version" not in document:
        raise config_error("the file lacks version")
    version = document["version"]
    if type(version) is int and version == 1:
        raise Failure(f"configuration error in {CONFIG}: version 1 is no longer read; version {CONFIG_VERSION} names "
                      "its House Rules source in a sources list",
                      f'set "version": {CONFIG_VERSION} and add "sources": {json.dumps([DEFAULT_SOURCE])}, '
                      "through a reviewed change")
    if type(version) is not int or version != CONFIG_VERSION:
        raise config_error(f"unsupported version {version!r}; this runner reads version {CONFIG_VERSION}")
    printable(document, config_error)
    if "house_rules" in document:
        raise config_error("remove house_rules: sources names the House Rules source")
    return document, source_layer(document)


def source_layer(document):
    """The House Rules source layer the file names: its one `sources` entry, validated, with its URL filled in."""
    if "sources" not in document:
        raise config_error("the file lacks sources")
    sources = document["sources"]
    if not isinstance(sources, list) or not sources:
        raise config_error("sources must be a nonempty list")
    if len(sources) > MAX_SOURCES:
        raise config_error(f"sources lists {len(sources)} entries; at most {MAX_SOURCES} are allowed")
    entry = sources[0]
    fields(entry, "sources[0]", ("name", "ref"), ("url",))
    if entry["name"] != HOUSE_RULES:
        raise config_error(f'sources[0].name must be "{HOUSE_RULES}": the first layer is House Rules')
    for number, later in enumerate(sources[1:], 1):
        if isinstance(later, dict) and later.get("name") == HOUSE_RULES:
            raise config_error(f'sources[{number}] is named "{HOUSE_RULES}"; only the first source is House Rules')
    if len(sources) > 1:
        raise Failure(f"{HOUSE_RULES}: {CONFIG}: custom source layers are not supported by this runner yet (#217)",
                      f"remove the extra entry from sources in {CONFIG}")
    url = entry.get("url", DEFAULT_URL)
    if not text(url) or "\0" in url:
        raise config_error("sources[0].url must be nonempty text")
    shown_url(url)  # a URL that cannot be parsed stops here, before any message could show it
    ref = entry["ref"]
    if isinstance(ref, str) and SHA256_COMMIT.fullmatch(ref):
        raise Failure(f"configuration error in {CONFIG}: sources[0].ref names a 64-digit commit; SHA-256 sources are "
                      "not supported yet", "use the source's SHA-1 commit or a branch, through a reviewed change")
    if not text(ref) or not (COMMIT.fullmatch(ref) or branch_name(ref)):
        raise config_error(f"sources[0].ref must be a branch name or a full commit identity of 40 hexadecimal "
                           f"digits, not {ref!r}")
    return {"name": entry["name"], "url": url, "ref": ref.lower() if COMMIT.fullmatch(ref) else ref}


def branch_name(ref):
    """Whether `ref` is a valid branch name, as `git check-ref-format --branch` judges it."""
    if "\0" in ref:
        return False
    return git(".", "check-ref-format", "--branch", ref, foreign=True, check=False).returncode == 0


def check_budgets(budgets, error):
    """Validate a `budgets` object; `error` builds the configuration error of the file it came from."""
    if not isinstance(budgets, dict):
        raise error("budgets must be an object")
    unknown = [k for k in budgets if k not in HOOK_STAGES]
    if unknown:
        raise error(f"budgets has unknown field {', '.join(unknown)}")
    for stage, entry in budgets.items():
        if not isinstance(entry, dict) or sorted(entry) != ["reason", "seconds"]:
            raise error(f"budgets.{stage} must be an object with seconds and reason")
        seconds = entry["seconds"]
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not seconds > 0:
            raise error(f"budgets.{stage}.seconds must be a positive number")
        if not text(entry["reason"]):
            raise error(f"budgets.{stage}.reason must be nonempty text")
    return budgets


def check_git_settings(settings):
    """Validate `git_settings`: Git setting names mapped to {"value", "reason"}; return {name: value}.

    No entry may set what the runner sets, or include another configuration file, whose settings would come from
    outside the configuration.
    """
    if not isinstance(settings, dict):
        raise config_error("git_settings must be an object")
    values = {}
    for name, entry in settings.items():
        if not GIT_SETTING.fullmatch(name):
            raise config_error(f"git_settings has {name!r}, which is no Git setting name (section.key or "
                               "section.subsection.key)")
        section, key = name.split(".", 1)[0].lower(), name.rsplit(".", 1)[1].lower()
        if f"{section}.{key}" in RUNNER_GIT_SETTINGS:
            raise config_error(f"git_settings.{name} is set by the runner for every check")
        if section in ("include", "includeif"):
            raise config_error(f"git_settings.{name} would include another configuration file; set each setting "
                               "itself")
        fields(entry, f"git_settings.{name}", ("value", "reason"), ())
        if not isinstance(entry["value"], str) or "\0" in entry["value"]:
            raise config_error(f"git_settings.{name}.value must be text without a NUL character")
        if not text(entry["reason"]):
            raise config_error(f"git_settings.{name}.reason must be nonempty text")
        values[name] = entry["value"]
    return values


def local_error(message):
    return Failure(f"configuration error in {LOCAL_CONFIG}: {message}",
                   f"fix or remove {LOCAL_CONFIG}, which the working tree of this clone holds")


def parse_local(data):
    """Validate the local file: an object that may set only `budgets`, so it can never change a check's result."""
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise local_error(f"not valid JSON ({exc})")
    if not isinstance(document, dict):
        raise local_error("the file must be an object")
    printable(document, local_error)
    for key in document:
        if key != "budgets":
            raise local_error(f"{key} is not allowed: the local file may set only budgets, because it may not "
                              "change whether a check passes")
    return check_budgets(document.get("budgets", {}), local_error)


def budget_override(stage, entry, layer):
    return {"id": f"budgets.{stage}", "layer": layer, "change": f"seconds: {json.dumps(entry['seconds'])}",
            "reason": entry["reason"]}


def effective_checks(data, local=None):
    """Validate the whole file against this runner's built-in definitions and return the effective set.

    The layers apply in order: the House Rules built-ins, the repository's entries, then the local file's budgets,
    each replacing what an earlier layer set for the same check or stage. `local` is the local file's bytes or None.
    """
    document, _ = load_document(data)
    fields(document, "the file", ("version", "sources", "checks"), ("budgets", "git_settings"))
    budgets = dict(check_budgets(document.get("budgets", {}), config_error))
    git_settings = check_git_settings(document.get("git_settings", {}))
    setting_overrides = [{"id": f"git_settings.{name}", "layer": "repository",
                          "change": f"value: {json.dumps(value)}", "reason": document["git_settings"][name]["reason"]}
                         for name, value in git_settings.items()]
    entries = document["checks"]
    if not isinstance(entries, dict):
        raise config_error("checks must be an object")
    checks, overrides = [], []
    for identity in [*BUILTINS, *(k for k in entries if k not in BUILTINS)]:
        if "\0" in identity:
            raise config_error("checks has an identity with a NUL character: "
                               + identity.encode("unicode_escape").decode())
        where = f"checks.{identity}"
        entry = entries.get(identity, {})
        default = BUILTINS.get(identity)
        required = () if default else REPOSITORY_REQUIRED
        if isinstance(entry, dict) and "enforced" in entry:
            raise config_error(f"{where}.enforced is set by House Rules, not by the configuration; "
                               "to turn the check off, set enabled: false with a reason")
        fields(entry, where, required, [f for f in FIELDS if f not in required])
        check_entry(where, entry)
        base = dict(DEFINITION_DEFAULTS, **(default or {}))
        definition = dict(base, **entry)
        if default:
            changed = [k for k in entry if k != "reason" and entry[k] != base.get(k)]
            if changed and "reason" not in entry:
                raise config_error(f"{where} changes {', '.join(changed)} without a reason")
            if changed:
                overrides.append({"id": identity, "layer": "repository", "reason": entry["reason"],
                                  "change": ", ".join(f"{k}: {json.dumps(entry[k])}" for k in changed)})
        check_definition(where, definition)
        checks.append(dict(definition, id=identity, layer=HOUSE_RULES if default else "repository"))
    layers = {stage: "repository" for stage in budgets}
    for stage, entry in (parse_local(local) if local is not None else {}).items():
        budgets[stage], layers[stage] = entry, "local"
    overrides += [budget_override(stage, budgets[stage], layers[stage]) for stage in budgets] + setting_overrides
    return {"checks": checks, "overrides": overrides, "budgets": budgets, "git_settings": git_settings}


def config_data(root, rev, blobs):
    if CONFIG not in blobs:
        return None
    return git(root, "cat-file", "blob", f"{rev}:{CONFIG}").stdout


def staged_data(root):
    proc = git(root, "cat-file", "blob", ":" + CONFIG, check=False)
    return proc.stdout if proc.returncode == 0 else None


def local_data(root):
    """The local file's bytes from the working tree, or None when the clone has none."""
    try:
        return (root / LOCAL_CONFIG).read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise local_error(f"cannot read it ({exc.strerror or exc})")


# Pinning and cache -----------------------------------------------------------------------

def cache_root():
    if os.environ.get("HOUSE_RULES_CACHE"):
        return Path(os.environ["HOUSE_RULES_CACHE"]).resolve()
    if os.environ.get("XDG_CACHE_HOME"):
        return Path(os.environ["XDG_CACHE_HOME"]).resolve() / "house-rules"
    return Path.home() / ".cache" / "house-rules"


def cache_failure(exc):
    return Failure(f"cannot write the House Rules cache at {cache_root()} ({exc})",
                   "make that folder writable, or set HOUSE_RULES_CACHE to a writable folder, and run again")


def own_tree():
    return Path(__file__).resolve().parents[3]


def own_revision():
    tree = own_tree()
    if tree.parent.name == "revisions" and re.fullmatch(r"[0-9a-f]{40}", tree.name):
        return tree.name
    return None


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


def utc(seconds=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


def url_parts(url):
    """The URL split into its parts; a URL the parser refuses is a preparation failure that shows nothing of it."""
    try:
        return urllib.parse.urlsplit(url)
    except ValueError:
        # The parser's message can hold the URL's authority, with its user name and password, so it is left out.
        raise Failure(f"the House Rules URL in {CONFIG} cannot be parsed", "correct it") from None


def kept_login(parts):
    """The user name an ssh URL keeps in messages and in its cache key, or None.

    An ssh login can choose the repository, such as through its home folder, so it is part of the source; its
    password, and the user name and password of any other transport, are not.
    """
    if parts.scheme.lower() != "ssh" or "@" not in parts.netloc:
        return None
    return parts.netloc.rpartition("@")[0].split(":", 1)[0] or None


def shown_url(url):
    """The URL as messages and reports show it: without the password, and without the user name except an ssh login."""
    parts = url_parts(url)
    if "@" not in parts.netloc:
        return url
    login, host = kept_login(parts), parts.netloc.rpartition("@")[2]
    return urllib.parse.urlunsplit(parts._replace(netloc=f"{login}@{host}" if login else host))


def hidden(text, url):
    """`text`, such as Git's error, with the URL's user name and password removed wherever they appear.

    Git itself always receives the full URL; only what the runner prints is changed.
    """
    parts = url_parts(url)
    if "@" not in parts.netloc:
        return text
    userinfo, login = parts.netloc.rpartition("@")[0], kept_login(parts)
    if login is None:
        secrets = {userinfo, *userinfo.split(":", 1)}
    else:  # an ssh login stays; only its password is hidden
        secrets = {userinfo.split(":", 1)[1]} if ":" in userinfo else set()
    secrets = {value for secret in secrets for value in (secret, urllib.parse.unquote(secret)) if value}
    text = text.replace(url, "\0")  # Git's error text holds no NUL, so this stands for the URL alone
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret + "@", "") if login is None else text.replace(":" + secret + "@", "@")
        text = text.replace(secret, "***")
    return text.replace("\0", shown_url(url))


def revision_folder(revision):
    return cache_root() / "revisions" / revision


def prepared(revision):
    """Whether the cache holds the commit's complete tree and the time it was first placed."""
    folder = revision_folder(revision)
    return (folder / RUNNER).is_file() and fetch_time_path(folder).is_file()


def fetch_time_path(tree):
    """revisions/<commit>.fetched: one line, the UTC time the commit's folder was first placed in the cache."""
    return Path(str(tree) + ".fetched")


def record_fetch_time(tree):
    """Write the commit's first-fetch time once; when another process already wrote it, keep that time."""
    path = fetch_time_path(tree)
    descriptor, temporary = tempfile.mkstemp(prefix=".fetched-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(utc() + "\n")
        try:
            os.link(temporary, str(path))  # fails when the time is there already, so the first one stays
        except FileExistsError:
            pass
    finally:
        os.unlink(temporary)


def source_key(url):
    """The source's identity in the cache: (scheme, key text), from its URL without passwords.

    The scheme is the transport, such as https, http, ssh or file. An ssh URL keeps its login and its path exactly as
    written: ssh://<login>@<host><path>. An scp-like URL, login@host:path, counts as ssh and gives
    ssh:<login>@<host>:<path>, so a path relative to the login's home folder stays relative. Any other URL gives
    <scheme>://<host>/<path> without user name and password; a file URL or a plain path is file, with its absolute
    path and no host. There empty path segments are dropped, so a trailing or doubled slash names the same source.
    """
    parts = url_parts(url)
    scp = not parts.scheme and ":" in url.split("/", 1)[0]
    if scp:
        return "ssh", "ssh:" + url
    if parts.scheme.lower() == "ssh":
        login, host = kept_login(parts), parts.netloc.rpartition("@")[2]
        return "ssh", f"ssh://{login + '@' if login else ''}{host}{parts.path}"
    if parts.scheme and parts.scheme != "file":
        scheme, host, path = parts.scheme.lower(), parts.netloc.rpartition("@")[2], parts.path
    else:
        scheme, host, path = "file", "", parts.path if parts.scheme == "file" else url
    return scheme, f"{scheme}://{host}" + "".join("/" + segment for segment in path.split("/") if segment)


def hashed(name):
    """A cache file or folder name for `name`: its SHA-256, so any length or character makes one bounded name."""
    return hashlib.sha256(name.encode("utf-8", "surrogateescape")).hexdigest()


def source_folder(url):
    """The cache folder of one source: sources/<SHA-256 of its key>, holding source.json, branches/ and lock."""
    return cache_root() / "sources" / hashed(source_key(url)[1])


@contextlib.contextmanager
def source_lock(url):
    """Hold the source's lock: one process at a time asks for its branches, fetches its commits into temporary
    repositories in the source's folder and writes its branch records.

    The lock is advisory (flock) and the system releases it when its process ends, however it ends.
    """
    folder = source_folder(url)
    folder.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(folder / "lock"), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        if not (folder / "source.json").is_file():  # names the source for a reader of the cache; no run reads it
            scheme, key = source_key(url)
            publish(folder / "source.json", {"url": shown_url(url), "scheme": scheme, "key": key})
        yield
    finally:
        os.close(descriptor)


def fetch_revision(url, revision):
    """Put one House Rules commit into the cache unless it is there; return (Git's error, removal error).

    Both are None after a successful fetch. Call it under the source's lock. Each fetch uses its own new bare
    repository, a .partial-* folder in the source's folder, fetches the
    commit with depth 1, extracts it into a temporary revision folder, renames that folder into place and deletes
    the repository. Nothing Git locks is ever used again, so an interrupted fetch leaves only a temporary folder
    that no run uses. When the fetch failed and removing its repository failed too, the removal error names that
    removal; the caller then reports the fetch with its own repair and adds the removal to the cause.
    """
    if prepared(revision):
        return None, None
    repository = partial(source_folder(url))
    failure = error = None
    try:
        error = fetch_into(repository, url, revision)
    except Failure as exc:
        failure = exc
    except OSError as exc:
        failure = cache_failure(exc)
    try:
        shutil.rmtree(str(repository))
    except OSError as exc:
        if failure is None and error is None:
            raise  # the caller reports it as a cache failure
        removal = f"removing the temporary repository {repository} failed too ({exc})"
        if failure is None:
            return error, removal
        # Keep the preparation failure and its repair, with the failed removal added to its cause.
        raise Failure(f"{failure.cause}; {removal}", failure.repair)
    if failure is not None:
        raise failure
    return error, None


def fetch_failure(cause, removal, repair):
    """The preparation failure of a failed fetch; a failed removal of its repository is added to the cause."""
    return Failure(f"{cause}; {removal}" if removal else cause, repair)


def fetch_into(repository, url, revision):
    """Fetch `revision` into the empty bare `repository` and put its files into the cache; return None or Git's error."""
    git(repository, "init", "--quiet", "--bare", ".", foreign=True)
    proc = git(repository, *PROGRESS, "fetch", "--quiet", "--depth=1", "--no-tags", url,
               f"{revision}:refs/pins/{revision}", foreign=True, check=False)
    if proc.returncode:
        return last_line(proc.stderr)
    temporary = partial(revision_folder(revision).parent)
    extract(repository, revision, temporary)
    if not (temporary / RUNNER).is_file():
        raise Failure(f"House Rules {revision} has no repository checks runner ({RUNNER})",
                      f"set sources in {CONFIG} to a House Rules repository and ref that have one, "
                      "or HOUSE_RULES_REVISION to a revision that has one")
    for folder, _, names in os.walk(str(temporary)):
        for name in names:
            path = os.path.join(folder, name)
            if not os.path.islink(path):
                os.chmod(path, os.stat(path).st_mode & ~0o222)
    record_fetch_time(place(temporary, revision_folder(revision), lambda path: (path / RUNNER).is_file()))
    return None


def ask_branch(url, branch):
    """Return (the branch's commit, None), or (None, Git's error).

    Git ends each record with a line feed and puts a tab between the commit and the reference; only those bytes
    delimit, so a branch name keeps every other character, such as U+2028. Names decode losslessly.
    """
    name = "refs/heads/" + branch
    proc = git(cache_root(), *PROGRESS, "ls-remote", url, name, foreign=True, check=False)
    if proc.returncode:
        return None, last_line(proc.stderr)
    heads = [line.split(b"\t", 1) for line in proc.stdout.split(b"\n")]
    revision = next((head[0].decode("ascii", "replace") for head in heads
                     if len(head) == 2 and head[1].decode("utf-8", "surrogateescape") == name), None)
    if revision is None or not COMMIT.fullmatch(revision):
        return None, f"the repository has no {branch} branch"
    return revision, None


def branch_record_path(url, branch):
    """Where the cache records the commit last resolved for one source and branch: branches/<SHA-256 of branch>.json."""
    return source_folder(url) / "branches" / (hashed(branch) + ".json")


def branch_record(url, branch):
    """The commit last resolved for `branch` of `url`, as {"url", "branch", "revision", "fetched"}, or None.

    The record's URL holds no user name or password. A record counts only when its URL has this source's key and its
    branch is `branch`, so a record in the wrong place, such as after a hash collision, is never used.
    """
    try:
        record = json.loads(branch_record_path(url, branch).read_text())
    except (OSError, ValueError):
        return None
    if not (isinstance(record, dict) and isinstance(record.get("url"), str) and record.get("branch") == branch
            and isinstance(record.get("revision"), str) and COMMIT.fullmatch(record["revision"])
            and isinstance(record.get("fetched"), str)):
        return None
    try:
        owner = source_key(record["url"])[1]
    except Failure:
        return None
    return record if owner == source_key(url)[1] else None


def write_branch_record(url, record):
    """Publish `record` for its source and branch; under the source's lock the latest successful resolution wins."""
    path = branch_record_path(url, record["branch"])
    path.parent.mkdir(parents=True, exist_ok=True)
    publish(path, record)


def publish(path, data):
    """Write `data` as JSON to `path` through a temporary file in its folder, so a reader sees the old or new file."""
    descriptor, temporary = tempfile.mkstemp(prefix=".partial-", dir=str(path.parent))
    with os.fdopen(descriptor, "w") as handle:
        json.dump(data, handle)
    os.replace(temporary, str(path))


def override_revision():
    """The commit HOUSE_RULES_REVISION names for this one run, or None when it is unset."""
    value = os.environ.get("HOUSE_RULES_REVISION")
    if value is None:
        return None
    if not COMMIT.fullmatch(value):
        raise Failure(f"HOUSE_RULES_REVISION {value!r} is not a full 40-character commit identity",
                      f"set it to a full commit identity, or unset it to run at the ref {CONFIG} names")
    return value.lower()


def handed_resolution(source=None):
    """The resolution the handing runner passed to this runner, when it names this runner's own revision.

    With `source`, the source this runner read from the configuration now, a handed resolution of another source
    stops the run: the configuration changed between the handing runner's read and this one.
    """
    try:
        resolution = json.loads(HANDED or "null")
    except ValueError:
        return None
    if not (isinstance(resolution, dict) and resolution.get("revision") == own_revision()
            and resolution.get("source") in SOURCES and isinstance(resolution.get("fetched"), str)
            and all(isinstance(resolution.get(k), str) for k in ("name", "url", "ref", "tree"))):
        return None
    if source is not None and not same_source(resolution, source):
        raise Failure("the configuration changed during the run", "run again")
    return resolution


def handed_snapshot():
    """The snapshot the handing runner built, accepted only together with its resolution."""
    if handed_resolution() is None:
        return None
    try:
        snapshot = json.loads(HANDED_SNAPSHOT or "null")
    except ValueError:
        return None
    if (isinstance(snapshot, dict) and snapshot.get("source") in ("index", "commit")
            and all(isinstance(snapshot.get(k), str) and OBJECT.fullmatch(snapshot[k]) for k in ("snapshot", "tree"))
            and (snapshot.get("parent") is None or (isinstance(snapshot["parent"], str)
                                                    and OBJECT.fullmatch(snapshot["parent"])))):
        return snapshot
    return None


def resolve(source, offline_repair=None):
    """Resolve the House Rules layer `source` for this run: the override, else its commit ref, else its branch
    fetched now, else the commit last resolved for that branch.

    Returns the layer {"name", "url", "ref", "revision", "source", "fetched"}, its URL without authentication, plus
    "warning" for a cached branch. Called once per run; the revision it returns is prepared in the cache.
    """
    resolution = handed_resolution(source)
    if resolution:
        return resolution
    url, ref = source["url"], source["ref"]
    shown = shown_url(url)
    layer = {"name": source["name"], "url": shown, "ref": ref}
    try:
        override = override_revision()
        if override or COMMIT.fullmatch(ref):
            revision = override or ref
            with source_lock(url):
                error, removal = fetch_revision(url, revision)
            if error:
                repair = ("run again when online, or set HOUSE_RULES_REVISION to a commit that exists there" if override
                          else f"run again when online, or set the ref in {CONFIG} to a commit that exists there")
                raise fetch_failure(f"cannot fetch House Rules {revision} from {shown} ({hidden(error, url)})",
                                    removal, repair)
            return dict(layer, revision=revision, source="override" if override else "pinned", fetched=None)
        with source_lock(url):
            fetched = utc()
            revision, error = ask_branch(url, ref)
            removal = None
            if not error:
                error, removal = fetch_revision(url, revision)
            if not error:
                write_branch_record(url, {"url": shown, "branch": ref, "revision": revision, "fetched": fetched})
                return dict(layer, revision=revision, source="fetched", fetched=fetched)
            record = branch_record(url, ref)
        # A failed removal stops the run even when the cache holds an earlier commit, as every cache failure does.
        if removal or record is None or not prepared(record["revision"]):
            raise fetch_failure(f"cannot fetch House Rules {ref} from {shown} ({hidden(error, url)})", removal,
                                offline_repair or "run again when online")
        return dict(layer, revision=record["revision"], source="offline", fetched=record["fetched"],
                    warning=f"cannot fetch House Rules {ref} from {shown} ({hidden(error, url)}); using the {ref} "
                            f"last fetched, {record['revision']}, fetched {record['fetched']}")
    except OSError as exc:
        raise cache_failure(exc)


def extract(source, revision, folder):
    environ = dict({k: v for k, v in os.environ.items() if k not in LOCAL_GIT_ENV}, **NO_REPLACE)
    archive = subprocess.Popen(["git", "archive", "--format=tar", revision], cwd=str(source), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=environ)
    try:
        tar = subprocess.run(["tar", "-xf", "-", "-C", str(folder)], stdin=archive.stdout, capture_output=True)
    except OSError as exc:
        archive.kill()
        archive.communicate()
        raise Failure(f"cannot start tar to extract House Rules {revision} ({exc.strerror or exc})",
                      "install tar and run again")
    archive.stdout.close()
    error = archive.stderr.read()
    if archive.wait() or tar.returncode:
        raise Failure(f"cannot extract House Rules {revision} ({last_line(error + tar.stderr)})",
                      f"run `{runner_command('prepare')}` again")


def prepared_at(tree):
    """When the cache first placed the commit's folder `tree`, from revisions/<commit>.fetched.

    A tree outside this cache that has no such file, such as a runner started from another cache folder, gives
    the folder's modification time instead.
    """
    try:
        recorded = fetch_time_path(tree).read_text().strip()
    except OSError:
        recorded = ""
    return recorded if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", recorded) else utc(os.stat(str(tree)).st_mtime)


def dispatch(tree, argv, resolution, stdin=None, snapshot=None):
    """Replace this process by the runner in `tree`, unless this file is that runner.

    The started runner receives `resolution`, so it uses the same revision without resolving again,
    `snapshot`, the snapshot this process built, so it checks that same content, and `stdin`, the input this
    process already read, as its standard input.
    """
    runner = tree / RUNNER
    if runner.resolve() == Path(__file__).resolve():
        return
    sys.stdout.flush()
    if stdin is not None:
        try:
            with tempfile.TemporaryFile() as saved:
                saved.write(stdin)
                saved.seek(0)
                os.dup2(saved.fileno(), 0)
        except OSError as exc:
            raise Failure(f"cannot save standard input for the resolved runner ({exc})",
                          "free space in or repair access to the temporary folder, and run again")
    os.environ[RESOLVED] = json.dumps(resolution)
    if snapshot is not None:
        os.environ[SNAPSHOT] = json.dumps(snapshot)
    try:
        os.execv(sys.executable, [sys.executable, "-I", str(runner), *argv])
    except OSError as exc:
        raise Failure(f"cannot start the resolved runner {runner} ({exc})", f"run `{runner_command('prepare')}` again")


def resolve_layers(data, offline_repair=None):
    """Resolve the source layers that `data`, the bytes of a configuration, names, for this run.

    Returns the layers in order, House Rules first, each {"name", "url", "ref", "revision", "source", "fetched",
    "tree"}, plus "warning" on a layer resolved offline. Each layer's commit is prepared in the cache at `tree`.
    This runner resolves only the House Rules layer.
    """
    _, source = load_document(data)
    layer = resolve(source, offline_repair)
    revision = layer["revision"]
    tree = own_tree() if own_revision() == revision else revision_folder(revision)
    if layer["fetched"] is None:
        layer["fetched"] = prepared_at(tree)  # a commit ref or an override: when the cache fetched that commit
    return [dict(layer, tree=str(tree))]


def resolved_tree(argv, data, stdin=None, offline_repair=None, snapshot=None):
    """Resolve the layers `data` names; return (the House Rules tree, the layers), or start the runner there.

    The started runner replaces this process and receives the same House Rules layer and `snapshot`.
    """
    layers = resolve_layers(data, offline_repair)
    tree = Path(layers[0]["tree"])
    dispatch(tree, argv, layers[0], stdin, snapshot)
    return tree, layers


def cached_resolution(source):
    """What a run would resolve without any network: (layer or None, its prepared tree or None).

    The override when set, else the commit ref, else the commit last resolved for the branch; `status` reports it
    and never fetches.
    """
    resolution = handed_resolution(source)
    if resolution is None:
        layer = {"name": source["name"], "url": shown_url(source["url"]), "ref": source["ref"]}
        override = override_revision()
        if override or COMMIT.fullmatch(source["ref"]):
            resolution = dict(layer, revision=override or source["ref"], source="override" if override else "pinned",
                              fetched=None)
        else:
            record = branch_record(source["url"], source["ref"])
            if record is None:
                return None, None
            resolution = dict(layer, revision=record["revision"], source="offline", fetched=record["fetched"])
    revision = resolution["revision"]
    tree = own_tree() if own_revision() == revision else revision_folder(revision)
    if not (tree / RUNNER).is_file():
        return resolution, None
    if resolution["fetched"] is None:
        resolution["fetched"] = prepared_at(tree)
    return resolution, tree


def label(layer):
    """How a report names where a layer's commit came from, its URL and when the cache fetched it."""
    what = {"fetched": f"branch {layer['ref']}", "offline": f"branch {layer['ref']}", "pinned": "commit",
            "override": "HOUSE_RULES_REVISION"}[layer["source"]]
    when = f"cached {layer['fetched']}" if layer["fetched"] else "not cached yet"
    return f"{layer['source']} {what} of {layer['url']}, {when}"


def same_source(layer, source):
    """Whether a snapshot's House Rules source is the one the run resolved."""
    return (layer["name"], layer["url"], layer["ref"]) == (source["name"], shown_url(source["url"]), source["ref"])


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


def environment(tree):
    """Return (interpreter, environment folder); the folder name digests the lock and interpreter version."""
    python, version = runtime_interpreter(tree)
    lock = tree / SPEC_SCRIPTS / "requirements.lock"
    try:
        data = lock.read_bytes()
    except OSError as exc:
        raise Failure(f"cannot read {lock} ({exc})", f"run `{runner_command('prepare')}` again")
    digest = hashlib.sha256(data + b"\0CPython " + version.encode()).hexdigest()
    return python, cache_root() / "environments" / digest


# A push fetches House Rules and builds its environment itself, so pushing again online repairs either.
PUSH_AGAIN = "push again when online; the push fetches House Rules and builds its environment itself"


def prepare_environment(tree, offline_repair=None):
    python, final = environment(tree)
    if (final / "bin" / "python").exists():
        return final / "bin" / "python"
    lock = tree / SPEC_SCRIPTS / "requirements.lock"
    try:
        temporary = partial(final.parent)
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

def command_run(args, argv):
    run = {"layers": [], "warnings": [], "snapshots": []}
    error, nothing = None, None
    try:
        nothing = check_stage(args, argv, run)
    except Failure as exc:
        error = exc
    snapshots = run["snapshots"]
    result = "error" if error else "fail" if any(s["result"] == "fail" for s in snapshots) else "pass"
    report = {"version": 3, "stage": args.stage, "result": result, "layers": run["layers"],
              "warnings": run["warnings"], "snapshots": snapshots}
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


def check_stage(args, argv, run):
    """Check each snapshot of the stage in turn, appending its entry; return why there is nothing to check, or None.

    The first snapshot with a configuration resolves its House Rules layer once for the whole run, into `run`;
    every later snapshot must name the same layer. A preparation failure stops the run; the snapshots checked
    before it stay in `run["snapshots"]`.
    """
    snapshots = run["snapshots"]
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
    offline = PUSH_AGAIN if pushing else None
    house_rules = layer = None
    local = None
    # A run that one runner handed over checks the snapshot that runner built; a push names its own commits.
    handed = None if pushing else handed_snapshot()
    for ref, head, remote_commit in items:
        try:
            if pushing:
                pushed, head = head, commit_id(root, head)
                if head is None:
                    raise Failure(f"the pushed reference {ref} points at {pushed[:7]}, which resolves to no commit",
                                  "change the reference, or push it without the hook's check under the rule line")
            target = snapshot_target(root, ref, head, from_index, remote_commit, handed)
            if target["data"] is None:
                snapshots.append(unadopted(target))
            else:
                # Read only the version and sources before handing over: the resolved runner judges the rest.
                _, source = load_document(target["data"])
                if house_rules is None:
                    passed = None if pushing else {k: target[k] for k in ("snapshot", "tree", "parent", "source")}
                    house_rules, layers = resolved_tree(argv, target["data"], stdin, offline, passed)
                    layer = layers[0]
                    run["layers"] = [{k: layer[k] for k in ("name", "url", "ref", "revision", "source", "fetched")}]
                    run["warnings"] += [layer["warning"]] if layer.get("warning") else []
                    local = local_data(root)
                if not same_source(layer, source):
                    # The shared resolver of #217 replaces this with a handover per snapshot.
                    raise Failure("the pushed commits declare different House Rules sources", "push them separately")
                config = effective_checks(target["data"], local)
                known = [c["id"] for c in config["checks"]]
                for name in args.only or ():
                    if name not in known:
                        raise Failure(f"unknown check '{name}' in --only", f"name one of {', '.join(known)}")
                snapshots.append(check_snapshot(root, args, target, config, house_rules, pushing))
            if from_index and index_tree(root) != target["tree"]:
                raise Failure("the staged index changed during the run, so the checks did not see the content Git "
                              "would commit", "review what was staged and commit again")
        except Failure as exc:
            exc.reference = ref
            raise
    return None


def snapshot_target(root, ref, head, from_index, remote_commit, handed=None):
    snapshot, tree, parent = build_snapshot(root, head, from_index, handed)
    files, blobs = tree_files(root, snapshot)
    return {"ref": ref, "snapshot": snapshot, "tree": tree, "parent": parent, "files": files, "blobs": blobs,
            "remote_commit": remote_commit, "source": "index" if from_index else "commit",
            "data": config_data(root, snapshot, blobs)}


def snapshot_entry(target, config, base, result, checks, warnings):
    return {"reference": target["ref"], "source": target["source"], "base": base, "snapshot": target["snapshot"],
            "result": result, "checks": checks, "overrides": config["overrides"] if config else [],
            "warnings": warnings}


def unadopted(target):
    return snapshot_entry(target, None, None, "pass", [],
                          [f"no {CONFIG} in this snapshot; repository checks are not adopted here"])


def check_snapshot(root, args, target, config, house_rules, pushing):
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
    values = {"base": base, "snapshot": snapshot, "house_rules": str(house_rules), "python": None}
    if any(uses(check, "python") for check in running):
        values["python"] = str(prepare_environment(house_rules, PUSH_AGAIN if pushing else None))
    if any(arg.startswith("--attr-source") for check in running for arg in check["run"]):
        if git(root, f"--attr-source={snapshot}", "rev-parse", "--git-dir", check=False).returncode:
            raise Failure(f"the installed Git ({out(root, '--version')}) cannot read attributes from a commit "
                          "(--attr-source)", "install a Git that supports it")

    started, results = time.monotonic(), []
    env = check_environment(args.stage, base, snapshot, config["git_settings"])
    for check, reason, inputs in plan:
        result = {"id": check["id"], "layer": check["layer"], "status": "skipped", "seconds": None,
                  "command": None, "output": "", "fix": None,
                  "rerun": runner_command(*rerun, "--only", check["id"]), "skip_reason": reason}
        if reason is None:
            command = expand(check["run"], values, inputs)
            begin = time.monotonic()
            status, output = start_check(command, root, env)
            # A failing check that House Rules does not enforce yet warns and leaves its snapshot passing.
            status = status or ("pass" if output[0] == 0 else "fail" if check["enforced"] else "warn")
            result.update(status=status, seconds=round(time.monotonic() - begin, 3), command=command,
                          output=output[1], fix=check["fix"] if status != "pass" else None)
        results.append(result)
    total = time.monotonic() - started
    ran = [r for r in results if r["status"] != "skipped"]
    warnings = []
    budget = config["budgets"].get(args.stage, {}).get("seconds") or (
        DEFAULT_BUDGET if args.stage == "pre-commit" else None)
    if budget is not None and total > budget:
        slowest = max(ran, key=lambda r: r["seconds"])["id"] if ran else None
        warnings.append(f"budget: {args.stage} took {total:.1f} s of {budget:g} s"
                        + (f"; slowest check {slowest}" if slowest else ""))
    order = {"error": 0, "fail": 1, "warn": 2, "pass": 3, "skipped": 4}
    results.sort(key=lambda r: order[r["status"]])
    outcome = "fail" if any(r["status"] in ("fail", "error") for r in ran) else "pass"
    return snapshot_entry(target, config, base, outcome, results, warnings)


def select(check, stage, from_index, target, changed):
    """Return (skip reason or None, inputs for a files-scope check).

    Inputs are paths that hold a file in the snapshot, a regular file or a symbolic link; a submodule is never one.
    """
    blobs = target["blobs"]
    if not check["enabled"]:
        return f"disabled: {check['reason']}", None
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
            return "no matching input", None
        return None, inputs
    selected = matches(changed)
    if not selected:
        return ("no staged input" if stage == "pre-commit" else "no changed input"), None
    inputs = [n for n in selected if n in blobs]
    if check["scope"] == "files" and not inputs:
        # A changed path that is still in the snapshot but holds no file is a submodule.
        return ("no matching input" if any(n in target["files"] for n in selected) else "only deleted inputs"), None
    return None, inputs


# Every check reads Git without personal or system configuration and without the system attributes file.
CHECK_GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1", **NO_REPLACE}


def check_environment(stage, base, snapshot, settings):
    """The environment of a check: the runner's own, without variables that bind Git to another repository or pass
    it configuration, plus CHECK_GIT_ENV, the CHECK_ values and Git configuration the runner sets itself.

    Git finds the clone's own Git directory from the repository root, the check's working folder. The runner passes
    core.attributesFile=/dev/null, so Git reads no personal attributes file such as ~/.config/git/attributes, which
    it reads by default even without a global configuration, followed by the configuration's `git_settings`.
    """
    env = {k: v for k, v in os.environ.items()
           if k not in LOCAL_GIT_ENV and not k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    env.update(CHECK_GIT_ENV, CHECK_STAGE=stage, CHECK_BASE=base, CHECK_SNAPSHOT=snapshot)
    passed = [("core.attributesFile", os.devnull), *settings.items()]
    env["GIT_CONFIG_COUNT"] = str(len(passed))
    for number, (name, value) in enumerate(passed):
        env[f"GIT_CONFIG_KEY_{number}"], env[f"GIT_CONFIG_VALUE_{number}"] = name, value
    return env


def start_check(command, root, env):
    """Run the check's command from the repository root; return (status or None, (exit status, output)).

    The status is "error" when the program was not found or could not start, and None when the command ran; then
    its exit status decides the result. `subprocess` finds the program on PATH and restores the default signal
    dispositions, so a check that SIGPIPE ends fails.
    """
    try:
        proc = subprocess.run(command, cwd=str(root), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
    except OSError as exc:
        return "error", (None, f"cannot start {command[0]!r}: {exc.strerror or exc}\n")
    return None, (proc.returncode, proc.stdout.decode(errors="surrogateescape"))


def expand(run, values, inputs):
    """Return the command: each `{files}` argument becomes the check's inputs, and placeholders their values."""
    command = []
    for arg in run:
        if arg == "{files}":
            command += inputs
        else:
            command.append(PLACEHOLDER.sub(lambda m: values[m.group(1)], arg))
    return command


def check_lines(results):
    lines = []
    for result in results:
        detail = result["skip_reason"] if result["status"] == "skipped" else f"{result['seconds']:.1f} s"
        lines.append(f"{LABELS[result['status']]:<6}{result['id']:<12} {detail}")
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
                     + (f", base {entry['base'][:7]}" if report["stage"] == "pre-push" else "")
                     + "".join(f", House Rules {layer['revision']} ({label(layer)})" for layer in report["layers"]))
        lines += check_lines(entry["checks"])
        lines += [override_line(o) for o in entry["overrides"]]
        lines += ["warning: " + w for w in entry["warnings"]]
        checks += entry["checks"]
    lines += ["warning: " + w for w in report["warnings"]]
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


def override_line(override):
    return f"override: {override['id']} {override['change']} ({override['layer']}); reason: {override['reason']}"


def command_prepare(args, argv):
    root = find_root()
    data = staged_data(root)
    if data is None:
        raise Failure(f"no {CONFIG} in the index", f"run `{runner_command('install')}` first")
    tree, (resolution,) = resolved_tree(argv, data)
    config = effective_checks(data, local_data(root))
    print(f"repository checks: House Rules {resolution['revision']} ({label(resolution)}) ready at {tree}")
    if resolution.get("warning"):
        print("warning: " + resolution["warning"])
    if any(c["enabled"] and uses(c, "python") for c in config["checks"]):
        print(f"repository checks: spec checker environment ready at {prepare_environment(tree).parent.parent}")
    return 0


def command_status(args, argv):
    if args.session:
        try:
            line = session_line(argv)
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
    _, source = load_document(data)
    resolution, tree = cached_resolution(source)
    prepare = runner_command("prepare")
    if tree is None:
        if resolution is None:
            print(f"repository checks: House Rules {source['ref']} not fetched yet (run: {prepare})")
        else:
            print(f"repository checks: House Rules {resolution['revision']} ({label(resolution)})")
            print(f"revision: not prepared in the cache (run: {prepare})")
        print(f"checks: unavailable until House Rules is prepared, because its runner defines the effective set "
              f"(run: {prepare})")
        return 0
    dispatch(tree, argv, resolution)  # the resolved runner prints the effective set of its own built-ins
    config = effective_checks(data, local_data(root))
    print(f"repository checks: House Rules {resolution['revision']} ({label(resolution)})")
    print(f"revision: in the cache at {tree}")
    if any(c["enabled"] and uses(c, "python") for c in config["checks"]):
        print("environment: " + (environment_problem(config, tree) or f"in the cache at {environment(tree)[1]}"))
    for stage in STAGES:
        names = [c["id"] + ("" if c["enforced"] else " (warning only)") for c in config["checks"]
                 if c["enabled"] and stage in c["stages"]]
        print(f"{stage}: {', '.join(names) or 'none'}")
    for override in config["overrides"]:
        print(override_line(override))
    return 0


def session_line(argv):
    proc = git(".", "rev-parse", "--show-toplevel", check=False)
    if proc.returncode:
        return None
    root = Path(output_text(proc.stdout))
    data = staged_data(root)
    if data is None:
        if (root / ".agents" / "rules.md").is_file():
            return f"repository checks: not installed; run: {runner_command('install')}"
        return None
    _, source = load_document(data)
    resolution, tree = cached_resolution(source)
    if tree is not None:
        dispatch(tree, argv, resolution)  # the resolved runner knows which checks need an environment
    hooks = root / out(root, "rev-parse", "--git-path", "hooks")
    missing = [name for name in HOOK_STAGES if not has_block(hooks / name)]
    # Git ignores a hook file that is not executable, so its block never runs.
    ignored = [name for name in HOOK_STAGES if name not in missing and not os.access(str(hooks / name), os.X_OK)]
    problems = [f"no hook block in {', '.join(missing)} (run: {runner_command('install')})"] if missing else []
    if ignored:
        problems.append(f"hook file {', '.join(ignored)} not executable "
                        f"(run: {shlex.join(['chmod', '+x', *(str(hooks / name) for name in ignored)])})")
    if resolution is None:
        problems.append(f"House Rules {source['ref']} not fetched yet (run: {runner_command('prepare')})")
    elif tree is None:
        problems.append(f"House Rules {resolution['revision'][:7]} not prepared in the cache "
                        f"(run: {runner_command('prepare')})")
    else:
        problem = environment_problem(effective_checks(data, local_data(root)), tree)
        problems += [problem] if problem else []
    where = f"House Rules {resolution['revision'][:7]}, {label(resolution)}" if resolution else ""
    if problems:
        return "repository checks: not ready" + (f" ({where})" if where else "") + ": " + "; ".join(problems)
    return f"repository checks: ready ({where}, hooks installed)"


def has_block(path):
    try:
        return HOOK_MARKER in path.read_text(errors="replace").splitlines()
    except OSError:
        return False


HANDED = None  # the resolution the handing runner passed, read once at start
HANDED_SNAPSHOT = None  # the snapshot the handing runner passed with it


def main(argv=None):
    global HANDED, HANDED_SNAPSHOT
    argv = sys.argv[1:] if argv is None else argv
    HANDED = os.environ.pop(RESOLVED, None)  # so no check inherits it
    HANDED_SNAPSHOT = os.environ.pop(SNAPSHOT, None)
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
    commands.add_parser("install", help="not implemented yet").add_argument("rest", nargs=argparse.REMAINDER)
    commands.add_parser("prepare", help="fetch the House Rules layer and build its environment in the cache")
    status = commands.add_parser("status", help="print the effective configuration and cache state")
    status.add_argument("--session", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            raise Failure("install is not implemented yet", "write the configuration and hooks by hand")
        return {"run": command_run, "prepare": command_prepare, "status": command_status}[args.command](args, argv)
    except Failure as exc:
        print(f"repository checks: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
