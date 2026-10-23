# Legacy docs retirement

**Status:** done
**Blocked by:** `living-docs-system-and-contracts`, `living-docs-ingestion`, `living-docs-core-hub`, `living-docs-research`, `living-docs-strategy-and-dashboard`, `living-docs-operations`, `living-docs-engineering-workflow` (every requirement must have its owner in `docs/` before its old text is cut), and `agent-instruction-hierarchy` (service READMEs link to the service `AGENTS.md` files it creates, and the extended guard reads them), all merged into `feature/living-docs-integration`. Decisions: `## 2026-10-17 — Living docs — CHOICE — fate of docs/requirements.md` (option A: reduce it to a non-normative § → ID index), `## 2026-10-17 — Living docs — CHOICE — run_pipeline.py support` (option A: keep it as a developer tool listed in the scraper README scripts table; the root README stops presenting it as a way to run ingestion), `## 2026-10-17 — Living docs — CHOICE — rollout branch model` (option A: integration branch `feature/living-docs-integration`; each part PRs into it and merges on the owner's word).
**Branch:** `feature/legacy-docs-retirement` (from and into `feature/living-docs-integration`)
**Docs impact:** none — creates, changes and retires no requirement ID. Reduces `docs/requirements.md` to the non-normative § → ID index. Trims `README.md`, `docker/README.md`, `orchestration/README.md` and the six service READMEs to orientation plus links. Labels `docs/strategy-research.md` as rationale and replaces its copied registered values with links. Fixes stale lines in `SETUP.md`, `docs/PREREQUISITES.md`, one note in `VERSIONS.md`, and the stale blockers in eight `TODO.md` Notes cells. Extends one doc-reading test.

---

## Context

Written against `develop` @ `e51f742`. By the time this spec starts, the domain specs have written every requirement into `docs/` with an ID (namespaces `INV SYS CON ING EXT HUB COR RES EVA STR DSH OPS ENG`), and `agent-instruction-hierarchy` has created `AGENTS.md` at the root, in `services/`, in each of the six service directories and in `docker/`. The old files still hold their old text, so every rule now exists twice. This spec removes the second copy. The rollout design is `specs/living-docs-cutover-design.md`; everything this spec needs from it is restated here.

**Files and what is wrong with them at e51f742:**

| File | Size | What it holds now | Known defects |
|---|---|---|---|
| `docs/requirements.md` | 39 KB | §0–§14: assumptions, stack, topics, boundaries, corroboration, cursor, connectors, archive, prices, graph, identity, extraction, observability, testing, settled | Says "no code exists… greenfield" (`:3`); stage order wrong (`:164`); fixture path wrong (`:402`); DLT same-partition text (`:55`); plan-step references to the deleted `docs/plan.md` |
| `README.md` | 6.6 KB | Architecture paragraph, 3-service table, quick start, all commands, structure tree, status, key constraints, watched tickers | **Stale status and services:** `PROGRESS.md` in the tree (`:82`, file absent); "Phase 3 complete … EPO OPS blocked on credentials" (`:91`, the connector is done); 3 of 7 services in the table (`:17-21`); "5 connectors" (`:19`) and "Five public sources" (`:9`); quick start runs `run_pipeline.py` (`:37`) |
| `docker/README.md` | 21 KB | Services table, memory and disk budgets, commands, topics, Postgres, recreate, password changes, observability, environment, Ollama | **Stale bucket list:** backup mirrors "both MinIO buckets" (`:23`; three are mirrored, compose `:247`). "DLT … publishes to the same partition number" (`:107`, wrong: the resolver returns partition `-1`). Memory table, alert thresholds and topics table copy `.env.example`, alert YAML and `topics.yaml` values |
| `orchestration/README.md` | 2 KB | DAG notes | Cursor rule from before 2026-10-09 (`:3`, `:17`); "API keys are Airflow Connections" (`:37`); omits four DAGs |
| `services/ingestion-scraper/README.md` | 9 KB | Stages, scheduling, connectors, `sources.yaml` schema, commands, testing layout, scripts, API constraints | `epo_ops` "Blocked — needs EPO OPS credentials" (`:35`); `fda_approval` "Active" with no `sources.yaml` entry (`:34`); stage order differs from `pipeline.py:101-108`; "5 public biotech sources" |
| `services/core-hub/README.md` | 8.6 KB | Architecture, DLT, data model, corroboration formula, REST API, commands, build and testing layout, key constraints | "steps 2.8 and 6.4" plan references |
| `services/backtesting/README.md` | 32 KB | Universe, catalysts, filing score, prices, metrics, evaluation, portfolio, ownership, short interest, H9, scripts, commands | Holds the only prose of six code-done specs (now in `docs/research/`) |
| `services/strategy/README.md` | 9.4 KB | Runtime, traces, risk, MinIO state, metrics, HTTP | `config/strategies/versions/` absent |
| `services/backup/README.md` | 1.6 KB | Pieces table, key constraints, commands | Restore boundary stated here, not under INV-2 |
| `services/dashboard/README.md` | 2.8 KB | Backend routing, configuration, commands | — |
| `SETUP.md` | 9 KB | Ordered manual steps | **Stale bucket list:** `minio-init` creates "`auspex-raw`, `auspex-prices`" (`:16`); startup table omits `airflow-db-role` and `airflow-state-init`; schedule table omits `auspex_daily_health` |
| `docs/PREREQUISITES.md` | 8.8 KB | Owner-action queue | Dead `.env` knobs `BACKFILL_BUDGET_CEILING`, `BACKFILL_TIME_CEILING_HOURS` (`:22-23`, in neither `.env.example` nor code), "Steady-state LLM budget" (`:25`, no variable); protocol-owned rows `KNOWN_AT_DELAY_DAYS`, `HOLDOUT_MONTHS`, `PROMOTION_T_THRESHOLD`, `PROMOTION_DEFLATED_SHARPE_THRESHOLD` (`:62-65`; the values are in `config/hypotheses/protocol.yaml`); cost-knob rows copy `.env.example` defaults (`:66-77`); H8 short strategy (`:53`, deleted); "openFDA key" configured (`:82`); duplicates of SETUP steps (`:33-35`, `:43`) |
| `VERSIONS.md` | 9.2 KB | Pins | **Stale bucket list:** MinIO row names two buckets (`:18`) |
| `docs/strategy-research.md` | 22 KB | Hypothesis rationale H1–H12 | "These are invariants for all hypotheses" (`:11`, they are not); benchmark copied from `protocol.yaml` (`### Benchmark`, `:28-29`); roles, statuses and trial budgets copied from `config/hypotheses/` (`## Triage (2026-10-07)` and `### Slow signals (2026-10-09)`, `:209-237`) |
| `TODO.md` | 33 KB | Spec index and session log | Notes cells that still name finished specs as blockers: Historical backfill (extraction-backend, model-evaluation), Forward paper trading (strategy-runtime, cross-sectional-portfolio-backtest), Slow-signal data refresh (infrastructure-observability), Managed ingestion config, Ingestion config UI, Signal browse views, Pipeline control view (dashboard foundation, wiring fixes), Lineage trace view (wiring fixes) |

**Paths that do not move** (code, tests or citations pin them; all are in `docs-check.toml` `frozen_paths`): `SETUP.md` (compose `:?` messages at `docker/docker-compose.yml:250,284,656-658`, `services/dashboard/src/app/api/auth/login/route.ts:10`, `docker/prometheus/prometheus.yml:63`, two tests); `VERSIONS.md` (`test_stack_observability_config.py:148`); `README.md`, `CLAUDE.md`, `docker/README.md`, `docker/CLAUDE.md` (read by `test_docs_never_offer_down_v_as_a_fix`); `docs/backup-restore.md` (`services/backup/src/auspex_backup/restore.py:2`); `docs/strategy-research.md` (`services/backtesting/src/auspex_backtesting/market_sim/costs.py:13`, "Defaults match the cost estimates in docs/strategy-research.md"); `docs/requirements.md` (cited by about 53 archived specs and many DECISIONS entries); `specs/first-run-on-stack-machine.md` (read by `test_new_secrets_are_documented_in_setup`). Editing their content is allowed; moving them is not.

**The two doc-reading tests** (`services/ingestion-scraper/tests/unit/test_stack_persistence_config.py`):

```python
def test_docs_never_offer_down_v_as_a_fix() -> None:                       # :152
    for doc in ("README.md", "CLAUDE.md", "SETUP.md", "docker/README.md", "docker/CLAUDE.md"):
        for n, line in enumerate((REPO_ROOT / doc).read_text(encoding="utf-8").splitlines(), 1):
            if "down -v" in line:
                assert "destroys all data" in line, f"{doc}:{n} mentions down -v without warning"
```

After `agent-instruction-hierarchy`, `CLAUDE.md` and `docker/CLAUDE.md` are one line, `@AGENTS.md`, so the guard no longer covers the text that moved to `AGENTS.md`, `docker/AGENTS.md` and `docs/operations/*.md`. `test_new_secrets_are_documented_in_setup` (`:159`) needs `` `AIRFLOW_FERNET_KEY` ``, `` `AIRFLOW_JWT_SECRET` `` and `` `AIRFLOW_SECRET_KEY` `` in `SETUP.md`, backticked.

**ID references.** An ID is `INV-<n>` (CLAUDE numbering, no zero padding) or `<NS>-<NNN>` for the namespaces above. It is defined in a living doc (`docs/**/*.md`, except the non-normative files `docs/README.md`, `docs/requirements.md`, `docs/strategy-research.md`, `docs/local-model-runbook.md`, `docs/backup-restore.md`, `docs/PREREQUISITES.md`, `docs/HISTORY.md`, `docs/soak-test-report.md`) by a list item that starts `<a id="ID"></a>**ID**`; one under `## Retired requirements` is retired.

## What this builds

1. **`docs/requirements.md` becomes the non-normative § index.** The file holds exactly:
   - one banner paragraph: "Not authoritative. Superseded by `docs/` on <cutover date>. Kept so that citations in `specs/done/` and `DECISIONS.md` resolve. Owners are listed in [docs/README.md](README.md).";
   - one table `| § | Original heading or label | Now owned by | IDs |`, one row per key the extraction rule below yields from the original file (107 rows at e51f742): every `##` and `###` section, every §0 table row (`§0.1` … `§0.7`), every numbered item (`§3.1` … `§3.12`; elsewhere `§5 item 1`, `§7.1 item 3`, …), and every bold-led line or bullet (`§2 · Partitioning`, `§12 · Structured JSON logs`, …). The `§` cell is the key text exactly as the extraction prints it.
   - **IDs cell:** the IDs whose verification rows cite that § as `Source`, found with `grep -rn "requirements §" docs/` on the merged domain docs, cross-checked against the matrix rows (`specs/living-docs-cutover-matrix.md`) whose source is that §. A key that became no requirement says why, in one word plus a link: `stale` (with the defect, e.g. "stale: fixture path"), `history`, or `rationale` (link to the owner's `## Rationale`). §0 assumptions now facts point at their requirement IDs; assumptions still open point at their `pending-decision` heading or at `docs/PREREQUISITES.md`. §14 points at the Rationale sections that absorbed it.
   - **§3 rows** use the INV numbering of root `CLAUDE.md`: `§3.1` → INV-1, `§3.2` → INV-2, `§3.3` → INV-6 plus the OPS log-contract ID in `docs/operations/observability.md` (logging has one owner), `§3.4` → INV-7, `§3.5` → INV-8, `§3.6` → INV-9, `§3.7` → INV-10, `§3.10` → INV-11 plus its CON and HUB IDs, `§3.11` → INV-12, `§3.12` → INV-11; `§3.8` and `§3.9` → HUB IDs only. If the matrix rows assign differently, the matrix wins and this list is corrected in the PR.
   - The table is generated, not hand-typed: the author runs the extraction (the script in the Definition of done) on the baseline text, fills the last two columns from the greps above, and reviews each row. No other text remains (check H).
2. **Root `README.md`** becomes orientation plus links, and owns the stack-level commands:
   - one architecture paragraph without rules, linking `docs/system/overview.md`; "Five public sources" removed;
   - a services table with every directory under `services/` (seven services: ingestion-scraper, core-hub, price-service/backtesting, strategy-runtime, backup, dashboard; plus the Airflow DAGs' location), each linking its README; no connector count;
   - quick start: `cp .env.example .env` with a link to `SETUP.md`, the full-stack `up`, and the dashboard URL. The `run_pipeline.py` line is removed (it is a developer tool, listed in the scraper README's scripts table);
   - **Stack commands** (owner): bring up infra, bring up the full stack, tear down, tear down and wipe volumes (its line keeps "destroys all data"), restore one backup (link `docs/backup-restore.md`), the core-hub REST smoke check `./verify_pipeline.sh` (described as two REST checks, not pipeline proof), and the Grafana provisioning check `docker/grafana/test_provisioning.sh`. The strategy kill switch is not listed: its command is owned by `services/strategy/AGENTS.md`, and the stack commands section has one line linking it ("Stop all strategies: the kill switch in `services/strategy/AGENTS.md`");
   - service commands removed; one line: "Service commands: the `AGENTS.md` in each service directory";
   - project structure tree with every top-level directory and every service; `PROGRESS.md` removed; the `CLAUDE.md` line ("Claude Code operational context (auto-loaded)", `:81`) becomes "`AGENTS.md` agent instructions (`CLAUDE.md` imports it)";
   - "Current status" removed (status lives in `TODO.md`); "Key constraints" and "Hard boundary" replaced by one line linking `docs/system/invariants.md`; "Watched tickers" replaced by a link to `WATCHED_TICKERS` in `.env.example`;
   - a link to `docs/README.md` near the top.
3. **Service READMEs** (`services/{ingestion-scraper,core-hub,backtesting,strategy,backup,dashboard}/README.md`): each keeps a one-paragraph purpose, its layout or packages, and its tables of components (scripts, connectors, pieces, configuration names without values). Every behaviour section is replaced by a link to its owner doc (the matrix row for that section names it). The commands section becomes one line linking the service's `AGENTS.md`. Specific fixes:
   - ingestion-scraper: connectors table statuses fixed (`epo_ops` active; `fda_approval` "approved source, not configured yet" with a link to its ING requirement, which stays `divergent` until a config spec adds the `sources.yaml` entry); "5 public biotech sources" removed; the `sources.yaml` field table and API constraints become links to `docs/ingestion/connectors.md`; `run_pipeline.py` stays in the scripts table as a developer tool;
   - core-hub: "steps 2.8 and 6.4" removed with the corroboration section (link `docs/core-hub/corroboration.md`); build and testing layout kept as layout, the contract-test and Flyway rules as links to their IDs;
   - backtesting: every research section becomes one line plus a link into `docs/research/`; the scripts table stays;
   - strategy: sections become links into `docs/strategy/`; the kill-switch command leaves the README for `services/strategy/AGENTS.md` like every other command;
   - backup: the pieces table stays; "Key constraints" becomes links to `docs/operations/backup.md` and INV-2; the restore boundary is not restated;
   - dashboard: routing becomes a link to `docs/dashboard.md`; configuration names stay without values.
4. **`docker/README.md`** becomes the operator description of the stack: a service → purpose → profile table (no image tags, ports or schedules); one line per subject linking `docs/operations/topology.md`, `orchestration.md`, `observability.md`, `backup.md`; the topic-repair procedure (`:109`) and the password-change table (`:138-146`) kept as procedures; commands replaced by a link to the root README's stack commands. Removed: the memory and disk tables, the topics table, the DLT partition sentence, the alert table, the metric list, the environment list (owner `SETUP.md` step 1), the Ollama memory budget (owner `docs/local-model-runbook.md`), and "both MinIO buckets".
5. **`orchestration/README.md`** becomes a pointer: where the six DAG files live (`services/ingestion-scraper/dags/`, `services/backtesting/dags/`, `services/backup/dags/`), that their policy is `docs/operations/orchestration.md`, and that the cursor rule is `docs/ingestion/pipeline.md`. The three stale statements go.
6. **`SETUP.md`:** the `minio-init` row names the three buckets `auspex-raw`, `auspex-prices`, `auspex-strategy`; the startup table gains `airflow-db-role` and `airflow-state-init`; the schedule table gains `auspex_daily_health`. Nothing else changes; the three backticked Airflow secrets stay.
7. **`docs/PREREQUISITES.md`:** delete the `BACKFILL_BUDGET_CEILING`, `BACKFILL_TIME_CEILING_HOURS`, backfill-depth and steady-state LLM budget rows (dead knobs; `specs/historical-backfill.md` introduces the ceilings when it is built) and the sentences in the decision rows that tell the owner to set them in `.env`; delete the `KNOWN_AT_DELAY_DAYS`, `HOLDOUT_MONTHS`, `PROMOTION_T_THRESHOLD`, `PROMOTION_DEFLATED_SHARPE_THRESHOLD` rows (their values are owned by `config/hypotheses/protocol.yaml`); replace the cost-knob rows with one line naming the cost-model group in `.env.example` and linking `docs/research/simulation.md`; delete the control-surface and Linux rows that duplicate `SETUP.md`; drop "H8 (negative asymmetry)" from the borrow row; drop the resolved delisted-price row; drop "openFDA key" and the gate thresholds from "Already configured".
8. **`VERSIONS.md`:** the MinIO row's note drops its bucket list; tags and every other row unchanged.
9. **`docs/strategy-research.md`** stays rationale and keeps its path, its hypothesis reasoning (`## Hypotheses`, H1–H8) and its cost estimates (`### Capital and friction`, cited by `costs.py:13`). Changes:
   - one banner paragraph under the title: "Rationale, not authoritative. Registered hypotheses, their roles, statuses and trial budgets are in `config/hypotheses/` (`h*.yaml`, `protocol.yaml`); the rules that apply them are in `[docs/research/evaluation-protocol.md](research/evaluation-protocol.md)`.";
   - "These are invariants for all hypotheses" (`:11`) becomes "These were the working constraints when the hypotheses were written.";
   - `### Benchmark`: the two copied bullets become one line naming `abnormal_return.benchmark` in `config/hypotheses/protocol.yaml`;
   - `## Triage (2026-10-07)` and `### Slow signals (2026-10-09)`: the two role and status tables and the trial-budget sentence go; each section keeps its explanatory paragraph and gains one line naming the fields that hold the values (`role` and `status` in each `config/hypotheses/h*.yaml`; `families.<name>.budget_cells` in `protocol.yaml`).
   Nothing else in the file changes; the dated history sections (`### Data window and sample expectations`, `## What the 24-month backfill realistically allows`) stay as history.
10. **`TODO.md` Notes cells naming finished blockers.** In the eight rows listed in Context, delete each blocker whose spec is in `specs/done/` from the Notes cell, keeping the rest of the cell. The statuses, links and every other row are untouched. (The `Blocked by` headers of those specs are owned by the rollout spec that owns each spec; this spec edits only `TODO.md`.)
11. **The one test change in the rollout.** `test_docs_never_offer_down_v_as_a_fix` keeps its name and assertion and reads, in addition to its five files: `AGENTS.md`, `services/AGENTS.md`, `docker/AGENTS.md`, every `services/*/AGENTS.md`, and every `docs/operations/*.md`. It asserts the list is not vacuous: root `AGENTS.md` exists and at least four `docs/operations/*.md` files were read. Intended shape:

    ```python
    def test_docs_never_offer_down_v_as_a_fix() -> None:
        operations = sorted((REPO_ROOT / "docs" / "operations").glob("*.md"))
        agents = [REPO_ROOT / "AGENTS.md", REPO_ROOT / "services" / "AGENTS.md", REPO_ROOT / "docker" / "AGENTS.md",
                  *sorted((REPO_ROOT / "services").glob("*/AGENTS.md"))]
        assert len(operations) >= 4, "docs/operations/*.md not found; the guard would be vacuous"
        docs = [*(REPO_ROOT / d for d in ("README.md", "CLAUDE.md", "SETUP.md", "docker/README.md", "docker/CLAUDE.md")),
                *agents, *operations]
        for path in docs:
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "down -v" in line:
                    assert "destroys all data" in line, f"{path.relative_to(REPO_ROOT)}:{n} mentions down -v without warning"
    ```

    `read_text` raises on a missing `AGENTS.md`, so a deleted agent file fails the test rather than shrinking it. The glob is not `**/AGENTS.md`, which would walk `services/dashboard/node_modules`.
12. **Archive this spec in the same PR.** Set `**Status:** done`, move this file to `specs/done/legacy-docs-retirement.md`, and update this spec's own `TODO.md` row (status `done`, link to `specs/done/…`).

## Out of scope

- Writing or changing any requirement: that is the domain specs' work. If a README sentence has no owner in `docs/`, stop and append a FLAG to `DECISIONS.md`; do not move the sentence into `docs/` here.
- Agent files (`AGENTS.md`, every `CLAUDE.md`): `agent-instruction-hierarchy`.
- `docs/README.md`: owned in full by `living-docs-system-and-contracts`; not edited here.
- In `TODO.md`: every status, link and row other than the eight Notes cells in item 10 and this spec's own row. Archive banners, enforcement and the reconciliation pass are `living-docs-cutover`'s.
- The `Blocked by` headers of the specs behind the eight TODO rows.
- `docs/HISTORY.md`, `docs/local-model-runbook.md`, `docs/backup-restore.md`: not edited here. In `docs/strategy-research.md`, everything except item 9.
- `SETUP.md` step 6 (`scripts/run_backfill.py` and the `BACKFILL_*` ceilings, neither of which exists yet): it is gated on `specs/historical-backfill.md` and says so; left as is. `SETUP.md`'s human-readable DAG times stay (a runbook may copy them; noted).
- `VERSIONS.md` "See open question 4/6" (dangling since `docs/plan.md` was deleted) and its missing strategy and wiremock entries: not part of the stale bucket list; left for a later spec.
- Any other test, and any application code or configuration.

## Constraints

- **Invariants.** No behaviour changes. The test change only widens a doc guard; it reads files and asserts on text (INV-15 test-first applies: red before green, below).
- **What may be cut.** This spec writes no requirement. A sentence is deleted only when the matrix row for it says `link`, `delete`, `move`, `ratify`, `divergent` or `retire`, and for the last four the ID it names exists in `docs/`. Check M for every namespace is the gate.
- **Conflicts.** READMEs and agent files never win on a requirement. When a README sentence and its owner doc disagree, the README sentence is deleted and the disagreement recorded in the PR (and, if the README was right, as a DECISIONS FLAG for the owner domain). Never "fix" the owner doc in this spec.
- **Paths that do not move.** No file listed in Context moves or is renamed. `docs/requirements.md` keeps its path and every §-number it had (as index keys).
- **IDs.** Only references: bare IDs or anchored links, each resolving to a definition. No `NS-?` placeholder may remain. Decisions are cited by their full DECISIONS heading text; no decision register number is written.
- **`down -v`.** Every remaining mention in any file the guard reads carries "destroys all data" on the same line.
- **`SETUP.md`** keeps `` `AIRFLOW_FERNET_KEY` ``, `` `AIRFLOW_JWT_SECRET` ``, `` `AIRFLOW_SECRET_KEY` ``.
- **`costs.py:13`** keeps pointing at real text: `### Capital and friction` in `docs/strategy-research.md` is not edited.
- **Test discipline.** The extended test must be shown red for the right reason before it is green, in a disposable worktree: `git worktree add "${TMPDIR:-/tmp}/legacy-red" HEAD`, add a line `docker compose down -v` to `docs/operations/topology.md` there, run the extended test (it fails naming `docs/operations/topology.md:<n>`; the old five-file test would pass), then `git worktree remove --force "${TMPDIR:-/tmp}/legacy-red"`. Nothing is committed or pushed. Run with `--strict-markers` and check the count.

## Dependencies

- **Needs:** `living-docs-system-and-contracts`, `living-docs-ingestion`, `living-docs-core-hub`, `living-docs-research`, `living-docs-strategy-and-dashboard`, `living-docs-operations` and `living-docs-engineering-workflow` merged, because the index and the README links point at their IDs and files; `agent-instruction-hierarchy` merged, because the service READMEs link to the service `AGENTS.md` files and the guard reads them.
- **Needs from `docs-check-tooling`:** checks A, H and M, and `[rollout] base` in `docs-check.toml`.
- **Hands to `living-docs-cutover`:** old authority files with no second copy of any rule, so the final gate's check H passes and the reconciliation pass has only owner docs to port develop deltas into.

## Affected files

| Path | Action |
|---|---|
| `docs/requirements.md` | modify (replace body with banner + index) |
| `README.md` | modify |
| `docker/README.md` | modify |
| `orchestration/README.md` | modify |
| `services/ingestion-scraper/README.md` | modify |
| `services/core-hub/README.md` | modify |
| `services/backtesting/README.md` | modify |
| `services/strategy/README.md` | modify |
| `services/backup/README.md` | modify |
| `services/dashboard/README.md` | modify |
| `SETUP.md` | modify (three rows) |
| `docs/PREREQUISITES.md` | modify (rows removed) |
| `VERSIONS.md` | modify (MinIO row note) |
| `docs/strategy-research.md` | modify (banner, one sentence, benchmark and triage values replaced by links) |
| `TODO.md` | modify (this spec's row, and only the Notes cells of the eight rows in item 10) |
| `services/ingestion-scraper/tests/unit/test_stack_persistence_config.py` | modify (`test_docs_never_offer_down_v_as_a_fix` only) |
| `specs/legacy-docs-retirement.md` → `specs/done/legacy-docs-retirement.md` | move, Status `done` |
| `docs/**/*.md` owner files, `AGENTS.md` files | untouched but cited (link targets) |
| `specs/living-docs-cutover-matrix.md`, `docs-check.toml` | untouched but cited |
| `CLAUDE.md`, `docker/CLAUDE.md`, `docs/README.md`, `docs/HISTORY.md`, `docs/local-model-runbook.md`, `docs/backup-restore.md`, `specs/first-run-on-stack-machine.md` | untouched (frozen or owned elsewhere) |

## Required tests

Checker assertions (commands created by `docs-check-tooling`; output lines are `CHECK path:line message`). `OWN` is this spec's edited files: `README.md,docker/README.md,orchestration/README.md,services/*/README.md,SETUP.md,docs/PREREQUISITES.md,docs/requirements.md,docs/strategy-research.md`.
- `legacy_requirements_file_holds_only_banner_and_index`: `python3 -m tools.docs_check --only H --paths docs/requirements.md` prints nothing and exits 0. Fails if any text other than the banner paragraph and the one table remains.
- `links_resolve_in_retired_files`: `python3 -m tools.docs_check --only A --paths "$OWN"` prints nothing and exits 0. Fails on a broken relative link or `#fragment` in any of them, or a `frozen_paths` entry that no longer exists.
- `matrix_rows_for_every_domain_resolve`: `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain <NS>` exits 0 for each of `INV SYS CON ING EXT HUB COR RES EVA STR DSH OPS ENG`. Fails if any text was cut whose matrix row promised an ID that does not exist.

Spec-specific checks (the scripts in the Definition of done):
- `ids_cited_in_retired_files_resolve`: every ID token in the `OWN` files and `VERSIONS.md` has an active definition in a living doc; in `docs/requirements.md` a retired definition also counts. Fails on an ID that does not exist or, outside the index, a retired one. (This is done here, not by check D, because the checker does not read these files for IDs.)
- `requirements_index_covers_every_legacy_item`: the extraction rule run on `git show <[rollout] base>:docs/requirements.md` yields the key list; every key is exactly one row's `§` cell, and no row has a key the rule does not yield. Fails on a missing or invented row.
- `requirements_index_rows_each_resolve_to_an_owner`: the index has at least 100 rows, and every row's IDs cell holds at least one ID, or starts with `stale`, `history` or `rationale` and holds a link. Fails on an empty index, or an empty or free-text cell.
- `legacy_invariant_rows_map_to_claude_numbering`: the rows `§3.1`, `§3.2`, `§3.3`, `§3.4`, `§3.5`, `§3.6`, `§3.7`, `§3.10`, `§3.11`, `§3.12` contain `INV-1`, `INV-2`, `INV-6`, `INV-7`, `INV-8`, `INV-9`, `INV-10`, `INV-11`, `INV-12`, `INV-11` respectively. Fails on requirements-file numbering (`§3.3` → `INV-3`).
- `no_normative_sentence_left_in_readmes`: outside code fences, no line of `README.md`, `docker/README.md`, `orchestration/README.md` or `services/*/README.md` matches `(?i)\b(must|never|always|shall|required)\b` unless the same line holds a Markdown link or an ID. Fails on "`@Transactional` must always be qualified" left in the core-hub README.
- `service_readmes_link_agents_and_hold_no_commands`: each `services/*/README.md` links `AGENTS.md`, and no README (root included) holds a line matching `pytest|gradlew|npm (run|ci)|ruff|mypy|auspex_strategy kill`. Fails on a leftover commands block or a kill-switch command outside `services/strategy/AGENTS.md`.
- `root_readme_drops_stale_status_and_names_every_service`: `README.md` contains none of `PROGRESS.md`, `Phase 3 complete`, `blocked on credentials`, `run_pipeline.py`, `5 connectors`, `Five public sources`, links every directory in `services/` that has a README, and links `services/strategy/AGENTS.md`. Fails on any one.
- `stale_bucket_lists_fixed`: `SETUP.md` names `auspex-strategy` on the `minio-init` row; `docker/README.md` has no `both MinIO buckets`; the `VERSIONS.md` MinIO row has no `auspex-prices`. Fails on a stale bucket list left anywhere.
- `setup_lists_every_one_shot_and_dag`: every compose service whose block has `restart: "no"`, except `restore`, and every DAG id (`auspex_price_refresh`, `auspex_universe_build`, `auspex_backup`, `auspex_daily_health`, `auspex_<source>`) appears in `SETUP.md`. Fails if a one-shot or DAG is missing.
- `prerequisites_holds_no_dead_or_protocol_owned_knob`: `docs/PREREQUISITES.md` contains none of `BACKFILL_BUDGET_CEILING`, `BACKFILL_TIME_CEILING_HOURS`, `KNOWN_AT_DELAY_DAYS`, `HOLDOUT_MONTHS`, `PROMOTION_T_THRESHOLD`, `PROMOTION_DEFLATED_SHARPE_THRESHOLD`, `negative asymmetry`, `openFDA key`, and every backticked upper-case name in a row that says `.env` is a key in `.env.example`. Fails on a dead or protocol-owned knob.
- `strategy_research_links_instead_of_copying`: `docs/strategy-research.md` contains `Rationale, not authoritative` and `abnormal_return.benchmark`; contains none of `These are invariants for all hypotheses`, `Primary: XBI`, `Trial budgets are per corpus family`; has no table row starting `| H` followed by a number; and still contains the `### Capital and friction` and `### H1 — Structural convergence premium` headings. Fails if a copied value stays or the cited cost text goes.
- `todo_notes_name_no_finished_blocker`: in the `TODO.md` rows linking the eight specs of item 10, the Notes cell contains none of `extraction-backend`, `model-evaluation`, `strategy-runtime`, `cross-sectional-portfolio-backtest`, `infrastructure-observability`, `dashboard foundation`, `wiring fixes`; and every spec named in the check list really is in `specs/done/`. Fails on a stale blocker left in a note.
- `test_docs_never_offer_down_v_as_a_fix` (extended): `cd services/ingestion-scraper && uv run pytest tests/unit/test_stack_persistence_config.py -q -k down_v` reports `1 passed`. Red first as in Constraints. Fails if any guarded file mentions `down -v` without "destroys all data", if an `AGENTS.md` it lists is missing, or if fewer than four `docs/operations/*.md` files exist.
- `test_new_secrets_are_documented_in_setup` (unchanged): same file, `-k new_secrets`, `1 passed`. Fails if the `SETUP.md` edit dropped a backticked secret.
- `legacy_spec_archived`: `specs/done/legacy-docs-retirement.md` exists with `**Status:** done`, `specs/legacy-docs-retirement.md` does not, and `TODO.md` links `specs/done/legacy-docs-retirement.md`.

Mutation check, in a disposable worktree (`git worktree add "${TMPDIR:-/tmp}/legacy-mutants" HEAD`, run the Definition of done there, then `git worktree remove --force "${TMPDIR:-/tmp}/legacy-mutants"`; nothing is committed or pushed): delete one index row; change `§3.3`'s ID to `INV-3`; cite a non-existent ID in a service README; put "must" in a service README without a link; restore `PROGRESS.md` in the root README; revert the `SETUP.md` bucket row; add `HOLDOUT_MONTHS` back to `PREREQUISITES.md`; put `Primary: XBI` back into `docs/strategy-research.md`; put `strategy-runtime` back into the Forward paper trading note; plant `docker compose down -v` in `docs/operations/topology.md` and in `docker/AGENTS.md`. Each must turn its check red. List them in the PR.

## Definition of done

```bash
set -u
OWN='README.md,docker/README.md,orchestration/README.md,services/*/README.md,SETUP.md,docs/PREREQUISITES.md,docs/requirements.md,docs/strategy-research.md'
echo "== checker"
python3 -m tools.docs_check --only H --paths docs/requirements.md; echo "h-exit=$?"
python3 -m tools.docs_check --only A --paths "$OWN"; echo "a-exit=$?"
for ns in INV SYS CON ING EXT HUB COR RES EVA STR DSH OPS ENG; do python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain "$ns" >/dev/null || echo "FAIL $ns"; done; echo "matrix-done"
BASE=$(python3 -c 'import tomllib; print(tomllib.load(open("docs-check.toml", "rb"))["rollout"]["base"])')
LEGACY=$(mktemp)
git show "$BASE:docs/requirements.md" > "$LEGACY"
python3 - "$LEGACY" <<'EOF'
import pathlib, re, sys
def keys(text):
    out, sec, fence = [], None, False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence; continue
        if fence: continue
        m = re.match(r"^##\s+(\d+)\.", line) or re.match(r"^###\s+(\d+\.\d+)", line)
        if m:
            sec = "§" + m[1]; out.append(sec); continue
        if sec is None: continue
        m = re.match(r"^\|\s*(0\.\d)\s*\|", line)
        if m:
            out.append("§" + m[1]); continue
        m = re.match(r"^\s{0,4}(\d+)\.\s", line)
        if m:
            out.append(f"§3.{m[1]}" if sec == "§3" else f"{sec} item {m[1]}"); continue
        m = re.match(r"^\s*(?:\* )?\*\*([^*]+?)\*\*", line)
        if m:
            out.append(f"{sec} · {m[1].strip().rstrip(':.').strip()}")
    return list(dict.fromkeys(out))
fails = []
def check(name, bad):
    print(f"{name}: {'FAIL ' + '; '.join(map(str, bad[:5])) if bad else 'ok'}"); fails.extend(bad)
def read(p):
    p = pathlib.Path(p)
    return p.read_text(encoding="utf-8") if p.is_file() else ""
idre = re.compile(r"\b(INV-\d{1,2}|(?:SYS|CON|ING|EXT|HUB|COR|RES|EVA|STR|DSH|OPS|ENG)-\d{3})\b")
nonnorm = {"docs/README.md", "docs/requirements.md", "docs/strategy-research.md", "docs/local-model-runbook.md", "docs/backup-restore.md", "docs/PREREQUISITES.md", "docs/HISTORY.md", "docs/soak-test-report.md"}
active, retired = set(), set()
for p in pathlib.Path("docs").rglob("*.md"):
    if p.as_posix() in nonnorm: continue
    t = p.read_text(encoding="utf-8")
    live, _, gone = t.partition("\n## Retired requirements")
    active |= set(re.findall(r'<a id="([A-Z]{3}-\d+)"></a>\*\*\1\*\*', live))
    retired |= set(re.findall(r"\*\*([A-Z]{3}-\d+)\*\*", gone))
readmes = [pathlib.Path(p) for p in ("README.md", "docker/README.md", "orchestration/README.md")] + sorted(pathlib.Path("services").glob("*/README.md"))
own = readmes + [pathlib.Path(p) for p in ("SETUP.md", "docs/PREREQUISITES.md", "docs/requirements.md", "docs/strategy-research.md", "VERSIONS.md")]
check("ids_cited_in_retired_files_resolve", ["no IDs defined in docs/"] if not active else [
    f"{p}:{n} {m[0]}" for p in own for n, l in enumerate(read(p).splitlines(), 1) for m in idre.finditer(l)
    if m[0] not in active and not (p.as_posix() == "docs/requirements.md" and m[0] in retired)])
want = keys(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
rows = {}
for l in read("docs/requirements.md").splitlines():
    if l.startswith("| §"):
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        rows[c[0]] = c
check("requirements_index_covers_every_legacy_item", [k for k in want if k not in rows] + [k for k in rows if k not in want])
check("requirements_index_rows_each_resolve_to_an_owner", [f"only {len(rows)} rows"] if len(rows) < 100 else [k for k, c in rows.items() if len(c) < 4 or not (idre.search(c[3]) or (re.match(r"(stale|history|rationale)\b", c[3]) and "](" in c[3]))])
inv = {"§3.1": "INV-1", "§3.2": "INV-2", "§3.3": "INV-6", "§3.4": "INV-7", "§3.5": "INV-8", "§3.6": "INV-9", "§3.7": "INV-10", "§3.10": "INV-11", "§3.11": "INV-12", "§3.12": "INV-11"}
check("legacy_invariant_rows_map_to_claude_numbering", [k for k, v in inv.items() if k not in rows or len(rows[k]) < 4 or not re.search(re.escape(v) + r"\b", rows[k][3])])
def prose(p):
    fence = False
    for n, l in enumerate(read(p).splitlines(), 1):
        if l.startswith("```"): fence = not fence; continue
        if not fence: yield n, l
check("no_normative_sentence_left_in_readmes", [f"{p}:{n}" for p in readmes for n, l in prose(p)
    if re.search(r"(?i)\b(must|never|always|shall|required)\b", l) and "](" not in l and not idre.search(l)])
svc = sorted(pathlib.Path("services").glob("*/README.md"))
check("service_readmes_link_agents_and_hold_no_commands", [f"{p} no AGENTS link" for p in svc if "AGENTS.md" not in read(p)] +
    [f"{p}:{n}" for p in readmes for n, l in enumerate(read(p).splitlines(), 1) if re.search(r"pytest|gradlew|npm (run|ci)|ruff|mypy|auspex_strategy kill", l)])
root = read("README.md")
check("root_readme_drops_stale_status_and_names_every_service", [s for s in ("PROGRESS.md", "Phase 3 complete", "blocked on credentials", "run_pipeline.py", "5 connectors", "Five public sources") if s in root] +
    [str(p.parent) for p in svc if f"{p.parent}/" not in root and str(p) not in root] + ([] if "services/strategy/AGENTS.md" in root else ["no kill-switch link"]))
setup = read("SETUP.md")
ver = [l for l in read("VERSIONS.md").splitlines() if l.startswith("| MinIO")]
check("stale_bucket_lists_fixed", ([] if any("minio-init" in l and "auspex-strategy" in l for l in setup.splitlines()) else ["SETUP minio-init row"]) +
    (["docker/README both buckets"] if "both MinIO buckets" in read("docker/README.md") else []) +
    (["VERSIONS MinIO row"] if any("auspex-prices" in l for l in ver) else []))
compose = read("docker/docker-compose.yml")
blocks = re.split(r"(?m)^  (?=[a-z][a-z0-9-]*:\s*$)", compose.split("\nvolumes:")[0])
oneshots = [b.split(":")[0] for b in blocks if 'restart: "no"' in b and not b.startswith("restore:")]
dags = ["auspex_price_refresh", "auspex_universe_build", "auspex_backup", "auspex_daily_health", "auspex_<source"]
check("setup_lists_every_one_shot_and_dag", ["no one-shots parsed"] if not oneshots else [x for x in oneshots + dags if x not in setup])
pre = read("docs/PREREQUISITES.md")
envkeys = set(re.findall(r"(?m)^([A-Z][A-Z0-9_]*)=", read(".env.example")))
dead = ["BACKFILL_BUDGET_CEILING", "BACKFILL_TIME_CEILING_HOURS", "KNOWN_AT_DELAY_DAYS", "HOLDOUT_MONTHS", "PROMOTION_T_THRESHOLD", "PROMOTION_DEFLATED_SHARPE_THRESHOLD", "negative asymmetry", "openFDA key"]
check("prerequisites_holds_no_dead_or_protocol_owned_knob", [d for d in dead if d in pre] +
    [k for l in pre.splitlines() if "`.env`" in l for k in re.findall(r"`([A-Z][A-Z0-9_]{2,})`", l) if k not in envkeys])
sr = read("docs/strategy-research.md")
check("strategy_research_links_instead_of_copying", [s for s in ("Rationale, not authoritative", "abnormal_return.benchmark", "### Capital and friction", "### H1 — Structural convergence premium") if s not in sr] +
    [s for s in ("These are invariants for all hypotheses", "Primary: XBI", "Trial budgets are per corpus family") if s in sr] +
    [l[:30] for l in sr.splitlines() if re.match(r"^\|\s*H\d+\b", l)])
gone = {"extraction-backend": "extraction-backend", "model-evaluation": "model-evaluation", "strategy-runtime": "strategy-runtime",
        "cross-sectional-portfolio-backtest": "cross-sectional-portfolio-backtest", "infrastructure-observability": "infrastructure-observability",
        "dashboard foundation": "dashboard-foundation", "wiring fixes": "graph-and-connector-wiring-fixes"}
eight = ["historical-backfill", "forward-paper-trading", "slow-signal-data-refresh", "managed-ingestion-config", "ingestion-config-ui", "signal-browse-views", "pipeline-control-view", "lineage-trace-view"]
todo = {m[1]: m[2] for m in re.finditer(r"(?m)^\| \[[^\]]+\]\(specs/([a-z0-9-]+)\.md\) \| `\w+` \| (.*) \|$", read("TODO.md"))}
check("todo_notes_name_no_finished_blocker", [f"{s} row missing" for s in eight if s not in todo] +
    [f"{s}: {p}" for s in eight for p in gone if p in todo.get(s, "")] +
    [f"{d} not done" for d in gone.values() if not pathlib.Path(f"specs/done/{d}.md").is_file()])
sys.exit(1 if fails else 0)
EOF
echo "exit=$?"
echo "== doc-reading tests"
(cd services/ingestion-scraper && uv run pytest tests/unit/test_stack_persistence_config.py -q -k "down_v or new_secrets")
echo "== legacy_spec_archived"
test ! -e specs/legacy-docs-retirement.md && grep -q '^\*\*Status:\*\* done' specs/done/legacy-docs-retirement.md && grep -q 'specs/done/legacy-docs-retirement.md' TODO.md && echo archived
```

Expected output: `h-exit=0` and `a-exit=0` with nothing printed before either; `matrix-done` with no `FAIL` line; thirteen lines `<name>: ok`; `exit=0`; `2 passed, … deselected`; `archived`.

The PR into `feature/living-docs-integration` shows the red output of the extended test (from the disposable worktree), lists the mutations checked, and gives, per trimmed file, its size before and after.

## Compatibility

- **Citations.** About 53 archived specs and many DECISIONS entries cite "requirements §N". Every such § is a row key in the index and points at its owner, so the citation resolves in one hop. Archived specs are not edited (`## 2026-10-15 — Living docs — PENDING — archive policy for specs/done`).
- **Links.** Inbound links to `README.md`, `docker/README.md`, `SETUP.md`, `docs/strategy-research.md` and the service READMEs keep working (no path changes). Anchors into the old READMEs' headings may disappear; check A finds any inside the checked scope, and `specs/done/` is out of scope by design.
- **Readers.** A human opening a README still finds what the component is, its layout, its scripts and where its rules are. Commands are one link away (service `AGENTS.md`) or in the root README (stack).
- **Agents.** Claude Code and Codex already load `AGENTS.md` (created by `agent-instruction-hierarchy`); nothing they load changes here. Codex at the root reads root `AGENTS.md`, which names `README.md` for stack commands.
- **Tests.** The guard covers more files; the secrets test reads the same lines. CI runs both in the scraper job unchanged.
- **Code pins.** Every path named by compose messages, the dashboard login route, `prometheus.yml`, `restore.py` and `costs.py` still exists with the content those messages point to (SETUP steps, the runbook, the cost estimates).

## Rollback

On the integration branch, before `living-docs-cutover`, in one PR into `feature/living-docs-integration`, merged on the owner's word:
1. `git revert --no-commit <integration tip before this spec merged>..<integration tip after it merged>` (the range includes this spec's first commit).
2. `git checkout HEAD -- DECISIONS.md`, so any FLAG appended while doing this spec stays.
3. Append `## <date> — Living docs — FLAG — legacy docs retirement rolled back`, recording the range reverted.
4. Commit once.

The old text returns intact, the extended test returns to its five files, the index returns to the full requirements text, and the eight TODO notes get their old blockers back. Nothing else depends on this spec except `living-docs-cutover`, whose final gate (check H) then fails until it is re-applied. After cutover, rollback is the cutover spec's range revert.

## Notes

- **Why this spec also waits for `agent-instruction-hierarchy`.** Service READMEs link to service `AGENTS.md`, and the extended guard reads them. Running the two in parallel would force the guard's `AGENTS.md` paths into the other spec's PR and split the rollout's one test change across two specs, so this spec runs after it.
- **"AGENTS.md" in the guard means every `AGENTS.md` that `agent-instruction-hierarchy` creates,** not only the root one. `docker/AGENTS.md` is the most likely home of a `down -v` command line.
- **`docs/backup-restore.md:22`** names `down -v` as a cause of data loss without the words "destroys all data". It is not in the guard's list and stays out; adding `docs/*.md` to the guard would need that line reworded first.
- **Kill switch.** It runs from `services/strategy` and acts on the running stack's MinIO. Its command has one owner, `services/strategy/AGENTS.md` (service commands live in the service's agent file); the root README's stack commands link it rather than repeat it.
- **`SETUP.md` keeps human-readable DAG times.** They copy values from DAG files and `sources.yaml`. A runbook is not checked for copied values; a later spec may replace them with links.
- **`docs/strategy-research.md` keeps its history sections.** The 24-month window, the eight watched companies and the "what the backfill allows" section are dated history, not copied values, and stay as written.
- **As built.**
  - **Branch.** Built on `feature/living-docs-legacy-retirement`, cut from `feature/living-docs-agent-instructions` (which carries every domain doc and the agent files), because the integration branch had not received those parts yet.
  - **Index header.** The table's first header cell is `Legacy §`, not `§`: the Definition of done reads every line starting `| §` as an index row, so a `| § |` header would count as a key the extraction rule never yields.
  - **Banner date.** The banner says "Superseded by `docs/` at the living-docs cutover" instead of a date: the cutover has not happened, and `living-docs-cutover` does not set the date in this file.
  - **§0.1.** The assumption stays open with the live-trading spec (`## 2026-10-17 — Living docs — CHOICE — historical-instrument amendment out of scope`); its IDs cell names EVA-028 (no real capital before a forward check passes), the rule that holds today.
  - **Disposable copies.** The red run and the mutation check ran in a `tar` copy of the working tree in the session's scratch directory, not in a separate worktree, because the session's version control was confined to its own worktree. Nothing in the copy was committed.
  - **Commands left the READMEs** as item 3 says, overriding the matrix `keep` rows M-RES-072/073 (backtesting), M-STR-001 (strategy) and M-DSH-011 (dashboard), which predate the service `AGENTS.md` files. Three command lines have no copy in an agent file: the strategy image build (the README keeps the build context as a sentence), the dashboard dev server and its password-hash script (the README layout names `.env.local.example` and `scripts/hash-password.mjs`; `SETUP.md` step 1 keeps the hash command).
  - **TODO notes.** Managed ingestion config, Signal browse views and Pipeline control view named only finished blockers, so their notes now start with the spec's content; their status and `Blocked by` headers are untouched (out of scope).
- **Size.** Expect `docs/requirements.md` to shrink from 39 KB to about 10 KB, `services/backtesting/README.md` from 32 KB to about 3 KB, `docker/README.md` from 21 KB to about 4 KB.
