"""Check G: every domain a PR touches changes its owner doc or says why not."""

import unittest

from tools.docs_check.tests.fixture_tree import CheckerCase


class ImpactTest(CheckerCase):
    def _changed(self, mutate):
        tree = self.tree()
        base = tree.head()
        mutate(tree)
        tree.commit()
        return tree, base

    def _run(self, tree, base, body):
        return tree.run("--only", "G", "--base", base, "--pr-body", tree.body(body))

    def _code_change(self, tree):
        tree.replace("services/alpha/app.py", "VALUE = 1", "VALUE = 5")

    def test_code_change_without_owner_doc_or_disposition_is_reported(self):
        tree, base = self._changed(self._code_change)
        result = self._run(tree, base, "A code change.\n")
        self.assertFinding(result, "G services/alpha/app.py:0 ")
        self.assertIn("alpha", result.stdout)

    def test_owner_doc_change_satisfies_domain(self):
        def mutate(tree):
            self._code_change(tree)
            tree.replace("docs/alpha.md", "What alpha covers.", "What alpha covers now.")

        tree, base = self._changed(mutate)
        self.assertClean(self._run(tree, base, ""))

    def test_docs_unchanged_line_satisfies_domain(self):
        tree, base = self._changed(self._code_change)
        self.assertClean(self._run(tree, base, "Summary.\n\nDocs unchanged: alpha — test-only\n"))
        self.assertClean(self._run(tree, base, "- Docs unchanged: alpha -- constant rename\n"))

    def test_placeholder_or_empty_reason_is_rejected(self):
        tree, base = self._changed(self._code_change)
        self.assertFinding(self._run(tree, base, "Docs unchanged: alpha — <reason>\n"), "G pr-body:1 ")
        self.assertFinding(self._run(tree, base, "Docs unchanged: alpha —\n"), "G pr-body:1 ")

    def test_unknown_domain_in_disposition_is_reported(self):
        tree, base = self._changed(self._code_change)
        result = self._run(tree, base, "Docs unchanged: alpha — test-only\nDocs unchanged: gamma — nothing\n")
        self.assertFinding(result, "G pr-body:2 ")
        self.assertEqual(len(result.lines), 1, result.stdout)

    def test_shared_file_requires_every_domain(self):
        tree, base = self._changed(
            lambda t: t.replace("services/alpha/messaging/producer.py", "'alpha'", "'alpha.v2'")
        )
        result = self._run(tree, base, "Docs unchanged: alpha — rename only\n")
        self.assertEqual(result.code, 1)
        self.assertEqual(len(result.lines), 1, result.stdout)
        self.assertIn("system", result.lines[0])

    def test_added_choice_heading_requires_decisions_disposition(self):
        tree, base = self._changed(
            lambda t: t.append("DECISIONS.md", "\n## 2026-02-01 — Alpha — CHOICE — a new choice\n**What:** x.\n")
        )
        result = self._run(tree, base, "")
        self.assertFinding(result, "G DECISIONS.md:0 ")
        self.assertIn("decisions", result.stdout)
        self.assertClean(self._run(tree, base, "Docs unchanged: decisions — history only\n"))

    def test_choice_heading_with_living_doc_change_satisfies_decisions(self):
        def mutate(tree):
            tree.append("DECISIONS.md", "\n## 2026-02-01 — Alpha — CHOICE — a new choice\n")
            tree.replace("docs/invariants.md", "Numbered as in", "Numbered exactly as in")

        tree, base = self._changed(mutate)
        self.assertClean(self._run(tree, base, ""))

    def test_other_decisions_edit_needs_no_disposition(self):
        tree, base = self._changed(
            lambda t: t.append(
                "DECISIONS.md",
                "\n## 2026-02-01 — Alpha — PENDING — a question\n**What:** a CHOICE is still open.\n\n"
                "```\n## 2026-02-02 — Alpha — CHOICE — inside a fence\n```\n",
            )
        )
        self.assertClean(self._run(tree, base, ""))

    def test_mutant_and_revert_commits_cancel_in_net_diff(self):
        tree = self.tree()
        base = tree.head()
        self._code_change(tree)
        mutant = tree.commit("mutant")
        tree.git("revert", "--no-edit", mutant)
        self.assertClean(self._run(tree, base, ""))

    def test_diff_is_taken_from_the_merge_base(self):
        tree = self.tree()
        tree.git("checkout", "-q", "-b", "target")
        self._code_change(tree)
        target = tree.commit("work that landed on the target branch")
        tree.git("checkout", "-q", "main")
        self.assertClean(self._run(tree, target, ""))

    def test_rename_counts_old_and_new_path(self):
        def mutate(tree):
            tree.path("services/beta").mkdir()
            tree.git("mv", "services/alpha/app.py", "services/beta/app.py")

        tree, base = self._changed(mutate)
        result = self._run(tree, base, "Docs unchanged: beta — moved only\n")
        self.assertFinding(result, "G services/alpha/app.py:0 ")
        self.assertClean(self._run(tree, base, "Docs unchanged: beta — moved only\nDocs unchanged: alpha — moved\n"))


if __name__ == "__main__":
    unittest.main()
