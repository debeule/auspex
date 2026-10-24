"""Check K: each active ID has one verification row whose evidence exists."""

import unittest

from tools.docs_check.tests.fixture_tree import BLOCKING_PENDING, FIRST_CHOICE, OPEN_QUESTION, CheckerCase


class VerificationTest(CheckerCase):
    def test_active_id_without_verification_row_is_reported(self):
        result = self.assertSeeded(
            lambda t: t.replace(
                "docs/alpha.md",
                "## Known traps",
                '- <a id="AAA-005"></a>**AAA-005** A new rule.\n\n## Known traps',
            ),
            "K docs/alpha.md:",
            "--only",
            "K",
        )
        self.assertIn("AAA-005", result.stdout)

    def test_row_for_undefined_id_and_duplicate_row_are_reported(self):
        tree = self.tree()
        tree.replace(
            "docs/invariants.md",
            "| INV-3 | CLAUDE.md |",
            "| INV-3 | CLAUDE.md | x | enforced |\n| INV-7 | CLAUDE.md | x | enforced |\n| INV-3 | CLAUDE.md |",
        )
        result = tree.run("--only", "K")
        self.assertFinding(result, "K docs/invariants.md:")
        self.assertIn("INV-7", result.stdout)
        self.assertIn("INV-3", result.stdout)

    def test_tested_row_naming_missing_test_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("services/alpha/tests/test_app.py", "def test_alpha_one(", "def test_alpha_first("),
            "K docs/",
            "--only",
            "K",
        )

    def test_tested_row_accepts_python_java_and_vitest_names(self):
        tree = self.tree()
        row = tree.read("docs/invariants.md")
        self.assertIn("WriterTest.java::onlyHubWrites", row)
        self.assertIn("test_app.py::test_alpha_one", row)
        self.assertClean(tree.run("--only", "K"))
        tree.replace("services/alpha/src/WriterTest.java", "void onlyHubWrites(", "void onlyHubWritesAll(")
        self.assertFinding(tree.run("--only", "K"), "K docs/invariants.md:")

    def test_tested_row_needs_at_least_one_test_token(self):
        tree = self.tree()
        tree.replace("docs/invariants.md", "| INV-3 | CLAUDE.md | ArchUnit rule in the hub | enforced |",
                     "| INV-3 | CLAUDE.md | the hub tests | tested |")
        self.assertFinding(tree.run("--only", "K"), "K docs/invariants.md:")

    def test_bare_typescript_test_file_resolves_under_bare_test_dirs(self):
        tree = self.tree()
        self.assertClean(tree.run("--only", "K"))
        tree.replace("services/dashboard/src/__tests__/auth.test.ts", "rejects a bad password", "rejects a wrong one")
        self.assertFinding(tree.run("--only", "K"), "K docs/invariants.md:")
        tree.replace("services/dashboard/src/__tests__/auth.test.ts", "rejects a wrong one", "rejects a bad password")
        self.assertClean(tree.run("--only", "K"))
        tree.replace("docs/invariants.md", "`auth.test.ts::", "`login.test.ts::")
        self.assertFinding(tree.run("--only", "K"), "K docs/invariants.md:")

    def test_divergent_row_without_decision_citation_is_reported(self):
        tree = self.tree()
        text = tree.read("docs/alpha.md")
        line = next(l for l in text.splitlines() if l.startswith("| AAA-003 |"))
        tree.write("docs/alpha.md", text.replace(line, "| AAA-003 | plain prose | `services/alpha/tests/test_app.py::test_alpha_two` | `divergent` |"))
        self.assertFinding(tree.run("--only", "K"), "K docs/alpha.md:")

    def test_pending_row_citing_non_pending_heading_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("docs/alpha.md", f"`{OPEN_QUESTION}`", f"`{FIRST_CHOICE}`"),
            "K docs/alpha.md:",
            "--only",
            "K",
        )

    def test_pending_row_citing_another_pending_heading_passes(self):
        tree = self.tree()
        tree.replace("docs/alpha.md", f"`{OPEN_QUESTION}`", f"`{BLOCKING_PENDING}`")
        self.assertClean(tree.run("--only", "K"))

    def test_empty_source_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("docs/invariants.md", "| INV-3 | CLAUDE.md |", "| INV-3 |  |"),
            "K docs/invariants.md:",
            "--only",
            "K",
        )

    def test_unknown_status_and_empty_enforced_evidence_are_reported(self):
        tree = self.tree()
        tree.replace("docs/invariants.md", "| ArchUnit rule in the hub | enforced |", "|  | enforced |")
        self.assertFinding(tree.run("--only", "K"), "K docs/invariants.md:")
        tree.replace("docs/invariants.md", "|  | enforced |", "| x | guessed |")
        self.assertFinding(tree.run("--only", "K"), "K docs/invariants.md:")


if __name__ == "__main__":
    unittest.main()
