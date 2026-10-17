#!/usr/bin/env python3
"""Local integration tests: no network, GitHub writes or model calls."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("prepare.py")
SPEC = importlib.util.spec_from_file_location("prepare", SCRIPT)
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class PrepareTests(unittest.TestCase):
    def setUp(self):
        scratch = SCRIPT.parents[3] / ".tmp"
        scratch.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # Ignore host Git aliases, hooks, signing and credentials; fetches use local remotes.
        self.env = mock.patch.dict(os.environ, {
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Test Author", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test Author", "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.binaries = self.root / "bin"
        self.binaries.mkdir()
        self.fixtures = self.root / "gh.json"
        self.fixtures.write_text("{}")
        self.gh_log = self.root / "gh.log"
        stub = self.binaries / "gh"
        stub.write_text("#!" + sys.executable + "\n" + r"""import json, os, pathlib, sys
args = sys.argv[1:]
assert args[:2] == ['pr', 'view'] or args[:3] == ['api', '--method', 'GET'], args
with open(os.environ['GH_TEST_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\n')
fixtures = json.loads(pathlib.Path(os.environ['GH_TEST_FIXTURES']).read_text())
key = ' '.join(args)
if key not in fixtures:
    print('Unexpected gh request: ' + key, file=sys.stderr)
    sys.exit(2)
value = fixtures[key]
if isinstance(value, dict) and '_error' in value:
    print(value['_error'], file=sys.stderr)
    sys.exit(1)
print(json.dumps(value))
""")
        stub.chmod(0o755)
        patch = mock.patch.dict(os.environ, {
            "PATH": str(self.binaries) + os.pathsep + os.environ["PATH"],
            "GH_TEST_FIXTURES": str(self.fixtures), "GH_TEST_LOG": str(self.gh_log),
        })
        patch.start()
        self.addCleanup(patch.stop)
        self.origin = self.root / "origin"
        self.origin.mkdir()
        self.git(self.origin, "init", "-b", "trunk")
        self.write(self.origin, "src/core.py", "def action():\n    return 1\n")
        self.commit(self.origin, "Initial")
        self.repo = self.root / "checkout"
        self.git(self.root, "clone", str(self.origin), str(self.repo))
        self.git(self.repo, "checkout", "-b", "feature")

    def run_quick(self, env_extra=None):
        env = dict(os.environ, REVIEW_PANEL_CONF=str(self.root / "none.conf"), **(env_extra or {}))
        prompt = self.root / "prompt.txt"
        prompt.write_text("review\n")
        return subprocess.run(["bash", str(SCRIPT.with_name("quick-review.sh")), "quick",
                               str(self.repo), str(prompt)], capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)

    def test_quick_review_refuses_binary_changes_even_before_text(self):
        (self.repo / "blob.bin").write_bytes(bytes(range(256)) * 4)
        self.write(self.repo, "notes.md", "".join(f"line {i}\n" for i in range(400)))
        self.commit(self.repo, "Binary first, then text")
        result = self.run_quick()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("binary files", result.stderr)

    def test_quick_review_refuses_oversized_and_invalid_limits(self):
        self.write(self.repo, "notes.md", "".join(f"line {i}\n" for i in range(400)))
        self.commit(self.repo, "Large text change")
        oversized = self.run_quick()
        self.assertEqual(oversized.returncode, 2, oversized.stderr)
        self.assertIn("exceed 300", oversized.stderr)
        invalid = self.run_quick({"QUICK_REVIEW_MAX_LINES": "9223372036854775808"})
        self.assertEqual(invalid.returncode, 2, invalid.stderr)
        self.assertIn("whole number", invalid.stderr)

    def git(self, repo, *args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True,
                              capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip()

    def write(self, repo, name, content):
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    def commit(self, repo, subject):
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", subject)

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = prepare.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def review(self, **kwargs):
        args = dict(pr=None, issue=[], spec=None, tests=None, test_prefix="PT", lens="generalist-a",
                    summary=None, format=None, cli="codex")
        args.update(kwargs)
        return prepare.review(self.repo, argparse.Namespace(**args), "origin/trunk", "origin")

    def test_panel_task_context_ignores_replacement_blobs_in_direct_and_streamed_reads(self):
        self.write(self.repo, "src/core.py", "def action():\n    return 2\n")
        self.commit(self.repo, "Change action")
        original = self.git(self.repo, "rev-parse", "HEAD:src/core.py")
        baseline = self.review(context_only=True, format="diff", cli="grok")
        replacement = subprocess.run(["git", "-C", str(self.repo), "hash-object", "-w", "--stdin"],
                                     stdin=None, input=b"Replacement canary\n", capture_output=True,
                                     check=True, timeout=5).stdout.decode().strip()
        self.git(self.repo, "replace", original, replacement)
        self.assertEqual(self.review(context_only=True, format="diff", cli="grok"), baseline)
        self.assertEqual(prepare.git(self.repo, "show", "HEAD:src/core.py"), "def action():\n    return 2\n")

    def test_context_preparation_does_not_execute_the_live_compiler(self):
        scripts = self.root / "live-scripts"
        scripts.mkdir()
        shutil.copyfile(SCRIPT, scripts / "prepare.py")
        (scripts / "prompt.py").write_text("print('DIRTY COMPILER CANARY')\nraise RuntimeError('live import')\n")
        result = subprocess.run([sys.executable, "-B", str(scripts / "prepare.py"),
                                 "review", str(self.repo), "--context-only", "--base", "origin/trunk",
                                 "--no-fetch"], capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DIRTY COMPILER CANARY", result.stdout)
        self.assertIn("# 3. Pull request and issue", result.stdout)

    def github(self, pr=None, issues=(), pr_comments=(), review_comments=(), reviews=(), issue_comments=None):
        self.git(self.repo, "remote", "set-url", "origin", "https://github.com/example/project.git")
        data = {}
        pr_value = pr or {"_error": "no pull requests found for branch feature"}
        for arg in ("", "1 "):
            data[f"pr view {arg}--json url,title,body"] = pr_value
        def comments(endpoint, values):
            data[f"api --method GET --paginate --slurp repos/{endpoint}?per_page=100"] = values
        if pr:
            comments("example/project/issues/1/comments", [list(pr_comments)])
            comments("example/project/pulls/1/comments", [list(review_comments)])
            comments("example/project/pulls/1/reviews", [list(reviews)])
        for issue in issues:
            location = issue["html_url"].removeprefix("https://github.com/")
            data[f"api --method GET repos/{location}"] = issue
            comments(location + "/comments", (issue_comments or {}).get(issue["number"], [[]]))
        self.fixtures.write_text(json.dumps(data))

    def pr(self, body):
        return {"url": "https://github.com/example/project/pull/1", "title": "Change title", "body": body}

    def issue(self, number, body="Issue requirement", owner_repo="example/project"):
        return {"number": number, "title": f"Requirement {number}", "body": body,
                "html_url": f"https://github.com/{owner_repo}/issues/{number}", "labels": [{"name": "acceptance"}]}

    def comment(self, number, association="MEMBER", login="maintainer", user_type="User", body=None):
        return {"html_url": f"https://github.com/example/project/issues/2#issuecomment-{number}",
                "author_association": association, "user": {"login": login, "type": user_type},
                "created_at": f"2026-01-{number:02d}T00:00:00Z", "body": body or f"Comment body {number}"}

    def test_null_pr_and_issue_bodies_are_empty(self):
        for pr_body in (None, "Refs #2"):
            with self.subTest(pr_body=pr_body):
                self.github(self.pr(pr_body), [self.issue(2, None)])
                prompt = self.review(issue=["2"])
                self.assertIn("Change title", prompt)
                self.assertIn("Requirement 2", prompt)
                # Inspect PR/issue context, not the review instructions ("None.").
                context = prompt.split("# 3. Pull request and issue", 1)[1]
                self.assertNotIn("None", context)

    def test_credentials_are_redacted_from_git_warnings_errors_and_prompts(self):
        url = "https://test-user:fake-password@github.com/example/project.git?access_token=fake-token&x=1&author=ada&authkey=fake-authkey&api_key=fake-prefix)fake-secret-tail"
        diagnostic = "fatal: unable to access '" + url + "'"
        self.git(self.repo, "remote", "set-url", "origin", url)
        real_run = prepare.run
        def offline(repo, *args):
            if args[:2] in (("git", "ls-remote"), ("git", "fetch")):
                return subprocess.CompletedProcess(args, 1, "", diagnostic)
            return real_run(repo, *args)
        outputs = []
        with mock.patch.object(prepare, "run", side_effect=offline):
            for base in (None, "origin/trunk"):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    prepare.resolve_base(self.repo, base)
                outputs.append(err.getvalue())
        with mock.patch.object(prepare, "run", return_value=subprocess.CompletedProcess([], 1, "", diagnostic)):
            with self.assertRaises(prepare.PrepareError) as caught:
                prepare.git(self.repo, "status")
            outputs.append(str(caught.exception))
        self.github(self.pr("Remote: " + url))
        data = json.loads(self.fixtures.read_text())
        data["api --method GET --paginate --slurp repos/example/project/pulls/1/reviews?per_page=100"] = {"_error": diagnostic}
        self.fixtures.write_text(json.dumps(data))
        outputs.append(self.review())
        for output in outputs:
            with self.subTest(output_kind=output[:30]):
                for secret in ("test-user", "fake-password", "fake-token", "fake-authkey", "fake-prefix", "fake-secret-tail"):
                    self.assertNotIn(secret, output)
                self.assertIn("github.com", output)
                self.assertIn("x=1", output)
                self.assertIn("author=ada", output)

    def test_query_credentials_end_at_query_separators(self):
        for separator in ("&x=1", "#section", ""):
            with self.subTest(separator=separator):
                url = "https://example.invalid/?api_key=fake-prefix)fake-tail" + separator
                self.assertEqual(prepare.redact(url),
                                 "https://example.invalid/?api_key=[REDACTED]" + separator)

    def test_query_redaction_handles_long_question_mark_runs(self):
        # Bound the old quadratic failure without leaving a stuck test process.
        code = """import sys
sys.path.insert(0, sys.argv[1])
from prepare import redact
noise = '?' * 300_000
assert redact(noise) == noise
assert redact(noise + 'api_key=fake)tail&x=1') == noise + 'api_key=[REDACTED]&x=1'
"""
        try:
            result = subprocess.run([sys.executable, "-c", code, str(SCRIPT.parent)],
                                    capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            self.fail("redaction rescans a 300,000-character query-start run")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_query_author_is_not_an_auth_credential(self):
        for key in ("auth", "authorization", "oauth", "client_auth", "authkey",
                    "accesskey", "privateKey", "api_key", "api-key", "auth%6bey",
                    "accessToken", "clientSecret", "dbPassword", "clientpasswd"):
            with self.subTest(key=key):
                text = f"?author=ada&{key}=fake-credential&x=1"
                self.assertEqual(prepare.redact(text),
                                 f"?author=ada&{key}=[REDACTED]&x=1")

    def test_size_guard_counts_emitted_escaped_spec_and_newline(self):
        path = self.repo / "spec.md"
        path.write_bytes(b"## 1 Behavior\n" + b"\xff" * 300_000)
        self.commit(self.repo, "Add spec")
        code, out, err = self.invoke("review", str(self.repo), "--base", "origin/trunk", "--no-fetch", "--spec", "spec.md")
        self.assertEqual(code, 0, err)
        self.assertLessEqual(len(out), prepare.CODEX_LIMIT)
        self.assertIn("trimmed R1 (spec)", out)
        self.assertIn(r"\xff", out)
        # The final newline is part of the measured emitted representation too.
        with mock.patch.object(prepare, "CODEX_LIMIT", len(out) - 1):
            code, smaller, err = self.invoke("review", str(self.repo), "--base", "origin/trunk", "--no-fetch", "--spec", "spec.md")
        self.assertEqual(code, 0, err)
        self.assertLessEqual(len(smaller), len(out) - 1)

    def test_oversized_spec_fails_without_reading_blob_or_claiming_missing_sections(self):
        self.write(self.repo, "docs/spec.md", "## 2 Small\nNeeded\n## 3 Appendix\n" + "x" * 2_000_001)
        self.commit(self.repo, "Add large spec")
        real_run = prepare.run
        def no_blob_read(repo, *args):
            if args[:2] == ("git", "show") and args[2].endswith(":docs/spec.md"):
                self.fail("oversized spec blob was read")
            return real_run(repo, *args)
        with mock.patch.object(prepare, "run", side_effect=no_blob_read) as calls:
            for selector in ([], ["--spec", "docs/spec.md"]):
                code, prompt, err = self.invoke("review", str(self.repo), "--base", "origin/trunk",
                                                "--no-fetch", "--tests", "PT1", *selector)
                self.assertEqual(code, 1, err)
                self.assertEqual(prompt, "")
                self.assertIn("docs/spec.md", err)
                self.assertIn(f"{(self.repo / 'docs/spec.md').stat().st_size:,} bytes", err)
                self.assertIn("2,000,000 bytes", err)
                self.assertNotIn("not found", err)
        self.assertTrue(any(call.args[1:3] == ("git", "cat-file") and "-s" in call.args for call in calls.call_args_list))

    def test_markdown_mentions_match_whole_paths_only(self):
        for path in ("README.md", "docs/named.md", "docs/design.md"):
            self.write(self.repo, path, "## 1 Behavior\n" + path)
        self.commit(self.repo, "Add docs")
        for mention in ("docs/README.md", "prefix/docs/named.md", "prefix+docs/named.md", "docs/named.md/extra", "https://[invalid/docs/named.md", "https://github.com/example/project/blob/main/prefix/docs/named.md"):
            with self.subTest(mention=mention):
                self.github(self.pr("See " + mention))
                self.assertIn("Design/spec docs/design.md", self.review())
        for mention in ("`docs/named.md`", "[design](docs/named.md#1)", "https://github.com/example/project/blob/main/docs/named.md", "https://raw.githubusercontent.com/example/project/main/docs/named.md", "https://gitlab.com/example/project/-/blob/main/docs/named.md"):
            with self.subTest(mention=mention):
                self.github(self.pr("See " + mention))
                self.assertIn("Design/spec docs/named.md", self.review())

    def test_unknown_panel_cli_fails_reviewer(self):
        summary, output, env = self.panel_fixture()
        Path(env["REVIEW_PANEL_CONF"]).write_text("a = codexx test-model - high\n")
        env["REVIEW_BASE"] = "origin/trunk"
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "unknown-cli", str(self.repo), str(summary), "generalist-a"], capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertNotEqual(result.returncode, 0)
        recorded = (output / "unknown-cli" / "summary.txt").read_text()
        self.assertIn("generalist-a failed:", recorded)
        self.assertNotIn("skipped", recorded)

    def test_repository_url_specs_resolve_host_routes_and_complete_refs(self):
        for path in ("docs/named.md", "docs/design.md"):
            self.write(self.repo, path, "## 1 Behavior\n" + path)
        self.commit(self.repo, "Add docs")
        self.git(self.repo, "branch", "-m", "work")
        self.git(self.repo, "branch", "feature/topic")
        self.git(self.repo, "update-ref", "refs/remotes/origin/release/topic", "HEAD")
        self.git(self.repo, "tag", "version/topic")
        routes = ("https://github.com/example/project/blob/",
                  "https://www.github.com/example/project/raw/",
                  "https://gitlab.com/group/subgroup/project/-/blob/",
                  "https://www.gitlab.com/group/subgroup/project/-/raw/",
                  "https://raw.githubusercontent.com/example/project/",
                  "https://bitbucket.org/example/project/src/")
        for route in routes:
            for ref in ("main", "feature/topic", "feature%2Ftopic", "release/topic", "version/topic"):
                with self.subTest(route=route, ref=ref):
                    path = prepare.discover_spec(self.repo, "HEAD", None,
                                                 [route + ref + "/docs/named.md#L1"], [])
                    self.assertEqual(path, "docs/named.md")

    def test_unresolved_repository_url_specs_are_visible_without_suffix_matches(self):
        for path in ("docs/named.md", "docs/design.md"):
            self.write(self.repo, path, "## 1 Behavior\n" + path)
        self.commit(self.repo, "Add docs")
        self.git(self.repo, "branch", "-m", "work")
        self.git(self.repo, "branch", "feature/topic")
        for tail in ("main/prefix/docs/named.md", "unknown/topic/docs/named.md",
                     "feature/topic/prefix/docs/named.md", "main/docs/absent.md"):
            with self.subTest(tail=tail):
                url = "https://gitlab.com/group/subgroup/project/-/blob/" + tail
                self.github(self.pr("See " + url))
                prompt = self.review()
                self.assertIn("not found: " + url, prompt.split("# 1. Review pack")[0])
                self.assertIn("Design/spec docs/design.md", prompt)
                self.assertNotIn("Design/spec docs/named.md", prompt)

    def test_prefixed_and_sentence_final_markdown_paths_are_whole_tokens(self):
        for path in ("docs/named.md", "docs/design.md"):
            self.write(self.repo, path, "## 1 Behavior\n" + path)
        self.commit(self.repo, "Add docs")
        files = [("1", "0", "docs/design.md")]
        for mention in ("./docs/named.md", "/docs/named.md", "docs/named.md."):
            with self.subTest(mention=mention):
                self.assertEqual(prepare.discover_spec(self.repo, "HEAD", None,
                                                       ["See " + mention], files), "docs/named.md")
        for mention in ("prefix/docs/named.md", "//docs/named.md", "../docs/named.md",
                        "docs/named.md.extra"):
            with self.subTest(mention=mention):
                self.assertEqual(prepare.discover_spec(self.repo, "HEAD", None,
                                                       ["See " + mention], files), "docs/design.md")

    def test_prefixed_design_paths_outrank_ordinary_mentions(self):
        for path in ("docs/other.md", "docs/spec.md"):
            self.write(self.repo, path, "## 1 Behavior\n" + path)
        self.commit(self.repo, "Add docs")
        for prefix in ("", "./", "/"):
            design = f"Design: {prefix}docs/spec.md [§1]"
            for texts in (["See docs/other.md\n" + design], ["See docs/other.md", design]):
                with self.subTest(prefix=prefix, texts=texts):
                    self.assertEqual(prepare.discover_spec(self.repo, "HEAD", None,
                                                           texts, []), "docs/spec.md")

    def test_panel_invalid_checkout_leaves_outputs_untouched(self):
        summary, output, env = self.panel_fixture()
        panel = output / "invalid-checkout"
        panel.mkdir(parents=True)
        saved = panel / "summary.txt"
        saved.write_text("previous run\n")
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), panel.name,
                                 str(self.root / "absent"), str(summary), "generalist-a"],
                                capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(saved.read_text(), "previous run\n")

    def test_no_fetch_still_merges_resolved_base(self):
        self.write(self.repo, "feature.py", "pass\n")
        self.commit(self.repo, "Feature")
        feature = self.git(self.repo, "rev-parse", "HEAD")
        self.write(self.origin, "base.py", "pass\n")
        self.commit(self.origin, "Base")
        self.git(self.repo, "fetch", "origin")
        for command in ("fix", "pr"):
            for status, flags in (("owned", ()), ("external", ("--update",)), ("unknown", ("--update",))):
                with self.subTest(command=command, status=status), mock.patch.object(
                    prepare, "ownership", return_value=status + " example/project"
                ), mock.patch.object(prepare, "run", wraps=prepare.run) as calls:
                    self.git(self.repo, "checkout", "-B", "feature", feature)
                    code, out, err = self.invoke(command, str(self.repo), "--base", "origin/trunk", "--no-fetch", *flags)
                    self.assertEqual(code, 0, err)
                    self.assertEqual(self.git(self.repo, "rev-list", "--count", "HEAD..origin/trunk"), "0")
                    self.assertFalse(any(c.args[1:3] in (("git", "fetch"), ("git", "ls-remote")) for c in calls.call_args_list))

    def test_null_github_users_keep_maintainer_comments(self):
        comment = self.comment(1, body="Deleted maintainer requirement")
        comment["user"] = None
        self.github(self.pr("Change"), pr_comments=[comment], review_comments=[comment], reviews=[comment])
        prompt = self.review()
        self.assertIn("Maintainer comment by unknown", prompt)
        self.assertIn("Deleted maintainer requirement", prompt)
        self.assertIn("unknown", prompt.split("# 1. Review pack")[0])

    def test_git_and_gh_are_noninteractive(self):
        stub = "#!" + sys.executable + "\n" + "import os, sys\nprint(os.environ.get('GIT_TERMINAL_PROMPT'), os.environ.get('GH_PROMPT_DISABLED'), sys.stdin.read())\n"
        (self.binaries / "git").write_text(stub)
        (self.binaries / "git").chmod(0o755)
        (self.binaries / "gh").write_text("#!" + sys.executable + "\nimport json, os, sys\n"
                                           "print(json.dumps([os.environ.get('GIT_TERMINAL_PROMPT'), os.environ.get('GH_PROMPT_DISABLED'), sys.stdin.read()]))\n")
        with mock.patch.dict(os.environ, {"GIT_TERMINAL_PROMPT": "1", "GH_PROMPT_DISABLED": "0"}):
            with self.subTest(cli="git"):
                self.assertEqual(prepare.run(self.repo, "git", "fetch").stdout.strip(), "0 1")
            with self.subTest(cli="gh"):
                self.assertEqual(prepare.gh_json(self.repo, "pr", "view"), ["0", "1", ""])

    def test_non_utf8_paths_keep_the_actual_diff(self):
        path = os.fsdecode(b"src/non-utf8-\xff.py")
        # Build the real Git tree directly: macOS cannot create this filesystem name.
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], stdin=None, cwd=self.repo,
                              input=b"unique_non_utf8_marker = 1\n", capture_output=True, check=True).stdout.strip()
        subprocess.run(["git", "update-index", "-z", "--index-info"], stdin=None, cwd=self.repo,
                       input=b"100644 " + blob + b"\t" + os.fsencode(path) + b"\0", check=True)
        self.git(self.repo, "commit", "-m", "Non UTF8 filename")
        files = prepare.changed_files(self.repo, "origin/trunk...HEAD")
        self.assertEqual(files[0][2], path)
        for mode in ("structured", "diff", "pack"):
            with self.subTest(mode=mode):
                output = prepare.change_part(self.repo, "origin/trunk...HEAD", files,
                                             "https://github.com/example/project", "HEAD", mode)
                self.assertIn("@@ -", output)
                self.assertIn("%FF.py", output)
                output.encode("utf-8")
                if mode != "pack":
                    self.assertIn("+unique_non_utf8_marker = 1", output)

    def test_explicit_missing_pr_or_issue_is_an_error(self):
        self.github()
        fixtures = json.loads(self.fixtures.read_text())
        fixtures["pr view missing-branch --json url,title,body"] = {"_error": "no pull requests found"}
        fixtures["api --method GET repos/example/project/issues/77"] = {"_error": "HTTP 404: Not Found"}
        self.fixtures.write_text(json.dumps(fixtures))
        for selector, value in (("--pr", "missing-branch"), ("--issue", "77")):
            with self.subTest(selector=selector):
                code, out, err = self.invoke("review", str(self.repo), "--base", "origin/trunk", "--no-fetch", selector, value)
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertIn(value, err)
        self.assertIn("# 1. Review pack", self.review())

    def test_panel_rejects_duplicate_reviewers_before_output_changes(self):
        summary, output, env = self.panel_fixture()
        panel = output / "duplicate"
        panel.mkdir(parents=True)
        (panel / "summary.txt").write_text("Existing summary")
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "duplicate",
                                 str(self.repo), str(summary), "generalist-a", "generalist-a"],
                                capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("duplicate reviewer", result.stderr)
        self.assertEqual((panel / "summary.txt").read_text(), "Existing summary")

    def test_panel_base_failure_is_recorded_in_a_fresh_directory(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "missing-ref"
        panel = output / "badbase"
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "badbase",
                                 str(self.repo), str(summary), "generalist-a"], capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("base resolution", (panel / "summary.txt").read_text())
        self.assertFalse(any(panel.glob("generalist-a.*")))

    def test_hyphens_are_part_of_acceptance_ids(self):
        self.write(self.repo, "docs/spec.md", "## Tests\n| AT1-case | Extended ID |\n| AT1 | Exact ID |\n| AT10 | Other ID |\n")
        self.commit(self.repo, "Implement AT1-case")
        prompt = self.review(tests="AT1", test_prefix="AT")
        requirements = prompt.split("# 4. Requirements")[1].split("# 5. Change")[0]
        self.assertIn("| AT1 | Exact ID |", requirements)
        self.assertIn("| AT1-case |", requirements)
        self.assertIn("| AT10 |", requirements)
        self.assertNotIn("not found:", prompt)
        self.write(self.repo, "docs/spec.md", "## Tests\n| AT1-case | Extended ID |\n| AT10 | Other ID |\n")
        self.commit(self.repo, "Remove exact acceptance ID")
        prompt = self.review(tests="AT1", test_prefix="AT")
        self.assertIn("not found: AT1", prompt.split("# 1. Review pack")[0])
        prompt = self.review(test_prefix="AT", spec="absent.md")
        self.assertNotIn("AT1", prompt.split("# 1. Review pack")[0])

    def test_spec_selection_reads_no_unselected_documents(self):
        for path in ("README.md", "docs/spec.md", "docs/other.md"):
            self.write(self.repo, path, "## 1 Behavior\nRequired\n")
        self.commit(self.repo, "Baseline documents")
        self.git(self.repo, "update-ref", "refs/remotes/origin/trunk", "HEAD")
        self.write(self.repo, "src/core.py", "pass\n")
        self.commit(self.repo, "Implement §1")
        with mock.patch.object(prepare, "run", wraps=prepare.run) as calls:
            prompt = self.review()
        self.assertNotIn("Design/spec", prompt)
        self.assertFalse(any(c.args[1:3] == ("git", "show") for c in calls.call_args_list))
        self.git(self.repo, "commit", "--allow-empty", "-m", "Requirements\n\nDesign: docs/spec.md [§1]")
        self.github(self.pr("See README.md"))
        with mock.patch.object(prepare, "run", wraps=prepare.run) as calls:
            prompt = self.review()
        self.assertIn("Design/spec docs/spec.md", prompt)
        reads = [c.args[3] for c in calls.call_args_list if c.args[1:3] == ("git", "show")]
        self.assertEqual(reads, [self.git(self.repo, "rev-parse", "HEAD") + ":docs/spec.md"])

    def test_briefs_list_files_without_reading_stack_manifests(self):
        for path in ("Cargo.toml", "CMakeLists.txt", "tests/test_core.py", "docs/guide.md"):
            self.write(self.repo, path, "invalid manifest contents\n")
        self.commit(self.repo, "Mixed change")
        for command in ("fix", "pr"):
            with self.subTest(command=command):
                code, out, err = self.invoke(command, str(self.repo), "--base", "origin/trunk", "--no-fetch")
                self.assertEqual(code, 0, err)
                for entry in ("source: Cargo.toml", "source: CMakeLists.txt", "test: tests/test_core.py", "docs: docs/guide.md"):
                    self.assertIn(entry, out)
                self.assertIn("declared gates in AGENTS.md and the rules file it points to", out)
                self.assertNotIn("cargo test", out)
                self.assertNotIn("ctest", out)
                self.assertNotIn("pytest", out)

    def test_changed_paths_are_literal_in_every_format(self):
        paths = ["prepar[e].py", "prepare.py", ":(glob)*.py", "star*.py", "starx.py",
                 "question?.py", "questionx.py", "-option.py", "tab\tname.py", "line\nname.py"]
        for n, path in enumerate(paths):
            self.write(self.repo, path, f"unique_marker_{n} = {n}\n")
        self.commit(self.repo, "Literal paths")
        files = prepare.changed_files(self.repo, "origin/trunk...HEAD")
        for mode in ("structured", "diff", "pack"):
            for n, path in enumerate(paths):
                with self.subTest(mode=mode, path=path):
                    selected = [row for row in files if row[2] == path]
                    output = prepare.change_part(self.repo, "origin/trunk...HEAD", selected, None, "HEAD", mode)
                    self.assertEqual(output.count("@@ -"), 1)
                    if mode != "pack":
                        self.assertIn(f"+unique_marker_{n} = {n}", output)
                        self.assertEqual(output.count("+unique_marker_"), 1)

    def test_offline_uses_cached_default_and_skips_merge_for_all_commands(self):
        self.git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.git(self.repo, "remote", "set-url", "origin", str(self.root / "offline"))
        for command in ("review", "fix", "pr"):
            with self.subTest(command=command), mock.patch.object(prepare, "update") as update:
                code, out, err = self.invoke(command, str(self.repo))
                self.assertEqual(code, 0, err)
                head = self.git(self.repo, "rev-parse", "HEAD") if command == "review" else "HEAD"
                self.assertIn(f"origin/trunk...{head}", out)
                self.assertIn("cached", err)
                update.assert_not_called()

    def test_failed_fetch_preserves_selected_base_and_skips_merge(self):
        original = prepare.run
        def fail_fetch(repo, *args):
            if args[:2] == ("git", "fetch"):
                return subprocess.CompletedProcess(args, 1, "", "network unavailable")
            return original(repo, *args)
        for command in ("review", "fix", "pr"):
            with self.subTest(command=command), mock.patch.object(prepare, "run", side_effect=fail_fetch), mock.patch.object(prepare, "update") as update:
                code, out, err = self.invoke(command, str(self.repo), "--base", "origin/trunk")
                self.assertEqual(code, 0, err)
                head = self.git(self.repo, "rev-parse", "HEAD") if command == "review" else "HEAD"
                self.assertIn(f"origin/trunk...{head}", out)
                self.assertIn("cached", err)
                update.assert_not_called()

    def test_explicit_local_base_never_fetches(self):
        with mock.patch.object(prepare, "run", wraps=prepare.run) as calls:
            code, out, err = self.invoke("fix", str(self.repo), "--base", "HEAD")
        self.assertEqual(code, 0, err)
        self.assertFalse(any(c.args[1:3] == ("git", "fetch") for c in calls.call_args_list))

    def test_no_fetch_uses_the_supplied_base_without_network(self):
        with mock.patch.object(prepare, "run", wraps=prepare.run) as calls:
            code, out, err = self.invoke("review", str(self.repo), "--base", "origin/trunk", "--no-fetch")
        self.assertEqual(code, 0, err)
        self.assertFalse(any(c.args[1:3] in (("git", "fetch"), ("git", "ls-remote")) for c in calls.call_args_list))
        code, out, err = self.invoke("review", str(self.repo), "--no-fetch")
        self.assertEqual(code, 1)
        self.assertIn("--no-fetch requires --base", err)

    def test_rewritten_remote_default_is_fetched(self):
        self.git(self.origin, "checkout", "--orphan", "replacement")
        self.write(self.origin, "new.py", "pass\n")
        self.commit(self.origin, "Rewritten default")
        self.git(self.origin, "branch", "-M", "trunk")
        base = prepare.resolve_base(self.repo)[0]
        self.assertEqual(self.git(self.repo, "rev-parse", base), self.git(self.origin, "rev-parse", "HEAD"))

    def test_nonexistent_named_specs_do_not_hide_real_tree_paths(self):
        self.add_review_change()
        files = prepare.changed_files(self.repo, "origin/trunk...HEAD")
        for text in ("See changelog.md", "Design: absent.md [§2]"):
            with self.subTest(text=text):
                self.assertEqual(prepare.discover_spec(self.repo, "HEAD", None, [text], files), "docs/design.md")
        self.assertIsNone(prepare.discover_spec(self.repo, "HEAD", "absent.md", [], files))

    def test_oxford_comma_issue_lists(self):
        self.assertEqual(prepare.issue_refs("Resolves #2, #3, and #4"), ["#2", "#3", "#4"])

    def test_qualified_issue_references_ignore_paths_and_anchors(self):
        cases = (
            ("Tracked in symbiotic-sh/warden#267.", ["symbiotic-sh/warden#267"]),
            ("(see owner/repo#12)", ["owner/repo#12"]),
            ("https://github.com/o/r/blob/abc/skills/design-flow/SKILL.md#5-implement", []),
            ("[guide](skills/design-flow/SKILL.md#5)", []),
            ("docs/a/b.md#3 and ../x/y.md#4", []),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(prepare.issue_refs(text), expected)

    def test_large_diff_memory_is_bounded_before_pack_fallback(self):
        self.write(self.repo, "large.py", "# " + "x" * 12_000_000 + "\n")
        self.commit(self.repo, "Large line")
        for mode in ("pack", "structured"):
            with self.subTest(mode=mode):
                tracemalloc.start()
                try:
                    prompt = self.review(format=mode)
                    peak = tracemalloc.get_traced_memory()[1]
                finally:
                    tracemalloc.stop()
                self.assertLess(peak, 6_000_000, f"peak memory: {peak}")
                self.assertIn("Touched functions", prompt)
                self.assertNotIn("x" * 1000, prompt)

    def panel_source(self):
        """Commit the running compiler and synthetic panel inputs in a local clone."""
        source = self.root / "panel-source"
        if source.exists():
            return
        source.mkdir()
        self.git(source, "init", "-b", "main")
        for folder in ("prompts", "rules"):
            shutil.copytree(SCRIPT.parents[3] / folder, source / folder)
        for name in ("prompt.py", "prepare.py", "review-panel.lenses"):
            dest = source / "skills/pr-ready/scripts" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SCRIPT.with_name(name), dest)
        self.commit(source, "Panel source")
        env = mock.patch.dict(os.environ, {
            "REVIEW_HOUSE_RULES_REPO": str(source),
            "REVIEW_HOUSE_RULES_REV": self.git(source, "rev-parse", "HEAD"),
        })
        env.start()
        self.addCleanup(env.stop)

    def test_panel_pack_preparation_never_imports_checkout_hashlib(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        env["PYTHONPATH"] = str(self.repo)
        marker = self.root / "checkout-hashlib-executed"
        self.write(self.repo, "hashlib.py",
                   "from pathlib import Path\n"
                   f"Path({str(marker)!r}).write_text('checkout module executed')\n"
                   "raise RuntimeError('checkout hashlib imported')\n")
        stub = self.binaries / "codex"
        stub.write_text("#!/bin/sh\n"
                        "while [ \"$1\" != '-o' ]; do shift; done\n"
                        "printf 'VERDICT: APPROVE\\n' > \"$2\"\n"
                        "cat > /dev/null\n")
        stub.chmod(0o755)
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "isolated",
                                 str(self.repo), str(summary), "generalist-a"],
                                cwd=self.repo, capture_output=True, text=True, timeout=10, env=env, stdin=subprocess.DEVNULL)
        self.assertFalse(marker.exists(), result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        pack = output / "isolated" / "generalist-a.pack"
        self.assertIn(summary.read_bytes(), (pack / "pack.txt").read_bytes())
        self.assertEqual(json.loads((pack / "manifest.json").read_text())["house_rules_revision"],
                         env["REVIEW_HOUSE_RULES_REV"])

    def test_panel_keeps_first_commit_when_head_moves_before_context(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        self.write(self.repo, "AGENTS.md", "FIRST RULES\n")
        self.write(self.repo, "docs/spec.md", "FIRST SPEC\n")
        self.write(self.repo, "src/core.py", "first_change = 2\n")
        self.commit(self.repo, "First title\n\nDesign: docs/spec.md")
        first = self.git(self.repo, "rev-parse", "HEAD")
        real_git = shutil.which("git")
        # Metadata selection starts after target-rule compilation. Move HEAD at
        # that boundary without sleeps or concurrent timing.
        wrapper = self.binaries / "git"
        wrapper.write_text("#!" + sys.executable + "\n" +
                          "import os, pathlib, subprocess, sys\n" +
                          "args = sys.argv[1:]\n" +
                          "if args[-1:] == [':(literal)docs/ENTITIES.json']:\n" +
                          f"    repo = pathlib.Path({str(self.repo)!r})\n" +
                          "    for path, body in [('AGENTS.md', 'SECOND RULES\\n'), " +
                          "('docs/spec.md', 'SECOND SPEC\\n'), ('src/core.py', 'second_change = 3\\n')]:\n" +
                          "        (repo / path).write_text(body)\n" +
                          f"    subprocess.run([{real_git!r}, '-C', str(repo), 'add', " +
                          "'AGENTS.md', 'docs/spec.md', 'src/core.py'], check=True, timeout=5, stdin=subprocess.DEVNULL)\n" +
                          f"    subprocess.run([{real_git!r}, '-C', str(repo), 'commit', '-m', " +
                          "'Second title\\n\\nDesign: docs/spec.md'], check=True, timeout=5, " +
                          "stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL)\n" +
                          f"os.execv({real_git!r}, [{real_git!r}, *args])\n")
        wrapper.chmod(0o755)
        stub = self.binaries / "codex"
        stub.write_text("#!/bin/sh\n"
                        "while [ \"$1\" != '-o' ]; do shift; done\n"
                        "printf 'VERDICT: APPROVE\\n' > \"$2\"\n"
                        "cat > /dev/null\n")
        stub.chmod(0o755)
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "moving-head",
                                 str(self.repo), str(summary), "generalist-a"],
                                capture_output=True, text=True, timeout=10, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        second = self.git(self.repo, "rev-parse", "HEAD")
        self.assertNotEqual(first, second)
        pack = output / "moving-head" / "generalist-a.pack"
        manifest = json.loads((pack / "manifest.json").read_text())
        self.assertEqual(manifest["target"]["commit"], first)
        prompt = (pack / "pack.txt").read_text()
        self.assertIn("FIRST RULES", prompt)
        self.assertIn(f"Range: `origin/trunk...{first}`; head: `{first}`", prompt)
        self.assertIn("Title: First title", prompt)
        self.assertIn("FIRST SPEC", prompt)
        self.assertIn("+first_change = 2", prompt)
        self.assertIn("Commit message " + first[:12], prompt)
        self.assertNotIn(second, prompt)
        for canary in ("SECOND RULES", "SECOND SPEC", "Second title", "second_change"):
            self.assertNotIn(canary, prompt)

    def test_panel_prompts_come_from_named_commit_and_manifest_matches_sent_bytes(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        stub = self.binaries / "codex"
        stub.write_text("#!/usr/bin/env python3\nimport pathlib, sys\n"
                        "args = sys.argv[1:]\n"
                        "data = sys.stdin.buffer.read()\n"
                        "pathlib.Path(args[args.index('-o') + 1]).with_suffix('.sent').write_bytes(data)\n"
                        "pathlib.Path(args[args.index('-o') + 1]).write_text('VERDICT: APPROVE')\n")
        stub.chmod(0o755)
        source = Path(env["REVIEW_HOUSE_RULES_REPO"])
        role = source / "prompts/roles/reviewer.md"
        role.write_text("DIRTY PANEL CANARY")
        for round_name in ("pinned", "branch", "replacement"):
            if round_name == "branch":
                self.commit(source, "Dirty role")
                self.git(source, "checkout", "-b", "other")
            if round_name == "replacement":
                compiler = source / "skills/pr-ready/scripts/prompt.py"
                original = self.git(source, "rev-parse", env["REVIEW_HOUSE_RULES_REV"] + ":skills/pr-ready/scripts/prompt.py")
                compiler.write_text("print('REPLACEMENT COMPILER CANARY')\n" + compiler.read_text())
                self.commit(source, "Replacement compiler")
                substitute = self.git(source, "rev-parse", "HEAD:skills/pr-ready/scripts/prompt.py")
                self.git(source, "replace", original, substitute)
                real_git = shutil.which("git")
                log = self.root / "extraction.log"
                recorder = self.binaries / "git"
                recorder.write_text("#!" + sys.executable + "\nimport json, os, sys\n"
                                    f"with open({str(log)!r}, 'a') as log: log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                                    f"os.execv({real_git!r}, ['git', *sys.argv[1:]])\n")
                recorder.chmod(0o755)
            result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), round_name,
                                     str(self.repo), str(summary), "generalist-a"],
                                    capture_output=True, text=True, timeout=10, env=env, stdin=subprocess.DEVNULL)
            self.assertEqual(result.returncode, 0, result.stderr)
            pack = output / round_name / "generalist-a.pack"
            data = (pack / "pack.txt").read_bytes()
            manifest = json.loads((pack / "manifest.json").read_text())
            self.assertEqual(manifest["house_rules_revision"], env["REVIEW_HOUSE_RULES_REV"])
            self.assertEqual(data, (output / round_name / "generalist-a.attempt-1.sent").read_bytes())
            self.assertEqual(manifest["pack"]["sha256"], __import__('hashlib').sha256(data).hexdigest())
            self.assertNotIn(b"DIRTY PANEL CANARY", data)
            self.assertIn(b"Repository rules: this repository has no rules of its own.", data)
            self.assertFalse((output / round_name / "generalist-a.task").exists())
            self.assertFalse((output / round_name / "lenses.conf").exists())
            if round_name == "replacement":
                calls = [json.loads(line) for line in log.read_text().splitlines()]
                extractions = [c for c in calls if "show" in c and
                               c[-1] == env["REVIEW_HOUSE_RULES_REV"] + ":skills/pr-ready/scripts/prompt.py"]
                self.assertEqual(len(extractions), 1, calls)
                self.assertEqual(extractions[0][0], "--no-replace-objects")
                self.assertEqual((output / round_name / "compiler.py").read_bytes(), SCRIPT.with_name("prompt.py").read_bytes())

    def test_context_budget_reserves_compiled_parts_and_keeps_trim_notices(self):
        self.write(self.repo, "docs/spec.md", "Spec\n" + "s" * 10_000)
        self.commit(self.repo, "Design: docs/spec.md")
        baseline = self.review(context_only=True, format="pack")
        overhead = 2000
        with mock.patch.object(prepare, "CODEX_LIMIT", len(baseline) + 1000):
            result = self.review(context_only=True, format="pack", compiled_chars=overhead)
            self.assertLessEqual(len(result) + overhead, prepare.CODEX_LIMIT)
            self.assertIn("Size guard: trimmed R1 (spec)", result)

    def test_codex_panel_compiles_each_requested_path_once_before_publication(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        summary.write_text("Review literal @rule house-rules:missing.md\nUnicode: café\n")
        stub = self.binaries / "codex"
        stub.write_text("#!/usr/bin/env python3\nimport pathlib, sys\n"
                        "args = sys.argv[1:]\n"
                        "pathlib.Path(args[args.index('-o') + 1]).with_suffix('.sent').write_bytes(sys.stdin.buffer.read())\n"
                        "pathlib.Path(args[args.index('-o') + 1]).write_text('VERDICT: APPROVE')\n")
        stub.chmod(0o755)
        real_git = shutil.which("git")
        log = self.root / "compilation.log"
        wrapper = self.binaries / "git"
        wrapper.write_text("#!" + sys.executable + "\nimport json, os, sys\n"
                           f"with open({str(log)!r}, 'a') as log: log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                           f"os.execv({real_git!r}, ['git', *sys.argv[1:]])\n")
        wrapper.chmod(0o755)
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "single-compile",
                                 str(self.repo), str(summary), "generalist-a"],
                                capture_output=True, text=True, timeout=10, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        panel = output / "single-compile"
        data = (panel / "generalist-a.pack/pack.txt").read_bytes()
        manifest = json.loads((panel / "generalist-a.pack/manifest.json").read_text())
        self.assertEqual(data, (panel / "generalist-a.attempt-1.sent").read_bytes())
        self.assertIn(summary.read_bytes(), data)
        self.assertEqual(manifest["pack"], {"bytes": len(data), "sha256": __import__('hashlib').sha256(data).hexdigest()})
        task = manifest["parts"][-1]
        task_bytes = data[-task["bytes"]:]
        self.assertEqual(task["source"], "review-panel-generalist-a")
        self.assertEqual(task["sha256"], __import__('hashlib').sha256(task_bytes).hexdigest())
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        lookups = [(c[c.index("-C") + 1], c[-1]) for c in calls
                   if "ls-tree" in c and c[-1].startswith(":(literal)")]
        expected = {(env["REVIEW_HOUSE_RULES_REPO"], ":(literal)" + p)
                    for p in ["skills/pr-ready/scripts/prompt.py", *[e["path"] for e in manifest["files"]]]}
        expected |= {(str(self.repo), ":(literal)" + p) for p in
                     ("AGENTS.md", ".agents/rules.md", "docs/ENTITIES.json", "docs/DOCUMENTS.json")}
        self.assertEqual(len(lookups), len(expected), lookups)
        self.assertEqual(set(lookups), expected)
        self.assertEqual(sum("--batch" in c for c in calls), 1, calls)

    def test_panel_size_budget_includes_pinned_rules_and_target_rules(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        summary.write_text("s" * (prepare.CODEX_LIMIT - 10_000))
        self.write(self.repo, "AGENTS.md", "Local rules\n" + "r" * 20_000)
        self.commit(self.repo, "Local rules")
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "rules-size",
                                 str(self.repo), str(summary), "generalist-a"],
                                capture_output=True, text=True, timeout=10, env=env, stdin=subprocess.DEVNULL)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("context preparation", (output / "rules-size/summary.txt").read_text())
        self.assertIn("800,000", (output / "rules-size/generalist-a.prepare.err").read_text())
        self.assertFalse((output / "rules-size/generalist-a.attempt-1.err").exists())

    def test_panel_checks_complete_prompt_before_dispatch(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        source = Path(env["REVIEW_HOUSE_RULES_REPO"])
        compiler = source / "skills/pr-ready/scripts/prompt.py"
        compiler.write_text(compiler.read_text().replace(
            '    manifest["pack"] = fingerprint(pack)',
            '    if tasks:\n        pack += b"x" * 800_001\n    manifest["pack"] = fingerprint(pack)'))
        self.commit(source, "Inject oversized final prompt")
        env["REVIEW_HOUSE_RULES_REV"] = self.git(source, "rev-parse", "HEAD")
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "final-size",
                                 str(self.repo), str(summary), "generalist-a"],
                                capture_output=True, text=True, timeout=10, env=env, stdin=subprocess.DEVNULL)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("complete prompt size", (output / "final-size/summary.txt").read_text())
        self.assertIn("800,000", (output / "final-size/generalist-a.prepare.err").read_text())
        self.assertFalse((output / "final-size/generalist-a.attempt-1.err").exists())

    def panel_fixture(self, summary_exists=True):
        self.panel_source()
        for cli in ("codex", "grok", "kimi"):
            stub = self.binaries / cli
            stub.write_text("#!/bin/sh\necho 'unexpected reviewer execution' >&2\nexit 99\n")
            stub.chmod(0o755)
        conf = self.root / "panel.conf"
        conf.write_text("a = codex test-model - high\nb = grok test-model - high\n")
        summary = self.root / "task.txt"
        if summary_exists:
            summary.write_text("Review locally")
        output = self.root / "output"
        env = dict(os.environ, REVIEW_PANEL_CONF=str(conf), REVIEW_PANEL_OUT=str(output))
        return summary, output, env

    def test_upstream_skill_documents_unknown_ownership_without_merging(self):
        skill = (SCRIPT.parents[2] / "upstream-contribution" / "SKILL.md").read_text()
        section = " ".join(skill.split("## 5.")[1].split("## 6.")[0].split())
        self.assertIn("external repositories or unknown ownership", section)
        self.assertIn("report how many commits the branch is behind without merging", section)
        self.assertIn("--update` forces a base merge", section)
        self.assertIn("Only confirmed owned repositories merge by default", section)
        self.assertIn("preparing a brief posts nothing", section)

    def test_panel_logs_size_guard_after_missing_reference(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        self.write(self.repo, "large.py", "# " + "x" * 800_001 + "\n")
        self.commit(self.repo, "Implement PT999")
        subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "round",
                        str(self.repo), str(summary), "generalist-a"],
                       capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        prompt = (output / "round" / "generalist-a.prompt").read_text()
        self.assertIn("not found: PT999", prompt)
        notice = next(line for line in prompt.splitlines() if line.startswith("Size guard:"))
        self.assertIn("generalist-a: " + notice, (output / "round" / "summary.txt").read_text())

    def test_panel_provider_retry_preserves_each_attempt_and_unchanged_inputs(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        env["TMPDIR"] = str(self.root)
        env["TEST_RETRY_ROOT"] = str(self.root)
        Path(env["REVIEW_PANEL_CONF"]).write_text(
            "a = codex test-model - high\nb = grok test-model - high\nc = kimi test-model\n")
        sleep = self.binaries / "sleep"
        sleep.write_text("#!/bin/sh\nexit 0\n")
        sleep.chmod(0o755)
        stub = "#!" + sys.executable + "\n" + r'''import hashlib, json, os, pathlib, sys
cli = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if cli == 'grok' and args[:1] == ['inspect']:
    print('  MCP Servers (0)\n  └ (none)\n\n  Hooks (0)\n  └ (none)\n')
    sys.exit(0)
root = pathlib.Path(os.environ['TEST_RETRY_ROOT'])
counter = root / (cli + '.count')
attempt = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(attempt))
family = {'codex': 'a', 'grok': 'b', 'kimi': 'c'}[cli]
pack = root / 'output' / family / ('generalist-' + family + '.pack')
data = (sys.stdin.buffer.read() if cli == 'codex' else
        pathlib.Path(args[args.index('--prompt-file') + 1]).read_bytes() if cli == 'grok' else
        args[args.index('-p') + 1].encode())
record = {'sent': hashlib.sha256(data).hexdigest(),
          'pack': hashlib.sha256((pack / 'pack.txt').read_bytes()).hexdigest(),
          'manifest': hashlib.sha256((pack / 'manifest.json').read_bytes()).hexdigest()}
(root / (cli + f'.attempt-{attempt}.inputs')).write_text(json.dumps(record))
report = f'Attempt {attempt}\n' + ('partial\n' if attempt == 1 else 'VERDICT: APPROVE\n')
if cli == 'codex':
    pathlib.Path(args[args.index('-o') + 1]).write_text(report)
    print(json.dumps({'attempt': attempt}))
elif cli == 'grok':
    print(json.dumps({'text': report}))
else:
    print(report, end='')
print(f'Attempt {attempt}: ' + ('at capacity' if attempt == 1 else 'complete'), file=sys.stderr)
sys.exit(99 if attempt == 1 else 0)
'''
        for cli in ("codex", "grok", "kimi"):
            (self.binaries / cli).write_text(stub)
        for family, cli in (("a", "codex"), ("b", "grok"), ("c", "kimi")):
            with self.subTest(cli=cli):
                result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), family,
                                         str(self.repo), str(summary), "generalist-" + family],
                                        capture_output=True, text=True, timeout=10, env=env, stdin=subprocess.DEVNULL)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                panel = output / family
                reviewer = "generalist-" + family
                for attempt in (1, 2):
                    prefix = panel / f"{reviewer}.attempt-{attempt}"
                    self.assertTrue(Path(str(prefix) + ".err").exists(), f"missing attempt {attempt} log")
                    self.assertIn(f"Attempt {attempt}:", Path(str(prefix) + ".err").read_text())
                    suffix = {"codex": ".jsonl", "grok": ".json", "kimi": ".md"}[cli]
                    self.assertIn(str(attempt), Path(str(prefix) + suffix).read_text())
                    if cli == "codex":
                        self.assertIn(f"Attempt {attempt}", Path(str(prefix) + ".md").read_text())
                inputs = [json.loads((self.root / f"{cli}.attempt-{n}.inputs").read_text()) for n in (1, 2)]
                self.assertEqual(inputs[0], inputs[1])
                self.assertEqual(inputs[0]["sent"], inputs[0]["pack"])
                self.assertIn("attempts=2", (panel / "summary.txt").read_text())
                self.assertIn("VERDICT: APPROVE", (panel / (reviewer + ".md")).read_text())

    def test_panel_provider_retry_refuses_changed_pack_or_manifest(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        sleep = self.binaries / "sleep"
        sleep.write_text("#!/bin/sh\nexit 0\n")
        sleep.chmod(0o755)
        stub = self.binaries / "codex"
        stub.write_text("#!" + sys.executable + "\n" + r'''import os, pathlib, sys
marker = pathlib.Path(os.environ['TEST_RETRY_MARKER'])
if marker.exists():
    pathlib.Path(sys.argv[sys.argv.index('-o') + 1]).write_text('VERDICT: APPROVE')
    sys.exit(0)
marker.write_text('first attempt')
pathlib.Path(os.environ['TEST_RETRY_MUTATE']).write_text('changed input')
print('at capacity', file=sys.stderr)
sys.exit(99)
''')
        for name in ("pack.txt", "manifest.json"):
            with self.subTest(input=name):
                panel = output / name
                env["TEST_RETRY_MARKER"] = str(self.root / (name + ".marker"))
                env["TEST_RETRY_MUTATE"] = str(panel / "generalist-a.pack" / name)
                result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), name,
                                         str(self.repo), str(summary), "generalist-a"],
                                        capture_output=True, text=True, timeout=10, env=env, stdin=subprocess.DEVNULL)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("pack or manifest changed", (panel / "summary.txt").read_text())
                self.assertFalse((panel / "generalist-a.attempt-2.md").exists())

    def test_panel_reviewer_cli_failure_returns_nonzero(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        Path(env["REVIEW_PANEL_CONF"]).write_text(
            "a = codex test-model - high\nb = grok test-model - high\nc = kimi test-model\n")
        # Valid JSON must not hide Grok's failing exit status during text extraction.
        (self.binaries / "grok").write_text('#!/bin/sh\nif [ "$1" = inspect ]; then printf "  MCP Servers (1)\n  \342\224\224 chrome-devtools (stdio)  ~/.claude.json [claude] [disabled]\n\n  Hooks (0)\n  \342\224\224 (none)\n"; exit 0; fi\nprintf \'{"text":"partial"}\\n\'\nexit 99\n')
        for family in ("a", "b", "c"):
            with self.subTest(family=family):
                result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), family,
                                         str(self.repo), str(summary), "generalist-" + family],
                                        capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("failed: reviewer CLI (exit 99", (output / family / "summary.txt").read_text())

    def test_panel_refuses_grok_with_enabled_hook_or_mcp(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        for listing in ("  MCP Servers (1)\\n  \\342\\224\\224 tracker (stdio)  .mcp.json\\n\\n  Hooks (0)\\n  \\342\\224\\224 (none)\\n",
                        "  MCP Servers (0)\\n  \\342\\224\\224 (none)\\n\\n  Hooks (1)\\n  \\342\\224\\224 command matcher=*  user\\n",
                        "unparseable\\n"):
            with self.subTest(listing=listing):
                (self.binaries / "grok").write_text(
                    '#!/bin/sh\nif [ "$1" = inspect ]; then printf "' + listing + '"; exit 0; fi\n'
                    'echo "reviewer must not run" >&2\nexit 99\n')
                result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "b",
                                         str(self.repo), str(summary), "generalist-b"],
                                        capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
                self.assertNotEqual(result.returncode, 0)
                recorded = (output / "b" / "summary.txt").read_text()
                self.assertIn("Grok would load an enabled hook or MCP server", recorded)

    def test_panel_report_requires_valid_verdict(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        Path(env["REVIEW_PANEL_CONF"]).write_text(
            "a = codex test-model - high\nb = grok test-model - high\nc = kimi test-model\n")
        stub = "#!" + sys.executable + "\n" + r"""import json, os, pathlib, sys
cli = pathlib.Path(sys.argv[0]).name
report = json.loads(os.environ['TEST_REVIEW_REPORT'])
if cli == 'codex':
    if report is not None:
        pathlib.Path(sys.argv[sys.argv.index('-o') + 1]).write_text(report)
elif cli == 'grok':
    if sys.argv[1:2] == ['inspect']:
        print('  MCP Servers (1)\n  └ chrome-devtools (stdio)  ~/.claude.json [claude] [disabled]\n\n  Hooks (0)\n  └ (none)\n')
        sys.exit(0)
    print(json.dumps({} if report is None else {'text': report}))
else:
    print(report or '', end='')
"""
        for cli in ("codex", "grok", "kimi"):
            (self.binaries / cli).write_text(stub)
        reports = [None, "", "Review incomplete\n", "VERDICT: UNKNOWN\n",
                   "VERDICT: APPROVED\n", "Example VERDICT: APPROVE\n",
                   "I will review...VERDICT: REQUEST_CHANGES",
                   "VERDICT: APPROVE\nProgress...**VERDICT:** **REQUEST_CHANGES**",
                   "VERDICT: REQUEST_CHANGES\nDone: __VERDICT: APPROVE__",
                   "VERDICT: APPROVE\n", "Findings\nVERDICT: REQUEST_CHANGES\n", "**VERDICT: REQUEST_CHANGES**\n", "_VERDICT: APPROVE_\n", None]
        for family, cli in (("a", "codex"), ("b", "grok"), ("c", "kimi")):
            for index, report in enumerate(reports):
                with self.subTest(cli=cli, report=report):
                    name = f"{family}-{index}"
                    env["TEST_REVIEW_REPORT"] = json.dumps(report)
                    result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), name,
                                             str(self.repo), str(summary), "generalist-" + family],
                                            capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
                    recorded = (output / name / "summary.txt").read_text()
                    if index < 5 or report is None:
                        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn(f"generalist-{family} failed: reviewer report", recorded)
                        self.assertIn("missing valid VERDICT", recorded)
                        self.assertNotIn("verdict=", recorded)
                    else:
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn("verdict=" + ("REQUEST_CHANGES" if "REQUEST_CHANGES" in report else "APPROVE"), recorded)

    def test_panel_reuse_refuses_and_preserves_previous_provenance(self):
        summary, output, env = self.panel_fixture(summary_exists=False)
        env["REVIEW_BASE"] = "origin/trunk"
        for family in ("a", "c"):
            with self.subTest(family=family):
                panel = output / family
                panel.mkdir(parents=True)
                reviewer = "generalist-" + family
                suffixes = ("md", "jsonl", "json", "err", "prepare.err", "prompt", "task")
                for suffix in suffixes:
                    (panel / f"{reviewer}.{suffix}").write_text("previous run\n")
                (panel / "summary.txt").write_text("previous run verdict=APPROVE\n")
                pack = panel / f"{reviewer}.pack"
                pack.mkdir()
                (pack / "pack.txt").write_text("pinned previous prompt\n")
                (pack / "manifest.json").write_text('{"previous": true}\n')
                untouched = (panel / f"{reviewer}.notes", panel / "generalist-b.md")
                for path in untouched:
                    path.write_text("keep\n")
                result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), family,
                                         str(self.repo), str(summary), reviewer],
                                        capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("fresh panel directory", result.stderr)
                self.assertEqual((panel / "summary.txt").read_text(), "previous run verdict=APPROVE\n")
                for suffix in suffixes:
                    path = panel / f"{reviewer}.{suffix}"
                    self.assertEqual(path.read_text(), "previous run\n")
                self.assertEqual((pack / "pack.txt").read_text(), "pinned previous prompt\n")
                self.assertEqual((pack / "manifest.json").read_text(), '{"previous": true}\n')
                for path in untouched:
                    self.assertEqual(path.read_text(), "keep\n")

    def test_panel_name_traversal_preserves_checkout_files(self):
        summary, _, env = self.panel_fixture()
        env.pop("REVIEW_PANEL_OUT")
        env["REVIEW_BASE"] = "origin/trunk"
        saved = {"summary.txt": "keep summary\n", "generalist-a.md": "keep report\n"}
        for filename, content in saved.items():
            (self.repo / filename).write_text(content)
        result = subprocess.run(
            ["bash", str(SCRIPT.with_name("review-panel.sh")), "../..",
             str(self.repo), str(summary), "generalist-a"],
            capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        for filename, content in saved.items():
            self.assertTrue((self.repo / filename).exists(), f"cleanup deleted {filename}")
            self.assertEqual((self.repo / filename).read_text(), content)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("invalid panel name", result.stderr)
        self.assertFalse((self.repo / ".tmp").exists())

    def test_panel_rejects_invalid_panel_names_before_output_changes(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        for name in ("", ".", "..", "../escape", "nested/round", "/absolute",
                     r"nested\round", ".hidden", "-round", "_round", "round name",
                     "round\n", "röund"):
            with self.subTest(name=name):
                result = subprocess.run(
                    ["bash", str(SCRIPT.with_name("review-panel.sh")), name,
                     str(self.repo), str(summary), "generalist-a"],
                    capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("invalid panel name", result.stderr)
                self.assertFalse(output.exists())

    def test_panel_directory_must_resolve_strictly_inside_output_root(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        output.mkdir()
        # Reject the root itself, a sibling sharing its prefix, and the checkout.
        sibling = output.with_name(output.name + "-other")
        sibling.mkdir()
        for target in (output, sibling, self.repo):
            with self.subTest(target=target):
                saved = {"summary.txt": "keep summary\n", "generalist-a.md": "keep report\n"}
                for filename, content in saved.items():
                    (target / filename).write_text(content)
                panel = output / ("round-" + target.name)
                panel.symlink_to(target, target_is_directory=True)
                result = subprocess.run(
                    ["bash", str(SCRIPT.with_name("review-panel.sh")), panel.name,
                     str(self.repo), str(summary), "generalist-a"],
                    capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
                for filename, content in saved.items():
                    self.assertTrue((target / filename).exists(), f"cleanup deleted {filename}")
                    self.assertEqual((target / filename).read_text(), content)
                self.assertTrue(panel.is_symlink())
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("outside output root", result.stderr)

    def test_panel_rejects_traversal_before_deleting_outside_files(self):
        summary, _, env = self.panel_fixture()
        env.pop("REVIEW_PANEL_OUT")
        env["REVIEW_BASE"] = "origin/trunk"
        victim = self.repo / "README.md"
        victim.write_text("keep outside panel\n")
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "round",
                                 str(self.repo), str(summary), "../../../README"],
                                capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertTrue(victim.exists(), "cleanup deleted checkout README.md")
        self.assertEqual(victim.read_text(), "keep outside panel\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid reviewer", result.stderr)
        self.assertFalse((self.repo / ".tmp" / "review-panel").exists())

    def test_panel_rejects_invalid_or_unknown_reviewers_before_any_output_changes(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        panel = output / "existing"
        panel.mkdir(parents=True)
        saved = {"summary.txt": "keep summary\n", "generalist-a.md": "keep report\n"}
        for filename, content in saved.items():
            (panel / filename).write_text(content)
        for reviewer in ("", "../generalist-a", "/generalist-a", "generalist_a",
                         "Generalist-a", "generalist-a\n", "unknown-reviewer"):
            for name in ("new", "existing"):
                with self.subTest(reviewer=reviewer, panel=name):
                    result = subprocess.run(
                        ["bash", str(SCRIPT.with_name("review-panel.sh")), name,
                         str(self.repo), str(summary), "generalist-a", reviewer],
                        capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("invalid reviewer", result.stderr)
                    self.assertFalse((output / "new").exists())
                    self.assertEqual({p.name: p.read_text() for p in panel.iterdir()}, saved)

    def test_panel_refuses_cleanup_paths_resolving_outside_panel(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        filenames = [f"generalist-a.{suffix}" for suffix in
                     ("md", "jsonl", "json", "err", "prepare.err", "prompt")]
        filenames.append("summary.txt")
        for filename in filenames:
            with self.subTest(filename=filename):
                panel = output / ("round-" + filename)
                panel.mkdir(parents=True)
                # A sibling sharing the panel's prefix is still outside it.
                outside = output / (panel.name + "-other")
                outside.mkdir()
                victim = outside / "keep.txt"
                victim.write_text("keep outside panel\n")
                for name in filenames:
                    (panel / name).write_text("previous run\n")
                link = panel / filename
                link.unlink()
                link.symlink_to(victim)
                result = subprocess.run(
                    ["bash", str(SCRIPT.with_name("review-panel.sh")), panel.name,
                     str(self.repo), str(summary), "generalist-a"],
                    capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
                self.assertTrue(link.is_symlink(), "escaping cleanup path was removed")
                self.assertEqual(victim.read_text(), "keep outside panel\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("fresh panel directory", result.stderr)
                for name in filenames:
                    if name != filename:
                        self.assertEqual((panel / name).read_text(), "previous run\n")
                link.unlink()

    def test_panel_preparation_failure_returns_nonzero(self):
        summary, output, env = self.panel_fixture(summary_exists=False)
        env["REVIEW_BASE"] = "origin/trunk"
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "round", str(self.repo), str(summary)], capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("context preparation", (output / "round" / "summary.txt").read_text())

    def test_panel_oversized_prompt_is_preparation_failure_without_reviewer(self):
        summary, output, env = self.panel_fixture()
        summary.write_text("s" * (prepare.CODEX_LIMIT + 1))
        env["REVIEW_BASE"] = "origin/trunk"
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "round",
                                 str(self.repo), str(summary), "generalist-a"],
                                capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("context preparation", (output / "round" / "summary.txt").read_text())
        self.assertIn("800,000", (output / "round" / "generalist-a.prepare.err").read_text())
        self.assertFalse((output / "round" / "generalist-a.prompt").exists())
        self.assertFalse((output / "round" / "generalist-a.pack").exists())
        self.assertFalse((output / "round" / "generalist-a.attempt-1.err").exists())

    def test_panel_resolves_and_fetches_once(self):
        summary, output, env = self.panel_fixture(summary_exists=False)
        real_git = prepare.shutil.which("git")
        log = self.root / "git.log"
        wrapper = self.binaries / "git"
        wrapper.write_text("#!" + sys.executable + "\nimport os, sys, json\n"
                           + f"with open({str(log)!r}, 'a') as log: log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                           + f"os.execv({real_git!r}, [{real_git!r}, *sys.argv[1:]])\n")
        wrapper.chmod(0o755)
        env.pop("REVIEW_BASE", None)
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), "round", str(self.repo), str(summary)], capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(sum(c[0] == "fetch" for c in calls), 1, result.stderr)
        self.assertEqual(sum(c[0] == "ls-remote" for c in calls), 1, result.stderr)

    def test_remote_default_overrides_stale_local_head_and_is_fetched(self):
        self.git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.git(self.repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        self.write(self.origin, "upstream.txt", "new upstream\n")
        self.commit(self.origin, "Upstream advances")
        base, remote, fresh = prepare.resolve_base(self.repo)
        self.assertEqual((base, remote, fresh), ("origin/trunk", "origin", True))
        self.assertEqual(self.git(self.repo, "rev-parse", base), self.git(self.origin, "rev-parse", "HEAD"))

    def test_fork_prefers_upstream_and_explicit_base_wins(self):
        upstream = self.root / "upstream"
        self.git(self.root, "clone", str(self.origin), str(upstream))
        self.git(upstream, "branch", "-m", "stable")
        self.git(self.repo, "remote", "add", "upstream", str(upstream))
        self.assertEqual(prepare.resolve_base(self.repo), ("upstream/stable", "upstream", True))
        self.assertEqual(prepare.resolve_base(self.repo, "origin/trunk"), ("origin/trunk", "origin", True))

    def test_fallback_main_when_remote_head_is_unadvertised(self):
        self.git(self.origin, "branch", "-m", "main")
        bare = self.root / "bare"
        self.git(self.root, "clone", "--bare", str(self.origin), str(bare))
        self.git(bare, "symbolic-ref", "HEAD", "refs/heads/missing")
        self.git(self.repo, "remote", "set-url", "origin", str(bare))
        self.assertEqual(prepare.resolve_base(self.repo), ("origin/main", "origin", True))

    def test_local_checkout_without_remote_accepts_explicit_base(self):
        self.git(self.repo, "remote", "remove", "origin")
        self.assertEqual(prepare.resolve_base(self.repo, "HEAD"), ("HEAD", None, True))
        with self.assertRaisesRegex(prepare.PrepareError, "specify --base"):
            prepare.resolve_base(self.repo)

    def add_review_change(self):
        self.write(self.repo, "src/core.py", "def action():\n    return 2\n")
        self.write(self.repo, "tests/test_core.py", "assert True\n")
        self.write(self.repo, "docs/design.md", "# Design\n## 1 Scope\nOutside content\n## 2 Behavior\nRequired behavior\n### 2.1 Detail\nNested detail\n```python\n# Not a heading\n```\n## 20 Other\nUnselected section\n## Acceptance\n| ID | Requirement |\n| --- | --- |\n| AT1-case | Included row |\n| AT2 | Excluded row |\n")
        self.write(self.repo, "Cargo.lock", "LOCK_ONLY_MARKER\n")
        self.write(self.repo, "odd name.py", "pass\n")
        self.commit(self.repo, "Implement behavior")

    def test_lens_settings_read_plain_config_and_fail_visible(self):
        config = self.root / "review-panel.lenses"
        config.write_text("generalist-a b read-only\n")
        self.assertEqual(prepare.lens_settings("generalist-a", config), ("b", "read-only"))
        for text in ("generalist-a b read-only\ngeneralist-a a read-only\n",
                     "generalist-a b\n", "generalist-a z read-only\n",
                     "generalist-a b workspace-write\n", "other a read-only\n"):
            with self.subTest(config=text):
                config.write_text(text)
                with self.assertRaises(prepare.PrepareError):
                    prepare.lens_settings("generalist-a", config)
        config.unlink()
        with self.assertRaises(prepare.PrepareError):
            prepare.lens_settings("generalist-a", config)

    def test_review_requires_lens_config_without_emitting_prompt(self):
        with mock.patch.object(prepare, "HERE", self.root):
            code, out, err = self.invoke("review", str(self.repo), "--base", "origin/trunk", "--no-fetch")
            self.assertEqual(code, 1, err)
            self.assertEqual(out, "")
            self.assertIn("review-panel.lenses", err)

    def test_panel_dispatches_family_from_plain_lens_config(self):
        summary, output, env = self.panel_fixture()
        env["REVIEW_BASE"] = "origin/trunk"
        kit = self.root / "kit"
        scripts = kit / "skills/pr-ready/scripts"
        shutil.copytree(SCRIPT.parent, scripts)
        shutil.copytree(SCRIPT.parents[3] / "prompts", kit / "prompts")
        shutil.copytree(SCRIPT.parents[3] / "rules", kit / "rules")
        (scripts / "review-panel.lenses").write_text("generalist-a b read-only\n")
        self.git(kit, "init", "-b", "main")
        self.commit(kit, "Pinned family configuration")
        env["REVIEW_HOUSE_RULES_REPO"] = str(kit)
        env["REVIEW_HOUSE_RULES_REV"] = self.git(kit, "rev-parse", "HEAD")
        (scripts / "review-panel.lenses").write_text("generalist-a a read-only\n")
        Path(env["REVIEW_PANEL_CONF"]).write_text("b = codex family-b-model - high\n")
        (self.binaries / "codex").write_text("#!" + sys.executable + "\n" +
            "import pathlib, sys\n" +
            "assert sys.argv[sys.argv.index('-s') + 1] == 'read-only'\n" +
            "pathlib.Path(sys.argv[sys.argv.index('-o') + 1]).write_text('VERDICT: APPROVE\\n')\n")
        result = subprocess.run(["bash", str(scripts / "review-panel.sh"), "round",
                                 str(self.repo), str(summary), "generalist-a"],
                                capture_output=True, text=True, env=env, timeout=15, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("generalist-a codex/family-b-model", result.stdout)
        prompt = (output / "round/generalist-a.prompt").read_text()
        self.assertNotRegex(prompt, r"(?m)^(family:|sandbox:|lens:|---$)")

    def test_review_preserves_whole_role_and_lens_files(self):
        from prompt import expand

        prompt = self.review()
        role, _ = expand(file="prompts/roles/reviewer.md")
        lens = (SCRIPT.parents[3] / "prompts/lenses/generalist-a.md").read_text()
        self.assertIn("# 1. Review pack\n" + role, prompt)
        self.assertIn("# 2. Instructions\n" + lens, prompt)
        self.assertNotRegex(prompt, r"(?m)^@rule ")
        for rule in (SCRIPT.parents[3] / "prompts/skills").glob("*.md"):
            self.assertEqual(prompt.count(rule.read_text()), 1)

    def test_spec_is_preserved_whole_despite_section_and_test_references(self):
        doc = b"# Design\r\n\r\n## 1 Scope ##\r\nOutside content\r\n## 2 Behavior\r\nRequired behavior\r\n### 2.1 Detail\r\n```python\r\n# Not a heading\r\n```\r\n## Tests\r\n| PT1 | One |\r\n| PT10 | Ten |\r\nTail without newline"
        path = "docs/spec.md"
        self.write(self.repo, path, "")
        (self.repo / path).write_bytes(doc)
        self.commit(self.repo, "Implement §2\n\n§2.1 (Old title) and PT1")
        head = self.git(self.repo, "rev-parse", "HEAD")
        files = prepare.changed_files(self.repo, "origin/trunk...HEAD")
        for spec, tests, reference, commit_text in (
            (path, None, "", ""),
            (None, None, "Design: docs/spec.md [§1–§2.1]\n§2 (Stale title)", ""),
            (path, "PT1", "PT1", ""),
            (None, None, "PT1", ""),
            (None, None, "", "Implement §2.1 (Old title) and PT1"),
        ):
            with self.subTest(spec=spec, tests=tests, reference=reference, commit=commit_text):
                args = argparse.Namespace(spec=spec, tests=tests, test_prefix="PT")
                missing, notices = [], []
                entries = prepare.requirement_entries(
                    self.repo, args, {}, [], [], [reference],
                    [(head, commit_text)] if commit_text else [], files,
                    None, head, missing, notices,
                )
                specs = [entry for entry in entries if entry["category"] == "spec"]
                self.assertEqual(len(specs), 1)
                self.assertEqual(specs[0]["body"], doc.decode())
                self.assertIn("docs/spec.md:1", specs[0]["link"])
                self.assertEqual(missing, [])
                self.assertEqual(notices, [])
                self.github(self.pr(reference))
                self.assertIn(doc.decode(), self.review(spec=spec, tests=tests))

    def test_explicit_spec_section_selectors_fail_without_prompt(self):
        self.add_review_change()
        for selector in ("2", "2,20", "Verification", ""):
            with self.subTest(selector=selector):
                spec = "docs/design.md#" + selector
                with self.assertRaisesRegex(prepare.PrepareError, "section selectors"):
                    prepare.discover_spec(self.repo, "HEAD", spec, [], [])
                code, out, err = self.invoke(
                    "review", str(self.repo), "--base", "origin/trunk", "--no-fetch",
                    "--spec", spec,
                )
                self.assertEqual(code, 1, err)
                self.assertEqual(out, "")
                self.assertIn("section selectors", err)

    def test_missing_prompt_include_fails_without_emitting_review(self):
        import prompt

        with mock.patch.object(prompt, "expand", side_effect=prompt.PromptError("missing rule")):
            code, out, err = self.invoke("review", str(self.repo), "--base", "origin/trunk",
                                         "--no-fetch")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("missing rule", err)

    def test_requirements_order_whole_spec_acceptance_ids_sort_and_lockfiles(self):
        self.add_review_change()
        prompt = self.review(spec="docs/design.md", tests="AT1")
        positions = [prompt.index(f"# {n}. {title}") for n, title in enumerate(
            ["Review pack", "Instructions", "Pull request and issue", "Requirements", "Change"], 1)]
        self.assertEqual(positions, sorted(positions))
        spec = prompt[positions[3]:positions[4]]
        self.assertIn("R1. Design/spec docs/design.md — Full document — [docs/design.md:1]", spec)
        self.assertIn("### 2.1 Detail", spec)
        self.assertIn("# Not a heading", spec)
        self.assertIn("| AT1-case | Included row |", spec)
        self.assertIn("not found: AT1", prompt)
        self.assertIn("Excluded row", spec)
        self.assertIn("Unselected section", spec)
        files = prepare.changed_files(self.repo, "origin/trunk...HEAD")
        self.assertEqual([prepare.kind(f[2]) for f in files], ["source", "source", "source", "test", "docs"])
        change = prompt[positions[4]:]
        self.assertIn("Cargo.lock — source +1/-0", change)
        self.assertIn("(lockfile: listed only)", change)
        self.assertNotIn("LOCK_ONLY_MARKER", change)
        self.assertIn("odd name.py", change)
        self.assertIn("Implement behavior", prompt)

    def test_diff_has_only_spec_index_pack_has_hunks_and_cli_defaults(self):
        self.add_review_change()
        diff = self.review(spec="docs/design.md", format="diff")
        spec = diff.split("# 4. Requirements", 1)[1].split("# 5. Change", 1)[0]
        self.assertIn("R1. Design/spec docs/design.md — Full document", spec)
        self.assertNotIn("Required behavior", spec)
        self.assertIn("```diff", diff)
        pack = self.review(cli="grok")
        self.assertIn("Touched functions (hunk headers)", pack)
        self.assertNotIn("```diff", pack)
        self.assertNotIn("+    return 2", pack)
        self.assertIn("```diff", self.review(cli="kimi", format="structured"))

    def test_pr_design_and_summary_precedence_with_optional_gh(self):
        self.add_review_change()
        summary = self.root / "summary.txt"
        summary.write_text("Round task override")
        pr = {"url": "https://github.com/example/project/pull/1", "title": "Change title",
              "body": "PR body\nDesign: docs/design.md [§2, §20]\n"}
        self.github(pr)
        prompt = self.review(pr="1", summary=str(summary), tests="AT1")
        self.assertIn("Round task override", prompt)
        self.assertIn("R1. Design/spec docs/design.md — Full document", prompt)
        self.assertIn("## 20 Other\nUnselected section", prompt)
        self.assertIn("Title: Change title", prompt)
        with mock.patch.object(prepare.shutil, "which", return_value=None):
            with self.assertRaisesRegex(prepare.PrepareError, "explicitly requested PR/issue"):
                self.review(pr="1")
            prompt = self.review()
        self.assertIn("Implement behavior", prompt)

    def test_missing_specs_or_tests_report_at_top(self):
        self.add_review_change()
        for spec, expected in (("docs/design.md", "MISSING"), ("absent.md", "absent.md, MISSING")):
            with self.subTest(spec=spec):
                prompt = self.review(spec=spec, tests="MISSING")
                self.assertTrue(prompt.startswith("not found: " + expected))
                self.assertIn("# 5. Change", prompt)

    def test_references_from_all_sources_include_one_whole_spec(self):
        self.write(self.repo, "docs/spec.md", "# Design\n## 3A.2.5 First\nFirst requirement\n## 3A.2.5a Middle\nMiddle requirement\n## 3A.2.6 Last\nLast requirement\n## 3A.5 Other\nOther requirement\n## 9 Outside\nExcluded requirement\n## Tests\n| PT1 | One |\n| PT10 | Ten |\n| PT2 | Two |\n")
        self.commit(self.repo, "Implement §3A.5\n\nAcceptance PT2")
        for dash in ("–", "-"):
            with self.subTest(dash=dash):
                self.github(self.pr(f"Refs #2\nDesign: docs/spec.md [§3A.2.5{dash}§3A.2.6]\nPT1"),
                            [self.issue(2, "Also §3A.5 and PT2")])
                prompt = self.review()
                requirements = prompt.split("# 4. Requirements")[1].split("# 5. Change")[0]
                self.assertIn("R1. Design/spec docs/spec.md — Full document", requirements)
                self.assertEqual(requirements.count((self.repo / "docs/spec.md").read_text()), 1)
                self.assertIn("| PT1 | One |", requirements)
                self.assertIn("| PT2 | Two |", requirements)
                self.assertIn("| PT10 | Ten |", requirements)
                self.assertIn("Excluded requirement", requirements)
                self.assertNotIn("not found:", prompt)

    def test_document_discovery_uses_only_named_or_edited_documents(self):
        for path, body in {
            "docs/other.md": "## 3A.5 Shared\nWrong tie\n",
            "docs/specs/right.md": "## 3A.5 Shared\nPreferred tie\n## 3A.6 More\nMatched two\n",
            "docs/design/wrong.md": "## 8 Wrong\nIrrelevant\n",
            "docs/named.md": "## 3A.5 Shared\nNamed document\n",
        }.items():
            self.write(self.repo, path, body)
        self.commit(self.repo, "Base docs")
        self.git(self.repo, "update-ref", "refs/remotes/origin/trunk", "HEAD")
        self.write(self.repo, "src/core.py", "pass\n")
        self.commit(self.repo, "Implement §3A.5 and §3A.6")
        prompt = self.review()
        self.assertNotIn("Design/spec", prompt)
        self.github(self.pr("Refs #2"), [self.issue(2, "See [design](docs/named.md): §3A.5")])
        self.assertIn("Design/spec docs/named.md", self.review())
        self.github(self.pr("See [design](https://github.com/example/project/blob/main/docs/named.md): §3A.5"))
        self.assertIn("Design/spec docs/named.md", self.review())
        self.assertIn("Design/spec docs/other.md", self.review(spec="docs/other.md"))
        self.write(self.repo, "docs/design/wrong.md", "## 3A.5 Shared\nEdited design\n")
        self.commit(self.repo, "Update design")
        self.github()
        self.assertIn("Design/spec docs/design/wrong.md", self.review())

    def test_issue_forms_repeatable_cli_comments_associations_bots_and_order(self):
        self.add_review_change()
        issues = [self.issue(n, owner_repo="other/project" if n == 3 else "example/project") for n in range(2, 7)]
        self.github(self.pr("Closes #2; Refs other/project#3; Fixes https://github.com/example/project/issues/4; Resolves #5; Refs #2"),
                    issues, pr_comments=[self.comment(6, "OWNER"), self.comment(2, "CONTRIBUTOR"),
                                         self.comment(3, login="automation[bot]"), self.comment(4, user_type="Bot")],
                    review_comments=[self.comment(7, "COLLABORATOR")], reviews=[self.comment(8, "MEMBER")],
                    issue_comments={2: [[self.comment(5, "MEMBER")], [self.comment(1, "OWNER")]]})
        code, prompt, err = self.invoke("review", str(self.repo), "--base", "origin/trunk", "--no-fetch", "--pr", "1",
                                        "--issue", "6", "--issue", "example/project#2")
        self.assertEqual(code, 0, err)
        requirements = prompt.split("# 4. Requirements")[1].split("# 5. Change")[0]
        for n in range(2, 7):
            self.assertIn(f"Issue #{n}: Requirement {n} (labels: acceptance)", requirements)
        for n in (2, 3, 4):
            self.assertNotIn(f"Comment body {n}", prompt)
        positions = [requirements.index(f"Comment body {n}") for n in (1, 5, 6, 7, 8)]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(requirements.index("Design/spec"), requirements.index("Issue #"))
        self.assertLess(requirements.index("Issue #"), requirements.index("Maintainer comment"))
        self.assertLess(requirements.index("Maintainer comment"), requirements.index("PR description (author claims)"))
        calls = [json.loads(line) for line in self.gh_log.read_text().splitlines()]
        self.assertEqual(sum(call[-1] == "repos/example/project/issues/2" for call in calls), 1)

    def test_unresolved_references_are_reported_without_dropping_found_content(self):
        self.write(self.repo, "docs/spec.md", "## 3A.5 Found\nKnown requirement\n## Tests\n| PT4 | Known test |\n| PT400 | Different test |\n")
        self.commit(self.repo, "Implement §3A.5")
        self.github(self.pr("Design: docs/spec.md [§3A.5–§3A.9]\nPT4 PT40\nRefs #77"))
        fixtures = json.loads(self.fixtures.read_text())
        fixtures["api --method GET repos/example/project/issues/77"] = {"_error": "HTTP 404: Not Found"}
        self.fixtures.write_text(json.dumps(fixtures))
        prompt = self.review()
        top = prompt.split("# 1. Review pack")[0]
        for ref in ("PT40", "#77"):
            self.assertIn(ref, top)
        self.assertIn("Known requirement", prompt)
        self.assertIn("| PT4 | Known test |", prompt)
        self.assertNotIn("GitHub context unavailable", prompt)

    def test_no_gh_and_network_failure_keep_local_commits_spec_and_missing_issues(self):
        self.write(self.repo, "docs/spec.md", "## 2 Behavior\nLocal requirement\n## Tests\n| PT1 | Test requirement |\n")
        self.commit(self.repo, "Implement §2\n\nPT1 Full commit body")
        self.github(self.pr("PR body must be skipped"))
        with mock.patch.object(prepare.shutil, "which", return_value=None):
            prompt = self.review(spec="docs/spec.md")
        top = prompt.split("# 1. Review pack")[0]
        self.assertIn("sources 2–4", top)
        self.assertIn("gh is not installed", top)
        self.assertIn("Local requirement", prompt)
        self.assertIn("Full commit body", prompt)
        self.assertIn("Commit message", prompt)
        fixtures = json.loads(self.fixtures.read_text())
        fixtures["pr view --json url,title,body"] = {"_error": "network unavailable"}
        self.fixtures.write_text(json.dumps(fixtures))
        prompt = self.review()
        self.assertTrue(prompt.startswith("GitHub context unavailable"))
        self.assertIn("network unavailable", prompt)
        self.assertIn("Full commit body", prompt)
        self.assertNotIn("PR body must be skipped", prompt)

    def test_later_network_failure_keeps_already_collected_references(self):
        self.write(self.repo, "docs/spec.md", "## 2 Known\nLocal requirement\n")
        self.commit(self.repo, "Change")
        self.github(self.pr("Design: docs/spec.md [§2, §9]\nPT40\nRefs #2"), [self.issue(2)])
        fixtures = json.loads(self.fixtures.read_text())
        fixtures["api --method GET --paginate --slurp repos/example/project/issues/2/comments?per_page=100"] = {
            "_error": "network unavailable"}
        self.fixtures.write_text(json.dumps(fixtures))
        prompt = self.review()
        top = prompt.split("# 1. Review pack")[0]
        for token in ("PT40", "network unavailable", "issues/2/comments"):
            self.assertIn(token, top)
        self.assertIn("Local requirement", prompt)
        requirements = prompt.split("# 4. Requirements")[1].split("# 5. Change")[0]
        self.assertIn("PR description", requirements)
        self.assertIn("Issue #2", requirements)
        self.assertNotIn("#2", top)

    def test_custom_test_prefix_and_local_issue_without_pr(self):
        self.write(self.repo, "docs/design.md", "## 1 Behavior\nRequired\n## Tests\n| AT2 | Custom test |\n| PT3 | Default test |\n")
        self.commit(self.repo, "Implement AT2 PT3")
        self.github(issues=[self.issue(2, "Design: docs/design.md [§1]\nAT2")])
        code, prompt, err = self.invoke("review", str(self.repo), "--base", "origin/trunk", "--no-fetch",
                                        "--issue", "2", "--test-prefix", "AT")
        self.assertEqual(code, 0, err)
        requirements = prompt.split("# 4. Requirements")[1].split("# 5. Change")[0]
        self.assertIn("| AT2 | Custom test |", requirements)
        self.assertIn("| PT3 | Default test |", requirements)
        self.assertIn("Issue #2", requirements)
        self.assertNotIn("Commit message", requirements)

    def test_comment_cap_and_size_guard_trim_in_authority_order_largest_first(self):
        self.write(self.repo, "docs/spec.md", "## 1 Small\n" + "s" * 1000 + "\n## 2 Large\n" + "l" * 8000)
        self.commit(self.repo, "Requirements §1, §2")
        self.github(self.pr("Design: docs/spec.md [§1, §2]\nRefs #2"), [self.issue(2, "i" * 7000)],
                    pr_comments=[self.comment(1, body="c" * 5000)])
        full = self.review(format="pack")
        self.assertIn("Comment capped at 4,000 characters", full.split("# 1. Review pack")[0])
        self.assertIn("c" * 4000, full)
        self.assertNotIn("c" * 4001, full)
        for reduction, expected in [(1000, ["comment"]), (6000, ["comment", "issue"]),
                                     (14000, ["comment", "issue", "spec"])]:
            with self.subTest(reduction=reduction), mock.patch.object(prepare, "CODEX_LIMIT", len(full) - reduction):
                prompt = self.review(format="pack")
                top = prompt.split("# 1. Review pack")[0]
                trimmed = re.findall(r"Size guard: trimmed R\d+ \((\w+)\)", top)
                self.assertEqual(trimmed, expected)
                self.assertLessEqual(len(prompt), len(full) - reduction)
                if "spec" in expected:
                    self.assertIn("trimmed R1 (spec)", top)
                self.assertIn("PR description (author claims)", prompt)
                self.assertIn("s" * 1000, prompt)

    def test_web_links_use_base_remote_and_head_sha(self):
        head = self.git(self.repo, "rev-parse", "HEAD")
        for remote, route in [("git@github.com:example/project.git", "/blob/"),
                              ("ssh://git@gitlab.com/example/group/project.git", "/-/blob/")]:
            self.git(self.repo, "remote", "set-url", "origin", remote)
            url = prepare.web_remote(self.repo, "origin")
            result = prepare.link(url, head, "src/has space.py", 3)
            self.assertIn(f"{route}{head}/src/has%20space.py#L3", result)
        self.assertEqual(prepare.link(None, head, "src/a.py", 3), "src/a.py:3")

    def test_codex_size_guard_counts_entire_prompt_and_preserves_context(self):
        self.write(self.repo, "large.py", "# " + "x" * 800_001 + "\n")
        self.commit(self.repo, "Large change")
        prompt = self.review()
        self.assertTrue(prompt.startswith("Size guard:"))
        self.assertIn("# 1. Review pack", prompt)
        self.assertIn("Large change", prompt)
        self.assertNotIn("```diff", prompt)
        self.assertIn("Touched functions", prompt)
        # Guard includes task/spec overhead, not just the raw diff size.
        summary = self.root / "summary.txt"
        summary.write_text("s" * 800_001)
        with self.assertRaisesRegex(prepare.PrepareError, "limit 800,000 characters"):
            self.review(summary=str(summary))
        self.assertEqual(summary.read_text(), "s" * 800_001)

    def test_irreducible_prompt_fails_with_limit_final_size_and_trim_history(self):
        self.write(self.repo, "docs/spec.md", "## 1 Behavior\n" + "x" * 1000)
        self.commit(self.repo, "Requirements §1")
        self.github(self.pr("Design: docs/spec.md [§1]\nRefs #2"),
                    [self.issue(2, "i" * 1000)],
                    pr_comments=[self.comment(1, body="c" * 1000)])
        summary = self.root / "summary.txt"
        summary.write_text("s" * (prepare.CODEX_LIMIT + 1))
        code, out, err = self.invoke("review", str(self.repo), "--base", "origin/trunk",
                                     "--no-fetch", "--summary", str(summary))
        self.assertEqual(code, 1, err)
        self.assertEqual(out, "")
        self.assertIn("limit 800,000 characters", err)
        final_size = re.search(r"final size ([\d,]+) characters", err)
        self.assertIsNotNone(final_size, err)
        self.assertGreater(int(final_size[1].replace(",", "")), prepare.CODEX_LIMIT)
        self.assertIn("change part uses pack", err)
        self.assertEqual(re.findall(r"trimmed R\d+ \((\w+)\)", err),
                         ["comment", "issue", "spec"])
        self.assertIn("docs/spec.md", err)

    def test_fix_merge_conflict_stops_and_leaves_merge_in_progress(self):
        self.write(self.repo, "src/core.py", "feature change\n")
        self.commit(self.repo, "Feature")
        self.write(self.origin, "src/core.py", "base change\n")
        self.commit(self.origin, "Base")
        code, out, err = self.invoke("fix", str(self.repo), "--update")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("range: origin/trunk...HEAD", err)
        self.assertIn("merge left in progress", err)
        self.assertIn("src/core.py", err)
        self.git(self.repo, "rev-parse", "--verify", "MERGE_HEAD")

    def test_external_fix_and_pr_report_behind_without_merging(self):
        self.write(self.repo, "feature.py", "pass\n")
        self.commit(self.repo, "Feature")
        feature = self.git(self.repo, "rev-parse", "HEAD")
        for n in range(2):
            self.write(self.origin, "upstream.py", f"value = {n}\n")
            self.commit(self.origin, f"Base {n}")
        for command in ("fix", "pr"):
            with self.subTest(command=command), mock.patch.object(
                prepare, "ownership", return_value="external example/project"
            ) as ownership:
                code, out, err = self.invoke(command, str(self.repo))
                self.assertEqual(code, 0, err)
                self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), feature)
                self.assertEqual(self.git(self.repo, "rev-list", "--count", "HEAD..origin/trunk"), "2")
                self.assertIn("2 commit(s) behind origin/trunk", out)
                self.assertIn("operator", out)
                self.assertIn("--update", out)
                ownership.assert_called_once_with(self.repo.resolve(), "origin")

    def test_owned_and_explicit_external_updates_merge_for_fix_and_pr(self):
        self.write(self.repo, "feature.py", "pass\n")
        self.commit(self.repo, "Feature")
        feature = self.git(self.repo, "rev-parse", "HEAD")
        self.write(self.origin, "upstream.py", "pass\n")
        self.commit(self.origin, "Base")
        for command in ("fix", "pr"):
            for status, flags in (("owned", ()), ("external", ("--update",))):
                with self.subTest(command=command, status=status), mock.patch.object(
                    prepare, "ownership", return_value=status + " example/project"
                ) as ownership:
                    self.git(self.repo, "checkout", "-B", f"{command}-{status}", feature)
                    code, out, err = self.invoke(command, str(self.repo), *flags)
                    self.assertEqual(code, 0, err)
                    self.assertEqual(self.git(self.repo, "rev-parse", "HEAD^1"), feature)
                    self.assertEqual(self.git(self.repo, "rev-parse", "HEAD^2"), self.git(self.origin, "rev-parse", "HEAD"))
                    ownership.assert_called_once_with(self.repo.resolve(), "origin")

    def test_unknown_ownership_skips_merge_reports_behind_and_update_forces(self):
        self.write(self.repo, "feature.py", "pass\n")
        self.commit(self.repo, "Feature")
        feature = self.git(self.repo, "rev-parse", "HEAD")
        for n in range(2):
            self.write(self.origin, "upstream.py", f"value = {n}\n")
            self.commit(self.origin, f"Base {n}")
        (self.binaries / "gh").write_text("#!/bin/sh\necho 'network unavailable' >&2\nexit 2\n")
        for command in ("fix", "pr"):
            for unavailable in (True, False):
                with self.subTest(command=command, no_gh=unavailable), mock.patch.object(
                    prepare, "web_remote", return_value="https://github.com/example/project"
                ), mock.patch.object(prepare.shutil, "which", return_value=None if unavailable else str(self.binaries / "gh")):
                    self.git(self.repo, "checkout", "-B", "feature", feature)
                    code, out, err = self.invoke(command, str(self.repo))
                    self.assertEqual(code, 0, err)
                    self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), feature)
                    self.assertIn("unknown", out)
                    self.assertIn("2 commit(s) behind origin/trunk", out)
                    self.assertIn("Base merge skipped", out)
                    self.assertIn("--update", out)
                    code, out, err = self.invoke(command, str(self.repo), "--update")
                    self.assertEqual(code, 0, err)
                    self.assertEqual(self.git(self.repo, "rev-parse", "HEAD^1"), feature)
                    self.assertEqual(self.git(self.repo, "rev-parse", "HEAD^2"),
                                     self.git(self.origin, "rev-parse", "HEAD"))

    def test_fix_merges_without_rebasing_and_lists_reviews_without_running_tests(self):
        self.write(self.repo, "tests/test_feature.py", "raise RuntimeError('must not run')\n")
        self.commit(self.repo, "Feature")
        feature = self.git(self.repo, "rev-parse", "HEAD")
        self.write(self.origin, "upstream.py", "pass\n")
        self.commit(self.origin, "Base")
        code, out, err = self.invoke("fix", str(self.repo), "--update", "--reviews", "review-a.md", "review-b.md")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD^1"), feature)
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD^2"), self.git(self.origin, "rev-parse", "HEAD"))
        self.assertIn("test: tests/test_feature.py", out)
        self.assertIn("declared gates", out)
        self.assertNotIn("pytest", out)
        self.assertIn("review-a.md\nreview-b.md", out)

    def test_panel_keeps_family_cli_options_and_summary_task(self):
        self.panel_source()
        self.add_review_change()
        binaries = self.root / "bin"
        binaries.mkdir(exist_ok=True)
        stub = """#!/usr/bin/env python3
import json, os, pathlib, sys
cli = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
if cli == 'codex':
    pathlib.Path(args[args.index('-o') + 1]).write_text('VERDICT: APPROVE')
    data = sys.stdin.buffer.read()
    pathlib.Path(os.environ['TEST_SENT_ROOT'], 'a.sent').write_bytes(data)
    assert b'# 3. Pull request and issue' in data
elif cli == 'grok':
    assert os.environ['GROK_CLAUDE_AGENTS_ENABLED'] == '0'
    assert os.environ['GROK_CURSOR_SKILLS_ENABLED'] == '0'
    # Grok runs outside the checkout so no project configuration is discovered.
    assert not (pathlib.Path.cwd() / '.git').exists()
    if args[:1] == ['inspect']:
        print('  MCP Servers (1)\\n  └ chrome-devtools (stdio)  ~/.claude.json [claude] [disabled]\\n\\n  Hooks (0)\\n  └ (none)\\n')
        sys.exit(0)
    assert '--disable-web-search' in args
    assert args[args.index('--tools') + 1] == 'read_file,list_dir,grep'
    prompt = pathlib.Path(args[args.index('--prompt-file') + 1]).read_text()
    assert 'The checkout under review is ' in prompt
    pathlib.Path(os.environ['TEST_SENT_ROOT'], 'b.sent').write_bytes(pathlib.Path(args[args.index('--prompt-file') + 1]).read_bytes())
    print(json.dumps({'text': 'VERDICT: APPROVE'}))
else:
    assert 'Round task from file' in args[args.index('-p') + 1]
    pathlib.Path(os.environ['TEST_SENT_ROOT'], 'c.sent').write_bytes(args[args.index('-p') + 1].encode())
    print('VERDICT: APPROVE')
"""
        for cli in ("codex", "grok", "kimi"):
            path = binaries / cli
            path.write_text(stub)
            path.chmod(0o755)
        conf = self.root / "panel.conf"
        conf.write_text("a = codex test-model - high\nb = grok test-model - high\nc = kimi test-model\n")
        summary = self.root / "task.txt"
        summary.write_text("Round task from file")
        output = self.root / "output"
        sent = self.root / "sent"
        sent.mkdir()
        env = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                   REVIEW_PANEL_CONF=str(conf), REVIEW_PANEL_OUT=str(output), REVIEW_BASE="origin/trunk",
                   TEST_SENT_ROOT=str(sent))
        name = "Round9._-"
        result = subprocess.run(["bash", str(SCRIPT.with_name("review-panel.sh")), name,
                                 str(self.repo), str(summary)], capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("verdict=APPROVE"), 3, result.stdout + result.stderr)
        for family in ("a", "b", "c"):
            prompt = (output / name / f"generalist-{family}.prompt").read_text()
            self.assertIn("Round task from file", prompt.split("# 3. Pull request and issue")[1])
            self.assertEqual("```diff" in prompt, family == "a")
            pack = output / name / f"generalist-{family}.pack" / "pack.txt"
            self.assertEqual((sent / f"{family}.sent").read_bytes(), pack.read_bytes())

    def test_pr_brief_works_without_gh_and_classifies_owned_external(self):
        self.write(self.repo, "tests/test_new.py", "assert True\n")
        self.commit(self.repo, "Add regression")
        with mock.patch.object(prepare.shutil, "which", return_value=None):
            code, out, err = self.invoke("pr", str(self.repo))
        self.assertEqual(code, 0, err)
        self.assertIn("## Commits", out)
        self.assertIn("Add regression", out)
        self.assertIn("unknown", out)
        self.assertIn("Nothing is posted without operator approval", out)
        self.git(self.repo, "remote", "set-url", "origin", "https://github.com/example/project.git")
        for status, returncode in [("owned", 0), ("external", 1)]:
            with mock.patch.object(prepare.shutil, "which", return_value="gh"), mock.patch.object(
                prepare, "run", return_value=subprocess.CompletedProcess([], returncode, status + " example/project\n", "")
            ) as run:
                with mock.patch.object(prepare, "web_remote", return_value="https://github.com/example/project"):
                    self.assertEqual(prepare.ownership(self.repo, "origin"), status + " example/project")
                self.assertTrue(run.call_args.args[2].endswith("repo-ownership.sh"))


if __name__ == "__main__":
    unittest.main()
