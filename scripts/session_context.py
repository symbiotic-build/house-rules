#!/usr/bin/env python3
"""Put House Rules into an agent session's context at start, resume, clear and compaction.

INSTALL-AGENTS.md §3 registers this script as a session-start hook. It prints INDEX.md, the rule
files its "Always load" section lists, the operator-writing skill and this computer's
custom/INDEX.md, read live from the House Rules checkout that holds this script.

  session_context.py claude <n>      part <n> for Claude Code; one hook per part
  session_context.py codex           every part, as one Codex additionalContext value
  session_context.py approved        open approved work items, when custom/approved-work.conf names
                                     GitHub owners or owner/repo pairs (one per line); nothing otherwise
  session_context.py hooks <product> [<root>]
                                     the hook entry INSTALL-AGENTS.md §3 registers, running this
                                     interpreter and the script under <root> (default: this checkout)

Claude Code caps each hook's output at 10 000 characters and runs a product's hooks in
parallel, so parts can arrive in any order. Parts split only at file and heading boundaries,
and each part names its number, the part count, and the file and heading it starts at.
A missing file, a section larger than one part or more parts than hooks prints a visible
error line in place of the text.
"""

import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys


CAP = 10_000      # Claude Code's limit for one hook's output, in UTF-16 code units.
RESERVE = 1_200   # Room in a part for its label, the part 1 introduction, an overflow error and the end line.
SLOTS = 12        # Claude Code hooks registered; the last one reports text that needs more.
TIMEOUT = 10      # Seconds each product waits for one hook.
ERROR = "HOUSE RULES HOOK ERROR:"
# Every reply is operator-facing text, which INDEX.md sends to this skill.
EXTRA_FILES = ["skills/operator-writing/SKILL.md"]
LOCAL_INDEX = "custom/INDEX.md"
APPROVED_CONF = "custom/approved-work.conf"
APPROVED_CAP = 3_000  # characters of the approved-work list; the rest is named, not dropped silently
GH_TIMEOUT = 8        # seconds for the listing's GitHub query, under the hook's TIMEOUT
HEADING = re.compile(r" {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t#]*$")
FENCE = re.compile(r"\s*(`{3,}|~{3,})")


