#!/usr/bin/env python3
"""Put House Rules into an agent session's context at start, resume, clear and compaction.

INSTALL-AGENTS.md §3 registers this script as a session-start hook. It prints INDEX.md, the rule
files its "Always load" section lists, the operator-writing skill and this computer's
custom/INDEX.md, read live from the House Rules checkout that holds this script.

  session_context.py claude <n>      part <n> for Claude Code; one hook per part
  session_context.py codex           every part, as one Codex additionalContext value
  session_context.py hooks <product> [<root>]
                                     the hook entry INSTALL-AGENTS.md §3 registers, running this
                                     interpreter and the script under <root> (default: this checkout)

Claude Code caps each hook's output at 10 000 characters and runs a product's hooks in
parallel, so parts can arrive in any order. Parts split only at file and heading boundaries,
and each part names its number, the part count, and the file and heading it starts at.
A missing file, a part over the cap or more parts than hooks prints a visible error line
instead of dropping text.
"""

import json
from pathlib import Path
import re
import shlex
import subprocess
import sys


CAP = 10_000      # Claude Code's limit for one hook's output, in UTF-16 code units.
RESERVE = 800     # Room in each part for its label, the part 1 introduction and the end line.
SLOTS = 12        # Claude Code hooks registered; the last one reports text that needs more.
TIMEOUT = 10      # Seconds each product waits for one hook.
ERROR = "HOUSE RULES HOOK ERROR:"
# Every reply is operator-facing text, which INDEX.md sends to this skill.
EXTRA_FILES = ["skills/operator-writing/SKILL.md"]
LOCAL_INDEX = "custom/INDEX.md"
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
    """Split one file at headings outside code fences: (file, heading, text, continued)."""
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
                    blocks.append((name, heading, "".join(lines), False))
                lines, heading = [], (match.group(2) or "").strip() or name
        lines.append(line)
    blocks.append((name, heading, "".join(lines), False))
    return blocks


def pieces(block, limit):
    """Split one section larger than a part at blank lines, then lines, then spaces."""
    name, heading, text, _ = block
    for separator in ("\n\n", "\n", " "):
        chunks = [chunk + separator for chunk in text.split(separator)]
        chunks[-1] = chunks[-1][:-len(separator)]
        if all(units(chunk) <= limit for chunk in chunks):
            break
    else:
        raise ValueError(f"{name} under {heading!r} holds a word longer than {limit} characters")
    result, current = [], ""
    for chunk in chunks:
        if current and units(current + chunk) > limit:
            result.append(current)
            current = ""
        current += chunk
    result.append(current)
    return [(name, heading, part, index > 0) for index, part in enumerate(result) if part]


def parts(base=None):
    """Pack whole sections into parts under the cap; returns (revision, [(file, heading, continued, text)])."""
    base = base or root()
    limit = CAP - RESERVE
    blocks = []
    for name, text in sources(base):
        file_blocks = sections(name, text)
        name, heading, first, continued = file_blocks[0]
        file_blocks[0] = (name, heading, f"\n===== House Rules file {name} =====\n{first}", continued)
        for block in file_blocks:
            blocks.extend(pieces(block, limit) if units(block[2]) > limit else [block])
    packed, current, start = [], "", None
    for name, heading, text, continued in blocks:
        if current and units(current + text) > limit:
            packed.append((*start, current))
            current = ""
        if not current:
            start = (name, heading, continued)
        current += text
    packed.append((*start, current))
    return revision(base), packed


def label(number, total, rev, start):
    name, heading, continued = start
    where = "continues" if continued else "starts at"
    heading = heading if len(heading) <= 100 else heading[:99] + "…"
    return f"===== House Rules part {number} of {total} (revision {rev}); {where} {name}, heading \"{heading}\" ====="


def render(number, rev, packed):
    """The text of one part, with its label; part 1 also says how to read the parts."""
    total = len(packed)
    if number > total:
        return ""
    name, heading, continued, text = packed[number - 1]
    lines = [label(number, total, rev, (name, heading, continued))]
    if number == 1:
        lines.append(f"House Rules INDEX.md, its always-load rules, the operator-writing skill and this computer's "
                     f"{LOCAL_INDEX} follow in full, in {total} parts. They apply to every reply in this session. "
                     "The parts can arrive in any order: read them in part-number order. Each part names the file "
                     "and heading it starts at.")
        if total > SLOTS:
            lines.append(overflow(total))
    lines.append(text.rstrip("\n"))
    lines.append(f"===== End of House Rules part {number} of {total} =====")
    output = "\n".join(lines)
    if units(output) >= CAP:
        raise ValueError(f"part {number} is {units(output)} characters, over the {CAP}-character cap")
    return output


def overflow(total):
    return (f"{ERROR} the rules need {total} parts but only {SLOTS} hooks are registered, so parts "
            f"{SLOTS + 1} to {total} are not in this context. Read those files from {root()} directly; "
            f"raise SLOTS in scripts/session_context.py.")


def claude(number):
    rev, packed = parts()
    output = render(number, rev, packed)
    if number == SLOTS and len(packed) > SLOTS:
        output += "\n" + overflow(len(packed))
    return output


def codex():
    rev, packed = parts()
    text = "\n\n".join(render(number, rev, packed) for number in range(1, len(packed) + 1))
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}})


def command(python, base, *args):
    return shlex.join([python, "-I", str(base / "scripts/session_context.py"), *args])


def hooks(product, python=None, base=None):
    """The hooks.SessionStart entry for one product's native hook file, as INSTALL-AGENTS.md §3 registers it."""
    python, base = python or sys.executable, base or root()
    if product == "claude":
        handlers = [{"type": "command", "command": command(python, base, "claude", str(number)), "timeout": TIMEOUT}
                    for number in range(1, SLOTS + 1)]
    elif product == "codex":
        # The hook caps its own output at SLOTS parts, so Codex may pass it whole (limit 0).
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
        elif len(argv) in (2, 3) and argv[0] == "hooks":
            output = json.dumps(hooks(argv[1], base=Path(argv[2]) if len(argv) == 3 else None), indent=2)
        else:
            sys.exit(f"usage: session_context.py claude <1-{SLOTS}> | codex | hooks <claude|codex> [<root>]")
    except (OSError, ValueError, UnicodeDecodeError) as error:
        # The hook's output is the only channel the model sees; print the failure there.
        output = f"{ERROR} {error}"
    if output:
        print(output)


if __name__ == "__main__":
    main(sys.argv[1:])
