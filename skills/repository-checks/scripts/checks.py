#!/usr/bin/env python3
"""Run a repository's declared checks before each commit, before each push and in CI.

The contract is docs/design/194-repository-checks.md. This file uses only the
standard library and runs on CPython 3.9 or later.
"""
import argparse
import contextlib
import errno
import hashlib
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
import urllib.parse
from pathlib import Path

RUNNER = "skills/repository-checks/scripts/checks.py"
SPEC_SCRIPTS = "skills/spec-writing/scripts"
CONFIG = "house-rules.json"
CONFIG_VERSION = 2
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
# The URL of the House Rules layer when its entry names none, and the one the installed CI workflow clones.
DEFAULT_URL = "https://github.com/symbiotic-build/house-rules"
# Git's explicit remote-helper form, <transport>::<address>, by Git's own rule: URL-scheme characters, the first
# a letter or digit, then "::" directly.
REMOTE_HELPER = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9+.-]*)?::")
# A House Rules fetch fails on lack of progress, never on elapsed time: below 1 byte/s for 30 s over HTTP.
PROGRESS = ("-c", "http.lowSpeedLimit=1", "-c", "http.lowSpeedTime=30")
# `house-rules exec`, or a handing runner, passes the run's resolved House Rules layer to the runner it starts.
RESOLVED = "HOUSE_RULES_RESOLVED"
# Where a layer's commit came from: its branch fetched now, its branch as last resolved (offline), a commit ref
# (pinned), or the HOUSE_RULES_REVISION test override.
SOURCES = ("fetched", "offline", "pinned", "override")
# The record `house-rules exec` passes may also name an answer younger than its reuse window, or a linked checkout.
EXEC_SOURCES = SOURCES + ("reused", "link")
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


def printable(document):
    """Refuse a document that holds text the runner could not print or pass to a program.

    A surrogate escape of a file name byte encodes; an unpaired surrogate from a JSON escape does not, and would crash
    the text report or a process start. The error names no field and repeats no text.
    """
    try:
        json.dumps(document, ensure_ascii=False).encode(sys.getfilesystemencoding(), "surrogateescape")
    except UnicodeEncodeError:
        raise config_error("the file holds text that cannot be printed or passed to a program") from None


def load_document(data):
    """Parse the file and validate what every runner reads before the handover: `version` and `sources`.

    Returns (the document, its House Rules source layer {"name", "url", "ref"}). Only the runner at the run's
    resolved House Rules revision judges the rest (`effective_checks`).
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
    if type(version) is not int or version != CONFIG_VERSION:
        raise config_error(f"unsupported version {version!r}; this runner reads version {CONFIG_VERSION}")
    printable(document)
    return document, source_layer(document)


def source_layer(document):
    """The House Rules source layer the file names: its one `sources` entry, validated, with its URL filled in."""
    if "sources" not in document:
        raise config_error("the file lacks sources")
    sources = document["sources"]
    if not isinstance(sources, list) or not sources:
        raise config_error("sources must be a nonempty list")
    entry = sources[0]
    fields(entry, "sources[0]", ("name", "ref"), ("url",))
    if entry["name"] != HOUSE_RULES:
        raise config_error(f'sources[0].name must be "{HOUSE_RULES}": the first layer is House Rules')
    if len(sources) > 1:
        raise Failure(f"{HOUSE_RULES}: {CONFIG}: custom source layers are not supported by this runner yet (#217)",
                      f"remove the extra entry from sources in {CONFIG}")
    url = entry.get("url", DEFAULT_URL)
    if not text(url) or "\0" in url:
        raise config_error("sources[0].url must be nonempty text")
    if REMOTE_HELPER.match(url):  # the address after "::" goes to a helper unchecked; the message repeats none of it
        raise Failure(f"the House Rules URL in {CONFIG} uses Git's <transport>:: form, which this runner does not "
                      "accept", "use a plain URL and a Git credential helper")
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:  # the parser's message can repeat the URL, so it is left out
        raise Failure(f"the House Rules URL in {CONFIG} cannot be parsed", "correct it") from None
    # Credentials belong to a Git credential helper, never to a tracked file; an ssh login without a password names
    # the account, which can choose the repository.
    userinfo = parts.netloc.rpartition("@")[0]
    if ":" in userinfo or (userinfo and parts.scheme.lower() in ("http", "https")):
        raise Failure(f"the House Rules URL in {CONFIG} carries credentials", "use a Git credential helper")
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


def check_budgets(budgets):
    """Validate a `budgets` object."""
    error = config_error
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


def budget_override(stage, entry):
    return {"id": f"budgets.{stage}", "layer": "repository", "change": f"seconds: {json.dumps(entry['seconds'])}",
            "reason": entry["reason"]}


def profile_definitions():
    """The profiles that this runner's House Rules tree defines in its ruleset.json, or {} without that file."""
    path = own_tree() / "ruleset.json"
    try:
        ruleset = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise Failure(f"cannot read {path} ({exc})", "delete the House Rules cache and run again")
    profiles = ruleset.get("profiles") if isinstance(ruleset, dict) else None
    return profiles if isinstance(profiles, dict) else {}


