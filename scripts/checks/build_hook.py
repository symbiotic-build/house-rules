#!/usr/bin/env python3
"""Refuse a workspace-wide cargo test or clippy run before an agent's shell call starts it.

Usage: build_hook.py <claude|codex> [--log PATH]   (the PreToolUse hook input on standard input)

INSTALL-AGENTS.md §3 step 10 registers it as the PreToolUse hook of Claude Code and of every Codex
home. Both products send a shell call's command as `tool_input.command` under the tool name `Bash`,
and read the same two channels: exit status 2 with the reason on standard error blocks the call,
and exit status 0 lets it run. The first argument names the product in the log.

The hook takes one decision per command, from build_command.py's findings:
- refused: a `cargo test`, `cargo nextest run` or `cargo clippy` with no `-p`/`--package`, or with
  `--workspace` or `--all`. The call is blocked, and standard error says why and what to run instead.
- warned: every other build_command.py finding, such as a missing test-name filter, no single clippy
  target, a debug build, `make test` or `ctest` without a selector. The call runs.
- unsure: text the parser cannot read exactly, because the shell expands it or feeds it in: a
  here-document or here-string, a parameter expansion (`$NAME`, `${NAME}`, `$@`), command or
  process substitution, backticks, a command run by `eval` or `xargs`, or a command that does not
  parse. `eval` and `xargs` count only as the program a command runs, not as an argument. The call runs, even when it would otherwise be refused.
Every other command runs and is not logged; an unsure command is logged only when its text names a
checked program (cargo, ctest, make, ninja, cmake), since no other command could be refused.

Each refused, warned or unsure decision appends one JSON line per rule to the log: time, harness,
session id when the input has one, working folder, decision, rule and the command, with the value of
each NAME=value assignment and the argument after each flag named like token, key, secret or password
replaced by <redacted>. Redaction reads whole shell words, with quotes, escapes and substitutions,
and the scripts quoted inside them, such as a `bash -c` script; an unclosed quote or substitution
runs to the end of the command, so all of it is redacted. The log is PATH, else $XDG_STATE_HOME/house-rules/build-hook.jsonl, else
~/.local/state/house-rules/build-hook.jsonl. A log that cannot be written changes no decision; the
hook says so on standard error.

Input that cannot be read exits 1 with the reason on standard error: both products show it and run
the command, so a broken hook never stops a session.
"""
import contextlib
import io
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_command  # noqa: E402
import findings  # noqa: E402

BLOCK = 2
PRODUCTS = ("claude", "codex")
SHELL_TOOLS = {"Bash"}  # the tool name both products give a shell call
LOG_FILE = "build-hook.jsonl"
CLEAR_RULES = {"crate_wide_test", "crate_wide_clippy"}  # refused when build_command.py marks them workspace-wide
# Text the shell expands or feeds in, so the parser cannot tell what runs: (rule, pattern).
UNSURE = (("here_document", re.compile(r"<<")),
          ("parameter_expansion", re.compile(r"\$(?:[A-Za-z_{@*#?$!0-9-])")),
          ("command_substitution", re.compile(r"\$\(")),
          ("backticks", re.compile(r"`")),
          ("process_substitution", re.compile(r"[<>]\(")))
INDIRECT = ("eval", "xargs")  # programs that run their arguments as a command the parser does not read
CHECKED = re.compile(r"(?<![\w.-])(?:[\w./-]*/)?(?:cargo|ctest|g?make|ninja|cmake)(?![\w.-])")
WORD_END = set(";&|()<>")  # unquoted characters that end a shell word, beside whitespace
SECRET_FLAG = re.compile(r"(-{1,2}[\w-]*(?:token|key|secret|password)[\w-]*)(=.*)?", re.IGNORECASE | re.DOTALL)
ASSIGNMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=", re.DOTALL)


def default_log():
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "house-rules" / LOG_FILE


def closing(text, index, opening, close):
    """The index just past the `close` that matches the `opening` at index, or the text's end."""
    depth = 0
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        depth += text[index] == opening
        depth -= text[index] == close
        index += 1
        if depth == 0:
            return index
    return len(text)


def shell_words(text):
    """(start, end, unquoted text) for each shell word; quotes, backslashes and substitutions join a word.

    An unclosed quote or substitution runs to the end of the text.
    """
    result, index = [], 0
    while index < len(text):
        if text[index].isspace() or text[index] in WORD_END:
            index += 1
            continue
        start, value = index, []
        while index < len(text) and not (text[index].isspace() or text[index] in WORD_END):
            char = text[index]
            if char == "\\":
                value.append(text[index + 1:index + 2])
                index += 2
            elif text.startswith(("$(", "${"), index) or char == "`":
                end = text.find("`", index + 1) + 1 if char == "`" else \
                    closing(text, index + 1, text[index + 1], ")" if text[index + 1] == "(" else "}")
                end = len(text) if end <= 0 else end
                value.append(text[index:end])
                index = end
            elif char == "'":
                close = text.find("'", index + 1)
                close = len(text) if close < 0 else close
                value.append(text[index + 1:close])
                index = close + 1
            elif char == '"':
                index += 1
                while index < len(text) and text[index] != '"':
                    if text[index] == "\\":
                        index += 1
                    value.append(text[index:index + 1])
                    index += 1
                index += 1
            else:
                value.append(char)
                index += 1
        result.append((start, min(index, len(text)), "".join(value)))
    return result


