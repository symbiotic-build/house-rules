#!/usr/bin/env python3
"""Launcher contract tests using synthetic executables, homes and canary records."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import signal
import time
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = Path(__file__).with_name("specialist.py")


class SpecialistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="specialist-test-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.workdir = self.base / "checkout"
        self.workdir.mkdir()
        self.root = self.base / "rules"
        self.root.mkdir()
        self.user = self.base / "user"
        self.user.mkdir()
        self.home = self.base / "specialist-home"
        self.home.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.calls = self.base / "calls.jsonl"
        self.pack = self.base / "pack.txt"
        self.manifest = self.base / "manifest.json"
        self.out = self.base / "answer.txt"
        self.qualification = self.base / "canary.json"
        self.data = b"House Rules revision: " + b"a" * 40 + b"\n\nRequired skill text\r\nTask\n\n"
        self.pack.write_bytes(self.data)
        self.manifest.write_text(json.dumps({"house_rules_revision": "a" * 40,
            "files": [], "pack": {"sha256": hashlib.sha256(self.data).hexdigest()}}))
        self.env = {**os.environ, "HOME": str(self.user), "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                    "FAKE_CALLS": str(self.calls), "FAKE_DEBUG": "[]",
                    "FAKE_ADMIN_SKILLS": str(self.base / "administrative-skills")}
        for key in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "KIMI_CODE_HOME"):
            self.env[key] = str(self.base / ("normal-" + key))
            Path(self.env[key]).mkdir()
        (Path(self.env["CODEX_HOME"]) / "config.toml").write_text("# normal test home\n")
        # The test process only executes these files, never an installed model CLI.
        fake = '''#!{python}
import json, os, pathlib, sys
tool = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if args == ["--version"]:
    if os.environ.get("FAKE_MUTATE_MCP"):
        pathlib.Path(os.environ["FAKE_MUTATE_MCP"]).write_text("changed original mcp")
    print(tool + " fixture-1")
    sys.exit(0)
if args[:2] == ["debug", "prompt-input"]:
    if any(flag in args for flag in ("-s", "-C", "-m")):
        print("unsupported debugger execution flag", file=sys.stderr)
        sys.exit(2)
    with open(os.environ["FAKE_CALLS"] + ".debug", "a") as f:
        f.write(json.dumps({{"args":args,"home":os.environ["CODEX_HOME"],"cwd":os.getcwd(),
                            "config":pathlib.Path(os.environ["CODEX_HOME"], "config.toml").read_text()}}) + "\\n")
    if os.environ.get("FAKE_MUTATE_HOME"):
        pathlib.Path(os.environ["FAKE_MUTATE_HOME"]).write_text("changed original config")
    if os.environ.get("FAKE_ADD_SKILL"):
        skill = pathlib.Path(os.environ["FAKE_ADD_SKILL"])
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("skill added after clean capture")
    print(os.environ["FAKE_DEBUG"])
    sys.exit(int(os.environ.get("FAKE_DEBUG_EXIT", "0")))
data = sys.stdin.buffer.read() if tool != "kimi" else args[args.index("-p") + 1].encode()
with open(os.environ["FAKE_CALLS"], "a") as f:
    f.write(json.dumps({{"tool":tool, "args":args, "pack":data.hex(), "cwd":os.getcwd(),
                        "mcp":pathlib.Path(args[args.index("--mcp-config") + 1]).read_text() if "--mcp-config" in args else None,
                        "config":pathlib.Path(os.environ["CODEX_HOME"], "config.toml").read_text() if tool == "codex" else None,
                        "home":os.environ.get("CODEX_HOME" if tool == "codex" else "KIMI_CODE_HOME")}}) + "\\n")
if os.environ.get("FAKE_TREE"):
    import subprocess, time
    handle = os.open(os.environ["FAKE_HEARTBEAT"], os.O_WRONLY)
    grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(4)"], pass_fds=(handle,))
    pathlib.Path(os.environ["FAKE_TREE"]).write_text(json.dumps([os.getpid(), grandchild.pid]))
    time.sleep(4)
if tool == "claude":
    print(os.environ.get("FAKE_INIT", json.dumps({{"type":"system", "subtype":"init",
          "cwd":os.getcwd(), "session_id":"synthetic-session", "tools":[], "mcp_servers":[],
          "model":"fixture", "permissionMode":"acceptEdits", "claude_code_version":"fixture-1",
          "agents":[], "skills":[], "plugins":[]}})), flush=True)
    if os.environ.get("FAKE_BLOCK"):
        import time
        time.sleep(10)
    print(json.dumps({{"type":"result", "subtype":"success", "is_error":False, "result":"answer\\n"}}))
elif tool == "codex":
    pathlib.Path(args[args.index("-o") + 1]).write_text("answer\\n")
else:
    print("answer")
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
'''.format(python=sys.executable)
        for tool in ("codex", "claude", "kimi"):
            path = self.bin / tool
            path.write_text(fake)
            path.chmod(0o755)

    def register(self, tool):
        (self.root / "custom").mkdir(exist_ok=True)
        (self.root / "custom/sync.env").write_text(
            f'SPECIALIST_{"CODEX_HOME" if tool == "codex" else "KIMI_CODE_HOME"}="{self.home}"\n')
        (self.home / "config.toml").write_text("project_doc_max_bytes = 0\n")
        if tool == "codex":
            (self.home / "auth.json").write_text("{}")
        else:
            (self.home / "credentials").mkdir(exist_ok=True)
            (self.home / "credentials/kimi-code.json").write_text("{}")

    def qualify(self, tool, mode="rw", prevention=None, mcp=None):
        # Canary artifacts are existing evidence, not a launcher-owned cache.
        log = self.base / "canary.log"
        log.write_text("Synthetic isolation and write-denial evidence\n")
        config = self.home / "config.toml"
        record = {"tool": tool, "version": tool + " fixture-1", "mode": mode,
                  "home": str(self.home) if tool != "claude" else None,
                  "workdir": str(self.workdir), "isolation": True,
                  "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest() if tool != "claude" else None,
                  "evidence": {"path": str(log), "sha256": hashlib.sha256(log.read_bytes()).hexdigest()},
                  "write_prevention": prevention, "codex_prompt_input": [],
                  "claude_init_contract": {"skills": "required-empty", "memory_paths": "optional-empty"},
                  "write_test": {"baseline_allowed": True, "denied": True, "write_absent": True},
                  "mcp_sha256": hashlib.sha256(mcp.read_bytes()).hexdigest() if mcp else None,
                  "mcp_isolated": bool(mcp), "mcp_tool_succeeded": bool(mcp), "kimi_start": "empty"}
        self.qualification.write_text(json.dumps(record))
        return record

    def invoke(self, tool="claude", mode="rw", qualify=False, extra=(), readonly_mount=False,
               start=False, tracked=True, parent_exit=False):
        args = [sys.executable, "-B", str(LAUNCHER), "--root", str(self.root), "--tool", tool,
                "--pack", str(self.pack), "--manifest", str(self.manifest), "--workdir", str(self.workdir),
                "--mode", mode, "--out", str(self.out), *extra]
        if qualify:
            args += ["--qualification", str(self.qualification)]
        read_fd, write_fd = os.pipe()
        self.addCleanup(os.close, write_fd)
        self.addCleanup(os.close, read_fd)
        if tracked:
            args += ["--parent-fd", str(read_fd)]
        if readonly_mount:
            self.env["FAKE_READONLY_MOUNT"] = "1"
        driver = """
