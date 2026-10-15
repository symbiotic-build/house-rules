#!/usr/bin/env python3
"""Synthetic homes and local Git remotes; no network or installed-home writes."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/sync.py"
SPEC = importlib.util.spec_from_file_location("sync", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)



# The always-load rule files the fixture index lists (the real index lists the same seven).
RULES = ("core", "outcome", "delivery", "writing", "git", "priority-labels", "session-writing")

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="house-rules-sync-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.env = mock.patch.dict(os.environ, {
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Test Author", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test Author", "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        for variable in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "KIMI_CODE_HOME"):
            os.environ.pop(variable, None)
        self.origin = self.base / "origin"
        self.origin.mkdir()
        self.git(self.origin, "init", "-b", "main")
        self.write(self.origin / ".gitignore", "custom/\n")
        shutil.copyfile(REPO / "INSTALL-AGENTS.md", self.origin / "INSTALL-AGENTS.md")
        self.write(self.origin / "skills/sample/SKILL.md", "# Sample\n")
        self.write(self.origin / "INDEX.md", "# Index\n\n## Always load\n\n" + "".join(
            f"- [{name}](rules/{name}.md)\n" for name in RULES) + "\n## Load when needed\n")
        for name in RULES:
            self.write(self.origin / f"rules/{name}.md", f"# {name} rules\n")
        self.commit(self.origin, [".gitignore", "INSTALL-AGENTS.md", "INDEX.md", "skills/sample/SKILL.md",
                                  *(f"rules/{name}.md" for name in RULES)])
        self.root = self.base / "House Rules checkout"
        self.git(self.base, "clone", str(self.origin), str(self.root))
        self.home = self.base / "user"
        self.home.mkdir()
        self.claude = self.home / ".claude"
        self.codex = self.home / ".codex"
        self.kimi = self.home / ".kimi-code"
        self.claude.mkdir()
        self.kimi.mkdir()
        self.write(self.codex / "config.toml", "# fixture\n")
        patch = mock.patch.object(Path, "home", return_value=self.home)
        patch.start()
        self.addCleanup(patch.stop)
        original_discovery = sync.discover_skills
        admin = mock.patch.object(sync, "discover_skills", side_effect=lambda folder, *args, **kwargs:
                                  set() if folder == Path("/etc/codex/skills") else original_discovery(folder, *args, **kwargs))
        admin.start()
        self.addCleanup(admin.stop)

    def git(self, root, *args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, root, paths):
        self.git(root, "add", "--", *paths)
        self.git(root, "commit", "-m", "Fixture change")

    def invoke(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sync.main(["--root", str(self.root)])
        return code, out.getvalue(), err.getvalue()

    def receipt(self, data):
        self.write(self.root / "custom/installations/fixture.json", json.dumps(data))

    def link(self, path, target):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target, target_is_directory=True)

    def test_removed_fix_option_is_rejected_without_installation_writes(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                sync.main(["--root", str(self.root), "--fix"])
        self.assertEqual(stopped.exception.code, 2)
        self.assertFalse((self.claude / "CLAUDE.md").exists())
        self.assertFalse((self.root / "custom").exists())

    def test_default_run_updates_then_reports_new_skill_without_installing(self):
        self.install_fixture()
        self.write(self.origin / "skills/new/SKILL.md", "# New\n")
        self.commit(self.origin, ["skills/new/SKILL.md"])
        with mock.patch.object(sync, "git", wraps=sync.git) as calls:
            code, out, err = self.invoke()
        revision = self.git(self.origin, "rev-parse", "HEAD")
        self.assertTrue(any(call.args[1:] == ("merge", "--ff-only", "--no-overwrite-ignore", revision)
                            for call in calls.call_args_list))
        self.assertEqual(sum("fetch" in call.args for call in calls.call_args_list), 1)
        self.assertFalse(any("pull" in call.args for call in calls.call_args_list))
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD"),
                         self.git(self.origin, "rev-parse", "HEAD"))
        for folder in (self.claude / "skills", self.home / ".agents/skills"):
            self.assertIn(str(folder / "new"), out)
            self.assertFalse((folder / "new").exists())
        self.assertFalse((self.root / "custom").exists())

    def test_missing_rule_files_are_reported_without_installation_writes(self):
        self.install_fixture()
        for name in RULES:
            with self.subTest(name=name):
                path = self.root / f"rules/{name}.md"
                text = path.read_text()
                path.unlink()
                code, out, err = self.invoke()
                self.assertEqual(code, 1, out + err)
                self.assertIn(f"missing rule file: {path}", out)
                self.assertFalse(path.exists())
                self.assertEqual(err, "")
                path.write_text(text)

    def test_compaction_wording_is_the_authoritative_template(self):
        self.assertIn("At session start and after every context compaction or reset, read "
                      f"`{self.root}/INDEX.md`.", sync.template(self.root))

    def test_old_index_blocks_are_stale_in_every_known_home(self):
        self.install_fixture()
        old_block = sync.template(self.root).replace('/INDEX.md', '/AGENTS.md')
        paths = [self.claude / 'CLAUDE.md', self.codex / 'AGENTS.md',
                 self.kimi / 'AGENTS.md', self.codex / 'AGENTS.override.md']
        for path in paths:
            with self.subTest(path=path):
                self.write(path, old_block)
                findings, selected = [], []
                sync.verify(self.root, self.home, findings, selected)
                self.assertEqual(findings, [f'stale block: {path}'])
                self.assertEqual(path.read_text(), old_block)
                if path.name == 'AGENTS.override.md':
                    path.unlink()
                else:
                    self.write(path, sync.template(self.root))

    def test_renamed_index_is_required_without_old_index_fallback(self):
        index = self.root / 'INDEX.md'
        self.write(self.root / 'AGENTS.md', index.read_text())
        findings = []
        self.assertEqual(sync.always_load(self.root, findings),
                         [self.root / f'rules/{name}.md' for name in RULES])
        self.assertEqual(findings, [])
        index.unlink()
        self.assertEqual(sync.always_load(self.root, findings), [])
        self.assertEqual(findings, [f'missing index: {index}'])

    def test_update_preserves_ignored_files_colliding_with_incoming_paths(self):
        path = "custom/INDEX.md"
        self.write(self.root / path, "Machine-local index\n")
        self.write(self.origin / path, "Incoming tracked file\n")
        self.git(self.origin, "add", "--force", "--", path)
        self.git(self.origin, "commit", "-m", "Add colliding path")
        head = self.git(self.root, "rev-parse", "HEAD")
        code, out, err = self.invoke()
        self.assertEqual((self.root / path).read_text(), "Machine-local index\n")
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD"), head)
        self.assertEqual(code, 2, out + err)
        self.assertIn("ERROR:", err)
        self.assertIn("missing block", out)
        self.assertIn("3 homes checked", out)

    def test_later_verification_errors_preserve_earlier_findings(self):
        real_read, real_scan = Path.read_bytes, os.scandir
        for operation in ("read", "scan"):
            with self.subTest(operation=operation):
                def read(path):
                    if operation == "read" and path == self.codex / "AGENTS.md":
                        raise PermissionError("fixture instruction read denied")
                    return real_read(path)

                def scan(path):
                    if operation == "scan" and Path(path) == self.claude / "skills":
                        raise PermissionError("fixture skill scan denied")
                    return real_scan(path)

                self.write(self.codex / "AGENTS.md", "Local rules\n")
                (self.claude / "skills").mkdir(exist_ok=True)
                with mock.patch.object(Path, "read_bytes", autospec=True, side_effect=read), \
                        mock.patch.object(os, "scandir", side_effect=scan):
                    code, out, err = self.invoke()
                self.assertEqual(code, 2, out + err)
                self.assertIn(f"REPORT: missing block: {self.claude / 'CLAUDE.md'}", out)
                self.assertIn("verification incomplete", out)
                self.assertIn("3 homes selected", out)
                self.assertNotIn("homes checked", out)
                self.assertIn(f"{1 if operation == 'read' else 4} findings", out)
                failure = "instruction read" if operation == "read" else "skill scan"
                self.assertIn(f"fixture {failure} denied", err)

    def test_documented_windows_homes_preserve_backslashes(self):
        text = (REPO / "INSTALL-AGENTS.md").read_text(encoding="utf-8")
        values = [r"C:\Users\example\.codex-extra", r"\\server\share\.codex-extra"]
        for value in values:
            with self.subTest(value=value):
                line = f"CODEX_HOME='{value}'"
                self.assertTrue(line in text, f"missing quoted example: {line}")
                self.assertEqual(shlex.split(line, comments=True), [f"CODEX_HOME={value}"])

    def test_documented_sync_command_quotes_source_paths_with_spaces(self):
        text = (REPO / "INSTALL-AGENTS.md").read_text(encoding="utf-8")
        command = re.search(r"^python3 .*scripts/sync\.py.*$", text, re.M).group()
        root = "/opt/House Rules"
        self.assertEqual(shlex.split(command.replace("<HOUSE_RULES_ROOT>", root), comments=True),
                         ["python3", f"{root}/scripts/sync.py"])

    def test_bad_configuration_and_invalid_codex_home_fail_visibly(self):
        for text in ("UNKNOWN=/example\n", 'CODEX_HOME="relative"\n', "CODEX_HOME=$(false)\n"):
            with self.subTest(text=text):
                self.write(self.root / "custom/sync.env", text)
                code, _, err = self.invoke()
                self.assertEqual(code, 2)
                self.assertIn("ERROR:", err)
        (self.root / "custom/sync.env").unlink()
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(self.home / "absent")}):
            code, _, err = self.invoke()
            self.assertEqual(code, 2)
            self.assertIn("CODEX_HOME", err)
        (self.codex / "config.toml").unlink()
        self.assertIn("not a Codex home", self.invoke()[2])

    def test_malformed_duplicate_reversed_and_mixed_markers_are_not_changed(self):
        path = self.claude / "CLAUDE.md"
        cases = ["<!-- forge:begin -->", "<!-- forge:end --><!-- forge:begin -->",
                 "<!-- forge:begin --><!-- house-rules:end -->",
                 sync.template(self.root) + sync.template(self.root)]
        for text in cases:
            with self.subTest(text=text):
                self.write(path, text)
                code, out, err = self.invoke()
                self.assertNotEqual(code, 0)
                self.assertIn("malformed or multiple", out)
                self.assertEqual(path.read_text(), text)

    def test_unrelated_files_directories_and_symlinks_are_never_overwritten(self):
        entries = [self.claude / "skills/sample", self.home / ".agents/skills/sample",
                   self.codex / "skills/sample", self.kimi / "skills/sample"]
        self.write(entries[0], "Foreign file\n")
        self.write(entries[1] / "SKILL.md", "Foreign directory\n")
        self.link(entries[2], self.home / "unrelated")
        self.link(entries[3], self.root / "skills/different-name")
        self.assert_conflicts(entries)
        self.assertEqual(entries[0].read_text(), "Foreign file\n")
        self.assertEqual((entries[1] / "SKILL.md").read_text(), "Foreign directory\n")
        self.assertEqual(os.readlink(entries[2]), str(self.home / "unrelated"))
        self.assertEqual(os.readlink(entries[3]), str(self.root / "skills/different-name"))

    def test_written_link_target_determines_ownership(self):
        path = self.claude / "skills/sample"
        target = self.root / "skills/sample"
        self.link(path, os.path.relpath(target, path.parent))
        self.assertEqual(path.resolve(), target)
        self.assertFalse(sync.owned_link(path, {str(self.root)}))
        self.assert_conflicts([path])

    def test_skill_folder_alias_into_codex_system_is_rejected(self):
        self.install_fixture()
        system = self.codex / "skills/.system"
        self.write(system / "marker", "Protected\n")
        folder = self.claude / "skills"
        folder.rename(self.claude / "original-skills")
        folder.symlink_to(system, target_is_directory=True)
        code, _, err = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("protected", err)
        self.assertFalse(sync.present(system / "sample"))
        self.assertEqual((system / "marker").read_text(), "Protected\n")

    def assert_conflicts(self, entries):
        code, out, err = self.invoke()
        self.assertEqual(code, 1, out + err)
        for entry in entries:
            self.assertIn(str(entry), out)
            self.assertTrue(sync.present(entry))

    def test_feature_branch_and_detached_head_are_not_pulled(self):
        self.git(self.root, "checkout", "-b", "work")
        self.assertIn("not main", self.invoke()[1])
        self.git(self.root, "checkout", "--detach")
        self.assertIn("detached HEAD", self.invoke()[1])

    def test_git_failure_reaches_caller(self):
        self.git(self.root, "remote", "set-url", "origin", str(self.base / "absent"))
        code, out, err = self.invoke()
        self.assertEqual(code, 2)
        self.assertIn("ERROR:", err)
        self.assertIn("missing block", out)
        self.assertIn("3 homes checked", out)
        self.assertFalse((self.claude / "CLAUDE.md").exists())

    def test_hidden_untracked_files_prevent_pull(self):
        self.git(self.root, "config", "status.showUntrackedFiles", "no")
        self.write(self.root / "hidden-untracked", "fixture")
        with mock.patch.object(sync, "git", wraps=sync.git) as calls:
            code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        self.assertIn("dirty", out)
        self.assertFalse(any(call.args[1] in ("pull", "merge") for call in calls.call_args_list))

    def changed_during_fetch(self, mutation):
        self.write(self.origin / "remote", "fixture")
        self.commit(self.origin, ["remote"])
        real_git = sync.git

        def git(root, *args):
            result = real_git(root, *args)
            if "fetch" in args:
                if mutation == "dirty":
                    self.write(self.root / "dirty", "fixture")
                elif mutation == "branch":
                    self.git(self.root, "checkout", "-b", "other")
                else:
                    self.git(self.root, "commit", "--allow-empty", "-m", "Concurrent edit")
            return result

        with mock.patch.object(sync, "git", side_effect=git) as calls:
            code, out, err = self.invoke()
        self.assertEqual(code, 1, out + err)
        self.assertIn("changed during update", out)
        self.assertFalse(any(call.args[1] in ("pull", "merge") for call in calls.call_args_list))

    def test_rechecks_cleanliness_after_fetch(self):
        self.changed_during_fetch("dirty")

    def test_rechecks_branch_after_fetch(self):
        self.changed_during_fetch("branch")

    def test_rechecks_revision_after_fetch(self):
        self.changed_during_fetch("revision")

    def test_rechecks_before_pull(self):
        self.write(self.origin / "remote", "fixture")
        self.commit(self.origin, ["remote"])
        real_git = sync.git

        def git(root, *args):
            result = real_git(root, *args)
            if "rev-list" in args:
                self.write(self.root / "concurrent-untracked", "fixture")
            return result

        with mock.patch.object(sync, "git", side_effect=git) as calls:
            code, out, err = self.invoke()
        self.assertEqual(code, 1, out + err)
        self.assertFalse(any(call.args[1] in ("pull", "merge") for call in calls.call_args_list))

    def test_named_home_instruction_duplicates_are_reported(self):
        self.install_fixture()
        for name in ("AGENTS.md", "CLAUDE.md"):
            with self.subTest(name=name):
                path = self.home / name
                self.write(path, "Local rules\n<!-- forge:begin -->old<!-- forge:end -->")
                before = path.read_bytes()
                code, out, err = self.invoke()
                self.assertEqual(code, 1, out + err)
                self.assertIn("duplicate", out)
                self.assertIn(str(path), out)
                self.assertEqual(path.read_bytes(), before)
                path.unlink()

    def test_source_status_errors_preserve_installed_links(self):
        self.install_fixture()
        real_stat = Path.stat
        real_is_dir, real_is_file = Path.is_dir, Path.is_file
        for denied in (self.root / "skills/sample", self.root / "skills/sample/SKILL.md"):
            with self.subTest(denied=denied):
                def stat(path, *args, **kwargs):
                    if path == denied:
                        raise PermissionError("source status unavailable")
                    return real_stat(path, *args, **kwargs)

                # Model Python 3.14's error-suppressing predicates on older Python too.
                def predicate(method):
                    return lambda path: False if path == denied else method(path)

                with mock.patch.object(Path, "stat", autospec=True, side_effect=stat), \
                        mock.patch.object(Path, "is_dir", autospec=True,
                                          side_effect=predicate(real_is_dir)), \
                        mock.patch.object(Path, "is_file", autospec=True,
                                          side_effect=predicate(real_is_file)):
                    code, _, err = self.invoke()
                self.assertEqual(code, 2, err)
                self.assertIn("source status unavailable", err)
                self.assertTrue((self.claude / "skills/sample").is_symlink())

    def test_broken_default_homes_are_visible(self):
        self.claude.rmdir()
        for dangling in (False, True):
            with self.subTest(dangling=dangling):
                if dangling:
                    self.link(self.claude, self.home / "absent")
                else:
                    self.write(self.claude, "not a directory")
                try:
                    code, _, err = self.invoke()
                    self.assertEqual(code, 2, err)
                    self.assertIn(str(self.claude), err)
                finally:
                    self.claude.unlink()

    def test_report_disables_optional_git_locks(self):
        real_run = subprocess.run

        def run(command, **kwargs):
            if command[0] == "git":
                self.assertTrue("--no-optional-locks" in command or
                                kwargs.get("env", {}).get("GIT_OPTIONAL_LOCKS") == "0")
            return real_run(command, **kwargs)

        with mock.patch.object(subprocess, "run", side_effect=run):
            sync.update(self.root)

    def install_fixture(self):
        for key, home in sync.homes(self.root, self.home):
            instruction = sync.instruction_file(key, home)
            self.write(instruction, sync.template(self.root) + "\n")
        for folder in (self.claude / "skills", self.home / ".agents/skills"):
            path = folder / "sample"
            if not path.is_symlink():
                self.link(path, self.root / "skills/sample")

    def test_missing_links_stale_and_missing_blocks_are_reported_without_writes(self):
        original = "Operator rules\n<!-- house-rules:begin -->\nstale\n<!-- house-rules:end -->\nTail\n"
        self.write(self.claude / "CLAUDE.md", original)
        self.write(self.codex / "AGENTS.md", "Codex rules\n")
        before = sorted(str(path.relative_to(self.home)) for path in self.home.rglob("*"))
        code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        for reason in ("stale block", "missing block", "missing or stale skill link"):
            self.assertIn(reason, out)
        self.assertFalse((self.root / "custom").exists())
        self.assertEqual(before, sorted(str(path.relative_to(self.home)) for path in self.home.rglob("*")))
        self.assertEqual((self.claude / "CLAUDE.md").read_text(), original)
        self.assertEqual((self.codex / "AGENTS.md").read_text(), "Codex rules\n")

    def test_manual_installation_is_clean_on_repeated_runs_without_receipts(self):
        self.install_fixture()
        for _ in range(2):
            code, out, err = self.invoke()
            self.assertEqual(code, 0, out + err)
            self.assertIn("3 homes checked; 0 findings", out)
            self.assertFalse((self.root / "custom").exists())

    def test_extra_homes_are_only_checked_when_configured(self):
        self.install_fixture()
        extra = self.home / "extra codex"
        self.write(extra / "config.toml", "# fixture\n")
        self.assertEqual(self.invoke()[0], 0)
        self.write(self.root / "custom/sync.env", f'CODEX_HOME="{extra}" # extra\n')
        code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        self.assertIn(str(extra / "AGENTS.md"), out)
        self.assertIn("4 homes checked", out)
        self.assertFalse((extra / "AGENTS.md").exists())
        self.write(extra / "AGENTS.md", sync.template(self.root))
        self.assertEqual(self.invoke()[0], 0)

    def test_extra_claude_and_kimi_homes_and_environment_defaults(self):
        extra_claude, extra_kimi = self.home / "claude extra", self.home / "kimi extra"
        extra_claude.mkdir()
        extra_kimi.mkdir()
        self.write(self.root / "custom/sync.env",
                   f'CLAUDE_CONFIG_DIR="{extra_claude}"\nKIMI_CODE_HOME="{extra_kimi}"\n')
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(extra_claude)}):
            code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        for path in (extra_claude / "CLAUDE.md", extra_claude / "skills/sample",
                     extra_kimi / "AGENTS.md"):
            self.assertIn(str(path), out)
            self.assertFalse(path.exists())
        self.assertNotIn(str(self.claude), out)

    def test_override_and_instruction_symlink_are_checked_without_writes(self):
        self.install_fixture()
        target = self.home / "instructions.md"
        self.write(target, "Local rules\n")
        (self.codex / "AGENTS.override.md").symlink_to(target)
        self.write(self.codex / "AGENTS.md", "Inactive rules\n")
        code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        self.assertIn(str(self.codex / "AGENTS.override.md"), out)
        self.assertNotIn(str(self.codex / "AGENTS.md"), out)
        self.assertTrue((self.codex / "AGENTS.override.md").is_symlink())
        self.assertEqual(target.read_text(), "Local rules\n")
        self.assertEqual((self.codex / "AGENTS.md").read_text(), "Inactive rules\n")
        self.write(target, "Local rules\n" + sync.template(self.root))
        self.assertEqual(self.invoke()[0], 0)

    def test_shared_instruction_target_is_reported_for_every_home(self):
        self.install_fixture()
        target, alias = self.codex / "AGENTS.md", self.kimi / "AGENTS.md"
        alias.unlink()
        alias.symlink_to(target)
        self.write(target, "Shared rules\n")
        code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        for path in (target, alias):
            self.assertIn(f"missing block: {path}", out)
        self.assertEqual(target.read_text(), "Shared rules\n")
        self.assertTrue(alias.is_symlink())

    def test_legacy_markers_are_reported_without_changing_surrounding_bytes(self):
        for family in ("forge", "groundwork"):
            with self.subTest(family=family):
                path = self.claude / "CLAUDE.md"
                original = f"Before\r\n<!-- {family}:begin -->\r\nold\r\n<!-- {family}:end -->\r\nAfter\r\n"
                path.write_bytes(original.encode())
                path.chmod(0o640)
                code, out, err = self.invoke()
                self.assertEqual(code, 1, err)
                self.assertIn(f"stale block: {path}", out)
                self.assertEqual(path.read_bytes(), original.encode())
                self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_owned_removed_and_shadowing_links_are_reported_and_system_is_excluded(self):
        self.install_fixture()
        removed = self.home / ".agents/skills/removed"
        shadow = self.codex / "skills/sample"
        kimi_shadow = self.kimi / "skills/sample"
        self.link(removed, self.root / "skills/removed")
        self.link(shadow, self.root / "skills/sample")
        self.link(kimi_shadow, self.root / "skills/sample")
        system = self.codex / "skills/.system"
        self.write(system / "sample/SKILL.md", "Protected\n")
        self.link(system / "removed", self.root / "skills/removed")
        code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        self.assertIn(f"removed skill: {removed}", out)
        for path in (shadow, kimi_shadow):
            self.assertIn(f"shadowing skill: {path}", out)
        for path in (removed, shadow, kimi_shadow, system / "removed"):
            self.assertTrue(path.is_symlink())
        self.assertEqual((system / "sample/SKILL.md").read_text(), "Protected\n")
        self.assertNotIn(str(system), out)

    def test_prior_receipt_roots_identify_owned_stale_and_removed_links(self):
        old = self.base / "previous-source"
        stale, removed = self.claude / "skills/sample", self.claude / "skills/removed"
        self.link(stale, old / "skills/sample")
        self.link(removed, old / "skills/removed")
        self.receipt({"source_root": str(old)})
        receipt = self.root / "custom/installations/fixture.json"
        before = receipt.read_bytes()
        code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        self.assertIn(f"missing or stale skill link: {stale}", out)
        self.assertIn(f"removed skill: {removed}", out)
        self.assertEqual(os.readlink(stale), str(old / "skills/sample"))
        self.assertEqual(receipt.read_bytes(), before)
        self.assertFalse((self.root / "custom/backups").exists())

    def test_alias_skill_folders_are_checked_for_both_scan_roles(self):
        self.install_fixture()
        folder = self.codex / "skills"
        folder.symlink_to(self.home / ".agents/skills", target_is_directory=True)
        code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        self.assertIn(f"shadowing skill: {folder / 'sample'}", out)
        self.assertTrue((self.home / ".agents/skills/sample").is_symlink())

    def test_stale_written_link_through_source_alias_is_reported(self):
        self.install_fixture()
        old = self.base / "old-source"
        self.link(old, self.root)
        path = self.claude / "skills/sample"
        path.unlink()
        self.link(path, old / "skills/sample")
        self.receipt({"previous_roots": [str(old)]})
        code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        self.assertIn(f"missing or stale skill link: {path}", out)
        self.assertEqual(os.readlink(path), str(old / "skills/sample"))

    def test_dirty_checkout_is_reported_and_never_pulled(self):
        self.write(self.root / "untracked", "dirty\n")
        with mock.patch.object(sync, "git", wraps=sync.git) as calls:
            code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        self.assertIn("dirty", out)
        self.assertFalse(any(call.args[1] in ("pull", "merge") for call in calls.call_args_list))
        self.assertIn("3 homes checked", out)

    def test_diverged_and_ahead_checkouts_are_reported_and_never_pulled(self):
        self.write(self.root / "local", "local\n")
        self.commit(self.root, ["local"])
        self.assertIn("ahead", self.invoke()[1])
        self.write(self.origin / "remote", "remote\n")
        self.commit(self.origin, ["remote"])
        with mock.patch.object(sync, "git", wraps=sync.git) as calls:
            code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        self.assertIn("diverged", out)
        self.assertFalse(any(call.args[1] in ("pull", "merge") for call in calls.call_args_list))

    def test_receipt_and_skill_scan_errors_reach_caller(self):
        directory = self.root / "custom/installations"
        directory.mkdir(parents=True)
        real_scan = os.scandir
        for denied in (directory, self.root / "skills", self.claude / "skills"):
            denied.mkdir(exist_ok=True)
            with self.subTest(denied=denied):
                def scan(path):
                    if Path(path) == denied:
                        raise PermissionError("fixture scan denied")
                    return real_scan(path)
                with mock.patch.object(os, "scandir", side_effect=scan):
                    code, _, err = self.invoke()
                self.assertEqual(code, 2, err)
                self.assertIn("fixture scan denied", err)

    def test_malformed_receipt_roots_fail_visibly(self):
        for data in ([], {"previous_roots": None}, {"previous_roots": "not a list"},
                     {"source_root": "relative"}, {"previous_roots": [1]}):
            with self.subTest(data=data):
                self.receipt(data)
                code, _, err = self.invoke()
                self.assertEqual(code, 2, err)
                self.assertIn("fixture.json", err)

    def test_dangling_instruction_link_is_reported_without_replacing_it(self):
        path = self.codex / "AGENTS.override.md"
        self.link(path, self.home / "missing-target")
        code, out, err = self.invoke()
        self.assertEqual(code, 1, err)
        self.assertIn(f"instruction symlink has no regular target: {path}", out)
        self.assertTrue(path.is_symlink())

    def specialist(self, key="SPECIALIST_CODEX_HOME"):
        path = self.base / key
        self.write(path / "config.toml", "project_doc_max_bytes = 0\n")
        self.write(self.root / "custom/sync.env", f'{key}="{path}"\n')
        return path

    def test_specialist_keys_parse_and_stay_out_of_normal_installation_checks(self):
        self.install_fixture()
        codex = self.specialist()
        kimi = self.base / "specialist-kimi"
        kimi.mkdir()
        with (self.root / "custom/sync.env").open("a") as config:
            config.write(f'SPECIALIST_KIMI_CODE_HOME="{kimi}"\n')
        # Normal user skills must be explicitly disabled even outside the tool home.
        with (codex / "config.toml").open("a") as config:
            config.write(f'[[skills.config]]\npath = "{self.home / ".agents/skills/sample/SKILL.md"}"\nenabled = false\n')
        selected = sync.homes(self.root, self.home)
        self.assertIn(("SPECIALIST_CODEX_HOME", codex), selected)
        self.assertIn(("SPECIALIST_KIMI_CODE_HOME", kimi), selected)
        self.assertFalse(any(folder.is_relative_to(codex) or folder.is_relative_to(kimi)
                             for folder, _ in sync.skill_folders(selected, self.home)))
        findings = []
        sync.verify(self.root, self.home, findings, [])
        self.assertEqual(findings, [])
        self.assertFalse((codex / "AGENTS.md").exists())
        self.assertFalse((kimi / "skills").exists())

    def test_conflicting_specialist_normal_home_aliases_are_rejected(self):
        alias = self.base / "codex-alias"
        alias.symlink_to(self.codex, target_is_directory=True)
        self.write(self.root / "custom/sync.env", f'SPECIALIST_CODEX_HOME="{alias}"\n')
        with self.assertRaisesRegex(ValueError, "both specialist and normal"):
            sync.homes(self.root, self.home)

    def test_specialist_home_inside_checkout_is_rejected(self):
        path = self.root / "custom/specialist"
        self.write(path / "config.toml", "project_doc_max_bytes = 0\n")
        self.write(self.root / "custom/sync.env", f'SPECIALIST_CODEX_HOME="{path}"\n')
        with self.assertRaisesRegex(ValueError, "outside.*checkout"):
            sync.homes(self.root, self.home)

    def test_specialist_checks_report_all_instruction_files_regardless_of_brand(self):
        path = self.specialist()
        for name, text in (("AGENTS.md", "Unbranded operator instructions"),
                           ("AGENTS.override.md", "<!-- forge:begin -->rules")):
            self.write(path / name, text)
        findings = []
        sync.specialist_findings(self.root, self.home, "SPECIALIST_CODEX_HOME", path, findings)
        for name in ("AGENTS.md", "AGENTS.override.md"):
            self.assertTrue(any(str(path / name) in finding for finding in findings))

    def test_specialist_checks_report_installed_and_enabled_skills_from_any_source(self):
        path = self.specialist()
        self.write(path / "skills/third-party/SKILL.md", "third party")
        self.write(self.home / ".agents/skills/change-review/SKILL.md", "new skill")
        self.write(path / "skills/.system/builtin/SKILL.md", "built in skill")
        findings = []
        sync.specialist_findings(self.root, self.home, "SPECIALIST_CODEX_HOME", path, findings)
        for name in ("third-party", "change-review", "builtin"):
            self.assertTrue(any(name in finding for finding in findings), findings)
        self.assertTrue(any("missing disable entry" in finding for finding in findings))

    def test_specialist_nonzero_project_limit_and_enabled_config_entries_are_reported(self):
        path = self.specialist()
        extra = self.base / "external-skill"
        self.write(extra / "SKILL.md", "external")
        self.write(path / "config.toml", f'project_doc_max_bytes = 100\n[[skills.config]]\npath = "{extra}"\nenabled = true\n')
        findings = []
        sync.specialist_findings(self.root, self.home, "SPECIALIST_CODEX_HOME", path, findings)
        self.assertTrue(any("project_doc_max_bytes" in finding for finding in findings))
        self.assertTrue(any(str(extra) in finding for finding in findings))

    def test_specialist_disabled_alias_is_resolved_and_blank_instructions_are_allowed(self):
        path = self.specialist()
        skill = self.home / ".agents/skills/third-party"
        self.write(skill / "SKILL.md", "third party")
        alias = self.base / "skill-alias"
        alias.symlink_to(skill, target_is_directory=True)
        self.write(path / "config.toml", f"project_doc_max_bytes = 0\n[[skills.config]]\npath = '{alias / 'SKILL.md'}'\nenabled = false\n")
        self.write(path / "AGENTS.md", " \n")
        findings = []
        sync.specialist_findings(self.root, self.home, "SPECIALIST_CODEX_HOME", path, findings)
        self.assertEqual(findings, [])

    def test_specialist_directory_selector_does_not_disable_native_document(self):
        path = self.specialist()
        skill = self.home / ".agents/skills/extra"
        self.write(skill / "SKILL.md", "third party")
        self.write(path / "config.toml", f'project_doc_max_bytes = 0\n[[skills.config]]\npath = "{skill}"\nenabled = false\n')
        findings = []
        sync.specialist_findings(self.root, self.home, "SPECIALIST_CODEX_HOME", path, findings)
        self.assertTrue(any(str(skill / "SKILL.md") in finding for finding in findings), findings)

    def test_alternate_isolation_table_headers_refuse_visibly(self):
        path = self.specialist()
        for header in ('[[ skills.config ]]', '[["skills"."config"]]', "[['skills'.'config']]", '[skills]', '[ "skills" ]', r'[["ski\u006cls"."config"]]'):
            with self.subTest(header=header):
                self.write(path / "config.toml", f'project_doc_max_bytes = 0\n{header}\npath = "/synthetic/SKILL.md"\nenabled = true\n')
                with self.assertRaisesRegex(ValueError, "unsupported skills.config table header"):
                    sync.codex_specialist_config(path / "config.toml")

    def test_kimi_shared_user_instructions_are_checked_outside_tool_home(self):
        path = self.specialist("SPECIALIST_KIMI_CODE_HOME")
        shared = self.home / ".agents/AGENTS.md"
        self.write(shared, "shared synthetic instructions")
        findings = []
        sync.specialist_findings(self.root, self.home, "SPECIALIST_KIMI_CODE_HOME", path, findings)
        self.assertTrue(any(str(shared) in finding for finding in findings), findings)

    def test_synthetic_specialist_fixture_does_not_scan_administrative_skills(self):
        path = self.specialist()
        original = sync.status

        def deny_admin(candidate, **kwargs):
            if candidate == Path("/etc/codex/skills"):
                raise PermissionError("synthetic administrative skills must not be read")
            return original(candidate, **kwargs)

        findings = []
        with mock.patch.object(sync, "status", side_effect=deny_admin):
            sync.specialist_findings(self.root, self.home, "SPECIALIST_CODEX_HOME", path, findings)
        self.assertEqual(findings, [])

    def test_specialist_malformed_disable_entries_fail_visibly(self):
        path = self.specialist()
        self.write(path / "config.toml", 'project_doc_max_bytes = 0\n[[skills.config]]\nenabled = false\n')
        with self.assertRaisesRegex(ValueError, "skills.config"):
            sync.specialist_findings(self.root, self.home, "SPECIALIST_CODEX_HOME", path, [])

    def test_specialist_config_instruction_sources_are_reported(self):
        path = self.specialist()
        for setting in ("developer_instructions", "model_instructions_file"):
            self.write(path / "config.toml", f'project_doc_max_bytes = 0\n{setting} = "additional instructions"\n')
            findings = []
            sync.specialist_findings(self.root, self.home, "SPECIALIST_CODEX_HOME", path, findings)
            self.assertTrue(any(setting in finding for finding in findings), findings)

    def test_kimi_home_rejects_additional_agent_and_plugin_sources(self):
        path = self.specialist("SPECIALIST_KIMI_CODE_HOME")
        self.write(path / "agents/extra.yaml", "task instructions")
        self.write(path / "plugins/extra/SKILL.md", "plugin skill")
        findings = []
        sync.specialist_findings(self.root, self.home, "SPECIALIST_KIMI_CODE_HOME", path, findings)
        for folder in ("agents", "plugins"):
            self.assertTrue(any(str(path / folder) in finding for finding in findings), findings)


class PointerTemplateTests(unittest.TestCase):
    EXPECTED_BLOCK = """<!-- house-rules:begin -->
