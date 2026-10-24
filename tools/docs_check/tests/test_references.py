"""Check D: ID references, invariant aliases, placeholders, decision citations and register numbers."""

import unittest

from tools.docs_check.tests.fixture_tree import (
    FIRST_CHOICE,
    HEADING_SIZER,
    MATRIX,
    REPO_ROOT,
    CheckerCase,
    run_checker,
)

COMPANION_LINES = (
    "\nUnresolved AAA-999 here.\n\nA placeholder AAA-? here.\n\nA register label D-12 here.\n\n"
    "A citation `2026-01-01 — Alpha — CHOICE — no such choice` here.\n"
)


class ReferencesTest(CheckerCase):
    def test_unresolved_id_reference_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("docs/alpha.md", "What alpha covers.", "What alpha covers, see AAA-999."),
            "D docs/alpha.md:",
            "--only",
            "D",
        )

    def test_invariant_alias_resolves_and_unresolved_alias_is_reported(self):
        tree = self.tree()
        self.assertIn("Invariants 1 and 2", tree.read("docs/alpha.md"))
        tree.append("specs/first.md", "\nBoth invariant #2 and Invariants 1 and 3 hold.\n")
        self.assertClean(tree.run("--only", "D"))
        tree.append("specs/first.md", "\nInvariant 9 does not exist.\n")
        result = tree.run("--only", "D")
        self.assertFinding(result, "D specs/first.md:")
        self.assertIn("INV-9", result.stdout)

    def test_active_spec_citing_retired_id_is_reported(self):
        self.assertSeeded(
            lambda t: t.append("specs/first.md", "\nKeeps AAA-004 alive.\n"), "D specs/first.md:", "--only", "D"
        )

    def test_placeholder_id_is_reported(self):
        self.assertSeeded(
            lambda t: t.append("specs/first.md", "\nAllocates AAA-? later.\n"), "D specs/first.md:", "--only", "D"
        )

    def _planned_beta_references(self, tree):
        tree.append("docs/alpha.md", "\nBeta lives in `docs/beta.md`.\n")
        tree.append("specs/first.md", "\nBuilds BBB-001 and BBB-? and [beta](../docs/beta.md#scope).\n")

    def test_planned_domain_link_path_id_and_placeholder_are_notices(self):
        tree = self.tree()
        self._planned_beta_references(tree)
        result = tree.run()
        self.assertClean(result)
        notices = result.notices
        for prefix in ("A notice specs/first.md:", "B notice docs/alpha.md:", "D notice specs/first.md:"):
            self.assertTrue(any(n.startswith(prefix) for n in notices), f"{prefix} missing in {notices}")
        self.assertTrue(any("BBB-001" in n for n in notices), notices)
        self.assertTrue(any("BBB-?" in n for n in notices), notices)

    def test_removing_domain_from_planned_turns_notices_into_findings(self):
        tree = self.tree()
        self._planned_beta_references(tree)
        tree.replace("docs-check.toml", 'planned_domains = ["beta"]', "planned_domains = []")
        result = tree.run()
        self.assertEqual(result.code, 1, result.stderr)
        self.assertEqual(result.notices, [])
        for prefix in ("A specs/first.md:", "B docs/alpha.md:", "D specs/first.md:", "F docs/beta.md:"):
            self.assertTrue(any(line.startswith(prefix) for line in result.lines), f"{prefix}:\n{result.stdout}")
        self.assertTrue(any("BBB-001" in line for line in result.lines))
        self.assertTrue(any("BBB-?" in line for line in result.lines))

    def test_missing_directory_of_planned_owner_docs_gives_notices(self):
        tree = self.tree()
        tree.replace("docs-check.toml", 'owners = ["docs/beta.md"]', 'owners = ["docs/beta/one.md", "docs/beta/two.md"]')
        tree.append("docs/alpha.md", "\nBeta will live in `docs/beta/` and `docs/beta/other.md`.\n")
        tree.replace("specs/first.md", "(../docs/beta.md)", "(../docs/beta/one.md)")
        tree.append("specs/first.md", "\nSee [beta](../docs/beta/).\n")
        result = tree.run()
        self.assertClean(result)
        self.assertEqual(len([n for n in result.notices if n.startswith(("A notice", "B notice"))]), 4, result.stderr)
        tree.append("docs/alpha.md", "\nGamma is not planned: `docs/gamma/`.\n")
        self.assertFinding(tree.run(), "B docs/alpha.md:")

    def test_unknown_decision_heading_is_reported(self):
        self.assertSeeded(
            lambda t: t.append("specs/first.md", "\nPer `2026-01-01 — Alpha — CHOICE — first pick`.\n"),
            "D specs/first.md:",
            "--only",
            "D",
        )

    def test_template_citation_with_ellipsis_is_skipped(self):
        tree = self.tree()
        tree.append(
            "specs/first.md",
            "\nCite as `## 2026-01-01 — <topic> — CHOICE — <title>` or `2026-01-01 — Alpha — CHOICE — …`.\n",
        )
        self.assertClean(tree.run("--only", "D"))

    def test_bare_register_number_in_living_doc_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("docs/alpha.md", "What alpha covers.", "What alpha covers (D-12)."),
            "D docs/alpha.md:",
            "--only",
            "D",
        )

    def test_register_number_in_spec_is_reported(self):
        tree = self.tree()
        tree.append(
            "specs/first.md",
            f"\nAs agreed in D-04.\n\nPer `{FIRST_CHOICE}` (D-05).\n\n| Item | Label |\n|---|---|\n| x | D-06 |\n",
        )
        result = tree.run("--only", "D")
        self.assertEqual(result.code, 1)
        register = [line for line in result.lines if "register number" in line]
        self.assertEqual(len(register), 3, result.stdout)
        self.assertTrue(all(line.startswith("D specs/first.md:") for line in register))

    def test_register_number_in_matrix_is_not_checked(self):
        tree = self.tree()
        tree.append(MATRIX, "\nNote: from D-07.\n")
        self.assertClean(tree.run("--only", "D"))

    def test_cutover_companions_are_excluded_from_d(self):
        tree = self.tree()
        tree.write("specs/living-docs-cutover-design.md", "# Design\n" + COMPANION_LINES)
        tree.append(MATRIX, COMPANION_LINES)
        result = tree.run("--only", "D")
        self.assertClean(result)
        self.assertFalse([n for n in result.notices if "cutover" in n], result.notices)
        tree.append("specs/hold/third.md", COMPANION_LINES)
        result = tree.run("--only", "D")
        self.assertEqual(len([line for line in result.lines if line.startswith("D specs/hold/third.md:")]), 4,
                         result.stdout)

    def test_double_backtick_citation_of_heading_with_backticks_resolves(self):
        tree = self.tree()
        for text in (tree.read("specs/first.md"), tree.read("docs/alpha.md"), tree.read(MATRIX)):
            self.assertIn(f"``{HEADING_SIZER}``", text.replace("``## ", "``"))
        self.assertClean(tree.run("--only", "D,K"))
        tree.replace("specs/first.md", "PositionSizer `fx_rate` is EUR", "PositionSizer `fx_rate` is USD")
        self.assertFinding(tree.run("--only", "D"), "D specs/first.md:")

    def test_ids_in_readmes_setup_versions_and_legacy_docs_are_resolved(self):
        tree = self.tree()
        tree.append("README.md", "\nSee AAA-901.\n")
        tree.append("SETUP.md", "\nSee AAA-902.\n")
        tree.append("VERSIONS.md", "\nSee AAA-903.\n")
        tree.append("docs/requirements.md", "| §15 | AAA-904 |\n")
        result = tree.run("--only", "D")
        self.assertEqual(result.code, 1)
        for path, ident in (("README.md", "AAA-901"), ("SETUP.md", "AAA-902"), ("VERSIONS.md", "AAA-903"),
                            ("docs/requirements.md", "AAA-904")):
            self.assertTrue(any(line.startswith(f"D {path}:") and ident in line for line in result.lines),
                            result.stdout)

    def test_agent_file_and_readme_citing_retired_id_is_reported(self):
        tree = self.tree()
        tree.append("AGENTS.md", "\nOld rule AAA-004.\n")
        tree.append("README.md", "\nOld rule AAA-004.\n")
        result = tree.run("--only", "D")
        self.assertEqual(result.code, 1)
        self.assertTrue(any(line.startswith("D AGENTS.md:") and "retired" in line for line in result.lines))
        self.assertTrue(any(line.startswith("D README.md:") and "retired" in line for line in result.lines))

    def test_retired_id_in_legacy_index_is_allowed(self):
        tree = self.tree()
        self.assertIn("AAA-004", tree.read("docs/requirements.md"))
        self.assertIn("AAA-004", tree.read("docs/alpha.md"))
        self.assertClean(tree.run("--only", "D"))

    def test_pr_body_references_are_checked(self):
        tree = self.tree()
        base = tree.head()
        tree.replace("services/alpha/app.py", "VALUE = 1", "VALUE = 4")
        tree.commit()
        good = tree.body(f"Implements AAA-001 per `{FIRST_CHOICE}`.\n\nDocs unchanged: alpha — refactor only\n")
        self.assertClean(tree.run("--base", base, "--pr-body", good))
        bad = tree.body(
            "Implements AAA-999 and AAA-?.\n\nPer `2026-01-01 — Alpha — CHOICE — no such`.\n\n"
            "Docs unchanged: alpha — refactor only\n"
        )
        result = tree.run("--base", base, "--pr-body", bad)
        self.assertEqual(result.code, 1)
        body_lines = [line for line in result.lines if line.startswith("D pr-body:")]
        self.assertEqual(len(body_lines), 3, result.stdout)

    def test_no_active_spec_carries_a_register_number(self):
        result = run_checker(REPO_ROOT, "--only", "D")
        self.assertIn(result.code, (0, 1), result.stderr)
        self.assertRegex(result.stderr, r"docs_check: (clean|\d+ findings)")
        offending = [
            line
            for line in result.lines
            if "register number" in line and (line.startswith("D specs/") and not line.startswith("D specs/done/"))
        ]
        self.assertEqual(offending, [])


if __name__ == "__main__":
    unittest.main()
