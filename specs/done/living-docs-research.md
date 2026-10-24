# Living docs: research and evaluation protocol

> Archived. Not authoritative: current behaviour is in docs/ (see docs/README.md).

**Status:** done
**Blocked by:**
1. `specs/docs-check-tooling.md`. It provides `python3 -m tools.docs_check` (checks A–H, J–M), `docs-check.toml` and the integration branch `feature/living-docs-integration`. None of these exist at `e51f742`.
2. `specs/living-docs-system-and-contracts.md`. It merges `docs/README.md`, `docs/system/invariants.md` (INV-1…15) and `docs/system/contracts.md` (CON IDs) into the integration branch, so this spec can cite real INV and CON numbers.
3. Owner answers. Each is appended to `DECISIONS.md` as a `CHOICE`. This spec cites the CHOICE once it exists, and the PENDING heading until then.
   - `## 2026-10-15 — Living docs — PENDING — code-done specs blocked on the Mac`. Blocking: it approves moving the six specs' merged behaviour into `docs/`.
   - `## 2026-10-15 — Living docs — PENDING — spec paths cited by hash-locked hypotheses`. Blocking: it approves the one-hop pointer for `SpecialistClassifier`.
   - `## 2026-10-15 — Living docs — PENDING — trial ledger and holdout as untracked local files`. Not blocking: the default records the requirement as `divergent`.
   - `## 2026-10-15 — Living docs — PENDING — processing time in as-of decisions`. Not blocking: until the owner's CHOICE, RES and STR carry the processing-time rule themselves. If that CHOICE adopts a sixteenth invariant, the cutover writes it (step 3) and links these IDs.
   - `## 2026-10-15 — Living docs — PENDING — defects found while scoping`. Not blocking: `divergent` rows cite it.

**Branch:** `feature/living-docs-research` (from `feature/living-docs-integration`; PR into it)
**Docs impact:**
- Creates six docs under `docs/research/`:
  - namespace RES: `market-data.md`, `universe.md`, `panels.md`, `simulation.md` and `backtesting.md`;
  - namespace EVA: `evaluation-protocol.md`.
- Modifies 10 active specs (tables in "What this builds" §4 and §5):
  - adds `Docs impact`;
  - replaces restated requirements with IDs;
  - reduces the six code-done specs to their Mac acceptance, keeping every required section.
- Appends one PENDING ratification-batch heading to `DECISIONS.md`.
- In `specs/living-docs-cutover-matrix.md`, fills:
  - the RES and EVA ID cells;
  - the `IDs` cells of the binding decisions rows this spec carries.
- Removes `research` from `[rollout] planned_domains` in `docs-check.toml`.
- Moves this spec to `specs/done/` and updates its own `TODO.md` row.
- Changes no README, no `docs/requirements.md`, no `docs/strategy-research.md`, nothing under `config/**` and no code.

---

## Context

**Repository state at `e51f742` (develop).** Read code and docs from that commit. Every path below is relative to the repo root.

**Where research requirements live today.** No single file owns them.
- **`docs/requirements.md`** says little about research:
  - §0.1 (historical instrument), `docs/requirements.md:11`;
  - §0.3 (backfill prerequisite), `:13`;
  - §4.1 (superseded corroborations kept so that a backtest can read the participant set as of a date), `:114`;
  - §6.7 (`published_date` is the only alignment timestamp), `:198-209`;
  - §8 (yfinance, fetch once to Parquet in MinIO, Stooq fallback), `:268-273`.

  Its preamble still says "No code exists" (`:3`).
- **Machine authorities:**
  - `config/hypotheses/protocol.yaml` and `h1…h12.yaml`, hash-locked in `registry.jsonl` (`services/backtesting/src/auspex_backtesting/hypothesis.py:43,156`);
  - `config/universe/rules.yaml` and `us_small_mid.yaml`, version-locked in MinIO on first build (`universe/store.py:88-103`, `RulesVersionError`);
  - `config/short_interest/finra_calendar.csv`.
- **`services/backtesting/README.md`** (226 lines): the most complete description of current behaviour. It also copies registered values (`:23`, `:118`, `:201`).
- **Archived specs** (`specs/done/`):
  - `price-finality-and-split-availability`, `market-simulation` and `realistic-cost-model`;
  - `backtest-look-ahead-fix`, `backtesting`, `performance-metrics` and `point-in-time-alignment`;
  - `evaluation-protocol`, `slow-signal-preregistration` and `cross-sectional-portfolio-backtest`;
  - `forward-check-input-validation`, `ownership-share-basis`, `hypothesis-registry` and `price-ingestion`.
- **`DECISIONS.md` `CHOICE` entries.** The Decisions table of `specs/living-docs-cutover-matrix.md` classifies each one as binding or history. The section "Research, strategy and dashboard" of that file maps every research statement to a target.
- **Six active specs whose code is merged** but which wait on their first Mac run. Their policy text is today the only home of merged behaviour:
  - `specs/point-in-time-universe.md`;
  - `specs/sec-ownership-datasets.md`;
  - `specs/short-interest-snapshots.md`;
  - `specs/catalyst-date-panel.md`;
  - `specs/filing-text-change-score.md`;
  - `specs/holdings-composite-score.md`.
- **`docs/strategy-research.md`**: rationale (H1–H12 reasoning, triage, the slow-signal table). It stays non-normative and in place: it is in `frozen_paths`, and `market_sim/costs.py:13` cites it. Its banner and its link edits belong to `specs/legacy-docs-retirement.md`. This spec does not edit it.

**Paths cited by hash-locked files.** These four files are never moved or renamed:
- `config/hypotheses/h9.yaml:18` cites `specs/sec-ownership-datasets.md#SpecialistClassifier`.
- `h11.yaml:8` cites `specs/clinicaltrials-version-diffs.md`.
- `h12.yaml:8` cites `specs/catalyst-date-panel.md`.
- `config/universe/rules.yaml:1` cites `specs/point-in-time-universe.md` in a comment.

`services/backtesting/tests/unit/test_preregistered_protocol.py:440` asserts the h9 string.

**`SpecialistClassifier` is not a Markdown heading.** It is list item 2 of "What this builds" (`specs/sec-ownership-datasets.md:29`). GitHub therefore generates no `#SpecialistClassifier` anchor today. The pointer in §3 adds an explicit anchor.

**Known divergences between approved intent and code.** Each one becomes a `divergent` verification row, never a silent restatement of the code.
- **Trial ledger and holdout records are untracked local files:**
  - `config/hypotheses/trials/<id>.jsonl` (`evaluation/ledger.py`);
  - `config/hypotheses/holdout/<id>[.<use>].json` (`portfolio/verdict.py:308-336`).

  Only `trials/.lock` is ignored (`.gitignore:52`), and nothing commits, backs up or shares the files. The event holdout has no persistent read record (`evaluation/results.py:240-270`).
- **`hypothesis.run_backtest`** (`hypothesis.py:190-230`) reserves cells, but it does not call `EvaluationProtocol.admit()` and does not refuse a `suspended` hypothesis. This is item D F3 of `## 2026-10-15 — Living docs — PENDING — defects found while scoping`.
- **`scripts/fetch_prices.py` → `PriceFetcher`** (`prices/price_fetcher.py:19-45`) writes snapshots with no settle filter and no `adjusted_through`. `market_cap_usd` then raises for that ticker forever (`universe/market_cap.py:36`).
- **Portfolio grid checks are missing:**
  - `PortfolioRule.from_hypothesis` (`portfolio/rules.py:76-110`) does not check that the cell is in `trial_grid`;
  - nothing checks a cell's `floor` axis against `--score-version`;
  - `--filter-score` applies the H10 filter without reserving its cells.
- **`CurrencyConverter.eur_per_usd(d)` uses day d's close** for an order at d's open (`market_sim/fx.py:17-19`). No approved source states the rule, so it goes to the ratification batch.

**What does not exist yet:**
- `docs/research/`;
- `tools/docs_check/` and `docs-check.toml`;
- `AGENTS.md`.

## What this builds

When this spec merges into the integration branch, every approved research and evaluation rule has one owner file and an ID. The six code-done specs keep every required section, cut down to what still has to happen on the Mac.

### 1. Six living docs

