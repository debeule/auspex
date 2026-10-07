# Prerequisites — outstanding items

Everything here needs a person before the blocked step can proceed. [`SETUP.md`](../SETUP.md) puts the ones needed to run the system in order.

---

## 👤 Needs your decision

| Item | Blocks | Effort | Notes |
|---|---|---|---|
| **Local model selection** | Golden set expansion; Historical backfill | 2–4 hours | Follow `docs/local-model-runbook.md`: install Ollama, register and run `scripts/evaluate_model.py` + `scripts/score_extraction.py` on the candidates (Llama 3.1 8B Q8 primary, 8B Q4_K_M fallback; on the 24 GB M4 Pro larger models do not fit next to Docker). The candidate that reaches ≥0.85 `is_signal` precision on the golden set becomes the backfill and live extraction model. Record the chosen model in DECISIONS.md. Required before golden-set-expansion and historical-backfill specs can run. |
| **Backfill time approval (local model)** | Historical backfill | — | The backfill machine is a 24 GB M4 Pro. At an estimated 10–15 s/document for Llama 3.1 8B Q8, the 24-month backfill takes roughly 3–5 days of runtime. Replace this estimate with the `evaluate_model.py` measurement. Run under `caffeinate -i scripts/run_backfill.py ...`. Set `BACKFILL_TIME_CEILING_HOURS` in `.env` before starting. The run is checkpointed — safe to interrupt and resume. Confirm you can commit the machine for this duration before executing. |
| **Backfill budget approval (API model fallback)** | Historical backfill | 15 min | Only applies if no local candidate passes the gate and you fall back to `gpt-4o-mini-2024-07-18`. Run the dry-run first — it prints estimated LLM calls and cost (~$65 for 24 months). Set `BACKFILL_BUDGET_CEILING` in `.env`. |
| **Broken-PR CI verification** | CI/CD pipeline (Phase 6) | 15 min | Push a deliberately failing test once, confirm CI goes red, revert. Certifies the CI gate is real. |

---

## 🔢 Numbers to set before Phase 4

| Setting | Where | Notes |
|---|---|---|
| `BACKFILL_BUDGET_CEILING` | `.env` | API backend only. Dollars. Set after reviewing the dry-run cost estimate. Runner aborts if estimate exceeds this before any LLM calls. |
| `BACKFILL_TIME_CEILING_HOURS` | `.env` | Local backend only. Hours. Recommended: `48` (36-hour estimate + 33% for latency variance and rate-limit backoff). Runner aborts if estimate exceeds this before any LLM calls. |
| Backfill depth | `--start-date` / `--end-date` CLI flags | Default plan: 24 months (Sep 2024–Sep 2026). Adjust if you want more or less history. |
| Steady-state LLM budget | `.env` | How many extractions per day is acceptable ongoing. Starter: 500/day. |

---

## Infrastructure (Linux hosts only)

| Setting | How to apply | Notes |
|---|---|---|
| `vm.max_map_count=262144` | `sysctl -w vm.max_map_count=262144` (root) · persist via `/etc/sysctl.d/99-elasticsearch.conf` | Required by Elasticsearch. Docker Desktop (macOS/Windows) sets this automatically inside its VM — Linux hosts must set it manually or Elasticsearch fails to start. |

---

## Strategy layer — required before session 3 (live trading)

| Item | Blocks | Effort | Notes |
|---|---|---|---|
| **Belgian tax advisor consultation** | Live trading (session 3) | 1–2 hours | Confirm: (a) whether systematic corroboration-based equity trading is investment income (10% CGT) or speculative income (33%); (b) whether short-selling triggers speculative classification regardless of frequency; (c) how to document non-speculative intent for the record. Record advisor's conclusion in DECISIONS.md before session 3 begins. |
| **IBKR account open and funded** | Live trading (session 3) | 1–2 days | Interactive Brokers account required. Confirm the account supports: US equity trading, short-selling (margin account required), and a Belgian tax residence. |
| **IBKR borrow availability for watchlist tickers** | H8 (negative asymmetry) and any short test | 30 min | Verify SRPT, SPRB, BEAM, CRSP, CAPR, ABVX, RCKT, QURE are borrowable on IBKR and at what annualised borrow fee. Check via IBKR's Short Stock Availability tool or Trader Workstation. Some small-cap biotech names may be unavailable or prohibitively expensive to borrow. Record per-ticker availability in DECISIONS.md before designing short-side backtests. |
| **Delisted ticker price data source** | Survivorship bias correction; `specs/point-in-time-universe.md` | 1–2 hours | Superseded in scope by the point-in-time universe, which includes every delisted biotech in the window, not only the 8 watched names; Decided 2026-10-07: free sources only (yfinance, then Stooq); incomplete names are excluded per event, counted, and bounded in the report (see the spec). Original note: if any of the 8 watched companies is acquired, merged, or delisted during the 24-month backfill window (Sep 2024–Sep 2026), yfinance may not return complete price history. Identify any such events in the watchlist; find a source for delisted price history (IBKR historical data, Tiingo, or similar). Record findings in DECISIONS.md. |

---

## 🔢 Strategy layer — numbers to set before running Phase 4

| Setting | Where | Notes |
|---|---|---|
| `KNOWN_AT_DELAY_DAYS` | `.env` | Days added to `corroborated_at` before entry. Default: `1`. Run sensitivity analysis at 0, 1, 3, 5 before reporting final results. |
| `HOLDOUT_MONTHS` | `.env` | Months sealed at the end of the backfill window. Default: `3`. Do not change after any in-sample backtest has run. |
| `PROMOTION_T_THRESHOLD` | `.env` | Minimum t-statistic for promotion. Default: `3.0` (Harvey, Liu & Zhu 2016). |
| `PROMOTION_DEFLATED_SHARPE_THRESHOLD` | `.env` | Minimum deflated Sharpe for promotion. Default: `0.95` (Bailey & López de Prado 2014). |
| `SPREAD_BPS` | `.env` | Flat half-spread in basis points per leg, used only when `CostModel` has no `SpreadEstimator`. Default: `50`. Backtests should pass a `SpreadEstimator` for per-ticker spreads. |
| `MIN_HALF_SPREAD_BPS` | `.env` | Floor on the estimated per-ticker half-spread, basis points per leg. Default: `2.0`. |
| `FX_FEE_RATE` | `.env` | IBKR EUR/USD conversion fee per leg, fraction of notional. Default: `0.0003`. |
| `MAX_ADV_FRACTION` | `.env` | Largest order as a fraction of 20-session average daily volume. Default: `0.01`. |
| `BORROW_FEE_ANNUAL_PCT` | `.env` | Annualised borrow fee for short positions. Default: `3.0`. Update with IBKR actual rates per ticker. |
| `IBKR_RATE_PER_SHARE` | `.env` | IBKR commission per share (USD). Default: `0.005`. |
| `USD_MIN_COMMISSION` | `.env` | IBKR minimum commission per order (USD). Default: `1.00`. |
| `TOB_RATE` | `.env` | Belgian TOB rate per leg. Default: `0.0035`. Update if rate changes. |

---

## ✅ Already configured
OpenAI key + billing, NCBI key, openFDA key, `SEC_USER_AGENT`, extraction quality gate (≥0.85 precision), corroboration precision gate (≥0.85 genuine), extraction model (`gpt-4o-mini`), EPO OPS key + secret.
