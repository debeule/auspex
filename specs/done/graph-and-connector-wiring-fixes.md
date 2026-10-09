# Graph and Connector Wiring Fixes

**Status:** done
**Branch:** `feature/graph-and-connector-wiring-fixes`

---

## Context

The 2026-10-08 control-surface audit found three defects that would make every later view show wrong or empty data. Each was confirmed in the code on `develop`:

1. **Mechanism corroboration can never fire.** `docs/requirements.md` §9 defines `(:Signal)-[:USES_MECHANISM]->(:Mechanism)`, and `CorroborationScanner` matches `[:TARGETS|USES_MECHANISM]`. `Neo4jWriteService.mergeMechanismRelationship` writes `[:VIA]` instead, so a mechanism shared across sources is never matched. Only gene-target corroboration works today.
2. **Ticker lookups match nothing.** `SignalQueryService` (`GET /api/v1/signals/{ticker}`) and `WatchlistService` (summary, signal counts) match `(:Company {ticker: $ticker})`. No code sets `Company.ticker`; only an index exists (`Neo4jSchemaInitializer`). §9 says `ticker` is a set-if-known property and `Company` merges on normalized `name`.
3. **The scraper API can run only two of its sources.** `auspex_ingest/api.py` `_build_connector` branches on `if source_type == "biorxiv"` / `"clinicaltrials"` and raises `ValueError` for every other `sources.yaml` entry (mock, pubmed, edgar, epo_ops). This breaks Invariant 4, and those DAGs fail in production. The same function hardcodes `min_confidence_to_publish=0.5` and the rate limits.

What exists: `SecTickerCache` in core-hub (`watchlist/`) loads SEC `company_tickers.json` (ticker, title). The connectors take their HTTP client and settings through constructors; `scripts/run_pipeline.py` already builds every connector for the CLI path.

## What this builds

- Mechanism links are written as `USES_MECHANISM`. No graph data exists yet, so there is nothing stored under `VIA` to migrate.
- `Company.ticker` is set when it is known: when a `Company` is merged, core-hub looks the normalized name up in `SecTickerCache` and sets `ticker` only on a single unambiguous match. Adding a ticker to the watchlist also back-fills `ticker` on the existing `Company` node whose normalized name matches the SEC title.
- A connector registry in `auspex_ingest`: each `SourceConnector` registers a builder under its `source_type`; `api.py` and `scripts/run_pipeline.py` both build connectors through it. The publish threshold and rate limits come from the `sources.yaml` entry (with the current values as defaults), not from code.

## Out of scope

- New corroboration kinds or Program nodes (`specs/company-program-corroboration.md`).
- Managing tickers or vocabulary at runtime (`specs/managed-ingestion-config.md`).
- Changing the corroboration window, degree cap or scoring.

## Constraints

- Invariant 2: only core-hub writes Neo4j.
- Invariant 4: no `if source_type ==` anywhere in shared code, Python or Java. The registry is the only place a `source_type` string maps to a class.
- Invariant 12: the ticker lookups use bind parameters.
- §9: `Company` keeps merging on normalized `name`; `ticker` is never a MERGE key. A null or ambiguous ticker leaves the property unset, never set to null on an existing value.
- Name normalization for the SEC match: lower-case, strip punctuation and corporate suffixes (`inc`, `corp`, `corporation`, `co`, `ltd`, `plc`, `nv`, `sa`, `ag`, `holdings`), collapse whitespace. The same function is used on both sides.

## Required tests

core-hub, `src/integrationTest/java/.../persistence/MechanismRelationshipIT.java`:
- `mechanismLinkIsWrittenAsUsesMechanism`
- `twoSourcesSharingOnlyAMechanismProduceACorroboration`

core-hub, `src/integrationTest/java/.../persistence/CompanyTickerIT.java`:
- `companyMatchingOneSecTitleGetsItsTicker`
- `companyMatchingTwoSecTitlesGetsNoTicker`
- `existingTickerIsNotClearedByALaterUnmatchedMerge`
- `addingAWatchlistTickerBackfillsTheMatchingCompanyNode`
- `signalsByTickerReturnsSignalsMentioningTheTickeredCompany`

core-hub, `src/test/java/.../persistence/CompanyNameNormalizerTest.java`:
- `corporateSuffixesAndPunctuationAreStripped`
- `normalizationIsIdempotent`

core-hub ArchUnit (`src/test/java/.../architecture/`):
- `noRelationshipTypeOtherThanThoseInTheGraphModelIsWritten`: a scan of Cypher string constants in `persistence` finds only `TARGETS`, `USES_MECHANISM` and `MENTIONS`.

ingestion-scraper, `tests/unit/test_connector_registry.py`:
- `test_every_source_in_sources_yaml_builds_a_connector_through_the_registry`
- `test_unknown_source_type_raises_a_named_error_listing_registered_types`
- `test_api_ingest_reaches_each_registered_connector` (one parametrized case per `sources.yaml` entry, connectors faked)
- `test_publish_threshold_and_rate_limit_come_from_the_source_entry`
- `test_no_source_type_equality_branch_in_shared_modules`: an AST scan of `auspex_ingest` (excluding `connectors/`) finds no comparison of `source_type` to a string literal.

## Definition of done

```bash
cd services/core-hub && ./gradlew test integrationTest --rerun-tasks
cd services/ingestion-scraper && uv run pytest tests/unit -q --strict-markers && uv run ruff check . && uv run mypy src
```

Expected: all green; the 14 new tests above are in the reports (9 Java, 5 Python, parametrized cases counted once).

Then on the stack: `POST /ingest/pubmed` returns a `RunResult` instead of a 500.

## Notes

- `requirements.md` §9 is the authority on relationship names; the writer was wrong, not the scanner.
- The ticker match is deliberately conservative: a wrong ticker would attach another company's signals to a watchlist entry, which is worse than a missing one. Managed aliases (`specs/managed-ingestion-config.md`) cover names the SEC title doesn't match.
