# CLAUDE.md — Auspex

Auto-loaded every session.

## Always-loaded context
@TODO.md
@VERSIONS.md

Those two are imported, so they are already in context — do not re-read them from disk. Everything else is on demand:
- `specs/<name>.md` — the current spec (active). `specs/done/<name>.md` for completed ones. Self-contained; read it in full before starting.
- `docs/requirements.md` — read the sections the spec cites when verifying test consistency.
- `docs/PREREQUISITES.md` — read when a spec is blocked on a credential or user decision.
- `DECISIONS.md` — read before flagging something (it may already be logged); append when you flag.
- `docs/plan.md` — reference only; contains original phase definitions for Phases 0–6.

**The first `ready` spec in TODO.md is the work.** Update it as items complete, not at the end of the session.

## Naming (fixed — do not vary)
Project **Auspex**. Named for the Roman official who read scattered signs for meaning, which is the job: no single source is evidence, convergence is.

| Where | Value |
|---|---|
| Repo / compose project | `auspex` · `COMPOSE_PROJECT_NAME=auspex` |
| Kafka topics | `auspex.raw.ingested`, `auspex.signals.extracted`, `auspex.signals.corroborated`, `*.dlt` |
| Java root package | `dev.auspex.corehub` |
| Python packages | `auspex_ingest` (inside `services/ingestion-scraper/src/`) · `auspex_backtesting` (inside `services/backtesting/src/`) |
| MinIO buckets | `auspex-raw` (signal documents) · `auspex-prices` (OHLCV Parquet snapshots) |
| Postgres databases | `auspex` (application) · `airflow` (metadata) |
| Neo4j / Postgres roles | `auspex_app`, `airflow` |

**Service directories stay descriptive**: `ingestion-scraper` and `core-hub`, never themed. The project gets a name; the components get descriptions.

**No plan step references in code or names.** `step_3_2`, `phase_2`, `test_step_1_1` — these mean nothing outside the execution plan and become confusion the moment the work is done. Use technical, descriptive names: `corroboration_review`, `academic_papers`, `test_biorxiv_payload_maps_to_rawdocument`. This applies to: file names, function names, test names, variable names, branch names beyond the phase branch itself, and commit messages.

## What this is
See README.md for system overview and architecture.

## Session start (every time, no exceptions)
1. Read `TODO.md` — find the first `ready` spec. That is the work.
2. Open that spec file in `specs/` and read it in full. It is self-contained.
3. If no spec is `ready`, pick a `draft` spec to scope — see `specs/README.md` for the format. Scoping means filling in required tests and definition of done, not implementation.
4. Confirm the spec's required tests are consistent with `docs/requirements.md` before writing them (see "The rule that matters most" below).
5. Work only the current spec. Do not start another.
6. When done: mark the spec `done`, move it to `specs/done/`, update its row in `TODO.md` (link points to `specs/done/<name>.md`), commit.

## No legacy system
Phases 0–3 are complete. There is no legacy system predating this project — no prior schema to migrate from, no behaviour to preserve from a prior release. The only Flyway "migrations" are the scripts that create the schema on an empty database — Flyway's word, not a change of direction.

## The rule that matters most
**A green suite is necessary, not sufficient.** Before writing a step's tests, verify they are consistent with `docs/requirements.md`. If a listed test can only pass by violating a requirement, **stop, append to `DECISIONS.md`, and ask.** Do not write the test.

This is not hypothetical: v1 of this plan contained a test (`test_dag_task_only_invokes_fetch_since`) that could only pass by putting the entire pipeline inside every connector. TDD would have built the wrong architecture faithfully.

