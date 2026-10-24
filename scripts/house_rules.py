#!/usr/bin/env python3
"""House Rules command: resolve a repository's source layers and run House Rules scripts at that version.

The contract is docs/design/218-layered-configuration.md. A repository's house-rules.json lists ordered source
layers (House Rules first, then custom rule and setting repositories), each at a branch, which always resolves to
its latest commit, or at a commit, a deliberate pin. This file resolves them into a per-user version cache, builds
the effective configuration with the layer of every value, and logs what it resolved. It keeps no "current
version": the repository's file, else the per-user file's default sources, else House Rules main decides.

The checks runner imports this file as its resolver. It uses only the standard library and runs on CPython 3.9
or later.

  house-rules resolve [--repo PATH] [--rev COMMIT] [--json]
  house-rules path [--repo PATH] [--layer NAME]
  house-rules exec [--repo PATH] [--hook] PATH [ARGUMENT]...
  house-rules link CHECKOUT [--url URL] | unlink CHECKOUT|URL | links
  house-rules cache list | cache prune [--dry-run]
  house-rules init [--dry-run] [--profile NAME]...
  house-rules install [--dry-run] | self-update | version
"""
import argparse
import calendar
import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

DEFAULT_URL = "https://github.com/symbiotic-build/house-rules"
CONFIG = "house-rules.json"
LOCAL_CONFIG = "house-rules.local.json"
OLD_CONFIG = ".agents/checks.json"
VERSION = 2        # the repository configuration version this command knows
FILE_VERSION = 1   # the version of layer files and the global configuration
BASE_FILE = "checks/base.json"
PROFILE_FOLDER = "checks/profiles"
COMMAND = "scripts/house_rules.py"
REUSE_SECONDS = 60          # a branch answer younger than this is reused without asking the remote
PRUNE_UNUSED_SECONDS = 7 * 86_400   # a tree no branch record names is removed after this long unused
RECORD_UNUSED_SECONDS = 30 * 86_400  # a branch record unused this long expires; its branch loses offline fallback
PARTIAL_SECONDS = 86_400             # a temporary fetch folder older than this belongs to no running fetch
RESOLVED = "HOUSE_RULES_RESOLVED"
OVERRIDE = "HOUSE_RULES_REVISION"
LINK = "HOUSE_RULES_LINK"
HOOK_ERROR = "HOUSE RULES HOOK ERROR:"  # the error prefix agent session hooks print, as session_context.py does
COMMIT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# A fetch fails on lack of progress, never on elapsed time: below 1 byte/s for 30 s over HTTP.
PROGRESS = ("-c", "http.lowSpeedLimit=1", "-c", "http.lowSpeedTime=30")
NO_REPLACE = {"GIT_NO_REPLACE_OBJECTS": "1"}
# Variables that bind a Git command to the calling repository; a hook inherits some of them.
LOCAL_GIT_ENV = ("GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_CONFIG", "GIT_CONFIG_COUNT",
                 "GIT_CONFIG_PARAMETERS", "GIT_DIR", "GIT_GRAFT_FILE", "GIT_IMPLICIT_WORK_TREE",
                 "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_OBJECT_DIRECTORY", "GIT_PREFIX",
                 "GIT_REPLACE_REF_BASE", "GIT_SHALLOW_FILE", "GIT_WORK_TREE")
# Profiles `init` writes, from marker files at the repository root; no tool detects profiles at run time.
PROFILE_MARKERS = (("rust", ("Cargo.toml",)), ("typescript", ("package.json", "tsconfig.json")),
                   ("python", ("pyproject.toml",)), ("svelte", ("svelte.config.js",)),
                   ("specs", ("docs/ENTITIES.json",)))
GIT_SETTING = re.compile(r"[A-Za-z][A-Za-z0-9-]*(?:\.[^\n]+)?\.[A-Za-z][A-Za-z0-9-]*")
# Keys the isolated Git environment of the checks runner sets itself, which a repository cannot change.
RESERVED_GIT_SETTINGS = ("core.bare", "core.worktree", "core.repositoryformatversion", "core.attributesfile")
REPOSITORY_FIELDS = ("version", "sources", "profiles", "budgets", "checks", "git_settings")
LAYER_FIELDS = ("version", "checks", "budgets", "context")
GLOBAL_FIELDS = ("version", "sources", "budgets", "checks")
LOCAL_FIELDS = ("budgets",)
BUDGET_FIELDS = ("seconds", "reason")


class Failure(Exception):
    """A configuration or resolution failure: one line naming the cause and its repair, exit status 2."""

    def __init__(self, message, status=2):
        super().__init__(message)
        self.status = status


def utc(seconds=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


def last_line(data):
    lines = data.decode(errors="replace").strip().splitlines()
    return lines[-1] if lines else "no output"


def git(cwd, *args, foreign=False, check=True, deadline=None):
    """Run Git; `foreign` drops variables that bind it to a calling repository, as for the cache's own repositories.

    With a deadline that has a limit, a command still running at it is stopped and DeadlinePassed is raised.
    """
    environ = dict(os.environ)
    if foreign:
        for name in LOCAL_GIT_ENV:
            environ.pop(name, None)
    environ.update(NO_REPLACE)
    left = deadline.left() if deadline is not None else None
    if left is not None and left <= 0:
        raise DeadlinePassed()
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), env=environ, stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=left)
    except subprocess.TimeoutExpired:
        raise DeadlinePassed()
    except OSError as exc:
        raise Failure(f"house-rules: cannot run git in {cwd} ({exc.strerror or exc}); install Git and run again")
    if check and proc.returncode:
        raise Failure(f"house-rules: git {' '.join(args[:2])} failed in {cwd} ({last_line(proc.stderr)})")
    return proc


# Folders and keys

def cache_root():
    if os.environ.get("HOUSE_RULES_CACHE"):
        return Path(os.environ["HOUSE_RULES_CACHE"]).resolve()
    if os.environ.get("XDG_CACHE_HOME"):
        return Path(os.environ["XDG_CACHE_HOME"]).resolve() / "house-rules"
    return Path.home() / ".cache" / "house-rules"


def config_home():
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]).resolve() / "house-rules"
    return Path.home() / ".config" / "house-rules"


def shown_url(url):
    """The URL as messages show it: without the user name and password in its authority."""
    parts = urllib.parse.urlsplit(url)
    if "@" not in parts.netloc:
        return url
    return urllib.parse.urlunsplit(parts._replace(netloc=parts.netloc.rpartition("@")[2]))


def hidden(text, url):
    """`text`, such as Git's error, with the URL's user name and password removed wherever they appear."""
    netloc = urllib.parse.urlsplit(url).netloc
    if "@" not in netloc:
        return text
    userinfo = netloc.rpartition("@")[0]
    secrets = {userinfo, *userinfo.split(":", 1)}
    secrets = {value for secret in secrets for value in (secret, urllib.parse.unquote(secret)) if value}
    text = text.replace(url, "\0")
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret + "@", "").replace(secret, "***")
    return text.replace("\0", shown_url(url))


