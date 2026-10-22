"""Check M (rollout only): the migration matrix, the decisions table, the blocking list and the rollout workflows.

The living-docs cutover deletes this module together with the check.
"""

import re
import unittest

from tools.docs_check.tests.fixture_tree import (
    BLOCKING_LIST,
    BLOCKING_PENDING,
    FIRST_CHOICE,
    HISTORY_CHOICE,
    MATRIX,
    OPEN_QUESTION,
    REPO_ROOT,
    CheckerCase,
)

DOMAIN = ("--matrix", MATRIX, "--domain", "AAA")
DECISIONS_MODE = ("--matrix", MATRIX, "--decisions")
PENDING = ("--pending", "--blocking-list", BLOCKING_LIST)


def row(row_id: str, source: str, klass: str, disposition: str, ns: str, entry: str) -> str:
    return f"| {row_id} | {source} | rule | {klass} | {disposition} | docs/alpha.md | {ns} | first |  | {entry} |\n"


class MatrixRowsTest(CheckerCase):
    def _add_rows(self, tree, *rows):
        tree.append(MATRIX, "".join(rows))

    def _set_cell(self, tree, row_id, old_tail, new_tail):
        text = tree.read(MATRIX)
        line = next(l for l in text.splitlines() if l.startswith(f"| {row_id} |"))
        self.assertTrue(line.endswith(old_tail), line)
        tree.write(MATRIX, text.replace(line, line[: len(line) - len(old_tail)] + new_tail))

    def test_matrix_row_without_defined_id_is_reported(self):
        self.assertSeeded(
            lambda t: self._set_cell(t, "M-AAA-001", "| AAA-001 |", "|  |"),
            f"M {MATRIX}:",
            *DOMAIN,
        )

    def test_retire_row_must_point_at_retired_definition(self):
        tree = self.tree()
        self._set_cell(tree, "M-AAA-004", "| AAA-004 |", "| AAA-001 |")
        result = tree.run(*DOMAIN)
        self.assertFinding(result, f"M {MATRIX}:")
        self.assertIn("M-AAA-004", result.stdout)
        tree = self.tree()
        self._set_cell(tree, "M-AAA-001", "| AAA-001 |", "| AAA-004 |")
        self.assertFinding(tree.run(*DOMAIN), f"M {MATRIX}:")

    def test_matrix_id_whose_source_lacks_row_source_reference_is_reported(self):
        result = self.assertSeeded(
            lambda t: t.replace("docs/alpha.md", "`CLAUDE.md:140`; requirements §13;", "`CLAUDE.md:140`;"),
            f"M {MATRIX}:",
            *DOMAIN,
        )
        self.assertIn("M-AAA-002", result.stdout)
        self.assertNotIn("M-AAA-001", result.stdout)

    def test_source_reference_ignores_line_numbers(self):
        tree = self.tree()
        self.assertIn("| M-AAA-001 | `CLAUDE.md:137` |", tree.read(MATRIX))
        self.assertIn("| M-AAA-002 | requirements §13 ¶2 |", tree.read(MATRIX))
        self.assertClean(tree.run(*DOMAIN))
        tree.replace("docs/alpha.md", "`CLAUDE.md:140`", "`CLAUDE.md`")
        self.assertClean(tree.run(*DOMAIN))
        tree.replace("docs/alpha.md", "`CLAUDE.md`", "`services/CLAUDE.md`")
        self.assertFinding(tree.run(*DOMAIN), f"M {MATRIX}:")

    def test_section_relative_source_resolves_against_section_header(self):
        tree = self.tree()
        self.assertClean(tree.run(*DOMAIN))
        tree.replace("docs/alpha.md", "| AAA-002 | docs/legacy.md;", "| AAA-002 | docs/other.md;")
        result = tree.run(*DOMAIN)
        self.assertFinding(result, f"M {MATRIX}:")
        self.assertIn("M-AAA-003", result.stdout)
        tree = self.tree()
        tree.replace(MATRIX, "### `docs/legacy.md`", "### Legacy notes")
        result = tree.run(*DOMAIN)
        self.assertFinding(result, f"M {MATRIX}:")
        self.assertIn("M-AAA-003", result.stdout)

    def test_at_risk_or_scoping_or_same_as_source_gets_id_existence_only(self):
        tree = self.tree()
        sources = ("at-risk class #18", "C5", "same as M-AAA-001")
        self._add_rows(tree, *(row(f"M-AAA-02{i}", s, "requirement", "move", "AAA", "AAA-002")
                               for i, s in enumerate(sources)))
        self.assertClean(tree.run(*DOMAIN))
        tree = self.tree()
        self._add_rows(tree, *(row(f"M-AAA-02{i}", s, "requirement", "move", "AAA", "AAA-077")
                               for i, s in enumerate(sources)))
        result = tree.run(*DOMAIN)
        self.assertEqual(result.code, 1)
        self.assertEqual(len(result.lines), 3, result.stdout)

    def test_prose_or_two_word_label_source_gets_id_existence_only(self):
        tree = self.tree()
        sources = ("Statuses (new)", "E F18", "D F6")
        self._add_rows(tree, *(row(f"M-AAA-03{i}", s, "requirement", "ratify", "AAA", "AAA-002")
                               for i, s in enumerate(sources)))
        self.assertClean(tree.run(*DOMAIN))

    def test_matrix_row_id_is_not_an_id_reference(self):
        tree = self.tree()
        tree.append("specs/first.md", "\nFrom matrix row M-AAA-251.\n")
        self.assertClean(tree.run("--only", "D"))
        tree.append("specs/first.md", "\nAnd AAA-251 itself.\n")
        self.assertFinding(tree.run("--only", "D"), "D specs/first.md:")

    def test_trap_row_may_name_a_section_anchor(self):
        tree = self.tree()
        self.assertIn("docs/alpha.md#known-traps", tree.read(MATRIX))
        self.assertClean(tree.run(*DOMAIN))
        tree.replace(MATRIX, "| lowercase suffix | trap |", "| lowercase suffix | requirement |")
        self.assertFinding(tree.run(*DOMAIN), f"M {MATRIX}:")
        tree = self.tree()
        tree.replace(MATRIX, "docs/alpha.md#known-traps", "docs/alpha.md#rationale")
        self.assertFinding(tree.run(*DOMAIN), f"M {MATRIX}:")

    def test_trap_section_without_row_source_reference_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("docs/alpha.md", "(from CLAUDE.md, Known traps)", "(from the old notes)"),
            f"M {MATRIX}:",
            *DOMAIN,
        )

    def test_trap_row_explicit_item_anchor_checks_only_that_item(self):
        tree = self.tree()
        self._add_rows(tree, row("M-AAA-040", "`services/CLAUDE.md:30`", "trap", "move", "AAA",
                                 "docs/alpha.md#trap-dlt-suffix"))
        self.assertClean(tree.run(*DOMAIN))
        tree = self.tree()
        self._add_rows(tree, row("M-AAA-041", "CLAUDE.md:200", "trap", "move", "AAA",
                                 "docs/alpha.md#trap-dlt-suffix"))
        self.assertFinding(tree.run(*DOMAIN), f"M {MATRIX}:")
        tree = self.tree()
        tree.replace("docs/alpha.md", "Invariants 1 and 2 bound it",
                     'Invariants 1 and 2 bound it.\n\n- <a id="trap-outside"></a>From services/CLAUDE.md, bound it')
        self._add_rows(tree, row("M-AAA-042", "`services/CLAUDE.md:30`", "trap", "move", "AAA",
                                 "docs/alpha.md#trap-outside"))
        self.assertFinding(tree.run(*DOMAIN), f"M {MATRIX}:")

    def test_link_row_target_must_carry_anchor_or_source(self):
        tree = self.tree()
        self.assertIn("AGENTS.md#where-things-are", tree.read(MATRIX))
        self._add_rows(
            tree,
            row("M-AAA-050", "`CLAUDE.md:12`", "process", "link", "AAA", "docs/alpha.md"),
            row("M-AAA-051", "`CLAUDE.md:12`", "process", "link", "AAA", ""),
        )
        self.assertClean(tree.run(*DOMAIN))
        tree.replace(MATRIX, "AGENTS.md#where-things-are", "AGENTS.md#nowhere")
        self.assertFinding(tree.run(*DOMAIN), f"M {MATRIX}:")
        tree = self.tree()
        self._add_rows(tree, row("M-AAA-052", "`docker/compose.yml:3`", "process", "link", "AAA",
                                 "docs/invariants.md"))
        self.assertFinding(tree.run(*DOMAIN), f"M {MATRIX}:")

    def test_rows_of_other_namespaces_and_dispositions_are_not_checked(self):
        tree = self.tree()
        self._add_rows(tree, row("M-BBB-060", "`CLAUDE.md:9`", "requirement", "move", "BBB", ""),
                       row("M-AAA-061", "`CLAUDE.md:9`", "requirement", "keep", "AAA", ""))
        self.assertClean(tree.run(*DOMAIN))

    def test_matrix_without_id_column_exits_2(self):
        tree = self.tree()
        tree.append(MATRIX, "\n### `docs/more.md`\n\n| Row | Source | Disposition | NS |\n|---|---|---|---|\n"
                            "| M-AAA-070 | `CLAUDE.md:1` | move | AAA |\n")
        result = tree.run(*DOMAIN)
        self.assertEqual(result.code, 2)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith("docs_check: error:"))

    def test_missing_matrix_file_exits_2(self):
        result = self.tree().run("--matrix", "specs/nothing.md", "--domain", "AAA")
        self.assertEqual(result.code, 2)