import importlib.util, sys, os
from pathlib import Path
from unittest import mock
spec = importlib.util.spec_from_file_location("tested_specialist", sys.argv[1])
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
if os.environ.get("FAKE_READONLY_MOUNT"):
    launcher.os.statvfs = lambda path: mock.Mock(f_flag=os.ST_RDONLY)
original = launcher.sync.discover_skills
with mock.patch.object(launcher.sync, "discover_skills", side_effect=lambda folder, *args, **kwargs:
                       original(Path(os.environ["FAKE_ADMIN_SKILLS"]) if folder == Path("/etc/codex/skills")
                                else folder, *args, **kwargs)):
    sys.exit(launcher.main(sys.argv[2:]))
"""
        command = [sys.executable, "-B", "-c", driver, str(LAUNCHER), *args[3:]]
        if parent_exit:
            parent_driver = """
import json, os, subprocess, sys, time
command = json.loads(sys.argv[1])
read_fd, write_fd = os.pipe()
command[command.index("--parent-fd") + 1] = str(read_fd)
child = subprocess.Popen(command, pass_fds=(read_fd,))
os.close(read_fd)
deadline = time.monotonic() + 2
while not os.path.exists(os.environ["FAKE_TREE"]) and time.monotonic() < deadline:
    time.sleep(0.01)
