"""Check J: the TODO.md spec index matches the spec files."""

import unittest

from tools.docs_check.tests.fixture_tree import MATRIX, CheckerCase, spec_text

FIRST_ROW = "| [First](specs/first.md) | `ready` | the first |\n"


class IndexTest(CheckerCase):
    def test_duplicate_todo_row_is_reported(self):
        result = self.assertSeeded(
            lambda t: t.replace("TODO.md", "| [Old](specs/done/old.md)", FIRST_ROW + "| [Old](specs/done/old.md)"),
            "J TODO.md:",
            "--only",
            "J",
        )
        self.assertIn("specs/first.md", result.stdout)

    def test_status_mismatch_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("specs/first.md", "**Status:** ready", "**Status:** draft"),
            "J TODO.md:",
            "--only",
            "J",
        )

    def test_done_row_outside_specs_done_is_reported(self):
        def mutate(tree):
            tree.replace("specs/first.md", "**Status:** ready", "**Status:** done")
            tree.git("mv", "specs/first.md", "specs/done/first.md")

        self.assertSeeded(mutate, "J TODO.md:", "--only", "J")

    def test_done_status_row_pointing_into_specs_is_reported(self):
        tree = self.tree()
        tree.replace("specs/first.md", "**Status:** ready", "**Status:** done")
        tree.replace("TODO.md", "| [First](specs/first.md) | `ready`", "| [First](specs/first.md) | `done`")
        result = tree.run("--only", "J")
        self.assertFinding(result, "J TODO.md:")
        self.assertIn("specs/done/", result.stdout)

    def test_spec_without_row_is_reported(self):
        self.assertSeeded(
            lambda t: t.write("specs/fourth.md", spec_text("Fourth", "draft", "New.")),
            "J specs/fourth.md:0 ",
            "--only",
            "J",
        )

    def test_session_log_table_is_ignored(self):
        tree = self.tree()
        tree.append("TODO.md", "| 2026-01-02 | [Nothing](specs/nothing.md) | gone | No |\n"
                               "| 2026-01-03 | First | again | No |\n")
        self.assertClean(tree.run("--only", "J"))

    def test_matrix_and_design_companion_in_specs_done_need_no_row(self):
        tree = self.tree()
        tree.write("specs/living-docs-cutover-design.md", "# Design\n")
        tree.commit()
        tree.git("mv", MATRIX, "specs/done/living-docs-cutover-matrix.md")
        tree.git("mv", "specs/living-docs-cutover-design.md", "specs/done/living-docs-cutover-design.md")
        tree.commit()
        self.assertClean(tree.run("--only", "J"))


if __name__ == "__main__":
    unittest.main()
