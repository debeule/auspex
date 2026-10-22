"""Check F and `--owners`: every path owned, owner docs present unless planned."""

import unittest

from tools.docs_check.tests.fixture_tree import EMPTY_LIVING_DOC, REPO_ROOT, CheckerCase, run_checker


class OwnershipTest(CheckerCase):
    def test_unowned_path_is_reported(self):
        result = self.assertSeeded(lambda t: t.write("newdir/x.py", "X = 1\n"), "F newdir/x.py:0 ", "--only", "F")
        self.assertIn("unowned", result.stdout)

    def test_missing_owner_doc_is_reported_unless_domain_is_planned(self):
        tree = self.tree()
        self.assertFalse(tree.path("docs/beta.md").exists())
        self.assertClean(tree.run("--only", "F"))
        tree.delete("docs/invariants.md")
        tree.commit()
        result = tree.run("--only", "F")
        self.assertFinding(result, "F docs/invariants.md:0 ")
        self.assertNotIn("docs/beta.md", result.stdout)

    def test_planned_domain_with_all_owner_docs_present_is_reported(self):
        tree = self.tree()
        seed = tree.git("rev-list", "--max-parents=0", "HEAD")
        tree.write("docs/beta.md", EMPTY_LIVING_DOC.replace("{SEED}", seed))
        result = tree.run("--only", "F")
        self.assertFinding(result, "F docs-check.toml:")
        self.assertIn("planned_domains", result.stdout)

    def test_owners_prints_union_of_domains_for_shared_file(self):
        tree = self.tree()
        shared = tree.run("--owners", "services/alpha/messaging/producer.py", "README.md")
        self.assertEqual(shared.code, 0, shared.stderr)
        lines = shared.stdout.splitlines()
        self.assertEqual(lines[0], "services/alpha/messaging/producer.py\talpha,system\tdocs/alpha.md docs/invariants.md")
        self.assertEqual(lines[1], "README.md\tunowned-ok")
        unowned = tree.run("--owners", "newdir/x.py", "services/alpha/gone.py")
        self.assertEqual(unowned.code, 1)
        self.assertEqual(unowned.stdout.splitlines()[0], "newdir/x.py\tUNOWNED")
        self.assertEqual(unowned.stdout.splitlines()[1], "services/alpha/gone.py\talpha\tdocs/alpha.md")

    def test_repository_ownership_map_covers_every_tracked_path(self):
        result = run_checker(REPO_ROOT, "--only", "F")
        self.assertIn(result.code, (0, 1), result.stderr)
        self.assertRegex(result.stderr, r"docs_check: (clean|\d+ findings)")
        self.assertEqual([line for line in result.lines if "unowned" in line], [])


if __name__ == "__main__":
    unittest.main()