## Invariants (never violate; if a task seems to require it, stop and flag)
1. `ingestion-scraper` writes only to MinIO and Kafka. Nothing else. Ever.
2. `core-hub` is the sole writer to the application DB and Neo4j.
3. DAG code calls the scraper HTTP API (`/ingest/<source_type>`). No ingestion logic in DAGs; no pipeline logic in `fetch_since()`.
4. New source = a `SourceConnector` + a `sources.yaml` entry. No `if source_type == ...` anywhere in shared code.
5. All corroboration sits behind `CorroborationService`.
6. No credentials, URLs, or ports in source. `.env` only; API keys are Airflow Connections.
7. Python model and Java record stay field-for-field identical; snake_case on the wire; the contract fixture is **generated** by pytest.
8. Synchronous Python throughout. No `async`, no `aiokafka`.
9. UTC everywhere, including derived strings like MinIO keys.
10. Idempotent writes on each path's **declared** natural key (requirements §3.7) — not one global key.
11. Nothing dies silently: DLT with headers, never blocking a partition.
12. Parameterized queries only. Enforced by ArchUnit + behavioural injection tests.
13. The MinIO archive is unconditional — written before any other side effect.
14. `event_id` is document identity. It never varies with schema version, prompt, model, or which source saw it.
15. Test-first, subject to the rule above.

## Commands

| Purpose | Command |
|---|---|
| Bring up infra only | `docker compose -f docker/docker-compose.yml --env-file .env up -d --wait` |
| Bring up full stack (incl. app services) | `docker compose --profile app -f docker/docker-compose.yml --env-file .env up -d --wait` |
| Tear down (keep volumes) | `docker compose -f docker/docker-compose.yml --env-file .env down` |
| Tear down (wipe volumes) | `docker compose -f docker/docker-compose.yml --env-file .env down -v` |
| Python: install | `cd services/ingestion-scraper && uv sync --all-extras` |
| Python: unit tests (inner loop) | `cd services/ingestion-scraper && uv run pytest tests/unit -q` |
| Python: one file's tests | `cd services/ingestion-scraper && uv run pytest tests/unit/test_ingestion_pipeline.py -q` |
| Python: full suite | `cd services/ingestion-scraper && uv run pytest -q` |
| Python: lint + types | `cd services/ingestion-scraper && uv run ruff check . && uv run mypy src` |
| Java: unit only (inner loop) | `cd services/core-hub && ./gradlew test` |
| Java: container tests only | `cd services/core-hub && ./gradlew integrationTest` |
| Java: everything | `cd services/core-hub && ./gradlew check` |
| Java: one test class | `cd services/core-hub && ./gradlew test --tests '*GraphUpdateServiceTest'` |
| Java: forked-TZ execution | `cd services/core-hub && ./gradlew timezoneCheck` |
| Java: force re-run (defeat up-to-date) | `cd services/core-hub && ./gradlew test --rerun-tasks` |
| Smoke test | `./verify_pipeline.sh` |
| Regenerate contract fixture | `cd services/ingestion-scraper && uv run pytest tests/unit/test_contract_fixture.py` |

**A test run that executes zero tests is a failure, not a pass.** Gradle's `test` task with no test classes succeeds; so does pytest with a wrong path. Always check the reported test count. Set `failOnNoDiscoveredTests = true` on every `Test` task (confirm it exists on the pinned Gradle version at Step 0.0) and use `--strict-markers` in pytest.

**Gradle caches task outcomes.** A second `./gradlew test` with no source changes reports `UP-TO-DATE` and runs nothing — which looks exactly like a pass. When you need to *prove* a test ran (verifying a red, or confirming a fix), use `--rerun-tasks`, or read the count out of `build/reports/tests/`.

## The TDD loop
```
1. Write the spec's tests.           2. Run them.
3. Verify each fails for the RIGHT reason:
     Python: ImportError / AttributeError / AssertionError — NOT collection or syntax errors
     Java:   compile error on a missing class is acceptable; assertion failure preferred
   Paste the failure output into TODO.md under the spec.
4. Implement the minimum to pass.    5. Re-run the spec's tests.
6. Run the unit suite (fast).        7. Update docs (see below).   8. Commit.
9. At spec completion only: run the full container suite.
```
Do not run the full container suite on every red-green cycle — it takes minutes and you will stop doing it.

## Documentation maintenance

**Doc updates are part of the commit, not an afterthought.** Before committing any step, update every README and CLAUDE.md affected by the change. The table below maps change types to files:

