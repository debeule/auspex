# Strategy Research — Foundation Layer

**Purpose:** Identify and rank tradeable hypotheses derivable from Auspex corroboration data. Each H-number maps to a pre-registered file in `config/hypotheses/` (hypothesis-registry spec). This document is the reference for those registrations — not a backtest plan or trading strategy.

**Session:** Strategy layer session 1 of 3. Sessions 2 and 3 cover the strategy framework runtime and live trading UI respectively.

---

## Constraints and parameters

These are invariants for all hypotheses. They determine which hypotheses are survivable and how results must be reported.

### Capital and friction
- Capital: few thousand EUR (working assumption: €5,000 deployed)
- Broker: Interactive Brokers
- Round-trip friction estimate (small-cap biotech, NASDAQ): 1.5–3.0% — spread ~0.5–1.5%, IBKR commission ~$0.005/share (minimum $1/order), slippage ~0.5–1.0% for thinly traded names
- Break-even abnormal return (round-trip midpoint): ~2.5%
- Target minimum expected abnormal return per event before committing capital: **≥5%** over the measurement window (after friction, before tax)

### Belgian tax
- TOB (taks op beursverrichtingen): 0.35% per buy + 0.35% per sell for foreign shares on foreign exchanges — 0.70% round-trip additional friction
- CGT: 10% on net taxable gains above €10,000 annual exemption (2026 rate)
- Speculative classification risk: gains taxed at 33% if the SPF Finances classifies trading as speculative. Factors: frequency, size relative to income, use of leverage, short-selling, derivative use. Require qualified Belgian tax advisor confirmation before live trading (see PREREQUISITES.md).
- Short selling: borrow fees 1–8%+ annualised for hard-to-borrow small-cap biotech. Belgian treatment of short-sale gains under the speculative test is unconfirmed. Do not short before obtaining advisor confirmation.
- Effective all-in break-even (below €10k CGT exemption): ~3.2% per trade (2.5% friction + 0.70% TOB; negligible CGT below threshold).

### Benchmark
- Primary: XBI (SPDR S&P Biotech ETF) — sector-matched, liquid, fetchable via yfinance same as OHLCV data
- Secondary (where sample permits): size-matched basket of gene-therapy companies not in the watchlist

### Entry timing
Per `specs/done/point-in-time-alignment.md`: join on `corroborated_at` (the maximum `published_date` of the two corroborating signals). Never join on `ingested_at` or `retrieved_at`. A configurable known-at delay (default 1 business day) is added to simulate realistic ingestion-to-trade latency; sensitivity analysis over 0, 1, 3, 5 days required (see evaluation-protocol spec).

### Data window and sample expectations
- 24-month backfill: September 2024 – September 2026 across five sources (ClinicalTrials.gov, EPO OPS patents, EDGAR 8-K, bioRxiv, PubMed)
- 8 watched companies: SRPT, SPRB, BEAM, CRSP, CAPR, ABVX, RCKT, QURE
- Estimated corroboration event count: 50–150 entity-level events — actual count unknown until the backfill runs
- This is a small sample. Phase 4 is hypothesis-generating research, not hypothesis-confirming.

---

## Hypotheses

For each hypothesis, the table covers: mechanism, signal definition (in Auspex field terms), direction, entry, holding period, exit, benchmark, expected sample size in the 24-month backfill, minimum detectable effect at that sample size (80% power, two-tailed, α=0.05), cost survivability, capacity constraint, and prior evidence.

---

### H1 — Structural convergence premium

| | |
|---|---|
| **Mechanism** | Multi-source corroboration reduces uncertainty about a clinical development. If markets are slow to aggregate signals across heterogeneous specialised sources (Cohen & Lou 2012, "complicated firms"), abnormal returns should follow corroboration by days to weeks. This is the premise of the whole system; H1 is the null hypothesis. |
| **Signal definition** | All corroborations on watched tickers, entity-only variant: `entity_key` + `corroborated_at` + `source_count ≥ 2`. No directionality or confidence filter. |
| **Direction** | Long. The extractor's `is_signal=true` gate is calibrated toward clinical-stage positive events; the dataset skews positive by design. |
| **Entry** | T+1 NYSE open after `corroborated_at + known_at_delay_days` |
| **Holding period** | Test at 5, 10, 20, 30 calendar days simultaneously |
| **Exit** | Fixed horizon close |
| **Benchmark** | XBI cumulative return over same window |
| **Expected sample** | 50–150 events; true count unknown until backfill |
| **MDE (80% power)** | At n=100, 20-day window: ~2.0% mean abnormal return (biotech annualised vol ~80%; 20-day σ ≈ 7%) |
| **Cost survivability** | Probably not at 5-day window (MDE < 2.5% break-even); likely at 20-day window if effect > 3% |
| **Capacity** | €500–2,000 per position before market impact at ADTV of these names |
| **Prior evidence** | Cohen & Lou (2012) slow diffusion for complex firms; Engelberg, Reed & Ringgenberg (2012) short sellers and hard-to-process news; Da, Engelberg & Gao (2011) attention and returns |

