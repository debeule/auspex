"""Check B: backticked repository paths in living docs and agent files."""

import unittest

from tools.docs_check.tests.fixture_tree import CheckerCase


class PathsTest(CheckerCase):
    def test_backticked_tracked_prefix_path_that_does_not_exist_is_reported(self):
        self.assertSeeded(
            lambda t: t.append("docs/alpha.md", "\nThe old code lived in `services/x/gone.py`.\n"),
            "B docs/alpha.md:",
            "--only",
            "B",
        )

    def test_path_with_line_or_test_suffix_is_resolved_without_suffix(self):
        tree = self.tree()
        tree.append(
            "docs/alpha.md",
            "\nSee `services/alpha/app.py:12`, `services/alpha/app.py:3-9`, "
            "`services/alpha/tests/test_app.py::test_alpha_one` and `docs/alpha.md#scope`.\n",
        )
        self.assertClean(tree.run("--only", "B"))
        tree.append("docs/alpha.md", "\nAnd `services/alpha/nope.py:12`.\n")
        self.assertFinding(tree.run("--only", "B"), "B docs/alpha.md:")

    def test_tokens_outside_prefixes_and_globs_are_ignored(self):
        tree = self.tree()
        tree.append(
            "docs/alpha.md",
            "\nSee `scripts/x.py`, `strategy/killswitch/global.json`, `docs/**/*.md`, `docs/<name>.md` "
            "and `services/$SERVICE/x.py`.\n",
        )
        self.assertClean(tree.run("--only", "B"))

    def test_path_check_ignores_specs_and_readmes(self):
        tree = self.tree()
        tree.append("specs/first.md", "\nOld code: `services/x/gone.py`.\n")
        tree.append("README.md", "\nOld code: `services/x/gone.py`.\n")
        self.assertClean(tree.run("--only", "B"))

    def test_path_in_agent_file_is_checked(self):
        tree = self.tree()
        tree.append("services/AGENTS.md", "\nSee `services/alpha/app.py` and `docs/`.\n")
        self.assertClean(tree.run("--only", "B"))
        tree.append("services/AGENTS.md", "\nSee `docker/compose.yml`.\n")
        self.assertFinding(tree.run("--only", "B"), "B services/AGENTS.md:")


if __name__ == "__main__":
    unittest.main()