**Template** (`specs/living-docs-cutover-design.md` §5.1). Each doc has:
- **A header line:** `Domain: RES` (or `EVA`) `· Code: <paths> · Last reviewed against: develop @ <rollout base SHA>`.
- **Required H2s:** `Scope`, `Requirements`, `Verification` and `Retired requirements` (the last stays empty).
- **Optional H2s, used where they have content:** `Machine-readable authorities`, `Known traps` and `Rationale`.
- **Each requirement:** `<a id="RES-NNN"></a>**RES-NNN**` followed by one present-tense, testable statement.
- **The verification table:** the first table under `## Verification`, with columns `ID | Source | Verified by | Status`.
  - **Status** is one of `tested`, `enforced`, `untested`, `divergent` or `pending-decision`.
  - **Verified by:** a `tested` row cites `path::name` of a test read in the code.
  - **Decision citations:** a `divergent` or `pending-decision` row cites an existing `DECISIONS.md` heading.

**Writing rules:**
- **Numbering.** Allocate IDs in file order with `python3 -m tools.docs_check --next RES` and `--next EVA`.
- **Decision sources.** A `Source` cell that rests on a decision contains that decision's heading text verbatim, after `## `. Check M compares that text.
- **Values.** A value owned by a machine authority is named by file and key (`protocol.yaml` `promotion.holdout_months`), never copied.
- **Wording.** The lists below give the content each file must cover. The wording is the writer's, checked against the code.

**`docs/research/market-data.md` (RES).** Code: `services/backtesting/src/auspex_backtesting/prices/`, `api.py`, `stack_bootstrap.py`.
- **Snapshots.**
  - One OHLCV Parquet snapshot per ticker in `auspex-prices`, fetched from Yahoo, with Stooq as the fallback.
  - A bar, once written, is never rewritten.
  - A refresh only appends bars after the last stored one.
  - Sources: requirements §8; ``## 2026-10-07 — Startup data — CHOICE — data fills itself on `up`; prices refresh daily``.
- **Settled bars only.**
  - A session bar is stored after its NYSE close plus the settle delay, early closes included.
  - FX bars, and bars on non-session days, settle after their UTC day ends.
  - An unfinished bar is dropped and fetched again.
  - Sources: archived `price-finality-and-split-availability`; `## 2026-10-10 — Price finality and split availability — CHOICE — edges the spec leaves open`.
- **Overlap rule.**
  - A refresh appends only when the response repeats the last stored bar within the tolerance.
  - A mismatch, or a non-empty response without that bar, raises `SnapshotDiscontinuityError` and writes nothing.
  - An empty response appends nothing and is not an error.
  - Rebuilding a snapshot is a deliberate delete-and-refetch, never scheduled.
- **Share basis.** `adjusted_through` records the first-download date. The snapshot's closes are on that day's share basis.
- **Split histories.**
  - Each ticker's history is `available`, `confirmed_empty` or `unavailable`, and vouches only up to `covered_through`.
  - A read beyond `covered_through` fetches again.
  - `unavailable` is never read as "no splits".
- **What every refresh covers.** The protocol's benchmark ticker and the EUR/USD pair. Name the code (`price_refresher.py` `price_universe`); do not copy the list.
- **History start.** A snapshot is first fetched from `PRICE_HISTORY_START` (the value lives in `.env.example`). The schedule never extends it backwards.
- **Every snapshot carries `adjusted_through`.** Status `divergent`: `scripts/fetch_prices.py` writes without it (`prices/price_fetcher.py:19-45`). Cite `## 2026-10-15 — Living docs — PENDING — defects found while scoping`.
- **HTTP surface.**
  - `POST /prices/refresh`.
  - `POST /universe/build`, which answers 409 on a configuration conflict.
  - `GET /health`.
  - Out of scope here, with links: the DAG schedule (`docs/operations/orchestration.md`) and the metric catalogue (`docs/operations/observability.md`).
- **Known traps:**
  - Yahoo `auto_adjust` also adjusts dividends;
  - Stooq uses its own symbols;
  - `YFRateLimitError` blocks for hours.

**`docs/research/universe.md` (RES).** Code: `universe/`, `backtest/membership.py`, `dags/universe_build.py`, `scripts/build_universe.py`. Machine authorities: `config/universe/rules.yaml`, `us_small_mid.yaml`.
- **One rules file per universe.**
  - Biotech uses `rules.yaml`, stored under `universe/{version}/`.
  - Any other universe uses `<universe_id>.yaml`, stored under `universe/<id>/{version}/`.
  - An all-digit id is refused, and no code names a universe.
  - Source: `## 2026-10-15 — Filing text change score — CHOICE — how the panel reads EDGAR and where the second universe lives`, items 2 and 6.
- **Version lock.**
  - The rules file is pinned in MinIO on its version's first build.
  - A changed file under a built version is refused (`RulesVersionError`).
  - Changing a built universe means a new version, which is a new trial.
  - Sources: the `rules.yaml:1-3` comment; `point-in-time-universe`, What this builds item 1.
- **Known before the rebalance.** The rebalance is the first NYSE session of the month. A member is admitted only on data public before that session opens:
  - share counts filed strictly before it;
  - closes strictly before it;
  - never period-end dates.

  Source: `## 2026-10-08 — Point-in-time universe — CHOICE — how the monthly list is derived from free SEC data`, item 1.
- **Listing spans, exit reasons and tickers.** Items 2–4 of the same CHOICE:
  - `ticker_source` is `current`, `filing` or `unresolved`;
  - tickers before 2019 come from the XBRL instance name (`## 2026-10-09 — Point-in-time universe — CHOICE — one universe from 2014, backfill scope from its own start`, item 3);
  - prices more than 30 days after an exit belong to a reused symbol and are discarded.
- **Unknowns.**
  - A rule that cannot be evaluated does not exclude the company (item 5).
  - A month whose market caps need an unknown split history is not written. The next build retries it (`split_unavailable`).
- **Window and history.**
  - The window comes from the rules file.
  - A `PRICE_HISTORY_START` later than the liquidity lookback before the window is refused (409).
  - Source: the 2014 CHOICE, item 2.
- **Storage.**
  - Monthly snapshots are written once (`SnapshotExistsError`).
  - `listings.parquet` and `coverage.json` are rewritten on every build. Backtests read exits and coverage from the latest one.
  - State this as current behaviour. Reproducibility is EVA's input-manifest requirement.
- **Backfill scope.** `backfill_scope.yaml` is the union of members from `BACKFILL_SCOPE_START`.
- **The backtest universe is rules-based and pre-registered.** Live ingestion scope (the watchlist) never defines it. Source: `## 2026-10-08 — Control-surface scoping — CHOICE — the watchlist is the single source for tracked tickers and terms`, item 4.
- **Accepted limitations:**
  - classification uses the current SIC code only;
  - a renamed issuer carries its current ticker.
- **Incomplete price history.** Members stay in the snapshot with `price_coverage = none | partial`. The exclusion rule and the bound are in `backtesting.md`.
- **SEC access.**
  - The build uses the bulk archives.
  - Per-company lookups are paced and stop on 403/429.
  - Link the SEC rules in `docs/ingestion/connectors.md` and the request budget in `docs/operations/orchestration.md`; do not restate them.

**`docs/research/panels.md` (RES).** Code: `ownership/`, `short_interest/`, `catalysts/`, `filings/`, `scores/`. Machine authorities: `h9.yaml`, `h10.yaml`, `config/short_interest/finra_calendar.csv`.

*Shared contract, stated once.* Sources: `## 2026-10-07 — Edge research scoping — CHOICE — ownership and insider data are snapshots, not connectors`; `## 2026-10-07 — Second-wave specs — CHOICE — short interest is a market-data snapshot, not a connector`.
- Every row has a known-at instant, never a period or event date.
- Reads are `as_of`.
- Stores are append-only or write-once.
- Missing data is missing with a reason, never zero or carried forward.
- Each document is fetched once (the requirements §8 pattern).
- Panels hold universe companies only.
- Panels are snapshots in `auspex-prices`, not connectors.

*Ownership:*
- **Acceptance time.** `filing_accepted_at` is 22:00 US Eastern on the filing date (`## 2026-10-09 — SEC ownership datasets — CHOICE — acceptance time from a filing date`). Daily Form 4 rows carry their real acceptance time.
- **Counting rules.** The 13F report as of a date, the CUSIP→CIK mapping, insider rows and offering participation follow `## 2026-10-09 — SEC ownership datasets — CHOICE — how filings, amendments and trades are counted`, items 1 and 3–5.
  - Unmapped CUSIPs are counted, never dropped.
  - Daily rows fill a quarter until its data set exists. The data set is then preferred, and any disagreement is reported.
  - Data sets keep SEC's labels.