def escape(segment):
    """One path segment of a source key: characters outside [A-Za-z0-9._-] become %XX of their UTF-8 bytes,
    and a segment made only of dots has each dot escaped, as the checks runner names the same folders."""
    if set(segment) == {"."}:
        return "%2E" * len(segment)
    return "".join(c if re.fullmatch(r"[A-Za-z0-9._-]", c) else "".join(f"%{b:02X}" for b in c.encode())
                   for c in segment)


def source_key(url):
    """The cache folder of a source: transport, host and path, as in https/github.com/owner/repository.

    The transport is https, http, ssh (an scp-like git@host:path too) or file, so an answer read over HTTP never
    stands for an HTTPS source. The host is lower case; user name, password, the default port, a trailing slash and
    a trailing .git are dropped. A file URL or a local path is file/<absolute path>. Characters outside
    [A-Za-z0-9._-] are escaped in each segment.
    """
    scp = re.fullmatch(r"(?:[^@/:]+@)?([^/:]+):(?!//)(.+)", url)
    if scp and "://" not in url and not os.path.exists(url):
        scheme, host, path = "ssh", scp.group(1).lower(), scp.group(2)
    else:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme in ("", "file") or not parts.hostname:
            scheme, host = "file", None
            path = os.path.abspath(urllib.parse.unquote(parts.path) if parts.scheme == "file" else url)
        else:
            scheme = parts.scheme.lower()
            default = {"https": 443, "http": 80, "ssh": 22}.get(scheme)
            host = parts.hostname.lower() + (f":{parts.port}" if parts.port and parts.port != default else "")
            path = parts.path
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    segments = [segment for segment in (scheme, host, *path.split("/")) if segment]  # empty segments are dropped
    return "/".join(escape(segment) for segment in segments)


def source_folder(url):
    return cache_root() / "sources" / source_key(url)


def tree_folder(url, commit):
    """A commit's files; a commit identifies its content, so every source shares one folder per commit."""
    return cache_root() / "revisions" / commit


def prepared(tree):
    """A tree counts only once revisions/<commit>.fetched exists, as the checks runner decides."""
    return Path(tree).is_dir() and Path(str(tree) + ".fetched").is_file()


def partial(folder):
    folder.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=".partial-", dir=str(folder)))


class Deadline:
    """Hook mode's limit on lock waits, ls-remote and fetches: 2 s before the agent product's 10 s hook timeout.

    Outside hook mode there is no deadline; Git's own progress limit (PROGRESS) is the only one.
    """

    def __init__(self, seconds=None):
        self.seconds = seconds
        self.end = None if seconds is None else time.monotonic() + seconds

    def left(self):
        return None if self.end is None else max(0.0, self.end - time.monotonic())

    def passed(self):
        return self.end is not None and time.monotonic() >= self.end


HOOK_SECONDS = 8   # the hook timeout, 10 s, minus 2 s to print what happened
NO_DEADLINE = Deadline()


class DeadlinePassed(Exception):
    pass


