"""Check H: the legacy requirements file is only a banner and an index table."""

import unittest

from tools.docs_check.tests.fixture_tree import CheckerCase


class LegacyTest(CheckerCase):
    def test_requirement_text_in_legacy_index_is_reported_once(self):
        result = self.assertSeeded(
            lambda t: t.append("docs/requirements.md", "\nThe system must do X.\nAnd also Y.\n\n## 5. More\n"),
            "H docs/requirements.md:",
            "--only",
            "H",
        )
        self.assertEqual(len(result.lines), 1, result.stdout)
        self.assertTrue(result.lines[0].startswith("H docs/requirements.md:10 "), result.stdout)
        self.assertIn("3 ", result.lines[0])

    def test_missing_banner_is_reported(self):
        tree = self.tree()
        tree.replace("docs/requirements.md", "Not authoritative. ", "Authoritative. ")
        self.assertFinding(tree.run("--only", "H"), "H docs/requirements.md:")


if __name__ == "__main__":
    unittest.main()
