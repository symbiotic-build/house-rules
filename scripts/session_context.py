#!/usr/bin/env python3
"""Put House Rules into an agent session's context at start, resume, clear and compaction.

INSTALL-AGENTS.md §3 registers this script as a session-start hook. It prints INDEX.md, the rule
files its "Always load" section lists, the operator-writing skill and this computer's
custom/INDEX.md, read live from the House Rules tree that holds this script. Registered through
`house-rules exec --hook`, it runs from the tree the House Rules command resolved for the session's
repository; part 1 then starts with that resolution, and each custom source layer's context files follow
the House Rules files. This computer's custom/ folder is the tree's own when it has one (a checkout),
and otherwise the one in the House Rules configuration folder (~/.config/house-rules/custom).

  session_context.py claude <n>      part <n> for Claude Code; one hook per part
  session_context.py codex           every part, as one Codex additionalContext value
  session_context.py kimi prompt     every part, on the first prompt of each Kimi session id
  session_context.py approved        open approved work items, when custom/approved-work.conf names
                                     GitHub owners or owner/repo pairs (one per line); nothing otherwise
  session_context.py hooks <product> [<root>]
                                     the hook entry INSTALL-AGENTS.md §3 registers, running this
                                     interpreter and the script under <root> (default: this checkout)
  session_context.py hooks <product> --command <house-rules>
                                     the same entry run through the House Rules command, which
                                     resolves the repository's House Rules version first

Kimi Code passes no session-start hook output to the model, so for Kimi a UserPromptSubmit
hook prints the rules once per session id. Kimi 2.2.0 and later keep that output through
compaction. The session ids already given the complete rules are empty files under
$KIMI_CODE_HOME/house-rules-sessions, written only after the rules were printed.

Claude Code caps each hook's output at 10 000 characters and runs a product's hooks in
parallel, so parts can arrive in any order. Parts split only at file and heading boundaries,
and each part names its number, the part count, and the file and heading it starts at.
A missing file, a section larger than one part or more parts than hooks prints a visible
error line in place of the text.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time


CAP = 10_000      # Claude Code's limit for one hook's output, in UTF-16 code units.
RESERVE = 1_200   # Room in a part for its label, the part 1 introduction, an overflow error and the end line.
SLOTS = 12        # Claude Code hooks registered; the last one reports text that needs more.
TIMEOUT = 10      # Seconds each product waits for one hook.
ERROR = "HOUSE RULES HOOK ERROR:"
# Every reply is operator-facing text, which INDEX.md sends to this skill.
EXTRA_FILES = ["skills/operator-writing/SKILL.md"]
LOCAL_INDEX = "custom/INDEX.md"
APPROVED_CONF = "custom/approved-work.conf"
APPROVED_CAP = 3_000  # characters the hook prints; issue rows that do not fit give way to one notice
GH_TIMEOUT = 7        # seconds for all of the listing's GitHub searches, under the hook's TIMEOUT
GH_LIMIT = 100        # issues per search, more than the cap can show; reaching it prints the notice
KIMI_STATE = "house-rules-sessions"   # Folder in the Kimi home holding one empty file per session id given the rules.
SESSION_ID = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,199}")
HEADING = re.compile(r" {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t#]*$")
FENCE = re.compile(r"\s*(`{3,}|~{3,})")


def root():
    return Path(__file__).resolve().parents[1]


def house_rules():
    """scripts/house_rules.py beside this script, or None in a tree that predates it."""
    path = Path(__file__).with_name("house_rules.py")
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("house_rules", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolution():
    """The resolution `house-rules exec` handed this run, when it resolved this script's own tree."""
    module = house_rules()
    record = module.handed() if module else None
    if record and record["layers"] and Path(record["layers"][0]["tree"]).resolve() == root():
        return record
    return None


def local_index(base):
    """This computer's custom/INDEX.md: the tree's own custom/ when it has one, else the configuration folder's."""
    module = house_rules()
    if (base / "custom").is_dir() or module is None:
        return base / LOCAL_INDEX
    return module.config_home() / LOCAL_INDEX