def take_lock(descriptor, mode, deadline):
    """flock with the deadline: a wait that would pass it raises DeadlinePassed."""
    if deadline.end is None:
        fcntl.flock(descriptor, mode)
        return
    while True:
        try:
            fcntl.flock(descriptor, mode | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if deadline.passed():
                raise DeadlinePassed()
            time.sleep(0.05)


@contextlib.contextmanager
def source_lock(url, deadline=NO_DEADLINE):
    """Hold one source's lock: one process at a time asks for a branch, fetches, writes the branch record or prunes
    the source's temporary folders.

    The lock is advisory (flock), so the system releases it when its process ends, however it ends.
    """
    folder = source_folder(url)
    folder.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(folder / "lock"), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        take_lock(descriptor, fcntl.LOCK_EX, deadline)
        yield
    finally:
        os.close(descriptor)


# Reading and checking configuration files

def load_json(data, where):
    try:
        value = json.loads(data)
    except UnicodeDecodeError as exc:
        raise Failure(f"house-rules: {where}: not UTF-8 ({exc.reason})")
    except ValueError as exc:
        raise Failure(f"house-rules: {where}: invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}")
    if not isinstance(value, dict):
        raise Failure(f"house-rules: {where}: the file must hold one JSON object")
    return value


def known_fields(value, allowed, where):
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise Failure(f"house-rules: {where}: unknown field {unknown[0]}; allowed: {', '.join(allowed)}")


def check_version(value, where, version=FILE_VERSION):
    if value.get("version") != version:
        if isinstance(value.get("version"), int) and value["version"] > version:
            raise Failure(f"house-rules: {where} has version {value['version']}; this house-rules command knows "
                          f"version {version}; run house-rules self-update")
        raise Failure(f"house-rules: {where}: version must be {version}")


def check_sources(sources, where):
    """Validate a sources list and return it with defaults filled in: url for house-rules, ref main."""
    if not isinstance(sources, list) or not sources:
        raise Failure(f"house-rules: {where}: sources must be a non-empty list of layer entries")
    result, names = [], set()
    for index, entry in enumerate(sources):
        at = f"{where}: sources[{index}]"
        if not isinstance(entry, dict):
            raise Failure(f"house-rules: {at}: a layer entry is an object with name, url and ref")
        known_fields(entry, ("name", "url", "ref"), at)
        name = entry.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise Failure(f"house-rules: {at}: name must be lower kebab case, such as team-rules")
        if index == 0 and name != "house-rules":
            raise Failure(f"house-rules: {where}: sources[0] must be house-rules; House Rules is always the first layer")
        if index and name == "house-rules":
            raise Failure(f"house-rules: {at}: only the first layer may be named house-rules")
        if name in names:
            raise Failure(f"house-rules: {at}: the name {name} is used twice")
        names.add(name)
        url = entry.get("url", DEFAULT_URL if name == "house-rules" else None)
        if not isinstance(url, str) or not url:
            raise Failure(f"house-rules: {at}: layer {name} needs a url")
        ref = entry.get("ref", "main")
        if not isinstance(ref, str) or not ref:
            raise Failure(f"house-rules: {at}: ref must be a branch name or a full commit identity")
        if not COMMIT.fullmatch(ref.lower()) and git(".", "check-ref-format", "--branch", ref,
                                                    foreign=True, check=False).returncode:
            raise Failure(f"house-rules: {at}: {ref!r} is not a branch name Git accepts")
        result.append({"name": name, "url": url, "ref": ref.lower() if COMMIT.fullmatch(ref.lower()) else ref})
    return result


def check_map(value, field, where):
    if not isinstance(value, dict) or not all(isinstance(entry, dict) for entry in value.values()):
        raise Failure(f"house-rules: {where}: {field} must map each key to an object")
    return value


def check_budgets(budgets, where):
    check_map(budgets, "budgets", where)
    for stage, entry in budgets.items():
        known_fields(entry, BUDGET_FIELDS, f"{where}: budgets.{stage}")
        seconds = entry.get("seconds")
        if "seconds" in entry and (isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0):
            raise Failure(f"house-rules: {where}: budgets.{stage}.seconds must be a positive number")
    return budgets


def repository_config(data, where=CONFIG):
    """Parse a repository configuration; return it with sources defaulted to None and the other fields filled in."""
    value = load_json(data, where)
    check_version(value, where, VERSION)
    known_fields(value, REPOSITORY_FIELDS, where)
    if "sources" not in value:
        raise Failure(f"house-rules: {where}: sources is required; list at least "
                      '{"name": "house-rules", "ref": "main"}')
    settings = value.get("git_settings", {})
    if not isinstance(settings, dict) or not all(isinstance(k, str) and GIT_SETTING.fullmatch(k) and isinstance(v, str)
                                                 for k, v in settings.items()):
        raise Failure(f"house-rules: {where}: git_settings must map Git setting names (section.key or "
                      "section.subsection.key) to strings")
    for key in settings:
        if key.lower() in RESERVED_GIT_SETTINGS or key.lower().startswith("extensions."):
            raise Failure(f"house-rules: {where}: git_settings.{key}: the isolated Git environment sets this itself")
    profiles = value.get("profiles", [])
    if not isinstance(profiles, list) or not all(isinstance(p, str) and NAME.fullmatch(p) for p in profiles) \
            or len(set(profiles)) != len(profiles):
        raise Failure(f"house-rules: {where}: profiles must be a list of distinct lower kebab case names")
    checks = check_map(value.get("checks", {}), "checks", where)
    for identity, entry in checks.items():
        if "enforced" in entry:
            raise Failure(f"house-rules: {where}: checks.{identity}.enforced: only a layer file decides whether a "
                          "check refuses or warns")
    return {"sources": check_sources(value["sources"], where), "profiles": profiles,
            "budgets": check_budgets(value.get("budgets", {}), where), "checks": checks, "git_settings": settings}


def layer_file(data, where):
    value = load_json(data, where)
    if "sources" in value:
        raise Failure(f"house-rules: {where}: only house-rules.json lists sources")
    check_version(value, where)
    known_fields(value, LAYER_FIELDS, where)
    context = value.get("context", [])
    if not isinstance(context, list) or not all(isinstance(p, str) and p.endswith(".md") and not p.startswith("/")
                                                and ".." not in Path(p).parts for p in context):
        raise Failure(f"house-rules: {where}: context must list Markdown files inside the layer")
    return {"checks": check_map(value.get("checks", {}), "checks", where),
            "budgets": check_budgets(value.get("budgets", {}), where), "context": context}


def global_path():
    return config_home() / CONFIG


def global_config(warnings, need_sources=False):
    """The global configuration, or None. A problem in it only warns, except when its sources are needed."""
    path = global_path()
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        data, error = None, Failure(f"house-rules: cannot read {path} ({exc.strerror or exc})")
    try:
        if data is None:
            raise error
        value = load_json(data, str(path))
        check_version(value, str(path))
        known_fields(value, GLOBAL_FIELDS, str(path))
        return {"sources": check_sources(value["sources"], str(path)) if "sources" in value else None,
                "budgets": check_budgets(value.get("budgets", {}), str(path)),
                "checks": check_map(value.get("checks", {}), "checks", str(path))}
    except Failure as failure:
        if need_sources:
            raise
        warnings.append(f"warning: {str(failure)[len('house-rules: '):]}; ignoring the global configuration")
        return None


def local_config(repository, warnings):
    """The repository's untracked local configuration: budgets only.

    A tracked file is ignored with a warning. Any field other than budgets is a configuration error: it
    refuses, and never makes a failing check pass.
    """
    path = Path(repository) / LOCAL_CONFIG
    if not path.is_file():
        return None
    if not git(repository, "ls-files", "--error-unmatch", "--", LOCAL_CONFIG, check=False).returncode:
        warnings.append(f"warning: {LOCAL_CONFIG} is tracked by Git; it holds machine budgets only and must stay "
                        "untracked; ignoring it")
        return None
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise Failure(f"house-rules: cannot read {path} ({exc.strerror or exc})")
    value = load_json(data, LOCAL_CONFIG)
    extra = sorted(set(value) - set(LOCAL_FIELDS))
    if extra:
        raise Failure(f"house-rules: {LOCAL_CONFIG}: {extra[0]} is not allowed; the local file holds budgets only")
    return {"budgets": check_budgets(value.get("budgets", {}), LOCAL_CONFIG)}


# Finding the repository configuration

def find_repository(path=None):
    proc = git(path or ".", "rev-parse", "--show-toplevel", check=False)
    if proc.returncode:
        return None
    return os.fsdecode(proc.stdout).rstrip("\n")


def read_configuration(repository, rev=None):
    """Return (configuration bytes or None, origin) from the working tree, or from commit `rev`."""
    if rev is None:
        path = Path(repository) / CONFIG
        if path.is_file():
            return path.read_bytes(), {"origin": "working tree", "commit": None}
        old = (Path(repository) / OLD_CONFIG).is_file()
        return None, {"origin": "working tree", "commit": None, "old": old}
    commit = git(repository, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}", check=False)
    if commit.returncode:
        raise Failure(f"house-rules: {rev} is no commit in {repository}")
    commit = commit.stdout.decode().strip()
    shown = git(repository, "show", f"{commit}:{CONFIG}", check=False)
    if shown.returncode:
        old = not git(repository, "cat-file", "-e", f"{commit}:{OLD_CONFIG}", check=False).returncode
        return None, {"origin": "commit", "commit": commit, "old": old}
    return shown.stdout, {"origin": "commit", "commit": commit}


# Resolving one layer

def ask_branch(url, branch, deadline=NO_DEADLINE):
    """Return (the branch's latest commit, None), or (None, Git's error)."""
    reference = f"refs/heads/{branch}"
    proc = git(cache_root(), *PROGRESS, "ls-remote", url, reference, foreign=True, check=False, deadline=deadline)
    if proc.returncode:
        return None, last_line(proc.stderr)
    heads = [line.split("\t") for line in proc.stdout.decode(errors="replace").splitlines()]
    commit = next((head[0] for head in heads if head[1:] == [reference]), None)
    if commit is None:
        return None, "missing"
    if not COMMIT.fullmatch(commit):
        return None, f"ls-remote answered {commit!r}"
    return commit, None


def reachable(url, deadline=NO_DEADLINE):
    """Git's error when the remote cannot be reached at all, else None."""
    proc = git(cache_root(), *PROGRESS, "ls-remote", "--heads", url, "refs/heads/main", foreign=True, check=False,
               deadline=deadline)
    return last_line(proc.stderr) if proc.returncode else None


def branch_record_path(url, branch):
    return source_folder(url) / "branches" / f"{branch}.json"


def branch_record(url, branch):
    """The last answer for one branch, as {"url", "branch", "revision", "fetched"}, or None.

    The checks runner writes the same record, so both share one answer. `url` is stored without credentials.
    """
    try:
        record = json.loads(branch_record_path(url, branch).read_text())
        seconds = calendar.timegm(time.strptime(record["fetched"], "%Y-%m-%dT%H:%M:%SZ"))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not (isinstance(record, dict) and record.get("url") == shown_url(url) and record.get("branch") == branch
            and isinstance(record.get("revision"), str) and COMMIT.fullmatch(record["revision"])):
        return None
    return dict(record, seconds=seconds)


def write_branch_record(record):
    path = branch_record_path(record["url"], record["branch"])  # the key never holds credentials
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".branch-", dir=str(path.parent))
    with os.fdopen(descriptor, "w") as handle:
        json.dump(record, handle)
    os.replace(temporary, str(path))


