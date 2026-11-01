#!/usr/bin/env python3
"""Run the House Rules checks as Claude Code and Codex hooks.

Usage: agent_hook.py PreToolUse | Stop | UserPromptSubmit   (the hook input on standard input)

INSTALL-AGENTS.md §3 step 10 registers one hook per event. Claude Code and Codex send the same
input fields for these events and read the same two channels from the hook, so one form serves
both: exit status 2 with the reason on standard error blocks, and standard output on exit 0 is
context for the model.

- PreToolUse: on a shell tool call (`Bash`), runs build_command.py on `tool_input.command`. A
  refused command is blocked before it runs, with each refusal as the reason. Any other tool
  passes.
- Stop: runs report_check.py on the final message (`last_assistant_message`), and
  question_format.py too when the message holds a numbered question heading. On a finding it
  blocks the stop once with the findings, so the agent rewrites the message. When the harness
  says a stop hook already continued this turn (`stop_hook_active`), the stop goes through and
  one line is appended to check-hooks.jsonl in the state folder ($XDG_STATE_HOME/house-rules, by
  default ~/.local/state/house-rules), with the session id and the rules the message still breaks.
- UserPromptSubmit: runs blocker_classify.py on the operator's message (`prompt`). It never
  blocks. When the message names an operator-only blocker, it prints the class and the action.

An input that cannot be read exits 1 with the reason on standard error: both harnesses show it and
continue, so a broken hook never stops a session.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blocker_classify  # noqa: E402
import build_command  # noqa: E402
import findings  # noqa: E402
import markdown_text as md  # noqa: E402
import question_format  # noqa: E402
import report_check  # noqa: E402

BLOCK = 2
SHELL_TOOLS = {"Bash"}  # the tool name both harnesses give a shell call
STATE_FILE = "check-hooks.jsonl"


def state_folder():
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "house-rules"


def listed(records):
    return "\n".join(f"- line {record['line']}, {record['rule']}: {record['message']}" if record.get("line") else
                     f"- {record['rule']}: {record['message']}" for record in records)


def pre_tool_use(data, stdout, stderr):
    command = data.get("tool_input", {}).get("command") if isinstance(data.get("tool_input"), dict) else None
    if data.get("tool_name") not in SHELL_TOOLS or not isinstance(command, str):
        return 0
    refusals = build_command.check(command)
    if not refusals:
        return 0
    stderr.write("House Rules build check refused this command before it ran (rules/delivery.md §Verification):\n"
                 f"{listed(refusals)}\nRun a targeted command instead; CI runs the full suite.\n")
    return BLOCK


def asks_numbered_question(text):
    """True when a heading of the text is a numbered question, as question_format.py reads one."""
    for line in md.read_lines(text):
        parsed = md.heading(line)
        asked = parsed and question_format.question_heading(*parsed)
        if asked and asked[0] is not None:
            return True
    return False


def stop(data, stdout, stderr):
    message = data.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        return 0
    found = report_check.check(message)
    if asks_numbered_question(message):
        found += question_format.check(message)
    if not found:
        return 0
    if data.get("stop_hook_active") is not True:
        stderr.write("House Rules report check: the final message breaks these rules (rules/writing.md §Claim "
                     "labels and §Checks before sending, rules/session-writing.md §Questions to the operator). "
                     f"Rewrite the message and send it again:\n{listed(found)}\n")
        return BLOCK
    record = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": "Stop",
              "session_id": data.get("session_id"), "released": True,
              "rules": sorted({f"{item['check']}.{item['rule']}" for item in found})}
    path = state_folder() / STATE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
    except OSError as error:
        stderr.write(f"House Rules report check let the stop through after one rewrite, but could not record it "
                     f"in {path}: {error}\n")
        return findings.INPUT_ERROR
    stdout.write(json.dumps({"systemMessage": f"House Rules report check: the rewritten final message still breaks "
                                              f"{len(found)} rule(s); the stop went through and is recorded in "
                                              f"{path}."}) + "\n")
    return 0


def user_prompt_submit(data, stdout, stderr):
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return 0
    result = blocker_classify.classify({"text": prompt})
    if result["operator_only"]:
        stdout.write(f"House Rules blocker check: the operator's message names an operator-only blocker, class "
                     f"`{result['class']}` (matched \"{result['matched']}\"). Only the operator can clear it. "
                     f"Action: {result['action']}\n")
    return 0


EVENTS = {"PreToolUse": pre_tool_use, "Stop": stop, "UserPromptSubmit": user_prompt_submit}


def main(argv=None, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in EVENTS:
        stderr.write(f"usage: agent_hook.py {' | '.join(EVENTS)}   (the hook input on standard input)\n")
        return findings.INPUT_ERROR
    try:
        data = json.loads(stdin.read())
    except (OSError, UnicodeDecodeError, ValueError) as error:
        stderr.write(f"House Rules {argv[0]} hook: the hook input is not JSON: {error}\n")
        return findings.INPUT_ERROR
    if not isinstance(data, dict):
        stderr.write(f"House Rules {argv[0]} hook: the hook input is not a JSON object\n")
        return findings.INPUT_ERROR
    return EVENTS[argv[0]](data, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