def effective_checks(data):
    """Validate the whole file against this runner's built-in definitions and return the effective set.

    The layers apply in order: the House Rules built-ins, then the repository's entries, which replace what the
    built-ins set for the same check.
    """
    document, _ = load_document(data)
    fields(document, "the file", ("version", "sources", "checks"), ("budgets", "profiles"))
    profiles = document.get("profiles", [])
    if not isinstance(profiles, list):
        raise config_error("profiles must be a list")
    defined = profile_definitions() if profiles else {}
    for name in profiles:  # `house-rules init` writes the list; a profile that sets nothing changes nothing
        if not isinstance(name, str) or name not in defined:
            raise config_error(f"profiles lists {name!r}, which this House Rules revision does not define")
        if defined[name]:  # this runner cannot apply what a profile sets yet, and never ignores it
            raise Failure(f"{HOUSE_RULES}: {CONFIG}: profile {name} sets checks or settings, which this runner "
                          "does not support yet (#217)", f"remove {name} from profiles in {CONFIG}")
    budgets = check_budgets(document.get("budgets", {}))
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
    overrides += [budget_override(stage, entry) for stage, entry in budgets.items()]
    return {"checks": checks, "overrides": overrides, "budgets": budgets}


def config_data(root, rev, blobs):
    """The configuration at `rev`, the index when `rev` is empty, or None when no file is at exactly its path."""
    if CONFIG not in blobs:
        return None
    return git(root, "cat-file", "blob", f"{rev}:{CONFIG}").stdout


def staged_data(root):
    """The staged configuration, by the rule `run` uses. A file that the index lists but Git cannot read, such as a
    missing blob or an unmerged entry, is a preparation failure with Git's message, never taken for an absent one."""
    return config_data(root, "", file_paths(git(root, "ls-files", "--stage", "-z", "--", CONFIG).stdout))


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


def revision_folder(revision):
    return cache_root() / "revisions" / revision


def prepared(revision):
    """Whether the cache holds the commit's tree: a fetch renames the folder into place only once it is complete."""
    return revision_folder(revision).is_dir()


def fetch_time_path(tree):
    """revisions/<commit>.fetched: one line, the UTC time of the first fetch that placed the commit's folder."""
    return Path(str(tree) + ".fetched")


