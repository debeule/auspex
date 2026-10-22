"""Checks C and C2: one definition per ID, and no ID disappears since the base."""

import unittest

from tools.docs_check.tests.fixture_tree import CheckerCase

RETIRED_LINE = "- **AAA-004** Alpha wrote twice (from requirements §13). Replaced by AAA-001.\n"


class UniqueTest(CheckerCase):
    def test_id_defined_twice_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace(
                "docs/invariants.md",
                "## Verification",
                '- <a id="AAA-001"></a>**AAA-001** A copy.\n\n## Verification',
            ),
            "C docs/",
            "--only",
            "C",
        )

    def test_retired_and_active_definition_of_one_id_is_reported(self):
        self.assertSeeded(
            lambda t: t.append("docs/alpha.md", "- **AAA-001** Retired copy of an active rule.\n"),
            "C docs/alpha.md:",
            "--only",
            "C",
        )

    def test_invariant_cannot_be_retired(self):
        self.assertSeeded(
            lambda t: t.append("docs/invariants.md", "\n- **INV-4** A retired invariant.\n"),
            "C docs/invariants.md:",
            "--only",
            "C",
        )


class NoReuseTest(CheckerCase):
    def test_id_removed_since_base_is_reported(self):
        tree = self.tree()
        base = tree.head()
        tree.replace("docs/alpha.md", RETIRED_LINE, "")
        tree.commit("drop a retired entry")
        result = tree.run("--only", "C2", "--base", base)
        self.assertFinding(result, "C2 docs/alpha.md:")
        self.assertIn("AAA-004", result.stdout)

    def test_id_moved_to_another_file_since_base_passes(self):
        tree = self.tree()
        base = tree.head()
        tree.replace("docs/alpha.md", RETIRED_LINE, "")
        tree.append("docs/invariants.md", "\n" + RETIRED_LINE)
        tree.commit("move a retired entry")
        self.assertClean(tree.run("--base", base))

    def test_default_mode_with_base_includes_c2(self):
        tree = self.tree()
        base = tree.head()
        tree.replace("docs/alpha.md", RETIRED_LINE, "")
        tree.commit("drop a retired entry")
        self.assertFinding(tree.run("--base", base), "C2 docs/alpha.md:")


if __name__ == "__main__":
    unittest.main()
