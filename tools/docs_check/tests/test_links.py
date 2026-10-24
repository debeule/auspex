"""Check A: relative links, fragments and frozen paths."""

import unittest

from tools.docs_check.tests.fixture_tree import CheckerCase


class LinksTest(CheckerCase):
    def test_broken_relative_link_is_reported(self):
        self.assertSeeded(lambda t: t.delete("services/alpha/app.py"), "A specs/first.md:", "--only", "A")

    def test_missing_anchor_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("docs/alpha.md", "## Known traps", "## Known pitfalls"),
            "A specs/first.md:",
            "--only",
            "A",
        )

    def test_explicit_id_anchor_satisfies_fragment(self):
        tree = self.tree()
        tree.append("specs/first.md", "\nSee [the rule](../docs/alpha.md#AAA-001).\n")
        self.assertClean(tree.run("--only", "A"))
        tree.append("specs/first.md", "\nSee [no rule](../docs/alpha.md#AAA-009).\n")
        self.assertFinding(tree.run("--only", "A"), "A specs/first.md:")

    def test_missing_frozen_path_is_reported(self):
        self.assertSeeded(lambda t: t.delete("README.md"), "A README.md:0 ", "--only", "A")

    def test_links_in_specs_done_and_decisions_are_not_checked(self):
        tree = self.tree()
        tree.append("specs/done/old.md", "\nSee [gone](gone.md) and [anchor](../docs/alpha.md#nowhere).\n")
        tree.append("DECISIONS.md", "\nSee [gone](gone.md).\n")
        tree.commit()
        self.assertClean(tree.run())

    def test_root_relative_link_resolves_from_repo_root(self):
        tree = self.tree()
        tree.append("specs/first.md", "\nSee [alpha](/docs/alpha.md#scope) and [site](https://example.com/x.md).\n")
        self.assertClean(tree.run("--only", "A"))
        tree.append("specs/first.md", "\nSee [nothing](/docs/nothing.md).\n")
        self.assertFinding(tree.run("--only", "A"), "A specs/first.md:")


if __name__ == "__main__":
    unittest.main()
