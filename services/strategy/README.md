# services/strategy

Strategy plugins (`auspex_strategy`) and `strategy-runtime`, the service that runs them on corroborations into virtual books, checks their intents against the risk layer, traces each decision and serves per-version strategy metrics. Its requirements are owned by [docs/strategy/](../../docs/strategy/).

Commands, the kill switch included: [AGENTS.md](AGENTS.md).

---

## Layout

| Package | Holds | Owner |
|---|---|---|
| `abc.py`, `models.py`, `registry.py`, `strategies/` | The `Strategy` contract, `AsOfContext`, `TradeIntent`, the registry and the seed strategies | [contract.md](../../docs/strategy/contract.md) |
| `runtime/` | `BacktestReplayRunner`, `StreamingRuntime`, `IsolatedDecider`, `InputHealthMonitor`, `OverlapDetector`, `LatencyTracer`, `PaperBroker` / `VirtualBook`, `PassThroughRiskManager`, `FunnelCounter`, the HTTP API | [runtime.md](../../docs/strategy/runtime.md) |
| `risk/` | `KellySizer`, position limits, `BinaryEventGuard`, `ShortGuard`, `DrawdownAndFlowLimits`, `KillSwitch`, `RiskManager`, `PortfolioRiskReview` | [risk.md](../../docs/strategy/risk.md) |
| `trace/` | `TraceRecord`, `TraceValidator`, `TraceStore`, `DecisionTracer`, `TraceReplayer` | [decision-trace.md](../../docs/strategy/decision-trace.md) |
| `metrics/` | `ActivityFunnel`, `TradeMetrics`, `ReturnMetrics`, `BacktestPaperComparison`, `CorrelationMatrix`, `LatencyMetrics` | [runtime.md](../../docs/strategy/runtime.md) |

Strategy configuration lives at the repository root: `config/strategies/` and `config/themes.yaml`. The risk limits are the "Risk limits" group of `.env.example`. The runtime's state (books, funnel counts, pauses, latency, offsets, traces, kill switch flags) is in the `auspex-strategy` bucket; the keys are listed in [runtime.md](../../docs/strategy/runtime.md).

The image builds with `services/` as its context (`services/strategy/Dockerfile`), because it installs `services/backtesting` from source.
