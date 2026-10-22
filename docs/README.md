# Auspex documentation

The index of `docs/`: which file owns which subject, the requirement ID namespaces, the machine-readable authorities, and the legends used in every verification table. Non-normative: this file defines no requirement.

## Layers

| Layer | Where | What it is |
|---|---|---|
| Approved current behaviour | the living docs listed under [Tree](#tree) | The requirements the system meets today, each with an ID, a source and a verification status |
| Proposed changes | `specs/*.md` and `specs/hold/*.md` | A change spec governs only its own work until it merges; it cites the IDs it adds, changes or retires |
| Archive | `specs/done/`, [HISTORY.md](HISTORY.md), `DECISIONS.md` entries classified as history | What was decided and built, and why. Read for rationale; never the source of a current rule |

## Tree

Living docs, one owner per subject:

- [README.md](README.md) — this index.
- [system/overview.md](system/overview.md) — SYS: component map, naming table, single-user premise, no legacy system, glossary.
- [system/invariants.md](system/invariants.md) — INV: the fifteen invariants, with their scope, amendments and the only text of each approved exception.
- [system/contracts.md](system/contracts.md) — CON: everything that crosses a process boundary on Kafka.
- [ingestion/connectors.md](ingestion/connectors.md) — ING: the connector contract, source configuration, per-source timestamps and rates.
- [ingestion/pipeline.md](ingestion/pipeline.md) — ING: stage order, archive, deduplication and precedence, run result, cursor rule, scraper HTTP API.
- [ingestion/extraction.md](ingestion/extraction.md) — EXT: extraction contract, model registry and gate, prompt version, re-extraction.
- [core-hub/consumption.md](core-hub/consumption.md) — HUB: listeners, deserialization, validation, dead-lettering, pause and replay.
- [core-hub/storage.md](core-hub/storage.md) — HUB: Postgres and Neo4j semantics, write order, idempotency, raw audit.
- [core-hub/corroboration.md](core-hub/corroboration.md) — COR: `CorroborationService`, the scan, scoring.
- [core-hub/http-api.md](core-hub/http-api.md) — HUB: endpoints, watchlist, write token, health reporting.
- [research/market-data.md](research/market-data.md) — RES: prices, splits, FX, reference snapshots.
- [research/universe.md](research/universe.md) — RES: point-in-time universes and their rules files.
- [research/panels.md](research/panels.md) — RES: ownership, short interest, catalysts, filing text, holdings score.
- [research/simulation.md](research/simulation.md) — RES: calendar, fills, costs, sizing, currency.
- [research/backtesting.md](research/backtesting.md) — RES: event and portfolio backtests, look-ahead rules.
- [research/evaluation-protocol.md](research/evaluation-protocol.md) — EVA: pre-registration, trial ledger, kill criteria, holdout, forward check.
- [strategy/contract.md](strategy/contract.md) — STR: the strategy interface, as-of context, registry, versioning.
- [strategy/runtime.md](strategy/runtime.md) — STR: replay and streaming runtime, virtual books, input health, metrics.
- [strategy/risk.md](strategy/risk.md) — STR: sizing, limits, check order, kill switch.
- [strategy/decision-trace.md](strategy/decision-trace.md) — STR: trace records and replay.
- [dashboard.md](dashboard.md) — DSH: the server layer, login and pages.
- [operations/topology.md](operations/topology.md) — OPS: compose services, profiles, limits, volumes, startup one-shots.
- [operations/orchestration.md](operations/orchestration.md) — OPS: Airflow DAGs, schedules, pools, retries, cursor storage.
- [operations/observability.md](operations/observability.md) — OPS: logs, metrics, alerts, health summary.
- [operations/backup.md](operations/backup.md) — OPS: what is backed up and kept.
- [engineering/change-workflow.md](engineering/change-workflow.md) — ENG: change lifecycle, docs impact, provenance, conflict policy, branching.
- [engineering/conventions.md](engineering/conventions.md) — ENG: naming, comments, per-stack conventions.
- [engineering/verification.md](engineering/verification.md) — ENG: test strategy, test-first loop, merge bar, CI.

Non-normative files in `docs/` (roles below): [requirements.md](requirements.md), [strategy-research.md](strategy-research.md), [local-model-runbook.md](local-model-runbook.md), [backup-restore.md](backup-restore.md), [PREREQUISITES.md](PREREQUISITES.md), [HISTORY.md](HISTORY.md).

## ID namespaces

A requirement ID is `INV-N` for an invariant (root agent-instruction numbering) and `NS-NNN` for every other namespace, numbered in file order. The namespace names the domain where the requirement was created; a requirement keeps its ID when it moves to another file. Adding a namespace changes `docs-check.toml` and this file in one PR.

| Namespace | Domain | Owner files | ID form |
|---|---|---|---|
| INV | Invariants | [system/invariants.md](system/invariants.md) | `INV-N` |
| SYS | System | [system/overview.md](system/overview.md) | `SYS-NNN` |
| CON | Cross-service contracts | [system/contracts.md](system/contracts.md) | `CON-NNN` |
| ING | Ingestion | [ingestion/connectors.md](ingestion/connectors.md), [ingestion/pipeline.md](ingestion/pipeline.md) | `ING-NNN` |
| EXT | Extraction | [ingestion/extraction.md](ingestion/extraction.md) | `EXT-NNN` |
| HUB | core-hub | [core-hub/consumption.md](core-hub/consumption.md), [core-hub/storage.md](core-hub/storage.md), [core-hub/http-api.md](core-hub/http-api.md) | `HUB-NNN` |
| COR | Corroboration | [core-hub/corroboration.md](core-hub/corroboration.md) | `COR-NNN` |
| RES | Research data and backtests | [research/market-data.md](research/market-data.md), [research/universe.md](research/universe.md), [research/panels.md](research/panels.md), [research/simulation.md](research/simulation.md), [research/backtesting.md](research/backtesting.md) | `RES-NNN` |
| EVA | Evaluation protocol | [research/evaluation-protocol.md](research/evaluation-protocol.md) | `EVA-NNN` |
| STR | Strategy | [strategy/contract.md](strategy/contract.md), [strategy/runtime.md](strategy/runtime.md), [strategy/risk.md](strategy/risk.md), [strategy/decision-trace.md](strategy/decision-trace.md) | `STR-NNN` |
| DSH | Dashboard | [dashboard.md](dashboard.md) | `DSH-NNN` |
| OPS | Operations | [operations/topology.md](operations/topology.md), [operations/orchestration.md](operations/orchestration.md), [operations/observability.md](operations/observability.md), [operations/backup.md](operations/backup.md) | `OPS-NNN` |
| ENG | Engineering workflow | [engineering/change-workflow.md](engineering/change-workflow.md), [engineering/conventions.md](engineering/conventions.md), [engineering/verification.md](engineering/verification.md) | `ENG-NNN` |

## Machine-readable authorities

These files own their values. A living doc names the file, says what it governs and states only what the file cannot express; it never copies the file's values.

| Authority | Governs | Lock | Explained in |
|---|---|---|---|
| `config/hypotheses/` (`protocol.yaml`, `h*.yaml`) and `config/hypotheses/registry.jsonl` | Pre-registered hypotheses, the evaluation protocol, the registration record | Each file's hash in the append-only `registry.jsonl`; the loader refuses an unregistered or edited file | [research/evaluation-protocol.md](research/evaluation-protocol.md) |
| `config/universe/` (`rules.yaml`, `us_small_mid.yaml`) | Universe rules, one file per universe | Version-locked on first build | [research/universe.md](research/universe.md) |
| `config/models/registry.yaml`, `config/models/local_candidates.yaml`, gate records in `config/models/scores/` | Extraction models, digests, context length, gate results | Digest compared at startup; no extraction without a passing gate record | [ingestion/extraction.md](ingestion/extraction.md) |
| `config/strategies/registry.yaml`, `config/themes.yaml` | Strategy registry, themes | — | [strategy/contract.md](strategy/contract.md), [strategy/risk.md](strategy/risk.md) |
| `config/short_interest/finra_calendar.csv` | FINRA publication calendar | — | [research/panels.md](research/panels.md) |
| `services/ingestion-scraper/config/sources.yaml` | Source entries, rates, lookback, thresholds | — | [ingestion/connectors.md](ingestion/connectors.md) |
| `docker/topics.yaml` | Topic names, partition counts, retention | Read by the `kafka-init` one-shot | [system/contracts.md](system/contracts.md) |
| `services/core-hub/src/test/resources/contract/` (`signal_event_v1.json`, `raw_pointer_v1.json`) | Wire shape of the signal event and the raw pointer | Generated by pytest; CI fails on a difference | [system/contracts.md](system/contracts.md) |
| `services/core-hub/src/main/resources/db/migration/` | Postgres schema | Flyway checksums; an applied script is frozen | [core-hub/storage.md](core-hub/storage.md) |
| `docker/docker-compose.yml`, `.env.example` | Services, profiles, limits, environment variable names | Stack configuration tests | [operations/topology.md](operations/topology.md) |
| `docker/grafana/provisioning/alerting/`, `docker/prometheus/prometheus.yml`, `docker/elasticsearch/ilm_policy.json`, `docker/statsd-exporter/mapping.yml` | Alert rules, scrape targets, log retention, metric mapping | promtool and stack configuration tests | [operations/observability.md](operations/observability.md) |
| `VERSIONS.md` and the lock files (`uv.lock` per Python service, `services/core-hub/gradle/libs.versions.toml`, `services/dashboard/package-lock.json`) | Pinned versions | The lock files | [engineering/conventions.md](engineering/conventions.md) (the rules, not the values) |
| `.github/workflows/`, `.github/scripts/check_commit_identity.sh` | CI gates, commit identity | — | [engineering/verification.md](engineering/verification.md) |

## Precedence

When `docs/`, code and other files disagree, the conflict policy in [engineering/change-workflow.md](engineering/change-workflow.md) decides. An exception to an invariant lives only under that invariant in [system/invariants.md](system/invariants.md).

## Verification status

Every living doc ends its requirements with a verification table (`ID | Source | Verified by | Status`). The status is one of:

| Status | Meaning | Allowed at cutover |
|---|---|---|
| `tested` | A named test (`path::name`) asserts the requirement as written | yes |
| `enforced` | A machine check (CI step, ArchUnit rule, loader refusal), named in the row, enforces it | yes |
| `untested` | Approved and believed implemented; no test asserts it as written. Tests covering part of it are named in the row | yes; listed in the cutover report |
| `divergent` | Approved, and the code is known not to comply. The row cites the `DECISIONS.md` heading that records the gap | yes, when it cites one |
| `pending-decision` | The owner has not yet approved the requirement. The row cites the `DECISIONS.md` `PENDING` heading that asks | only for requirements the final gate does not list as blocking |

## Evidence labels

Used in reviews, audits and `DECISIONS.md` `VERIFIED` entries to say what a claim rests on:

| Label | Meaning |
|---|---|
| `APPROVED-INTENT` | The owner approved it (a `docs/` requirement or a `CHOICE` entry); says nothing about the code |
| `OBSERVED-IMPL` | Read in the code at a stated commit; not run |
| `TEST-ASSERTION` | A named test asserts it; the test's passing is shown by CI or a recorded run |
| `EXECUTED` | Run and observed, with the command and its output recorded |
| `HISTORICAL` | True when an archived spec or history entry was written; not rechecked |
| `PROPOSED` | Stated by an open spec or a `PENDING` entry; not approved |
| `UNVERIFIED` | Claimed with none of the above behind it |
| `VERIFIED-DOCS` | Read in vendor documentation on a stated date; not execution |
| `VERIFIED-SOURCE` | Read in vendor source at a stated tag; not execution |

## Non-normative and legacy files

| File | Role |
|---|---|
| [requirements.md](requirements.md) | Legacy index: maps each section of the former requirements document to the IDs and owner files that absorbed it, so citations in archived specs and `DECISIONS.md` resolve. Non-normative |
| [strategy-research.md](strategy-research.md) | Research rationale behind the hypotheses. Non-normative |
| [local-model-runbook.md](local-model-runbook.md) | Runbook: install, register and gate a local extraction model |
| [backup-restore.md](backup-restore.md) | Runbook: restore a nightly backup into empty stores |
| [PREREQUISITES.md](PREREQUISITES.md) | Queue of user actions (credentials, decisions) |
| [HISTORY.md](HISTORY.md) | Archive of completed phases |