if not os.path.exists(os.environ["FAKE_TREE"]):
    child.terminate()
    child.wait(timeout=2)
    sys.exit(1)
os._exit(0)  # The tracked parent exits with its lifetime pipe still open.
"""
            command = [sys.executable, "-B", "-c", parent_driver, json.dumps(command)]
        if start:
            child = subprocess.Popen(command, env=self.env, pass_fds=(read_fd,),
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.addCleanup(self.stop_child, child)
            return child, write_fd
        return subprocess.run(command, env=self.env, pass_fds=(read_fd,), capture_output=True, timeout=5)

    @staticmethod
    def stop_child(child):
        if child.poll() is None:
            child.terminate()
        child.communicate(timeout=2)

    def called(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def refused(self, result, check):
        self.assertEqual(result.returncode, 2, result.stderr.decode())
        self.assertIn(check, result.stderr.decode())
        self.assertEqual(self.called(), [])
        self.assertFalse(self.out.exists())

    def test_missing_and_mismatched_headers_refuse_before_model_call(self):
        for data in (b"Task\n", self.data.replace(b"a" * 40, b"b" * 40)):
            with self.subTest(data=data):
                self.pack.write_bytes(data)
                self.refused(self.invoke(), "header")

    def test_hash_mismatch_refuses_before_model_call(self):
        self.pack.write_bytes(self.data + b"changed")
        self.refused(self.invoke(), "hash")

    def test_manifest_requires_files_and_revision(self):
        for key in ("files", "house_rules_revision", "pack"):
            record = json.loads(self.manifest.read_text())
            record.pop(key)
            self.manifest.write_text(json.dumps(record))
            self.refused(self.invoke(), "manifest")
            self.set_manifest()

    def set_manifest(self):
        self.manifest.write_text(json.dumps({"house_rules_revision": "a" * 40, "files": [],
                                           "pack": {"sha256": hashlib.sha256(self.data).hexdigest()}}))

    def test_missing_registered_homes_and_login_state_refuse(self):
        for tool in ("codex", "kimi"):
            with self.subTest(tool=tool):
                self.refused(self.invoke(tool), "registered")
        self.register("codex")
        (self.home / "auth.json").unlink()
        self.refused(self.invoke("codex"), "login")

    def test_branded_and_unbranded_global_instructions_refuse(self):
        self.register("codex")
        self.qualify("codex")
        for name in ("AGENTS.md", "AGENTS.override.md"):
            for text in ("Operator task instructions", "<!-- house-rules:begin -->rules", "<!-- forge:begin -->rules", "<!-- groundwork:begin -->rules"):
                with self.subTest(name=name, text=text):
                    path = self.home / name
                    path.write_text(text)
                    self.refused(self.invoke("codex", qualify=True), str(path))
                    path.unlink()

    def test_enabled_third_party_and_new_skills_need_disable_entries(self):
        self.register("codex")
        self.qualify("codex")
        for name in ("third-party", "change-review"):
            path = self.user / ".agents/skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text("skill")
            self.refused(self.invoke("codex", qualify=True), str(path.parent))

    def test_codex_debug_rejects_instruction_and_skill_messages_from_any_source(self):
        self.register("codex")
        self.qualify("codex")
        for text in ("Unbranded task instructions", "## Skills\nthird-party", "Project rules"):
            self.env["FAKE_DEBUG"] = json.dumps([{"type": "message", "role": "developer", "content": [{"type":"input_text", "text":text}]}])
            self.refused(self.invoke("codex", qualify=True), "prompt-input")

    def test_codex_debug_failure_and_unknown_format_refuse(self):
        self.register("codex")
        self.qualify("codex")
        for value in ("not json", "{}"):
            self.env["FAKE_DEBUG"] = value
            self.refused(self.invoke("codex", qualify=True), "prompt-input")
        self.env["FAKE_DEBUG"] = "[]"
        self.env["FAKE_DEBUG_EXIT"] = "7"
        self.refused(self.invoke("codex", qualify=True), "prompt-input")

    def test_read_only_without_qualified_write_prevention_refuses_every_tool(self):
        for tool in ("codex", "claude", "kimi"):
            with self.subTest(tool=tool):
                if tool != "claude":
                    self.register(tool)
                self.qualify(tool, "ro", "prompt")
                self.refused(self.invoke(tool, "ro", True), "write prevention")

    def test_unqualified_isolation_and_stale_versions_refuse(self):
        self.register("kimi")
        self.refused(self.invoke("kimi"), "runtime instruction discovery")
        self.register("codex")
        record = self.qualify("codex")
        record["version"] = "old version"
        self.qualification.write_text(json.dumps(record))
        self.refused(self.invoke("codex", qualify=True), "version")

    def test_codex_preflight_arguments_each_mode_then_refusal(self):
        self.register("codex")
        for mode, sandbox in (("ro", "read-only"), ("rw", "workspace-write")):
            with self.subTest(mode=mode):
                self.qualify("codex", mode, "tool")
                result = self.invoke("codex", mode, True, ["--model", "model", "--effort", "high"])
                self.refused(result, "Codex runtime skill discovery")
                call = json.loads(Path(str(self.calls) + ".debug").read_text().splitlines()[-1])
                self.assertNotEqual(call["home"], str(self.home))
                self.assertFalse(Path(call["home"]).exists())
                self.assertIn('sandbox_mode="' + sandbox + '"', call["args"])
                self.assertIn("model_reasoning_effort=\"high\"", call["args"])
                for arg in ("project_doc_max_bytes=0", 'model="model"'):
                    self.assertIn(arg, call["args"])
                self.assertEqual(call["cwd"], str(self.workdir))

    def test_claude_native_safe_mode_event_and_output_extraction(self):
        self.qualify("claude")
        for event in ({"type":"system", "subtype":"init", "skills":[]},
                      {"type":"system", "subtype":"init", "skills":[], "memory_paths":[]}):
            self.env["FAKE_INIT"] = json.dumps(event)
            result = self.invoke(qualify=True, extra=["--model", "model"])
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            call = self.called()[-1]
            self.assertEqual(bytes.fromhex(call["pack"]), self.data)
            for arg in ("-p", "--safe-mode", "--output-format", "stream-json", "--verbose", "--permission-prompts", "none", "model", "--permission-mode"):
                self.assertIn(arg, call["args"])
            self.assertEqual(self.out.read_text(), "answer\n")
            self.out.unlink()

    def test_claude_discovery_stops_child_at_initial_event(self):
        self.qualify("claude")
        for field in ("skills", "memory_paths"):
            self.env["FAKE_INIT"] = json.dumps({"type":"system", "subtype":"init", "skills":[], "memory_paths":[], field:["third party instructions"]})
            self.env["FAKE_BLOCK"] = "1"
            result = self.invoke(qualify=True)
            self.assertEqual(result.returncode, 2, result.stderr.decode())
            self.assertIn(field, result.stderr.decode())
            self.assertFalse(self.out.exists())

    def test_claude_missing_initial_metadata_refuses(self):
        self.qualify("claude")
        self.env["FAKE_INIT"] = '{"type":"system","subtype":"init"}'
        self.assertEqual(self.invoke(qualify=True).returncode, 2)

    def test_required_pack_skill_is_allowed_but_mcp_requires_matching_qualification(self):
        mcp = self.base / "mcp.json"
        mcp.write_text('{"mcpServers": {}}')
        self.refused(self.invoke(extra=["--mcp-config", str(mcp)]), "MCP")
        self.qualify("claude", mcp=mcp)
        result = self.invoke(qualify=True, extra=["--mcp-config", str(mcp)])
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        call = self.called()[-1]
        snapshot = Path(call["args"][call["args"].index("--mcp-config") + 1])
        self.assertNotEqual(snapshot, mcp)
        self.assertFalse(snapshot.exists())
        self.assertEqual(call["mcp"], mcp.read_text())
        self.assertIn("--safe-mode", self.called()[-1]["args"])
        self.out.unlink()
        self.calls.unlink()
        mcp.write_text("changed")
        self.refused(self.invoke(qualify=True, extra=["--mcp-config", str(mcp)]), "MCP")

    def test_kimi_refuses_runtime_discovery_even_with_clean_qualification(self):
        self.register("kimi")
        self.qualify("kimi")
        self.refused(self.invoke("kimi", qualify=True), "runtime instruction discovery")
        shared = self.user / ".agents/AGENTS.md"
        shared.parent.mkdir()
        shared.write_text("instructions added after qualification")
        self.refused(self.invoke("kimi", qualify=True), str(shared))
        self.refused(self.invoke("kimi", qualify=True, extra=["--effort", "high"]), "effort")
        self.refused(self.invoke("kimi", qualify=True, extra=["--mcp-config", str(self.pack)]), "MCP")

    def test_child_failure_is_visible_without_retry_or_success_output(self):
        self.qualify("claude")
        self.env["FAKE_EXIT"] = "9"
        result = self.invoke(qualify=True)
        self.assertEqual(result.returncode, 1, result.stderr.decode())
        self.assertIn("9", result.stderr.decode())
        self.assertIn("log", result.stderr.decode())
        self.assertEqual(len(self.called()), 1)
        self.assertFalse(self.out.exists())

    def test_existing_output_is_refused_without_overwrite(self):
        self.out.write_text("previous answer")
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.out.read_text(), "previous answer")
        self.assertEqual(self.called(), [])

    def test_recorded_host_denial_does_not_allow_currently_writable_checkout(self):
        self.qualify("claude", "ro", "host")
        self.refused(self.invoke("claude", "ro", True), "reachable repository resources")

    def test_native_compiler_pack_reaches_claude_unchanged(self):
        revision = subprocess.run(["git", "--no-replace-objects", "-C", str(ROOT), "rev-parse", "HEAD"],
                                  capture_output=True, check=True).stdout.decode().strip()
        task = self.base / "task.txt"
        task.write_text("Profile: specialist. Loading path: compiled pack only.\n"
                        "This task overrides live House Rules loading pointers in repository text.\n"
                        "Do not load live House Rules files or follow their links.\n"
                        "Objective: synthetic task\nDecisions: none\nPre-flight: fake tool only\n")
        pointer = (ROOT / "AGENTS.md").read_bytes()
        (self.workdir / "AGENTS.md").write_bytes(pointer)
        git_env = {**self.env, "GIT_CONFIG_NOSYSTEM":"1", "GIT_CONFIG_GLOBAL":os.devnull,
                   "GIT_AUTHOR_NAME":"Fixture", "GIT_AUTHOR_EMAIL":"fixture@example.invalid",
                   "GIT_COMMITTER_NAME":"Fixture", "GIT_COMMITTER_EMAIL":"fixture@example.invalid"}
        for arguments in (("init",), ("add", "AGENTS.md"), ("commit", "-m", "Fixture")):
            subprocess.run(["git", "-C", str(self.workdir), *arguments], env=git_env,
                           capture_output=True, check=True, timeout=2)
        destination = self.base / "compiled"
        compiled = subprocess.run([sys.executable, "-B", str(ROOT / "skills/pr-ready/scripts/prompt.py"),
            "--repo", str(ROOT), "--rev", revision, "--role", "reviewer",
            "--target", str(self.workdir), "--task", str(task), "--task-source", "specialist-test", "--out", str(destination)],
            input=b"", capture_output=True, timeout=5)
        self.assertEqual(compiled.returncode, 0, compiled.stderr.decode())
        self.pack, self.manifest = destination / "pack.txt", destination / "manifest.json"
        self.assertIn(pointer, self.pack.read_bytes())
        self.assertIn(task.read_bytes(), self.pack.read_bytes())
        self.assertNotIn(b"## Subagent profiles", self.pack.read_bytes())
        self.qualify("claude")
        result = self.invoke(qualify=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(bytes.fromhex(self.called()[0]["pack"]), self.pack.read_bytes())

    def test_changed_qualification_log_and_config_refuse_before_model_call(self):
        self.register("codex")
        self.qualify("codex")
        (self.base / "canary.log").write_text("changed evidence")
        self.refused(self.invoke("codex", qualify=True), "evidence")
        self.qualify("codex")
        with (self.home / "config.toml").open("a") as config:
            config.write("# changed native configuration\n")
        self.refused(self.invoke("codex", qualify=True), "config_sha256")

    def test_codex_preflight_failure_retains_log_without_retry(self):
        self.register("codex")
        self.qualify("codex")
        self.env["FAKE_DEBUG_EXIT"] = "8"
        result = self.invoke("codex", qualify=True)
        self.refused(result, "preflight exited 8")
        self.assertIn("log", result.stderr.decode())
        self.assertEqual(len(Path(str(self.calls) + ".debug").read_text().splitlines()), 1)

    def test_numeric_manifest_revision_refuses_without_traceback(self):
        record = json.loads(self.manifest.read_text())
        record["house_rules_revision"] = int("1" * 40)
        self.manifest.write_text(json.dumps(record))
        self.pack.write_bytes(b"House Rules revision: " + b"1" * 40 + b"\n")
        spec = importlib.util.spec_from_file_location("numeric_revision_test", LAUNCHER)
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with self.assertRaisesRegex(launcher.Refusal, "manifest"):
            launcher.verified_pack(self.pack, self.manifest)
        result = self.invoke()
        self.refused(result, "manifest")
        self.assertNotIn("Traceback", result.stderr.decode())

    def test_codex_live_discovery_refuses_after_clean_preflight_in_both_modes(self):
        self.register("codex")
        for mode in ("ro", "rw"):
            for source in (self.user / ".agents/skills", self.base / "administrative-skills",
                           self.workdir / ".agents/skills"):
                with self.subTest(mode=mode, source=source):
                    self.out.unlink(missing_ok=True)
                    self.calls.unlink(missing_ok=True)
                    self.qualify("codex", mode, "tool")
                    added = source / (mode + "/SKILL.md")
                    self.env["FAKE_ADD_SKILL"] = str(added)
                    result = self.invoke("codex", mode, True)
                    try:
                        self.refused(result, "Codex runtime skill discovery is not disabled or isolated")
                        self.assertEqual(added.read_text(), "skill added after clean capture")
                    finally:
                        added.unlink(missing_ok=True)

    def test_snapshot_accepts_canonical_disable_for_linked_builtin_skills(self):
        self.register("codex")
        external = self.base / "external-system"
        skill = external / "example/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("synthetic builtin")
        (external / "alias").symlink_to(skill.parent, target_is_directory=True)
        other = self.base / "external-skill.md"
        other.write_text("synthetic linked document")
        alias = external / "linked/SKILL.md"
        alias.parent.mkdir()
        alias.symlink_to(other)
        (self.home / "skills").mkdir()
        (self.home / "skills/.system").symlink_to(external, target_is_directory=True)
        with (self.home / "config.toml").open("a") as config:
            for canonical in (skill, other):
                config.write(f'[[skills.config]]\npath = "{canonical}"\nenabled = false\n')
        spec = importlib.util.spec_from_file_location("linked_builtin_test", LAUNCHER)
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        original = launcher.sync.discover_skills
        with mock.patch.object(Path, "home", return_value=self.user), mock.patch.object(
                launcher.sync, "discover_skills", side_effect=lambda folder, *args, **kwargs:
                set() if folder == Path("/etc/codex/skills") else original(folder, *args, **kwargs)):
            findings = []
            launcher.sync.specialist_findings(self.root, self.user, "SPECIALIST_CODEX_HOME",
                                             self.home, findings, self.workdir)
            self.assertEqual(findings, [])
            staging = self.base / "inputs"
            staging.mkdir()
            args = mock.Mock(root=self.root, workdir=self.workdir, mcp_config=None)
            home = launcher.snapshot_inputs(args, self.home, staging, self.env.copy())
        for relative in ("alias/SKILL.md", "example/SKILL.md", "linked/SKILL.md"):
            copied = home / "skills/.system" / relative
            self.assertTrue(copied.is_file())
            self.assertFalse(copied.is_symlink())
            self.assertIn(str(copied), args.skill_options[1])

    def test_codex_snapshot_preflight_survives_source_changes_then_refuses_execution(self):
        self.register("codex")
        config = self.home / "config.toml"
        # Built-in document selectors must follow the copied home through native overrides.
        skill = self.home / "skills/.system/example/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("synthetic builtin")
        with config.open("a") as output:
            output.write(f'[[skills.config]]\npath = "{skill}"\nenabled = false\n')
        self.qualify("codex")
        original = config.read_text()
        self.env["FAKE_MUTATE_HOME"] = str(config)
        result = self.invoke("codex", qualify=True)
        self.refused(result, "Codex runtime skill discovery")
        debug = json.loads(Path(str(self.calls) + ".debug").read_text())
        self.assertEqual(debug["config"], original)
        self.assertEqual(config.read_text(), "changed original config")
        self.assertIn(str(Path(debug["home"]) / "skills/.system/example/SKILL.md"), " ".join(debug["args"]))
        self.assertFalse(Path(debug["home"]).exists())

    def test_codex_snapshot_dereferences_config_alias_before_preflight(self):
        self.register("codex")
        config = self.home / "config.toml"
        canonical = self.base / "native-config.toml"
        canonical.write_bytes(config.read_bytes())
        config.unlink()
        config.symlink_to(canonical)
        self.qualify("codex")
        original = canonical.read_text()
        self.env["FAKE_MUTATE_HOME"] = str(canonical)
        result = self.invoke("codex", qualify=True)
        self.refused(result, "Codex runtime skill discovery")
        debug = json.loads(Path(str(self.calls) + ".debug").read_text())
        self.assertNotEqual(debug["home"], str(self.home))
        self.assertEqual(debug["config"], original)
        self.assertEqual(canonical.read_text(), "changed original config")

    def test_claude_mcp_snapshot_survives_source_replacement_before_qualification(self):
        source = self.base / "mcp.json"
        source.write_text('{"mcpServers": {}}')
        self.qualify("claude", mcp=source)
        original = source.read_text()
        self.env["FAKE_MUTATE_MCP"] = str(source)
        result = self.invoke(qualify=True, extra=["--mcp-config", str(source)])
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(self.called()[0]["mcp"], original)
        self.assertEqual(source.read_text(), "changed original mcp")

    def test_claude_native_contract_needs_qualification_evidence(self):
        record = self.qualify("claude")
        record.pop("claude_init_contract")
        self.qualification.write_text(json.dumps(record))
        self.refused(self.invoke(qualify=True), "native initialization contract")

    def test_read_only_mount_with_writable_git_and_symlink_resources_is_refused(self):
        writable = self.base / "writable-repository-data"
        writable.mkdir()
        (self.workdir / ".git").write_text(f"gitdir: {writable}\n")
        (self.workdir / "linked-task").symlink_to(writable, target_is_directory=True)
        for tool in ("claude", "kimi"):
            if tool == "kimi":
                self.register(tool)
            self.qualify(tool, "ro", "host")
            self.refused(self.invoke(tool, "ro", True, readonly_mount=True), "reachable repository resources")

    def test_untracked_and_invalid_parent_handles_refuse(self):
        self.qualify("claude")
        self.refused(self.invoke(qualify=True, tracked=False), "tracked parent pipe")
        self.refused(self.invoke(qualify=True, tracked=False, extra=["--parent-fd", "1"]), "read end")

    @staticmethod
    def kill_owned_fixture(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def wait_for_tree(self, path):
        deadline = time.monotonic() + 2
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(path.exists(), "synthetic child never started within 2s")
        return json.loads(path.read_text())

    def assert_tree_stopped(self, heartbeat):
        # Both generations hold the FIFO write end. EOF proves both exited,
        # including a grandchild reparented to the OS (without requiring ps).
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                self.assertEqual(os.read(heartbeat, 1), b"")
                return
            except BlockingIOError:
                time.sleep(0.01)
        self.fail("owned child or grandchild still holds its lifetime handle")

    def test_launcher_termination_and_parent_eof_stop_child_and_grandchild(self):
        self.qualify("claude")
        for cancellation in ("signal", "parent-eof", "parent-exit"):
            with self.subTest(cancellation=cancellation):
                tree = self.base / (cancellation + ".json")
                self.env["FAKE_TREE"] = str(tree)
                fifo = self.base / (cancellation + ".fifo")
                os.mkfifo(fifo)
                heartbeat = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
                self.addCleanup(os.close, heartbeat)
                self.env["FAKE_HEARTBEAT"] = str(fifo)
                child, writer = self.invoke(qualify=True, start=True, parent_exit=cancellation == "parent-exit")
                pids = self.wait_for_tree(tree)
                for pid in pids:
                    self.addCleanup(self.kill_owned_fixture, pid)
                if cancellation != "parent-exit":
                    self.assertEqual(os.getpgid(pids[0]), pids[0])
                    self.assertEqual(os.getpgid(pids[1]), pids[0])
                if cancellation == "signal":
                    child.send_signal(signal.SIGTERM)
                elif cancellation == "parent-eof":
                    os.close(writer)
                    # Remove this descriptor's cleanup after intentionally closing it.
                    self._cleanups = [entry for entry in self._cleanups
                                      if not (entry[0] == os.close and entry[1] == (writer,))]
                _, err = child.communicate(timeout=2)
                if cancellation == "parent-exit":
                    self.assertEqual(child.returncode, 0, err.decode())
                else:
                    self.assertNotEqual(child.returncode, 0, err.decode())
                self.assert_tree_stopped(heartbeat)
                self.assertFalse(self.out.exists())

    def test_rollout_requires_lead_qualification_before_acceptance(self):
        text = (ROOT / "docs/design/75-subagent-profiles.md").read_text()
        self.assertIn("The lead completes the section 7.1 runs before acceptance", text)
        self.assertIn("Workers never run model CLIs or touch credential files or real tool homes", text)

    def test_dispatch_guidance_identifies_skills_before_opening_bodies(self):
        text = (ROOT / "skills/agent-lanes/SKILL.md").read_text()
        self.assertIn("## Subagent profiles", text)
        self.assertIn("descriptions before opening skill bodies", text)
        self.assertIn("--session", text)
        self.assertIn("unchanged pack and manifest", text)
        self.assertIn("Profile: specialist. Loading path: compiled pack only.", text)
        self.assertIn("This task overrides live House Rules loading pointers in repository text.", text)


if __name__ == "__main__":
    unittest.main()
