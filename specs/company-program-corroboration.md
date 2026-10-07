# Company-Program Corroboration

**Status:** blocked
**Blocked by:**
1. Company-level event extraction (in progress, first wave) — `ResearchSignalEvent` must carry the event type and the company and program identifiers (company CIK or ticker where known, lead sponsor, NCT ID, drug code such as `SRP-9001`) before signals can be matched on them. Use the field names that spec lands; this spec does not add extraction fields.
2. User approval of the requirements amendment below (§4 and §9 of `docs/requirements.md`). Logged in `DECISIONS.md` 2026-10-07 FLAG "corroboration is matched on gene target, not company".

**Branch:** `feature/company-program-corroboration`

---

## Context

Corroboration today (`docs/requirements.md` §4, §9) links two signals when they share a `GeneTarget` or `Mechanism` node, come from distinct `source_type`s, and are published within 90 days of each other. The 2026-10-07 edge feasibility audit rated this event definition fatal for trading: a bioRxiv paper and a trial on DMD are not Sarepta news, and nothing maps a gene target to the stock it moves. It also found two point-in-time defects in the same component.

What exists in `services/core-hub`:
- `corroboration/CorroborationService` (interface) with one implementation, `ScheduledCorroborationService`, which delegates to `CorroborationScanner` and publishes `CorroboratedSignalEvent` to `auspex.signals.corroborated`.
- `CorroborationScanner` — Cypher `MATCH (s)-[:TARGETS|USES_MECHANISM]->(e)`, a ±90-day window (`WINDOW_SECONDS`), a degree cap (`corroboration.degree-cap`, default 500), a watermark in `corroboration_state`, and the `corroboration` table keyed on `(entity_key, participants_hash)` with supersession (§4.1).
- `CorroborationScorer` — `0.7 × diversity + 0.3 × recency`, where recency is measured against `clock.instant()`. It is called at read time by `query/SignalQueryService`. Recomputing a historical corroboration's score therefore depends on the day the code runs (audit row 13).
- `watchlist/SecTickerCache` — SEC `company_tickers.json` lookup (ticker ↔ CIK ↔ name).
- `CorroborationServiceContractTest` (abstract, `src/integrationTest`) — any `CorroborationService` implementation must pass it unmodified.
- Flyway `V1`–`V3` create the schema on an empty database (there is no legacy data to migrate).

Audit rows covered here: 4 (core-hub side), 11 and 13.

## What this builds

1. **Program graph.** `EntityNormalizer` gains company and program normalization. Every signal with a resolved company gets `(:Signal)-[:ABOUT_PROGRAM]->(:Program {key})-[:SPONSORED_BY]->(:Company)`. `Program.key` is `<company key>|<program id>`, where the program id is the drug code if present, else the NCT ID, else the literal `company` (a company-level event such as a financing). `Company` keeps merging on normalized `name` (known trap); a resolved CIK is stored as a set-if-known property with a unique constraint on non-null values, and the ticker resolved through `SecTickerCache` as of the signal's `published_date`.
2. **A second corroboration kind.** The scheduled run executes two scans and writes both into the existing `corroboration` table:
   - `GENE_TARGET` — today's scan, unchanged. Kept as context; not a trading trigger.
   - `COMPANY_PROGRAM` — signals sharing a `Program` node, distinct `source_type`s, within the window. `entity_key` is `program:<Program.key>`, so the natural key `(entity_key, participants_hash)` and supersession are unchanged.
   A `kind` column (`V4__corroboration_kind.sql`, `NOT NULL`, no default) and a `tickers` array are added. `CorroboratedSignalEvent` gains `kind` and `tickers` (additive; consumers already ignore unknown fields). Both scans stay behind `CorroborationService` — this is a second scanner inside the existing implementation, not a new implementation, so the contract test runs unmodified.
3. **Configurable window.** `corroboration.window-days` (default 90) replaces the hard-coded constant, so 7- and 30-day variants can be run as pre-registered alternatives (row 11). The Python side records which window produced a corroboration through a `window_days` column.
4. **Mechanism-only matches flagged.** A `GENE_TARGET` corroboration whose only shared entity is a `Mechanism` (AAV, CRISPR) carries `mechanism_only = true`. Trading consumers exclude these (row 11).
5. **Degree-cap report.** Each scan logs and counts (`auspex.corroboration.entities.skipped.total`, tagged by label) the entities skipped by the degree cap, and `GET /api/v1/corroborations/skipped-entities` lists them with their degree. The audit asks whether core targets such as DMD are silently skipped (row 11).
6. **Point-in-time score.** `CorroborationScorer.score(distinctSourceCount, corroboratedAt, asOf)` measures recency against `asOf`, never the wall clock, and the `Clock` dependency moves out of the scorer. `SignalQueryService` (the only caller, which scores at read time) passes an explicit `asOf`: the new optional `as_of` query parameter on the corroboration endpoints, defaulting to now for live reads. A backtest querying with `as_of` gets the same score on any run date (row 13).

## Out of scope

