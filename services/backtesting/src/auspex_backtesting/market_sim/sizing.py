import math

from auspex_backtesting.market_sim.errors import PositionTooSmallError


class PositionSizer:
    def size_shares(self, capital_eur: float, fx_rate: float, price_usd: float) -> int:
        """Whole shares affordable with `capital_eur`.

        `fx_rate` is EUR per 1 USD (`CurrencyConverter.eur_per_usd`), so `capital_eur / fx_rate`
        is USD. Passing the raw EURUSD=X close (USD per EUR) here would undersize every position.
        """
        shares = math.floor(capital_eur / fx_rate / price_usd)
        if shares < 1:
            raise PositionTooSmallError(
                f"{capital_eur} EUR buys no whole share at {price_usd} USD (fx_rate {fx_rate})"
            )
        return shares

