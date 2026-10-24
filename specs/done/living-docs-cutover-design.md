# Living docs cutover: design

> Archived. Not authoritative: current behaviour is in docs/ (see docs/README.md).

> Companion to `specs/living-docs-cutover.md`, archived with it. It is the design the eleven rollout specs implement. It is not a spec (checks E and J skip it) and not an authority: once the rollout lands, `docs/engineering/` owns the rules described here, and this file is history.

Written against: `develop` @ `e51f74201fda30dd9a28af318cc74b824e39dafc` (2026-10-15). Decision references name `DECISIONS.md` headings dated 2026-10-15 and prefixed `Living docs — PENDING — `, given here by their suffix in quotes.

---

## 1. The three layers

| Layer | Path | What it is | Authority |
|---|---|---|---|
| Living specs | `docs/` | Approved current behaviour, one owner file per subject, every requirement with a stable ID | **Normative.** The only prose authority for what the system must do |
| Change specs | `specs/*.md`, `specs/hold/*.md` | Proposed changes not yet merged, with tests and a definition of done | Normative only for the work it describes, and only until it merges. It never overrides `docs/` for current behaviour |
| Archive | `specs/done/*.md`, `docs/HISTORY.md`, `DECISIONS.md` entries classified as history at cutover (§9.1(5)) | What was decided and built, and why | **Not authoritative.** Read for rationale. Never cite as the source of a current rule |

Two further classes sit beside the layers:

* **Machine-readable authorities** (§4) own values. Docs describe their meaning and link to them, but never copy their values.
* **Agent instructions** (`AGENTS.md`, `CLAUDE.md`) own agent workflow only (§7). They hold no requirement text.

A requirement is "approved" when it is in `docs/` on `develop`. That does not make it "implemented". Every requirement carries a verification status (§5.4), and docs are never evidence that the code complies (§9.1).

---

## 2. Target `docs/` tree

Where investigations proposed different names for one subject, one name was chosen. `system/` and `engineering/` are kept so the three cross-cutting owners sit together. There is one file per subject a change typically touches, and no file per class.

```
docs/
├── README.md                       index: domain → owner file, ID namespaces, authority map, status and label legend
├── system/
│   ├── overview.md                 SYS: component map, data flow, naming table, no-legacy statement, glossary
│   ├── invariants.md               INV-1 … INV-15 (root CLAUDE.md numbering), each with scope, amendments and the
│   │                               only text of its approved exceptions (restore, CT.gov lookup, read-only scraper access)
│   └── contracts.md                CON: topics (semantics), raw/signal/corroborated events, identity, natural keys per path,
│                                   versioning, closed sets, DLT naming/partition/headers, fixture rule
├── ingestion/
│   ├── connectors.md               ING: SourceConnector contract, sources.yaml semantics, per-source timestamps,
│   │                               verified APIs, rate limits, source traps (SEC, EPO, openFDA, CT.gov, bioRxiv)
│   ├── pipeline.md                 ING: stage order, archive-first, dedup/precedence, pre-filter, publish threshold,
│   │                               run result, cursor rule, HTTP API (/ingest/<source_type>)
│   └── extraction.md               EXT: extraction contract, not-a-signal, untrusted input, model registry + digest,
│                                   gate, prompt version, re-extraction
├── core-hub/
│   ├── consumption.md              HUB: listeners, deserialisation, validation, DLT, pause/back-off, replay, ack mode
│   ├── storage.md                  HUB: Postgres schema semantics, Neo4j model, write order, idempotency, edge replacement,
│   │                               raw audit, single-user schema (no user_id)
│   ├── corroboration.md            COR: CorroborationService, pending flag + write token, scan, scoring formula, corroboration kinds
│   └── http-api.md                 HUB: endpoints, watchlist, write token + no CORS (owner), health reporter
├── research/
│   ├── market-data.md              RES: prices, settled bars, splits, FX, snapshots in auspex-prices
│   ├── universe.md                 RES: point-in-time universe(s), rules files, version lock, survivorship
│   ├── panels.md                   RES: ownership, short interest, catalysts, filing text, holdings score;
│   │                               publication and as-of rules
│   ├── simulation.md               RES: calendar, fills, cost model, sizing, currency
│   ├── backtesting.md              RES: event backtest, portfolio backtest, look-ahead rules
│   └── evaluation-protocol.md      EVA: pre-registration, research config read-only, trial ledger, kill criteria, holdout,
│                                   forward check, deflated Sharpe, entity-only vs full variant reporting (owner)
├── strategy/
│   ├── contract.md                 STR: Strategy ABC, AsOfContext, registry, versioning, intents
│   ├── runtime.md                  STR: replay/streaming runtime, virtual book, input health, latency, strategy metrics and API
│   ├── risk.md                     STR: sizing, limits, check order, kill switch
│   └── decision-trace.md           STR: trace records, deterministic ids, replay
├── dashboard.md                    DSH: BFF, single-user login, pages (write token and CORS: links to http-api.md)
├── operations/
│   ├── topology.md                 OPS: compose services, profiles, limits, volumes, persistence, startup one-shots
│   ├── orchestration.md            OPS: Airflow DAGs, schedules, pools, retries, cursors storage, Fernet
│   ├── observability.md            OPS: logs, metrics, alert intent, health summary
│   └── backup.md                   OPS: what is backed up, retention (restore exception: links to INV-2)
├── engineering/
│   ├── verification.md             ENG: test strategy, TDD loop, merge bar, mutation check, CI vs cloud vs Mac
│   ├── change-workflow.md          ENG: lifecycle, docs impact, conversion provenance, handoff format, conflict policy,
│   │                               branching and merge recipe
│   └── conventions.md              ENG: naming, comments, per-stack conventions, doc ownership rules
│
├── requirements.md                 legacy: becomes a non-normative § → ID index (owner decision decision "fate of docs/requirements.md")
├── strategy-research.md            rationale (unchanged path; labelled non-normative in docs/README.md)
├── local-model-runbook.md          runbook (unchanged path)
├── backup-restore.md               runbook (unchanged path)
├── PREREQUISITES.md                user-action queue (unchanged; not behaviour)
└── HISTORY.md                      archive (unchanged)
```