---

### H2 — Signal time decay

| | |
|---|---|
| **Mechanism** | Alpha from any information event decays as the market incorporates the signal. The decay curve shape determines optimal holding period and reveals whether early entry (T+1) captures most of the move or whether a longer hold is required. |
| **Signal definition** | H1 events, no additional filter. Abnormal returns measured cumulatively at T+1, T+3, T+5, T+10, T+20, T+30. |
| **Direction** | Long |
| **Entry** | Same as H1 |
| **Holding period** | All six measurement points simultaneously; reported as a decay curve |
| **Exit** | Each measurement is independent; not a real hold decision |
| **Benchmark** | XBI |
| **Expected sample** | Same as H1 |
| **MDE** | Same as H1 per window; unrelated variance accumulates at longer windows |
| **Cost survivability** | Diagnostic: the crossing point of the decay curve and the all-in cost line reveals the minimum holding period for positive net expectancy |
| **Capacity** | Same as H1 |
| **Prior evidence** | Jegadeesh & Titman (1993) momentum decay; Tetlock, Saar-Tsechansky & Macskassy (2008) news effect decay; McLean & Pontiff (2016) anomaly decay |

**Note:** This is an analysis on the H1 event set, not a new event definition. Implement alongside H1.

---

### H3 — Pre-announcement drift

| | |
|---|---|
| **Mechanism** | If `corroborated_at` is a lagging indicator — the second signal was already reflected in price before we observed it — most of the move occurs in the [T−20, T−1] window, and forward returns at T+1 are residual noise. Measuring both windows simultaneously isolates where the alpha sits. |
| **Signal definition** | H1 events; cumulative abnormal return in [T−20, T−1] relative to `corroborated_at` compared against [T+1, T+20]. |
| **Direction** | Diagnostic only |
| **Entry** | Not a tradeable entry |
| **Holding period** | Pre: [−20, −1]; post: [+1, +20] |
| **Exit** | n/a |
| **Benchmark** | XBI |
| **Expected sample** | Same as H1 |
| **MDE** | n/a — diagnostic decomposition |
| **Cost survivability** | n/a |
| **Capacity** | n/a |
| **Prior evidence** | Kandel & Pearson (1995) pre-announcement drift; Savor (2012) asset prices around information events |

**Note:** If the pre-window shows systematic drift in the same direction as the post-window, the strategy is backward-looking and the edge is not forward-implementable. This is the most important gating diagnostic.

---

### H4 — Directional premium over entity-only baseline

| | |
|---|---|
| **Mechanism** | LLM-extracted `directionality` should add information over structural corroboration if the model correctly identifies event direction rather than encoding hindsight. Positive-directional corroborations should show larger positive abnormal returns than entity-only; negative ones should show negative returns. |
| **Signal definition** | H1 events filtered to those where both contributing signals share the same `directionality` value: both `positive` (long) or both `negative` (short). Mixed-directionality pairs excluded. |
| **Direction** | Long (positive pair) or Short (negative pair) |
| **Entry** | Same as H1 |
| **Holding period** | Same as H1 |
| **Exit** | Same as H1 |
| **Benchmark** | XBI |
| **Expected sample** | ~60–100 positive-directional pairs; ~15–30 negative pairs |
| **MDE (80% power)** | At n=80 positive events, 20-day window: ~2.2% mean abnormal return |
| **Cost survivability** | Depends; requires MDE > 2.5% break-even |
| **Capacity** | Same as H1 |
| **Prior evidence** | Tetlock (2007) media pessimism and stock returns; Garcia (2013) sentiment and asset prices |

**Warning:** This is the highest contamination-risk hypothesis. Run the leakage canary (model-evaluation spec 2b) before interpreting results. If H4 substantially outperforms H1, document the delta in DECISIONS.md before drawing conclusions. Negative pairs require short positions — see H8 for operational constraints.

---

### H5 — Source-type composition effect

