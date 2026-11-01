"""Tests for report_check.py on synthetic operator reports."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report_check  # noqa: E402

GOOD = """\
**Blocker, credential: sign in to the alpha provider again with its hardware key.** Its jobs stop until then.

## Done
- **Importer:** `FACT` `python3 -m unittest tests/test_import.py` passed at 10:04 UTC.
- **Cost:** `FACT` [The spend ledger](https://example.com/ledger) shows 4.20 USD for the run.
- **Queue:** `ASSUMPTION` (the import lane's report) The queue held 12 jobs at 10:00 UTC.

## Parallelism before and after
`FACT` `config/run.json` sets 16 slots, up from 8.
"""


def rules(text, fields=()):
    return [item["rule"] for item in report_check.check(text, fields)]


class FactSourceTest(unittest.TestCase):
    def test_report_with_sources_and_labels_passes(self):
        self.assertEqual(report_check.check(GOOD, ["Parallelism before and after"]), [])

    def test_fact_without_source_fails(self):
        text = "`FACT` In the service log, the login expiry moved to 10:12 UTC.\n"
        self.assertEqual(rules(text), ["fact_source"])

    def test_documented_limits_of_the_code_span_rule(self):
        # Lead decision: a one-word command is rejected, a multi-word value passes.
        self.assertEqual(rules("`FACT` `uptime` shows a load of 3.\n"), ["fact_source"])
        self.assertEqual(rules("`FACT` All jobs are `in progress`.\n"), [])

    def test_command_in_a_code_span_is_a_source(self):
        for text in ("`FACT` `uptime -p` shows the host up for 3 days.\n",
                     "`FACT` I ran `make check` at 10:00 UTC; it passed.\n",
                     "`FACT` `cargo test --release -p core parse` completed successfully.\n",
                     "`FACT` The whitespace check passed with `git diff --check`.\n"):
            with self.subTest(text=text):
                self.assertEqual(rules(text), [])

    def test_fact_with_a_path_passes(self):
        self.assertEqual(rules("`FACT` The limit is 3600 s in config/limits.toml.\n"), [])

    def test_fact_with_a_quote_passes(self):
        self.assertEqual(rules('`FACT` The service log says "limit reached" at 10:12 UTC.\n'), [])

    def test_each_fact_sentence_needs_its_own_source(self):
        text = "`FACT` `uptime -p` shows the host up for 3 days. `FACT` The queue is empty.\n"
        self.assertEqual(rules(text), ["fact_source"])

    def test_sentence_covered_by_an_earlier_fact_label_needs_a_source(self):
        text = "`FACT` `uptime -p` shows the host up for 3 days. The queue is empty.\n"
        self.assertEqual(rules(text), ["fact_source"])

    def test_formatted_value_is_not_a_source(self):
        for text in ("`FACT` The queue contains `12` jobs.\n", "`FACT` All jobs are `done`.\n",
                     "`FACT` The run ended at `03:12`.\n"):
            with self.subTest(text=text):
                self.assertEqual(rules(text), ["fact_source"])

    def test_code_block_is_not_checked(self):
        self.assertEqual(rules("Example:\n\n```text\n`FACT` no source here\n```\n"), [])


class RelayTest(unittest.TestCase):
    def test_unlabelled_claim_from_another_lane_fails(self):
        self.assertEqual(rules("The import lane found 12 failed jobs.\n"), ["relay_label"])

    def test_relayed_claim_labelled_fact_fails(self):
        self.assertEqual(rules("`FACT` The review lane's report at `notes/review.md` says CI passed.\n"),
                         ["relay_label"])

    def test_relayed_claim_labelled_assumption_passes(self):
        self.assertEqual(rules("`ASSUMPTION` (the import lane's estimate) The run ends at 14:00 UTC.\n"), [])

    def test_label_carries_to_later_sentences_of_the_same_item(self):
        text = "- `ASSUMPTION` (worker report) Two jobs failed. The worker's report names a timeout.\n"
        self.assertEqual(rules(text), [])


class RequiredFieldTest(unittest.TestCase):
    def test_missing_required_field_fails(self):
        self.assertEqual(rules(GOOD, ["Thinking levels"]), ["required_field"])

    def test_field_given_as_bold_label_passes(self):
        self.assertEqual(rules("- **Thinking levels:** high for every model.\n", ["Thinking levels"]), [])

    def test_field_only_in_a_plain_table_cell_fails(self):
        text = "| Thinking levels | high |\n|---|---|\n"
        self.assertEqual(rules(text, ["Thinking levels"]), ["required_field"])

    def test_field_given_as_numbered_heading_passes(self):
        self.assertEqual(rules("## 2. Thinking levels\nHigh.\n", ["thinking levels"]), [])

    def test_plan_file_supplies_the_fields(self):
        plan = {"id": "c", "goal": "g", "instructions": [], "decisions": [], "policies": [], "constraints": [
            {"id": "a", "instructionId": "i", "rule": {"kind": "required_report_field", "field": "Thinking levels"}},
            {"id": "b", "instructionId": "i", "rule": {"kind": "minimum", "setting": "slots", "value": 16}}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "plan.json"
            path.write_text(json.dumps(plan))
            self.assertEqual(report_check.required_fields(str(path)), ["Thinking levels"])


class ReferenceTest(unittest.TestCase):
    def test_reference_to_text_elsewhere_fails(self):
        for text in ("The details are as discussed earlier.\n", "See above for the numbers.\n",
                     "My last message had the plan.\n", "The report also asks about the top-up.\n",
                     "See [the PR](https://example.com/pr) for the details.\n"):
            with self.subTest(text=text):
                self.assertIn("reference_elsewhere", rules(text))

    def test_words_inside_code_do_not_count(self):
        self.assertEqual(rules("Run `grep 'see above' notes.md` to list them.\n"), [])


class BlockerLineTest(unittest.TestCase):
    def test_blocker_named_in_a_middle_bullet_fails(self):
        text = "The run is slow.\n\n- Jobs time out.\n- The alpha account needs a top-up before more runs.\n"
        self.assertEqual(rules(text), ["blocker_first"])

    def test_bold_first_line_missing_one_blocker_fails(self):
        text = "**Blocker, balance: top up the alpha account.**\n\n- beta refuses: \"not authenticated with " \
               "one of your authorized hardware keys\".\n"
        found = report_check.check(text)
        self.assertEqual([item["rule"] for item in found], ["blocker_first"])
        self.assertIn("credential", found[0]["message"])

    def test_blocker_outside_the_bold_span_of_the_first_line_fails(self):
        self.assertEqual(rules("**Done.** The alpha account needs a top-up.\n"), ["blocker_first"])

    def test_blocker_line_after_the_first_line_fails(self):
        text = "Status at 10:00 UTC.\n\n**Blocker: none named here.**\n"
        self.assertEqual(rules(text), ["blocker_first"])

    def test_report_title_is_skipped(self):
        text = "# Status\n\n**Blocker, balance: top up the alpha account.**\n\nThe top-up unblocks 12 jobs.\n"
        self.assertEqual(rules(text), [])

    def test_report_without_blockers_needs_no_bold_line(self):
        self.assertEqual(rules("The run finished.\n\n- 12 jobs passed.\n"), [])

    def test_bare_status_number_is_not_a_blocker(self):
        self.assertEqual(rules("The run used 402 jobs and 4 029 tokens.\n"), [])


class CommandLineTest(unittest.TestCase):
    def run_check(self, *args, text=""):
        return subprocess.run([sys.executable, "-B", str(HERE / "report_check.py"), *args], input=text,
                              stdin=None, capture_output=True, text=True)

    def test_exit_status_is_zero_on_pass_and_two_on_fail(self):
        self.assertEqual(self.run_check(text=GOOD).returncode, 0)
        failed = self.run_check(text="`FACT` The queue is empty.\n")
        self.assertEqual(failed.returncode, 2)
        self.assertEqual(json.loads(failed.stdout)["rule"], "fact_source")

    def test_plan_that_is_not_json_exits_one(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "plan.json"
            path.write_text("goal: not json\n")
            self.assertEqual(self.run_check("--plan", str(path), text=GOOD).returncode, 1)


if __name__ == "__main__":
    unittest.main()
