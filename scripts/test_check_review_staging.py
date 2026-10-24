#!/usr/bin/env python3
"""The review-staging check passes on this checkout and fails on a role that includes a file
the review service does not copy."""
import ast
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import check_review_staging

REPO = Path(__file__).resolve().parents[1]

# (repository-relative source, line): reason the child must read caller input.
INHERITED_STDIN_ALLOWLIST = {}


def python_sources(path):
    """Yield Python files and literal Python heredocs / -c programs in shell scripts."""
    source = path.read_text()
    if path.suffix == ".py" or source.startswith(("#!/usr/bin/env python", "#!/usr/bin/python")):
        yield 0, source
        return
    lines = source.splitlines(keepends=True)
    shell = list(lines)
    index = 0
    while index < len(lines):
        match = re.search(r"(?<!<)<<(-?)\s*(['\"]?)([A-Za-z_]\w*)\2", lines[index])
        if not match:
            index += 1
            continue
        header = lines[index]
        previous = index - 1
        while previous >= 0 and lines[previous].rstrip().endswith("\\"):
            header = lines[previous] + header
            previous -= 1
        start = index + 1
        index = start
        while index < len(lines) and lines[index].strip() != match[3]:
            index += 1
        if index == len(lines):
            raise ValueError(f"{path}:{start}: unterminated heredoc")
        if "python" in header:
            block = lines[start:index]
            yield start, "".join(line.lstrip("\t") if match[1] else line for line in block)
        for position in range(start, index + 1):
            shell[position] = "\n"
        index += 1
    lexer = shlex.shlex("".join(shell), posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    tokens = list(lexer)
    for index, token in enumerate(tokens):
        if not (re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", Path(token).name)
                or re.fullmatch(r"\$\{?\w*python\}?", token)):
            continue
        for argument in range(index + 1, len(tokens)):
            if tokens[argument] == "-c":
                yield 0, tokens[argument + 1]
                break
            if tokens[argument].strip(";|&()<>\n") == "":
                break


def subprocess_calls(tree):
    """Find subprocess entry points, including aliased imports."""
    modules = {"subprocess"}
    functions = set()
    names = {"run", "Popen", "check_output", "call"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.asname or alias.name for alias in node.names if alias.name == "subprocess")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            functions.update(alias.asname or alias.name for alias in node.names if alias.name in names)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if ((isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name)
             and function.value.id in modules and function.attr in names)
                or (isinstance(function, ast.Name) and function.id in functions)):
            yield node


class ReviewStagingTest(unittest.TestCase):
    def test_every_subprocess_declares_standard_input(self):
        # Prove that both embedded forms and imported aliases reach the guard.
        with tempfile.TemporaryDirectory() as tmp:
            shell = Path(tmp) / "embedded.sh"
            shell.write_text("python3 - <<'PY'\nimport subprocess as sp\nsp.run([])\nPY\n"
                             "python3 -I -B -c 'from subprocess import Popen as child; child([])'\n")
            blocks = list(python_sources(shell))
            self.assertEqual(len(blocks), 2)
            for offset, source in blocks:
                calls = list(subprocess_calls(ast.parse(source)))
                self.assertEqual(len(calls), 1)
                self.assertFalse(any(keyword.arg == "stdin" for keyword in calls[0].keywords))
        violations = []
        allowed = set()
        for folder in ("scripts", "skills"):
            for path in sorted((REPO / folder).rglob("*")):
                if not path.is_file() or path.suffix not in (".py", ".sh"):
                    continue
                for offset, source in python_sources(path):
                    for call in subprocess_calls(ast.parse(source, filename=str(path))):
                        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
                        key = (path.relative_to(REPO).as_posix(), offset + call.lineno)
                        stdin = keywords.get("stdin")
                        inherits = isinstance(stdin, ast.Constant) and stdin.value is None
                        # run(input=...) creates its own PIPE; Python forbids stdin=PIPE with input=.
                        supplied_input = keywords.get("input")
                        if inherits and supplied_input is not None and not (
                                isinstance(supplied_input, ast.Constant) and supplied_input.value is None):
                            inherits = False
                        if "stdin" not in keywords or inherits:
                            reason = INHERITED_STDIN_ALLOWLIST.get(key)
                            if reason and reason.strip():
                                allowed.add(key)
                            else:
                                violations.append(f"{key[0]}:{key[1]}: explicit stdin required")
        self.assertFalse(violations, "\n".join(violations))
        self.assertEqual(allowed, set(INHERITED_STDIN_ALLOWLIST), "remove unused stdin exceptions")

    def test_staging_finishes_while_caller_standard_input_stays_open(self):
        read_fd, write_fd = os.pipe()
        try:
            with subprocess.Popen([sys.executable, "-B", str(REPO / "scripts/check_review_staging.py")],
                                  stdin=read_fd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  start_new_session=True) as child:
                try:
                    output, errors = child.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    output, errors = child.communicate()
                    self.fail(f"staging blocked on open stdin: {output!r} {errors!r}")
                self.assertEqual(child.returncode, 0, output + errors)
                self.assertIn(b"OK: roles and lenses prepared", output)
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_a_fixture_commit_starts_no_background_maintenance(self):
        with tempfile.TemporaryDirectory() as folder:
            trace = Path(folder) / "git-trace"
            repo = Path(folder) / "repo"
            repo.mkdir()
            (repo / "a.txt").write_text("a\n")
            with unittest.mock.patch.dict(os.environ, {"GIT_TRACE": str(trace)}):
                for args in (["git", "init", "-q", "-b", "main"], ["git", "add", "a.txt"], ["git", "commit", "-qm", "a"]):
                    self.assertEqual(check_review_staging.run(args, repo).returncode, 0)
            self.assertIn("git commit", trace.read_text())
            self.assertNotIn("maintenance run", trace.read_text())  # Git would start one, detached, after the commit

    def test_this_checkout_prepares_every_role_and_lens(self):
        self.assertEqual(check_review_staging.check(REPO), [])

    def test_role_including_an_unstaged_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("prompts", "rules", "skills"):
                shutil.copytree(REPO / folder, root / folder)
            role = root / "prompts/roles/triager.md"
            role.write_text(role.read_text() + "@rule house-rules:skills/operator-writing/SKILL.md\n")
            failures = check_review_staging.check(root)
            self.assertTrue(any(f.startswith("role triager:") for f in failures), failures)

    def test_missing_matching_checker_fails_documentation_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in check_review_staging.STAGED:
                shutil.copytree(REPO / folder, root / folder)
            (root / "skills/spec-writing/scripts/spec_docs.py").unlink()
            failures = check_review_staging.check(root)
            self.assertTrue(any(f.startswith("documentation staging:") for f in failures), failures)


if __name__ == "__main__":
    unittest.main()