class DecisionsTableTest(CheckerCase):
    def test_every_choice_heading_must_be_classified(self):
        result = self.assertSeeded(
            lambda t: t.replace(MATRIX, f"| `## {HISTORY_CHOICE}` | history |  | M-BBB-001 |\n", ""),
            "M DECISIONS.md:",
            *DECISIONS_MODE,
        )
        self.assertIn("history choice", result.stdout)

    def test_duplicate_row_unknown_heading_and_bad_classification_are_reported(self):
        tree = self.tree()
        tree.replace(
            MATRIX,
            f"| `## {HISTORY_CHOICE}` | history |  | M-BBB-001 |\n",
            f"| `## {HISTORY_CHOICE}` | history |  | M-BBB-001 |\n"
            f"| `## {HISTORY_CHOICE}` | history |  | M-BBB-001 |\n"
            "| `## 2026-01-09 — Alpha — CHOICE — never made` | history |  |  |\n",
        )
        tree.replace(MATRIX, f"| `## {FIRST_CHOICE}` | binding |", f"| `## {FIRST_CHOICE}` | maybe |")
        result = tree.run(*DECISIONS_MODE)
        self.assertEqual(result.code, 1)
        self.assertEqual(len([l for l in result.lines if l.startswith(f"M {MATRIX}:")]), 3, result.stdout)

    def test_fenced_template_heading_is_not_a_choice(self):
        tree = self.tree()
        self.assertIn("## YYYY-MM-DD — <topic> — [BLOCKED | FLAG | CHOICE", tree.read("DECISIONS.md"))
        self.assertClean(tree.run(*DECISIONS_MODE))

    def test_binding_choice_needs_an_id_citing_it_as_source(self):
        self.assertSeeded(
            lambda t: t.replace("docs/alpha.md", f"requirements §13; `{FIRST_CHOICE}`", "requirements §13"),
            f"M {MATRIX}:",
            *DECISIONS_MODE,
        )

    def test_binding_choice_with_empty_ids_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace(MATRIX, f"| binding | AAA-001 | M-AAA-001 |", "| binding |  | M-AAA-001 |"),
            f"M {MATRIX}:",
            *DECISIONS_MODE,
        )

    def test_decisions_check_filtered_by_domain(self):
        tree = self.tree()
        tree.append(
            "DECISIONS.md",
            "\n## 2026-03-01 — Beta — CHOICE — selected by ns\n\n## 2026-03-02 — Alpha — CHOICE — not selected\n\n"
            "## 2026-03-03 — Alpha — CHOICE — missing fragment\n\n## 2026-03-04 — Beta — CHOICE — beta only\n\n"
            "## 2026-03-05 — Alpha — CHOICE — unclassified\n",
        )
        tree.replace(
            MATRIX,
            "\n## Alpha (AAA)",
            "| `## 2026-03-01 — Beta — CHOICE — selected by ns` | binding |  | M-BBB-004 |\n"
            "| `## 2026-03-02 — Alpha — CHOICE — not selected` | binding |  | M-AAA-019 |\n"
            "| `## 2026-03-03 — Alpha — CHOICE — missing fragment` | binding |  | M-AAA-404 |\n"
            "| `## 2026-03-04 — Beta — CHOICE — beta only` | binding |  | M-BBB-001 |\n"
            "\n## Alpha (AAA)",
        )
        tree.append(MATRIX, row("M-BBB-004", "`CLAUDE.md:20`", "requirement", "keep", "AAA", "")
                    + row("M-AAA-019", "`CLAUDE.md:21`", "requirement", "keep", "BBB", ""))
        result = tree.run("--matrix", MATRIX, "--decisions", "--domain", "AAA")
        self.assertEqual(result.code, 1, result.stderr)
        self.assertEqual(len(result.lines), 2, result.stdout)
        self.assertIn("selected by ns", result.stdout)
        self.assertIn("M-AAA-404", result.stdout)
        self.assertNotIn("not selected", result.stdout)
        self.assertNotIn("beta only", result.stdout)
        self.assertNotIn("unclassified", result.stdout)