def extract(repository, commit, folder):
    environ = dict({k: v for k, v in os.environ.items() if k not in LOCAL_GIT_ENV}, **NO_REPLACE)
    archive = subprocess.Popen(["git", "archive", "--format=tar", commit], cwd=str(repository),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, env=environ)
    try:
        tar = subprocess.run(["tar", "-xf", "-", "-C", str(folder)], stdin=archive.stdout, capture_output=True)
    except OSError as exc:
        archive.kill()
        archive.communicate()
        raise Failure(f"house-rules: cannot start tar ({exc.strerror or exc}); install tar and run again")
    archive.stdout.close()
    error = archive.stderr.read()
    archive.stderr.close()
    if archive.wait() or tar.returncode:
        raise Failure(f"house-rules: cannot extract {commit} ({last_line(error + tar.stderr)}); run again")


def fetch_commit(url, commit, deadline=NO_DEADLINE):
    """Put one commit's files into the cache unless they are there; return None, or Git's error.

    Each fetch uses its own new bare repository in the source's folder, fetches the commit with depth 1, extracts
    it into a temporary folder there, renames that folder to revisions/<commit>/ and deletes the repository, so an
    interrupted fetch leaves only an unused temporary folder in the source's folder. The first fetch's time is
    written once to revisions/<commit>.fetched, just before the rename. The caller holds the source's lock.
    """
    final = tree_folder(url, commit)
    if prepared(final):
        return None
    repository = partial(source_folder(url))
    try:
        git(repository, "init", "--quiet", "--bare", "--template=", ".", foreign=True)
        proc = git(repository, *PROGRESS, "fetch", "--quiet", "--depth=1", "--no-tags", url,
                   f"{commit}:refs/pins/{commit}", foreign=True, check=False, deadline=deadline)
        if proc.returncode:
            return last_line(proc.stderr)
        temporary = partial(source_folder(url))
        extract(repository, commit, temporary)
        final.parent.mkdir(parents=True, exist_ok=True)
        stamp = Path(str(final) + ".fetched")
        if not stamp.exists():
            stamp.write_text(utc() + "\n")
        for folder, _, names in os.walk(str(temporary)):
            for name in names:
                path = os.path.join(folder, name)
                if not os.path.islink(path):
                    os.chmod(path, os.stat(path).st_mode & ~0o222)
        try:
            os.rename(str(temporary), str(final))
        except OSError:
            if not final.is_dir():
                raise
            shutil.rmtree(str(temporary))  # another process placed the same commit first
        return None
    finally:
        shutil.rmtree(str(repository), ignore_errors=True)


def placed_at(tree):
    """When the cache first received a commit's files: revisions/<commit>.fetched, else the folder's time."""
    try:
        return Path(str(tree) + ".fetched").read_text().strip()
    except OSError:
        return utc(os.stat(str(tree)).st_mtime)


def mark_used(tree):
    marker = Path(str(tree) + ".used")
    try:
        marker.touch()
        os.utime(str(marker), None)
    except OSError:
        pass  # a read-only cache still resolves; prune then treats the tree as unused