**Why these boundaries.**
* `system/contracts.md` is the single owner of everything that crosses a process boundary on Kafka. B, C and E each proposed a contracts file; they are merged here. The Python model, the Java record and the generated fixture remain the machine authority for field lists (INV-7).
* Core-hub is split by the four reasons it changes (consume, store, corroborate, serve). Corroboration has its own namespace because it is the most specified area and has its own extension point (INV-5).
* Research is split by data dependency, not by service. The six "code done, blocked on the Mac" specs (point-in-time universe, SEC ownership, short interest, catalyst panel, filing text, holdings score) land in `universe.md` and `panels.md`. Their merged behaviour is approved and implemented, so it belongs in `docs/` (§8.4).
* Operations owns Airflow because the DAGs are thin HTTP callers (INV-3). What each DAG asks for belongs to the service it calls; the DAG's schedule, pool, retries and timeout belong to `operations/orchestration.md`. The ingestion cursor rule is pipeline behaviour (`ingestion/pipeline.md`). Where the cursor is stored, Airflow Variables under Fernet, is operations.
* Runbooks, rationale and the user-action queue keep their paths. Inbound citations from `specs/done/` and `DECISIONS.md` cannot be edited, so moving these files would only add redirects. They are labelled by role in `docs/README.md`.
* No `docs/architecture/` folder: `system/` holds the three cross-cutting owners and nothing else.
* Seams settled:
  * Extraction quality tooling (`model_evaluation.py`, `sampling.py`, `evaluate_model.py`, `check_leakage.py`, `compare_models.py`, `sample_corroborations.py`) is owned by `ingestion/extraction.md`. That covers the ≥ 0.85 gates (model and corroboration review), the leakage canary and the decision rule fixed in advance. `sample_corroborations.py` reads Postgres and Neo4j from the scraper package. That is a read, so INV-1 (writes only) holds, and `invariants.md` states the read-only scope explicitly.
  * Build and runtime glue (6 Dockerfiles, 3 `gunicorn.conf.py`, compose one-shots, ES setup) belongs to `operations/topology.md`. The single-process gunicorn rule stays a requirement there.
  * `operations/observability.md` owns the one catalogue of metric names and alert intent that dashboards and alert rules depend on. Domains link to it.
  * The combined SEC request budget across containers (EDGAR connector plus universe and panel builds) is owned by `operations/topology.md`, with per-connector rates in `ingestion/connectors.md`.
  * The DAG side of the cursor (save, then fail; Variables under Fernet) is owned by `operations/orchestration.md`. The cursor rule itself is owned by `ingestion/pipeline.md`.
  * DAGs live in `services/*/dags/`. There is no `airflow/` directory.
* **Paths pinned by code or tests stay where they are and are listed in `frozen_paths`:**
  * `SETUP.md`: compose `:?` messages, the dashboard login route, `prometheus.yml`;
  * `VERSIONS.md`: read by a test;
  * `docs/backup-restore.md`: `restore.py` docstring;
  * `docs/strategy-research.md`: `costs.py`;
  * the three hypothesis-cited specs and `specs/point-in-time-universe.md` (§4);
  * files read by tests: `README.md`, `CLAUDE.md`, `docker/README.md`, `docker/CLAUDE.md` (`test_docs_never_offer_down_v_as_a_fix`) and `specs/first-run-on-stack-machine.md` (`test_new_secrets_are_documented_in_setup`). `legacy-docs-retirement` extends the `down -v` test's file list to `AGENTS.md` and `docs/operations/*.md`, so the guard keeps covering moved text.

  The rollout creates no redirect stubs because it moves none of them.

**What stays outside `docs/`.**

| File | Role after cutover |
|---|---|
| `README.md` | Orientation for humans: what Auspex is, quick start, **stack-level commands (owner: compose up/down, smoke, restore)**, a link to `docs/README.md`. No requirements |
| service `README.md` | How to work in that service: layout, scripts table, connectors table. Commands are a link to the service `AGENTS.md`, their owner. Behaviour sentences are replaced by links to their `docs/` owner |
| `docker/README.md` | Operator-facing description of the stack. Requirements move to `operations/*` |
| `orchestration/README.md` | Pointer to `operations/orchestration.md` and where DAG files live |
| `SETUP.md` | Manual steps in order (unchanged role) |
| `VERSIONS.md` | Machine-readable authority for pins (§4) |
| `DECISIONS.md` | Append-only decision log. Records why and who decided. A binding `CHOICE` is absorbed into a `docs/` ID (§9.1) |
| `TODO.md` | Spec index and session log (unchanged role). Notes carry status only, never rules. It is no longer auto-loaded |

---

## 3. Responsibilities of each document kind

| Kind | Must contain | Must not contain |
|---|---|---|
| Living spec (`docs/**`) | Scope, ID'd requirements, the machine authorities it relies on, a verification table, traps, retired requirements | Plan steps, change narration, values owned by a machine authority, "will"/"should eventually" (future work belongs in a change spec), unconfirmed claims |
| Change spec (`specs/*.md`) | Existing required fields plus a **Docs impact** field listing the requirement IDs it adds, changes or retires | Restated requirements from `docs/`. It cites IDs instead |
| Archive (`specs/done`) | Whatever it said when it was archived, plus an optional archive banner added once at cutover (decision "archive policy for specs/done") | Edits after archiving. Corrections go to `docs/` or `DECISIONS.md` |
| README | Orientation, layout, commands, tables of components | Requirements. Any "must" sentence links to its owner |
| Runbook | Ordered operator steps for one procedure, with checks | Requirements. It links to the owner for the "why" |
| Agent instructions | Workflow, hard process rules, routing to owners, local commands and traps (pointers) | Requirement text, copies of invariants, copies of commands owned elsewhere |
| `DECISIONS.md` | Dated entries: flag, block, choice, with reasons | The current rule as its only home. An entry that changes behaviour is paired in the same PR with the `docs/` edit (§9.1(5)) |

---

## 4. Machine-readable authorities

These own their values. A living doc names the file, says what it governs and states only the semantics the file cannot express. **A doc that restates a value from one of these files is a defect.** Checker B flags a backticked path that does not exist, and the semantic review (§10.2) catches copied values.

| Authority | Governs | Lock | Doc that explains it |
|---|---|---|---|
| `config/hypotheses/protocol.yaml`, `h1…h12.yaml` | Pre-registered hypotheses, thresholds, families, kill criteria | Hash in `registry.jsonl`; loader refuses an unregistered or edited file | `research/evaluation-protocol.md` |
| `config/hypotheses/registry.jsonl` | Registration record | Append-only | same |
| `config/universe/rules.yaml`, `us_small_mid.yaml` | Universe rules per universe | Version-locked in MinIO on first build (`RulesVersionError`) | `research/universe.md` |
| `config/models/registry.yaml`, `local_candidates.yaml` | Extraction models, digests, `num_ctx`, gate records | Digest compared at startup | `ingestion/extraction.md` |
| `config/strategies/registry.yaml`, `config/themes.yaml` | Strategy registry, themes | — | `strategy/contract.md`, `strategy/risk.md` |
| `config/short_interest/finra_calendar.csv` | FINRA publication calendar | — | `research/panels.md` |
| `services/ingestion-scraper/…/sources.yaml` | Source entries, rates, lookback, thresholds | — | `ingestion/connectors.md` |
| `docker/topics.yaml` | Topics, partitions, retention | Read by `kafka-init` | `system/contracts.md` |
| `services/core-hub/src/test/resources/contract/signal_event_v1.json` | Signal event wire shape | **Generated** by pytest; CI diff check | `system/contracts.md` |
| Flyway `V*__*.sql` | Postgres schema | Checksums; frozen once applied | `core-hub/storage.md` |
| `docker/docker-compose.yml`, `.env.example` | Services, profiles, limits, env names | Compose tests | `operations/topology.md` |
| `docker/grafana/provisioning/alerting/*.yaml`, `docker/prometheus/prometheus.yml`, `docker/elasticsearch/ilm_policy.json`, `docker/statsd-exporter/mapping.yml` | Alert rules, scrape, retention, metric mapping | promtool and stack-config tests | `operations/observability.md` |
| `VERSIONS.md`, `uv.lock`, `gradle/libs.versions.toml`, `package-lock.json` | Pins | Lock files | `engineering/conventions.md` (rules), not values |
| `.github/workflows/*.yml`, `.github/scripts/check_commit_identity.sh` | CI gates | — | `engineering/verification.md` |

**Paths cited by locked files.**

* **What the locked files cite.**
  * `h9.yaml`, `h11.yaml` and `h12.yaml` (hash-locked) cite `specs/sec-ownership-datasets.md#SpecialistClassifier`, `specs/clinicaltrials-version-diffs.md` and `specs/catalyst-date-panel.md`.
  * `config/universe/rules.yaml:1` cites `specs/point-in-time-universe.md` in a comment. That file is byte-hashed when the first build locks it.