class PendingTest(CheckerCase):
    def test_pending_row_citing_blocking_heading_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("docs/alpha.md", f"`{OPEN_QUESTION}`", f"`{BLOCKING_PENDING}`"),
            "M docs/alpha.md:",
            *PENDING,
        )

    def test_pending_row_citing_non_blocking_heading_passes(self):
        tree = self.tree()
        self.assertIn(f"`{OPEN_QUESTION}` | none yet | `pending-decision`", tree.read("docs/alpha.md"))
        self.assertClean(tree.run(*PENDING))

    def test_pending_row_citing_no_pending_heading_is_reported(self):
        self.assertSeeded(
            lambda t: t.replace("docs/alpha.md", f"; `{OPEN_QUESTION}`", ""), "M docs/alpha.md:", *PENDING
        )

    def test_blocking_list_cells_are_plain_suffix_text(self):
        tree = self.tree()
        self.assertIn("| raw-pointer contract |", tree.read(BLOCKING_LIST))
        tree.replace("docs/alpha.md", f"`{OPEN_QUESTION}`", f"`{BLOCKING_PENDING}`")
        self.assertFinding(tree.run(*PENDING), "M docs/alpha.md:")
        tree = self.tree()
        tree.append("DECISIONS.md", "\n## 2026-01-05 — Gamma — PENDING — as-of reads\n")
        tree.replace("docs/alpha.md", f"`{OPEN_QUESTION}`", "`2026-01-05 — Gamma — PENDING — as-of reads`")
        self.assertFinding(tree.run(*PENDING), "M docs/alpha.md:")


