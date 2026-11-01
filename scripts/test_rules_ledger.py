"""rules_ledger.py records each change in a temporary home's ledger and reverts one with one command."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().with_name("rules_ledger.py")


class RulesLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = {**os.environ, "HOME": str(self.home)}
        self.env.pop("XDG_STATE_HOME", None)
        self.ledger = self.home / ".local/state/house-rules/ledger.jsonl"
        self.rule = self.home / "rules/core.md"
        self.rule.parent.mkdir()
        self.rule.write_text("- Keep records.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, stdin=b""):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], input=stdin, stdin=None, env=self.env,
                              capture_output=True)

    def records(self):
        return [json.loads(line) for line in self.ledger.read_text().splitlines()]

    def test_one_command_reverts_a_recorded_change_and_the_rollback_is_recorded(self):
        out = self.run_script("write", str(self.rule), "--actor", "agent", "--reason", "stronger wording",
                              "--pr", "#7", stdin=b"- Keep all records.\n")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.rule.read_text(), "- Keep all records.\n")
        [change] = self.records()
        self.assertEqual((change["action"], change["actor"], change["file"], change["reason"], change["source_pr"]),
                         ("change", "agent", str(self.rule.resolve()), "stronger wording", "#7"))
        self.assertNotEqual(change["before"], change["after"])

        out = self.run_script("rollback", change["id"])
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.rule.read_text(), "- Keep records.\n")
        _, rollback = self.records()
        self.assertEqual((rollback["action"], rollback["actor"], rollback["rollback_of"]),
                         ("rollback", "human", change["id"]))
        self.assertEqual((rollback["before"], rollback["after"]), (change["after"], change["before"]))

        out = self.run_script("rollback", rollback["id"])
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.rule.read_text(), "- Keep all records.\n")

    def test_rollback_of_a_new_file_removes_it(self):
        skill = self.home / "skills/new/SKILL.md"
        out = self.run_script("write", str(skill), "--actor", "service", "--reason", "add skill", stdin=b"x\n")
        self.assertEqual(out.returncode, 0, out.stderr)
        [change] = self.records()
        self.assertIsNone(change["before"])
        self.assertEqual(self.run_script("rollback", change["id"]).returncode, 0)
        self.assertFalse(skill.exists())

    def test_stored_contents_are_private_and_a_write_keeps_the_file_mode(self):
        self.rule.chmod(0o600)
        out = self.run_script("write", str(self.rule), "--actor", "agent", "--reason", "private", stdin=b"secret\n")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.rule.stat().st_mode & 0o777, 0o600)
        blobs = list((self.home / ".local/state/house-rules/ledger-blobs").iterdir())
        self.assertEqual(len(blobs), 2)
        self.assertEqual({blob.stat().st_mode & 0o777 for blob in blobs}, {0o600})

    def test_unchanged_content_and_unknown_ids_add_no_record(self):
        out = self.run_script("write", str(self.rule), "--actor", "human", "--reason", "same",
                              stdin=b"- Keep records.\n")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn(b"UNCHANGED", out.stdout)
        out = self.run_script("rollback", "000000000000")
        self.assertEqual(out.returncode, 1)
        self.assertIn(b"no ledger record", out.stderr)
        self.assertFalse(self.ledger.exists())


if __name__ == "__main__":
    unittest.main()