def redact(command):
    """The command with assignment values and the values of secret-named flags replaced by <redacted>."""
    replacements, secret_next = [], False
    for start, end, word in shell_words(command):
        flag = SECRET_FLAG.fullmatch(word)
        assignment = ASSIGNMENT.match(word)
        if secret_next:
            replacements.append((start, end, "<redacted>"))
        elif flag and flag[2]:
            replacements.append((start, end, f"{flag[1]}=<redacted>"))
        elif assignment and not word.startswith("-"):
            replacements.append((start, end, f"{assignment[1]}=<redacted>"))
        elif command[start:end] != word and redact(word) != word:  # a quoted script, such as bash -c's
            replacements.append((start, end, shlex.quote(redact(word))))
        secret_next = bool(flag) and not flag[2] and not secret_next
    for start, end, text in reversed(replacements):
        command = command[:start] + text + command[end:]
    return command


def indirect(text):
    """The programs among INDIRECT that a command of the text runs, inside `sh -c` scripts too."""
    result = []
    for _, tokens in build_command.split_commands(text):
        command = build_command.unwrap(tokens)
        name = Path(command[0]).name if command else None
        if name in INDIRECT:
            result.append(name)
        elif name in build_command.SHELLS:
            script = build_command.shell_script(command[1:])
            result.extend(indirect(script) if script is not None else [])
    return result


def decide(command):
    """(decision, [(rule, message)]): decision is refused, warned, unsure, or None for a command that matched no rule."""
    unsure = [rule for rule, pattern in UNSURE if pattern.search(command)]
    found = []
    if not unsure:
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                unsure = list(dict.fromkeys(indirect(command)))
                found = [] if unsure else build_command.check(command)
        except SystemExit:
            unsure = ["parse_error"]
    if unsure:
        return ("unsure", [(rule, None) for rule in unsure]) if CHECKED.search(command) else (None, [])
    if not found:
        return None, []
    clear = [item for item in found if item["rule"] in CLEAR_RULES and item.get("workspace")]
    if not clear:
        return "warned", [(item["rule"], item["message"]) for item in found]
    return "refused", [(item["rule"], item["message"]) for item in clear]


def log(path, harness, data, decision, rules, command):
    """Append one JSON line per rule; returns the error text when the log cannot be written, else None."""
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    session = data.get("session_id") if isinstance(data.get("session_id"), str) else None
    folder = data.get("cwd") if isinstance(data.get("cwd"), str) else os.getcwd()
    lines = "".join(json.dumps({"time": stamp, "harness": harness, **({"session_id": session} if session else {}),
                                "cwd": folder, "decision": decision, "rule": rule, "command": redact(command)},
                               ensure_ascii=False) + "\n" for rule, _ in rules)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(lines)
    except OSError as error:
        return f"House Rules build-command hook: the {decision} decision could not be logged in {path}: {error}\n"
    return None


def pre_tool_use(harness, path, data, stderr):
    tool_input = data.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if data.get("tool_name") not in SHELL_TOOLS or not isinstance(command, str):
        return 0
    decision, rules = decide(command)
    if decision is None:
        return 0
    failure = log(path, harness, data, decision, rules, command)
    if decision != "refused":
        if failure:
            stderr.write(failure)
        return 0
    stderr.write("House Rules build-command hook refused this command before it ran: it runs across every crate, "
                 "and local runs stay targeted (rules/delivery.md §Verification); CI runs the full suite.\n" +
                 "".join(f"- {rule}: {message}\n" for rule, message in rules) +
                 "Run a targeted command instead, for example `cargo test --release -p <crate> <test_name>` or "
                 "`cargo clippy --release -p <crate> --lib`.\n" + (failure or ""))
    return BLOCK


def main(argv=None, stdin=sys.stdin, stderr=sys.stderr):
    argv = sys.argv[1:] if argv is None else argv
    if not (argv[:1] in ([product] for product in PRODUCTS) and
            (len(argv) == 1 or (len(argv) == 3 and argv[1] == "--log" and Path(argv[2]).is_absolute()))):
        stderr.write("usage: build_hook.py <claude|codex> [--log ABSOLUTE-PATH]   (the hook input on standard input)\n")
        return findings.INPUT_ERROR
    path = Path(argv[2]) if len(argv) == 3 else default_log()
    try:
        data = json.loads(stdin.read())
    except (OSError, UnicodeDecodeError, ValueError) as error:
        stderr.write(f"House Rules build-command hook: the hook input is not JSON: {error}\n")
        return findings.INPUT_ERROR
    if not isinstance(data, dict):
        stderr.write("House Rules build-command hook: the hook input is not a JSON object\n")
        return findings.INPUT_ERROR
    return pre_tool_use(argv[0], path, data, stderr)


if __name__ == "__main__":
    sys.exit(main())