def hold_tree(tree):
    """Take a shared lock on revisions/<commit>.used for this process's lifetime, so prune leaves the tree alone.

    Returns the descriptor, which the caller keeps open while it, or a script it starts, uses the tree. A linked
    checkout has no marker and returns None.
    """
    tree = Path(tree)
    if tree.parent != cache_root() / "revisions":
        return None
    descriptor = os.open(str(tree) + ".used", os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(descriptor, fcntl.LOCK_SH)
    if not tree.is_dir():  # pruned between resolution and the lock
        os.close(descriptor)
        raise Failure(f"house-rules: {tree} was removed while this run started; run again")
    return descriptor


def touch_record(url, branch):
    with contextlib.suppress(OSError):
        os.utime(str(branch_record_path(url, branch)), None)


def checkout_state(path):
    head = git(path, "rev-parse", "HEAD", foreign=True, check=False)
    if head.returncode:
        return None
    dirty = git(path, "status", "--porcelain", "--untracked-files=normal", foreign=True, check=False)
    return {"path": str(path), "head": head.stdout.decode().strip(), "dirty": bool(dirty.stdout.strip())}


def linked_layer(entry, path, how):
    state = checkout_state(path) if Path(path).is_dir() else None
    if state is None:
        raise Failure(f"house-rules: link {source_key(entry['url'])}: {path} is not a Git checkout; "
                      f"run house-rules unlink {path}" if how == "links.json"
                      else f"house-rules: {LINK}={path} is not a Git checkout; unset it or name a checkout")
    changes = " with uncommitted changes" if state["dirty"] else ""
    warning = (f"warning: LINKED {entry['name']} -> {path} at {state['head']}{changes}; "
               "this run does not use the fetched source")
    layer = dict(entry, ref_kind="link", revision=state["head"], source="link", fetched=None, tree=str(path),
                 link=state)
    return layer, warning


def resolve_layer(entry, links, warnings, deadline=NO_DEADLINE):
    """Resolve one layer entry to {name, url, ref, ref_kind, revision, source, fetched, tree, link}.

    For the house-rules layer, the one-run variables HOUSE_RULES_LINK and HOUSE_RULES_REVISION win over links.json.
    """
    url, ref, name = entry["url"], entry["ref"], entry["name"]
    shown = shown_url(url)
    override = os.environ.get(OVERRIDE) if name == "house-rules" else None
    if name == "house-rules" and os.environ.get(LINK):
        layer, warning = linked_layer(entry, os.path.abspath(os.path.expanduser(os.environ[LINK])), LINK)
        warnings.append(warning)
        return layer
    link = links.get(source_key(url)) if override is None else None
    if link:
        layer, warning = linked_layer(entry, link, "links.json")
        warnings.append(warning)
        return layer
    if override is not None:
        if not COMMIT.fullmatch(override.lower()):
            raise Failure(f"house-rules: {OVERRIDE}={override!r} is not a full commit identity; set a full commit "
                          "or unset it", status=1)
        commit, source = override.lower(), "override"
        warnings.append(f"warning: TEST OVERRIDE {OVERRIDE}={commit}; this run does not use house-rules {ref}")
    elif COMMIT.fullmatch(ref):
        commit, source = ref, "pinned"
    else:
        commit = None
    try:
        if commit is not None:
            try:
                with source_lock(url, deadline):
                    error = fetch_commit(url, commit, deadline)
            except DeadlinePassed:
                error = f"the remote did not answer within {HOOK_SECONDS} s"
            if error:
                if prepared(tree_folder(url, commit)):
                    error = None
                elif error.startswith("the remote did not answer") or reachable(url, deadline):
                    raise Failure(f"house-rules: cannot reach {shown} ({hidden(error, url)}) and {name} {commit} is "
                                  "not cached; run again when online")
                else:
                    raise Failure(f"house-rules: {name}: commit {commit} not found at {shown} ({hidden(error, url)}); "
                                  "check the ref")
            tree = tree_folder(url, commit)
            mark_used(tree)
            return dict(entry, ref_kind="commit" if COMMIT.fullmatch(ref) else "branch", revision=commit, source=source,
                        fetched=placed_at(tree), tree=str(tree), link=None)
        record, source, error = branch_record(url, ref), None, None
        try:
            with source_lock(url, deadline):
                record = branch_record(url, ref)
                now = time.time()
                if record and 0 <= now - record["seconds"] < REUSE_SECONDS and \
                        prepared(tree_folder(url, record["revision"])):
                    commit, source = record["revision"], "reused"
                else:
                    commit, error = ask_branch(url, ref, deadline)
                    if error == "missing":
                        raise Failure(f"house-rules: {name}: no branch {ref} at {shown}; check the ref in {CONFIG}")
                    if not error:
                        error = fetch_commit(url, commit, deadline)
                    if not error:
                        # Published only now that the commit's tree is complete.
                        write_branch_record({"url": shown, "branch": ref, "revision": commit, "fetched": utc(now)})
                        source = "fetched"
        except DeadlinePassed:
            commit, error = None, f"the remote did not answer within {HOOK_SECONDS} s"
        if commit is None or source not in ("reused", "fetched"):
            if record is None or not prepared(tree_folder(url, record["revision"])):
                raise Failure(f"house-rules: cannot reach {shown} ({hidden(error, url)}) and no earlier fetch of "
                              f"{name} {ref} is cached; run again when online")
            commit, source = record["revision"], "offline"
            tree = tree_folder(url, commit)
            if error.startswith("the remote did not answer"):
                warnings.append(f"warning: {error}; using {name} {ref} last fetched {placed_at(tree)}, {commit}")
            else:
                warnings.append(f"warning: cannot reach {shown} ({hidden(error, url)}); using {name} {ref} last "
                                f"fetched {placed_at(tree)}, {commit}")
        touch_record(url, ref)
        tree = tree_folder(url, commit)
        mark_used(tree)
        return dict(entry, ref_kind="branch", revision=commit, source=source, fetched=placed_at(tree), tree=str(tree),
                    link=None)
    except OSError as exc:
        raise Failure(f"house-rules: cannot write the cache at {cache_root()} ({exc.strerror or exc}); make it "
                      "writable, or set HOUSE_RULES_CACHE to a writable folder")


# Links

def links_path():
    return config_home() / "links.json"


def read_links():
    try:
        value = json.loads(links_path().read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise Failure(f"house-rules: cannot read {links_path()} ({exc}); repair or delete it")
    return {link["key"]: link["path"] for link in value.get("links", [])}


def write_links(links):
    path = links_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": 1, "links": [{"key": key, "path": links[key]} for key in sorted(links)]}
    descriptor, temporary = tempfile.mkstemp(prefix=".links-", dir=str(path.parent))
    with os.fdopen(descriptor, "w") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.replace(temporary, str(path))


# Resolution

def default_sources(warnings):
    configured = global_config(warnings, need_sources=True)
    if configured and configured["sources"]:
        return configured["sources"], "global"
    return [{"name": "house-rules", "url": DEFAULT_URL, "ref": "main"}], "default"


def resolve(repository=None, rev=None, data=None, origin=None, deadline=NO_DEADLINE):
    """Resolve the layers for `repository` (or for no repository) and return the resolution record.

    The configuration is `data` when the caller read it (the checks runner reads it from its snapshot, with its
    own `origin`), else the file at commit `rev`, else the working tree's file. The record's `context` lists each
    custom layer's context files in layer order, read from the resolved trees.
    """
    if os.environ.get(LINK) and os.environ.get(OVERRIDE):
        raise Failure(f"house-rules: set {LINK} or {OVERRIDE}, not both", status=1)
    warnings, config = [], None
    if repository is not None and data is None:
        data, origin = read_configuration(repository, rev)
        if data is None and origin.pop("old", False):
            raise Failure(f"house-rules: {OLD_CONFIG} is replaced by {CONFIG} at the repository root; rename it")
    if data is not None:
        config = repository_config(data)
    if config is not None:
        sources = config["sources"]
    else:
        sources, kind = default_sources(warnings)
        origin = {"origin": kind, "commit": None}
    links = read_links()
    layers = [resolve_layer(entry, links, warnings, deadline) for entry in sources]
    record = {"version": 1, "repository": repository, "configuration": origin,
              "profiles": config["profiles"] if config else [], "layers": layers, "context": [],
              "warnings": warnings}
    record["context"] = [{"layer": label, "path": str(Path(path).relative_to(layer_tree(record, label.split("/")[0])))}
                         for label, path in effective(record)["context"]]
    if config is None:
        point_default(layers[0])
    return record


def point_default(layer):
    """Move the cache's `default` link to the House Rules tree of a resolution of the global default sources."""
    link = cache_root() / "default"
    if layer["source"] == "link" or (link.is_symlink() and os.readlink(str(link)) == layer["tree"]):
        return
    temporary = cache_root() / f".default-{os.getpid()}"
    try:
        cache_root().mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
        os.symlink(layer["tree"], str(temporary))
        os.replace(str(temporary), str(link))
    except OSError:
        with contextlib.suppress(OSError):
            temporary.unlink()


def handed():
    """The resolution a starting tool passed in HOUSE_RULES_RESOLVED, or None."""
    try:
        record = json.loads(os.environ.get(RESOLVED) or "null")
    except ValueError:
        return None
    if isinstance(record, dict) and record.get("version") == 1 and isinstance(record.get("layers"), list):
        return record
    return None


def layer_tree(record, name="house-rules"):
    for layer in record["layers"]:
        if layer["name"] == name:
            return Path(layer["tree"])
    raise Failure(f"house-rules: no layer named {name}; the layers are "
                  f"{', '.join(layer['name'] for layer in record['layers'])}", status=1)


def describe_configuration(record):
    origin = record["configuration"]
    where = f"repository {record['repository']}, " if record["repository"] else "no repository, "
    if origin["origin"] in ("global", "default"):
        return f"house-rules: {where}configuration none ({'global default' if origin['origin'] == 'global' else 'default'} sources)"
    at = {"working tree": "working tree", "index": "index", "commit": f"commit {origin.get('commit')}",
          "base": f"base {origin.get('commit')}"}[origin["origin"]]
    return f"house-rules: {where}configuration {CONFIG} ({at})"


def describe_layer(layer, width):
    """One layer's line: name, URL without credentials, ref, commit, source and first fetch."""
    name, url = layer["name"].ljust(width), shown_url(layer["url"])
    if layer["source"] == "link":
        changes = " with uncommitted changes" if layer["link"]["dirty"] else ""
        return f"house-rules: layer {name} {url} link {layer['tree']} at {layer['revision']}{changes}"
    when = f"fetched {layer['fetched']}"
    if layer["source"] == "pinned":
        return f"house-rules: layer {name} {url} ref {layer['ref']} (pinned, {when})"
    if layer["source"] == "override":
        return f"house-rules: layer {name} {url} ref {layer['ref']} -> {layer['revision']} (override {OVERRIDE}, {when})"
    detail = when if layer["source"] == "fetched" else f"{layer['source']}, {when}"
    return f"house-rules: layer {name} {url} ref {layer['ref']} -> {layer['revision']} ({detail})"


def describe(record):
    """The resolution record's text form: warnings, the configuration line, one line per layer, the profiles."""
    width = max(len(layer["name"]) for layer in record["layers"])
    lines = list(record["warnings"]) + [describe_configuration(record)]
    lines += [describe_layer(layer, width) for layer in record["layers"]]
    if record["profiles"]:
        lines.append(f"house-rules: profiles {', '.join(record['profiles'])}")
    return lines


# The effective configuration

def merge_entry(state, settings, section, key, entry, label, need_reason, earlier_defined):
    """Apply one entry field by field; record each changed value with its layer, and require a reason for it."""
    current = state[section].get(key)
    if current is None:
        state[section][key] = {field: (value, label) for field, value in entry.items()}
        if earlier_defined:
            settings.append({"key": f"{section}.{key}", "value": entry, "layer": label, "replaces": None,
                             "reason": entry.get("reason")})
        return
    changed = [field for field, value in entry.items() if field != "reason"
               and (field not in current or current[field][0] != value)]
    if changed and need_reason and not isinstance(entry.get("reason"), str):
        earlier = current[changed[0]][1] if changed[0] in current else current[next(iter(current))][1]
        raise Failure(f"house-rules: {label} {section}.{key}.{changed[0]}: changes {earlier}'s value; add a reason")
    for field in changed:
        replaces = current[field][1] if field in current else None
        settings.append({"key": f"{section}.{key}.{field}", "value": entry[field], "layer": label,
                         "replaces": replaces, "reason": entry.get("reason")})
    for field, value in entry.items():
        if field == "reason" and not changed:
            continue
        current[field] = (value, label)


def read_layer_file(layer, relative):
    path = Path(layer["tree"]) / relative
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise Failure(f"house-rules: {layer['name']} {relative}: cannot read ({exc.strerror or exc})")
    return layer_file(data, f"{layer['name']} {relative}")


def effective(record, config=None, repository=None, hooks=False):
    """Build the effective configuration: each layer's base then its profiles, the repository's settings, and in
    hooks the global and local configuration. Every value keeps the label of the step that set it.

    Returns {"checks": {id: {field: value}}, "budgets": {...}, "context": [(label, path)], "layers_of": {...},
    "settings": [...], "personal": [ids], "warnings": [...]}.
    """
    state = {"checks": {}, "budgets": {}}
    settings, context, warnings = [], [], []
    profiles = record["profiles"]
    defined = {profile: False for profile in profiles}
    first = True
    for layer in record["layers"]:
        steps = [(layer["name"], BASE_FILE)]
        steps += [(f"{layer['name']}/{profile}", f"{PROFILE_FOLDER}/{profile}.json") for profile in profiles]
        for label, relative in steps:
            content = read_layer_file(layer, relative)
            if content is None:
                continue
            if "/" in label:
                defined[label.split("/", 1)[1]] = True
            for section in ("checks", "budgets"):
                for key, entry in content[section].items():
                    merge_entry(state, settings, section, key, entry, label, not first, not first)
            for name in content["context"]:
                path = Path(layer["tree"]) / name
                if not path.is_file():
                    raise Failure(f"house-rules: {label}: context file {name} does not exist in the layer")
                context.append((label, str(path)))
        first = False  # House Rules' own files define the defaults; every later file's change is listed
    missing = [profile for profile, found in defined.items() if not found]
    if missing:
        raise Failure(f"house-rules: profile {missing[0]} is defined by no layer "
                      f"({', '.join(layer['name'] for layer in record['layers'])})")
    if config is not None:
        for section in ("checks", "budgets"):
            for key, entry in config[section].items():
                merge_entry(state, settings, section, key, entry, "repository", True, True)
    personal = []
    if hooks:
        configured = global_config(warnings)
        if configured:
            for stage, entry in configured["budgets"].items():
                merge_entry(state, settings, "budgets", stage, entry, "global", False, True)
            for identity, entry in configured["checks"].items():
                if identity in state["checks"]:
                    warnings.append(f"warning: global configuration check {identity} names a check of this "
                                    "repository; personal checks need new names; ignored")
                    continue
                if "enforced" in entry or not isinstance(entry.get("reason"), str):
                    warnings.append(f"warning: global configuration check {identity} needs a reason and cannot set "
                                    "enforced; ignored")
                    continue
                merge_entry(state, settings, "checks", identity, dict(entry, enforced=False), "global", False, True)
                personal.append(identity)
        if repository is not None:
            local = local_config(repository, warnings)
            if local:
                for stage, entry in local["budgets"].items():
                    merge_entry(state, settings, "budgets", stage, entry, "local", False, True)
    flat = {section: {key: {field: value for field, (value, _) in entry.items()} for key, entry in state[section].items()}
            for section in state}
    layers_of = {key: {field: label for field, (_, label) in entry.items()} for key, entry in state["checks"].items()}
    return {"checks": flat["checks"], "budgets": flat["budgets"], "context": context, "layers_of": layers_of,
            "settings": settings, "personal": personal, "warnings": warnings}


def describe_settings(settings):
    lines = []
    for item in settings:
        value = json.dumps(item["value"], separators=(", ", ": "))
        reason = f" (reason: {item['reason']})" if item["reason"] else ""
        replaces = f"; replaces {item['replaces']}" if item["replaces"] else ""
        lines.append(f"  {item['key']} = {value}  from {item['layer']}{replaces}{reason}")
    return lines


# Commands

def cmd_resolve(args):
    record = resolve(args.repository, args.rev)
    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print("\n".join(describe(record)))
        stale = installed_differs(record)
        if stale:
            print(stale)
    return 0


def installed_differs(record):
    """A warning when this installed command differs from the command in the global default's House Rules tree."""
    own = Path(__file__).resolve()
    default = cache_root() / "default" / COMMAND
    if "revisions" in own.parts or not default.is_file():
        return None
    try:
        if own.read_bytes()[own.read_bytes().index(b"\n"):] != default.read_bytes()[default.read_bytes().index(b"\n"):]:
            return "warning: this house-rules command differs from the one in House Rules main; run house-rules self-update"
    except (OSError, ValueError):
        return None
    return None


def command_repository(args):
    if args.repo:
        repository = find_repository(args.repo)
        if repository is None:
            raise Failure(f"house-rules: {args.repo} is not inside a Git working tree", status=1)
        return repository
    return find_repository()


def cmd_path(args):
    record = resolve(command_repository(args))
    print("\n".join(describe(record)), file=sys.stderr)  # standard output carries only the path
    print(layer_tree(record, args.layer))
    return 0


def cmd_exec(args):
    stdin = None
    folder = args.repo
    if args.hook:
        stdin = sys.stdin.buffer.read()
        try:
            folder = folder or json.loads(stdin or b"{}").get("cwd")
        except (ValueError, AttributeError):
            folder = folder or None
    repository = find_repository(folder) if folder else find_repository()
    try:
        # A hook must finish before the agent product's timeout kills it without a trace.
        record = resolve(repository, deadline=Deadline(HOOK_SECONDS) if args.hook else NO_DEADLINE)
        tree = layer_tree(record)
    except Failure as failure:
        if not args.hook:
            raise
        # A failed resolution never stops an agent session: name it, then the global default's rules, labelled.
        tree, record = Path(os.path.realpath(str(cache_root() / "default"))), None
        known = (tree / args.path).is_file()
        print(f"{HOOK_ERROR} {failure}. " + (
            f"The House Rules below are the global default's ({tree}), not this repository's resolved rules, and "
            "this repository's custom layers are missing." if known else "No House Rules tree is cached, so this "
            "context holds no House Rules; fix the cause above and start a new session."))
        sys.stdout.flush()
        if not known:
            return 0
    # Shared locks on every tree this run uses, held until the script ends, so `cache prune` leaves them alone.
    held = [hold_tree(layer["tree"]) for layer in record["layers"]] if record else [hold_tree(tree)]
    script = tree / args.path
    if not script.is_file():
        raise Failure(f"house-rules: house-rules {record['layers'][0]['revision']} has no {args.path}; check the path "
                      "or the house-rules ref")
    environ = dict(os.environ)
    if record is not None:
        environ[RESOLVED] = json.dumps(record)
    environ.pop(LINK, None)
    environ.pop(OVERRIDE, None)
    command = [sys.executable, "-I", str(script), *args.arguments] if script.suffix == ".py" else [str(script), *args.arguments]
    if stdin is not None:  # a hook's input, already read for its cwd, goes on to the script
        proc = subprocess.run(command, input=stdin, stdin=None, env=environ, cwd=repository or None)
    else:  # any other script reads this command's own standard input, as a Git hook's references
        proc = subprocess.run(command, stdin=sys.stdin, env=environ, cwd=repository or None)
    for descriptor in held:
        if descriptor is not None:
            os.close(descriptor)
    return proc.returncode


def cmd_link(args):
    checkout = os.path.abspath(os.path.expanduser(args.checkout))
    if checkout_state(checkout) is None:
        raise Failure(f"house-rules: {checkout} is not a Git checkout", status=1)
    url = args.url
    if url is None:
        proc = git(checkout, "config", "--get", "remote.origin.url", foreign=True, check=False)
        if proc.returncode:
            raise Failure(f"house-rules: {checkout} has no remote.origin.url; name the source with --url URL", status=1)
        url = proc.stdout.decode().strip()
    key = source_key(url)
    links = read_links()
    links[key] = checkout
    write_links(links)
    print(f"house-rules: linked {key} -> {checkout}; every run on this machine that lists this source uses the "
          "checkout and warns")
    return 0


def cmd_unlink(args):
    links = read_links()
    target = os.path.abspath(os.path.expanduser(args.target))
    keys = [key for key, path in links.items() if path == target]
    if not keys:
        with contextlib.suppress(Failure):
            keys = [key for key in links if key == source_key(args.target)]
    if not keys:
        raise Failure(f"house-rules: no link names {args.target}; house-rules links lists them", status=1)
    for key in keys:
        del links[key]
        print(f"house-rules: unlinked {key}")
    write_links(links)
    return 0


def cmd_links(args):
    for key, path in sorted(read_links().items()):
        print(f"{key} -> {path}")
    return 0


def folder_size(path):
    total = 0
    for folder, _, names in os.walk(str(path)):
        for name in names:
            with contextlib.suppress(OSError):
                total += os.lstat(os.path.join(folder, name)).st_size
    return total


def last_used(tree):
    try:
        return os.stat(str(tree) + ".used").st_mtime
    except OSError:
        try:
            return os.stat(str(tree)).st_mtime
        except OSError:
            return 0


def cache_sources():
    """The folder of every source the cache has resolved: sources/<transport>/<host>/<path>/, which holds its lock."""
    root = cache_root() / "sources"
    if not root.is_dir():
        return []
    return sorted(path.parent for path in root.glob("**/lock") if path.is_file())


def branch_records(source):
    """(record path, branch, revision, fetched) of every branch record of one source."""
    records = []
    for path in sorted((source / "branches").glob("*.json")):
        with contextlib.suppress(OSError, ValueError, KeyError):
            value = json.loads(path.read_text())
            records.append((path, value["branch"], value["revision"], value["fetched"]))
    return records


def trees():
    folder = cache_root() / "revisions"
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.iterdir() if path.is_dir() and COMMIT.fullmatch(path.name))


def cmd_cache_list(args):
    for source in cache_sources():
        print(source.relative_to(cache_root() / "sources"))
        for _, branch, commit, fetched in branch_records(source):
            print(f"  branch {branch} -> {commit} (fetched {fetched})")
    for tree in trees():
        print(f"tree {tree.name} {folder_size(tree) / 1_048_576:.1f} MiB, first fetched {placed_at(tree)}, "
              f"last used {utc(last_used(tree))}")
    return 0


def prune_plan(now=None):
    """What `cache prune` removes, as (path, reason, source folder or None), in removal order.

    Per docs/design/218-layered-configuration.md §Cache pruning: abandoned branch records, then unnamed old
    trees, then old temporary fetch folders, then an earlier draft's main.json and main.lock. Environments belong
    to the checks runner, which records no use of them, so prune leaves them. Whether a tree is in use is decided
    at removal, under its lock, not here.
    """
    now = time.time() if now is None else now
    root = cache_root()
    plan = []
    default = None
    with contextlib.suppress(OSError):
        default = os.path.realpath(str(root / "default"))
    named = set()
    for source in cache_sources():
        for path, _, commit, _ in branch_records(source):
            if now - path.stat().st_mtime > RECORD_UNUSED_SECONDS:
                plan.append((path, f"branch record unused since {utc(path.stat().st_mtime)}", source))
            else:
                named.add(commit)
    for tree in trees():
        unused = now - last_used(tree)
        if tree.name not in named and os.path.realpath(str(tree)) != default and unused > PRUNE_UNUSED_SECONDS:
            plan.append((tree, f"unused since {utc(last_used(tree))}", None))
    for source in cache_sources():
        for path in sorted(source.glob(".partial-*")):
            if now - path.stat().st_mtime > PARTIAL_SECONDS:
                plan.append((path, "unfinished fetch", source))
    for name in ("main.json", "main.lock"):
        if (root / name).is_file():
            plan.append((root / name, "record of an earlier checks runner draft", None))
    return plan


def remove_tree(path):
    for folder, _, _ in os.walk(str(path)):
        with contextlib.suppress(OSError):
            os.chmod(folder, 0o755)
    shutil.rmtree(str(path))


def cmd_cache_prune(args):
    removed = 0
    for path, reason, source in prune_plan():
        if args.dry_run:
            print(f"would remove {path} ({reason})")
            removed += 1
            continue
        if path.parent == cache_root() / "revisions":
            # In use when another process holds its shared lock: keep it. Hold the lock through the removal.
            descriptor = os.open(str(path) + ".used", os.O_RDWR | os.O_CREAT, 0o644)
            try:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    print(f"keep {path} (in use)")
                    continue
                remove_tree(path)
                for suffix in (".fetched", ".used"):
                    with contextlib.suppress(FileNotFoundError):
                        Path(str(path) + suffix).unlink()
            finally:
                os.close(descriptor)
        elif source is not None:
            descriptor = os.open(str(source / "lock"), os.O_RDWR | os.O_CREAT, 0o644)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)  # no fetch of this source is running
                if path.is_dir():
                    remove_tree(path)
                elif path.exists():
                    path.unlink()
            finally:
                os.close(descriptor)
        else:
            path.unlink()
        print(f"remove {path} ({reason})")
        removed += 1
    if not removed:
        print("house-rules: nothing to prune")
    return 0


