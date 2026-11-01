"""Tests for build_hook.py, the PreToolUse hook, on synthetic hook inputs."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_hook  # noqa: E402


def hook_input(command, tool="Bash", **extra):
    return {"tool_name": tool, "tool_input": {"command": command}, "session_id": "session-1", "cwd": "/work/app",
            **extra}


class HookTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.log = self.folder / "state/build-hook.jsonl"

    def run_hook(self, command, harness="claude", **extra):
        stderr = io.StringIO()
        data = command if isinstance(command, dict) else hook_input(command, **extra)
        status = build_hook.main([harness, "--log", str(self.log)], io.StringIO(json.dumps(data)), stderr)
        return status, stderr.getvalue()

    def logged(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]


class WorksAloneTest(HookTest):
    """The installed form: the script run by only an interpreter, with synthetic hook input."""

    def run_script(self, command, harness):
        environment = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.folder / "home"),
                       "XDG_STATE_HOME": str(self.folder / "state-home")}
        result = subprocess.run([sys.executable, "-I", str(HERE / "build_hook.py"), harness],
                                input=json.dumps(hook_input(command)), stdin=None, capture_output=True, text=True,
                                env=environment, cwd=self.folder)
        return result.returncode, result.stderr

    def test_one_refusal_one_warning_one_unsure_and_one_allowed_command(self):
        log = self.folder / "state-home/house-rules/build-hook.jsonl"
        for harness in build_hook.PRODUCTS:
            with self.subTest(harness=harness):
                status, stderr = self.run_script("cargo test", harness)
                self.assertEqual(status, 2, stderr)
                self.assertIn("refused this command before it ran", stderr)
                self.assertIn("cargo test --release -p <crate> <test_name>", stderr)
        self.assertEqual(self.run_script("cargo test --release -p core", "claude"), (0, ""))
        self.assertEqual(self.run_script("cat <<'EOF'\ncargo test --workspace\nEOF", "codex"), (0, ""))
        self.assertEqual(self.run_script("cargo test --release -p core --lib parse", "claude"), (0, ""))
        records = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual([(record["harness"], record["decision"], record["rule"]) for record in records], [
            ("claude", "refused", "crate_wide_test"), ("codex", "refused", "crate_wide_test"),
            ("claude", "warned", "crate_wide_test"), ("codex", "unsure", "here_document")])
        self.assertEqual(set(records[0]), {"time", "harness", "session_id", "cwd", "decision", "rule", "command"})
        self.assertEqual((records[0]["session_id"], records[0]["cwd"], records[0]["command"]),
                         ("session-1", "/work/app", "cargo test"))

    def test_without_xdg_state_home_the_log_is_in_the_home_state_folder(self):
        environment = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.folder / "home")}
        result = subprocess.run([sys.executable, "-I", str(HERE / "build_hook.py"), "claude"],
                                input=json.dumps(hook_input("cargo clippy --workspace")), stdin=None, capture_output=True,
                                text=True, env=environment)
        self.assertEqual(result.returncode, 2, result.stderr)
        log = self.folder / "home/.local/state/house-rules/build-hook.jsonl"
        self.assertEqual(json.loads(log.read_text())["rule"], "crate_wide_clippy")


class RefusalTest(HookTest):
    def test_workspace_wide_test_and_clippy_runs_are_refused(self):
        for command in ("cargo test --release parse", "cargo test --release --workspace -p core parse",
                        "cargo test --release --all parse", "cargo nextest run --release parse",
                        "cargo clippy --release --lib", "cargo clippy --release -p core --lib --all",
                        "git status && cargo t --release parse", "bash -c 'cargo test --release parse'"):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(command)[0], 2)

    def test_a_refusal_logs_only_the_workspace_rule(self):
        self.assertEqual(self.run_hook("cargo test")[0], 2)
        self.assertEqual([(record["decision"], record["rule"]) for record in self.logged()],
                         [("refused", "crate_wide_test")])

    def test_a_refusal_that_cannot_be_logged_still_blocks_and_says_so(self):
        self.log.parent.write_text("a file where the log folder should be")
        status, stderr = self.run_hook("cargo test --workspace")
        self.assertEqual(status, 2)
        self.assertIn("refused this command", stderr)
        self.assertIn(f"the refused decision could not be logged in {self.log}", stderr)


class WarningTest(HookTest):
    def test_every_other_finding_runs_and_is_logged_as_a_warning_with_its_rule(self):
        for command, rule in (("cargo test --release -p core", "crate_wide_test"),
                              ("cargo clippy --release -p core --all-targets", "crate_wide_clippy"),
                              ("cargo build -p core", "debug_build"), ("make test", "whole_suite"),
                              ("ctest --output-on-failure", "whole_suite")):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(command), (0, ""))
                self.assertEqual((self.logged()[-1]["decision"], self.logged()[-1]["rule"]), ("warned", rule))

    def test_a_warning_that_cannot_be_logged_runs_and_says_so(self):
        self.log.parent.write_text("a file where the log folder should be")
        status, stderr = self.run_hook("cargo build -p core")
        self.assertEqual(status, 0)
        self.assertIn("the warned decision could not be logged", stderr)


class UnsureTest(HookTest):
    def test_text_the_parser_cannot_read_exactly_is_allowed_and_logged_as_unsure(self):
        for command, rule in (
                ("cat <<'EOF' > notes.md\nrun `cargo test --workspace` in CI\nEOF\n", "here_document"),
                # A here-document whose punctuation could hide a later command is still only unsure.
                ("cat <<'EOF'\n'\nEOF\ncargo test --workspace", "here_document"),
                ("bash <<< 'cargo test --workspace'", "here_document"),
                ("cargo test $(echo --workspace)", "command_substitution"),
                ("cargo test `echo --workspace`", "backticks"),
                ("diff <(cargo tree) expected.txt", "process_substitution"),
                ("eval 'cargo test --workspace'", "eval"),
                ("echo -p core | xargs cargo test", "xargs"),
                ("cargo test 'unterminated", "parse_error")):
            with self.subTest(command=command):
                before = len(self.logged())
                self.assertEqual(self.run_hook(command), (0, ""))
                records = self.logged()[before:]
                self.assertEqual({record["decision"] for record in records}, {"unsure"})
                self.assertIn(rule, [record["rule"] for record in records])

    def test_unsure_text_without_a_checked_program_is_not_logged(self):
        self.assertEqual(self.run_hook("echo $(date) && cat <<EOF\nnotes\nEOF"), (0, ""))
        self.assertEqual(self.run_hook("echo 'unterminated"), (0, ""))
        self.assertEqual(self.logged(), [])


class AllowedTest(HookTest):
    def test_commands_that_match_no_rule_run_and_are_not_logged(self):
        for command in ("cargo test --release -p core --lib parse", "cargo clippy --release -p core --lib",
                        "git commit -m 'avoid cargo test --workspace'", "ls -la"):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(command), (0, ""))
        self.assertEqual(self.logged(), [])

    def test_other_tools_and_inputs_without_a_command_run(self):
        self.assertEqual(self.run_hook("cargo test", tool="Write"), (0, ""))
        self.assertEqual(self.run_hook({"tool_name": "Bash", "tool_input": "cargo test"}), (0, ""))
        self.assertEqual(self.logged(), [])

    def test_input_that_is_not_a_json_object_exits_1_so_the_command_still_runs(self):
        for text in ("not json", "[]"):
            stderr = io.StringIO()
            self.assertEqual(build_hook.main(["claude"], io.StringIO(text), stderr), 1)
            self.assertIn("build-command hook", stderr.getvalue())

    def test_a_wrong_argument_is_a_usage_error(self):
        for argv in ([], ["kimi"], ["claude", "--log"], ["claude", "--log", "relative.jsonl"]):
            with self.subTest(argv=argv):
                self.assertEqual(build_hook.main(argv, io.StringIO("{}"), io.StringIO()), 1)


class RedactionTest(HookTest):
    def test_assignment_values_and_secret_flag_arguments_are_redacted(self):
        for command, logged in (
                ("API_TOKEN=abc123 cargo test", "API_TOKEN=<redacted> cargo test"),
                ("env DB_URL='postgres://user:pw@host/db' cargo test",
                 "env DB_URL=<redacted> cargo test"),
                ("cargo test --workspace --token abc --api-key=xyz --client-secret \"s e\" --password p",
                 "cargo test --workspace --token <redacted> --api-key=<redacted> --client-secret <redacted> "
                 "--password <redacted>")):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(command)[0], 2)
                self.assertEqual(self.logged()[-1]["command"], logged)
        text = self.log.read_text()
        for secret in ("abc123", "postgres://", "xyz", "s e", " p\""):
            self.assertNotIn(secret, text)

    def test_a_session_id_is_logged_only_when_the_input_has_one(self):
        self.run_hook({"tool_name": "Bash", "tool_input": {"command": "cargo test"}})
        self.assertNotIn("session_id", self.logged()[0])
        self.assertEqual(self.logged()[0]["cwd"], os.getcwd())


if __name__ == "__main__":
    unittest.main()
