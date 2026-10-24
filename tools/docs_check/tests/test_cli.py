"""The command line: output format, exit codes, modes, `--next` and `--paths`."""

import re
import tempfile
import unittest

from tools.docs_check.tests.fixture_tree import CheckerCase, run_checker

FINDING_LINE = re.compile(r"^[A-M]2? \S+:\d+ .+$")


class OutputTest(CheckerCase):
    def test_findings_are_printed_one_per_line_as_check_path_line_message(self):
        tree = self.tree()
        tree.append("specs/first.md", "\nSee AAA-999.\n")
        tree.append("docs/alpha.md", "\nSee [gone](gone.md).\n")
        result = tree.run()
        self.assertEqual(result.code, 1, result.stderr)
        self.assertEqual(len(result.lines), 2, result.stdout)
        for line in result.lines:
            self.assertRegex(line, FINDING_LINE)
        self.assertEqual(result.lines, sorted(result.lines))
        self.assertTrue(result.lines[0].startswith("A docs/alpha.md:"))
        self.assertTrue(result.lines[1].startswith("D specs/first.md:"))
        self.assertIn("docs_check: 2 findings (A=1, D=1)", result.stderr)


class ConfigErrorTest(CheckerCase):
    def _assert_usage_error(self, result):
        self.assertEqual(result.code, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith("docs_check: error:"), result.stderr)

    def test_invalid_config_exits_2_with_no_stdout(self):
        tree = self.tree()
        original = tree.read("docs-check.toml")
        tree.write("docs-check.toml", original.replace("[budgets]", "[budgets]\nsurprise = 1"))
        self._assert_usage_error(tree.run())
        tree.write("docs-check.toml", original.replace('ids = ["AAA", "BBB"]', 'ids = ["AB", "BBB"]'))
        self._assert_usage_error(tree.run())
        tree.write("docs-check.toml", original + "\n[[[ not toml\n")
        self._assert_usage_error(tree.run())

    def test_config_without_rollout_table_runs_as_if_nothing_is_planned(self):
        tree = self.tree()
        tree.drop_rollout()
        result = tree.run()
        self.assertEqual(result.code, 1, result.stderr)
        self.assertTrue(any(line.startswith("A specs/first.md:") for line in result.lines), result.stdout)
        self.assertTrue(any(line.startswith("F docs/beta.md:") for line in result.lines), result.stdout)
        self.assertEqual(result.notices, [])
        from tools.docs_check.tests.fixture_tree import EMPTY_LIVING_DOC

        tree.write("docs/beta.md", EMPTY_LIVING_DOC.replace("{SEED}", tree.git("rev-list", "--max-parents=0", "HEAD")))
        self.assertClean(tree.run())

    def test_unresolvable_base_exits_2(self):
        self._assert_usage_error(self.tree().run("--base", "nosuchref"))

    def test_only_g_without_base_exits_2(self):
        tree = self.tree()
        self._assert_usage_error(tree.run("--only", "G"))
        self._assert_usage_error(tree.run("--only", "C2"))

    def test_unknown_check_letter_exits_2(self):
        self._assert_usage_error(self.tree().run("--only", "A,Z"))

    def test_g_without_pr_body_is_skipped_not_failed(self):
        tree = self.tree()
        base = tree.head()
        tree.replace("services/alpha/app.py", "VALUE = 1", "VALUE = 3")
        tree.commit()
        result = tree.run("--base", base)
        self.assertClean(result)
        self.assertIn("G skipped: no PR body", result.stderr)

    def test_conflicting_modes_exit_2(self):
        self._assert_usage_error(self.tree().run("--next", "AAA", "--owners", "x"))

    def test_outside_a_git_work_tree_exits_2(self):
        with tempfile.TemporaryDirectory() as plain:
            self._assert_usage_error(run_checker(plain))

    def test_next_unknown_namespace_exits_2(self):
        self._assert_usage_error(self.tree().run("--next", "ZZZ"))

    def test_paths_empty_list_exits_2(self):
        self._assert_usage_error(self.tree().run("--paths", ""))


class NextTest(CheckerCase):
    def test_next_skips_retired_ids(self):
        result = self.tree().run("--next", "AAA")
        self.assertEqual((result.code, result.stdout), (0, "AAA-005\n"))

    def test_next_for_invariant_namespace_is_unpadded(self):
        result = self.tree().run("--next", "INV")
        self.assertEqual((result.code, result.stdout), (0, "INV-4\n"))

    def test_next_for_unused_namespace_starts_at_one(self):
        result = self.tree().run("--next", "BBB")
        self.assertEqual((result.code, result.stdout), (0, "BBB-001\n"))


class PathsTest(CheckerCase):
    def _two_defects(self):
        tree = self.tree()
        tree.append("specs/first.md", "\nSee AAA-999.\n")
        tree.append("specs/hold/third.md", "\nSee AAA-998.\n")
        return tree

    def test_paths_limits_reported_findings_and_notices(self):
        tree = self._two_defects()
        result = tree.run("--paths", "specs/first.md")
        self.assertEqual(result.code, 1)
        self.assertEqual(len(result.lines), 1, result.stdout)
        self.assertTrue(result.lines[0].startswith("D specs/first.md:"))
        self.assertTrue(result.notices, "the planned beta link in specs/first.md is a notice")
        clean = tree.run("--paths", "specs/second.md")
        self.assertClean(clean)
        self.assertEqual(clean.notices, [])
        self.assertIn("docs_check: clean", clean.stderr)

    def test_paths_accepts_comma_lists_and_several_arguments(self):
        tree = self._two_defects()
        tree.append("specs/second.md", "\nSee AAA-997.\n")
        comma = tree.run("--paths", "specs/hold/**,specs/first.md")
        several = tree.run("--paths", "specs/hold/third.md", "specs/first.md")
        self.assertEqual(comma.code, 1)
        self.assertEqual(len(comma.lines), 2, comma.stdout)
        self.assertEqual(comma.stdout, several.stdout)
        self.assertNotIn("specs/second.md", comma.stdout)

    def test_paths_combines_with_only(self):
        tree = self.tree()
        tree.append("specs/first.md", "\nSee [gone](gone.md) and AAA-999.\n")
        tree.append("specs/hold/third.md", "\nSee AAA-998.\n")
        result = tree.run("--only", "D", "--paths", "specs/first.md")
        self.assertEqual(result.code, 1)
        self.assertEqual(len(result.lines), 1, result.stdout)
        self.assertTrue(result.lines[0].startswith("D specs/first.md:"))
        other = tree.run("--only", "A", "--paths", "specs/hold/third.md")
        self.assertClean(other)
        self.assertIn("docs_check: clean", other.stderr)


if __name__ == "__main__":
    unittest.main()