def record_fetch_time(tree):
    """Write the commit's fetch time once, create-only; when another process already wrote it, keep that time."""
    try:
        descriptor = os.open(str(fetch_time_path(tree)), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return
    with os.fdopen(descriptor, "w") as handle:
        handle.write(utc() + "\n")


def source_folder(url):
    """The cache folder of one source: sources/<SHA-256 of its URL as written>, holding branches/ and the
    temporary repositories of its fetches."""
    return cache_root() / "sources" / hashlib.sha256(url.encode("utf-8", "surrogateescape")).hexdigest()


def fetch_revision(url, revision):
    """Put one House Rules commit into the cache unless it is there; return None, or Git's error.

    Each fetch uses its own new bare repository, a .partial-* folder in the source's folder, fetches the commit with
    depth 1, extracts it into a temporary revision folder, renames that folder into place and deletes the
    repository. Nothing Git locks is ever used again, so an interrupted fetch, or a repository that could not be
    deleted, leaves only a temporary folder that no run uses.
    """
    if prepared(revision):
        return None
    repository = partial(source_folder(url))
    try:
        return fetch_into(repository, url, revision)
    finally:
        shutil.rmtree(str(repository), ignore_errors=True)


def fetch_into(repository, url, revision):
    """Fetch `revision` into the empty bare `repository` and put its files into the cache; return None or Git's error."""
    git(repository, "init", "--quiet", "--bare", "--template=", ".", foreign=True)  # no template attributes
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
    record_fetch_time(revision_folder(revision))  # before the rename, so a ready tree normally has its time
    place(temporary, revision_folder(revision), lambda path: path.is_dir())  # an existing tree is never replaced
    return None


def ask_branch(url, branch):
    """Return (the branch's commit, None), or (None, Git's error).

    Git ends each record with a line feed and puts a tab between the commit and the reference; only those bytes
    delimit, so a branch name keeps every other character, such as U+2028. Names decode losslessly.
    """
    name = "refs/heads/" + branch
    cache_root().mkdir(parents=True, exist_ok=True)  # Git runs there, outside any clone and its configuration
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
    return source_folder(url) / "branches" / (hashlib.sha256(branch.encode("utf-8", "surrogateescape")).hexdigest()
                                              + ".json")


def branch_record(url, branch):
    """The commit last resolved for `branch` of `url`, as {"url", "branch", "revision", "fetched"}, or None."""
    try:
        record = json.loads(branch_record_path(url, branch).read_text())
    except (OSError, ValueError):
        return None
    if not (isinstance(record, dict) and all(isinstance(record.get(k), str) for k in ("url", "branch", "fetched"))
            and isinstance(record.get("revision"), str) and COMMIT.fullmatch(record["revision"])):
        return None
    return record


def write_branch_record(url, record):
    """Publish `record` for its source and branch through a temporary file, so a reader sees the old or new record.

    Two runs that resolve at the same time may leave either result; the next run asks again.
    """
    path = branch_record_path(url, record["branch"])
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".partial-", dir=str(path.parent))
    with os.fdopen(descriptor, "w") as handle:
        json.dump(record, handle)
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


def handed_resolution(source=None, other_snapshot=False):
    """The House Rules layer this runner was started with, or None.

    `house-rules exec` passes its whole resolution record, and its first layer counts when exec started this runner
    from that layer's tree: the run then checks with exactly the commit exec resolved and logged, and resolves
    nothing again. A handing runner passes one layer that names this runner's own revision.

    With `source`, the source this runner read from the configuration now, a handed layer of another source stops
    the run: the configuration changed between the handing read and this one. With `other_snapshot`, exec's record
    may describe another snapshot, as at pre-push, where exec resolves HEAD and the runner checks each pushed commit:
    a record of another source is then ignored, and the runner resolves that snapshot itself.
    """
    try:
        resolution = json.loads(HANDED or "null")
    except ValueError:
        return None
    from_exec = isinstance(resolution, dict) and resolution.get("version") == 1 and isinstance(
        resolution.get("layers"), list)
    if from_exec:
        resolution = exec_layer(resolution)
    elif not (isinstance(resolution, dict) and resolution.get("revision") == own_revision()
              and resolution.get("source") in SOURCES and isinstance(resolution.get("fetched"), str)
              and all(isinstance(resolution.get(k), str) for k in ("name", "url", "ref", "tree"))):
        return None
    if resolution is None:
        return None
    if source is not None and not same_source(resolution, source):
        if from_exec and other_snapshot:
            return explicit_selection(resolution, source)
        raise Failure("the configuration changed during the run", "run again")
    return resolution


def explicit_selection(resolution, source):
    """For a snapshot whose source differs from the one exec resolved: exec's explicit selection, kept, or None.

    exec removes HOUSE_RULES_REVISION and HOUSE_RULES_LINK before it starts this runner, so only its record can
    carry them. The revision override applies to the House Rules layer whatever its ref; a link applies to its URL.
    Without either, the runner resolves the snapshot's own source itself.
    """
    if resolution["source"] == "override" or (resolution["source"] == "link" and resolution["url"] == source["url"]):
        kept = {k: resolution[k] for k in ("revision", "source", "fetched", "tree")}
        if resolution.get("warning"):
            kept["warning"] = resolution["warning"]
        return dict(kept, name=source["name"], url=source["url"], ref=source["ref"])
    return None


