# Managed Ingestion Config

**Status:** blocked
**Blocked by:** `specs/graph-and-connector-wiring-fixes.md` (connector registry; publish threshold and rate limits read from the source entry) and `specs/dashboard-foundation.md` (core-hub write token).
**Branch:** `feature/managed-ingestion-config`

---

## Context

Decided 2026-10-08: tracked companies and their search terms become manageable at runtime, with the watchlist as the single source. core-hub stores the config with full history, and the version of the term list in force is stamped on every extraction. Research config stays locked: hypotheses, `protocol.yaml`, strategies, the model registry and gate, the universe rules, rate limits and the XBI/EURUSD benchmark tickers.

Today the same intent lives in three places that don't talk to each other:

| Where | Controls | Read |
|---|---|---|
| `.env` `WATCHED_TICKERS` (8 tickers) | Which tickers price-service refreshes (`price_universe()`) | At container start |
| `config/sources.yaml` `prefilter_vocabulary` per source; PubMed `source_config.search_term` | Keyword gate before the LLM; the PubMed query | Scraper `create_app`, at start |
| `connectors/epo_ops.py` `_CPC_CLASSES`; `connectors/sec_edgar.py` forms and items, no CIK filter | Patent and EDGAR scope | Hardcoded |
| Postgres `watchlist`, `watchlist_gene_target` (Flyway V3) | The user's tracked companies and gene targets, edited in the dashboard | Feeds nothing |

`prefilter.py` fixes `PREFILTER_VERSION = "v1"` whatever the vocabulary holds. That value goes into `extraction_id` (`identity.py`) and into the model gate check (`extraction_backend._check_gate`), so an edited vocabulary today leaves no trace of which terms let a document through. Requirements §6.6: the vocabulary "is versioned alongside the prompt" and "measured on the golden set for false negatives". Golden documents carry a `prefilter_should_pass` label (`tests/golden/FORMAT.txt`).

## What this builds

1. **Storage in core-hub** (Postgres, next free Flyway version at implementation time):
   - The existing `watchlist` gains `cik` and `active`; new `watchlist_alias` (company name variants, drug and program names) alongside the existing gene targets.
   - `source_query_config(source_type, key, value)`: per-source terms and query parameters as generic key/value rows (e.g. `prefilter_term`, `search_term`, `cpc_class`, `include_watchlist_terms`). core-hub never interprets a key per source.
   - `ingestion_config_version`: append-only. Every change through the API writes a new row holding the full effective config as canonical JSON, its SHA-256, `created_at` (UTC), and the `reason` sent with the change. No row is updated or deleted.
   - A seed migration copies today's `sources.yaml` vocabulary and query terms, the hardcoded CPC classes, and the eight `WATCHED_TICKERS` with company names into these tables as version 1. After it, `prefilter_vocabulary` is removed from `sources.yaml` and `WATCHED_TICKERS` from `.env.example`.
2. **core-hub API** (writes need the write token):
   - `GET /api/v1/ingestion-config/{source_type}` returns the effective config for one source: `version`, `vocabulary_hash`, `prefilter_terms` (source terms plus, when `include_watchlist_terms` is set, active watchlist names, aliases and gene targets), and `query` (its key/value parameters).
   - `GET /api/v1/ingestion-config/versions` (paged) and `/versions/{id}` with a diff to the previous version.
   - `PUT /api/v1/ingestion-config/sources/{source_type}` and the watchlist alias endpoints; each takes a required `reason`.
   - `GET /api/v1/price-universe` returns active watchlist tickers.
3. **Scraper reads config per run.** At the start of each `/ingest/<source_type>` call, the scraper fetches its effective config from core-hub. It keeps the last good copy in memory; if core-hub is unreachable and it has none, the run fails with a named error and returns no cursor, so the DAG leaves the cursor untouched (§5). Connectors take their query parameters from the fetched `query`.
4. **Vocabulary version on every extraction.** `prefilter_version` becomes `"{algorithm_version}+{vocabulary_hash[:12]}"` (e.g. `v1+3f9a0c12d4e7`). The model gate compares only the algorithm part, so editing terms doesn't invalidate the model's gate record. Instead, a vocabulary is activated only if every golden document labelled `prefilter_should_pass` passes it (zero false negatives on the golden set). A failing vocabulary is refused, and the scraper keeps its last good one and logs an error naming the documents that failed. The golden set ships in the scraper image.
5. **`POST /config/validate-vocabulary`** on the scraper: given a candidate term list, returns pass/fail and the golden documents it would drop. The dashboard calls it before saving. It reads only the golden set and writes nothing.
6. **price-service universe** comes from `GET /api/v1/price-universe` plus the fixed benchmark and FX tickers, read at each refresh. If core-hub is unreachable the refresh fails and reports it; it does not fall back to a stale env list.

