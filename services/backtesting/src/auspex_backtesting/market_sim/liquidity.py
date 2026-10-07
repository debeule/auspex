import math
import os
from datetime import date

from auspex_backtesting.market_sim._snapshots import bars_before
from auspex_backtesting.market_sim.errors import PriceDataAbsentError
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore

SPREAD_LOOKBACK_SESSIONS = 21  # about one trading month
ADV_LOOKBACK_SESSIONS = 20


class SpreadEstimator:
    """Per-ticker bid-ask spread from daily close, high and low (Abdi and Ranaldo 2017).

    With `c` the log close and `eta` the log high-low midpoint, the squared spread is
    `4 * mean((c_t - eta_t) * (c_t - eta_{t+1}))` over consecutive sessions. A negative mean,
    which happens on quiet liquid names, is read as zero; `CostModel` applies the floor.
    Only bars before `as_of` are used, so the estimate is known when the order is placed.
    """

    def __init__(
        self, store: PriceSnapshotStore, lookback_sessions: int = SPREAD_LOOKBACK_SESSIONS
    ) -> None:
        self._store = store
        self._lookback = lookback_sessions

    def half_spread(self, ticker: str, as_of: date) -> float:
        """Half the proportional spread, the cost of crossing it once (one leg)."""
        bars = bars_before(self._store, ticker, as_of, self._lookback)[["close", "high", "low"]]
        # Provider gaps show up as NaN or zero prices; a log of either would poison the mean.
        bars = bars[(bars > 0).all(axis=1)]
        if len(bars) < 2:
            raise PriceDataAbsentError(
                f"{ticker}: need 2 sessions with valid prices before {as_of.isoformat()}, "
                f"found {len(bars)}"
            )
        c = [math.log(v) for v in bars["close"]]
        eta = [
            (math.log(h) + math.log(lo)) / 2
            for h, lo in zip(bars["high"], bars["low"], strict=True)
        ]
        products = [(c[t] - eta[t]) * (c[t] - eta[t + 1]) for t in range(len(bars) - 1)]
        squared = 4 * sum(products) / len(products)
        return math.sqrt(max(squared, 0.0)) / 2


class VolumeCap:
    """Largest order that stays a small fraction of a ticker's average daily volume.

    Above roughly 1 to 2% of ADV a retail order starts to move a thin name, which the
    open and close fills cannot represent; capping size keeps fills plausible instead.
    """

    def __init__(
        self,
        store: PriceSnapshotStore,
        max_adv_fraction: float | None = None,
        lookback_sessions: int = ADV_LOOKBACK_SESSIONS,
    ) -> None:
        self._store = store
        self._fraction = (
            max_adv_fraction
            if max_adv_fraction is not None
            else float(os.environ.get("MAX_ADV_FRACTION", "0.01"))
        )
        self._lookback = lookback_sessions

    def max_shares(self, ticker: str, as_of: date) -> int:
        volume = bars_before(self._store, ticker, as_of, self._lookback)["volume"].dropna()
        if volume.empty:
            raise PriceDataAbsentError(f"{ticker}: no volume before {as_of.isoformat()}")
        return math.floor(float(volume.mean()) * self._fraction)