| Change | Update these files |
|---|---|
| New connector | `services/ingestion-scraper/README.md` — connectors table |
| New script | `services/ingestion-scraper/README.md` — scripts table |
| Pipeline stage added/removed | `services/ingestion-scraper/README.md` — pipeline stages list |
| New `sources.yaml` field | `services/ingestion-scraper/README.md` — configuration schema table |
| New Kafka topic | `docker/README.md` — topics table · `services/CLAUDE.md` — topics table · `docker/CLAUDE.md` — DLT parity note |
| New Docker service | `docker/README.md` — services table |
| New service capability or endpoint | `services/core-hub/README.md` — relevant section |
| New invariant | `CLAUDE.md` — invariants list · relevant service README — key constraints |
| New known trap discovered | `CLAUDE.md` — known traps · relevant service CLAUDE.md — traps |
| New dev command | `README.md` — development commands table · relevant service README |
| New API constraint discovered | `services/ingestion-scraper/README.md` — known API constraints |
| Architecture changes | `README.md` — architecture section |

If a change affects both Claude's operational context and developer understanding, update both the CLAUDE.md file and the README for that directory. They have different audiences and intentional duplication is fine.

**Scaffolding exemption:** creating `pyproject.toml`, `pom.xml`, `docker-compose.yml`, directory trees, and `.env.example` is not behaviour and needs no prior test. Everything else does.

## Test file conventions
```
services/ingestion-scraper/tests/unit/test_<module>.py          # @pytest.mark.unit (default)
services/ingestion-scraper/tests/integration/test_<subject>.py  # @pytest.mark.integration
services/core-hub/src/test/java/**/<Subject>Test.java             # unit, no Spring context      -> ./gradlew test
services/core-hub/src/integrationTest/java/**/<Subject>IT.java    # container-backed, own source set -> ./gradlew integrationTest
```
`CorroborationServiceContractTest` is an **abstract** class. Any new `CorroborationService` implementation must pass it unmodified — do not inline its cases into a concrete test.

## Git

**Branching strategy: Git Flow**
- `main` — production-ready only. Never commit directly.
- `develop` — integration branch. Feature branches merge here.
- `feature/<name>` — one per spec, branched from `develop`. Use the branch name in the spec file.
- `release/<version>` — cut from `develop` when shipping. Merged into both `main` and `develop`.
- `hotfix/<name>` — branched from `main`, merged into both `main` and `develop`.

**Merging: rebase, not merge commits.**
- Before merging a feature branch into `develop`, rebase it onto `develop`: `git rebase develop`.
- Resolve conflicts during rebase, not in a merge commit.
- Fast-forward merge only: `git merge --ff-only feature/<name>`.
- Never merge with `--no-ff` unless explicitly agreed — it creates unnecessary merge commits.

**End-of-spec flow (run in order when a spec is done):**
```bash
git push -u origin feature/<name>
git checkout feature/<name> && git rebase develop
git checkout develop && git merge --ff-only feature/<name>
git push -u origin develop
git checkout main && git merge --ff-only develop
git push origin main
git checkout develop          # reset for the next spec
```

**Other rules:**
- Commit only when the spec's tests pass. A bad change is then one `git revert` away.
- Never commit `.env`, `target/`, `.venv/`, `__pycache__/`, or Docker volumes.
- **No `Co-Authored-By` line.** Do not add Claude attribution to commits.
- **Commit message style:** subject line only, lowercase, `subject: detail1, detail2`. Examples: `real connector wiring: sources.yaml, run_pipeline.py, CT API fix` · `deduplication & amendment precedence` · `confidence scoring for corroboration strength`. No body, no description.

