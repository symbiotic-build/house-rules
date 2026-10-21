#!/usr/bin/env python3
"""Prepare every role and lens the way the review service does, and fail on any error.

The staged tool set includes the shared specification checker from the same House Rules
revision. Compile every role and prepare every lens, then exercise registered-document
preparation and a commit-built documentation pack without a live checkout fallback.
Registered specifications require the spec-writing tool's pinned Python environment.
Usage: check_review_staging.py [--root <house-rules checkout>]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STAGED = ("prompts", "rules", "skills/pr-ready", "skills/spec-writing")
# The review service stages only these folders and runs the preparer in isolated mode.
SERVICE_STAGED = ("prompts", "rules", "skills/pr-ready")
SERVICE_RUN = ("import runpy, sys; from pathlib import Path; sys.argv = sys.argv[1:]; "
               "sys.path.insert(0, str(Path(sys.argv[0]).resolve().parent)); runpy.run_path(sys.argv[0], run_name='__main__')")
# The service prepares Codex reviews in the structured format: lens instructions come last.
SECTIONS = ("# 1. Review pack", "# 3. Pull request and issue", "# 4. Requirements", "# 5. Change",
            "# 7. Lens instructions")
GIT_ENV = {"GIT_AUTHOR_NAME": "check", "GIT_AUTHOR_EMAIL": "check@example.invalid",
           "GIT_COMMITTER_NAME": "check", "GIT_COMMITTER_EMAIL": "check@example.invalid"}


def run(args, cwd):
    return subprocess.run(args, stdin=subprocess.DEVNULL, cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV})


def fixture(path):
    """A repository with one base commit on main and one change on a branch."""
    path.mkdir()
    steps = [(None, ["git", "init", "-q", "-b", "main"]), ("base\n", ["git", "add", "a.txt"]),
             (None, ["git", "commit", "-qm", "base"]), (None, ["git", "checkout", "-q", "-b", "change"]),
             ("base\nchange\n", ["git", "commit", "-qam", "change"])]
    for text, args in steps:
        if text is not None:
            (path / "a.txt").write_text(text)
        result = run(args, path)
        if result.returncode:
            raise RuntimeError(f"fixture: {' '.join(args)}: {result.stderr.strip()}")


def documentation_fixture(repo, stage):
    """Add a real, checked miniature and its explicit assignment to the Git fixture."""
    fixtures = stage / "skills/spec-writing/scripts/fixtures/miniature"
    for name in ("ENTITIES.json", "DOCUMENTS.json", "acceptance.md", "settings.md"):
        destination = repo / "docs" / (name if name.endswith(".json") else "example/" + name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixtures / name, destination)
    manifest_path = repo / "docs/DOCUMENTS.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["documents"][0]["status"] = "draft"
    manifest["documents"][0].pop("approval")
    manifest_path.write_text(json.dumps(manifest))
    generated = run([sys.executable, "-B", str(stage / "skills/spec-writing/scripts/spec_docs.py"),
                     "generate", "--root", str(repo)], repo)
    if generated.returncode:
        raise RuntimeError("documentation fixture: " + generated.stderr.strip())
    for args in (["git", "add", "docs", ".gitattributes"],
                 ["git", "commit", "-qm", "Documentation fixture"]):
        result = run(args, repo)
        if result.returncode:
            raise RuntimeError("documentation fixture: " + result.stderr.strip())
    assignment = repo.parent / "assignment.json"
    assignment.write_text(json.dumps({"version": 1, "sections": ["example-demo#acceptance"]}))
    return assignment


def check(root):
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "stage"
        for folder in STAGED:
            shutil.copytree(root / folder, stage / folder)
        scripts = stage / "skills/pr-ready/scripts"
        for role in sorted((stage / "prompts/roles").glob("*.md")):
            result = run([sys.executable, str(scripts / "prompt.py"), f"prompts/roles/{role.name}"], stage)
            if result.returncode or not result.stdout.strip():
                failures.append(f"role {role.stem}: {result.stderr.strip() or 'empty prompt'}")
        repo = Path(tmp) / "fixture"
        fixture(repo)
        lenses = [line.split()[0] for line in (scripts / "review-panel.lenses").read_text().splitlines()
                  if line.strip() and not line.startswith("#")]
        for lens in lenses:
            result = run([sys.executable, str(scripts / "prepare.py"), "review", str(repo), "--base", "main",
                          "--no-fetch", "--lens", lens, "--cli", "codex"], stage)
            missing = [s for s in SECTIONS if s not in result.stdout]
            if result.returncode or missing:
                detail = result.stderr.strip().splitlines()[-1:] or [f"missing {', '.join(missing)}"]
                failures.append(f"lens {lens}: {detail[0]}")
        try:
            assignment = documentation_fixture(repo, stage)
            # The service's own layout has no shared checker: review proceeds and says so.
            service = Path(tmp) / "service"
            for folder in SERVICE_STAGED:
                shutil.copytree(root / folder, service / folder)
            result = run([sys.executable, "-I", "-B", "-c", SERVICE_RUN,
                          str(service / "skills/pr-ready/scripts/prepare.py"), "review", str(repo), "--base", "main",
                          "--no-fetch", "--lens", "correctness-security", "--cli", "codex"], repo)
            if result.returncode or "Registered documentation context was not prepared" not in result.stdout:
                failures.append("service-layout review of a registered repository: " +
                                (result.stderr.strip().splitlines()[-1:] or ["missing documentation notice"])[0])
            result = run([sys.executable, "-B", str(scripts / "prepare.py"), "review", str(repo),
                          "--base", "main", "--no-fetch", "--context-only", "--assignment", str(assignment)], stage)
            if result.returncode or "# Complete registry" not in result.stdout or "UTF-8 bytes" not in result.stdout:
                failures.append("documentation preparation: " + (result.stderr.strip() or "missing context/size report"))
            # Pin the copied tool set; the pack compiler must fetch its helper from it.
            for args in (["git", "init", "-q", "-b", "main"], ["git", "add", *STAGED],
                         ["git", "commit", "-qm", "Staged tool fixture"]):
                result = run(args, stage)
                if result.returncode:
                    raise RuntimeError("tool fixture: " + result.stderr.strip())
            extracted = Path(tmp) / "compiler.py"
            shutil.copyfile(scripts / "prompt.py", extracted)
            result = run([sys.executable, "-I", "-B", str(extracted), "--repo", str(stage), "--rev", "HEAD",
                          "--role", "reviewer", "--lens", "design-spec", "--target", str(repo), "--target-base", "main",
                          "--assignment", str(assignment)], stage)
            if result.returncode or "# Complete registry" not in result.stdout or "UTF-8 bytes" not in result.stdout:
                failures.append("documentation compilation: " + (result.stderr.strip() or "missing context/size report"))
        except (OSError, ValueError, RuntimeError) as exc:
            failures.append("documentation staging: " + str(exc))
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args(argv).root.resolve()
    failures = check(root)
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"{'FAILED' if failures else 'OK'}: roles and lenses prepared from {', '.join(STAGED)} only")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