def resolve(source, offline_repair=None, other_snapshot=False):
    """Resolve the House Rules layer `source` for this run: the override, else its commit ref, else its branch
    fetched now, else the commit last resolved for that branch.

    Returns the layer {"name", "url", "ref", "revision", "source", "fetched"}, plus "warning" for a cached branch. Called once per run; the revision it returns is prepared in the cache.
    """
    resolution = handed_resolution(source, other_snapshot)
    if resolution:
        return resolution
    url, ref = source["url"], source["ref"]
    layer = {"name": source["name"], "url": url, "ref": ref}
    try:
        override = override_revision()
        if override or COMMIT.fullmatch(ref):
            revision = override or ref
            error = fetch_revision(url, revision)
            if error:
                repair = ("run again when online, or set HOUSE_RULES_REVISION to a commit that exists there" if override
                          else f"run again when online, or set the ref in {CONFIG} to a commit that exists there")
                raise Failure(f"cannot fetch House Rules {revision} from {url} ({error})", repair)
            return dict(layer, revision=revision, source="override" if override else "pinned", fetched=None)
        fetched = utc()
        revision, error = ask_branch(url, ref)
        if not error:
            error = fetch_revision(url, revision)
        if not error:
            write_branch_record(url, {"url": url, "branch": ref, "revision": revision, "fetched": fetched})
            return dict(layer, revision=revision, source="fetched", fetched=fetched)
        record = branch_record(url, ref)
        if record is None or not prepared(record["revision"]):
            raise Failure(f"cannot fetch House Rules {ref} from {url} ({error})", offline_repair or "run again when online")
        return dict(layer, revision=record["revision"], source="offline", fetched=record["fetched"],
                    warning=f"cannot fetch House Rules {ref} from {url} ({error}); using the {ref} last fetched, "
                            f"{record['revision']}, fetched {record['fetched']}")
    except OSError as exc:
        raise cache_failure(exc)


