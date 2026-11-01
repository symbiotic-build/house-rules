"""rules_changelog.py builds the rules changelog from merge commits and flags merges without a Rule changes section."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().with_name("rules_changelog.py")


class RulesChangelogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        self.write("rules/core.md", "- Keep records.\n")
        self.commit("base")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                              check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout

    def write(self, path, text):
        (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / path).write_text(text)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def merge(self, branch, path, text, body):
        self.git("checkout", "-q", "-b", branch)
        self.write(path, text)
        self.commit(branch)
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", branch, "-m", f"Merge {branch}", "-m", body)

    def run_script(self, *args, stdin=""):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], input=stdin, stdin=None,
                              capture_output=True, text=True)

    def test_changelog_lists_declared_merges_and_check_flags_undeclared_rule_merges(self):
        self.merge("declared", "rules/core.md", "- Keep all records.\n",
                   "## Rule changes\n- RC1 Change rules/core.md line 1: stronger.\n\n## Tests\nnone")
        self.merge("undeclared", "rules/core.md", "- Keep records.\n", "No section here.")
        self.merge("code-only", "src/app.py", "x = 1\n", "Not rule text.")
        out = self.run_script("--repo", str(self.repo))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Merge declared", out.stdout)
        self.assertIn("RC1 Change rules/core.md line 1: stronger.", out.stdout)
        self.assertNotIn("## Tests", out.stdout)
        self.assertNotIn("Merge undeclared", out.stdout)
        check = self.run_script("--check", "--repo", str(self.repo))
        self.assertEqual(check.returncode, 1)
        self.assertIn("Merge undeclared: changed rules/core.md", check.stdout)
        self.assertNotIn("declared:", check.stdout.replace("undeclared:", ""))
        self.assertNotIn("code-only", check.stdout)

    def test_section_extracts_the_rule_changes_part_of_a_pr_body(self):
        body = "Intro.\r\n\r\n## Rule changes\r\n- RC1 Remove a rule. Approved 2026-10-20.\r\n\r\n## Tests\r\nok\r\n"
        out = self.run_script("--section", stdin=body)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout, "## Rule changes\n\n- RC1 Remove a rule. Approved 2026-10-20.\n")
        self.assertEqual(self.run_script("--section", stdin="No section.").returncode, 1)

    def test_check_starts_where_main_brought_the_script_in(self):
        self.git("checkout", "-q", "-b", "intro")
        self.write("skills/pr-ready/scripts/rules_changelog.py", "# the script arrives here\n")
        self.commit("add the changelog script")
        self.git("checkout", "-q", "main")
        self.merge("legacy", "rules/core.md", "- Keep all records.\n", "Merged before the convention.")
        self.git("merge", "-q", "--no-ff", "intro", "-m", "Merge intro", "-m", "## Rule changes\n- RC1 Add the script.")
        self.merge("after", "rules/core.md", "- Keep records.\n", "No section after the convention.")
        check = self.run_script("--check", "--repo", str(self.repo))
        self.assertEqual(check.returncode, 1)
        self.assertIn("Merge after: changed rules/core.md", check.stdout)
        self.assertNotIn("legacy", check.stdout)

    def test_a_fenced_example_heading_is_not_the_section(self):
        body = ("How to declare:\n\n```markdown\n## Rule changes\n- RC1 Example only.\n```\n\n"
                "## Rule changes\n- RC1 The real declaration.\n")
        out = self.run_script("--section", stdin=body)
        self.assertEqual(out.stdout, "## Rule changes\n\n- RC1 The real declaration.\n")
        self.merge("fenced", "rules/core.md", "- Keep all records.\n", body)
        log = self.run_script("--repo", str(self.repo)).stdout
        self.assertIn("RC1 The real declaration.", log)
        self.assertNotIn("Example only", log)


if __name__ == "__main__":
    unittest.main()