- New extraction fields or prompt changes (company-level event extraction spec).
- Typed-event hypotheses and their registration (pre-registration work, first wave).
- Changes to how the backtesting module builds events from corroborations (backtest look-ahead fix, first wave). This spec only adds `kind`, `tickers`, `window_days` and `mechanism_only` for it to filter on.
- A Kafka Streams implementation (`specs/kafka-streams-correlation.md`).
- Dropping `GENE_TARGET` corroboration.

## Constraints

- Invariant 2: core-hub remains the sole writer to Postgres and Neo4j.
- Invariant 5: both kinds sit behind `CorroborationService`. `CorroborationServiceContractTest` must pass unmodified.
- Invariant 10: natural key stays `(entity_key, participants_hash)` per requirements §3.7.
- Invariant 12: all new Cypher and SQL use bind parameters; the ArchUnit rule covers the new classes.
- Requirements §4 window semantics are between the two signals, not against today — the configurable window keeps that.
- Write ordering Neo4j → Postgres → ack is unchanged; every new `@Transactional` is qualified.
- `MERGE (c:Company {ticker: null})` trap: never MERGE on ticker or CIK.
- Ticker resolution must be point-in-time where the data allows: a ticker reassigned after `published_date` must not attach. `SecTickerCache` only knows today's mapping, so a CIK that resolved through it is stamped `ticker_source = 'current'` and the backtest treats it as a known limitation, recorded in `DECISIONS.md`.

**Requirements amendment (do this first, in the same PR):** §4 gains a second, company-program corroboration rule and the `kind` field; §9 gains the `Program` node and `ABOUT_PROGRAM`/`SPONSORED_BY` relationships, and the typed corroboration pattern is stated per kind. Without this amendment the tests below would contradict §4 and must not be written.

## Required tests

Unit (`./gradlew test`):
- `CorroborationScorerTest.scoreIsIdenticalOnAnyRunDateForTheSameAsOf` — same inputs and `asOf`, two different system clocks → identical score
- `CorroborationScorerTest.recencyIsMeasuredAgainstAsOfNotWallClock` — `asOf = corroboratedAt + 45 days` → recency factor 0.5
- `EntityNormalizerTest.programKeyPrefersDrugCodeThenNctIdThenCompany`
- `EntityNormalizerTest.drugCodeVariantsNormalizeToOneProgram` — `SRP-9001`, `SRP 9001`, `srp-9001` → one key
- `EntityNormalizerTest.tickerResolvedFromTodaysMappingIsStampedCurrent` — CIK resolved through `SecTickerCache` carries `ticker_source = 'current'`
- `CorroborationScannerTest.windowDaysIsReadFromConfiguration` — window 7: signals 8 days apart do not match; 7 days apart do

Integration (`./gradlew integrationTest`):
- `CompanyProgramCorroborationIT.twoSourcesOnTheSameProgramProduceOneCompanyProgramCorroboration`
- `CompanyProgramCorroborationIT.sameGeneTargetDifferentCompaniesProducesNoCompanyProgramCorroboration` — DMD paper + DMD trial sponsored by an unrelated company → `GENE_TARGET` row only
- `CompanyProgramCorroborationIT.sameCompanyDifferentProgramsDoNotCorroborate`
- `CompanyProgramCorroborationIT.corroborationEventCarriesKindAndResolvedTickers`
- `CompanyProgramCorroborationIT.mechanismOnlyGeneTargetCorroborationIsFlagged`
- `CompanyProgramCorroborationIT.degreeCapSkipsAreCountedAndListed`
- `CompanyProgramCorroborationIT.corroborationRecordsTheWindowDaysThatProducedIt`
- `CompanyProgramCorroborationIT.companyNodesWithNullCikAreNotMerged` — two unrelated companies without CIK stay two nodes
- `SignalRestIT.corroborationScoreForAPastAsOfIsStableAcrossRuns` — `?as_of=` on a fixed corroboration returns the same score under two different `Clock` beans
- `CorroborationServiceContractTest` (existing, unmodified) — still green

## Definition of done

```bash
cd services/core-hub && ./gradlew test --rerun-tasks && ./gradlew integrationTest --rerun-tasks
```

Expected: 6 new unit tests and 9 new integration tests pass alongside the existing suite; `build/reports/tests/` shows a non-zero count for both tasks; the contract test file is unchanged in the diff.

Then: `docs/requirements.md` §4 and §9 amended; `services/core-hub/README.md` corroboration section updated; the degree-cap report run against the stack and its result (which watched targets exceed the cap) recorded in `DECISIONS.md`.

## Notes

- Why one implementation with two scanners rather than a new `CorroborationService`: a company-program implementation cannot pass the gene-target contract cases, and Invariant 5 forbids editing the contract test. Keeping gene-target corroboration as context also lets the backtest compare the two definitions.
- The 0.85 event-to-ticker precision gate (audit row 4 done-when) is measured on the golden set by the company-level extraction spec. This spec consumes its output and does not re-measure.
- The score is not persisted today and should stay that way: a stored recency term would reintroduce the wall-clock dependency row 13 removes.
