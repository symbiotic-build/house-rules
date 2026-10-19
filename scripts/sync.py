#!/usr/bin/env python3
"""Update the checkout and report House Rules installation drift; see INSTALL-AGENTS.md §6.

With --install-hooks it also writes the session-context hook into each Claude Code and Codex
hook file (INSTALL-AGENTS.md §3 step 10). It writes no other file.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time


MARKERS = re.compile(r"<!-- (house-rules|forge|groundwork):(begin|end) -->")
_SPEC = importlib.util.spec_from_file_location("session_context", Path(__file__).with_name("session_context.py"))
session_context = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(session_context)
# Native hook file and session_context.py product name for each product with a session-start hook.
# Kimi Code runs SessionStart hooks but does not pass their output to the model (INSTALL-AGENTS.md §1).
HOOK_FILES = {"CLAUDE_CONFIG_DIR": ("settings.json", "claude"), "CODEX_HOME": ("hooks.json", "codex")}


def status(path, *, follow_symlinks=True):
    """Treat only a missing path as absent; propagate other filesystem errors."""
    try:
        return path.stat() if follow_symlinks else path.lstat()
    except FileNotFoundError:
        return None


def is_dir(path):
    info = status(path)
    return info is not None and stat.S_ISDIR(info.st_mode)


def is_file(path):
    info = status(path)
    return info is not None and stat.S_ISREG(info.st_mode)


def is_link(path):
    info = status(path, follow_symlinks=False)
    return info is not None and stat.S_ISLNK(info.st_mode)


def present(path):
    return status(path, follow_symlinks=False) is not None


def git(root, *args):
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def update(root):
    """Never update dirty, non-default, ahead or diverged checkouts."""
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        return ["checkout is dirty; not pulled"]
    branch = git(root, "branch", "--show-current")
    head = git(root, "rev-parse", "HEAD")
    remote = git(root, "ls-remote", "--symref", "origin", "HEAD")
    match = re.search(r"^ref: refs/heads/(.+)\s+HEAD$", remote, re.M)
    if not match:
        raise ValueError("origin does not advertise a default branch")
    default = match.group(1)
    if branch != default:
        return [f"checkout is on {branch or 'detached HEAD'}, not {default}; not pulled"]
    git(root, "fetch", "origin", default)
    revision = git(root, "rev-parse", "FETCH_HEAD")
    ahead, behind = map(int, git(root, "rev-list", "--left-right", "--count",
                                f"HEAD...{revision}").split())
    if (git(root, "branch", "--show-current") != branch or
            git(root, "rev-parse", "HEAD") != head or
            git(root, "status", "--porcelain", "--untracked-files=all")):
        return ["checkout changed during update; not pulled"]
    if ahead:
        return [f"checkout is {'diverged' if behind else 'ahead'}; not pulled"]
    if behind:
        print(git(root, "merge", "--ff-only", "--no-overwrite-ignore", revision))
    return []


def template(root):
    """Derive the adapter from its single authoritative Markdown template."""
    text = (root / "INSTALL-AGENTS.md").read_text(encoding="utf-8")
    match = re.search(r"```markdown\n(.*?)\n\s*```", text, re.S)
    if not match:
        raise ValueError("managed block template is missing")
    block = "\n".join(line.removeprefix("   ") for line in match.group(1).splitlines())
    if not block.startswith("<!-- house-rules:begin -->") or not block.endswith(
            "<!-- house-rules:end -->"):
        raise ValueError("invalid managed block template")
    return block.replace("<HOUSE_RULES_ROOT>", str(root))


def homes(root, home):
    """Select present default homes and explicitly configured extra homes."""
    defaults = {
        "CLAUDE_CONFIG_DIR": Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude")),
        "CODEX_HOME": Path(os.environ.get("CODEX_HOME", home / ".codex")),
        "KIMI_CODE_HOME": Path(os.environ.get("KIMI_CODE_HOME", home / ".kimi-code")),
    }
    selected = []
    for key, path in defaults.items():
        if key in os.environ and (not path.is_absolute() or not is_dir(path)):
            raise ValueError(f"{key} must be an existing absolute directory")
        if present(path) and not is_dir(path):
            raise ValueError(f"{key} default home is not a directory: {path}")
        if is_dir(path):
            selected.append((key, path.absolute()))
    config = root / "custom/sync.env"
    if present(config):
        for number, line in enumerate(config.read_text(encoding="utf-8").splitlines(), 1):
            tokens = shlex.split(line, comments=True)
            if not tokens:
                continue
            if len(tokens) != 1 or "=" not in tokens[0]:
                raise ValueError(f"{config}:{number}: expected KEY=path")
            key, value = tokens[0].split("=", 1)
            if key not in defaults or not value:
                raise ValueError(f"{config}:{number}: unknown key or empty home")
            path = Path(value).expanduser()
            if not path.is_absolute() or not is_dir(path):
                raise ValueError(f"{config}:{number}: home must be an existing absolute directory")
            selected.append((key, path))
    for key, path in selected:
        if not path.is_absolute():
            raise ValueError(f"{key} must be an absolute directory")
        if key == "CODEX_HOME" and not any(is_file(path / name)
                                           for name in ("config.toml", "auth.json")):
            raise ValueError(f"not a Codex home (no config.toml or auth.json): {path}")
    return list(dict.fromkeys(selected))


def children(path):
    """Enumerate with errors intact on every supported Python version."""
    with os.scandir(path) as entries:
        return sorted(Path(entry.path) for entry in entries)


def receipts(root):
    """(path, receipt object) for each machine-readable installation receipt."""
    directory = root / "custom/installations"
    result = []
    for path in children(directory) if present(directory) else []:
        if path.suffix != ".json" or path.name.startswith("sync-"):
            continue
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            raise ValueError(f"receipt must be an object: {path}")
        result.append((path, receipt))
    return result


def replaced_hooks(root):
    """Scripts of earlier hand-made House Rules hooks, which receipts list under replaced_hooks."""
    scripts = set()
    for path, receipt in receipts(root):
        listed = receipt.get("replaced_hooks", [])
        if not isinstance(listed, list) or any(
                not isinstance(value, str) or not Path(value).is_absolute() for value in listed):
            raise ValueError(f"invalid receipt replaced_hooks: {path}")
        scripts.update(listed)
    return scripts


def ownership_roots(root):
    """Read manual installation receipts solely to recognize prior-root links."""
    roots = {str(root)}
    for path, receipt in receipts(root):
        previous = receipt.get("previous_roots", [])
        if not isinstance(previous, list):
            raise ValueError(f"invalid receipt roots: {path}")
        recorded = [receipt.get("source_root", str(root)), *previous]
        if any(not isinstance(value, str) or not Path(value).is_absolute() for value in recorded):
            raise ValueError(f"invalid receipt roots: {path}")
        roots.update(recorded)
    return roots


def owned_link(path, roots):
    # Compare the target as written; never follow an unrelated alias into ownership.
    return is_link(path) and os.readlink(path) in {
        str(Path(root) / "skills" / path.name) for root in roots}


def instruction_file(key, home):
    if key == "CLAUDE_CONFIG_DIR":
        return home / "CLAUDE.md"
    override = home / "AGENTS.override.md"
    return override if key == "CODEX_HOME" and present(override) else home / "AGENTS.md"


def protected_paths(selected):
    return [(path / "skills/.system").resolve()
            for key, path in selected if key == "CODEX_HOME"]


def check_protected(path, selected):
    resolved = path.resolve()
    if any(resolved == system or system in resolved.parents
           for system in protected_paths(selected)):
        raise ValueError(f"path aliases protected Codex .system content: {path}")


def skill_folders(selected, home):
    """Check each configured scan location, including aliases with different roles."""
    folders = set()
    for key, product_home in selected:
        if key == "CLAUDE_CONFIG_DIR":
            folders.add((product_home / "skills", True))
        else:
            folders.update(((home / ".agents/skills", True), (product_home / "skills", False)))
    return sorted(folders)


def verify(root, home, findings, selected, hook_root=None):
    """Collect results in caller-owned lists so a later error cannot discard them."""
    block = template(root)
    selected.extend(homes(root, home))
    roots = ownership_roots(root) | {str(hook_root or root)}
    skills = {path.name: path for path in children(root / "skills")
              if is_dir(path) and is_file(path / "SKILL.md")}
    if ".system" in skills:
        raise ValueError(".system is reserved; cannot install a House Rules skill there")
    instructions = {instruction_file(key, product_home) for key, product_home in selected}
    for path in (home / "AGENTS.md", home / "CLAUDE.md"):
        if path not in instructions and present(path) and MARKERS.search(
                path.read_bytes().decode("utf-8")):
            findings.append(f"duplicate home-level managed block: {path}")
    for path in sorted(instructions):
        if is_link(path) and not is_file(path):
            findings.append(f"instruction symlink has no regular target: {path}")
            continue
        check_protected(path, selected)
        text = path.read_bytes().decode("utf-8") if present(path) else ""
        markers = list(MARKERS.finditer(text))
        if not markers:
            findings.append(f"missing block: {path}")
        elif (len(markers) != 2 or markers[0].group(2) != "begin" or
              markers[1].group(2) != "end" or markers[0].group(1) != markers[1].group(1)):
            findings.append(f"malformed or multiple managed blocks: {path}")
        elif text[markers[0].start():markers[1].end()] != block:
            findings.append(f"stale block: {path}")
    for folder, install in skill_folders(selected, home):
        check_protected(folder, selected)
        entries = {path.name: path for path in children(folder)} if present(folder) else {}
        for name in sorted(set(skills) | set(entries)):
            if name == ".system":
                continue
            path = folder / name
            exists = name in entries
            ours = exists and owned_link(path, roots)
            if install and name in skills:
                if exists and not ours:
                    findings.append(f"same-name skill conflict: {path}")
                elif not is_link(path) or os.readlink(path) != str(skills[name]):
                    findings.append(f"missing or stale skill link: {path}")
            elif ours:
                reason = "shadowing skill" if name in skills else "removed skill"
                findings.append(f"{reason}: {path}")
            elif exists and not install and name in skills:
                findings.append(f"same-name shadowing conflict: {path}")

    for path in always_load(root, findings):
        if not is_file(path):
            findings.append(f"missing rule file: {path}")
    for key, product_home in selected:
        if key in HOOK_FILES:
            check_hook(hook_root or root, roots, product_home / HOOK_FILES[key][0], HOOK_FILES[key][1], findings,
                       replaced_hooks(root))
    _, packed, too_long = session_context.parts(root)
    if len(packed) > session_context.SLOTS:
        findings.append(f"session context needs {len(packed)} parts; the hook registers {session_context.SLOTS}")
    for name, heading in too_long:
        findings.append(f"session context section too long for one part: {name}, heading \"{heading}\"")


def read_hooks(path, data=None):
    """The hook file's object and its SessionStart list; a file that is not a JSON object is an error.

    data: the file's bytes when the caller already read them, so it can detect later changes.
    """
    if data is None and present(path):
        data = path.read_bytes()
    try:
        settings = json.loads(data.decode("utf-8")) if data is not None else {}
    except ValueError as error:
        raise ValueError(f"hook file is not valid JSON: {path}: {error}") from error
    if not isinstance(settings, dict):
        raise ValueError(f"hook file is not a JSON object: {path}")
    hooks = settings.get("hooks", {})
    entries = hooks.get("SessionStart", []) if isinstance(hooks, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"hook file has no SessionStart list: {path}")
    return settings, entries


def check_hook(root, roots, path, product, findings, replaced=frozenset()):
    """Exactly the INSTALL-AGENTS.md §3 SessionStart entry, run by an existing absolute interpreter."""
    _, entries = read_hooks(path)
    scripts = {str(Path(other) / "scripts/session_context.py") for other in roots}
    if any(script_of(tokens) in replaced for entry in entries if isinstance(entry, dict)
           for tokens in handler_commands(entry)):
        findings.append(f"replaced House Rules hook still registered: {path}")
    owned = [(entry, commands) for entry in entries if isinstance(entry, dict)
             for commands in [handler_commands(entry)] if any(script_of(tokens) in scripts for tokens in commands)]
    if not owned:
        findings.append(f"missing session context hook: {path}")
        return
    entry, commands = owned[0]
    python = commands[0][0] if commands[0] else ""
    if len(owned) != 1 or not Path(python).is_absolute() or not is_file(Path(python)) or \
            entry != session_context.hooks(product, python, root):
        findings.append(f"stale session context hook: {path}")


def script_of(tokens, python=None):
    """The script a command runs: <python> [options] <script> ..., env <python> ..., or <script> ...

    A Python interpreter is the installer's own executable or a program whose name starts with
    "py" (python3, python3.14t, py, pypy3). A command that only mentions a path, such as
    `test -f <path>` or `echo <path>`, runs its own program, never that path. Code given with
    -c or a module given with -m, attached or separate, runs no script file.
    """
    if len(tokens) in (4, 5) and tokens[1] == "-I" and Path(tokens[2]).name == "session_context.py" and (
            tokens[3:] == ["codex"] or (tokens[3] == "claude" and tokens[4:5] != [] and tokens[4].isdigit())):
        return tokens[2]  # the exact form session_context.hooks() prints, whatever the interpreter is called
    if tokens and Path(tokens[0]).name == "env":
        tokens = tokens[1:]
    if not tokens:
        return None
    if tokens[0] != python and not Path(tokens[0]).name.startswith("py"):
        return tokens[0]
    arguments = iter(tokens[1:])
    for token in arguments:
        if token.startswith(("-c", "-m")):
            return None
        if token in ("-W", "-X"):
            next(arguments, None)
        elif not token.startswith("-"):
            return token
    return None


def handler_commands(entry):
    """Each handler's command as tokens; a handler without a parsable command gives no tokens."""
    result = []
    for handler in entry.get("hooks") if isinstance(entry.get("hooks"), list) else []:
        command = handler.get("command") if isinstance(handler, dict) else None
        try:
            result.append(shlex.split(command) if isinstance(command, str) else [])
        except ValueError:
            result.append([])
    return result