def detect_profiles(repository):
    return [name for name, markers in PROFILE_MARKERS if all((Path(repository) / m).is_file() for m in markers)]


def cmd_init(args):
    repository = command_repository(args) or None
    if repository is None:
        raise Failure("house-rules: not inside a Git working tree; run init in a repository", status=1)
    path = Path(repository) / CONFIG
    if path.exists():
        raise Failure(f"house-rules: {path} exists; edit it instead", status=1)
    profiles = args.profile if args.profile else detect_profiles(repository)
    text = json.dumps({"version": VERSION, "sources": [{"name": "house-rules", "ref": "main"}], "profiles": profiles,
                       "checks": {}}, indent=2) + "\n"
    if args.dry_run:
        print(f"would create {path}:")
        print(text, end="")
        return 0
    path.write_text(text)
    print(f"house-rules: created {path} with profiles {', '.join(profiles) or 'none'}; review it and commit it")
    return 0


def install_target():
    return Path.home() / ".local" / "bin" / "house-rules"


def installed_text(source):
    """This file's text with its first line naming the interpreter that runs the install, isolated (-I)."""
    text = Path(source).read_text()
    return f"#!{sys.executable} -I\n" + text.split("\n", 1)[1]


def write_command(source, dry_run):
    target = install_target()
    print(f"{'would write' if dry_run else 'write'} {target}")
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".house-rules-{os.getpid()}")
    temporary.write_text(installed_text(source))
    temporary.chmod(0o755)
    os.replace(str(temporary), str(target))


