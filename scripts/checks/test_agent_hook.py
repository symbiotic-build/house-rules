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

    def run_hook(self, event, data, state=None, extra=()):
        environment = {**os.environ, "XDG_STATE_HOME": state or self.state.name}
        result = subprocess.run([sys.executable, "-I", str(HERE / "agent_hook.py"), event, *extra],
                                input=json.dumps(data), stdin=None, capture_output=True, text=True, env=environment)
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

    def test_a_here_document_body_is_checked_whatever_program_reads_it(self):
        # bash runs its body and cat does not; the check cannot tell them apart, so both are refused (#290).
        for program in ("bash", "cat > notes.md"):
            status, out, err = self.run_hook("PreToolUse", claude_input("PreToolUse", tool_name="Bash", tool_input={
                "command": f"{program} <<'EOF'\ncargo test --workspace --release\nEOF"}))
            self.assertEqual(status, 2, program)
            self.assertIn("crate_wide_test", err)

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
    """The default mode: a finding never blocks the stop; it warns and is recorded."""

    def stop(self, message, active=False, extra=(), state=None):
        return self.run_hook("Stop", codex_input("Stop", stop_hook_active=active, last_assistant_message=message),
                             state=state, extra=extra)

    def test_a_failing_final_message_warns_and_is_recorded_without_blocking(self):
        for active in (False, True):  # stop_hook_active plays no part when the hook only warns
            status, out, err = self.stop(FAILING_REPORT, active)
            self.assertEqual((status, err), (0, ""))
            self.assertEqual(json.loads(out)["systemMessage"], "House Rules report check: the final message breaks "
                             "1 rule(s) (report_check.fact_source); the stop went through and is recorded in "
                             f"{Path(self.state.name) / 'house-rules/check-hooks.jsonl'}.")
        self.assertEqual([(record["event"], record["session_id"], record["mode"], record["rules"])
                          for record in self.records()], [("Stop", "session-1", "warn", ["report_check.fact_source"])] * 2)

    def test_a_passing_final_message_prints_and_records_nothing(self):
        self.assertEqual(self.stop(PASSING_REPORT), (0, "", ""))
        self.assertEqual(self.records(), [])

    def test_a_finding_that_cannot_be_recorded_still_warns_and_lets_the_stop_through(self):
        blocked = Path(self.state.name) / "a file"
        blocked.write_text("")
        status, out, err = self.stop(FAILING_REPORT, state=str(blocked))
        self.assertEqual((status, err), (0, ""))
        warning = json.loads(out)["systemMessage"]
        self.assertIn("breaks 1 rule(s) (report_check.fact_source)", warning)
        self.assertIn("could not be recorded in", warning)

    def test_numbered_questions_are_checked_for_their_format(self):
        status, out, err = self.stop("## Release\n\n### 1\\. Ship the parser?\nIt is ready.\n")
        self.assertEqual(status, 0, err)
        self.assertIn("question_format.context_flag", json.loads(out)["systemMessage"])

    def test_a_message_without_numbered_questions_skips_the_question_check(self):
        self.assertEqual(self.stop("The parser is ready. Should I ship it?\n"), (0, "", ""))

    def test_input_without_a_final_message_passes(self):
        status, out, err = self.run_hook("Stop", claude_input("Stop", stop_hook_active=False))
        self.assertEqual((status, out, err), (0, "", ""))


class BlockingStopTest(StopTest.__base__):
    """Stop --block, the opt-in mode: a finding blocks the stop once."""

    def stop(self, message, active=False):
        return self.run_hook("Stop", codex_input("Stop", stop_hook_active=active, last_assistant_message=message),
                             extra=("--block",))

    def test_a_failing_final_message_cannot_stop_without_a_rewrite(self):
        status, out, err = self.stop(FAILING_REPORT)
        self.assertEqual((status, out), (2, ""))
        self.assertIn("fact_source", err)
        self.assertIn("Rewrite the message", err)
        self.assertEqual(self.records(), [])
        self.assertEqual(self.stop(PASSING_REPORT, True), (0, "", ""))  # the rewrite, after the harness continued

    def test_a_rewrite_that_still_fails_goes_through_once_and_is_recorded(self):
        status, out, err = self.stop(FAILING_REPORT, True)
        self.assertEqual((status, err), (0, ""))
        self.assertIn("the rewritten final message breaks 1 rule(s)", json.loads(out)["systemMessage"])
        [record] = self.records()
        self.assertEqual((record["mode"], record["rules"]), ("block", ["report_check.fact_source"]))

    def test_numbered_questions_are_checked_for_their_format(self):
        status, out, err = self.stop("## Release\n\n### 1\\. Ship the parser?\nIt is ready.\n")
        self.assertEqual(status, 2)
        self.assertIn("context_flag", err)


class UserPromptSubmitTest(HookTest):
    def test_a_balance_or_credential_blocker_adds_its_class_and_action_as_context(self):
        for prompt, name, matched, action in (
                ("The provider balance is empty; I will top up tonight.", "balance", "balance is empty",
                 "Top up the provider account balance, then tell the agent the balance is restored."),
                ("Reauthenticate the review account first.", "credential", "Reauthenticate",
                 "Sign in to the provider again or replace its credential, then tell the agent the credential is "
                 "ready.")):
            status, out, err = self.run_hook("UserPromptSubmit", codex_input("UserPromptSubmit", prompt=prompt))
            self.assertEqual((status, err), (0, ""))
            self.assertEqual(out, f"House Rules blocker check: the operator's message names an operator-only blocker, "
                                  f"class `{name}` (matched \"{matched}\"). Only the operator can clear it. "
                                  f"Action: {action}\n")

    def test_an_ordinary_message_adds_nothing(self):
        status, out, err = self.run_hook("UserPromptSubmit", claude_input("UserPromptSubmit",
                                                                          prompt="Keep the import running."))
        self.assertEqual((status, out, err), (0, "", ""))


class InputTest(HookTest):
    def test_unreadable_input_and_unknown_events_exit_one_with_the_reason(self):
        for arguments, text in ((["Stop"], "not json"), (["Stop"], "[]"), (["SessionEnd"], "{}"),
                                (["Stop", "--warn"], "{}"), (["PreToolUse", "--block"], "{}")):
            result = subprocess.run([sys.executable, "-I", str(HERE / "agent_hook.py"), *arguments], input=text,
                                    stdin=None, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, (arguments, text))
            self.assertTrue(result.stderr, (arguments, text))


if __name__ == "__main__":
    unittest.main()