def root():
    return Path(__file__).resolve().parents[1]


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
    try:
        return subprocess.run(["git", "--no-optional-locks", "-C", str(base), "rev-parse", "--short=12", "HEAD"],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True,
                              timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def sources(base):
    """(name, text) for every injected file; a missing file becomes an error line."""
    index = base / "INDEX.md"
    names = ["INDEX.md"]
    if index.is_file():
        listed = always_load(index.read_text(encoding="utf-8"))
        if not listed:
            yield "INDEX.md", f"{ERROR} {index} lists no always-load rule files.\n"
        names += listed
    names += EXTRA_FILES
    for name in names:
        path = base / name
        yield name, path.read_text(encoding="utf-8") if path.is_file() else f"{ERROR} {path} is missing.\n"
    path = base / LOCAL_INDEX
    yield LOCAL_INDEX, path.read_text(encoding="utf-8") if path.is_file() else (
        f"{ERROR} this computer's local index {path} is missing, so its local policies are not loaded. "
        "INSTALL-AGENTS.md §4 creates it.\n")


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


def parts(base=None):
    """Pack whole sections into parts under the cap.

    Returns (revision, [(file, heading, text)] per part, [(file, heading)] of sections too long for
    one part). A section is never split: one too long for a part becomes a visible error line.
    """
    base = base or root()
    limit = CAP - RESERVE
    blocks, too_long = [], []
    for name, text in sources(base):
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
        lines.append(f"House Rules INDEX.md, its always-load rules, the operator-writing skill and this computer's "
                     f"{LOCAL_INDEX} follow in full, in {total} parts. They apply to every reply in this session. "
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


def overflow(total):
    return (f"{ERROR} the rules need {total} parts but the hook delivers only {SLOTS}, so parts "
            f"{SLOTS + 1} to {total} are not in this context. Read those files from {root()} directly; "
            f"raise SLOTS in scripts/session_context.py.")


def approved(base=None):
    """Open issues labelled `approved` for the configured owners, with each issue's Owner: line.

    Approved work that waits on another step or session is tracked as such an issue (work-tracking
    §Work item and owner); listing it at session start and after compaction keeps it from being dropped."""
    conf = (base or root()) / APPROVED_CONF
    if not conf.is_file():
        return ""
    scopes = [line.strip() for line in conf.read_text().splitlines() if line.strip() and not line.startswith("#")]
    rows = []
    for scope in scopes:
        flag = "--repo" if "/" in scope else "--owner"
        try:
            out = subprocess.run(["gh", "search", "issues", flag, scope, "--label", "approved", "--state", "open",
                                  "--limit", "100", "--json", "repository,number,title,body"],
                                 capture_output=True, text=True, timeout=GH_TIMEOUT, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as error:
            return f"{ERROR} approved-work listing for {scope} failed: {error}"
        if out.returncode:
            return f"{ERROR} approved-work listing for {scope} failed: {out.stderr.strip()[:300]}"
        for item in json.loads(out.stdout or "[]"):
            owner = next((line.split(":", 1)[1].strip() for line in (item.get("body") or "").splitlines()
                          if line.lower().startswith("owner:")), "no Owner: line")
            rows.append(f"- {item['repository']['nameWithOwner']}#{item['number']} {item['title']} — Owner: {owner}")
    if not rows:
        return ""
    text = "Open approved work (start or continue each item; its issue names the owner and next action):\n"
    shown = []
    for row in sorted(rows):
        if len(text) + sum(len(r) + 1 for r in shown) + len(row) > APPROVED_CAP:
            break
        shown.append(row)
    text += "\n".join(shown)
    if len(shown) < len(rows):
        text += f"\n{ERROR} {len(rows) - len(shown)} more approved items are not shown; list them with gh."
    return text


def claude(number):
    rev, packed, _ = parts()
    return render(number, rev, packed)


def codex():
    """Parts 1 to SLOTS in one value: the same strict cap as Claude Code, so Codex may pass it whole."""
    rev, packed, _ = parts()
    text = "\n\n".join(render(number, rev, packed) for number in range(1, min(len(packed), SLOTS) + 1))
    listing = approved()
    if listing:
        text += "\n\n" + listing
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}})


def command(python, base, *args):
    return shlex.join([python, "-I", str(base / "scripts/session_context.py"), *args])


def hooks(product, python=None, base=None):
    """The hooks.SessionStart entry for one product's native hook file, as INSTALL-AGENTS.md §3 registers it."""
    python, base = python or sys.executable, base or root()
    if product == "claude":
        handlers = [{"type": "command", "command": command(python, base, "claude", str(number)), "timeout": TIMEOUT}
                    for number in range(1, SLOTS + 1)]
        handlers.append({"type": "command", "command": command(python, base, "approved"), "timeout": TIMEOUT})
    elif product == "codex":
        # codex() caps its own output at SLOTS parts, so Codex may pass it whole (limit 0).
        handlers = [{"type": "command", "command": command(python, base, "codex"), "timeout": TIMEOUT,
                     "statusMessage": "Loading House Rules", "additionalContextLimit": 0}]
    else:
        raise ValueError(f"no session-start hook for {product}")
    return {"hooks": handlers}


def main(argv):
    try:
        if len(argv) == 2 and argv[0] == "claude" and argv[1].isdigit() and 1 <= int(argv[1]) <= SLOTS:
            output = claude(int(argv[1]))
        elif argv == ["codex"]:
            output = codex()
        elif argv == ["approved"]:
            output = approved()
        elif len(argv) in (2, 3) and argv[0] == "hooks":
            output = json.dumps(hooks(argv[1], base=Path(argv[2]) if len(argv) == 3 else None), indent=2)
        else:
            sys.exit(f"usage: session_context.py claude <1-{SLOTS}> | codex | approved | hooks <claude|codex> [<root>]")
    except (OSError, ValueError, UnicodeDecodeError) as error:
        # The hook's output is the only channel the model sees; print the failure there.
        output = f"{ERROR} {error}"
    if output:
        print(output)


if __name__ == "__main__":
    main(sys.argv[1:])
