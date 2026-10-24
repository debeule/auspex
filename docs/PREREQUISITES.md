# Prerequisites — outstanding items

Everything here needs a person before the blocked step can proceed. [`SETUP.md`](../SETUP.md) puts the ones needed to run the system in order.

---

## 👤 Needs your decision

| Item | Blocks | Effort | Notes |
|---|---|---|---|
| **Local model selection** | Golden set expansion; Historical backfill | 2–4 hours | Follow `docs/local-model-runbook.md`: install Ollama, register and run `scripts/evaluate_model.py` + `scripts/score_extraction.py` on the candidates (Llama 3.1 8B Q8 primary, 8B Q4_K_M fallback; on the 24 GB M4 Pro larger models do not fit next to Docker). The candidate that reaches ≥0.85 `is_signal` precision on the golden set becomes the backfill and live extraction model. Record the chosen model in DECISIONS.md. Required before golden-set-expansion and historical-backfill specs can run. |
| **FINRA API credential** | Short interest snapshots (first fetch, first-run spec step 3c) | 15 min | Create a free public API credential in FINRA's API console (`developer.finra.org`) and set `FINRA_API_CLIENT_ID` and `FINRA_API_CLIENT_SECRET` in `.env`. FINRA's API answers nothing without one. |
| **Backfill time approval (local model)** | Historical backfill | — | The backfill machine is a 24 GB M4 Pro. At an estimated 10–15 s/document for Llama 3.1 8B Q8, the 24-month backfill takes roughly 3–5 days of runtime. Replace this estimate with the `evaluate_model.py` measurement. Run under `caffeinate -i scripts/run_backfill.py ...`. The run is checkpointed — safe to interrupt and resume. Confirm you can commit the machine for this duration before executing. |
| **Backfill budget approval (API model fallback)** | Historical backfill | 15 min | Only applies if no local candidate passes the gate and you fall back to `gpt-4o-mini-2024-07-18`. Run the dry-run first — it prints estimated LLM calls and cost (~$65 for 24 months). |

---

## Strategy layer — required before live trading

| Item | Blocks | Effort | Notes |
|---|---|---|---|
| **Belgian tax advisor consultation** | Live trading | 1–2 hours | Confirm: (a) whether systematic corroboration-based equity trading is investment income (10% CGT) or speculative income (33%); (b) whether short-selling triggers speculative classification regardless of frequency; (c) how to document non-speculative intent for the record. Record advisor's conclusion in DECISIONS.md before live trading begins. |
| **IBKR account open and funded** | Live trading | 1–2 days | Interactive Brokers account required. Confirm the account supports: US equity trading, short-selling (margin account required), and a Belgian tax residence. |
| **IBKR borrow availability for watchlist tickers** | Any short test | 30 min | Verify SRPT, SPRB, BEAM, CRSP, CAPR, ABVX, RCKT, QURE are borrowable on IBKR and at what annualised borrow fee. Check via IBKR's Short Stock Availability tool or Trader Workstation. Some small-cap biotech names may be unavailable or prohibitively expensive to borrow. Record per-ticker availability in DECISIONS.md before designing short-side backtests. |

---

## 🔢 Strategy layer — numbers to set before the first backtest

The cost model's settings are the "Backtest costs" group of `.env.example`; check them against your broker account before the first backtest. What each one does: [docs/research/simulation.md](research/simulation.md).

---

## ✅ Already configured
OpenAI key + billing, NCBI key, `SEC_USER_AGENT`, EPO OPS key + secret. The extraction model is not chosen yet: see "Local model selection" above.