## Known traps (verified — do not rediscover these)
- **`ErrorHandlingDeserializer` is mandatory.** Without it a malformed payload fails inside the poll loop before any error handler runs, and the container retries the same offset forever. Two required tests depend on this.
- **`DeadLetterPublishingRecoverer` defaults to `.DLT` (uppercase) and the same partition number.** We use lowercase `.dlt`, so a custom resolver is required — and it must return partition `-1`, or publishing fails when partition counts differ. *Re-verify against Spring Kafka 4.x; this was confirmed for 2.x/3.x.*
- **`confluent-kafka` `produce()` is asynchronous.** Always `flush()` and check delivery reports. A "successful" run can publish nothing.
- **`MERGE (c:Company {ticker: null})` matches every null-ticker node.** MERGE Company on normalized `name`.
- **Neo4j has no decimal type.** `confidence_score` is `BigDecimal` in the DTO, `NUMERIC(4,3)` in Postgres, and a `double` in the graph via an explicit converter — otherwise SDN may persist a string and Cypher comparison silently breaks.
- **Primitive `double` cannot be null.** A missing `confidence_score` would deserialize to `0.0` and pass validation. Use `BigDecimal` + `@NotNull`.
- **Jackson `FAIL_ON_UNKNOWN_PROPERTIES` must be `false`** on the consumer, or the first additive schema change dead-letters everything.
- **Patents: `filed_date` is NOT the public disclosure date.** A US application publishes ~18 months after filing. Align on the pre-grant publication date. Getting this backwards inverts the look-ahead-bias guard.
- **Clinical trials: same trap.** `first_submitted_date` is private; the post date is public.
- **SEC blocks by IP at 10 req/s aggregate across all `*.sec.gov` hosts**, for ~10 minutes, and retrying extends the block. A descriptive `User-Agent` is mandatory (403 without). `data.sec.gov` counts against the same bucket. To look up a filing's primary document, use `https://data.sec.gov/submissions/CIK{cik_zero_padded_10}.json` (`filings.recent.primaryDocument[i]`); the `Archives/{cik}/{accession_nodash}/index.json` directory endpoint exists but carries no sequence or form-type metadata. EFTS `_source` field names are `adsh`, `ciks`, `display_names` — not `accession_no`, `entity_id`, `entity_name` (those were invented fixture fields; see `specs/edgar-efts-fixture-alignment.md`).
- **openFDA has no designations endpoint.** Do not attempt Fast Track/RMAT/orphan via openFDA — see requirements §6.9.
- **Both PatentsView URLs are superseded, and Lens.org is not free for this use case.** `api.patentsview.org` discontinued 2025-05-01; `search.patentsview.org` migrated to USPTO ODP (requires government ID). Lens.org classifies investment research as commercial use (institutional subscription required). Use **EPO OPS** instead: `https://ops.epo.org/3.2/rest-services/`, OAuth2 client credentials (`EPO_OPS_KEY` / `EPO_OPS_SECRET`), free public service, no government ID, no commercial-use restriction. Register at `developers.epo.org`.
- **Airflow 3 renamed `schedule_interval` to `schedule`.** Task code cannot touch the metadata DB directly; Variables and Connections are proxied through the Task SDK.
- **Local model backend — Docker/Metal:** Docker Desktop on macOS cannot use Metal. Run the model server (Ollama) on the host; the scraper reaches it via `host.docker.internal` in `EXTRACTION_BASE_URL`. See `docker/README.md` for the memory budget table.
- **Local model backend — tag re-pointing:** `ollama pull gemma3:27b` downloads whatever HEAD is at that tag at pull time. The registry pins the exact digest (`gemma3:27b@sha256:...`); `LLMExtractorFactory` compares the registered digest against `ollama show` output at startup and fails before any extraction runs if they differ.

## File map
| File | Purpose |
|---|---|
| `CLAUDE.md` | This file. Always loaded. |
| `TODO.md` | Spec index — status of each spec, session entry point. |
| `specs/` | Active specs — `draft`, `ready`, `blocked`. One file per feature. |
| `specs/done/` | Completed specs — moved here when status is set to `done`. |
| `specs/README.md` | Spec format requirements — what a spec must contain before status is `ready`. |
| `VERSIONS.md` | Pinned versions — single source of truth. |
| `DECISIONS.md` | Append-only log of flags, blocks, and choices made. |
| `docs/requirements.md` | What the system must satisfy. Cited by specs when verifying tests. |
| `docs/PREREQUISITES.md` | Outstanding credentials and user decisions. |
| `docs/HISTORY.md` | Completed phases (0–3) — test counts, pre-fix failures, key decisions. |
| `docs/plan.md` | Reference only — original phase definitions. Superseded by `specs/` for active work. |

## Tone
Do not report a step complete unless its tests actually ran and passed. If something is blocked, say so plainly in `DECISIONS.md` and stop — do not work around an invariant to keep moving.
