#!/usr/bin/env python3
"""Update the checkout and report House Rules installation drift; see INSTALL-AGENTS.md §6."""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import time


MARKERS = re.compile(r"<!-- (house-rules|forge|groundwork):(begin|end) -->")
SPECIALIST_KEYS = {"SPECIALIST_CODEX_HOME", "SPECIALIST_KIMI_CODE_HOME"}


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
                            capture_output=True, text=True, check=True)
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
            if key not in defaults.keys() | SPECIALIST_KEYS or not value:
                raise ValueError(f"{config}:{number}: unknown key or empty home")
            path = Path(value).expanduser()
            if not path.is_absolute() or not is_dir(path):
                raise ValueError(f"{config}:{number}: home must be an existing absolute directory")
            selected.append((key, path))
    for key, path in selected:
        if not path.is_absolute():
            raise ValueError(f"{key} must be an absolute directory")
        if key in ("CODEX_HOME", "SPECIALIST_CODEX_HOME") and not any(is_file(path / name)
                                           for name in ("config.toml", "auth.json")):
            raise ValueError(f"not a Codex home (no config.toml or auth.json): {path}")
        if key in SPECIALIST_KEYS:
            outside_checkout(path, root)
            if any(other_key not in SPECIALIST_KEYS and path.resolve() == other.resolve()
                   for other_key, other in selected):
                raise ValueError(f"home registered as both specialist and normal: {path}")
    return list(dict.fromkeys(selected))


def children(path):
    """Enumerate with errors intact on every supported Python version."""
    with os.scandir(path) as entries:
        return sorted(Path(entry.path) for entry in entries)


def ownership_roots(root):
    """Read manual installation receipts solely to recognize prior-root links."""
    roots = {str(root)}
    directory = root / "custom/installations"
    paths = children(directory) if present(directory) else []
    for path in paths:
        if path.suffix != ".json" or path.name.startswith("sync-"):
            continue
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            raise ValueError(f"receipt must be an object: {path}")
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
        if key in SPECIALIST_KEYS:
            continue
        if key == "CLAUDE_CONFIG_DIR":
            folders.add((product_home / "skills", True))
        else:
            folders.update(((home / ".agents/skills", True), (product_home / "skills", False)))
    return sorted(folders)


def outside_checkout(path, root, target=None):
    """Specialist configuration must not live in a rules or project checkout."""
    resolved = path.resolve()
    if any(resolved == checkout.resolve() or checkout.resolve() in resolved.parents
           for checkout in (root, target) if checkout is not None):
        raise ValueError(f"specialist home must be outside the checkout: {path}")
    if any(present(parent / ".git") for parent in (resolved, *resolved.parents)):
        raise ValueError(f"specialist home must be outside any project checkout: {path}")


def discover_skills(folder, seen=None, *, canonical=True):
    """Find skill identities or source locations, including links and nested skills."""
    seen = set() if seen is None else seen
    if not canonical:
        # Keep sibling aliases as separate copy locations; stop only ancestor cycles.
        seen = set(seen)
    if not present(folder):
        return set()
    resolved = folder.resolve()
    if resolved in seen:
        return set()  # An already enumerated alias adds no discoverable skill.
    seen.add(resolved)
    if not is_dir(folder):
        raise ValueError(f"skill scan location is not a directory: {folder}")
    if is_file(folder / "SKILL.md"):
        path = folder / "SKILL.md"
        return {path.resolve() if canonical else path}
    found = set()
    for entry in children(folder):
        if is_dir(entry):
            found.update(discover_skills(entry, seen, canonical=canonical))
        elif is_link(entry) and not present(entry.resolve()):
            raise ValueError(f"broken skill link: {entry}")
    return found


def codex_specialist_config(path):
    """Read the native isolation settings' simple TOML spelling on Python 3.9.

    Other native settings remain opaque. Unsupported spellings of isolation
    settings fail visibly; this is not a replacement for the tool's TOML parser.
    """
    section, limit, entries, entry, instructions = "", None, [], None, []
    # Strip TOML comments without consuming backslashes inside quoted paths.
    tokens = re.compile(r'"(?:\\.|[^"\\])*"|\'[^\']*\'|#[^\n]*|[^"\'#]+')
    for line in path.read_text(encoding="utf-8").splitlines():
        text = "".join(m.group() for m in tokens.finditer(line) if not m.group().startswith("#")).strip()
        if not text:
            continue
        if text.startswith("["):
            if text == "[[skills.config]]":
                entry = {}
                entries.append(entry)
                section = "skills.config"
            else:
                # Recognize quoted/spaced isolation headers before ignoring opaque tables.
                header = text.strip("[] ")
                parts = re.findall(r'"(?:\\.|[^"\\])*"|\'[^\']*\'|[A-Za-z0-9_-]+', header)
                first = parts[0] if parts else ""
                if first.startswith('"'):
                    first = json.loads(first)
                elif first.startswith("'"):
                    first = first[1:-1]
                if first == "skills":
                    raise ValueError(f"unsupported skills.config table header: {path}")
                section = text.strip("[] ")
                entry = None
            continue
        if "=" not in text:
            if section == "skills.config":
                raise ValueError(f"unsupported skills.config syntax: {path}")
            continue
        key, value = (part.strip() for part in text.split("=", 1))
        if key.strip("\"'") in ("developer_instructions", "user_instructions", "instructions",
                                 "model_instructions_file", "experimental_instructions_file") and value not in ('""', "''"):
            instructions.append(key)
        if key.strip("\"'") == "project_doc_max_bytes":
            if section or limit is not None or not re.fullmatch(r"[0-9_]+", value):
                raise ValueError(f"unsupported project_doc_max_bytes setting: {path}")
            limit = int(value.replace("_", ""))
        elif section == "skills.config" and entry is not None:
            if key not in ("path", "enabled") or key in entry:
                raise ValueError(f"unsupported skills.config setting: {path}")
            if key == "enabled":
                if value not in ("true", "false"):
                    raise ValueError(f"invalid skills.config enabled value: {path}")
                entry[key] = value == "true"
            else:
                try:
                    name = value[1:-1] if re.fullmatch(r"'[^']*'", value) else json.loads(value)
                except ValueError as error:
                    raise ValueError(f"unsupported skills.config path: {path}") from error
                if not isinstance(name, str) or not Path(name).is_absolute():
                    raise ValueError(f"skills.config path must be absolute: {path}")
                entry[key] = Path(name).resolve()
        elif key.strip("\"'") in ("skills", "skills.config") or key.startswith("skills."):
            raise ValueError(f"unsupported skills.config syntax: {path}")
    if any(set(entry) != {"path", "enabled"} for entry in entries):
        raise ValueError(f"skills.config requires path and enabled: {path}")
    if len({entry["path"] for entry in entries}) != len(entries):
        raise ValueError(f"duplicate skills.config path: {path}")
    return limit, entries, instructions