def install_hooks(root, hook_root, home, python, report):
    """Write the current hook entry into each Claude Code and Codex hook file; report(path, backup) per file.

    Removes House Rules handlers of any recorded root and receipt-listed replaced hooks, keeps every
    other entry and setting, backs up an existing file beside it and replaces the file atomically.
    A file whose only House Rules entry is already the current one is not written. The file is
    read again just before replacement, and a change since the first read is an error; a change
    in the instant between that check and the replacement is not detected, so installation runs
    while no agent session changes its settings (INSTALL-AGENTS.md §3 step 10). Each write is
    reported as it happens, so a later failure cannot hide files already changed.
    """
    roots = ownership_roots(root) | {str(hook_root)}
    ours = {str(Path(other) / "scripts/session_context.py") for other in roots} | replaced_hooks(root)
    for key, product_home in homes(root, home):
        if key not in HOOK_FILES:
            continue
        name, product = HOOK_FILES[key]
        path = product_home / name
        data = path.read_bytes() if present(path) else None
        settings, entries = read_hooks(path, data)
        expected = session_context.hooks(product, python, hook_root)
        kept, owned = [], []
        for entry in entries:
            handlers = entry.get("hooks") if isinstance(entry, dict) else None
            if isinstance(handlers, list):
                remaining = [handler for handler, tokens in zip(handlers, handler_commands(entry))
                             if script_of(tokens, python) not in ours]
                if len(remaining) != len(handlers):
                    owned.append(entry)
                if not remaining:
                    continue
                if len(remaining) != len(handlers):
                    entry = {**entry, "hooks": remaining}
            kept.append(entry)
        if owned == [expected]:
            continue
        settings.setdefault("hooks", {})["SessionStart"] = kept + [expected]
        mode = stat.S_IMODE(os.stat(path).st_mode) if data is not None else 0o600
        backup = backup_copy(path, data, mode) if data is not None else None
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(settings, indent=2) + "\n")
            os.chmod(temporary, mode)
            if (path.read_bytes() if present(path) else None) != data:
                raise ValueError(f"hook file changed during installation; not written: {path}")
            os.replace(temporary, path)
        except BaseException:
            os.unlink(temporary)
            raise
        report(path, backup)


