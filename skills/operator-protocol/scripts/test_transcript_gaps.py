from pathlib import Path
import io
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import transcript_gaps


SCRIPT = Path(__file__).with_name("transcript_gaps.py")
FIXTURES = SCRIPT.parent / "fixtures"


class TranscriptGapsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.state = self.root / "state"
        self.env = {"HOME": str(self.home), "PATH": os.defpath,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "TRANSCRIPT_GAPS_STATE_DIR": str(self.state)}

    def run_script(self, script=SCRIPT, env=None):
        return subprocess.run([sys.executable, str(script)], stdin=subprocess.DEVNULL, env=env or self.env,
                              capture_output=True, text=True, timeout=5, cwd=self.root)

    def fixture(self, name, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURES / name, destination)
        return destination

    def rows(self):
        batches = sorted(self.state.glob("messages-*.jsonl"), key=lambda p: p.stat().st_mtime_ns)
        return [json.loads(line) for line in batches[-1].read_text().splitlines()]

    def test_each_tool_keeps_exactly_human_text(self):
        self.fixture("claude.jsonl", self.home / ".claude/projects/project/session.jsonl")
        self.fixture("codex.jsonl", self.home / ".codex/sessions/date/session.jsonl")
        self.fixture("codex-exec.jsonl", self.home / ".codex/sessions/date/agent.jsonl")
        self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(result.stdout.strip()).is_file())
        self.assertEqual(Path(result.stdout.strip()).parent, self.state)
        self.assertEqual(self.rows(), [
            {"tool": "claude", "session": "claude-session", "timestamp": "2026-01-01T00:00:00Z",
             "text": "Use clear labels."},
            {"tool": "claude", "session": "claude-session", "timestamp": "2026-01-01T00:00:01Z",
             "text": "Keep all text.\nIncluding this line."},
            {"tool": "codex", "session": "codex-session", "timestamp": "2026-01-01T00:00:00Z",
             "text": "Report failed checks."},
            {"tool": "codex", "session": "codex-session", "timestamp": "2026-01-01T00:00:01Z",
             "text": "Explain the AGENTS.md rule and <environment_context> tag."},
            {"tool": "kimi", "session": "history", "timestamp": None,
             "text": "Keep examples generic."},
        ])

    def test_no_new_messages_produces_nothing_and_changes_no_state(self):
        self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")
        self.assertEqual(self.run_script().returncode, 0)
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.state.iterdir()}
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                                  for p in self.state.iterdir()})

    def test_failed_output_delivery_preserves_marker_and_retry_delivers_batch(self):
        path = self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")
        self.assertEqual(self.run_script().returncode, 0)
        marker = self.state / "last-run.json"
        for operation in ("write", "flush"):
            with self.subTest(operation=operation):
                before = marker.read_bytes()
                text = f"Keep instructions after failed output {operation}."
                with path.open("a") as stream:
                    stream.write(json.dumps({"content": text}) + "\n")
                output = mock.Mock()
                getattr(output, operation).side_effect = BrokenPipeError("closed output")
                errors = io.StringIO()
                with mock.patch.dict(os.environ, self.env, clear=True), \
                        mock.patch.object(sys, "stdout", output), \
                        mock.patch.object(sys, "stderr", errors):
                    status = transcript_gaps.main()
                self.assertEqual(status, 2)
                self.assertIn("closed output", errors.getvalue())
                self.assertEqual(marker.read_bytes(), before)
                self.assertEqual([row["text"] for row in self.rows()], [text])
                batch = max(self.state.glob("messages-*.jsonl"), key=lambda p: p.stat().st_mtime_ns)
                result = self.run_script()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), str(batch))
                self.assertEqual([row["text"] for row in self.rows()], [text])
                self.assertNotEqual(marker.read_bytes(), before)
                self.assertEqual(self.run_script().stdout, "")

    def test_appended_messages_and_late_files_do_not_depend_on_dates(self):
        path = self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")
        self.assertEqual(self.run_script().returncode, 0)
        with path.open("a") as stream:
            stream.write(json.dumps({"content": "Keep examples generic."}) + "\n")
        self.fixture("claude.jsonl", self.home / ".claude/projects/late/session.jsonl")
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual([r["text"] for r in self.rows()],
                         ["Use clear labels.", "Keep all text.\nIncluding this line.",
                          "Keep examples generic."])
        self.assertEqual(self.run_script().stdout, "")

    def test_local_config_sources_extra_homes_and_roots_without_changing_defaults(self):
        checkout = self.root / "checkout"
        script = checkout / "skills/operator-protocol/scripts/transcript_gaps.py"
        script.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, script)
        config = checkout / "custom/transcript-gaps.env"
        config.parent.mkdir()
        extra = self.root / "extra home"
        claude = self.root / "extra projects"
        self.fixture("codex.jsonl", extra / "sessions/date/session.jsonl")
        self.fixture("claude.jsonl", claude / "project/session.jsonl")
        self.assertEqual(self.run_script(script).stdout, "")
        config.write_text('TRANSCRIPT_GAPS_CODEX_HOMES="' + str(extra) + '"\n'
                          'TRANSCRIPT_GAPS_CLAUDE_ROOTS="' + str(claude) + '"\n')
        result = subprocess.run(
            ["/bin/sh", "-c", 'set -a; . "$1"; exec "$2" "$3"',
             "transcript-gaps", str(config), sys.executable, str(script)],
            stdin=subprocess.DEVNULL, env=self.env, capture_output=True, text=True, timeout=5, cwd=self.root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({row["tool"] for row in self.rows()}, {"claude", "codex"})

    def test_home_overrides_and_overlapping_extra_paths(self):
        codex = self.root / "codex home"
        kimi = self.root / "kimi home"
        self.env.update(CODEX_HOME=str(codex), KIMI_CODE_HOME=str(kimi),
                        TRANSCRIPT_GAPS_CODEX_HOMES=str(codex) + os.pathsep + str(codex))
        self.fixture("codex.jsonl", codex / "sessions/date/session.jsonl")
        self.fixture("kimi.jsonl", kimi / "user-history/history.jsonl")
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(len(self.rows()), 3)

    def test_writes_nothing_inside_checkout(self):
        checkout = self.root / "checkout"
        (checkout / ".git").mkdir(parents=True)
        script = checkout / "skills/operator-protocol/scripts/transcript_gaps.py"
        script.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, script)
        self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")

        def snapshot():
            return {str(p.relative_to(checkout)): (p.stat().st_mtime_ns,
                                                  p.read_bytes() if p.is_file() else None)
                    for p in checkout.rglob("*")}

        before = snapshot()
        self.assertEqual(self.run_script(script).returncode, 0)
        self.assertEqual(before, snapshot())
        for directory in (checkout / "state", checkout / ".git/state"):
            self.env["TRANSCRIPT_GAPS_STATE_DIR"] = str(directory)
            result = self.run_script(script)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertFalse(directory.exists())
        self.assertEqual(before, snapshot())

    def test_state_in_other_repository_or_symlink_is_rejected(self):
        repository = self.root / "other"
        repository.mkdir()
        (repository / ".git").write_text("gitdir: placeholder\n")
        alias = self.root / "alias"
        alias.symlink_to(repository, target_is_directory=True)
        for path in (repository / "state", alias / "state"):
            self.env["TRANSCRIPT_GAPS_STATE_DIR"] = str(path)
            result = self.run_script()
            self.assertEqual(result.returncode, 2)
            self.assertFalse(path.exists())

    def test_marker_symlink_is_rejected_without_touching_target(self):
        self.state.mkdir()
        target = self.root / "target"
        target.write_text("unchanged")
        (self.state / "last-run.json").symlink_to(target)
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(target.read_text(), "unchanged")

    def test_output_symlink_cannot_redirect_writes_into_repository(self):
        self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        batch = Path(result.stdout.strip())
        repository = self.root / "repository"
        (repository / ".git").mkdir(parents=True)
        target = repository / "unchanged"
        target.write_text("unchanged")
        batch.unlink()
        batch.symlink_to(target)
        (self.state / "last-run.json").unlink()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(batch.is_symlink())
        self.assertEqual(target.read_text(), "unchanged")

    def test_malformed_input_fails_without_advancing_marker_or_leaking_text(self):
        path = self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")
        self.assertEqual(self.run_script().returncode, 0)
        before = {p.name: p.read_bytes() for p in self.state.iterdir()}
        with path.open("a") as stream:
            stream.write('{"content":"unclosed synthetic value"\n')
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("unclosed synthetic value", result.stderr)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.state.iterdir()})

    def test_truncated_source_fails_visibly(self):
        path = self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")
        self.assertEqual(self.run_script().returncode, 0)
        path.write_text("")
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIn("truncated", result.stderr)

    def test_missing_codex_provenance_and_unknown_human_content_fail_closed(self):
        path = self.home / ".codex/sessions/session.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"type":"response_item","payload":{"role":"user"}}\n')
        self.assertEqual(self.run_script().returncode, 2)
        path.unlink()
        path = self.home / ".kimi-code/user-history/history.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"content":42}\n')
        self.assertEqual(self.run_script().returncode, 2)

    def test_malformed_structured_fields_fail_without_a_traceback(self):
        path = self.home / ".codex/sessions/session.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"type":"session_meta","payload":null}\n')
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_codex_subagent_source_is_excluded(self):
        path = self.fixture("codex-exec.jsonl", self.home / ".codex/sessions/session.jsonl")
        lines = path.read_text().splitlines()
        metadata = json.loads(lines[0])
        metadata["payload"]["originator"] = "codex_cli_rs"
        metadata["payload"]["source"] = {"subagent": {"thread_spawn": {}}}
        path.write_text(json.dumps(metadata) + "\n" + lines[1] + "\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(list(self.state.glob("messages-*.jsonl")), [])

    def test_default_state_uses_user_state_directory_outside_checkout(self):
        del self.env["TRANSCRIPT_GAPS_STATE_DIR"]
        self.env["XDG_STATE_HOME"] = str(self.root / "user-state")
        self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()).parent,
                         self.root / "user-state/house-rules/transcript-gaps")

    def test_injected_parts_are_dropped_whole(self):
        parts = [
            "# AGENTS.md instructions",
            "# AGENTS.md instructions for /example\n<INSTRUCTIONS>rules</INSTRUCTIONS>`",
            "<environment_context>rules</environment_context>`",
            "<turn_aborted>guidance",
            "<subagent_notification>completion",
            "<recommended_plugins>plugins",
            "<goal_context>goal",
            "<codex_delegation>delegation",
            "<skill>context",
            "<task-notification>notification",
            '<teammate-message teammate_id="example">notification',
            "<future_tag-123>context",
            "<123>context",
            "<_context>context",
            "<-context>context",
        ]
        for tool in ("codex", "claude"):
            for part in parts:
                with self.subTest(tool=tool, part=part):
                    self.assertEqual(transcript_gaps.text_content(part, tool), "")
                    self.assertEqual(transcript_gaps.text_content(" \t\n" + part, tool), "")

    def test_human_parts_are_kept_whole_unchanged(self):
        parts = [
            " \tKeep whitespace.\n",
            "Explain <environment_context>rules</environment_context>.",
            "Keep # AGENTS.md instructions literally.",
            "`<skill>context</skill>`",
            "<",
            "< 3 examples are enough.",
            "</environment_context> is a closing tag.",
        ]
        for tool in ("codex", "claude"):
            for part in parts:
                with self.subTest(tool=tool, part=part):
                    self.assertEqual(transcript_gaps.text_content(part, tool), part)

    def test_human_part_starting_with_opening_tag_is_dropped(self):
        for tool in ("codex", "claude"):
            with self.subTest(tool=tool):
                self.assertEqual(transcript_gaps.text_content(
                    "<example>Use this literal example in the documentation.</example>", tool), "")

    def test_injected_parts_do_not_discard_human_parts_in_same_item(self):
        paths = {
            "claude": self.fixture("claude.jsonl", self.home / ".claude/projects/project/session.jsonl"),
            "codex": self.fixture("codex.jsonl", self.home / ".codex/sessions/session.jsonl"),
        }
        self.assertEqual(self.run_script().returncode, 0)
        human = " \tKeep <environment_context>literal tags</environment_context>.\n"
        for tool, path in paths.items():
            content = [{"type": "input_text" if tool == "codex" else "text", "text": text}
                       for text in ("\n<recommended_plugins>injected", human,
                                    "# AGENTS.md instructions", "Keep this too.")]
            record = {"timestamp": "2026-01-01T00:00:02Z"}
            if tool == "codex":
                record.update(type="response_item", payload={
                    "type": "message", "role": "user", "content": content})
            else:
                record.update(type="user", origin={"kind": "human"},
                              sessionId="claude-session", message={"content": content})
            with path.open("a") as stream:
                stream.write(json.dumps(record) + "\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r["text"] for r in self.rows()], [human + "\nKeep this too."] * 2)

    def test_codex_interruption_and_skill_context_are_excluded(self):
        path = self.home / ".codex/sessions/session.jsonl"
        path.parent.mkdir(parents=True)
        records = [{"type": "session_meta", "payload": {
            "id": "codex-session", "originator": "codex_cli_rs", "source": "cli"}}]
        for text in ("<turn_aborted>\nSynthetic interruption guidance.\n</turn_aborted>",
                     "<skill>\n<name>example</name>\n<path>/example/SKILL.md</path>\n"
                     "Synthetic skill context.\n</skill>"):
            records.append({"type": "response_item", "timestamp": "2026-01-01T00:00:00Z",
                            "payload": {"type": "message", "role": "user", "content": [
                                {"type": "input_text", "text": text}]}})
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(list(self.state.glob("messages-*.jsonl")), [])
        self.assertEqual(json.loads((self.state / "last-run.json").read_text()),
                         {"codex:" + str(path): path.stat().st_size})

    def test_kimi_paths_are_not_slash_commands(self):
        path = self.home / ".kimi-code/user-history/history.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"content":"/example/project needs clear documentation."}\n')
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.rows()[0]["text"], "/example/project needs clear documentation.")

    def test_kimi_slash_commands_require_nonempty_namespaces_and_token_boundaries(self):
        path = self.home / ".kimi-code/user-history/history.jsonl"
        path.parent.mkdir(parents=True)
        prose = ["/login: obtain confirmation before changes.", "/skill::example needs labels.",
                 "/skill:example: keep literal text.", "/login, report failures.",
                 "/skill:example/path needs documentation."]
        commands = ["/login", " /add-dir /example", "/release-notes", "/skill:example-skill",
                    "/skill:example:task argument", "/1", "/_example", "/-example"]
        path.write_text("".join(json.dumps({"content": text}) + "\n"
                                for text in prose + commands))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r["text"] for r in self.rows()], prose)

    def test_missing_explicit_primary_source_is_an_error(self):
        for variable in ("CODEX_HOME", "KIMI_CODE_HOME"):
            for home_exists in (False, True):
                with self.subTest(variable=variable, home_exists=home_exists):
                    override = self.root / (variable + str(home_exists))
                    if home_exists:
                        override.mkdir()
                    result = self.run_script(env={**self.env, variable: str(override)})
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(variable, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertFalse(self.state.exists())

    def test_claude_project_directory_symlink_is_followed_at_fixed_depth(self):
        project = self.root / "relocated-project"
        path = self.fixture("claude.jsonl", project / "session.jsonl")
        self.fixture("claude.jsonl", project / "deeper/ignored.jsonl")
        roots = self.home / ".claude/projects"
        roots.mkdir(parents=True)
        (roots / "project").symlink_to(project, target_is_directory=True)
        self.env["TRANSCRIPT_GAPS_CLAUDE_ROOTS"] = str(roots)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip(), "linked project produced no transcript batch")
        self.assertEqual([r["text"] for r in self.rows()],
                         ["Use clear labels.", "Keep all text.\nIncluding this line."])
        self.assertEqual(json.loads((self.state / "last-run.json").read_text()),
                         {"claude:" + str(path): path.stat().st_size})

    def test_ci_runs_transcript_acceptance_suite(self):
        workflow = SCRIPT.parents[3] / ".github/workflows/checks.yml"
        # Any interpreter may run it (CI uses the pinned documentation environment); the suite must run.
        self.assertRegex(workflow.read_text(),
                         r"\n        run: \S*python3? -B skills/spec-writing/scripts/junit_unittest\.py "
                         r"--jobs 4 --report \S+ discover -s skills/operator-protocol/scripts\n")

    def test_missing_extra_root_is_an_error(self):
        self.env["TRANSCRIPT_GAPS_CODEX_HOMES"] = str(self.root / "missing")
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertFalse(self.state.exists())

    def test_excluded_new_entries_advance_marker_without_new_output(self):
        path = self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")
        self.assertEqual(self.run_script().returncode, 0)
        before = sorted(self.state.glob("messages-*.jsonl"))
        with path.open("a") as stream:
            stream.write('{"content":"/login"}\n')
        self.assertEqual(self.run_script().stdout, "")
        marker = (self.state / "last-run.json").read_bytes()
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(marker, (self.state / "last-run.json").read_bytes())
        self.assertEqual(before, sorted(self.state.glob("messages-*.jsonl")))

    def test_state_files_are_private_and_prior_batches_are_retained(self):
        path = self.fixture("kimi.jsonl", self.home / ".kimi-code/user-history/history.jsonl")
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stderr)
        first_batch = Path(first.stdout.strip())
        original = first_batch.read_bytes()
        with path.open("a") as stream:
            stream.write('{"content":"Preserve older findings."}\n')
        second = self.run_script()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(first.stdout, second.stdout)
        self.assertEqual(first_batch.read_bytes(), original)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        for file in self.state.iterdir():
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)

    def test_schedule_examples_are_weekly_and_shell_syntax_is_valid(self):
        references = SCRIPT.parent.parent / "references"
        plist = plistlib.loads((references / "transcript-gaps.plist").read_bytes())
        calendar = plist["StartCalendarInterval"]
        self.assertEqual(calendar, {"Weekday": 1, "Hour": 9, "Minute": 0})
        timer = (references / "transcript-gaps.timer").read_text()
        self.assertIn("OnCalendar=Mon *-*-* 09:00:00", timer)
        service = (references / "transcript-gaps.service").read_text()
        command = service.split("ExecStart=/bin/sh -c '")[1].rstrip().removesuffix("'")
        for command in (plist["ProgramArguments"][2], command.replace("$$", "$")):
            result = subprocess.run(["/bin/sh", "-n", "-c", command],
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