| | |
|---|---|
| **Mechanism** | Different source-type pairings encode different information. A patent + clinical trial corroboration (early IP + active development) and a clinical trial + academic publication corroboration (results + peer validation) are structurally distinct events with different expected market impact. |
| **Signal definition** | H1 events grouped by the source_type pair of the two contributing signals: (clinicaltrials, pubmed), (clinicaltrials, biorxiv), (clinicaltrials, edgar), (pubmed, biorxiv), (clinicaltrials, patent), (pubmed, patent), (edgar, pubmed). |
| **Direction** | Long |
| **Entry** | Same as H1 |
| **Holding period** | 20-day window |
| **Exit** | Same as H1 |
| **Benchmark** | XBI |
| **Expected sample** | Per-pair: <20 events each for 8 companies over 24 months. Exploratory only. |
| **MDE (80% power)** | At n=20: ~3.5% mean abnormal return — high bar, unreliable at this n |
| **Cost survivability** | Per-group sample too small to support a reliable cost-survivability assessment |
| **Capacity** | Same as H1 |
| **Prior evidence** | Grossman & Stiglitz (1980) information cost hypothesis; Kogan et al. (2017) technological innovation from patent data |

**Note:** The most interesting subhypothesis is patent + clinical trial: patents are earlier in the development pipeline and may predict trial outcomes. Treat all per-group findings as exploratory pending larger sample.

---

### H6 — Gene target novelty premium

| | |
|---|---|
| **Mechanism** | The first corroboration for a company's gene target reduces uncertainty more than repeated confirmation of the same target. Novelty should command a premium as the market re-evaluates the company's pipeline scope. |
| **Signal definition** | H1 events where, within the 24-month window, there is no prior corroboration for the same (ticker, gene_target_from_entity_key) pair. "Novel" = first appearance. |
| **Direction** | Long |
| **Entry** | Same as H1 |
| **Holding period** | 20-day window |
| **Exit** | Same as H1 |
| **Benchmark** | XBI |
| **Expected sample** | ~30–50% of H1 events are first appearances (estimate) |
| **MDE (80% power)** | At n=60 novel events: ~2.5% mean abnormal return |
| **Cost survivability** | Depends on actual effect size |
| **Capacity** | Same as H1 |
| **Prior evidence** | Menzly & Ozbas (2010) industry information and cross-stock returns; Hirshleifer, Hsu & Li (2013) innovative efficiency and stock returns |

---

### H7 — Confidence score gradient

| | |
|---|---|
| **Mechanism** | Higher mean `confidence_score` on a corroborated pair reflects more decisive LLM extraction. If `confidence_score` correlates with true signal strength (rather than with training data knowledge of outcomes), higher-confidence pairs should produce larger abnormal returns. |
| **Signal definition** | H1 events split by above-median vs below-median mean `confidence_score` of the two contributing signals |
| **Direction** | Long |
| **Entry** | Same as H1 |
| **Holding period** | 20-day window |
| **Exit** | Same as H1 |
| **Benchmark** | XBI |
| **Expected sample** | ~50 per group (median split of H1 sample) |
| **MDE (80% power)** | At n=50 per group: ~3.0% mean difference in abnormal return between groups |
| **Cost survivability** | Filter only — not a standalone strategy |
| **Capacity** | Same as H1 |
| **Prior evidence** | Framing effects in analyst forecasts; confidence as a quality signal in automated extraction |

**Warning:** Second most contamination-exposed hypothesis after H4. `confidence_score` is an LLM judgment field; models with training data awareness of outcomes will assign high confidence to those outcomes. Treat as low priority unless the leakage canary is clean.

---

### H8 — Negative directionality asymmetry

| | |
|---|---|
| **Mechanism** | Negative biotech news (trial failure, safety signal, regulatory rejection) produces faster, more concentrated price moves than positive news because sell-side reactions are more binary and less subject to ongoing uncertainty. Negative corroborations should show front-loaded, larger-magnitude abnormal returns that decay within 1–5 days. |
| **Signal definition** | H4 negative subset: both contributing signals have `directionality = 'negative'`. Short position. |
| **Direction** | Short |
| **Entry** | Same as H1 (T+1 open after corroborated_at) |
| **Holding period** | 1, 3, 5 calendar days |
| **Exit** | Fixed horizon close; also test trailing stop |
| **Benchmark** | XBI (inverse — negative abnormal return relative to benchmark is positive for a short) |
| **Expected sample** | 15–30 negative corroborations across 8 companies in 24 months (estimate) |
| **MDE (80% power)** | At n=20: very high bar — not statistically reliable |
| **Cost survivability** | Probably not — borrow fees 1–8%/year + 0.70% TOB + CGT speculative risk |
| **Capacity** | Very limited — hard-to-borrow names often unavailable or prohibitively expensive |
| **Prior evidence** | Dichev & Janes (2003) short-selling around earnings; Safieddine & Wilhelm (1996) short sales and FDA decisions |

