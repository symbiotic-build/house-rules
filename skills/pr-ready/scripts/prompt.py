#!/usr/bin/env python3
"""Compile @rule includes and ordered packs; registered specs use the shared checker."""
import argparse
from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent.parent.parent
COMPILER = "skills/pr-ready/scripts/prompt.py"
DOC_TOOL = "skills/spec-writing/scripts/spec_docs.py"
DOC_INPUTS = ("skills/pr-ready/scripts/prepare.py", DOC_TOOL, "skills/spec-writing/scripts/runtime.json",
              "skills/spec-writing/scripts/requirements.lock",
              "skills/spec-writing/references/format-contract.json", "rules/writing.md")
DOC_METADATA = ("docs/ENTITIES.json", "docs/DOCUMENTS.json")
INCLUDE = re.compile(r"@rule house-rules:(.*)")
NAME = re.compile(r"[a-z0-9-]+")


class PromptError(Exception):
    """An input cannot be compiled; no compilation output may be published."""


class CompiledPack(bytes):
    """Compiled bytes with an in-memory lens span for deferred task assembly."""

    def __new__(cls, data, lens_span=None, lens_last=False):
        pack = super().__new__(cls, data)
        pack.lens_span = lens_span
        pack.lens_last = lens_last
        return pack


def relative_path(name):
    """Validate a whole-file repository path before handing it to Git."""
    if not name:
        raise PromptError("empty include path at repository root")
    if "\x00" in name or "\n" in name or "\r" in name:
        raise PromptError("NUL byte or newline in include path")
    if "#" in name:
        raise PromptError("section references are not allowed: " + name)
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise PromptError("path outside repository root: " + name)
    if path.as_posix() in (".", ""):
        raise PromptError("empty include path at repository root")
    return path.as_posix()


def fingerprint(data):
    """Describe the exact bytes of an input or output."""
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class WorkingTree:
    """Legacy expansion source; commit-built packs never use its disk reads."""

    def __init__(self, root):
        self.root = Path(root).resolve()

    def read(self, name, *, optional=False):
        name = relative_path(name)
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root):
            raise PromptError("path outside repository root: " + name)
        if optional and not path.exists():
            return None
        data = path.read_bytes()
        return data, {"path": name, **fingerprint(data)}