def backup_copy(path, data, mode):
    """A new backup beside the file, never replacing an earlier one, readable no wider than its owner."""
    stamp = time.strftime("%Y%m%dT%H%M%S")
    for number in range(1000):
        backup = path.with_name(f"{path.name}.house-rules-backup-{stamp}" + (f"-{number}" if number else ""))
        try:
            handle = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode & 0o600)
        except FileExistsError:
            continue
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        return backup
    raise ValueError(f"no free backup name beside {path}")


def always_load(root, findings):
    """Rule files the index (INDEX.md "Always load") requires, so the check follows the index."""
    index = root / "INDEX.md"
    if not is_file(index):
        findings.append(f"missing index: {index}")
        return []
    links = session_context.always_load(index.read_text(encoding="utf-8"))
    if not links:
        findings.append(f"index lists no always-load rule files: {index}")
    return [root / link for link in links]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--install-hooks", action="store_true",
                        help="write the session-context hook into each Claude Code and Codex hook file")
    args = parser.parse_args(argv)
    root, started = args.root.resolve(), time.monotonic()
    # Hook entries name the root as given, so a stable link to a moving checkout stays valid.
    hook_root = Path(os.path.abspath(args.root))
    failed = False
    findings = []
    selected = []
    verification_complete = False
    # A failed checkout update must not prevent checking the installed homes.
    def install():
        install_hooks(root, hook_root, Path.home(), sys.executable, lambda path, backup: print(
            f"REGISTERED: session context hook in {path}" + (f" (backup: {backup})" if backup else "")))

    for name, operation in (
            ("update", lambda: findings.extend(update(root))),
            *((("install", install),) if args.install_hooks else ()),
            ("verification", lambda: verify(root, Path.home(), findings, selected, hook_root))):
        try:
            operation()
        except (OSError, ValueError, RecursionError, subprocess.CalledProcessError) as error:
            failed = True
            print(f"ERROR: {error}", file=sys.stderr)
            if isinstance(error, subprocess.CalledProcessError):
                print(error.stderr, file=sys.stderr)
        else:
            if name == "verification":
                verification_complete = True
    for message in findings:
        print(f"REPORT: {message}")
    coverage = ("homes checked" if verification_complete else
                "homes selected; verification incomplete")
    print(f"{len(selected)} {coverage}; {len(findings)} findings; "
          f"{time.monotonic() - started:.3f}s")
    return 2 if failed else 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