**Warning:** Belgian speculative classification risk is highest for short positions. IBKR borrow availability for these names is unverified. Do not design short-side tests until PREREQUISITES.md open items on borrow availability and tax classification are resolved.

---

## Ranking

| Rank | Hypothesis | Rationale |
|---|---|---|
| 1 | H1 — Structural convergence | Validates the premise; entity-only is the cleanest test; best sample size; gates H2–H8 |
| 2 | H2 — Time decay | Determines optimal holding period; free from H1 events; no additional data needed |
| 3 | H3 — Pre-announcement drift | Critical timing diagnostic; gates whether the strategy is forward-implementable |
| 4 | H4 — Directional premium | Tests whether LLM directionality adds value; requires leakage canary first |
| 5 | H5 — Source-type composition | Interesting mechanism; per-group sample is exploratory only |
| 6 | H6 — Gene target novelty | Plausible mechanism; moderate sample; straightforward to implement from H1 |
| 7 | H7 — Confidence gradient | Small subgroups; contamination-exposed; lower priority than structure-based hypotheses |
| 8 | H8 — Negative asymmetry | Short-side operational complexity; very small sample; Belgian tax risk; defer until H1 confirms long-side edge |

### Triage (2026-10-07, supersedes the ranking above for execution order)

The edge feasibility audit found that gene-target corroboration does not map to a company, and that the price reaction to trial and FDA news finishes within one or two days. The hypotheses were re-registered as version 2 with a `role` and `status`, under the evaluation protocol locked in `config/hypotheses/protocol.yaml`.

| Hypothesis | Role | Status | Call |
|---|---|---|---|
| H3 — Pre-announcement drift | diagnostic | pre-registered | Run first. If the pre-window carries the move, the `lagging_signal` kill criterion retires gene-target corroboration as a trading trigger. |
| H2 — Time decay | diagnostic | pre-registered | Free diagnostic on H1 events; never promoted. |
| H1 — Structural convergence | promotable | suspended | Re-register on a company-level event definition. Primary cell fixed now: 20 days, known-at delay 1, entity-only; 32 trial cells. |
| H4 — Directional premium | promotable | suspended | Rework around typed company events (readout positive or negative, CRL, clinical hold). |
| H8 — Negative asymmetry | promotable | suspended | Rework as an exit or avoid filter on long holdings; no shorting. |
| H6 — Gene target novelty | promotable | suspended | Defer; the version worth testing is a first-time company-program event. |
| H5 — Source-type composition | descriptive | pre-registered | Reported as a table; no significance test. |
| H7 — Confidence gradient | descriptive | pre-registered | Reported only; confidence may be used as a declared entry filter. |

Every subgroup below about 50 events is noise at biotech volatility. Only promotable hypotheses count toward the family trial budget of 64 cells.

---

## What the 24-month backfill realistically allows

**One tentative finding.**

With 50–150 corroboration events across 8 small-cap biotech companies over 24 months:

- H1 (structural convergence) is the only hypothesis with a sample large enough for a meaningful test. Even then, at n=100 and biotech's 80% annualised volatility, the minimum detectable effect at a 20-day window is ~2.0% — below the ~3.2% all-in break-even. Statistical significance does not imply economic significance at this sample size.
- H2 (decay curve) and H3 (pre-announcement drift) are free from the H1 event set — they add insight without requiring more data.
- H4–H8 partition the H1 sample into subgroups of 15–80 events each. None is reliable in isolation. Report them, but treat all subgroup findings as exploratory.
- The deflated Sharpe ratio (Bailey & López de Prado 2014) penalises multiple testing on the same corpus. Testing all 8 hypotheses on a single 24-month sample will yield a deflated Sharpe substantially below the raw Sharpe. Promotion requires `t > 3.0` (Harvey, Liu & Zhu 2016 threshold for finance papers) AND `deflated_Sharpe > 0.95`. At n=100, achieving `t > 3` requires a mean abnormal return of ~4.5% at 20-day window with biotech volatility — a high bar.

**Realistic outcome range:**
- Best case: H1 shows `t > 2.0` at the 20-day window with mean abnormal return > 3%. Hypothesis-generating, not confirmatory. Proceed to expand the watchlist and collect more forward data.
- Most likely: H1 `t ∈ [1.0, 2.0]`. Suggestive but inconclusive. The right response is to extend the watchlist to 20–30 companies, deepen the backfill, or wait 12 months for forward data.
- Worst case: H1 `t < 1.0`. No detectable signal at this sample size. Either the mechanism does not hold at this scale, or the sample is too small. Do not allocate capital.

**Phase 4 is hypothesis-generating. A forward period of 12+ months with a larger watchlist, or an expanded backfill covering 30+ companies across the same gene therapy space, is required before capital allocation is appropriate.**