* **No moves.** The rollout moves or renames none of these files. All four are `frozen_paths`, and check A fails if one disappears.
* **SpecialistClassifier (decision "spec paths cited by hash-locked hypotheses").** Its definition moves to `docs/research/panels.md` as a RES ID, like every other merged behaviour (decision "code-done specs blocked on the Mac"). The `SpecialistClassifier` item (a list item at `specs/sec-ownership-datasets.md:29`, not a heading, so the h9 fragment resolves to nothing today) is replaced by one line carrying an explicit `<a id="SpecialistClassifier"></a>` anchor: "Defined in RES-0xx (`docs/research/panels.md#RES-0xx`). This heading is cited by the registered H9 hypothesis; do not rename it."
  * The locked hypothesis therefore reaches its rule through one documented hop.
  * The YAML, the registry and the test asserting the h9 string are untouched.
* **When one of these specs is archived,** its file stays at its path until the owner either re-registers the citing hypothesis (allowed only while the family has no trials) or accepts a one-line stub. That is a decision for the spec that completes it, not for this rollout.

---

## 5. Living-spec template and requirement IDs

### 5.1 Template

```markdown
# <Subject>

Domain: <NS> · Code: `<path>`, `<path>` · Last reviewed against: develop @ `<sha>`

## Scope
What this file owns, and the neighbouring owners for what it does not own (links).

## Requirements
- <a id="NS-001"></a>**NS-001** — One testable statement, in the present tense. Constraints and reasons follow in the same item.
- <a id="NS-002"></a>**NS-002** — … Applies INV-13.

## Machine-readable authorities
| File | Governs | Notes |

## Verification
| ID | Source | Verified by | Status |
|---|---|---|---|
| NS-001 | requirements §6.2 | `services/x/tests/unit/test_y.py::test_name` | tested |
| NS-002 | DECISIONS `## 2026-10-07 — … — CHOICE — …` | — | untested |

## Known traps
- Trap, why it bites, and which requirement it protects.

## Rationale
Links to `DECISIONS.md` entries and archived specs. Non-normative.