def cmd_install(args):
    write_command(__file__, args.dry_run)
    path = global_path()
    if not path.exists():
        print(f"{'would create' if args.dry_run else 'create'} {path}")
        if not args.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"version": FILE_VERSION}) + "\n")
    custom, own = config_home() / "custom", Path(__file__).resolve().parents[1] / "custom"
    if own.is_dir() and not custom.exists() and not custom.is_symlink():
        print(f"{'would link' if args.dry_run else 'link'} {custom} -> {own}")
        if not args.dry_run:
            custom.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(str(own), str(custom))
    # Prepare the global default before anything points through the cache's `default` link.
    print(f"{'would resolve' if args.dry_run else 'resolve'} the global default sources")
    if not args.dry_run:
        record = resolve(None)
        print("\n".join(describe(record)))
    return 0


def cmd_self_update(args):
    if args.source:
        source, origin = Path(args.source).resolve() / COMMAND, f"the checkout {Path(args.source).resolve()}"
    else:
        record = resolve(None)
        source, origin = layer_tree(record) / COMMAND, f"House Rules {record['layers'][0]['revision']}"
    if not source.is_file():
        raise Failure(f"house-rules: {origin} has no {COMMAND}")
    target = install_target()
    if target.is_file() and installed_text(source) == target.read_text():
        raise Failure("house-rules: the global default's House Rules has the same command; run python3 "
                      "<checkout>/scripts/house_rules.py install from a newer checkout" if not args.source else
                      f"house-rules: {origin} has the command already installed")
    write_command(source, False)
    print(f"house-rules: updated from {origin}")
    return 0


