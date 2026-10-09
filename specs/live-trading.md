# Live Trading

**Status:** draft
**Blocked by:**
1. `specs/forward-paper-trading.md`: a `pass` forward-check verdict at a capital tier for at least one hypothesis. This spec is scoped after that verdict, at that tier. Its tests and definition of done are written then, not now.
2. User actions in `docs/PREREQUISITES.md` ("Strategy layer — required before live trading"): Belgian tax advisor consultation, and an IBKR account opened and funded.
3. The `requirements.md §0.1` amendment (`DECISIONS.md` 2026-09-20 FLAG "requirements.md §0.1 assumption flips at session 3"). It is the first step of scoping this spec, before any live-trading code.

**Branch:** `feature/live-trading`

---

## Context

This draft gathers, in one place on the spec index, pre-live work that today exists only in `DECISIONS.md` and `docs/PREREQUISITES.md`. It does not start any of it early. Paper trading gates real capital (`DECISIONS.md` 2026-10-07 CHOICE "paper trading gates capital, run at several sizes"). The 2026-10-07 CHOICE "deferred items" says the IBKR mechanics belong in a live-trading spec written after a forward check passes.

What exists or is specified:
- `services/strategy`: strategy `status` runs `research` → `paper` → `live-confirm` → `live-auto`. `VirtualBook` with a `mode=live` book (`specs/strategy-runtime.md`).
- `specs/forward-paper-trading.md`: paper ledger per capital tier, `PortfolioRebalance` intents, tracking check.
- `specs/portfolio-and-risk.md`: kill switches and exposure limits, written for event strategies.
- Cost model with IBKR commission schedules and Belgian TOB (`specs/cross-sectional-portfolio-backtest.md`, `specs/done/realistic-cost-model.md`).

## What this builds (to be scoped)

Items already decided or named, to be turned into required tests when scoped:
1. **`requirements.md §0.1` amendment** and a review of the sections that assume research-only use: §0.1, §0.4 and any others the FLAG lists.
2. **Order tickets from paper intents**, `live-confirm` first: each rebalance's intents for the passing tier become limit orders, with the intent id as the order reference. The user confirms each ticket before submission.
3. **IBKR connectivity** (report 2, `/mnt/project-files/research/edge-result-2.md`): limit orders only, weekly re-authentication, and morning reconciliation of fills and positions against the `mode=live` `VirtualBook`.
4. **Live kill switches**: drawdown, reconciliation mismatch and stale input stop new orders. Taken from `portfolio-and-risk` where they apply to a long-only quarterly basket.
5. **Tax record**: per-trade data the Belgian advisor asks for (holding period, TOB paid), recorded from fills.

## Out of scope

Shorts and options, which the protocol disables (`instruments` in `protocol.yaml`). `live-auto` without per-ticket confirmation until a later decision. Capital sizing beyond the tier the forward check passed.

## Constraints

To be completed when scoped. At least these apply: Invariant 2 (no application-DB writes outside core-hub), Invariant 6 (broker credentials only in `.env` and Airflow Connections), and Invariant 9.

## Required tests

Not written. This spec stays `draft` until the forward check passes. A cold session must not implement it.

## Definition of done

Not written (see above).

## Notes

- Open user actions that gate this spec, all in `docs/PREREQUISITES.md` or `DECISIONS.md`: tax advisor conclusion (10% vs 33%), the five Belgian cost points to confirm with an accountant (`/mnt/project-files/research/belgian-costs.md`), and the speculation-risk ruling request before trading at scale.