- **`SpecialistClassifier`.** This ID is the target of the frozen pointer in §3.
  - It states the full rule: item 2 of that CHOICE, plus the classifier paragraph at `specs/sec-ownership-datasets.md:29` at the integration base.
  - Its thresholds are read only from the registered `h9.yaml` (`components.specialist_13f_ownership.thresholds`).
  - An unregistered or edited file is refused (`## 2026-10-09 — SEC ownership datasets — CHOICE — specialist thresholds have one source, the registered H9`).
  - The rule that the specialist list is derived from filings and never hand-made comes from the FLAG `## 2026-10-07 — Edge research scoping — FLAG — a hand-made specialist fund list is look-ahead`.
- **Share basis.** The share basis and the four missing-reasons come from archived `ownership-share-basis`.
- **Input times.** `specialist_ownership_known_at` and `net_insider_buying_known_at` report the input times.

*Short interest:*
- **Known at.** A record is known from the FINRA publication date, by the end of that day, never from the settlement date.
- **Publication dates.** They follow FINRA's rule, and rows in `finra_calendar.csv` win (`## 2026-10-10 — Short interest snapshots — CHOICE — publication dates from FINRA's rule, published rows win`).
- **`days_to_cover`.** The exact ratio; `None` at zero volume. An unreported ticker is stored `reported=false` (absent, not zero).
- **Storage.** Periods are appended and never rewritten.
- **Derived share and change.** On one split basis, or missing with a reason (`## 2026-10-11 — Short interest snapshots — CHOICE — short interest share and change on one split basis`).
- **History start.** `SHORT_INTEREST_HISTORY_START` in `.env.example`.

*Catalysts.* Source: `## 2026-10-09 — Catalyst date panel — CHOICE — how documents become rows`.
- **Sources and known-at times.**
  - PDUFA dates come from phrase rules over 8-K Item 7.01/8.01 Exhibit 99.1, and are known at acceptance.
  - AdCom meetings come from Federal Register notices, and are known at 06:00 Eastern on the publication date.
- **Precision** is kept as written: `day`, `month`, `quarter` or `half`.
- **Revisions.** A revision is a new row. `as_of` returns the latest row per alias.
- **Unmatched notices** are stored without a CIK and counted.
- **Cancellations** are counted, not applied.
- **Storage.** Documents are kept under `catalyst-documents/`.
- **Inputs.** `as_of` and `binaries_between` take aware datetimes.

*Filing text (H10).* Sources: the 2026-10-15 Filing text CHOICE above; `specs/filing-text-change-score.md` items 0–5 at the integration base, approved by the code-done CHOICE.
- **Index.** Stored per finished quarter, with membership applied at use.
- **Filings cut.** Originals are cut and amendments are counted. Item 1A cutting follows the heading rules, and statuses and reasons are kept.
- **Special statuses.** `no_change_statement` scores 0. `not_provided` is missing.
- **Comparison filing.** Same form family, period one year earlier within the stated tolerance, accepted earlier.
- **Score.** Change = 1 − cosine of term frequencies. It is known at the later filing's acceptance.
- **Monthly read.** The latest score accepted before the open within the lookback, with `score = −change`.
- **Snapshots.** One snapshot set per universe (version suffix). A snapshot is written only after its rebalance day.
- **SEC refusal.** An SEC refusal stops the run before scoring.

*H9 holdings composite.* Source: `## 2026-10-15 — Holdings composite score — CHOICE — where the spec left the H9 score open`.
- **Inputs.** Every parameter comes from the registered `h9.yaml`. Inputs are read as of the rebalance session's open.
- **Floor.** The floor comes from the universe snapshot, and an unknown value counts as under it. The `no_floor` cells get their own version.
- **Missing components.** The component missing-rules apply. There is no carry-forward.
- **Ranking.** The rank pool is the scored names. A name needs at least two components.
- **`known_at_max`** is the latest input time.
- **Variant.** The variant is chosen from coverage dates only.
- **Snapshots** are written once per (version, floor, date). The coverage report includes rank correlations.

*Known traps:*
- **No panel is refreshed by the stack.** Sources: `## 2026-10-09 — SEC ownership datasets — FLAG — panels are refreshed by a script, not a DAG`; `## 2026-10-09 — Catalyst date panel — FLAG — not kept current by the stack`. The refresh is proposed in `specs/slow-signal-data-refresh.md`. Do not describe it as current.
- **Test fixtures follow documented layouts, not real files.**
- **Two planned catalyst sources.** `catalyst-date-panel` (phrase rules, merged) and `catalyst-calendar` (LLM-based, not built) are both planned. Only the panel exists.

**`docs/research/simulation.md` (RES).** Code: `market_sim/`. Values: the cost variables in `.env.example`, named, never copied. This file owns the cost semantics that `market_sim/costs.py:13` attributes to `docs/strategy-research.md`; note this under Rationale.
- **`MarketCalendar`** gives NYSE sessions in UTC.
- **`FillModel`:**
  - enters at the open of the date it is given, and exits at the close;
  - never shifts entry dates (`## 2026-10-07 — Market simulation — CHOICE — FillModel does not shift entry dates`);
  - fills a gap through a stop at the open;
  - fills a touched stop on a caller-flagged binary day at the low (long) or the high (short).
- **`CostModel`.** Sources:
  - `## 2026-10-07 — Realistic cost model — CHOICE — per-ticker spread, FX fee, volume cap, gap-through stops`;
  - the defaults of `## 2026-10-08 — Edge research scoping — CHOICE — quarterly banded rotation; catalysts as a guard, not a trigger`;
  - `## 2026-10-11 — Cross-sectional portfolio backtest — CHOICE — how the engine reads the spec`, item 11.

  It covers:
  - commission on IBKR fixed or tiered pricing, plus tiered pass-through fees;
  - TOB;
  - the spread, from the Abdi–Ranaldo estimator over sessions strictly before entry: a negative estimate reads as zero, the result is floored at the minimum half-spread, and a flat fallback applies when there is no estimator;
  - an FX fee per leg;
  - a flat borrow fee;
  - a minimum ticket of the minimum commission ÷ the 1% commission cap.
- **Volume cap.** A fraction of ADV over sessions before entry.
- **FX conversion.** `fx_rate` is EUR per USD, and `eur_per_usd = 1 / EURUSD close`. Source: ``## 2026-10-07 — Market simulation — CHOICE — PositionSizer `fx_rate` is EUR per USD``.
- **FX rate known before the order.** The rate used for an order is a close known before that order. This goes to the ratification batch, because the code uses the same day's close (`fx.py:17-19`).
- **`TradableUniverse`** validates snapshots over membership spans.
- **`services/strategy` imports these classes as a path dependency and never copies them.** Source: ``## 2026-09-20 — Strategy layer session 2 — CHOICE — New `services/strategy/` service (not extending backtesting)``. STR links here.

**`docs/research/backtesting.md` (RES).** Code: `alignment/`, `backtest/`, `metrics/`, `portfolio/` (engine, rules, sizing, guard, scores, report).

Scope note: the event path is parked while H1, H4 and H6 are `suspended`. Read the status from `h*.yaml`; do not copy it.
- **Backfill ordering gate.** The LLM historical backfill does not start until the H11 and H12 diagnostics have been read and show that catalyst windows or registry edits carry return.
  - Source: `## 2026-10-08 — Edge research scoping — CHOICE — two non-LLM panels before the LLM backfill` ("the LLM backfill now waits until these diagnostics show…").
  - Status `untested`: it is a process gate. The gate's place in `specs/historical-backfill.md` Blocked by belongs to `specs/living-docs-ingestion.md`, which links this ID.
- **Processing time never decides known-at.**
  - Alignment uses only `published_date`, or `corroborated_at` for corroborations.
  - Joining on a processing-time field raises (`alignment/aligner.py:10,32`).
  - Sources: requirements §4.1 and §6.7; `## 2026-09-20 — Strategy layer session 2 — CHOICE — Strategies never see ingested_at or extracted_at; InputHealthMonitor handles model downtime`.
  - This RES requirement carries the rule. The sixteenth invariant does not exist during this spec: nobody writes it before the owner's CHOICE on "processing time in as-of decisions", and if that CHOICE adopts it, the cutover writes it (step 3).
- **Entry timing.** Source: `## 2026-10-07 — Backtest look-ahead fix — CHOICE — entry and holding-window timing`.
  - Entry is the first NYSE session whose open is after the timestamp.
  - A date-only timestamp is known after that day's close.
  - Windows are in calendar days, from the entry open to the close of `next_trading_day(entry + N)`.
  - A missing row gives `None`.
  - For ratification: a genuine `00:00:00 UTC` timestamp is treated as date-only.