def cmd_version(args):
    own = Path(__file__).resolve()
    print(f"house-rules command at {own}, repository configuration version {VERSION}")
    return 0


def parser():
    top = argparse.ArgumentParser(prog="house-rules", description="Resolve House Rules source layers per repository.")
    commands = top.add_subparsers(dest="command", required=True)
    p = commands.add_parser("resolve")
    p.add_argument("--repo")
    p.add_argument("--rev")
    p.add_argument("--json", action="store_true")
    p.set_defaults(run=cmd_resolve)
    p = commands.add_parser("path")
    p.add_argument("--repo")
    p.add_argument("--layer", default="house-rules")
    p.set_defaults(run=cmd_path)
    p = commands.add_parser("exec")
    p.add_argument("--repo")
    p.add_argument("--hook", action="store_true")
    p.add_argument("path")
    p.add_argument("arguments", nargs=argparse.REMAINDER)
    p.set_defaults(run=cmd_exec)
    p = commands.add_parser("link")
    p.add_argument("checkout")
    p.add_argument("--url")
    p.set_defaults(run=cmd_link)
    p = commands.add_parser("unlink")
    p.add_argument("target")
    p.set_defaults(run=cmd_unlink)
    commands.add_parser("links").set_defaults(run=cmd_links)
    cache = commands.add_parser("cache").add_subparsers(dest="cache_command", required=True)
    cache.add_parser("list").set_defaults(run=cmd_cache_list)
    p = cache.add_parser("prune")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(run=cmd_cache_prune)
    p = commands.add_parser("init")
    p.add_argument("--repo")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--profile", action="append")
    p.set_defaults(run=cmd_init)
    p = commands.add_parser("install")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(run=cmd_install)
    p = commands.add_parser("self-update")
    p.add_argument("--from", dest="source", metavar="CHECKOUT")
    p.set_defaults(run=cmd_self_update)
    commands.add_parser("version").set_defaults(run=cmd_version)
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "resolve":
        args.repository = command_repository(args)
    try:
        return args.run(args)
    except Failure as failure:
        print(str(failure), file=sys.stderr)
        return failure.status


if __name__ == "__main__":
    sys.exit(main())