class Commit:
    """Read only requested regular files through one replacement-protected batch."""

    def __init__(self, repo, rev):
        self.repo = Path(repo)
        try:
            self.revision = self.git("rev-parse", "--verify", "--end-of-options", rev + "^{commit}").decode().strip()
        except PromptError as exc:
            raise PromptError("cannot resolve commit " + rev + ": " + str(exc)) from exc
        self.batch = None
        self.batch_owner = self
        self.files = {}

    def git(self, *args):
        result = subprocess.run(["git", "--no-replace-objects", "-C", str(self.repo), *args],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
        if result.returncode:
            raise PromptError("Git " + args[0] + " failed: " + result.stderr.decode("utf-8", "replace").strip())
        return result.stdout

    def read(self, name, *, optional=False):
        name = relative_path(name)
        if name in self.files:
            result = self.files[name]
            if result is None and not optional:
                raise PromptError("missing file at " + self.revision[:12] + ": " + name)
            return result
        # Native cost: one exact path lookup, then one batch request per new file.
        entry = self.git("ls-tree", "-z", self.revision, "--", ":(literal)" + name)
        if not entry:
            self.files[name] = None
            if optional:
                return None
            raise PromptError("missing file at " + self.revision[:12] + ": " + name)
        records = entry.split(b"\0")
        if len(records) != 2 or records[1]:
            raise PromptError("ambiguous Git path: " + name)
        metadata, returned = records[0].split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        if returned != name.encode("utf-8") or mode not in ("100644", "100755") or kind != "blob":
            raise PromptError("not a regular file at " + self.revision[:12] + ": " + name)
        owner = self.batch_owner
        if owner.batch is None:
            owner.batch = subprocess.Popen(["git", "--no-replace-objects", "-C", str(self.repo),
                                            "cat-file", "--batch"], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        owner.batch.stdin.write((self.revision + ":" + name + "\n").encode("utf-8"))
        owner.batch.stdin.flush()
        header = owner.batch.stdout.readline().split()
        if len(header) != 3 or header[0].decode("ascii") != blob or header[1] != b"blob":
            raise PromptError("invalid Git blob response: " + name)
        size = int(header[2])
        data = owner.batch.stdout.read(size)
        if len(data) != size or owner.batch.stdout.read(1) != b"\n":
            raise PromptError("incomplete Git blob: " + name)
        result = data, {"path": name, "commit": self.revision, "blob": blob, **fingerprint(data)}
        self.files[name] = result
        return result

    def close(self):
        """Close the batch and propagate a Git failure before publication."""
        if self.batch is not None:
            child, self.batch = self.batch, None
            child.stdin.close()
            try:
                status = child.wait(timeout=5)
                error = child.stderr.read().decode("utf-8", "replace")
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                raise PromptError("Git cat-file did not finish")
            finally:
                child.stdout.close()
                child.stderr.close()
            if status:
                raise PromptError("Git cat-file failed: " + error.strip())

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def compiler(self):
        """Pin assembly code as well as its rule inputs."""
        data, entry = self.read(COMPILER)
        if Path(__file__).read_bytes() != data:
            raise PromptError("compiler differs from " + self.revision[:12] + "; run the compiler from that commit")
        return entry


class Expansion:
    """One compilation: cycle check, omission, repeat check, then recursive render."""

    def __init__(self, source, session=False):
        self.source = source
        self.session = session
        self.files = []
        self.seen = set()
        self.omitted = []
        self.repeats = []
        self.shared_declared = False
        self.part = 1

    def visit(self, name, stack=(), *, entry_file=False):
        name = relative_path(name)
        if name in stack:
            raise PromptError("include cycle: " + name)
        data, entry = self.source.read(name)
        if name.startswith("rules/"):
            self.shared_declared = True
            if self.session and not entry_file:
                if name not in self.omitted:
                    self.omitted.append(name)
                return ""
        if name in self.seen:
            self.repeats.append({"path": name, "part": self.part})
            return ""
        self.seen.add(name)
        self.files.append(entry)
        return self.render(data.decode("utf-8"), (*stack, name))

    def render(self, text, stack=()):
        parts = []
        for line in text.splitlines(keepends=True):
            match = INCLUDE.fullmatch(line.removesuffix("\n").removesuffix("\r"))
            parts.append(self.visit(match[1], stack) if match else line)
        return "".join(parts)

    def loading(self):
        mode = ("session; shared rules come from the live House Rules index." if self.session else
                "compiled shared rules; canonical owners are included in this pack.")
        return "Loading path: " + mode + "\n\n"

    def expand(self, text=None, file=None):
        """Render legacy input and its loading metadata through the shared owner."""
        result = self.visit(file, entry_file=True) if file is not None else self.render(text)
        if self.shared_declared or any(e["path"].startswith("prompts/roles/") for e in self.files):
            result = self.loading() + result
        return result


def expand(text=None, *, file=None, root=ROOT, source=None, session=False):
    """Expand files once in first-include order; retain the legacy loading header."""
    expansion = Expansion(source or WorkingTree(root), session)
    try:
        result = expansion.expand(text, file)
        return result, [e["path"] for e in expansion.files]
    except (OSError, UnicodeError, RuntimeError) as exc:
        raise PromptError(str(exc)) from exc


def target_rules(source):
    """Include both target rule files unchanged, with the bible before AGENTS.md."""
    parts = []
    files = []
    for path in (".agents/rules.md", "AGENTS.md"):
        selected = source.read(path, optional=True)
        if selected is not None:
            data, entry = selected
            data.decode("utf-8")  # Invalid target text fails without a lossy conversion.
            heading = f"Repository rules (<target>/{path} at {source.revision[:12]}):\n"
            parts.append(ending(heading.encode() + data))
            files.append(entry)
    text = (b"\n".join(parts) if parts else
            b"Repository rules: this repository has no rules of its own.\n")
    return text, {"commit": source.revision, "files": files}


def ending(data):
    """Every nonempty part ends in a newline; empty parts contribute nothing."""
    return data + b"\n" if data and not data.endswith(b"\n") else data


def logical_source(name):
    """Task provenance is a logical name or owner/repository#issue, never a file path."""
    if not (re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) or
            (re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[0-9]+", name) and
             not any(part in (".", "..") for part in name.split("#", 1)[0].split("/")))):
        raise PromptError("task source must be a logical identifier, never a machine path")
    return name


def review_plan(lenses):
    """Describe the responsibilities of the reviewers actually dispatched."""
    all_roles = ["technical", "readability", "design/cost", "failure/recovery", "whole-scenario"]
    specialists = {"naming-readability": ["readability"],
                   "design-spec": all_roles}
    return [{"id": lens, "responsibilities": all_roles if lens.startswith("generalist-")
             else specialists.get(lens, ["technical"])} for lens in lenses]


def documentation_context(source, target, assignment=None, *, base=None, plan=None, derive_assignment=False):
    """Use the matching shared selector on captured target bytes, never a live helper."""
    metadata = [target.read(path, optional=True) for path in DOC_METADATA]
    if not any(item is not None for item in metadata):
        if assignment is not None:
            raise PromptError("documentation assignment requires docs/ENTITIES.json and docs/DOCUMENTS.json")
        return None
    if not all(item is not None for item in metadata):
        raise PromptError("mandatory documentation context needs both docs/ENTITIES.json and docs/DOCUMENTS.json")
    if assignment is None and not derive_assignment:
        raise PromptError("mandatory documentation context needs an explicit --assignment JSON file")
    derive_assignment = derive_assignment and assignment is None
    if derive_assignment and base is None:
        raise PromptError("derived documentation review requires a comparison base")
    if plan is not None and base is None:
        raise PromptError("documentation review requires an explicit --target-base revision")
    # The snapshot owner uses one native tree inventory and one batch of required
    # blobs. Code/asset links use inventory existence, without reading their bytes.
    tools = []
    with tempfile.TemporaryDirectory(prefix="spec-docs-tool-") as directory:
        root = Path(directory)
        for path in DOC_INPUTS:
            data, entry = source.read(path)
            tools.append(entry)
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        policy_spec = importlib.util.spec_from_file_location("_pack_credential_policy", root / "skills/pr-ready/scripts/prepare.py")
        policy = importlib.util.module_from_spec(policy_spec)
        policy_spec.loader.exec_module(policy)
        name = "_pack_spec_docs_" + fingerprint((root / DOC_TOOL).read_bytes())["sha256"]
        spec = importlib.util.spec_from_file_location(name, root / DOC_TOOL)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
            if isinstance(assignment, (str, bytes)):
                diagnostics = module.Diagnostics()
                assignment = module.load_json(assignment, "assignment", diagnostics)
                if diagnostics.errors:
                    raise module.SpecDocsError(diagnostics)
            if not derive_assignment:
                if not isinstance(assignment, dict) or not module.strings(assignment.get("required_test_reviews", [])):
                    module.fail("D02", "malformed declaration: assignment needs an object and test selectors", "assignment")
                assignment = dict(assignment)
            snapshot = module.Snapshot.from_git(target.repo, rev=target.revision)
            corpus = module.load_corpus(snapshot)
            if base is not None:
                corpus.base = module.load_corpus(module.Snapshot.from_git(target.repo, rev=base), comparison=True)
            if derive_assignment:
                sections = module.changed_sections(corpus.base, corpus)
                if not sections:
                    diagnostics = module.check(corpus)
                    if diagnostics.errors:
                        raise module.SpecDocsError(diagnostics)
                    return None
                assignment = {"version": 1, "sections": sections}
            if plan is not None:
                assignment["review_plan"] = plan
            if base is not None:
                tests = {test for change in module.requirement_changes(corpus.base, corpus).changes
                         for test in change["tests"]}
                assignment["required_test_reviews"] = sorted(tests | set(assignment.get("required_test_reviews", [])))
            context = module.select_context(corpus, assignment)
            warnings = [str(w) for w in context.diagnostics.warnings]
            if policy.redact(context.content.decode()) != context.content.decode():
                raise PromptError("mandatory documentation context contains credential-bearing content; remove credentials before preparation")
        except module.SpecDocsError as exc:
            raise PromptError(policy.redact(str(exc))) from exc
        finally:
            sys.modules.pop(name, None)
    return {"content": context.content, "manifest": context.manifest,
            "size_bytes": context.size_bytes, "tools": tools, "warnings": warnings}


def documentation_part(context):
    """Report the selector's exact byte size beside its complete mandatory output."""
    heading = f"# Mandatory documentation context ({context['size_bytes']} UTF-8 bytes)\n\n"
    warnings = "\n".join(context["warnings"])
    return heading.encode() + context["content"] + ("\n" + warnings + "\n").encode()


def build_pack(source, *, role=None, lens=None, includes=(), tasks=(), target=None, omit_shared_rules=False,
               assignment=None, budget_bytes=None, target_base=None, plan=None):
    """Assemble revision, role, lens, extras, repository rules and literal tasks in order."""
    if target is not None and target.repo.resolve() == source.repo.resolve():
        # Different revisions in one repository still use one batch process.
        target.batch_owner = source.batch_owner
    compiler = source.compiler()
    manifest = {"format": 1, "compiler": compiler, "house_rules_revision": source.revision,
                "files": [], "parts": [], "skipped_repeats": [], "omitted_shared_rules": [], "target": None}
    expansion = Expansion(source, omit_shared_rules)
    parts = [f"House Rules revision: {source.revision}\n".encode()]
    lens_index = None
    requested = []
    for kind, name in (("role", role), ("lens", lens)):
        if name is not None:
            if not NAME.fullmatch(name):
                raise PromptError("invalid " + kind + " name: " + name)
            folder = "roles" if kind == "role" else "lenses"
            requested.append((kind, f"prompts/{folder}/{name}.md"))
    requested.extend(("include", path) for path in includes)
    for kind, path in requested:
        expansion.part = len(manifest["parts"]) + 1
        manifest["parts"].append({"kind": kind, "path": relative_path(path)})
        data = expansion.visit(path).encode("utf-8")
        if data:
            if kind == "lens":
                lens_index = len(parts)
            parts.append(data)
    if target is not None:
        data, manifest["target"] = target_rules(target)
        parts.append(data)
        manifest["parts"].append({"kind": "target"})
        if plan is None and role == "reviewer":
            plan = review_plan([lens or "generalist-a"])
        context = documentation_context(source, target, assignment, base=target_base, plan=plan)
        if context is not None:
            rule = "rules/specifications.md"
            if rule not in expansion.seen:
                parts.append(expansion.visit(rule).encode("utf-8"))
                manifest["parts"].append({"kind": "include", "path": rule})
            parts.append(documentation_part(context))
            manifest["documentation"] = {k: v for k, v in context.items() if k != "content"}
            manifest["parts"].append({"kind": "documentation"})
    elif assignment is not None:
        raise PromptError("documentation assignment requires --target")
    if expansion.shared_declared or role is not None:
        # Loading metadata belongs to the first text part, not a separate pack part.
        if len(parts) > 1:
            parts[1] = expansion.loading().encode() + parts[1]
        else:
            parts.append(expansion.loading().encode().rstrip(b"\n") + b"\n")
    lens_span = None
    if lens_index is not None:
        start = sum(len(ending(p)) + 1 for p in parts[:lens_index] if p)
        lens_span = (start, start + len(ending(parts[lens_index])))
    pack = CompiledPack(b"\n".join(ending(p) for p in parts if p), lens_span)
    manifest.update(files=expansion.files, skipped_repeats=expansion.repeats,
                    omitted_shared_rules=expansion.omitted)
    if budget_bytes is not None:
        if type(budget_bytes) is not int or budget_bytes < 0:
            raise PromptError("pack byte budget must be a nonnegative integer")
        manifest["budget_bytes"] = budget_bytes
    return append_tasks(pack, manifest, tasks)


def append_tasks(pack, manifest, tasks):
    """Finish a compiled pack with literal tasks, without rereading pinned inputs."""
    parts = []
    lens_span = getattr(pack, "lens_span", None)
    lens_last = getattr(pack, "lens_last", False)
    for file, name in tasks:
        data = ending(Path(file).read_bytes())
        data.decode("utf-8")
        manifest["parts"].append({"kind": "task", "source": logical_source(name), **fingerprint(data)})
        if data:
            parts.append(data)
            # The preparer's existing final heading also identifies structured
            # context when its change had to fall back to pack for size.
            lens_last |= data.rstrip(b"\n").endswith(b"\n# 7. Lens instructions")
    if lens_span is not None and lens_last:
        start, end = lens_span
        lens = pack[start:end]
        parts = [part for part in (pack[:start].removesuffix(b"\n"),
                                  pack[end:].removeprefix(b"\n"), *parts) if part]
        prefix = b"\n".join(parts)
        pack = CompiledPack(b"\n".join((prefix, lens)), (len(prefix) + 1, len(prefix) + 1 + len(lens)), True)
        old_parts = list(manifest["parts"])
        lens_part = next(part for part in old_parts if part["kind"] == "lens")
        manifest["parts"] = [part for part in old_parts if part is not lens_part] + [lens_part]
        for repeat in manifest["skipped_repeats"]:
            part = old_parts[repeat["part"] - 1]
            repeat["part"] = next(n for n, entry in enumerate(manifest["parts"], 1) if entry is part)
    else:
        pack = CompiledPack(b"\n".join([pack, *parts]), lens_span, lens_last)
    if "budget_bytes" in manifest and len(pack) > manifest["budget_bytes"]:
        raise PromptError(f"D25 complete pack requires {len(pack)} UTF-8 bytes; available budget is {manifest['budget_bytes']}")
    manifest["pack"] = fingerprint(pack)
    return pack, manifest


def manifest_bytes(manifest):
    """Stable JSON for an exact compiled-input record."""
    return (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")


def publish(destination, pack, manifest):
    """Publish both artifacts together through one sibling directory rename."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise PromptError("output destination exists: " + str(destination))
    staging = Path(tempfile.mkdtemp(prefix="." + destination.name + "-", dir=destination.parent))
    try:
        (staging / "pack.txt").write_bytes(pack)
        (staging / "manifest.json").write_bytes(manifest_bytes(manifest))
        # Recheck after writing; a concurrent destination must never be overwritten.
        if destination.exists() or destination.is_symlink():
            raise PromptError("output destination exists: " + str(destination))
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


class Parser(argparse.ArgumentParser):
    """All invalid input has the same one-line failure contract."""

    def error(self, message):
        raise PromptError(message)


class TaskOption(argparse.Action):
    """Retain task order and enforce immediately adjacent source annotations."""

    def __call__(self, parser, namespace, value, option_string=None):
        tasks = list(namespace.tasks or [])
        if option_string == "--task":
            tasks.append((value, "inline"))
        else:
            tasks[-1] = (tasks[-1][0], logical_source(value))
        namespace.tasks = tasks


def preparer_context(request):
    """Keep legacy preparer compilation here while reporting remains standalone."""
    common, instructions, context, sections = "", "", None, None
    if request["full"]:
        common, _ = expand(file="prompts/roles/reviewer.md")
        instructions, _ = expand(file="prompts/lenses/" + request["lens"] + ".md")
    if request["documentation"]:
        assignment = Path(request["assignment"]).read_bytes() if request["assignment"] else None
        with Commit(request["repo"], request["head"]) as target:
            selected = documentation_context(WorkingTree(ROOT), target, assignment, base=request["base"],
                                             plan=review_plan([request["lens"]]), derive_assignment=request.get("derive", False))
        if selected is not None:
            context = documentation_part(selected).decode("utf-8")
            sections = selected["manifest"]["assignment"]["sections"]
    return dict(common=common, instructions=instructions, documentation=context, sections=sections)


def main(argv=None):
    parser = Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument("file", nargs="?")
    parser.add_argument("--preparer-context", help=argparse.SUPPRESS)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--session", action="store_true")
    for option in ("rev", "repo", "role", "lens", "target", "target-rev", "target-base", "out", "manifest", "assignment"):
        parser.add_argument("--" + option)
    parser.add_argument("--budget-bytes", type=int)
    parser.add_argument("--include", action="append", default=[])
    parser.add_argument("--task", dest="tasks", action=TaskOption)
    parser.add_argument("--task-source", dest="tasks", action=TaskOption)
    parser.add_argument("--no-target", action="store_true")
    try:
        argv = list(sys.argv[1:] if argv is None else argv)
        # argparse actions see values, not intervening options: validate adjacency first.
        for n, token in enumerate(argv):
            if token == "--task-source" or token.startswith("--task-source="):
                preceding_task = ((n >= 2 and argv[n - 2] == "--task" and not argv[n - 1].startswith("--")) or
                                  (n >= 1 and argv[n - 1].startswith("--task=")))
                if not preceding_task:
                    raise PromptError("--task-source requires an immediately preceding --task")
        args = parser.parse_args(argv)
        if args.preparer_context is not None:
            sys.stdout.write(json.dumps(preparer_context(json.loads(args.preparer_context))))
            return 0
        for option in ("rev", "repo", "target", "target_rev", "target_base", "out", "manifest", "assignment"):
            if getattr(args, option) == "":
                raise PromptError("--" + option.replace("_", "-") + " must not be empty")
        pack_mode = bool(args.role is not None or args.lens is not None or args.include or args.tasks or
                         args.target is not None or args.no_target or args.out is not None or
                         args.assignment is not None or args.budget_bytes is not None)
        if (pack_mode or args.manifest is not None or args.target_rev is not None or args.repo is not None) and args.rev is None:
            raise PromptError("--rev is required for pack mode and manifest output")
        if args.out is not None and args.manifest is not None:
            raise PromptError("--out and --manifest are mutually exclusive")
        if pack_mode and args.file is not None:
            raise PromptError("entry file cannot be combined with pack parts")
        if pack_mode and ((args.target is not None) + args.no_target != 1):
            raise PromptError("pack mode requires exactly one of --target or --no-target")
        if (args.target_rev is not None or args.target_base is not None) and args.target is None:
            raise PromptError("--target-rev and --target-base require --target")
        if pack_mode and not sys.stdin.isatty() and sys.stdin.buffer.read(1):
            raise PromptError("standard-input text cannot be combined with pack parts")
        with ExitStack() as stack:
            source = (stack.enter_context(Commit(args.repo if args.repo is not None else ROOT, args.rev))
                      if args.rev is not None else WorkingTree(ROOT))
            if pack_mode:
                target = (stack.enter_context(Commit(args.target, args.target_rev if args.target_rev is not None else "HEAD"))
                          if args.target is not None else None)
                output, manifest = build_pack(source, role=args.role, lens=args.lens, includes=args.include,
                                              tasks=args.tasks or (), target=target, omit_shared_rules=args.session,
                                              assignment=Path(args.assignment).read_bytes() if args.assignment else None,
                                              budget_bytes=args.budget_bytes, target_base=args.target_base)
                used = [e["path"] for e in manifest["files"]]
            else:
                compiler = source.compiler() if args.rev is not None else None
                text = None if args.file else sys.stdin.buffer.read().decode("utf-8")
                expansion = Expansion(source, args.session)
                result = expansion.expand(text, args.file)
                output = result.encode("utf-8")
                used = [e["path"] for e in expansion.files]
                manifest = {"format": 1, "compiler": compiler, "house_rules_revision": source.revision if args.rev is not None else None,
                            "files": expansion.files, "parts": [], "target": None,
                            "omitted_shared_rules": expansion.omitted, "skipped_repeats": expansion.repeats,
                            "pack": fingerprint(output)}
        # Close and check every Git reader before any output is written.
        if args.list:
            output = "".join(path + "\n" for path in used).encode()
            manifest["pack"] = fingerprint(output)
        if args.out is not None:
            publish(args.out, output, manifest)
        else:
            if args.manifest is not None:
                Path(args.manifest).write_bytes(manifest_bytes(manifest))
            sys.stdout.buffer.write(output)
            sys.stdout.buffer.flush()
        return 0
    except (PromptError, OSError, UnicodeError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("prompt: " + " ".join(str(exc).splitlines()), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
