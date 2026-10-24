"""Check L: agent instruction files, their byte budgets and their imports."""

import unittest

from tools.docs_check.tests.fixture_tree import CheckerCase


def padded(text: str, size: int) -> str:
    """`text` padded with filler lines to exactly `size` UTF-8 bytes."""
    filler = size - len(text.encode("utf-8"))
    lines = []
    while filler > 0:
        chunk = min(filler, 80)
        lines.append("x" * (chunk - 1) + "\n" if chunk > 1 else "\n")
        filler -= chunk
    result = text + "".join(lines)
    assert len(result.encode("utf-8")) == size
    return result


class BudgetTest(CheckerCase):
    def test_root_agents_over_budget_is_reported(self):
        tree = self.tree()
        tree.write("AGENTS.md", padded(tree.read("AGENTS.md"), 6144))
        self.assertClean(tree.run("--only", "L"))
        tree.write("AGENTS.md", padded(tree.read("AGENTS.md")[:200], 6145))
        self.assertFinding(tree.run("--only", "L"), "L AGENTS.md:")

    def test_nested_agents_over_budget_is_reported(self):
        tree = self.tree()
        tree.write("services/AGENTS.md", padded("# Services\n", 3072))
        self.assertClean(tree.run("--only", "L"))
        tree.write("services/AGENTS.md", padded("# Services\n", 3073))
        self.assertFinding(tree.run("--only", "L"), "L services/AGENTS.md:")

    def test_chain_over_budget_is_reported(self):
        tree = self.tree()
        tree.write("AGENTS.md", padded(tree.read("AGENTS.md"), 6144))
        for directory in ("services", "services/a", "services/a/b"):
            tree.write(f"{directory}/AGENTS.md", padded("# Notes\n", 3072))
        self.assertClean(tree.run("--only", "L"))
        tree.write("services/a/b/c/AGENTS.md", padded("# Notes\n", 3072))
        result = tree.run("--only", "L")
        self.assertFinding(result, "L services/a/b/c/AGENTS.md:")
        self.assertEqual(len(result.lines), 1, result.stdout)


class ClaudeFileTest(CheckerCase):
    def test_claude_md_not_starting_with_agents_import_is_reported(self):
        self.assertSeeded(
            lambda t: t.write("services/CLAUDE.md", "See AGENTS.md\n"), "L services/CLAUDE.md:", "--only", "L"
        )

    def test_nested_claude_md_without_its_ancestor_imports_is_reported(self):
        self.assertSeeded(
            lambda t: t.write("services/CLAUDE.md", "@AGENTS.md\n"), "L services/CLAUDE.md:", "--only", "L"
        )

    def test_claude_md_with_ancestors_out_of_order_is_reported(self):
        self.assertSeeded(
            lambda t: t.write("services/CLAUDE.md", "@AGENTS.md\n@../AGENTS.md\n"), "L services/CLAUDE.md:", "--only", "L"
        )

    def test_claude_md_with_must_is_reported(self):
        self.assertSeeded(
            lambda t: t.append("CLAUDE.md", "You MUST read it first.\n"), "L CLAUDE.md:", "--only", "L"
        )

    def test_claude_md_over_512_bytes_is_reported(self):
        self.assertSeeded(
            lambda t: t.write("CLAUDE.md", padded("@AGENTS.md\n", 513)), "L CLAUDE.md:", "--only", "L"
        )

    def test_claude_md_without_sibling_agents_md_is_reported(self):
        self.assertSeeded(
            lambda t: t.write("services/alpha/CLAUDE.md", "@AGENTS.md\n"),
            "L services/alpha/CLAUDE.md:",
            "--only",
            "L",
        )

    def test_root_agents_md_missing_is_reported(self):
        self.assertSeeded(lambda t: t.delete("AGENTS.md"), "L AGENTS.md:0 ", "--only", "L")


class ImportTest(CheckerCase):
    def test_import_in_agents_md_is_reported(self):
        tree = self.tree()
        tree.append("AGENTS.md", "\nAn address `a@b.md` in code is fine, and so is `claude @docs/x.md`.\n\n"
                    "```\n@docs/fenced.md\n```\n")
        self.assertClean(tree.run("--only", "L"))
        tree.append("AGENTS.md", "\nRead @docs/x.md first.\n")
        result = tree.run("--only", "L")
        self.assertFinding(result, "L AGENTS.md:")
        self.assertEqual(len(result.lines), 1, result.stdout)

    def test_at_followed_by_a_word_is_not_an_import(self):
        tree = self.tree()
        tree.append("services/AGENTS.md", "\nNothing is imported; no @imports here.\n")
        self.assertClean(tree.run("--only", "L"))


if __name__ == "__main__":
    unittest.main()