def layer_context(record):
    """(name, text) of each custom layer's context file, in layer order, from the resolution's `context` list."""
    if record is None:
        return
    module = house_rules()
    for item in record.get("context", []):
        tree = Path(module.layer_tree(record, item["layer"].split("/", 1)[0]))
        name, path = f"{item['layer']} {item['path']}", tree / item["path"]
        try:
            yield name, path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            yield name, f"{ERROR} cannot read {path}: {error}\n"


def units(text):
    """Claude Code measures JavaScript string length: UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def always_load(index_text):
    """Rule files under INDEX.md's "Always load" heading, in index order."""
    section = index_text.split("## Always load", 1)
    if len(section) != 2:
        return []
    return re.findall(r"\]\((rules/[^)]+\.md)\)", section[1].split("\n## ", 1)[0])


def revision(base):
    record = resolution()
    if record:
        return record["layers"][0]["revision"][:12]
    try:
        return subprocess.run(["git", "--no-optional-locks", "-C", str(base), "rev-parse", "--short=12", "HEAD"],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True,
                              timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def sources(base, failures=None):
    """(name, text) for every injected file; a missing file becomes an error line.

    failures, when given, collects each House Rules file that could not be supplied. A missing local
    index is the operator's state, not a House Rules failure, so it is not collected.
    """
    failures = [] if failures is None else failures
    index = base / "INDEX.md"
    names = ["INDEX.md"]
    # Read the index once: the file list and the printed index come from the same text, so an update
    # between two reads cannot print an index whose newly listed file was never loaded.
    index_text = index.read_text(encoding="utf-8") if index.is_file() else None
    if index_text is not None:
        listed = always_load(index_text)
        if not listed:
            failures.append("INDEX.md")
            yield "INDEX.md", f"{ERROR} {index} lists no always-load rule files.\n"
        names += listed
    names += EXTRA_FILES
    for name in names:
        path = base / name
        if name == "INDEX.md":
            # Only the first read counts: an index restored after it was found missing is not printed
            # with a file list that was never loaded from it.
            if index_text is not None:
                yield name, index_text
            else:
                failures.append(name)
                yield name, f"{ERROR} {path} is missing.\n"
        elif path.is_file():
            yield name, path.read_text(encoding="utf-8")
        else:
            failures.append(name)
            yield name, f"{ERROR} {path} is missing.\n"
    path = local_index(base)
    # Only an absent local index is the operator's state; any other read failure (a denied folder, for
    # example) reaches the caller, so a Kimi session is not recorded as having the local policies.
    try:
        local = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        local = (f"{ERROR} this computer's local index {path} is missing, so its local policies are not loaded. "
                 "INSTALL-AGENTS.md §4 creates it.\n")
    yield LOCAL_INDEX, local
    yield from layer_context(resolution())


def sections(name, text):
    """Split one file at headings outside code fences: [(file, heading, text)]."""
    blocks, lines, heading, fence = [], [], name, None
    for line in text.splitlines(keepends=True):
        opening = FENCE.match(line)
        if fence is None and opening:
            fence = opening.group(1)
        elif fence is not None:
            if opening and opening.group(1)[0] == fence[0] and len(opening.group(1)) >= len(fence) and \
                    not line.strip().strip(fence[0]):
                fence = None
        else:
            match = HEADING.match(line.rstrip("\n"))
            if match:
                if lines:
                    blocks.append((name, heading, "".join(lines)))
                lines, heading = [], (match.group(2) or "").strip() or name
        lines.append(line)
    blocks.append((name, heading, "".join(lines)))
    return blocks


def parts(base=None, failures=None):
    """Pack whole sections into parts under the cap.

    Returns (revision, [(file, heading, text)] per part, [(file, heading)] of sections too long for
    one part). A section is never split: one too long for a part becomes a visible error line.
    failures, when given, collects the House Rules files sources() could not supply.
    """
    base = base or root()
    limit = CAP - RESERVE
    blocks, too_long = [], []
    for name, text in sources(base, failures):
        for index, (name, heading, section) in enumerate(sections(name, text)):
            if units(section) > limit:
                too_long.append((name, heading))
                section = (f"{ERROR} {name} section \"{heading}\" is {units(section)} characters, more than the "
                           f"{limit} one part holds, so it is not in this context. Read it from {base / name}.\n")
            if index == 0:
                section = f"\n===== House Rules file {name} =====\n{section}"
            blocks.append((name, heading, section))
    packed = []
    for name, heading, text in blocks:
        if not packed or units(packed[-1][2] + text) > limit:
            packed.append((name, heading, text))
        else:
            packed[-1] = (*packed[-1][:2], packed[-1][2] + text)
    return revision(base), packed, too_long


def fingerprint(packed):
    """Names the exact text all parts were cut from, so parts read at different moments differ visibly."""
    return hashlib.sha256("".join(text for _, _, text in packed).encode("utf-8")).hexdigest()[:12]


def label(number, total, rev, text_id, name, heading):
    heading = heading if len(heading) <= 100 else heading[:99] + "…"
    return (f"===== House Rules part {number} of {total} (revision {rev}, text {text_id}); "
            f"starts at {name}, heading \"{heading}\" =====")


def render(number, rev, packed):
    """The text of one part, with its label; part 1 also says how to read the parts."""
    total = len(packed)
    if number > total:
        return ""
    name, heading, text = packed[number - 1]
    text_id = fingerprint(packed)
    lines = [label(number, total, rev, text_id, name, heading)]
    if number == 1:
        lines.extend(resolution_lines())
        lines.append(f"House Rules INDEX.md, its always-load rules, the operator-writing skill and this computer's "
                     f"{LOCAL_INDEX}, then any custom layer's context files, follow in full, in {total} parts. They apply to every reply in this session. "
                     "The parts can arrive in any order: read them in part-number order. Each part names the file "
                     f"and heading it starts at. Every part names text {text_id}. A missing part number, or a part "
                     "with another part count or text, means the files changed while the parts were read: read "
                     f"the files from {root()} directly.")
    if total > SLOTS and number in (1, SLOTS):
        lines.append(overflow(total))
    # The body keeps its own trailing newlines, so blank source lines survive the split.
    output = "\n".join(lines) + "\n" + text + ("" if text.endswith("\n") else "\n") + \
        f"===== End of House Rules part {number} of {total} ====="
    if units(output) >= CAP:
        raise ValueError(f"part {number} is {units(output)} characters, over the {CAP}-character cap")
    return output


def resolution_lines():
    """Part 1's account of the resolved layers, and where skills are when they differ from the agent home's."""
    record = resolution()
    if record is None:
        return []
    module = house_rules()
    lines = module.describe(record)
    default = module.cache_root() / "default"
    tree = Path(record["layers"][0]["tree"])
    if default.is_symlink() and Path(os.path.realpath(str(default))) != tree.resolve():
        lines.append(f"This repository uses House Rules {record['layers'][0]['revision']}; the skills this agent "
                     f"lists come from the global default, {Path(os.path.realpath(str(default))).name}. Read skill "
                     f"files from {tree}/skills/<name>/SKILL.md.")
    return lines


def overflow(total):
    return (f"{ERROR} the rules need {total} parts but the hook delivers only {SLOTS}, so parts "
            f"{SLOTS + 1} to {total} are not in this context. Read those files from {root()} directly; "
            f"raise SLOTS in scripts/session_context.py.")


def one_line(text, limit=300):
    """Diagnostics stay one line: the listing promises one visible line per failure."""
    return " ".join(str(text).split())[:limit]


def approved(base=None):
    """Open issues labelled `approved` for the configured owners, with each issue's Owner: line.

    Approved work that waits on another step or session is tracked as such an issue (work-tracking
    §Work item and owner). Listing it at session start and after compaction keeps it from being dropped.
    It runs as its own hook, so it can never delay or replace the rules; every failure is one visible line.
    The list is a reminder bounded by APPROVED_CAP: when items are left out, one notice inside the cap says so."""
    try:
        try:
            config = (local_index(base or root()).parent / Path(APPROVED_CONF).name).read_text()
        except FileNotFoundError:
            return ""
        scopes = [line.split("#", 1)[0].strip() for line in config.splitlines()]
        scopes = [scope for scope in scopes if scope]
        deadline = time.monotonic() + GH_TIMEOUT
        rows, incomplete = [], False
        for scope in scopes:
            left = deadline - time.monotonic()
            if left <= 0:
                return f"{ERROR} approved-work listing used its {GH_TIMEOUT} s before searching {scope}."
            flag = "--repo" if "/" in scope else "--owner"
            out = subprocess.run(["gh", "search", "issues", flag, scope, "--label", "approved", "--state", "open",
                                  "--limit", str(GH_LIMIT), "--json", "repository,number,title,body"],
                                 capture_output=True, text=True, timeout=left, stdin=subprocess.DEVNULL)
            items = json.loads(out.stdout) if out.returncode == 0 else None
            if not isinstance(items, list) or not all(valid_issue(item) for item in items):
                return f"{ERROR} approved-work listing for {scope} failed: {one_line(out.stderr or out.stdout)}"
            incomplete |= len(items) >= GH_LIMIT
            for item in items:
                owner = next((line.split(":", 1)[1].strip() for line in item["body"].splitlines()
                              if line.lower().startswith("owner:")), "no Owner: line")
                rows.append(f"- {item['repository']['nameWithOwner']}#{item['number']} {item['title']} — Owner: {owner}")
    except (OSError, ValueError, RecursionError, subprocess.TimeoutExpired) as error:
        return f"{ERROR} approved-work listing failed: {one_line(error)}"
    if not rows:
        return ""
    kept = ["Open approved work. Continue the items you own; the others belong to the owners named:"]
    rows = sorted(rows)
    if not incomplete and len("\n".join([*kept, *rows])) <= APPROVED_CAP:
        return "\n".join([*kept, *rows])
    notice = (f"{ERROR} this list may not show every open approved item. Close the issues of finished "
              "approved work, so the label marks only work that still waits.")
    for row in rows:
        if len("\n".join([*kept, row, notice])) > APPROVED_CAP:
            break
        kept.append(row)
    return "\n".join([*kept, notice])


def valid_issue(item):
    """The fields the listing prints, with the types GitHub returns; anything else is a malformed response."""
    return (isinstance(item, dict) and isinstance(item.get("repository"), dict)
            and isinstance(item["repository"].get("nameWithOwner"), str)
            and type(item.get("number")) is int and isinstance(item.get("title"), str)
            and isinstance(item.get("body"), str))


def claude(number):
    rev, packed, _ = parts()
    return render(number, rev, packed)


def every_part(failures=None):
    """Parts 1 to SLOTS in one text: the same strict cap as Claude Code, so one value may carry it whole.

    failures, when given, collects what kept the text from being complete: missing House Rules files,
    sections too long for a part, and parts beyond SLOTS.
    """
    failures = [] if failures is None else failures
    rev, packed, too_long = parts(failures=failures)
    failures.extend(f"{name}, heading \"{heading}\"" for name, heading in too_long)
    if len(packed) > SLOTS:
        failures.append(f"parts {SLOTS + 1} to {len(packed)}")
    return "\n\n".join(render(number, rev, packed) for number in range(1, min(len(packed), SLOTS) + 1))


def codex():
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": every_part()}})


def kimi_records():
    home = os.environ.get("KIMI_CODE_HOME") or str(Path.home() / ".kimi-code")
    return Path(home) / KIMI_STATE


def kimi_session(stdin):
    """The session id from Kimi's hook input, or None when it is missing or unsafe as a file name."""
    try:
        data = json.loads(stdin.read())
    except ValueError:
        return None
    session = data.get("session_id") if isinstance(data, dict) else None
    return session if isinstance(session, str) and SESSION_ID.fullmatch(session) else None


def kimi_prompt(stdin, stdout):
    """Print every part on the first prompt of a session id, then record the id; later prompts print nothing.

    The record is written only after the rules were printed and flushed. A failed read, an error line in
    place of a House Rules file, or a hook stopped before printing leaves the next prompt to try again.
    """
    session = kimi_session(stdin)
    if session is None:
        # Without a session id the hook cannot tell prompts apart, so every prompt gets the rules.
        stdout.write(f"{ERROR} Kimi gave no usable session id, so the rules repeat on every prompt. "
                     "Check the UserPromptSubmit hook input.\n" + every_part() + "\n")
        return
    record = kimi_records() / session
    if record.exists():
        return
    failures = []
    output = every_part(failures)
    stdout.write(output + "\n")
    stdout.flush()
    if failures:
        return
    record.parent.mkdir(parents=True, exist_ok=True)
    record.touch()


def command(python, base, *args):
    if isinstance(python, HouseRulesCommand):
        return shlex.join([python.path, "exec", "--hook", "scripts/session_context.py", *args])
    return shlex.join([python, "-I", str(base / "scripts/session_context.py"), *args])


class HouseRulesCommand:
    """Hooks that run through the House Rules command, which resolves the repository's version first."""

    def __init__(self, path):
        self.path = str(path)


def hooks(product, python=None, base=None, house_rules=None):
    """The hooks.SessionStart entry for one product's native hook file, as INSTALL-AGENTS.md §3 registers it.

    With house_rules, the path of the installed House Rules command, every handler runs
    `house-rules exec --hook scripts/session_context.py ...` instead of this interpreter and script.
    """
    python, base = python or sys.executable, base or root()
    if house_rules:
        python = HouseRulesCommand(house_rules)
    if product == "claude":
        handlers = [{"type": "command", "command": command(python, base, "claude", str(number)), "timeout": TIMEOUT}
                    for number in range(1, SLOTS + 1)]
        handlers.append({"type": "command", "command": command(python, base, "approved"), "timeout": TIMEOUT})
    elif product == "codex":
        # codex() caps its own output at SLOTS parts, so Codex may pass it whole (limit 0).
        handlers = [{"type": "command", "command": command(python, base, "codex"), "timeout": TIMEOUT,
                     "statusMessage": "Loading House Rules", "additionalContextLimit": 0},
                    {"type": "command", "command": command(python, base, "approved", "codex"), "timeout": TIMEOUT,
                     "statusMessage": "Listing approved work"}]
    elif product == "kimi":
        # The [[hooks]] table of Kimi's config.toml; kimi_toml() prints it.
        handlers = [{"event": "UserPromptSubmit", "command": command(python, base, "kimi", "prompt"),
                     "timeout": TIMEOUT}]
    else:
        raise ValueError(f"no session-context hook for {product}")
    return {"hooks": handlers}


def kimi_toml(python=None, base=None, house_rules=None):
    """The [[hooks]] table INSTALL-AGENTS.md §3 appends to Kimi's config.toml."""
    # A JSON string with non-ASCII kept as is is a valid TOML basic string once DEL, which JSON
    # leaves literal and TOML rejects, is escaped too.
    return "\n".join("[[hooks]]\n" + "".join(f"{key} = {toml_string(value)}\n" for key, value in table.items())
                     for table in hooks("kimi", python, base, house_rules)["hooks"])


def toml_string(value):
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f") if isinstance(value, str) else json.dumps(value)


def main(argv):
    try:
        if len(argv) == 2 and argv[0] == "claude" and argv[1].isdigit() and 1 <= int(argv[1]) <= SLOTS:
            output = claude(int(argv[1]))
        elif argv == ["codex"]:
            output = codex()
        elif argv == ["approved"]:
            output = approved()
        elif argv == ["approved", "codex"]:
            listing = approved()
            output = listing and json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                                     "additionalContext": listing}})
        elif argv == ["kimi", "prompt"]:
            kimi_prompt(sys.stdin, sys.stdout)
            output = ""
        elif len(argv) == 4 and argv[0] == "hooks" and argv[2] == "--command":
            output = (kimi_toml(house_rules=argv[3]).rstrip("\n") if argv[1] == "kimi" else
                      json.dumps(hooks(argv[1], house_rules=argv[3]), indent=2))
        elif len(argv) in (2, 3) and argv[0] == "hooks" and argv[1] == "kimi":
            output = kimi_toml(base=Path(argv[2]) if len(argv) == 3 else None).rstrip("\n")
        elif len(argv) in (2, 3) and argv[0] == "hooks":
            output = json.dumps(hooks(argv[1], base=Path(argv[2]) if len(argv) == 3 else None), indent=2)
        else:
            sys.exit(f"usage: session_context.py claude <1-{SLOTS}> | codex | approved [codex] | kimi prompt | "
                     "hooks <claude|codex|kimi> [<root> | --command <house-rules>]")
    except (OSError, ValueError, UnicodeDecodeError) as error:
        # The hook's output is the only channel the model sees; print the failure there.
        output = f"{ERROR} {error}"
    if output:
        print(output)


if __name__ == "__main__":
    main(sys.argv[1:])