- **One event per corroboration.**
  - Replay follows `## 2026-10-07 — Backtest look-ahead fix — CHOICE — one backtest event per corroboration, not per superseding record`.
  - The full-variant weight uses the participants known at the event.
  - Superseded records stay readable as of a date (requirements §4.1).
  - For the corroboration window, link `docs/core-hub/corroboration.md`; do not restate it.
- **With a universe.**
  - Events outside the entry month's membership are dropped and counted.
  - Window rules 1–6 of `## 2026-10-08 — Point-in-time universe — CHOICE — windows the prices do not cover` apply.
  - The delisting bound and the `survivorship_gap = material` threshold apply, as `specs/point-in-time-universe.md` "Members with incomplete price history" states them at the integration base.
- **Portfolio engine.** Source: `## 2026-10-11 — Cross-sectional portfolio backtest — CHOICE — how the engine reads the spec`, items 1–8.
  - **`ScoreSnapshot` contract.** Path, columns, and `known_at_max` before the rebalance open, validated on write and on read. `ScoreStore.write` refuses to overwrite.
  - **Decisions.**
    - Decision dates, cadences and selection rules, with hold bands.
    - Ties are broken by CIK.
    - Fills at the next open, sells first, never borrowing.
  - **Sizing.**
    - `EqualRiskSizer` is capped at the protocol's `max_position_pct`.
    - The remainder is cash, never renormalised (`## 2026-10-10 — Consolidated code, strategy and BV audit — CHOICE — what becomes specs, what does not`, item 4).
    - Fewer than `min_names` raises.
  - **Catalyst guard.** The four `CatalystGuard` modes. Missing data is counted, never treated as clear.
  - **Delisting bound** in the portfolio.
  - **Result fields**, listed as outputs.
  - **Determinism.** Identical inputs give an identical result.
- **The score version a run reads matches its cell's `floor` axis.** For ratification, status `pending-decision`. Today `run_portfolio_backtest.py` relies on the operator.
- **Variant reporting.** Link EVA; do not restate it.

**`docs/research/evaluation-protocol.md` (EVA).**
- Code:
  - `hypothesis.py`, `protocol.py`, `evaluation/`;
  - `portfolio/verdict.py`;
  - `scripts/register_hypothesis.py`, `scripts/run_portfolio_backtest.py`.
- Machine authorities: `config/hypotheses/protocol.yaml`, `h*.yaml`, `registry.jsonl`.
- Values are cited by key only:
  - `abnormal_return.*`, `inference.*`;
  - `trials.*`, `families.*`;
  - `portfolio_inference.*`, `promotion.*`;
  - `sizing.*`, `instruments.*`;
  - `kill_criteria[*]`, `portfolio_kill_criteria[*]`.

*Registration:*
- The hash lock is a raw-byte SHA-256 per file. An unregistered or edited file is refused.
- Shape validation follows the event vs portfolio fields.
- The registry is append-only from the first evaluation on. Source: `## 2026-10-09 — Slow-signal pre-registration — CHOICE — one protocol and one version per hypothesis, H9–H12 registered`. The one-time reset is history.
- A family is named by its hypothesis, and an unlisted family has no budget. Source: the `protocol.yaml:33-34` comment, enforced by `admit()`.
- Instruments are ceilings. Enabling one is a re-registration, never an `.env` edit. Source: the `protocol.yaml:84` comment.

*Research config is read-only (owner):*
- **Covered:**
  - hypotheses and `protocol.yaml`;
  - the strategy registry;
  - the model registry and gate records;
  - universe rules.
- **Rule:** no UI, runtime or API path writes them. They change only through a dated re-registration or edit in the repo, with a `DECISIONS.md` entry.
- **Source:** `## 2026-10-08 — Control-surface scoping — CHOICE — research config is read-only in the dashboard`.
- **Links:** DSH and EXT link here.
- **Known trap:** `StrategyRegistry._check_version` writes `config/strategies/versions/` when given `versions_dir` (`services/strategy/src/auspex_strategy/registry.py:134-142`).

*Roles and status.* Source: `## 2026-10-07 — Pre-registration — CHOICE — hypothesis triage; versions 2 registered` (the role and status rule; the version facts are history).
- `suspended` is refused.
- Diagnostic and descriptive hypotheses are never counted or promoted.
- Filters count, but are never promoted.
- Each use is validated and promoted on its own.

*The admission gate:*
- `admit()` runs before any evaluation reads returns. It checks:
  - the family budget;
  - the role allowed in the family;
  - the instrument ceilings.

  Source: `## 2026-10-09 — Slow-signal pre-registration — CHOICE — details the spec left open`, item 7.
- `hypothesis.run_backtest` is `divergent`. Cite `## 2026-10-15 — Living docs — PENDING — defects found while scoping`, item D F3.

*Trial ledger.* Sources: `## 2026-10-10 — Consolidated code, strategy and BV audit — CHOICE — what becomes specs, what does not`, item 3; `## 2026-10-10 — Evaluation protocol — CHOICE — the raw-return backtest reserves trial cells too`.
- Cells are counted across the family (`## 2026-10-07 — Pre-registration — CHOICE — trials counted as cells across the hypothesis family, budget 64`; budgets are now per family).
- The budget check and the reservation are one step under a lock.
- Cells are reserved before any return is read. A failed run still counts.
- A torn final line is dropped. Any other bad line stops reservations.
- **Off-grid cells are refused.** `tested` for event runs; `divergent` for portfolio runs (`portfolio/rules.py:76-110`), citing the defects-found PENDING heading.
- **The H10 filter use's cells are reserved when the filter is applied.** `divergent`, citing the same heading. The source is the locked `protocol.yaml:40-42` comment.

*Durability.*
- The trial ledger and the holdout read records are durable and shared across every checkout and machine. A fresh clone can neither reset a family's count nor re-read a holdout.
- Status `divergent`, citing `## 2026-10-15 — Living docs — PENDING — trial ledger and holdout as untracked local files` (or its CHOICE).
- Sources:
  - `protocol.yaml` `portfolio_inference.holdout_reads`;
  - `## 2026-10-07 — Pre-registration — CHOICE — evaluation protocol and kill criteria locked before the backfill` ("the holdout and the trial count are spent").
- Durable storage is decided with `specs/research-input-archive.md`. Do not describe it here.

*Event evaluation.* Source: `## 2026-10-10 — Evaluation protocol — CHOICE — how the event evaluation reads the spec`, items 1–7.
- The deflated Sharpe is a probability, computed on per-observation Sharpe with the family count after the run's reservation.
- Horizon = CAR[+1, +h], with entry at `next_trading_day(corroborated_at + delay)`.
- The model is `## 2026-10-07 — Pre-registration — CHOICE — market-model abnormal returns against XBI with two-way clustered errors`, with values in `abnormal_return.*`.
- In-sample is everything before the holdout months.
- Walk-forward is a reported validation, never used for promotion. This goes to the ratification batch.
- The clustering fallback.
- The net return definition.
- `N_BOOTSTRAP` is required from `.env`.

*Entity-only vs full variant (owner).*
- Every result built on corroborations reports the entity-only variant beside the full variant.
- A full-variant result is not interpreted before the leakage canary passes (link `docs/ingestion/extraction.md`).
- Sources:
  - `## 2026-09-19 — Phase 4 — FLAG (v2, supersedes earlier Phase 4 note) — entity-only variant required in all Phase 4 output` (a FLAG with an action, absorbed as a binding rule and recorded as such in the Source cell);
  - archived `backtesting` and `performance-metrics`.

*Portfolio evaluation.* Sources: `## 2026-10-11 — Cross-sectional portfolio backtest — CHOICE — how the engine reads the spec`, items 8–10; `## 2026-10-10 — Pre-launch spec audit — CHOICE — portfolio verdict and the remaining blockers`, item 1.
- **Order:**
  1. manifests;
  2. the holdout-read check;
  3. reserve;
  4. in-sample at every tier, plus the companion run;
  5. the verdict at the smallest tier;
  6. the holdout, once.
- The verdict applies `portfolio_kill_criteria` and promotes only the primary cell.
- `HoldoutRecord` is created exclusively.
- One cell is reserved however many tiers run.

*Input manifests:*
- An admissible result (a final run, a holdout read, a promotion) needs a manifest for every snapshot it reads.
- Until one exists, every final run is refused (`NoInputManifests`, `InputsNotPinnedError`).
- Builds made before then are disposable.

*Forward check:*
- `forward_check_branch` gives the event or the portfolio branch.
- The portfolio branch is evaluated per tier. Malformed inputs give `invalid`, not a kill (archived `forward-check-input-validation`).
- No real capital goes in until a forward check passes at a tier. Sources:
  - `## 2026-10-07 — Second-wave specs — CHOICE — paper trading gates capital, run at several sizes`;
  - `## 2026-10-08 — Edge research scoping — CHOICE — portfolio paper-trading pass rule`.

