#!/usr/bin/env python3
"""agent_hook.py run as the harness runs it: an interpreter, the hook input on standard input, synthetic text only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAILING_REPORT = "# Status\n\n`FACT` The import finished.\n"
PASSING_REPORT = "# Status\n\n`FACT` The import finished: `import.log` ends with \"done\".\n"


def claude_input(event, **fields):
    """The common fields Claude Code sends with every hook input."""
    return {"session_id": "session-1", "transcript_path": "/tmp/example/transcript.jsonl", "cwd": "/tmp/example",
            "permission_mode": "default", "hook_event_name": event, **fields}


def codex_input(event, **fields):
    """The fields Codex 0.159 requires for the same event; it adds the model and the turn id."""
    return {**claude_input(event, **fields), "model": "example-model", "turn_id": "turn-1"}


class HookTest(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.TemporaryDirectory(prefix="agent-hook-state-")
        self.addCleanup(self.state.cleanup)

    def run_hook(self, event, data):
        environment = {**os.environ, "XDG_STATE_HOME": self.state.name}
        result = subprocess.run([sys.executable, "-I", str(HERE / "agent_hook.py"), event], input=json.dumps(data),
                                stdin=None, capture_output=True, text=True, env=environment)
        return result.returncode, result.stdout, result.stderr

    def records(self):
        path = Path(self.state.name) / "house-rules/check-hooks.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class PreToolUseTest(HookTest):
    def test_a_crate_wide_cargo_test_is_refused_before_it_runs(self):
        for make in (claude_input, codex_input):
            status, out, err = self.run_hook("PreToolUse", make(
                "PreToolUse", tool_name="Bash", tool_use_id="call-1", tool_input={"command": "cargo test --workspace"}))
            self.assertEqual(status, 2, err)
            self.assertIn("crate_wide_test", err)
            self.assertIn("refused this command before it ran", err)

    def test_targeted_and_read_only_commands_pass(self):
        for command in ("cargo test --release -p parser parse_header", "cargo test --help", "git status"):
            status, out, err = self.run_hook("PreToolUse", claude_input(
                "PreToolUse", tool_name="Bash", tool_input={"command": command}))
            self.assertEqual((status, err), (0, ""), command)

    def test_other_tools_pass(self):
        status, out, err = self.run_hook("PreToolUse", claude_input(
            "PreToolUse", tool_name="Write", tool_input={"file_path": "/tmp/example/a.txt", "content": "cargo test"}))
        self.assertEqual((status, out, err), (0, "", ""))


class StopTest(HookTest):
    def stop(self, message, active):
        return self.run_hook("Stop", codex_input("Stop", stop_hook_active=active, last_assistant_message=message))

    def test_a_failing_final_message_cannot_stop_without_a_rewrite(self):
        status, out, err = self.stop(FAILING_REPORT, False)
        self.assertEqual(status, 2)
        self.assertIn("fact_source", err)
        self.assertIn("Rewrite the message", err)
        status, out, err = self.stop(PASSING_REPORT, True)  # the rewrite, after the harness continued the turn
        self.assertEqual((status, out, err), (0, "", ""))
        self.assertEqual(self.records(), [])

    def test_a_rewrite_that_still_fails_goes_through_once_and_is_recorded(self):
        status, out, err = self.stop(FAILING_REPORT, True)
        self.assertEqual(status, 0, err)
        self.assertIn("still breaks 1 rule(s)", json.loads(out)["systemMessage"])
        [record] = self.records()
        self.assertEqual((record["event"], record["session_id"], record["released"], record["rules"]),
                         ("Stop", "session-1", True, ["report_check.fact_source"]))

    def test_numbered_questions_are_checked_for_their_format(self):
        message = "## Release\n\n### 1\\. Ship the parser?\nIt is ready.\n"
        status, out, err = self.stop(message, False)
        self.assertEqual(status, 2)
        self.assertIn("context_flag", err)

    def test_a_message_without_numbered_questions_skips_the_question_check(self):
        status, out, err = self.stop("The parser is ready. Should I ship it?\n", False)
        self.assertEqual((status, err), (0, ""))

    def test_input_without_a_final_message_passes(self):
        status, out, err = self.run_hook("Stop", claude_input("Stop", stop_hook_active=False))
        self.assertEqual((status, out, err), (0, "", ""))


class UserPromptSubmitTest(HookTest):
    def test_a_balance_or_credential_blocker_adds_its_class_as_context(self):
        for prompt, name in (("The provider balance is empty; I will top up tonight.", "balance"),
                             ("Reauthenticate the review account first.", "credential")):
            status, out, err = self.run_hook("UserPromptSubmit", codex_input("UserPromptSubmit", prompt=prompt))
            self.assertEqual(status, 0, err)
            self.assertIn(f"operator-only blocker, class `{name}`", out)
            self.assertIn("Action: ", out)

    def test_an_ordinary_message_adds_nothing(self):
        status, out, err = self.run_hook("UserPromptSubmit", claude_input("UserPromptSubmit",
                                                                          prompt="Keep the import running."))
        self.assertEqual((status, out, err), (0, "", ""))


class InputTest(HookTest):
    def test_unreadable_input_and_unknown_events_exit_one_with_the_reason(self):
        for event, text in (("Stop", "not json"), ("Stop", "[]"), ("SessionEnd", "{}")):
            result = subprocess.run([sys.executable, "-I", str(HERE / "agent_hook.py"), event], input=text,
                                    stdin=None, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, (event, text))
            self.assertTrue(result.stderr, (event, text))


if __name__ == "__main__":
    unittest.main()
