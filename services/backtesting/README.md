# backtesting

Price snapshots, the point-in-time stock universes, the research panels (catalysts, filing text, SEC ownership, short interest) and the scores built on them, market simulation, the backtest runners and the evaluation protocol (`auspex_backtesting`). The same image runs `price-service`, the HTTP API the price refresh and universe build DAGs call, and the `price-bootstrap` and `minio-init` one-shots.

Commands: [AGENTS.md](AGENTS.md).

---

## Where the rules are

| Subject | Package | Owner |
|---|---|---|
| Price snapshots, settled bars, splits, market caps, price refresh | `prices/` | [docs/research/market-data.md](../../docs/research/market-data.md) |
| Point-in-time universes and how backtests use them | `universe/` | [docs/research/universe.md](../../docs/research/universe.md) |
| Catalyst date panel | `catalysts/` | [docs/research/panels.md](../../docs/research/panels.md) |
| Filing text change score (H10) | `filings/` | [docs/research/panels.md](../../docs/research/panels.md) |
| SEC ownership panels | `ownership/` | [docs/research/panels.md](../../docs/research/panels.md) |
| Short interest | `short_interest/` | [docs/research/panels.md](../../docs/research/panels.md) |
| Holdings composite score (H9) | `scores/` | [docs/research/panels.md](../../docs/research/panels.md) |
| Calendar, fills, costs, currency, sizing | `market_sim/` | [docs/research/simulation.md](../../docs/research/simulation.md) |
| Point-in-time alignment, event backtest, portfolio backtest, metrics | `alignment/`, `backtest/`, `portfolio/`, `metrics/` | [docs/research/backtesting.md](../../docs/research/backtesting.md) |
| Hypothesis registry, trial ledger, event and portfolio evaluation | `hypothesis.py`, `protocol.py`, `evaluation/` | [docs/research/evaluation-protocol.md](../../docs/research/evaluation-protocol.md) |
| Price service metrics | `price_metrics.py` | [docs/operations/observability.md](../../docs/operations/observability.md) |

Research configuration lives at the repository root: `config/hypotheses/`, `config/universe/`, `config/short_interest/`.

---

## Scripts

| Script | Purpose |
|---|---|
| `scripts/fetch_prices.py` | Snapshot prices for tickers outside the watchlist, once |
| `scripts/build_universe.py` | Run a universe build outside the schedule (`--rules PATH` for a universe other than `UNIVERSE_RULES_PATH`'s), or `--export-backfill-scope PATH` to copy the backfill scope out of MinIO |
| `scripts/build_filing_panel.py` | Build or extend the H10 filing-text panel over a universe (`--rules PATH`, default `UNIVERSE_RULES_PATH`) and print coverage: filings found, sections cut, missing by reason, members scored per month. Needs that universe built first |
| `scripts/build_catalyst_panel.py` | Build or extend the catalyst panel (`--since`, default 2014-01-01; `--until`, default today) and print its coverage: catalysts per year, members with any catalyst, unmatched advisory committee notices, PDUFA hits by precision. Needs the universe built first |
| `scripts/register_hypothesis.py` | Register a hypothesis file in the pre-registration ledger |
| `scripts/fetch_ownership.py` | Backfill and extend the SEC ownership panels and print their coverage |
| `scripts/compute_holdings_scores.py` | Write the H9 score snapshot for every universe month still missing (`--no-floor` for the no-floor cells) and print coverage: the variant, per month members, under the floor, scored and left out, per year the component rank correlations. Needs the universe, ownership panels and short interest stored |
| `scripts/fetch_short_interest.py` | Backfill and extend FINRA short interest for the universe's tickers and print coverage: first available settlement date, periods FINRA returned nothing for, gaps, tickers with no report. Needs the universe built first |
| `scripts/run_portfolio_backtest.py` | Run a registered portfolio hypothesis's cell (default its primary cell) over a universe (`--universe-rules PATH`, default the biotech universe) at every tier in `PAPER_CAPITAL_TIERS_EUR`, reserve the cell in the trial ledger and write the report and verdict as JSON (`--final` reads the holdout once) |