*Known traps:*
- **Result-affecting parameters outside the registered files:**
  - the cost variables in `.env`;
  - `N_BOOTSTRAP` vs `inference.bootstrap_draws`;
  - the walk-forward lengths;
  - the delisting bound;
  - the survivorship threshold in metrics;
  - the H10 date tolerances.
- **The hash is over raw bytes,** so a whitespace edit is a new registration.

### 2. One ratification batch

Append one entry to `DECISIONS.md`: `## <date> — Living docs — PENDING — research ratification batch`. In this spec, `research ratification batch` in a Source cell is shorthand: the doc's verification `Source` cell carries the full citation `` `## <date> — Living docs — PENDING — research ratification batch` `` with the date the entry is appended, as check K requires for `pending-decision` rows. It lists every RES and EVA requirement whose only source is code, a README or a config comment. Each such requirement is written with:
- Source `research ratification batch`, plus the code path;
- status `pending-decision`.

The batch holds at least:

| Requirement | Only source |
|---|---|
| A genuine `00:00:00 UTC` timestamp is treated as date-only | `alignment/aligner.py:46-63` |
| The FX rate for an order is a close known before the order | none (`fx.py:17-19` does otherwise) |
| A portfolio run's score version matches its cell's `floor` axis | `run_portfolio_backtest.py` docstring |
| Every refresh includes the protocol benchmark and the EUR/USD pair | `price_refresher.py:34,59` |
| The price service's `GET /health` route | `api.py:68-99` |
| Walk-forward segments are reported, never used for promotion | `evaluation/walk_forward.py`; `services/backtesting/README.md:119` |

Before writing the batch, add any further code-only requirement found while checking the code, and list it in the PR body.

The owner records the approval as `## <date> — Living docs — CHOICE — research ratification batch`. Once that CHOICE exists, the cutover (step 3) flips these rows to their real status. This spec appends neither the CHOICE nor the flip.

### 3. The SpecialistClassifier pointer

The `SpecialistClassifier` text moves to its RES ID in `panels.md`. In `specs/sec-ownership-datasets.md`, list item 2 of "What this builds" (`:29`) is replaced in place by exactly one line:

```markdown
2. <a id="SpecialistClassifier"></a>**`SpecialistClassifier`** — defined in RES-0xx ([docs/research/panels.md#RES-0xx](../docs/research/panels.md#RES-0xx)). This item is cited by the registered H9 hypothesis (`config/hypotheses/h9.yaml:18`); do not rename or remove it.
```

`RES-0xx` is the real number. The anchor makes the hash-locked fragment resolve, which it does not today.

These stay untouched:
- `config/hypotheses/h9.yaml`;
- `registry.jsonl`;
- `test_preregistered_protocol.py:440`.

### 4. The six code-done specs reduced to their Mac acceptance

Each of the six specs keeps every field and section that `specs/README.md` and check E require. Each section is reduced to a pointer and the remaining Mac work.

| Section | New content |
|---|---|
| Title, `Status`, `Blocked by`, `Branch` | unchanged |
| `Docs impact` | "None: behaviour approved in RES-xxx…RES-yyy; the remaining work is acceptance on the stack machine." |
| `## Context` | Two to four lines: the code is merged at the integration base, the RES IDs that define it, and the first-run step that runs it. |
| `## What this builds` | One line per former item, each naming the RES ID that now defines it (at most eight lines). In `sec-ownership-datasets`, item 2 is the §3 pointer line. |
| `## Out of scope` | Kept as is. Out-of-scope lines are not behaviour. |
| `## Constraints` | One line per former constraint, as an ID citation: INV-6, INV-9, the RES fetch-once and as-of IDs, and the SEC rules in `docs/ingestion/connectors.md` (a file link where no ING ID exists yet). |
| `## Required tests` | One line: "Merged. Each test is cited in the `Verified by` cell of its RES ID. Definition of done reruns them." This is followed by the Mac acceptance checks from the table below, each as a named check. |
| `## Definition of done` | The existing pytest command and expected count. Under "On the stack machine": the run, the coverage record, the hand check, the files to commit, and the `DECISIONS.md` PENDING heading each one closes. |
| `## Notes` | Kept only for traps about the run. |

`Progress` paragraphs are history and are removed. Their facts are already in `DECISIONS.md`. A fact found only there moves to RES `Rationale` or is listed in the PR body.

**Kept in place, never renamed:**
- `specs/point-in-time-universe.md`;
- `specs/sec-ownership-datasets.md`;
- `specs/catalyst-date-panel.md`.

| Spec | Remaining acceptance (from its current Definition of done) | RES docs it cites |
|---|---|---|
| `point-in-time-universe` | Run the first build from 2014-01 on the Mac (`specs/first-run-on-stack-machine.md` step 3). Record in `DECISIONS.md` the member counts, the delisted count and the coverage split 2014–2018 / 2019 on. Commit `config/universe/backfill_scope.yaml`. Closes `## 2026-10-08 — Point-in-time universe — PENDING — SEC bulk URLs and first build on the stack`. | `universe.md`; `backtesting.md` (with-universe rules) |
| `sec-ownership-datasets` | Run `scripts/fetch_ownership.py` from 2013. Record the first data set of each kind, issuer coverage, the unmapped CUSIP share and the three layout points. Closes `## 2026-10-09 — SEC ownership datasets — PENDING — first backfill on the stack machine`. | `panels.md` (ownership, `SpecialistClassifier`) |
| `short-interest-snapshots` | Get the FINRA credential (`docs/PREREQUISITES.md`) and run the first fetch. Record the first settlement date, the empty periods and the gaps. Closes `## 2026-10-10 — Short interest snapshots — PENDING — first fetch on the stack machine`. | `panels.md` (short interest) |
| `catalyst-date-panel` | Build the panel from 2014. Record coverage and a 30-hit hand check, with the precision rule (≥ 0.9, one tightening). Closes `## 2026-10-09 — Catalyst date panel — PENDING — sources unreachable from the cloud session`. | `panels.md` (catalysts) |
| `filing-text-change-score` | Build the panels for both universes. Record coverage and a 20-filing hand check before scoring. | `panels.md` (filing text); `universe.md` (second universe) |
| `holdings-composite-score` | Compute scores from 2014, floor and no-floor. Record coverage and the variant used in `DECISIONS.md`. | `panels.md` (H9) |

Stale lines in the current Definitions of done are dropped, not carried over, because each is owned elsewhere or already done:
- "`CLAUDE.md` naming table describes `auspex-prices`…" (`point-in-time-universe.md:123`, `short-interest-snapshots.md:66`). The naming table is SYS (`docs/system/overview.md`), and the bucket description is already current;
- "`.env.example` gains…".

**Root `CLAUDE.md` section citations.** Repoint every remaining citation of a root `CLAUDE.md` section in the ten edited specs to the doc that owns the rule. Use the ID if it exists, else a file-level link. Known at `e51f742`:

| Citation | Repoint to |
|---|---|
| `filing-text-change-score.md:16` "the SEC traps in root `CLAUDE.md`" | SEC traps in `docs/ingestion/connectors.md` (Known traps) |
| `slow-signal-data-refresh.md:22` "Root `CLAUDE.md` ("Where work can run")… data that must stay current belongs in an Airflow DAG" | the no-hand-run-scripts rule in `docs/operations/topology.md`, and the DAG rule in `docs/operations/orchestration.md` |
| `slow-signal-data-refresh.md:61` "SEC traps (root `CLAUDE.md`)" | SEC traps in `docs/ingestion/connectors.md` |
| `point-in-time-universe.md:123`, `short-interest-snapshots.md:66` (naming table) | dropped with the stale Definition-of-done lines above |

Before writing, find any others with `grep -n 'CLAUDE\.md' <the ten specs>`. None of these edits touches the `SpecialistClassifier` anchor, and none renames a frozen path.

### 5. The other four active research specs