def extract(source, revision, folder):
    # No personal or system attributes file decides what the archive leaves out, such as with export-ignore.
    environ = dict({k: v for k, v in os.environ.items() if k not in LOCAL_GIT_ENV}, GIT_ATTR_NOSYSTEM="1",
                   **NO_REPLACE)
    archive = subprocess.Popen(["git", "-c", "core.attributesFile=/dev/null", "archive", "--format=tar", revision], cwd=str(source), stdout=subprocess.PIPE,
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
    """When a fetch first placed the commit's folder `tree`, from revisions/<commit>.fetched.

    A tree without that file, such as one placed by an older runner or one outside this cache, gives the folder's
    modification time instead.
    """
    try:
        recorded = fetch_time_path(tree).read_text().strip()
    except OSError:
        recorded = ""
    return recorded if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", recorded) else utc(os.stat(str(tree)).st_mtime)


def exec_layer(record):
    """The House Rules layer of the record `house-rules exec` passed, or None unless exec started this runner from
    that layer's tree. The record's warnings become the layer's warning, so the report shows them."""
    layer = record["layers"][0] if record["layers"] else None
    if not (isinstance(layer, dict) and layer.get("source") in EXEC_SOURCES
            and all(isinstance(layer.get(k), str) for k in ("name", "url", "ref", "revision", "tree"))
            and (layer.get("fetched") is None or isinstance(layer.get("fetched"), str))
            and Path(layer["tree"]).resolve() == own_tree()):
        return None
    resolved = {k: layer[k] for k in ("name", "url", "ref", "revision", "source", "fetched", "tree")}
    if layer.get("ref_kind") in ("branch", "tag", "commit"):
        resolved["ref_kind"] = layer["ref_kind"]
    # exec's warnings start with "warning: ", which the report adds itself.
    warnings = [w[len("warning: "):] if w.startswith("warning: ") else w
                for w in record.get("warnings") or () if isinstance(w, str)]
    return dict(resolved, warning="; ".join(warnings)) if warnings else resolved


def dispatch(tree, argv, resolution, stdin=None):
    """Replace this process by the runner in `tree`, unless this file is that runner.

    The started runner receives `resolution`, so it uses the same revision without resolving again, and `stdin`,
    the input this process already read, as its standard input.
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
    try:
        os.execv(sys.executable, [sys.executable, "-I", str(runner), *argv])
    except OSError as exc:
        raise Failure(f"cannot start the resolved runner {runner} ({exc})", f"run `{runner_command('prepare')}` again")


def resolve_layers(data, offline_repair=None, other_snapshot=False):
    """Resolve the source layers that `data`, the bytes of a configuration, names, for this run.

    Returns the layers in order, House Rules first, each {"name", "url", "ref", "revision", "source", "fetched",
    "tree"}, plus "warning" on a layer resolved offline. Each layer's commit is prepared in the cache at `tree`.
    This runner resolves only the House Rules layer.
    """
    _, source = load_document(data)
    layer = resolve(source, offline_repair, other_snapshot)
    tree = Path(layer["tree"]) if layer.get("tree") else layer_tree(layer["revision"])
    if layer["fetched"] is None and layer["source"] != "link":
        layer["fetched"] = prepared_at(tree)  # a commit ref or an override: when the cache fetched that commit
    return [dict(layer, tree=str(tree))]


def layer_tree(revision):
    return own_tree() if own_revision() == revision else revision_folder(revision)


def resolved_tree(argv, data, stdin=None, offline_repair=None, other_snapshot=False):
    """Resolve the layers `data` names; return (the House Rules tree, the layers), or start the runner there.

    The started runner replaces this process and receives the same House Rules layer.
    """
    layers = resolve_layers(data, offline_repair, other_snapshot)
    tree = Path(layers[0]["tree"])
    dispatch(tree, argv, layers[0], stdin)
    return tree, layers


def cached_resolution(source):
    """What a run would resolve without any network: (layer or None, its prepared tree or None).

    The override when set, else the commit ref, else the commit last resolved for the branch; `status` reports it
    and never fetches.
    """
    resolution = handed_resolution(source)
    if resolution is None:
        layer = {"name": source["name"], "url": source["url"], "ref": source["ref"]}
        override = override_revision()
        if override or COMMIT.fullmatch(source["ref"]):
            resolution = dict(layer, revision=override or source["ref"], source="override" if override else "pinned",
                              fetched=None)
        else:
            record = branch_record(source["url"], source["ref"])
            if record is None:
                return None, None
            resolution = dict(layer, revision=record["revision"], source="offline", fetched=record["fetched"])
    tree = Path(resolution["tree"]) if resolution.get("tree") else layer_tree(resolution["revision"])
    if not (tree / RUNNER).is_file():
        return resolution, None
    if resolution["fetched"] is None and resolution["source"] != "link":
        resolution["fetched"] = prepared_at(tree)
    return resolution, tree


def label(layer):
    """How a report names where a layer's commit came from, its URL and when the cache fetched it."""
    if layer["source"] == "link":
        return f"link of {layer['url']}"  # exec's warning names the checkout
    # exec names the ref's kind, a branch or a release tag; this runner's own resolver follows branches only.
    named = f"{layer.get('ref_kind', 'branch')} {layer['ref']}"
    what = {"fetched": named, "reused": named, "offline": named, "pinned": "commit",
            "override": "HOUSE_RULES_REVISION"}[layer["source"]]
    when = f"cached {layer['fetched']}" if layer["fetched"] else "not cached yet"
    return f"{layer['source']} {what} of {layer['url']}, {when}"


def same_source(layer, source):
    """Whether a snapshot's House Rules source is the one the run resolved."""
    return (layer["name"], layer["url"], layer["ref"]) == (source["name"], source["url"], source["ref"])


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
    folder = cache_root() / "environments" / digest
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

def command_run(args, argv):
    run = {"layers": [], "kinds": [], "warnings": [], "snapshots": []}
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
        print(render(report, run["kinds"]))
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
                # Read only the version and sources before handing over: the resolved runner judges the rest.
                _, source = load_document(target["data"])
                if house_rules is None:
                    house_rules, layers = resolved_tree(argv, target["data"], stdin, offline, other_snapshot=pushing)
                    layer = layers[0]
                    run["layers"] = [{k: layer[k] for k in ("name", "url", "ref", "revision", "source", "fetched")}]
                    run["kinds"] = [layer.get("ref_kind")]  # for the text header only; the report keeps six fields
                    run["warnings"] += [layer["warning"]] if layer.get("warning") else []
                if not same_source(layer, source):
                    # The shared resolver of #217 replaces this with a handover per snapshot.
                    raise Failure("the pushed commits declare different House Rules sources", "push them separately")
                config = effective_checks(target["data"])
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


def snapshot_target(root, ref, head, from_index, remote_commit):
    snapshot, tree, parent = build_snapshot(root, head, from_index)
    blobs = tree_files(root, snapshot)
    return {"ref": ref, "snapshot": snapshot, "tree": tree, "parent": parent, "blobs": blobs,
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
    env = check_environment(args.stage, base, snapshot)
    for check, reason, inputs in plan:
        result = {"id": check["id"], "layer": check["layer"], "status": "skipped", "seconds": None,
                  "command": None, "version": None, "output": "", "fix": None,
                  "rerun": runner_command(*rerun, "--only", check["id"]), "skip_reason": reason}
        if reason is None:
            command, version_arguments = expand(check["run"], values, inputs)
            begin = time.monotonic()
            status, output, version = start_check(command, version_arguments, root, env)
            # A failing check that House Rules does not enforce yet warns and leaves its snapshot passing.
            status = status or ("pass" if output[0] == 0 else "fail" if check["enforced"] else "warn")
            result.update(status=status, seconds=round(time.monotonic() - begin, 3), command=command,
                          version=version, output=output[1], fix=check["fix"] if status != "pass" else None)
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


def render(report, kinds=()):
    """The text report; `kinds` names each layer's ref kind where exec gave one, for its header."""
    kinds = list(kinds) + [None] * len(report["layers"])
    named = "".join(f", House Rules {layer['revision']} ({label(dict(layer, ref_kind=kind) if kind else layer)})"
                    for layer, kind in zip(report["layers"], kinds))
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
                     + named)
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
        raise Failure(f"no {CONFIG} in the index", unstaged_repair(root, f"run `{CHECKS_INSTALL}`"))
    tree, (resolution,) = resolved_tree(argv, data)
    config = effective_checks(data)
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
    config = effective_checks(data)
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
            return f"repository checks: not installed; {unstaged_repair(root, f'run: {CHECKS_INSTALL}')}"
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
        problem = environment_problem(effective_checks(data), tree)
        problems += [problem] if problem else []
    where = f"House Rules {resolution['revision'][:7]}, {label(resolution)}" if resolution else ""
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
SHELL_LINE = re.compile(r"#!\s*(?:/usr/bin/env\s+)?(?:\S*/)?(?:sh|bash|dash|ksh|zsh)(?:\s.*)?")
# The shell options a hook's first line may set and still run the block: errexit, nounset, allexport, noglob, verbose
# and xtrace. Any other, such as -n, which only reads the script, or -c, could leave the block inactive.
SUPPORTED_SHELL_LINE = re.compile(r"#!\s*(?:/usr/bin/env\s+)?(?:\S*/)?(?:sh|bash|dash|ksh|zsh)(?:\s+[-+][aefuvx]+)*\s*")
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
        # `rc`, not `status`: zsh reserves `status`, and the installer accepts zsh hooks.
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
    except RuntimeError as exc:  # a looping link, as Python before 3.13 reports it while resolving a path
        raise Failure(f"cannot read {what} ({exc})", INSPECT_REPAIR) from None


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


FILE_KINDS = ((stat.S_ISDIR, "a folder"), (stat.S_ISFIFO, "a named pipe"), (stat.S_ISCHR, "a device"),
              (stat.S_ISBLK, "a device"), (stat.S_ISSOCK, "a socket"))


def install_hook(plan, path, target, shared):
    """Add the hook block to one hook file, or refuse a file the install cannot edit safely.

    `target` is the file `path` resolves to through the file system, and `shared` whether the other hook file
    resolves to it too. Both are judged before anything is read, so a named pipe or a device is never opened.
    """
    stage, label = path.name, plan.show(path)
    if shared:
        plan.add("refused", f"{label}: pre-commit and pre-push are the same file, {target}",
                 detail=["give each hook its own file, then run install again"])
        return
    block = hook_block(stage)
    try:
        mode = os.stat(str(target)).st_mode
    except FileNotFoundError:  # no file, or a link to none: the block goes into a new file at the link's target
        data = ("#!/bin/sh\n" + "".join(block)).encode()
        plan.add("create", label, path, lambda: publish(target, data, 0o755, label))
        return
    if not stat.S_ISREG(mode):
        kind = next((name for test, name in FILE_KINDS if test(mode)), "not a regular file")
        plan.add("refused", f"{label}: {target} is {kind}, not a hook script",
                 detail=[f"replace {shlex.quote(str(target))} with a hook script, then run install again"])
        return
    try:
        data = target.read_bytes()
    except OSError as exc:
        plan.add("refused", f"{label}: cannot read it ({exc.strerror or exc})", detail=[INSPECT_REPAIR])
        return
    if not os.access(str(target), os.X_OK):
        plan.add("refused", f"{label}: not executable, so Git ignores it; making it executable also starts its own code",
                 detail=[f"to run it and add the block: chmod +x {shlex.quote(str(path))}, then run install again"])
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is None or "\0" in text:
        first = data.split(b"\n", 1)[0]
        shown = first[:60].decode("utf-8", "backslashreplace") + ("…" if len(first) > 60 else "")
        plan.add("refused", f"{label}: not a shell script (first line: {shown!r}); call the runner from it by hand")
        return
    lines = text.splitlines(keepends=True)
    first = lines[0].rstrip("\r\n") if lines else ""
    if SHELL_LINE.fullmatch(first) and not SUPPORTED_SHELL_LINE.fullmatch(first):  # a block there would not run
        plan.add("refused", f"{label}: its first line {first!r} starts the shell with options the install does not "
                            "support; call the runner from it by hand")
        return
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
    if any(sign in text for sign in FRAMEWORK_SIGNS):
        plan.add("refused", f"{label}: written by the pre-commit framework; add this entry to its configuration "
                            "(.pre-commit-config.yaml) under repos:", detail=framework_entry(stage))
        return
    if SHELL_LINE.fullmatch(first):
        head = lines[0] if lines[0].endswith("\n") else lines[0] + "\n"
        new = "".join([head] + block + lines[1:]).encode()
        plan.add("update", label, path, lambda: publish(target, new, mode, label, expected=data))
        return
    plan.add("refused", f"{label}: not a shell script (first line: {first!r}); call the runner from it by hand")


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
    mode = os.stat(str(path)).st_mode  # judged before any read, so a named pipe or a device is never opened
    if not stat.S_ISREG(mode):
        kind = next((name for test, name in FILE_KINDS if test(mode)), "not a regular file")
        plan.add("refused", f"{WORKFLOW}: it is {kind}, not a workflow file",
                 detail=[f"replace {shlex.quote(str(path))} with a workflow file, or remove it, then run install again"])
    elif RUNNER_STEP in path.read_text(errors="replace"):
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


def command_install(args, argv):
    root = find_root()
    data, origin = configuration_data(root)
    if data is None:
        raise Failure(f"no {CONFIG} in this repository", "run `house-rules init` first")
    found = shutil.which("house-rules")
    if found is None:
        raise Failure("the house-rules command is not on PATH", f"run `{COMMAND_INSTALL}` first")
    tree = config = None
    if not args.dry_run:
        # The install prepares what the hooks' first run needs; the runner at the resolved revision judges the file.
        # Without a working tree file, exec resolved another configuration than the staged one the install reads, so
        # its record is a bootstrap one: kept when it names the same source, else the install resolves its own.
        tree, _ = resolved_tree(argv, data, other_snapshot=origin == "index")
        config = effective_checks(data)
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


HANDED = None  # the resolution the handing runner passed, read once at start


def main(argv=None):
    global HANDED
    argv = sys.argv[1:] if argv is None else argv
    HANDED = os.environ.pop(RESOLVED, None)  # so no check inherits it
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
                "status": command_status}[args.command](args, argv)
    except Failure as exc:
        print(f"repository checks: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
