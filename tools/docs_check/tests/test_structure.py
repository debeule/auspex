"""Check E: living-doc sections and review line, spec header fields and sections."""

import unittest

from tools.docs_check.tests.fixture_tree import CheckerCase


class LivingDocStructureTest(CheckerCase):
    def test_living_doc_missing_required_h2_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("docs/invariants.md", "## Retired requirements\n", ""),
            "E docs/invariants.md:",
            "--only",
            "E",
        )

    def test_last_reviewed_sha_not_ancestor_of_head_is_reported(self):
        tree = self.tree()
        tree.git("checkout", "-q", "-b", "side")
        tree.write("services/alpha/side.py", "SIDE = 1\n")
        side = tree.commit("side work")
        tree.git("checkout", "-q", "main")
        seed = tree.git("rev-list", "--max-parents=0", "HEAD")
        tree.replace("docs/alpha.md", seed, side)
        tree.commit()
        result = tree.run("--only", "E")
        self.assertFinding(result, "E docs/alpha.md:")
        self.assertIn("ancestor", result.stdout)

    def test_unknown_last_reviewed_sha_is_reported(self):
        tree = self.tree()
        seed = tree.git("rev-list", "--max-parents=0", "HEAD")
        tree.replace("docs/invariants.md", seed, "deadbeefdeadbeef")
        self.assertFinding(tree.run("--only", "E"), "E docs/invariants.md:")

    def test_living_doc_without_review_line_is_reported(self):
        tree = self.tree()
        seed = tree.git("rev-list", "--max-parents=0", "HEAD")
        tree.replace("docs/invariants.md", f"Last reviewed against: develop @ {seed}\n", "")
        self.assertFinding(tree.run("--only", "E"), "E docs/invariants.md:")

    def test_non_normative_docs_and_spec_readme_are_not_checked(self):
        tree = self.tree()
        tree.append("docs/README.md", "\nNo sections at all.\n")
        tree.append("specs/README.md", "\nNo fields at all.\n")
        self.assertClean(tree.run("--only", "E"))


class SpecStructureTest(CheckerCase):
    def test_spec_without_docs_impact_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("specs/first.md", "**Docs impact:** alpha — docs/alpha.md\n", ""),
            "E specs/first.md:",
            "--only",
            "E",
        )

    def test_blocked_spec_without_blocked_by_is_reported(self):
        tree = self.tree()
        text = tree.read("specs/second.md")
        start = text.index("**Blocked by:**")
        tree.write("specs/second.md", text[:start] + text[text.index("\n", start) + 1:])
        self.assertFinding(tree.run("--only", "E"), "E specs/second.md:")

    def test_hold_status_is_accepted(self):
        tree = self.tree()
        self.assertIn("**Status:** hold", tree.read("specs/hold/third.md"))
        self.assertClean(tree.run("--only", "E"))

    def test_unknown_status_and_missing_section_are_reported(self):
        tree = self.tree()
        tree.replace("specs/hold/third.md", "**Status:** hold", "**Status:** paused")
        tree.replace("specs/first.md", "## Out of scope", "## Not in scope")
        result = tree.run("--only", "E")
        self.assertFinding(result, "E specs/hold/third.md:")
        self.assertFinding(result, "E specs/first.md:")

    def test_spec_exclusions_cover_matrix_and_design_companion(self):
        tree = self.tree()
        tree.write("specs/living-docs-cutover-design.md", "# Design\n\nNo fields here.\n")
        self.assertNotIn("**Status:**", tree.read("specs/living-docs-cutover-matrix.md"))
        self.assertClean(tree.run("--only", "E"))


if __name__ == "__main__":
    unittest.main()
