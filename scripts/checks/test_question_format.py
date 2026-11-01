"""Tests for question_format.py on synthetic operator messages."""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import question_format  # noqa: E402

GOOD = """\
Two answers are needed before the import continues.

## Import

### 1\\. Which store should the importer write to?
`FACT` The importer writes 40 records a minute to `data/staging.db`. `ASSESSMENT` The staging store fills in a week.\\
Either answer also applies to later imports.

1. **The archive store, with one copy per day (recommended).**
2. The staging store, cleared by hand each week.

## Reports

### 2\\. Send the error text from the failed upload?
`FACT` The upload log at `logs/upload.log` has no entry from that hour.

**Answer like so:**
```text
 1. 1
 2. explain where the log is written
 3. ok
```
"""


def rules(text):
    return [item["rule"] for item in question_format.check(text)]


class QuestionFormatTest(unittest.TestCase):
    def test_well_formed_questions_pass(self):
        self.assertEqual(question_format.check(GOOD), [])

    def test_message_without_questions_passes(self):
        self.assertEqual(question_format.check("The import finished. Nothing waits on you.\n"), [])

    def test_unescaped_number_fails(self):
        self.assertIn("question_number_unescaped", rules(GOOD.replace("### 1\\.", "### 1.")))

    def test_question_at_level_two_fails(self):
        self.assertIn("question_level", rules(GOOD.replace("### 2\\.", "## 2\\.")))

    def test_question_without_topic_fails(self):
        text = "### 1\\. Merge the change?\n`FACT` CI passed on `main`.\n\n**Answer like so:**\n" \
               "```text\n 1. ok\n 2. explain\n 3. ok\n```\n"
        self.assertIn("question_topic", rules(text))

    def test_reused_number_across_topics_fails(self):
        self.assertIn("question_number_duplicate", rules(GOOD.replace("### 2\\.", "### 1\\.")))

    def test_skipped_number_fails(self):
        self.assertIn("question_number_order", rules(GOOD.replace("### 2\\.", "### 3\\.")))

    def test_letter_suffix_fails(self):
        self.assertIn("question_number_suffix", rules(GOOD.replace("### 2\\.", "### 1b\\.")))

    def test_unflagged_context_sentence_fails(self):
        text = GOOD.replace("`ASSESSMENT` The staging store", "The staging store")
        self.assertIn("context_flag", rules(text))

    def test_assumption_flag_in_context_fails(self):
        text = GOOD.replace("`ASSESSMENT` The staging store", "`ASSUMPTION` The staging store")
        self.assertIn("context_flag", rules(text))

    def test_wrapped_context_line_fails(self):
        wrapped = GOOD.replace("`ASSESSMENT` The staging store fills in a week.\\",
                               "`ASSESSMENT` The staging store\nfills in a week.")
        self.assertIn("context_wrapped", rules(wrapped))

    def test_two_recommended_options_fail(self):
        text = GOOD.replace("2. The staging store, cleared by hand each week.",
                            "2. **The staging store (recommended).**")
        self.assertIn("recommended_count", rules(text))

    def test_no_recommended_option_fails(self):
        text = GOOD.replace("1. **The archive store, with one copy per day (recommended).**",
                            "1. The archive store, with one copy per day.")
        self.assertIn("recommended_count", rules(text))

    def test_partly_bold_recommended_option_fails(self):
        text = GOOD.replace("1. **The archive store, with one copy per day (recommended).**",
                            "1. **The archive store (recommended):** one copy per day.")
        self.assertIn("recommended_format", rules(text))

    def test_word_option_in_option_text_fails(self):
        text = GOOD.replace("2. The staging store", "2. Option two: the staging store")
        self.assertIn("option_word", rules(text))

    def test_nested_option_list_fails(self):
        text = GOOD.replace("2. The staging store, cleared by hand each week.",
                            "2. The staging store.\n   1. Cleared by hand.")
        self.assertIn("options_nested", rules(text))

    def test_missing_answer_block_fails(self):
        text = GOOD.split("**Answer like so:**")[0]
        self.assertIn("answer_block_missing", rules(text))

    def test_answer_block_without_one_space_indent_fails(self):
        self.assertIn("answer_block_format", rules(GOOD.replace(" 3. ok", "3. ok")))

    def test_answer_block_with_two_lines_fails(self):
        self.assertIn("answer_block_format", rules(GOOD.replace(" 3. ok\n", "")))

    def test_question_about_own_team_work_fails(self):
        text = GOOD.replace("Send the error text from the failed upload?", "Should I rerun the upload tests?")
        self.assertIn("team_work", rules(text))

    def test_requests_for_context_pass_as_the_answer_example(self):
        for request in ("please elaborate", "could you expand on the tradeoffs?", "why is the store full"):
            with self.subTest(request=request):
                text = GOOD.replace("explain where the log is written", request)
                self.assertEqual(rules(text), [])

    def test_test_as_a_verb_is_team_work(self):
        text = GOOD.replace("Send the error text from the failed upload?", "Should I test the upload?")
        self.assertIn("team_work", rules(text))

    def test_test_as_a_modifier_is_not_team_work(self):
        for title in ("Unlock the test account?", "Grant the importer access to test accounts?"):
            with self.subTest(title=title):
                text = GOOD.replace("Send the error text from the failed upload?", title)
                self.assertEqual(rules(text), [])

    def test_bullet_choices_fail(self):
        text = GOOD.replace("1. **The archive store, with one copy per day (recommended).**\n2. The staging store, "
                            "cleared by hand each week.",
                            "- **The archive store, with one copy per day (recommended).**\n- The staging store.")
        self.assertIn("options_not_numbered", rules(text))

    def test_indented_bullet_choices_fail(self):
        text = GOOD.replace("1. **The archive store, with one copy per day (recommended).**\n2. The staging store, "
                            "cleared by hand each week.",
                            " - **The archive store, with one copy per day (recommended).**\n - The staging store.")
        self.assertIn("options_not_numbered", rules(text))

    def test_reply_line_inside_a_question_fails(self):
        for line in ("Reply: ______", "[ ] yes"):
            with self.subTest(line=line):
                text = GOOD.replace("2. The staging store, cleared by hand each week.",
                                    "2. The staging store, cleared by hand each week.\n\n" + line)
                self.assertIn("question_extra", rules(text))

    def test_answer_example_without_the_three_answer_forms_fails(self):
        for example in (" alpha\n beta\n gamma", " 1. 1\n 2. banana\n 3. ok", " 1. 1\n 2. the cost is high\n 3. ok",
                        " 1. 1\n 2. no more context is needed\n 3. ok"):
            with self.subTest(example=example):
                text = GOOD.replace(" 1. 1\n 2. explain where the log is written\n 3. ok", example)
                self.assertEqual(rules(text), ["answer_block_format"])

    def test_recommended_options_outside_a_question_heading_fail(self):
        text = "**Should the import stop now?**\n1. **Stop it (recommended):** the batch is lost.\n2. Let it run.\n"
        self.assertEqual(sorted(rules(text)), ["options_without_question", "question_outside_heading"])

    def test_prose_question_outside_a_heading_fails(self):
        self.assertEqual(rules("The change is ready. Can you merge it?\n"), ["question_outside_heading"])

    def test_question_mark_inside_code_is_not_a_question(self):
        self.assertEqual(rules("The pattern `a?` matches an optional a.\n"), [])

    def test_question_after_the_answer_prompt_is_checked(self):
        text = GOOD + "\n## More\n\n### 1. Merge this?\nNo flag here.\n"
        found = rules(text)
        for rule in ("answer_block_order", "question_number_unescaped", "question_number_duplicate", "context_flag"):
            with self.subTest(rule=rule):
                self.assertIn(rule, found)

    def test_quote_inside_a_question_fails(self):
        text = GOOD.replace("`FACT` The upload log", "> the log said nothing\n\n`FACT` The upload log")
        self.assertIn("question_extra", rules(text))

    def test_fenced_heading_is_ignored(self):
        text = "Example of the format:\n\n```markdown\n### 1. Not escaped?\n```\n"
        self.assertEqual(question_format.check(text), [])


class CommandLineTest(unittest.TestCase):
    def run_check(self, text):
        return subprocess.run([sys.executable, "-B", str(HERE / "question_format.py")], input=text,
                              stdin=None, capture_output=True, text=True)

    def test_exit_status_is_zero_on_pass_and_two_on_fail(self):
        self.assertEqual(self.run_check(GOOD).returncode, 0)
        failed = self.run_check(GOOD.replace("### 1\\.", "### 1."))
        self.assertEqual(failed.returncode, 2)
        self.assertIn('"rule": "question_number_unescaped"', failed.stdout)

    def test_unreadable_path_exits_one(self):
        result = subprocess.run([sys.executable, "-B", str(HERE / "question_format.py"), str(HERE / "missing.md")],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)

    def test_unknown_argument_exits_one(self):
        result = subprocess.run([sys.executable, "-B", str(HERE / "question_format.py"), "--nope"],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