class RolloutWorkflowTest(unittest.TestCase):
    def test_docs_workflow_runs_report_only_with_body_through_env(self):
        text = (REPO_ROOT / ".github/workflows/docs.yml").read_text(encoding="utf-8")
        self.assertIn("types: [opened, synchronize, reopened, edited]", text)
        pull_request = text[text.index("pull_request:"): text.index("push:")]
        self.assertIn("- develop", pull_request)
        self.assertIn("- feature/living-docs-integration", pull_request)
        push = text[text.index("push:"): text.index("jobs:")]
        self.assertIn("- develop", push)
        self.assertIn("fetch-depth: 0", text)
        self.assertEqual(text.count("continue-on-error: true"), 1)
        steps = re.split(r"\n      - ", text)
        docs_step = next(s for s in steps if s.startswith("name: Docs check"))
        self.assertIn("continue-on-error: true", docs_step)
        tests_step = next(s for s in steps if s.startswith("name: Checker tests"))
        self.assertNotIn("continue-on-error", tests_step)
        body_uses = [line.strip() for line in text.splitlines() if "github.event.pull_request.body" in line]
        self.assertEqual(body_uses, ["PR_BODY: ${{ github.event.pull_request.body }}"])
        for step in steps:
            if "run:" in step:
                run_part = step[step.index("run:"):]
                self.assertNotIn("pull_request.body", run_part)
        self.assertIn("0000000000000000000000000000000000000000", text)

    def test_commit_identity_workflow_covers_integration_branch(self):
        text = (REPO_ROOT / ".github/workflows/commit-identity.yml").read_text(encoding="utf-8")
        branches = text[text.index("pull_request:"): text.index("jobs:")]
        self.assertIn("- develop\n      - feature/living-docs-integration", branches)
        self.assertIn("- main", branches)


if __name__ == "__main__":
    unittest.main()