# Shared operating foundation (House Rules)

At session start and after every context compaction or reset, read `<HOUSE_RULES_ROOT>/INDEX.md`.
It is the index for collaboration, verification, autonomy, and durable
execution rules. Load the rule files and Skills that its conditions select.
Repository-local rules supply project details and win over shared preferences; all work remains subject to the host's instruction hierarchy
and access controls.

Load only the House Rules Skills relevant to the task. Use
`<HOUSE_RULES_ROOT>/STRUCTURE.md` when deciding artifact paths and naming. Keep
model, permission, MCP, plugin, and hook configuration in the native tool
settings.
<!-- house-rules:end -->"""

    def test_parent_folder_cleanup_preserves_house_rules_repository_pointer(self):
        installer = (REPO / 'INSTALL-AGENTS.md').read_text()
        cleanup = installer.split('5. Put ', 1)[1].split('6. Preserve ', 1)[0]
        self.assertIn('remove such a block instead of migrating it.', cleanup)
        self.assertIn('Preserve `<HOUSE_RULES_ROOT>/AGENTS.md`, the canonical repository '
                      'pointer,\n   even when the House Rules checkout is a parent folder.',
                      cleanup)

    def test_global_discovery_requires_neutral_directory_before_counting_headings(self):
        installer = (REPO / 'INSTALL-AGENTS.md').read_text()
        verification = installer.split('Runtime verification:\n', 1)[1].split(
            'Report filesystem and runtime verification separately.', 1)[0]
        setup, checks = verification.split('1. Prefer discovery views', 1)
        self.assertIn('Run global-installation discovery verification from a neutral '
                      'working directory\noutside any repository.', setup)
        self.assertIn('Check that neither it nor any parent folder contains\n'
                      'instruction files such as `AGENTS.md` or `CLAUDE.md`.', setup)
        self.assertIn('exactly one `Shared operating foundation (House Rules)` heading',
                      checks)

    def test_installed_pointer_keeps_old_wording_with_renamed_index(self):
        self.assertEqual(sync.template(REPO), self.EXPECTED_BLOCK.replace(
            '<HOUSE_RULES_ROOT>', str(REPO)))

    def test_house_rules_pointer_keeps_portable_old_wording(self):
        self.assertEqual((REPO / 'AGENTS.md').read_text().strip(),
                         self.EXPECTED_BLOCK.replace('<HOUSE_RULES_ROOT>/', '').replace(
                             "read `INDEX.md`.\n",
                             "read `INDEX.md`.\n`INDEX.md` sits in the same folder as this file.\n"))

    def test_managed_repository_keeps_three_line_loader(self):
        structure = (REPO / 'STRUCTURE.md').read_text()
        loader = structure.split('```markdown\n', 1)[1].split('```', 1)[0]
        self.assertEqual(loader, '# AGENTS.md\n'
                         'This repository is managed by [House Rules](<House Rules URL>). '
                         'Read House Rules `INDEX.md` first and follow it.\n'
                         "This repository's own rules are in [.agents/rules.md](.agents/rules.md).\n")
        self.assertIn('A managed repository uses exactly this `AGENTS.md`:', structure)
        self.assertIn('A managed repository without its own rules omits the third line.', structure)

    def test_preferences_changes_only_index_filename(self):
        self.assertIn('These stack defaults apply whenever House Rules is installed. '
                      'Overrides follow INDEX.md,\n'
                      'and an existing coherent project stack also takes precedence over them.',
                      (REPO / 'PREFERENCES.md').read_text())

    def test_transcript_gaps_changes_only_index_filename(self):
        self.assertIn('Read the batch,\n'
                      'INDEX.md, all rule, skill and prompt files, and the configured '
                      'decisions file in full.',
                      (REPO / 'prompts/util/transcript-gaps.md').read_text())


if __name__ == "__main__":
    unittest.main()
