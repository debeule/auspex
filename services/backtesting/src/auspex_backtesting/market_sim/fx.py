from datetime import date

from auspex_backtesting.market_sim._snapshots import price_on
from auspex_backtesting.prices.snapshot_store import PriceSnapshotStore

# Yahoo quotes EURUSD=X as USD per 1 EUR. Fetched through PriceFetcher like any OHLCV series.
FX_TICKER = "EURUSD=X"


class CurrencyConverter:
    def __init__(self, store: PriceSnapshotStore) -> None:
        self._store = store

    def usd_to_eur(self, amount_usd: float, d: date) -> float:
        return amount_usd * self.eur_per_usd(d)

    def eur_per_usd(self, d: date) -> float:
        """The `fx_rate` PositionSizer expects: EUR for 1 USD on `d`, from the daily close."""
        return 1.0 / price_on(self._store, FX_TICKER, d, "close")