## Out of scope

- The dashboard pages (`specs/ingestion-config-ui.md`).
- Re-evaluating documents a previous vocabulary filtered out. `scripts/reextract.py` can be run per prefilter version later.
- The backtest universe, which stays rules-based and pre-registered (`specs/point-in-time-universe.md`). Live ingestion scope and the backtest universe are deliberately separate.
- Source schedules (Airflow reads them at DAG parse; pause and trigger belong in `specs/pipeline-control-view.md`), rate limits, EDGAR forms and items.

## Constraints

- Invariant 1: the scraper reads config over HTTP and writes only MinIO and Kafka. It never reads Postgres.
- Invariant 2: only core-hub writes the config tables.
- Invariant 4: no per-source branching in core-hub or shared scraper code; each connector reads its own keys.
- Invariant 6: core-hub's URL reaches the scraper and price-service through `.env`.
- Invariant 10: config versions are append-only, keyed by id; the content hash is deterministic (canonical JSON, sorted keys and terms, lower-cased terms).
- Invariant 14: `event_id` is unchanged by any config change. Only `extraction_id` (through `prefilter_version`) changes.
- Invariant 7: `prefilter_version` stays a string field; no schema change to `ResearchSignalEvent`.
- §6.6: the vocabulary is versioned, and measured on the golden set before it takes effect.

## Required tests

core-hub, `src/integrationTest/java/.../ingestionconfig/IngestionConfigIT.java`:
- `seedMigrationCreatesVersionOneWithCurrentTermsAndTickers`
- `everyChangeWritesANewVersionAndLeavesEarlierVersionsUnchanged`
- `changeWithoutReasonIsRejected`
- `contentHashIsIdenticalForTheSameConfigInAnyInsertionOrder`
- `effectiveConfigIncludesWatchlistTermsOnlyWhenTheSourceOptsIn`
- `inactiveWatchlistCompanyContributesNoTerms`
- `versionDiffListsAddedAndRemovedTerms`
- `priceUniverseListsActiveWatchlistTickersOnly`
- `configWriteWithoutTokenIsRejected`

core-hub ArchUnit:
- `ingestionConfigPackageHasNoSourceTypeLiteralBranches`

ingestion-scraper, `tests/unit/test_managed_config.py`:
- `test_ingest_fetches_effective_config_before_fetching_documents`
- `test_connector_receives_query_parameters_from_fetched_config`
- `test_prefilter_version_carries_algorithm_version_and_vocabulary_hash`
- `test_changed_vocabulary_changes_extraction_id_but_not_event_id`
- `test_model_gate_compares_only_the_algorithm_part_of_prefilter_version`
- `test_vocabulary_dropping_a_should_pass_golden_document_is_refused`
- `test_refused_vocabulary_keeps_the_last_good_one_and_logs_failing_documents`
- `test_core_hub_unreachable_uses_last_good_config`
- `test_core_hub_unreachable_with_no_config_fails_run_without_cursor`
- `test_validate_vocabulary_endpoint_reports_dropped_golden_documents`
- `test_golden_set_is_packaged_with_the_service`
- `test_sources_yaml_carries_no_prefilter_vocabulary`

backtesting, `tests/unit/test_price_universe.py`:
- `test_refresh_universe_is_watchlist_tickers_plus_benchmark_and_fx`
- `test_refresh_fails_loudly_when_core_hub_is_unreachable`
- `test_watched_tickers_env_is_no_longer_read`

## Definition of done

```bash
cd services/core-hub && ./gradlew test integrationTest --rerun-tasks
cd services/ingestion-scraper && uv run pytest tests/unit -q --strict-markers && uv run ruff check . && uv run mypy src
cd services/backtesting && uv run pytest tests/unit -q --strict-markers
```

Expected: all green, including the 10 Java, 12 scraper and 3 backtesting tests above.

Then on the stack: add a term to PubMed through the API with a reason; the next PubMed run's extractions carry the new `prefilter_version`, and `GET /api/v1/ingestion-config/versions` shows the change and its reason.

## Notes

- Why golden-set validation rather than re-gating the model: the prefilter is deterministic and cheap to measure, and adding terms can only let more documents through. Re-running the LLM gate for every edited term would make the config unmanageable on a local model.
- The existing gate record `config/models/scores/gpt-4o-mini-2024-07-18.json` stores `prefilter_version: "v1.0"` while `PREFILTER_VERSION` is `"v1"`. Comparing the algorithm part removes the mismatch only if both are normalised to the same algorithm id; settle it in this spec's first commit.
- Vocabulary removals are the risky edit: they can only add false negatives, which the golden check catches for labelled documents only.
