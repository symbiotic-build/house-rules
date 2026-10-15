#!/usr/bin/env python3
"""Launch one verified specialist pack; no compilation, scheduling or retries."""
import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("house_rules_sync", ROOT / "scripts/sync.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class Refusal(Exception):
    """Isolation or a required capability could not be established."""


class ChildFailure(Exception):
    """The launched child did not produce a successful result."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verified_pack(pack, manifest):
    """Verify bytes once, then send exactly those bytes to the child."""
    data = pack.read_bytes()
    record = json.loads(manifest.read_bytes())
    if (not isinstance(record, dict) or not isinstance(record.get("files"), list) or
            not isinstance(record.get("house_rules_revision"), str) or
            not re.fullmatch(r"[0-9a-f]{40}", record["house_rules_revision"]) or
            not isinstance(record.get("pack"), dict)):
        raise Refusal("manifest requires house_rules_revision, files and pack.sha256")
    header = b"House Rules revision: " + record["house_rules_revision"].encode() + b"\n"
    if not data.startswith(header):
        raise Refusal("pack header is missing or does not match manifest revision")
    if digest(data) != record["pack"].get("sha256"):
        raise Refusal("pack hash does not match manifest pack.sha256")
    if record.get("omitted_shared_rules"):
        raise Refusal("specialist pack must include shared rules; do not compile with --session")
    data.decode("utf-8")
    return data


class ChildOwner:
    """Own child groups while a tracked parent holds the pipe's write end.

    The harness passes only the read descriptor. EOF means the tracked parent
    exited or cancelled. Children never inherit the descriptor. Group cleanup
    precedes snapshot removal and output publication.
    """

    def __init__(self, descriptor):
        if descriptor is None:
            raise Refusal("tracked parent pipe is required: --parent-fd")
        if (not stat.S_ISFIFO(os.fstat(descriptor).st_mode) or
                fcntl.fcntl(descriptor, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY):
            raise Refusal("--parent-fd must be the read end of a tracked parent pipe")
        os.set_inheritable(descriptor, False)
        self.descriptor = descriptor
        self.stopped = threading.Event()
        self.done = threading.Event()
        self.lock = threading.Lock()
        self.groups = set()
        self.handlers = {}

    def check(self):
        if self.stopped.is_set():
            raise ChildFailure("tracked parent exited or launch was terminated")

    @staticmethod
    def kill_group(pid, signum):
        try:
            os.killpg(pid, signum)
        except ProcessLookupError:
            pass  # This owned group has already exited.

    def cancel(self, signum=signal.SIGTERM):
        self.stopped.set()
        # Signal handlers must not acquire a lock interrupted on this thread.
        for pid in tuple(self.groups):
            self.kill_group(pid, signum)
            self.kill_group(pid, signal.SIGKILL)

    def watch(self):
        while not self.done.is_set():
            ready, _, _ = select.select([self.descriptor], [], [], 0.1)
            if ready:
                # The pipe is a lifetime handle, never a command channel.
                os.read(self.descriptor, 1)
                self.cancel()
                return

    def __enter__(self):
        if select.select([self.descriptor], [], [], 0)[0]:
            raise Refusal("tracked parent pipe is closed or contains unexpected data")
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            self.handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, lambda number, frame: self.cancel(number))
        self.watcher = threading.Thread(target=self.watch, daemon=True)
        self.watcher.start()
        return self

    @contextlib.contextmanager
    def child(self, command, **kwargs):
        with self.lock:
            self.check()
            child = subprocess.Popen(command, start_new_session=True, close_fds=True, **kwargs)
            self.groups.add(child.pid)
        try:
            self.check()
            yield child
            self.check()
        finally:
            with self.lock:
                self.kill_group(child.pid, signal.SIGKILL)
                self.groups.remove(child.pid)
            child.wait()

    def run(self, command, *, input=None, timeout=None, **kwargs):
        if input is not None:
            kwargs["stdin"] = subprocess.PIPE
        with self.child(command, **kwargs) as child:
            stdout, stderr = child.communicate(input, timeout=timeout)
            return subprocess.CompletedProcess(command, child.returncode, stdout, stderr)

    def __exit__(self, *exc):
        self.done.set()
        self.watcher.join()
        for signum, handler in self.handlers.items():
            signal.signal(signum, handler)


def specialist_home(args):
    """Select a registered source home; only the private snapshot is inspected."""
    if args.tool == "claude":
        return None
    key = "SPECIALIST_CODEX_HOME" if args.tool == "codex" else "SPECIALIST_KIMI_CODE_HOME"
    matches = [path for kind, path in sync.homes(args.root, Path.home()) if kind == key]
    if len(matches) != 1:
        raise Refusal(f"{key} requires exactly one registered specialist home")
    return matches[0]


def snapshot_inputs(args, source_home, staging, env):
    """Copy once, then verify and execute against the same private inputs."""
    home = None
    args.skill_options = []
    if source_home is not None:
        home = (staging / "codex-home").resolve()
        # Dereference aliases: no snapshot file may reopen an original input.
        shutil.copytree(source_home, home, symlinks=False)
        home.chmod(0o700)
        findings = []
        sync.specialist_findings(args.root, Path.home(), "SPECIALIST_CODEX_HOME",
                                 home, findings, args.workdir, source_home=source_home)
        if findings:
            raise Refusal("; ".join(finding.replace(str(home), str(source_home)) for finding in findings))
        if not sync.is_file(home / "auth.json"):
            raise Refusal("missing codex login state in registered specialist home")
        _, entries, _ = sync.codex_specialist_config(home / "config.toml")
        mapped = sync.codex_snapshot_entries(entries, source_home, home)
        if mapped != entries:
            value = "[" + ",".join("{path=" + json.dumps(str(entry["path"])) +
                                    ",enabled=false}" for entry in mapped) + "]"
            args.skill_options = ["-c", "skills.config=" + value]
        env["CODEX_HOME"] = str(home)
    if args.mcp_config:
        snapshot = staging / "mcp.json"
        snapshot.write_bytes(args.mcp_config.read_bytes())
        snapshot.chmod(0o600)
        args.mcp_config = snapshot
    return home


def qualification(args, home, env, owner, source_home):
    """Consume caller-owned section 7.1 evidence; never create a qualification cache.

    The operator performing the canary attests its result. The launcher verifies
    the log, tool version and launch context, rather than qualifying a model by
    its answer or treating prompt restrictions as a filesystem boundary.
    """
    capability = "MCP" if args.mcp_config else "write prevention" if args.mode == "ro" else "isolation"
    if args.qualification is None:
        raise Refusal(f"{capability} qualification record is required for {args.tool}")
    record = json.loads(args.qualification.read_bytes())
    if not isinstance(record, dict):
        raise Refusal("qualification must be an object")
    version = owner.run([args.tool, "--version"], env=env, cwd=args.workdir,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    if version.returncode or record.get("version") != version.stdout.decode("utf-8").strip():
        raise Refusal("qualification tool version does not match installed version")
    expected = {"tool": args.tool, "home": str(source_home) if source_home else None,
                "workdir": str(args.workdir), "mode": args.mode, "isolation": True,
                "config_sha256": digest((home / "config.toml").read_bytes()) if home else None}
    for field, value in expected.items():
        if record.get(field) != value:
            raise Refusal(f"qualification does not match launch {field}")
    evidence = record.get("evidence")
    if (not isinstance(evidence, dict) or not isinstance(evidence.get("path"), str) or
            not Path(evidence["path"]).is_absolute() or
            digest(Path(evidence["path"]).read_bytes()) != evidence.get("sha256")):
        raise Refusal("qualification evidence log is missing or changed")
    if args.mode == "ro":
        if record.get("write_prevention") != "tool" or record.get("write_test") != {
                "baseline_allowed": True, "denied": True, "write_absent": True}:
            raise Refusal("read-only write prevention is not qualified; a prompt restriction is insufficient")
    if args.tool == "claude" and record.get("claude_init_contract") != {
            "skills": "required-empty", "memory_paths": "optional-empty"}:
        raise Refusal("Claude native initialization contract is not qualified")
    if args.mcp_config and (record.get("mcp_sha256") != digest(args.mcp_config.read_bytes()) or
                            record.get("mcp_isolated") is not True or
                            record.get("mcp_tool_succeeded") is not True):
        raise Refusal("Claude safe-mode MCP capability is not qualified for this configuration")
    return record


def prompt_context(data):
    """Compare native prompt items with the canary's clean capture, without text heuristics.

    Only the tool-generated environment context varies across captures. Every
    other instruction or skill item must match the qualified clean capture.
    """
    items = json.loads(data)
    if not isinstance(items, list):
        raise Refusal("unknown Codex prompt-input format")
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise Refusal("unknown Codex prompt-input item")
        content = item.get("content", [])
        if (item.get("type") == "message" and item.get("role") == "user" and
                len(content) == 1 and isinstance(content[0], dict) and
                content[0].get("type") == "input_text" and
                re.fullmatch(r"<environment_context>.*</environment_context>\s*",
                             content[0].get("text", ""), re.S)):
            continue
        result.append(item)
    return result


def codex_preflight(args, env, record, log, owner):
    command = ["codex", "debug", "prompt-input", "-c", "project_doc_max_bytes=0",
               "-c", "sandbox_mode=" + json.dumps("read-only" if args.mode == "ro" else "workspace-write")]
    command.extend(codex_options(args))
    capture = owner.run(command, env=env, cwd=args.workdir, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, timeout=30)
    log.write(capture.stdout)
    log.write(capture.stderr)
    log.flush()
    if capture.returncode:
        raise Refusal(f"Codex prompt-input preflight exited {capture.returncode}")
    try:
        clean = record["codex_prompt_input"]
        if not isinstance(clean, list) or prompt_context(capture.stdout) != clean:
            raise Refusal("Codex prompt-input differs from qualified clean capture: additional instructions or discovered skills")
    except (KeyError, ValueError, TypeError) as error:
        raise Refusal("Codex prompt-input capture is missing or invalid") from error


def codex_options(args):
    options = list(args.skill_options)
    if args.model:
        options += ["-c", "model=" + json.dumps(args.model)]
    if args.effort:
        options += ["-c", "model_reasoning_effort=" + json.dumps(args.effort)]
    return options


def claude_result(command, data, args, env, log, owner):
    """Inspect the initial event while the child runs and stop contaminated launches."""
    with owner.child(command, cwd=args.workdir, env=env, stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=log) as child:
        return claude_stream(child, data, log)


def claude_stream(child, data, log):
    """Validate the qualified native init contract and extract one final result."""
    initialized, result = False, None
    try:
        # Feed stdin concurrently: a large pack must not deadlock stream output.
        errors = []

        def feed():
            try:
                child.stdin.write(data)
                child.stdin.close()
            except OSError as error:
                errors.append(error)

        writer = threading.Thread(target=feed)
        writer.start()
        for line in child.stdout:
            log.write(line)
            log.flush()
            try:
                event = json.loads(line)
            except ValueError as error:
                raise Refusal("unknown Claude stream event format") from error
            if not isinstance(event, dict):
                raise Refusal("unknown Claude stream event format")
            if not initialized:
                if event.get("type") != "system" or event.get("subtype") != "init":
                    raise Refusal("Claude initial isolation event is missing")
                if event.get("skills") != []:
                    raise Refusal("Claude initial event has discovered skills or missing skills metadata")
                if "memory_paths" in event and event["memory_paths"] != []:
                    raise Refusal("Claude initial event has discovered memory_paths or invalid memory_paths metadata")
                initialized = True
            elif event.get("type") == "result":
                if result is not None:
                    raise ChildFailure("Claude emitted multiple final results")
                if event.get("is_error") is not False or event.get("subtype") != "success":
                    raise ChildFailure("Claude final result reports failure")
                result = event.get("result")
        status = child.wait()
        writer.join()
        if status:
            raise ChildFailure(f"child exit status {status}")
        if errors:
            raise ChildFailure("child failed to consume verified pack")
        if not initialized:
            raise Refusal("Claude initial isolation event is missing")
        if not isinstance(result, str):
            raise ChildFailure("Claude final text result is missing")
        return result.encode("utf-8")
    finally:
        ChildOwner.kill_group(child.pid, signal.SIGKILL)
        child.wait()
        if "writer" in locals():
            writer.join()
        child.stdout.close()


def launch(args, data, env, record, log, staging, owner):
    if args.tool == "codex":
        codex_preflight(args, env, record, log, owner)
        # A clean capture cannot freeze user, administrative or repository skills
        # for a separate execution process. No supported isolation control is qualified.
        raise Refusal("Codex runtime skill discovery is not disabled or isolated; "
                      "user, administrative and repository discovery sources remain live")
    elif args.tool == "claude":
        command = ["claude", "-p", "--safe-mode", "--output-format", "stream-json", "--verbose",
                   "--permission-prompts", "none"]
        command += ["--permission-mode", "acceptEdits"]
        if args.model:
            command += ["--model", args.model]
        if args.mcp_config:
            command += ["--mcp-config", str(args.mcp_config)]
        answer = staging / "answer"
        answer.write_bytes(claude_result(command, data, args, env, log, owner))
        return answer
    else:
        raise Refusal("Kimi runtime instruction discovery is not disabled or isolated")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--tool", choices=("codex", "claude", "kimi"), required=True)
    parser.add_argument("--mode", choices=("ro", "rw"), required=True)
    for name in ("pack", "manifest", "workdir", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--parent-fd", type=int)
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--mcp-config", type=Path)
    args = parser.parse_args(argv)
    started = time.monotonic()
    log_path = None
    try:
        args.workdir = args.workdir.resolve(strict=True)
        args.out = args.out.absolute()
        if not sync.is_dir(args.workdir):
            raise Refusal("workdir must be a directory")
        if sync.present(args.out):
            raise Refusal("--out already exists; retain each attempt's output")
        if args.effort and args.tool != "codex":
            raise Refusal(f"{args.tool} reasoning effort capability is unsupported")
        if args.mcp_config and args.tool != "claude":
            raise Refusal(f"explicit MCP configuration is unsupported for {args.tool}")
        if args.mcp_config:
            args.mcp_config = args.mcp_config.resolve(strict=True)
        data = verified_pack(args.pack, args.manifest)
        if args.mode == "ro" and args.tool != "codex":
            raise Refusal("host-only read-only write prevention cannot cover reachable repository resources")
        source_home = specialist_home(args)
        if args.tool == "kimi":
            findings = []
            sync.specialist_findings(args.root, Path.home(), "SPECIALIST_KIMI_CODE_HOME",
                                     source_home, findings, args.workdir)
            raise Refusal("; ".join([*findings, "Kimi runtime instruction discovery is not disabled or isolated"]))
        env = os.environ.copy()
        with ChildOwner(args.parent_fd) as owner:
            with tempfile.NamedTemporaryFile(prefix=args.out.name + "-", suffix=".log", dir=args.out.parent,
                                             delete=False) as log:
                log_path = Path(log.name)
                with tempfile.TemporaryDirectory(prefix="." + args.out.name + "-", dir=args.out.parent) as temporary:
                    staging = Path(temporary)
                    # Native tool homes must be outside project checkouts, even
                    # when the caller stores its answer inside the checkout.
                    with tempfile.TemporaryDirectory(prefix="specialist-inputs-") as inputs:
                        home = snapshot_inputs(args, source_home, Path(inputs), env)
                        record = qualification(args, home, env, owner, source_home)
                        answer = launch(args, data, env, record, log, staging, owner)
                        owner.check()
                        # Native no-clobber publication: never overwrite an earlier result.
                        os.link(answer, args.out)
        print(f"specialist: succeeded; pack {digest(data)}; log {log_path}; {time.monotonic() - started:.3f}s", file=sys.stderr)
        return 0
    except ChildFailure as error:
        print(f"specialist: {error}; log {log_path}; {time.monotonic() - started:.3f}s", file=sys.stderr)
        return 1
    except (Refusal, OSError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
        message = " ".join(str(error).splitlines())
        print(f"specialist: refused: {message}" + (f"; log {log_path}" if log_path else "") +
              f"; {time.monotonic() - started:.3f}s", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