## Retired requirements
- **NS-0xx** — retired YYYY-MM-DD by <spec or DECISIONS heading>; replaced by <ID | none>. Original text: "…"
```

* **Required H2s** (check E): `Scope`, `Requirements`, `Verification`, `Retired requirements`. A section may be empty, but it must exist. The rest are optional.
* **`Last reviewed against`** names a commit **on `develop`**, because feature-branch SHAs do not survive the rebase-and-fast-forward flow. It records where someone last read the file against the code; it is not a proof. Check E verifies that the SHA is an ancestor of HEAD.
* **`Source`** is the provenance of the requirement's approval (§8.5).
* **`Verified by`** is `path::name`. For rows marked `tested`, check K looks for `def name` or `void name(` inside that file.

### 5.2 ID scheme

* **Format.** `NS-NNN`: a fixed namespace and three digits, numbered sequentially within the namespace.
* **Invariant numbering.** `INV-1 … INV-15` take the numbering of today's root `CLAUDE.md`, because active specs cite "Invariant N" in that numbering.
  * `docs/requirements.md` §3 numbers them differently. Its item 3 is CLAUDE's 6, item 4 is CLAUDE's 7, and item 6 is CLAUDE's 9.
  * The legacy index (§6) has one row per `§3.N` → `INV-M`.
  * Check D aliases only "Invariant N", "Invariants N and M" and "invariant #N", all in CLAUDE numbering.
* **INV is the only namespace amended in place.**
  * An amended invariant keeps its number and gets a line `Amended YYYY-MM-DD by <DECISIONS heading>: previous text "…"`.
  * Its approved exceptions are listed under it, and nowhere else (§9.3).
  * A new invariant takes the next free INV number.
  * Every other namespace follows the retirement rule below.
* **Namespaces** are fixed in `docs-check.toml`: `INV`, `SYS`, `CON`, `ING`, `EXT`, `HUB`, `COR`, `RES`, `EVA`, `STR`, `DSH`, `OPS`, `ENG`.
  * A namespace names the domain where the requirement was created. A requirement keeps its ID when it moves to another file.
  * Adding a namespace changes `docs-check.toml` and `docs/README.md` in one PR.
* **Definition.** The list item that starts with `<a id="NS-NNN"></a>**NS-NNN**`.
  * The anchor makes `docs/x.md#NS-NNN` linkable on GitHub.
  * Each ID is defined exactly once across `docs/`, active or retired (check C).
* **References.** A bare `NS-NNN` in docs, specs, agent files and PR bodies, or the anchored link.
  * Every reference from `docs/`, an active spec or an agent file must resolve to a definition (check D).
  * An active spec citing a retired ID exits 1.
* **Allocation.** `python -m tools.docs_check --next NS` prints the highest ever-used number in the namespace (active or retired) plus one. There is no separate ledger: the retired section is the ledger.
  * Two open PRs can allocate the same number in different files of one namespace without a textual conflict. So the local merge recipe runs `python -m tools.docs_check --base origin/develop` after the rebase and before the fast-forward.
  * `docs.yml` also runs on push to `develop` as a backstop.
  * On a collision, the later PR renumbers its new IDs, including in its spec and PR body.
* **No reuse.** An ID defined at the merge base must still be defined at HEAD, active or retired (check C2). Deleting a retired entry fails.
* **Retirement** (every namespace except INV).
  * Move the item to `## Retired requirements` with the date, the spec or DECISIONS heading that retired it, the replacement ID or `none`, and the original text.
  * Rewording that keeps the meaning keeps the ID. A change of meaning retires the old ID and adds a new one.
* **Initial allocation** is done by the domain specs in §11, each in disjoint namespaces.
  * The migration matrix (C) maps every requirement to a namespace and a target file, but assigns no numbers. Numbers are assigned in file order when each domain spec writes its file.
  * `living-docs-system-and-contracts` owns INV, SYS and CON, and merges into the integration branch before the others cite CON numbers.
  * Until then, the other specs write CON placeholders (the namespace followed by a question mark), which check D rejects at the final gate.

### 5.3 Example 1 — cross-service: `docs/system/contracts.md` (excerpt)

> **Illustrative only.** This shows the format. The requirement text and the test names in the verification rows are not verified. The domain spec writes the final wording and cites real tests as `path::name`.

```markdown
# Cross-service contracts

Domain: CON · Code: `services/ingestion-scraper/src/auspex_ingest/models.py`,
`services/core-hub/src/main/java/dev/auspex/corehub/signal/`, `…/audit/RawAuditService.java` · Last reviewed against: develop @ e51f742

## Scope
Everything that crosses a process boundary on Kafka: topic semantics, event shapes, identity, versioning,
dead-letter naming and headers. Topic names, partitions and retention are values in `docker/topics.yaml`.
Write behaviour after consumption: [core-hub/storage.md](../core-hub/storage.md).

## Requirements
- <a id="CON-001"></a>**CON-001** — Every message on `auspex.raw.ingested` is a raw-document pointer: the `RawDocument`
  fields in snake_case plus `raw_object_key`, keyed by `external_id`, with a `schema_version` header.
  The producer is `KafkaPublisher.publish_raw`; the consumer is `RawAuditService`. Both read the same field names.
- <a id="CON-002"></a>**CON-002** — A raw pointer is published for every archived document, whether or not it yields a signal
  (pending: DECISIONS `## 2026-10-15 — Living docs — PENDING — raw-pointer contract`).
- <a id="CON-003"></a>**CON-003** — `event_id` is document identity and never varies with schema version, prompt, model,
  or which source saw the document (INV-14).
- <a id="CON-004"></a>**CON-004** — The Python `ResearchSignalEvent` and the Java record are field-for-field identical, in snake_case on
  the wire. `signal_event_v1.json` is generated by pytest, and CI fails if it differs from the committed file (INV-7).
- <a id="CON-005"></a>**CON-005** — A record that cannot be processed goes to `<topic>.dlt` (lowercase), on a partition the producer
  chooses (-1), with the exception headers. It never blocks its partition (INV-11).

## Machine-readable authorities
| File | Governs |
|---|---|
| `docker/topics.yaml` | Topic names, partitions, retention, DLT topics |
| `services/core-hub/src/test/resources/contract/signal_event_v1.json` | Signal event shape (generated) |

## Verification
| ID | Source | Verified by | Status |
|---|---|---|---|
| CON-001 | requirements §2; DECISIONS `## 2026-10-15 — Living docs — PENDING — raw-pointer contract` | `RawAuditIT` uses a hand-written payload with `ingested_at`, but the producer sends `retrieved_at` | **divergent** (DECISIONS `… raw-pointer contract`) |
| CON-002 | requirements §2, §3.7 | — | **divergent**: `pipeline.py:159` publishes only for published signals |
| CON-003 | INV-14; requirements §10.1 | `<path>::<test>` | tested |
| CON-004 | INV-7 | `services/ingestion-scraper/tests/unit/test_contract_fixture.py::<test>`; `python.yml` diff step | tested, enforced |
| CON-005 | requirements §2; DECISIONS 2026-08-16 | `<path>::<test>` | tested |

## Known traps
- `DeadLetterPublishingRecoverer` defaults to `.DLT` and the same partition. The custom resolver must return
  partition -1 (CON-005).

## Retired requirements
(none)
```

The excerpt shows the cross-service pattern. One owner states the contract, both services' code is listed under Code, the divergence is visible in the verification table instead of being hidden in prose, and the machine authority holds the values.

### 5.4 Example 2 — one domain: `docs/ingestion/pipeline.md` (excerpt)

> **Illustrative only,** as in 5.3.

```markdown
# Ingestion pipeline

Domain: ING · Code: `services/ingestion-scraper/src/auspex_ingest/pipeline.py`, `…/api.py` · Last reviewed against: develop @ e51f742

## Scope
What happens to a document between a connector yielding it and Kafka acknowledging it, and the HTTP API
that starts a run. The connector contract: [connectors.md](connectors.md). Extraction: [extraction.md](extraction.md).
Event shapes: [../system/contracts.md](../system/contracts.md).

## Requirements
- <a id="ING-001"></a>**ING-001** — Stages run in this order: archive to MinIO, dedup, pre-filter, extract, publish.
  The archive write is unconditional and happens before any other side effect (INV-13).
- <a id="ING-002"></a>**ING-002** — A run never advances the cursor past a document that failed. The task saves the cursor
  and then fails.
- <a id="ING-003"></a>**ING-003** — At most 150 documents are extracted per run …

## Verification
| ID | Source | Verified by | Status |
|---|---|---|---|
| ING-001 | INV-13; requirements §6.2 (order corrected, see Rationale) | `services/ingestion-scraper/tests/unit/test_ingestion_pipeline.py::<test>` | tested |
| ING-002 | archived spec `specs/done/ingestion-run-reliability.md` | `<path>::<test>` | tested |

## Rationale
Today's requirements §6.2 lists pre-filter → dedup → archive. The code and INV-13 put the archive first;
`docs/requirements.md` was stale. ING-001 states the approved order.
```

### 5.5 Verification status values

| Status | Meaning | Allowed at cutover? |
|---|---|---|
| `tested` | A named test asserts it. Check K confirms the `path::name` exists; CI proves it passes | yes |
| `enforced` | A machine check enforces it (CI step, ArchUnit, loader refusal), named in the row | yes |
| `untested` | Approved and believed implemented; no test asserts it | yes, listed in the cutover report |
| `divergent` | Approved, and the code is known not to comply. Must cite a `DECISIONS.md` heading (check D resolves it) | yes, if it cites one |
| `pending-decision` | The owner has not decided what is approved. Must cite a `DECISIONS.md` `PENDING` heading | only for requirements the final gate does not list as blocking (§12) |

**Decision references are always `DECISIONS.md` headings, never an ID from outside the repo.** Each open question is a `## 2026-10-15 — Living docs — PENDING — <title>` entry; register numbers from the scoping work never appear in the repo (check D rejects them). The owner's answer is then appended as a `CHOICE` entry, and docs cite that. Check D verifies that every cited heading exists in `DECISIONS.md`.

---

## 6. Fate of `docs/requirements.md`

**Default (decision "fate of docs/requirements.md"): reduce it to a non-normative index.**
* It opens with one banner paragraph: "Not authoritative. Superseded by `docs/` on <date>. Kept so that citations in `specs/done/` and `DECISIONS.md` resolve."
* It then has one table with one row per original § and sub-item, including each `§3.N` → `INV-M` row, giving the IDs and owner files that absorbed it.
* There is no other text. Check H allows only the banner paragraph and the table.
* This is the only legacy § map; `docs/README.md` links to it.

**Why not delete it.** About 53 archived specs and many DECISIONS entries cite "requirements §N". Those files are frozen, so a deleted target leaves dangling history. The index is one explicit redirect, not a second copy, and it has no content that could drift.

**Why not keep it as the owner.** At 39 KB it mixes system, services, research and process. It is stale in at least four places (findings #1–#4), and it cannot carry per-domain verification tables.

**Two sections are split up:**
* **§0 Assumptions.** Assumptions that are now facts become requirements in their domain. Assumptions still open become `pending-decision` entries or `docs/PREREQUISITES.md` items.
* **§14 Settled.** It becomes the `Rationale` sections of the affected owners plus the conflict policy (§9).

---

## 7. Agent instruction hierarchy (Claude Code and Codex)

### 7.1 Loading facts the design relies on

Two evidence labels describe external behaviour:
* `VERIFIED-DOCS`: read in vendor documentation on the stated date.
* `VERIFIED-SOURCE`: read in vendor source at the stated tag.

Neither is execution.

| Fact | Source | Label |
|---|---|---|
| Claude Code loads ancestor `CLAUDE.md` files at launch and nested ones on demand. `@path` imports expand, up to 4 hops | Claude Code memory docs, fetched 2026-10-15 | VERIFIED-DOCS |
| Claude Code reads `AGENTS.md` natively only from v2.1.277, and only when no `CLAUDE.md`/`CLAUDE.local.md` exists | same | VERIFIED-DOCS. The design does not depend on it: if both load, the result is a harmless double read of ≤ 6 KB |
| Codex reads `AGENTS.md` (or `AGENTS.override.md`) from the git root down to cwd. It reads nothing deeper than cwd and truncates silently at a 32 KiB combined default | Codex source `rust-v0.159.2` | VERIFIED-SOURCE |
| Codex does not expand `@` imports | same | VERIFIED-SOURCE |
| Neither CLI was executed | — | UNVERIFIED. `agent-instruction-hierarchy` has a manual load check on the Mac for both CLIs, launched at the repo root and in a service directory |

### 7.2 Option chosen: A (decision "agent instruction files")

**Structure.**
* `AGENTS.md` is canonical at every level.
* Each `CLAUDE.md` is `@AGENTS.md` as its first line. It is at most 512 B and contains no must/never/always.
* `AGENTS.md` contains **no `@` imports**; it names files as plain paths.

**Rejected options.**
* B (`AGENTS.md` only) breaks silently when anyone adds a `CLAUDE.local.md`.
* C needs per-user Codex config and still breaks imports.
* D (symlinks) breaks Windows checkouts and Claude's Edit tool.

**Codex at the repo root.** A Codex session started at the root never loads nested files. So:
* Root `AGENTS.md` carries the routing rule: before editing under a directory that has an `AGENTS.md`, open it.
* Nothing a change must obey lives only in a nested file.

**Budgets** (check L, a `wc -c` sum per launch chain):

| File or chain | Limit | Why |
|---|---|---|
| Root `AGENTS.md` | ≤ 6 KB | |
| Each nested `AGENTS.md` | ≤ 3 KB | |
| Root → deepest launch chain | ≤ 16 KB | Half of Codex's 32 KiB, which leaves room for user-level files |

**Auto-load drops.** `@TODO.md` and `@VERSIONS.md` stop auto-loading. Today about 68.8 KB loads per Claude session. Afterwards about 4–6 KB loads, plus `TODO.md` when the agent opens it.

**Ownership of rules that agents must always see.**

| Rule set | Owner | Others |
|---|---|---|
| **Agent-session hard rules**: the zero-tests and `UP-TO-DATE` rules (test-first itself is INV-15; `AGENTS.md` cites it), never push `develop`/`main`, merge only on the owner's word, identity and no trailers or footers, commit-subject style, where work can run, stop-and-flag | **Root `AGENTS.md`**. These are workflow rules for an agent, not system requirements, so they get no ENG ID | `docs/engineering/*` links to them and does not restate them |
| **Engineering process detail**: TDD loop steps, merge bar, mutation check, branching and merge recipe, conversion provenance, conflict policy, doc ownership, comments, naming | **`docs/engineering/*`** (ENG IDs) | Root `AGENTS.md` names the files |
| **Service commands** | **Service `AGENTS.md`** (Codex cannot follow links, so the commands must be in the loaded file) | Service README links to it |
| **Stack-level commands** (compose up/down, smoke, restore) | **Root `README.md`** | Root `AGENTS.md` names it |

**Where today's root `CLAUDE.md` goes.**

| Section | Destination |
|---|---|
| Naming table | `docs/system/overview.md` (SYS). Topic and bucket names link to `docker/topics.yaml`, compose and `.env.example`, not restated |
| No legacy system | `docs/system/overview.md` |
| Invariants 1–15 | `docs/system/invariants.md` (INV-1…15, CLAUDE numbering). `AGENTS.md` keeps the stop-and-flag rule and one link |
| Rule that matters most | Root `AGENTS.md`, verbatim and short |
| Commands | Split as in the table above |
| TDD loop, ready to merge, mutation check | `docs/engineering/verification.md` |
| Documentation maintenance | **Replaced** by `docs/engineering/conventions.md` → "Doc ownership": one owner per fact, link don't copy. |
| Code comments | `docs/engineering/conventions.md`. The per-stack form stays in `services/AGENTS.md` |
| Git, merge, identity | Hard rules in root `AGENTS.md`. Recipe and merge bar in `docs/engineering/change-workflow.md` |
| Where work can run | Root `AGENTS.md` (owner). `docs/engineering/verification.md` links to it for what CI proves vs what the Mac proves |
| Known traps | Each trap moves to its owner doc's `Known traps`. Service `AGENTS.md` files list one-line pointers |
| `CorroborationServiceContractTest` rule, Flyway frozen rule | COR and HUB requirements. The nested file keeps only the IDs |
| File map, tone | Root `AGENTS.md` |

### 7.3 Example: root `AGENTS.md` (illustrative, about 4.5 KB)

```markdown
# Auspex — agent instructions

Canonical for every coding agent. Claude Code reads it through `CLAUDE.md`; Codex reads it directly.
Nothing is imported into this file (Codex does not expand imports): open the paths named below when you need them.
Before editing under a directory that has its own `AGENTS.md`, open that file: it lists that directory's commands and the owner docs.

## Authority
- `docs/` is approved current behaviour, one owner per requirement, IDs like `ING-004`. `docs/README.md` maps domains to owners.
- `specs/` holds proposed changes; a spec governs only its own work and only until it merges. `specs/done/` is history, never authority.
- Values live in machine-readable files (`docker/topics.yaml`, `config/hypotheses/*`, `sources.yaml`, Flyway, `VERSIONS.md` …). Docs explain them; do not copy values.
- On conflict follow `docs/engineering/change-workflow.md` (conflict policy). Never edit a doc to match the code without the owner's decision.
- A brief, note or memory from outside the repo must name the develop commit it was written against. If HEAD has moved, re-read what it cites before acting.

## Session start
1. Your work is the spec you were assigned. With none, open `TODO.md` and take the first `ready` spec. With none ready, scope a `draft` (`specs/README.md`).
2. Read the spec in full, then every `docs/` file its **Docs impact** names.
3. Before writing a test, check it against those requirements. If a test can only pass by breaking one, stop, append to `DECISIONS.md`, and ask. Do not write it.
4. If a task seems to need an invariant broken (`docs/system/invariants.md`), stop and flag the same way.
5. Work only that spec.

## Hard rules
- Test-first (INV-15). A run that executes zero tests is a failure. Gradle `UP-TO-DATE` is not a pass: prove a red or a fix with `--rerun-tasks`.
- A behaviour change updates its owning doc in the same PR. Otherwise the PR body says `Docs unchanged: <domain> — <reason>`. CI checks it.
- Never push to `develop` or `main`. Open a PR; merge only when the owner says so, with the recipe in `docs/engineering/change-workflow.md`.
- Commits carry the requesting person's git identity. No Claude author or committer, no `Co-Authored-By` or `Claude-Session` trailers, no generated-by footers on GitHub. CI rejects them.
- Commit message: one lowercase subject line, `subject: detail1, detail2`. No plan-step names anywhere.
- Cloud sessions have no Docker, sec.gov or Yahoo. Container tests are proven in CI; say so in the PR. Mac-only work goes in a spec the owner runs there. No hand-run setup scripts.
- Do not report work complete unless its tests ran and passed.

## Where things are
| Need | Open |
|---|---|
| Work queue | `TODO.md` |
| Spec format | `specs/README.md` |
| Requirements | `docs/README.md` → domain owners |
| Process detail (TDD, merge bar, mutation check, merge recipe) | `docs/engineering/` |
| Pinned versions | `VERSIONS.md` (only when touching a dependency) |
| Decisions and flags | `DECISIONS.md` (read before flagging; append when you flag) |
| Stack commands | `README.md`; service commands: the service's `AGENTS.md` |
| Manual setup | `SETUP.md` |
```

### 7.4 Example: `CLAUDE.md` (root and every nested directory)

```markdown
@AGENTS.md
```

### 7.5 Example: nested `services/core-hub/AGENTS.md` (illustrative, about 1.3 KB)

```markdown
# core-hub

Owners for changes here: `docs/core-hub/{consumption,storage,corroboration,http-api}.md`; anything on Kafka also
`docs/system/contracts.md`. Read the ones your spec's Docs impact names.

## Commands
`./gradlew test` (unit) · `./gradlew integrationTest` (containers; CI in cloud sessions) · `./gradlew check` ·
`./gradlew test --tests '*X'` · `./gradlew timezoneCheck` · add `--rerun-tasks` to prove a run.

## Layout
Unit tests `src/test/java/**/*Test.java` (no Spring context) · container tests `src/integrationTest/java/**/*IT.java` ·
versions in `gradle/libs.versions.toml`.

## Requirements that bite here (text in the owner doc)
COR-0xx contract test is extended unmodified · HUB-0xx Flyway files frozen once applied · HUB-0xx ErrorHandlingDeserializer ·
CON-005 `.dlt` + partition -1 · CON-0xx BigDecimal `confidence_score` · HUB-0xx FAIL_ON_UNKNOWN_PROPERTIES=false ·
HUB-0xx MERGE Company on normalised name.
```

**Nested-file rules.**
1. A nested file holds only what is local to its directory: commands, layout, and IDs with a few words each.
2. It never restates a parent rule.
3. It contains no requirement text, only IDs and a few words of label.
4. Nothing a change must obey lives only in a nested file.

**Nested `AGENTS.md` + `CLAUDE.md` pairs** exist for:
* `services/`
* `services/core-hub/`
* `services/ingestion-scraper/`
* `services/backtesting/`
* `services/strategy/`
* `services/backup/`
* `services/dashboard/`
* `docker/`

### 7.6 Example: cross-domain handoff

**Scenario.** A later spec fixes the raw pointer (CON-001/002). It touches `ingestion-scraper` (producer), `core-hub` (consumer) and `system/contracts.md`.

* **Discovery.**
  * The spec's **Docs impact** lists CON-001, CON-002 and HUB-0xx (raw audit write). The agent opens all three owners before writing tests.
  * Claude started anywhere loads the root and opens the nested files it is told to.
  * Codex started at the root reads only root `AGENTS.md`. Its routing line sends the agent to `services/ingestion-scraper/AGENTS.md` and `services/core-hub/AGENTS.md` before editing.
  * Check G maps `kafka_producer.py` and `RawAuditService.java` to both their service domain and `system`. A PR that changes them without touching `contracts.md` or writing `Docs unchanged: system — <reason>` fails.
* **Stopping before done.** When the session stops before the spec is done, it appends a handoff block (§8.3):

```markdown
## Handoff
- Written against: develop @ e51f742; branch `feature/raw-pointer-contract`, 3 commits ahead
- Done: Python producer sends `retrieved_at` + `raw_object_key` for every archived doc; tests
  `…::test_raw_pointer_published_for_unpublished_documents` red→green; CON-002 text updated.
- Not done: core-hub `RawAuditService` still reads `ingested_at`; `RawAuditIT` fixture is hand-written.
- Next: generate the raw fixture from pytest (CON-001), point `RawAuditIT` at it, rename the Java field read.
- Docs: CON-001, CON-002 changed; HUB-0xx unchanged (raw audit write semantics unchanged).
- Open decisions: none.
- Verify: `cd services/ingestion-scraper && uv run pytest tests/unit -q` (expect ≥ N passed);
  `cd services/core-hub && ./gradlew test --rerun-tasks` (expect ≥ M); integration in CI.
```

* **Recovery.**
  * The next session runs `git log e51f742..origin/develop -- <files named in the block>`; the develop SHA survives rebases.
  * It also reads the branch's own commits with `git log origin/develop..HEAD`.
  * It re-reads anything that changed before trusting the block.

---

## 8. Development lifecycle after cutover

### 8.1 Flow

1. **Scope.** A change spec has a required **Docs impact** field (decision "docs impact field and Docs unchanged line"). It lists the requirement IDs the spec adds (as `NS-new`), changes or retires, or says `none — <reason>`.
2. **Test-first.** Tests are checked against the cited requirements, not against prose elsewhere.
3. **Implement.** The PR edits the owning doc in the same PR:
   * new IDs come from `--next`;
   * changed requirements keep their ID (INV: amended in place);
   * retired requirements move to `Retired requirements`;
   * verification rows are updated.
4. **Disposition per touched domain.** Check G maps each changed path to **one or more** domains via `docs-check.toml` `[ownership]`, so cross-cutting files map to their service and to `system` or `operations`. For every touched domain, one of these must hold:
   * an owner doc in that domain changed; or
   * the PR body has `Docs unchanged: <domain> — <reason>` (a literal placeholder is rejected).

   `DECISIONS.md` is treated as domain `decisions`: a PR that adds a `CHOICE` heading must change a `docs/` owner or say `Docs unchanged: decisions — <reason>`.
5. **Merge.** Use the recipe in `docs/engineering/change-workflow.md`:
   1. rebase onto `origin/develop`;
   2. run `python -m tools.docs_check --base origin/develop` locally;
   3. push with lease and wait for CI on the rebased head;
   4. fast-forward `develop`.

   The PR template records the semantic review (§10.2).
6. **Archive.** The spec moves to `specs/done/` with status `done` and is frozen (decision "archive policy for specs/done").

### 8.2 Status `hold`

`specs/README.md` gains the `hold` status already used by the 4 specs in `specs/hold/`.

### 8.3 Recoverable handoff format

The format is the block in §7.6. It is required whenever a session stops before its spec is done. Required lines:
* `Written against: develop @ <sha>` (plus branch and commits ahead)
* `Done`
* `Not done`
* `Next`
* `Docs`
* `Open decisions`
* `Verify`

It lives in the spec's optional `## Handoff` section, added to `_template.md`. The session-log row in `TODO.md` keeps its one-line role.

### 8.4 Code-done specs blocked on the Mac (decision "code-done specs blocked on the Mac")

* Merged behaviour moves to `docs/research/*`.
* The spec keeps its remaining operational acceptance (the Mac build, the coverage record, hand checks) and cites the IDs.
* The `SpecialistClassifier` heading follows §4.

### 8.5 Conversion provenance (initial rollout only)

The seven domain specs (`living-docs-system-and-contracts` through `living-docs-engineering-workflow`) write approved behaviour into `docs/` from sources of different standing. Every requirement they write carries a `Source` from this list, in priority order:
1. today's `docs/requirements.md` §, when still true;
2. a `DECISIONS.md` `CHOICE` heading;
3. an archived spec's requirement or test list;
4. an invariant;
5. an active code-done spec covered by the decision `code-done specs blocked on the Mac` (decision "code-done specs blocked on the Mac");
6. an owner ratification.

**If the only source is code, a README, a CLAUDE.md trap or a config comment,** the requirement is written with `Source: <domain> ratification batch` and status `pending-decision`. Its row cites the heading `## <date> — Living docs — PENDING — <domain> ratification batch`, which the domain spec appends to `DECISIONS.md` with the full list.
* The owner approves each domain's list once.
* The approval is appended to `DECISIONS.md` by the owner, as `## <date> — Living docs — CHOICE — <domain> ratification batch`.
* The rows are then updated to cite it.

**A source that contradicts the code** (for example the raw-pointer field; see decision "defects found while scoping") is written as the approved version with status `divergent`, citing a DECISIONS heading. It never silently follows the code.

The final gate requires every ratification batch to be approved, and allows no `pending-decision` row left on a blocking item.

---

## 9. Conflict policy

### 9.1 Precedence (highest first)

1. **Locked machine authorities.** Registered hypothesis files, applied Flyway migrations, and version-locked universe rules: a doc that disagrees is wrong. Changing a locked file follows its own lock procedure.
2. **Other machine authorities, for values.** Topics, compose, sources, alert rules and pins: a doc that disagrees on a value is wrong. A disagreement on meaning is handled as case 3.
3. **`docs/`, for approved behaviour.** When code disagrees, neither silently wins.
   * The finder records the divergence: status `divergent` plus a DECISIONS `FLAG` entry.
   * The owner chooses to **fix code** (a spec) or **ratify code** (a doc edit citing the decision).
   * Editing docs to match code without that decision is prohibited. The initial conversion follows §8.5.
4. **Active change spec.** It governs its own work. `docs/` stays authoritative for current behaviour until the spec merges. A spec that needs a requirement changed says so in Docs impact; it never quietly contradicts it.
5. **`DECISIONS.md`.** It records decisions; it is not a rule store.
   * At cutover, every still-binding `CHOICE` is absorbed: the matrix C maps it to an ID, and the doc row cites it as `Source`. Every other entry is history.
   * There are 117 `CHOICE` headings at e51f742 (outside code fences; plain grep gives 118 because of the format template). The matrix fragment of each domain classifies every one in its domain as binding or history. The cutover spec checks that all 117 are classified.
   * After cutover, a behaviour-changing `CHOICE` lands in the same PR as its doc edit (check G, domain `decisions`).
   * An unabsorbed decision never outranks `docs/`. A conflict between them is a `FLAG` entry plus a doc PR.
   * A DECISIONS entry cannot narrow an invariant; only an amendment or exception in `invariants.md` can (decision "can a DECISIONS entry narrow an invariant").
6. **Agent instructions and READMEs.** They never win on requirements. A conflict is fixed in the file that is not the owner. Agent-session hard rules are owned by root `AGENTS.md` (§7.2).
7. **`specs/done/`, `HISTORY.md`, `TODO.md` notes.** These are never consulted for current rules.

### 9.2 Docs are not proof

* A `tested` status means a named test exists.
* CI is the only evidence that the test passes.
* A mutation check is the only evidence that it would fail.
* Reviews and audits cite code or execution, never a doc, as evidence of compliance.

### 9.3 Approved exceptions

Approved exceptions to an invariant are stated **only under that invariant** in `invariants.md`, with the DECISIONS heading that approved them. Owner docs link to them. Three exceptions are known:
* **Restore path writes Postgres and Neo4j.** Exception to INV-2; restore runs into empty stores only (decision "restore exception to invariant 2").
* **core-hub calls ClinicalTrials.gov directly** for the watchlist preview (DECISIONS 2026-09-20). Stated under INV-4: an external source reached outside a `SourceConnector`, for one interactive lookup, with nothing archived, published or stored.
* **`sample_corroborations.py` reads Postgres and Neo4j from the scraper package.** It only reads, so it is within INV-1. It is stated as a scope note on INV-1.

---

## 10. Drift prevention

### 10.1 Deterministic: `tools/docs_check/`

This is proposed, not implemented; `docs-check-tooling` builds it.

* **Runtime.** Python stdlib only, run as `python3 -m tools.docs_check` from the repo root.
* **Configuration.** `docs-check.toml` holds:
  * the namespaces;
  * the ownership map: path globs → one or more domains → owner docs;
  * `frozen_paths`;
  * the budgets;
  * the check scopes;
  * `[rollout] base` (the recorded reconciliation base; §12).
* **Exit codes.** 0 clean, 1 findings, 2 configuration or usage error. A missing `--base` ref when C2 or G is requested is also 2.
* **Output.** One line per finding: `CHECK path:line message`.

| Check | Asserts | Scope |
|---|---|---|
| A links | Relative links and `#anchors` resolve. Every `frozen_paths` entry exists | `docs/`, active and hold specs, READMEs, agent files, `SETUP.md` (not `specs/done`, not `DECISIONS.md`) |
| B paths | A backticked token that starts with a tracked top-level directory (`services/`, `config/`, `docker/`, `docs/`, `specs/`, `.github/`, `tools/`), or names a tracked root file, exists. | `docs/**` and agent files only |
| C IDs unique | Each ID is defined once. **C2:** no ID defined at `--base` disappears | `docs/` |
| D references | Every `NS-NNN` and "Invariant N" reference resolves. Every cited `DECISIONS.md` heading exists. A bare `D-NN` (register number) in `docs/` or an agent file exits 1; in specs it is allowed only in parentheses after the heading it names. An active spec citing a retired ID, or a `CON-?` placeholder, exits 1 | `docs/`, active and hold specs, agent files, PR body |
| E structure | Required H2s in living docs. `Last reviewed against` SHA is an ancestor of HEAD. Active and hold specs carry the required fields, including Docs impact | `docs/**` except the non-normative files listed in `docs-check.toml`; `specs/*.md` and `specs/hold/*.md` except `README.md` and `_template.md` |
| F ownership | Every tracked path matches an ownership rule or `unowned_ok`, and every owner doc exists | repo |
| G impact | For each domain of a changed path, an owner doc changed or the PR body has `Docs unchanged: <domain> — <reason>` (the placeholder text is rejected). Skipped, not failed, when no PR body is given (push runs) | PR diff (`--base`, `--pr-body`) |
| H legacy | `docs/requirements.md` holds only the banner paragraph and the index table | one file |
| J index | Each TODO row's link exists and its status matches the spec's `**Status:**`. `done` rows point under `specs/done/`. Every spec has a row | `TODO.md`, `specs/` |
| K verification | Every active ID has exactly one verification row. For `tested` rows, `path::name` exists as `def name` / `void name(` / `it(`/`test(` with that name in that file. `Source` is non-empty | `docs/` |
| L agent files | Root `AGENTS.md` ≤ 6 KB, nested ≤ 3 KB, chain ≤ 16 KB. `CLAUDE.md` starts with `@AGENTS.md`, is ≤ 512 B, and has no must/never/always. No `@` import in `AGENTS.md` | agent files |
| M matrix (rollout only) | With `--matrix specs/living-docs-cutover-matrix.md --domain NS`, every matrix row for that domain with disposition move, ratify, divergent or retire has an assigned ID that check C finds defined. Removed by the cutover spec after the final gate, together with its tests | the matrix file |
| I archive | **Later.** A diff that touches `specs/done/*` other than a rename into it | PR diff |

**Regexes** (`docs-check-tooling` fixes them exactly):
* `\b(INV-\d{1,2}|(SYS|CON|ING|EXT|HUB|COR|RES|EVA|STR|DSH|OPS|ENG)-\d{3})\b`
* `[Ii]nvariants? #?(\d{1,2})( and #?(\d{1,2}))?`

**CI** (`docs-check-tooling`). `.github/workflows/docs.yml` runs:
* on `pull_request`, types `opened`, `synchronize`, `reopened` and `edited`, into `develop` and `feature/living-docs-integration`;
* on `push` to `develop`.

It checks out with `fetch-depth: 0`. On pull requests the base is `origin/${{ github.base_ref }}`. On push it is `${{ github.event.before }}`; when that is all zeros (a new branch), C2 and G are skipped with a notice, not failed. The PR body is passed through `env:`, never inline `${{ }}`, and a null body is written as an empty file. `docs-check-tooling` also adds `feature/living-docs-integration` to `commit-identity.yml`'s `pull_request` branches. The workflow is report-only (`continue-on-error: true`) until cutover. The cutover removes that flag.

**Checker tests.** Each check has unit tests over fixture trees built in temp directories, including a seeded-defect test that must exit 1. Mutant fixtures are never committed as standing branches or files outside the test tree.

### 10.2 Semantic

* **PR template** (`.github/pull_request_template.md`, new; `living-docs-engineering-workflow`). It records:
  * Docs impact: the IDs, or the `Docs unchanged:` lines;
  * "Requirements touched were read against the code in this diff: yes/no";
  * divergences found, with their DECISIONS heading;
  * tests mapped to IDs;
  * mutation checks.

  Check G parses only the `Docs unchanged:` lines; the rest is for the reviewer.
* **`Last reviewed against: develop @ <sha>`** on each living doc is bumped only by someone who re-read the doc against the code.
* **Docs drift audit spec.** A draft created at cutover and run later. It compares each owner with the code, oldest `Last reviewed against` relative to commits in its ownership globs first.

---

## 11. Implementation decomposition (one spec per row)

Each domain spec also owns its domain's **active and hold specs**:
* add `Docs impact`;
* replace restated requirement text with IDs;
* for research, apply decision "code-done specs blocked on the Mac".

The matrix assigns every active spec to one domain spec.

| Spec | Owns | Depends on |
|---|---|---|
| `docs-check-tooling` | `tools/docs_check/`, `docs-check.toml`, `.github/workflows/docs.yml` (report-only), the integration branch in `commit-identity.yml`, checker tests | — |
| `living-docs-system-and-contracts` | `docs/README.md`, `docs/system/*` | DECISIONS for decision "raw-pointer contract", decision "restore exception to invariant 2", decision "invariant 6 wording", decision "can a DECISIONS entry narrow an invariant" |
| `living-docs-ingestion` | `docs/ingestion/*`; ingestion active specs | `living-docs-system-and-contracts` (CON numbers); decision "initial_lookback value", decision "fda_approval source", decision "run_pipeline.py support", decision "RunResult counters" |
| `living-docs-core-hub` | `docs/core-hub/*`; core-hub active specs | `living-docs-system-and-contracts`; decision "closed sets on the wire" |
| `living-docs-research` | `docs/research/*`; research active specs incl. the six code-done specs | `living-docs-system-and-contracts`; decision "spec paths cited by hash-locked hypotheses", decision "code-done specs blocked on the Mac", decision "trial ledger and holdout as untracked local files" |
| `living-docs-strategy-and-dashboard` | `docs/strategy/*`, `docs/dashboard.md`; their active specs | `living-docs-system-and-contracts`, `living-docs-core-hub`, `living-docs-research` (placeholders allowed while they are planned); decision "as-of reads hide or raise" |
| `living-docs-operations` | `docs/operations/*`; operations active specs | `living-docs-system-and-contracts` |
| `living-docs-engineering-workflow` | `docs/engineering/*`, `specs/README.md`, `specs/_template.md`, `.github/pull_request_template.md` | `docs-check-tooling` |
| `agent-instruction-hierarchy` | all `AGENTS.md`/`CLAUDE.md` | the seven domain specs |
| `legacy-docs-retirement` | `docs/requirements.md` → § index (built from the merged domain docs); `docs/strategy-research.md` banner and copied values replaced by links; READMEs (root, services, docker, orchestration) trimmed to links; `SETUP.md`, `PREREQUISITES.md` (protocol-owned rows removed, dead knobs removed); `test_docs_never_offer_down_v_as_a_fix` file list extended | the seven domain specs, `agent-instruction-hierarchy` |
| `living-docs-cutover` | integration, reconciliation, final gate, enforcement on, archive banners, `TODO.md`/`DECISIONS.md`, rollback; the migration matrix `specs/living-docs-cutover-matrix.md` (excluded from checks D, E and J in `docs-check.toml`, archived with the cutover spec); removal of check M | all ten part specs |

**Parallelism.** After `docs-check-tooling`, `living-docs-system-and-contracts` and `living-docs-engineering-workflow` start; ingestion, core-hub, research and operations follow `living-docs-system-and-contracts`, and strategy-and-dashboard merges after core-hub and research. Placeholders let any of them be drafted earlier. While a domain is listed in `[rollout] planned_domains`, links into it and namespace placeholders for it are notices, not findings; each domain spec removes its own domain from the list as its last step, and the final gate requires the list to be empty. `legacy-docs-retirement` also needs `agent-instruction-hierarchy`, because READMEs link the service `AGENTS.md` files. Shared files have one writer per section: `docs/README.md` is written whole by `living-docs-system-and-contracts`; in `docs-check.toml`, `TODO.md` and the matrix `ID` cells (including the decisions-table `IDs` cells for binding rows) each spec edits only its own lines; `DECISIONS.md` is append-only. Each part spec archives itself and updates its own `TODO.md` row in its own PR.

**Code changes.** The rollout changes **no application code**. It does change one doc-reading test (`legacy-docs-retirement`) and CI configuration (`docs-check-tooling` and `living-docs-cutover`).

## 12. Cutover model (full plan in `specs/living-docs-cutover.md`)

* **Integration branch (decision "rollout branch model").** `feature/living-docs-integration` is cut from `develop` at a recorded base.
  * Each spec branches from it and opens a PR into it.
  * Merges into it follow the project rule: the owner's word, then a local rebase onto the integration branch and a fast-forward.
  * Nothing reaches `develop` until the cutover PR, so a partly written authority is never live.
* **Concurrent changes.** Other specs keep merging to `develop` during the rollout. The integration branch is rebased onto `develop` **only after all sub-specs have merged into it**, so no open sub-branch needs `rebase --onto`. The reconciliation pass then runs:
  1. `git diff <[rollout] base>..origin/develop` over docs, specs, config, compose, agent files and source.
  2. Map each changed path to its owners via `docs-check.toml`.
  3. If a commit on `develop` edited an old authority file (`docs/requirements.md`, `CLAUDE.md`, a README), keep the integration version and port the develop delta to the owner doc.
  4. New active specs from `develop` get `Docs impact`.
  5. New `CHOICE` entries are absorbed.
  6. Every item is logged in the cutover spec's `## Reconciliation log`, and `[rollout] base` is updated.

  The owner's freeze (decision "merge freeze around the cutover") covers **all** merges to `develop` from the start of this pass until the cutover merge. It is a short window, and it avoids a re-rebase after every code-only merge.
* **Final gate.** All of these must hold:
  * `docs_check` exits 0 with enforcement on;
  * every ratification batch is approved;
  * no `pending-decision` remains on a blocking item;
  * every matrix row and every binding `CHOICE` maps to an ID;
  * agent budgets pass;
  * the manual Claude and Codex load checks are recorded (root and service launch);
  * all existing CI is green on the rebased head;
  * one independent post-integration review has no open blocker.
* **Rollback.**
  * **Before the cutover merge:** stop. The integration branch never reached `develop`.
  * **At cutover:**
    1. Push a tag `pre-living-docs` at the develop SHA before the fast-forward. This is a tag push, not a force push.
    2. Fast-forward `develop`.

    To roll back, one PR reverts `pre-living-docs..<cutover tip>` (`git revert --no-commit <range>`, one commit).
  * **The revert is clean only until a later PR touches `docs/`, an agent file or a README.** After that, the revert must be reconciled by hand. The cutover spec states this window and the post-cutover watch period.
  * **Branch protection.** If the owner makes `docs` a required check, rollback also needs that setting removed by hand. The cutover spec lists it.
  * **No data or runtime rollback is needed.**
