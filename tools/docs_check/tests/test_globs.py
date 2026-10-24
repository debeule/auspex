"""Path globs and the ownership rules built on them."""

import unittest

from tools.docs_check import globs
from tools.docs_check.tests.fixture_tree import CheckerCase


class GlobTest(unittest.TestCase):
    def test_double_star_matches_zero_or_more_segments(self):
        self.assertTrue(globs.match("**/README.md", "README.md"))
        self.assertTrue(globs.match("**/README.md", "a/b/README.md"))
        self.assertTrue(globs.match("services/*/dags/**", "services/x/dags/a.py"))
        self.assertFalse(globs.match("services/*/dags/**", "services/x/y/dags/a.py"))
        self.assertTrue(globs.match("docs/**/*.md", "docs/a.md"))
        self.assertTrue(globs.match("docs/**/*.md", "docs/x/y/a.md"))
        self.assertFalse(globs.match("specs/*.md", "specs/done/a.md"))
        self.assertTrue(globs.match("a?c.md", "abc.md"))
        self.assertFalse(globs.match("a?c.md", "a/c.md"))


class OverrideTest(CheckerCase):
    def test_override_rule_replaces_union_domains(self):
        tree = self.tree()
        result = tree.run(
            "--owners", "services/alpha/tests/test_stack_compose.py", "services/alpha/messaging/producer.py"
        )
        self.assertEqual(result.code, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0].split("\t")[:2], ["services/alpha/tests/test_stack_compose.py", "system"])
        self.assertEqual(lines[1].split("\t")[:2], ["services/alpha/messaging/producer.py", "alpha,system"])


if __name__ == "__main__":
    unittest.main()