| Spec | Edit |
|---|---|
| `clinicaltrials-version-diffs` | `Docs impact`: adds RES IDs for the registry-history panel (`RES-new`, `panels.md`). Constraints: "Point-in-time…" becomes the shared panel ID plus a link to the `first_submitted_date` trap in `docs/ingestion/connectors.md`. "Invariant 6/9" stay as INV citations. "Requirements §8 pattern" becomes the RES fetch-once ID. The path is kept (h11). |
| `catalyst-calendar` | `Docs impact`: CON (schema change), HUB and EXT, plus "relation to the RES catalyst panel decided at scoping" (the two-planned-sources trap in `panels.md`). Constraints cite INV-7, INV-10, INV-12, INV-14 and the CON IDs. |
| `slow-signal-data-refresh` | `Docs impact`: RES (new refresh endpoints) and OPS (DAGs, alert). Constraints: the SEC traps link `docs/ingestion/connectors.md` and `docs/operations/orchestration.md`; "a refresh appends, never rewrites" becomes the shared panel ID. The root `CLAUDE.md` citations at `:22` and `:61` are repointed (table in §4). **Blocked by:** drop item 6 (`specs/infrastructure-observability.md` is done) and items 1–5, whose code is merged (each spec's tests run on fakes, as its own line under the list says). The field becomes one line: "None outstanding: the panel code it wraps is merged (RES-xxx…RES-yyy)". The status stays as `TODO.md` has it; the PR body notes that the owner can set it `ready`. |
| `research-input-archive` | `Docs impact`: EVA. The input-manifest requirement changes from refuse-all to verify, and the EVA durability ID is decided by this spec's scoping. The constraint "No change to universe rules or registered hypotheses" cites the EVA read-only ID. |

**Rule for other domains' requirements.** Cite an ING, HUB, COR or OPS requirement by its ID only when that ID exists on the integration branch. Otherwise cite the owner doc as a file link (for example `docs/ingestion/connectors.md`). Never write an `<NS>-?` placeholder. List each file-level link in the PR body, so the cutover reconciliation can narrow it to an ID.

### 6. Shared files: only this spec's sections

- **`specs/living-docs-cutover-matrix.md`:**
  - fill the `ID` cell of every row whose `NS` cell is RES or EVA and whose disposition is move, ratify, divergent or retire;
  - in the Decisions table, append to the `IDs` cell of every row classified `binding` the RES and EVA IDs whose `Source` cites that heading, separated by spaces. A cell other specs also fill keeps their IDs.

  Edit no other cell.
- **`docs-check.toml`:** as the last step, remove `"research"` from `[rollout] planned_domains`. Change no other line.
- **`TODO.md`:** update only this spec's row: Status `done` and the link `specs/done/living-docs-research.md`.
- **This spec:** move it to `specs/done/living-docs-research.md` with Status `done`, in this PR.
- **`docs/README.md`** is owned by `specs/living-docs-system-and-contracts.md`. This spec does not edit it.

## Out of scope

- Any change to application code, tests, `config/**` (hypotheses, registry, universe rules, `finra_calendar.csv`, themes) or `docs/strategy-research.md`. This spec never edits a machine-locked file.
- Fixing a divergence. Each of these is a separate fix spec, opened from the defects-found PENDING entry:
  - the trial-ledger store;
  - `run_backtest` admission;
  - `fetch_prices.py`;
  - the portfolio grid checks;
  - FX timing;
  - the `AsOfContext` docstring (STR).
- Edits that belong to `specs/legacy-docs-retirement.md`:
  - `services/backtesting/README.md`;
  - the `docs/requirements.md` § index;
  - the banner and links in `docs/strategy-research.md`;
  - `docs/PREREQUISITES.md` rows;
  - the stale blocker notes in `TODO.md`.
- `docs/README.md` (owned by `specs/living-docs-system-and-contracts.md`).
- Strategy, risk and dashboard requirements (`specs/living-docs-strategy-and-dashboard.md`).
- Any text for a sixteenth invariant. It is written only by the cutover (step 3), and only if the owner's CHOICE adopts it.
- The `specs/historical-backfill.md` Blocked-by edit for the backfill ordering gate. That is `specs/living-docs-ingestion.md`, which links the RES ID.
- Re-registering H9, H11 or H12, or archiving the six code-done specs. That is decided when each of them completes.

## Constraints

- **INV-15: docs are not proof.**
  - Every `tested` row names a test read in the code at the rollout base.
  - Every claim about behaviour is checked against code, not against the README.
- **Conversion provenance** (`specs/living-docs-cutover-design.md` §8.5). Each requirement's `Source` is, in priority order:
  1. a requirements §;
  2. a `CHOICE` heading;
  3. an archived spec;
  4. an invariant;
  5. an owner ratification.

  The six code-done specs' policy text counts as approved once the CHOICE answering "code-done specs blocked on the Mac" exists. Until then, cite it with status `pending-decision` and that PENDING heading.

  A source that contradicts the code is written as approved, with status `divergent`.
- **Conflict policy:**
  - Locked files win on values. A doc that disagrees with `protocol.yaml`, `h*.yaml` or `rules.yaml` is wrong.
  - Code that disagrees with an approved rule is `divergent`. It never silently wins.
- **Frozen paths.** Never move or rename these:
  - `specs/sec-ownership-datasets.md`;
  - `specs/clinicaltrials-version-diffs.md`;
  - `specs/catalyst-date-panel.md`;
  - `specs/point-in-time-universe.md`;
  - `docs/strategy-research.md`.

  The `SpecialistClassifier` item keeps its name.
- **ID rules:**
  - IDs are allocated with `--next`, numbered in file order and defined once.
  - Rewording keeps an ID.
  - No register number (`D-` followed by two digits) appears in `docs/` or in any spec this spec edits. Decisions are cited by their `DECISIONS.md` heading.
  - On a collision after rebase, renumber this spec's new IDs, including in the matrix and in the edited specs.
- **No registered value in prose.** The machine authority holds the number, and the doc names the key. This applies to:
  - the budget, threshold, window, bound and grid values of `protocol.yaml`, `h*.yaml` and `config/universe/*.yaml`;
  - the cost defaults in `.env.example`.

  Constants that live only in code or an approved spec (the −30% delisting bound, the 10% survivorship flag) may be stated with their source. They appear in the parameters trap in `evaluation-protocol.md`.
- **Citations in verification-table cells are always in backticks,** as check K requires. A heading is written as in `DECISIONS.md`; a heading that itself contains backticks is cited with double backticks, for example ``## 2026-10-07 — Startup data — CHOICE — data fills itself on `up`; prices refresh daily``.
- **No plan-step names** in IDs, headings or test names.
- **Deliberate defects** used to prove a test run only in a copy under `${TMPDIR:-/tmp}`. Nothing is committed or pushed.

## Dependencies

- **Needs:**
  - `specs/docs-check-tooling.md`: the checker, `--next` and check M;
  - `specs/living-docs-system-and-contracts.md`: the INV and CON IDs and `docs/README.md`;
  - the `DECISIONS.md` headings in Blocked by.
- **Hands to later specs:**
  - `specs/living-docs-strategy-and-dashboard.md` links `simulation.md`, `panels.md` and `evaluation-protocol.md` (trial ledger, deflated Sharpe, protocol `sizing`, read-only config).
  - `specs/living-docs-ingestion.md` links the backfill ordering gate from `specs/historical-backfill.md`.
  - `specs/legacy-docs-retirement.md`:
    - replaces the backtesting README's behaviour sentences, and the copied values in `docs/strategy-research.md`, with links to these IDs;
    - maps requirements §0.1, §0.3, §4.1 (backtest clause), §6.7 (research use) and §8 to RES IDs in the § index.
  - `specs/living-docs-cutover.md`:
    - runs check M on the RES and EVA rows;
    - flips the research ratification batch's rows after the owner answers;
    - narrows the file-level links listed in this PR body to IDs.

## Affected files

| Path | Action |
|---|---|
| `docs/research/market-data.md` | create |
| `docs/research/universe.md` | create |
| `docs/research/panels.md` | create |
| `docs/research/simulation.md` | create |
| `docs/research/backtesting.md` | create |
| `docs/research/evaluation-protocol.md` | create |
| `specs/point-in-time-universe.md` | modify (reduced to Mac acceptance, all required sections kept; path frozen) |
| `specs/sec-ownership-datasets.md` | modify (reduced; `SpecialistClassifier` pointer; path frozen) |
| `specs/short-interest-snapshots.md` | modify (reduced) |
| `specs/catalyst-date-panel.md` | modify (reduced; path frozen) |
| `specs/filing-text-change-score.md` | modify (reduced) |
| `specs/holdings-composite-score.md` | modify (reduced) |
| `specs/clinicaltrials-version-diffs.md` | modify (Docs impact, IDs; path frozen) |
| `specs/catalyst-calendar.md` | modify (Docs impact, IDs) |
| `specs/slow-signal-data-refresh.md` | modify (Docs impact, IDs) |
| `specs/research-input-archive.md` | modify (Docs impact, IDs) |
| `specs/living-docs-cutover-matrix.md` | modify: `ID` cells of rows with NS RES or EVA; RES/EVA IDs appended to binding Decisions-table `IDs` cells |
| `docs-check.toml` | modify: `[rollout] planned_domains`, remove `"research"` only |
| `DECISIONS.md` | modify (append one entry: research ratification batch) |
| `TODO.md` | modify (this spec's row only) |
| `specs/living-docs-research.md` → `specs/done/living-docs-research.md` | move, Status `done` |
| `config/hypotheses/*`, `config/universe/*`, `config/short_interest/finra_calendar.csv` | untouched, cited |
| `docs/README.md`, `docs/strategy-research.md`, `services/backtesting/README.md`, `docs/requirements.md` | untouched, cited |
| `services/backtesting/src/**`, `services/backtesting/tests/**` | untouched, cited |

## Required tests

All checker assertions run from the repo root on this branch, using `python3 -m tools.docs_check` (created by `specs/docs-check-tooling.md`). `--only`, `--paths` (a comma list of globs), `--matrix`, `--domain` and `--decisions` are the selectors that spec defines. The spec-specific checks are shell commands, each listed with what makes it fail.

In the commands below, `$OWN` stands for this spec's own files:

```text
docs/research/**,specs/point-in-time-universe.md,specs/sec-ownership-datasets.md,specs/short-interest-snapshots.md,specs/catalyst-date-panel.md,specs/filing-text-change-score.md,specs/holdings-composite-score.md,specs/clinicaltrials-version-diffs.md,specs/catalyst-calendar.md,specs/slow-signal-data-refresh.md,specs/research-input-archive.md,specs/done/living-docs-research.md
```

- **`research_docs_pass_structure_ids_and_links`.** Runs `python3 -m tools.docs_check --only A,B,C,D,E,K --paths "$OWN"`. It fails on:
  - a missing required H2 in a doc or in one of the ten edited specs;
  - a non-ancestor `Last reviewed against`;
  - a duplicate or unresolved ID;
  - a missing `Docs impact`;
  - a backticked path that does not exist;
  - a `tested` row whose `path::name` is absent;
  - a `divergent` or `pending-decision` row without an existing `DECISIONS.md` heading;
  - a register number or an `NS-?` placeholder in these files.
- **`matrix_rows_for_research_all_have_assigned_ids`.** Runs `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain RES`. It fails if any RES row with disposition move, ratify, divergent or retire lacks an ID that check C finds, or if that ID's `Source` lacks the row's source reference.
- **`matrix_rows_for_evaluation_all_have_assigned_ids`.** The same command with `--domain EVA`.
- **`binding_decisions_carried_by_research_ids`.** Runs `python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain RES` and the same with `--domain EVA`. It fails if a binding Decisions-table row with a RES or EVA fragment row has no RES or EVA ID in its `IDs` cell, or if that ID's `Source` does not contain the heading text.
- **`backfill_ordering_gate_is_a_research_requirement`.**
  - Command: `grep -nE '<a id="RES-[0-9]{3}"></a>.*backfill' docs/research/backtesting.md`.
  - It prints at least one line.
  - That ID's verification row cites `Edge research scoping — CHOICE — two non-LLM panels before the LLM backfill`.
  - It fails if the gate was dropped.
- **`hash_locked_and_version_locked_files_unchanged`.**
  - Command: `git diff --exit-code "$(git merge-base HEAD origin/feature/living-docs-integration)" -- config/ docs/strategy-research.md docs/README.md services/`.
  - It fails on any byte change under `config/`, in code, or in a file this spec must not edit.
- **`hypothesis_cited_spec_paths_still_exist`.**
  - Command: `test -f specs/sec-ownership-datasets.md && test -f specs/clinicaltrials-version-diffs.md && test -f specs/catalyst-date-panel.md && test -f specs/point-in-time-universe.md`.
  - Check A's `frozen_paths` must also pass.
- **`edited_research_specs_cite_no_root_claude_md_section`.** `grep -n 'CLAUDE\.md' specs/point-in-time-universe.md specs/sec-ownership-datasets.md specs/short-interest-snapshots.md specs/catalyst-date-panel.md specs/filing-text-change-score.md specs/holdings-composite-score.md specs/clinicaltrials-version-diffs.md specs/catalyst-calendar.md specs/slow-signal-data-refresh.md specs/research-input-archive.md` prints nothing. It fails on a residual section citation (at `e51f742` it prints five lines).
- **`specialist_classifier_pointer_resolves_in_one_hop`.** It fails if the anchor is missing or duplicated, or if the ID is undefined.
  - `grep -c 'id="SpecialistClassifier"' specs/sec-ownership-datasets.md` prints `1`.
  - The RES ID on that line is defined in `docs/research/panels.md` (check D).
  - That RES item names `h9.yaml` `components.specialist_13f_ownership.thresholds`.
- **`preregistered_protocol_tests_still_pass`.**
  - Command: `cd services/backtesting && uv run pytest tests/unit/test_preregistered_protocol.py tests/unit/test_hypothesis_registry.py -q --strict-markers`.
  - Expect the same count as on the integration base. At `e51f742` that is 37 + 8 by `def test_` count; read the real number before the change.
  - It proves the h9 string assertion is untouched.
- **`code_done_specs_keep_required_sections_and_cite_ids`.** It fails if a required section was dropped, if behaviour text was left in "What this builds", or if no ID is cited. For each of the six specs:
  - `grep -cE '^## (Context|What this builds|Out of scope|Constraints|Required tests|Definition of done)$'` prints `6`;
  - the "What this builds" section, extracted with `awk '/^## What this builds$/{f=1;next} /^## /{f=0} f && NF'`, has at most 8 non-empty lines, and each line matches `RES-[0-9]{3}`;
  - `grep -cE 'RES-[0-9]{3}'` over the whole spec is ≥ 2;
  - `grep -c '^## Scope$'` prints `0`.
- **`every_test_named_by_a_code_done_spec_is_cited_in_research_docs`.**
  - Collect each `test_[a-z0-9_]+` name in the six specs' `Required tests` at the integration base (`git show <base>:specs/<name>.md`).
  - Each must appear in a `Verified by` cell of `docs/research/*.md`.
  - It fails if a moved test lost its requirement.
- **`no_registered_value_restated_in_research_docs`.**
  - Run `grep -nE` over `docs/research/*.md` for the literal values that `protocol.yaml`, `h9.yaml`, `h10.yaml` and `config/universe/*.yaml` own.
  - The pattern list is fixed in the PR body. It covers at least `9999`, `\[-250, ?-30\]`, `budget_cells`, `\$?500k`, `\$?50M`, `\$?500M`, `\$?10B`, `\$?2M`, `0\.95` and `holdout_months: `.
  - It must print nothing outside a fenced example. It fails on a copied value.
- **`trial_ledger_durability_is_divergent_and_cites_its_decision`.**
  - In `evaluation-protocol.md`, the durability requirement's verification row has status `divergent`.
  - Its Source or Status cell contains `Living docs — PENDING — trial ledger and holdout as untracked local files`, or the matching CHOICE.
  - It fails otherwise.
- **`variant_reporting_and_read_only_config_are_owned_by_evaluation_protocol`.** For each of the two rules (pattern `entity-only`, pattern `read-only`):
  - `grep -lE '<a id="[A-Z]{3}-[0-9]{3}"></a>.*(PATTERN)' docs/research/*.md docs/strategy/*.md docs/dashboard.md 2>/dev/null` prints exactly `docs/research/evaluation-protocol.md`;
  - every other line in those files that matches the pattern also contains `evaluation-protocol.md#EVA-`.

  It fails if a second file defines the rule, or mentions it without linking the owner. Falsify it once in a copy of the tree under `${TMPDIR:-/tmp}`, by adding an `<a id="RES-999"></a>` line containing `entity-only` to the copy's `backtesting.md`. The test must print that file.
- **`research_planned_domain_removed`.**
  - Command: `python3 -c "import tomllib;d=tomllib.load(open('docs-check.toml','rb'));assert 'research' not in d['rollout']['planned_domains']"`.
  - It fails if the domain is still listed.
- **`at_risk_rules_in_research_map_to_ids`.** The matrix rows for these rules each carry an ID that check C finds:
  - date-only timing;
  - one event per corroboration;
  - variant reporting;
  - processing time (RES side);
  - read-only research config;
  - the universe version lock;
  - publication-date rules;
  - the code-done specs' rules.

  This is covered by check M. It is listed so a reviewer reads those rows.

## Definition of done

```bash
OWN='docs/research/**,specs/point-in-time-universe.md,specs/sec-ownership-datasets.md,specs/short-interest-snapshots.md,specs/catalyst-date-panel.md,specs/filing-text-change-score.md,specs/holdings-composite-score.md,specs/clinicaltrials-version-diffs.md,specs/catalyst-calendar.md,specs/slow-signal-data-refresh.md,specs/research-input-archive.md,specs/done/living-docs-research.md'
python3 -m tools.docs_check --only A,B,C,D,E,K --paths "$OWN"
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain RES
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --domain EVA
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain RES
python3 -m tools.docs_check --matrix specs/living-docs-cutover-matrix.md --decisions --domain EVA
git diff --exit-code "$(git merge-base HEAD origin/feature/living-docs-integration)" -- config/ services/ docs/strategy-research.md docs/README.md
grep -c 'id="SpecialistClassifier"' specs/sec-ownership-datasets.md
ls docs/research/*.md | wc -l
(cd services/backtesting && uv run pytest tests/unit/test_preregistered_protocol.py tests/unit/test_hypothesis_registry.py -q --strict-markers)
python3 -c "import tomllib;d=tomllib.load(open('docs-check.toml','rb'));assert 'research' not in d['rollout']['planned_domains'];print('planned ok')"
```

Expected:
- the five checker runs print nothing and exit 0;
- `git diff` exits 0;
- the `grep` prints `1`;
- the `ls` count prints `6`;
- pytest reports the same passed count as on the integration base, with 0 failed;
- the last line prints `planned ok`.

The `planned_domains` edit is the last commit. Only then does the first checker run treat broken research links as findings rather than notices.

The PR body lists:
- the ratification-batch heading;
- each `divergent` row with its heading;
- each file-level link to another domain's doc that still waits for an ID;
- the value pattern list used.

## Compatibility

- **Readers:**
  - `services/backtesting/README.md` and `docs/requirements.md` are unchanged until `specs/legacy-docs-retirement.md`, so the old and the new text both exist on the integration branch.
  - Nothing reaches `develop` before the cutover. Source: `## 2026-10-15 — Living docs — PENDING — rollout branch model`, or its CHOICE.
  - After the cutover, a README sentence becomes a link to its RES or EVA ID.
- **Hash-locked citations:**
  - `h9.yaml`, `h11.yaml` and `h12.yaml` still resolve to existing files.
  - h9 reaches the classifier through one documented hop, with an anchor that now exists.
  - `rules.yaml:1` still names an existing spec.
- **Tests:**
  - No test file changes.
  - The tests that read docs (`test_preregistered_protocol.py:440`, `test_docs_never_offer_down_v_as_a_fix`) read files this spec does not move.
- **Links:** links from archived specs and `DECISIONS.md` to the six code-done specs keep resolving, because the paths stay. The specs now say less, and the RES IDs say the rest.
- **Agents:** until `specs/agent-instruction-hierarchy.md` merges, `CLAUDE.md` still points at `specs/`. The reduced specs name their RES IDs, so a session reading a spec finds the rule in one hop.

## Rollback

On the integration branch, before the cutover. Use the integration-branch tip before this spec merged and the tip after it, so the range includes this spec's first commit:

```bash
git revert --no-commit <integration tip before merge>..<integration tip after merge>
git restore --staged --worktree --source=HEAD -- DECISIONS.md
# append to DECISIONS.md:
#   ## <date> — Living docs — FLAG — research docs rolled back
#   (what was reverted, why, and that the research ratification batch entry stays as history)
git add DECISIONS.md && git commit
```

The revert:
- restores the ten specs and this spec's place in `specs/`;
- restores `"research"` in `planned_domains` and this spec's `TODO.md` row;
- removes `docs/research/` and the matrix ID cells.

It never deletes a `DECISIONS.md` entry.

If later specs already cite RES or EVA IDs, revert those citations in the same PR, or check D fails. Nothing outside the integration branch changes, and no data or runtime state is involved.

## Notes

- **Approval of the code-done specs' text.** The provenance list in `specs/living-docs-cutover-design.md` §8.5 has no entry for "policy text of an active, code-done spec". This spec treats the CHOICE answering "code-done specs blocked on the Mac" as its approval, as Constraints says. The cutover reviewer should confirm that reading.
- **`docs/strategy-research.md`** still copies registered values (`:232-249`, the triage table at `:213-222`) and has a stale backfill section (`:241-257`). The banner and the link edits belong to `specs/legacy-docs-retirement.md`. This spec only owns the rules those copies refer to.
- **Matrix ownership.** `specs/living-docs-cutover-matrix.md` belongs to the cutover spec. Check M needs each domain spec to write its IDs into it, so this spec edits only the cells §6 names.
- **Event path parked.** H1, H4 and H6 are suspended. Documenting the event backtest as current behaviour is still correct, because the code runs. `backtesting.md` Scope says the path is parked.
- **Trap while writing.** `listings.parquet` and `coverage.json` make reruns differ. State that as current behaviour, not as a requirement that reruns are reproducible. Reproducibility is the EVA manifest requirement.
- **As built.**
  - **IDs.** RES-001…RES-082 in five docs (`market-data.md` RES-001…012, `universe.md` RES-013…025, `panels.md` RES-026…054, `simulation.md` RES-055…065, `backtesting.md` RES-066…082) and EVA-001…EVA-028 in `evaluation-protocol.md`. The fetch-once ID is RES-029; the shared panel IDs are RES-026 (known-at) and RES-027 (append-only); the `SpecialistClassifier` pointer names RES-033; the backfill ordering gate is RES-066; the EVA read-only ID is EVA-006 and the durability ID EVA-016 (`divergent`).
  - **Off-grid cells split.** The off-grid refusal is two IDs, one row each: EVA-013 (event runs, `tested`) and EVA-014 (portfolio runs, `divergent`), because the two paths have different statuses.
  - **RES-061 is `untested`.** Only the missing FX bar is asserted; no test checks that `fx_rate` is EUR per USD rather than its inverse.
  - **Ratification batch.** Exactly the six rows §2 lists (RES-008, RES-012, RES-062, RES-070, RES-082, EVA-021); no further code-only requirement was found. Approving RES-062 as written makes `fx.py` divergent, which the batch entry says.
  - **Dropped Definition-of-done lines.** Besides the two the spec names (the `CLAUDE.md` naming table and `.env.example`), the README and `docs/PREREQUISITES.md` update lines of `point-in-time-universe`, `sec-ownership-datasets` and `short-interest-snapshots` were dropped: `services/backtesting/README.md` and `docs/PREREQUISITES.md` belong to `specs/legacy-docs-retirement.md`.
  - **`pytest-socket` constraints** in the edited specs cite ENG-004, the engineering ID that owns the rule.
  - **Two matrix Source cells reformatted.** M-RES-170 and M-RES-174 cited headings that contain backticks as `\``-escaped single-backtick spans; check M read each span as ending at the backslash, so no doc could match it. Both are now double-backtick spans with the same text. No other non-ID cell changed.
  - **IDs cells separated by spaces,** as the existing ENG and CON cells are; the checker accepts commas too.
  - **Notes of the reduced specs** keep only run traps: ordering against other SEC runs (from `specs/first-run-on-stack-machine.md`), resuming a stopped run, the unmapped-CUSIP flag and the unresolved-ticker list.
  - **File-level links still waiting for an ID** (planned domains): `docs/ingestion/connectors.md` (SEC traps, clinical-trials trap; six specs and `backtesting.md`, `panels.md`, `universe.md`), `docs/ingestion/extraction.md` (catalyst-calendar, `evaluation-protocol.md`), `docs/core-hub/storage.md` and `docs/core-hub/http-api.md` (catalyst-calendar), `docs/core-hub/corroboration.md` (`backtesting.md`), `docs/operations/orchestration.md`, `docs/operations/topology.md` and `docs/operations/observability.md` (slow-signal-data-refresh, `market-data.md`, `universe.md`), `docs/strategy/risk.md` and `docs/dashboard.md` (`simulation.md`, `evaluation-protocol.md`).
  - **Value patterns used** for the no-registered-values check: `9999`, `\[-250, ?-30\]`, `budget_cells`, `\$?500k`, `\$?50M`, `\$?500M`, `\$?10B`, `\$?2M`, `0\.95`, `holdout_months: `. A rules-file value written as prose ("twenty sessions") was replaced by its key `liquidity_sessions`.
  - **`slow-signal-data-refresh`** keeps status `blocked` in `TODO.md`; its Blocked by now says nothing is outstanding, so the owner can set it `ready`.
