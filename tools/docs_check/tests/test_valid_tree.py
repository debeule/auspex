"""Every check and mode passes on the minimal valid tree; the real repository runs without a usage error."""

import re
import unittest

from tools.docs_check.tests.fixture_tree import BLOCKING_LIST, MATRIX, REPO_ROOT, CheckerCase, run_checker

FINDING_LINE = re.compile(r"^[A-M]2? \S+:\d+ .+$")


class ValidTreeTest(CheckerCase):
    def test_every_check_passes_on_minimal_valid_tree(self):
        tree = self.tree()
        self.assertClean(tree.run())
        base = tree.head()
        tree.replace("services/alpha/app.py", "VALUE = 1", "VALUE = 2")
        tree.replace("docs/alpha.md", "What alpha covers.", "What alpha covers, in full.")
        tree.commit("code and its owner doc")
        result = tree.run("--base", base, "--pr-body", tree.body(""))
        self.assertClean(result)
        self.assertNotIn("G skipped", result.stderr)
        self.assertClean(tree.run("--matrix", MATRIX, "--domain", "AAA"))
        self.assertClean(tree.run("--matrix", MATRIX, "--decisions"))
        self.assertClean(tree.run("--matrix", MATRIX, "--decisions", "--domain", "AAA"))
        self.assertClean(tree.run("--pending", "--blocking-list", BLOCKING_LIST))

    def test_dry_run_over_repository_completes_without_usage_error(self):
        result = run_checker(REPO_ROOT)
        self.assertIn(result.code, (0, 1), result.stderr)
        self.assertRegex(result.stderr, r"docs_check: (clean|\d+ findings)")
        for line in result.lines:
            self.assertRegex(line, FINDING_LINE)


if __name__ == "__main__":
    unittest.main()