def codex_snapshot_entries(entries, source_home, product_home):
    """Map disabled source identities to every document location in the copied home."""
    disabled = {entry["path"] for entry in entries if not entry["enabled"]}
    mapped = {entry["path"]: entry for entry in entries}
    source_home = source_home.resolve()
    for name in ("skills", "plugins"):
        for path in sorted(discover_skills(source_home / name, canonical=False)):
            if path.resolve() in disabled:
                copied = (product_home / path.relative_to(source_home)).resolve()
                mapped[copied] = {"path": copied, "enabled": False}
    return list(mapped.values())


def specialist_findings(root, home, key, product_home, findings, workdir=None, source_home=None):
    """Shared filesystem preflight for sync and the specialist launcher."""
    outside_checkout(product_home, root, workdir)
    # Check both Codex files even when an override currently masks AGENTS.md.
    names = ("AGENTS.md", "AGENTS.override.md") if key == "SPECIALIST_CODEX_HOME" else ("AGENTS.md", "SYSTEM.md")
    paths = [product_home / name for name in names]
    if key == "SPECIALIST_KIMI_CODE_HOME":
        paths.append(home / ".agents/AGENTS.md")
    for path in paths:
        if present(path):
            if not is_file(path):
                findings.append(f"specialist instruction source is not a regular file: {path}")
            elif path.read_text(encoding="utf-8").strip():
                findings.append(f"additional global task instructions: {path}")
    folder = product_home / "skills"
    if present(folder):
        for path in children(folder):
            # Codex-managed built-ins stay in place, but must be disabled below.
            if path.name != ".system" or key != "SPECIALIST_CODEX_HOME":
                findings.append(f"installed skill in specialist home: {path}")
    if key != "SPECIALIST_CODEX_HOME":
        for name in ("agents", "plugins"):
            path = product_home / name
            if present(path) and (not is_dir(path) or children(path)):
                findings.append(f"additional specialist instruction or skill sources: {path}")
        return
    config = product_home / "config.toml"
    if not is_file(config):
        findings.append(f"missing specialist config: {config}")
        return
    limit, entries, instructions = codex_specialist_config(config)
    if source_home is not None:
        entries = codex_snapshot_entries(entries, source_home, product_home)
    for setting in instructions:
        findings.append(f"additional global task instructions in {setting}: {config}")
    if limit != 0:
        findings.append(f"specialist project_doc_max_bytes must be 0: {config}")
    disabled = {entry["path"] for entry in entries if not entry["enabled"]}
    for entry in entries:
        if entry["enabled"]:
            findings.append(f"enabled discoverable skill: {entry['path']}")
    folders = [home / ".agents/skills", product_home / "skills", product_home / "plugins", Path("/etc/codex/skills")]
    if workdir is not None:
        folders.extend(parent / ".agents/skills" for parent in (workdir, *workdir.parents))
    for skill in sorted(set().union(*(discover_skills(folder) for folder in folders))):
        if skill not in disabled:
            findings.append(f"missing disable entry for discoverable skill: {skill} ({config})")


def verify(root, home, findings, selected):
    """Collect results in caller-owned lists so a later error cannot discard them."""
    block = template(root)
    selected.extend(homes(root, home))
    roots = ownership_roots(root)
    skills = {path.name: path for path in children(root / "skills")
              if is_dir(path) and is_file(path / "SKILL.md")}
    if ".system" in skills:
        raise ValueError(".system is reserved; cannot install a House Rules skill there")
    normal = [(key, path) for key, path in selected if key not in SPECIALIST_KEYS]
    instructions = {instruction_file(key, product_home) for key, product_home in normal}
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
        if key in SPECIALIST_KEYS:
            specialist_findings(root, home, key, product_home, findings)


def always_load(root, findings):
    """Rule files the index (INDEX.md "Always load") requires, so the check follows the index."""
    index = root / "INDEX.md"
    if not is_file(index):
        findings.append(f"missing index: {index}")
        return []
    section = index.read_text(encoding="utf-8").split("## Always load", 1)
    links = re.findall(r"\]\((rules/[^)]+\.md)\)", section[1].split("\n## ", 1)[0]) if len(section) == 2 else []
    if not links:
        findings.append(f"index lists no always-load rule files: {index}")
    return [root / link for link in links]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    root, started = args.root.resolve(), time.monotonic()
    failed = False
    findings = []
    selected = []
    verification_complete = False
    # A failed checkout update must not prevent checking the installed homes.
    for name, operation in (
            ("update", lambda: findings.extend(update(root))),
            ("verification", lambda: verify(root, Path.home(), findings, selected))):
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
