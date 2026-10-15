#!/usr/bin/env python3
"""The review-staging check passes on this checkout and fails on a role that includes a file
the review service does not copy."""
import shutil
import tempfile
import unittest
from pathlib import Path

import check_review_staging

REPO = Path(__file__).resolve().parents[1]


class ReviewStagingTest(unittest.TestCase):
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
