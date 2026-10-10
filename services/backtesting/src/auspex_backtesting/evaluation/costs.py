from __future__ import annotations

from datetime import date

from auspex_backtesting.evaluation.results import TradeRecord
from auspex_backtesting.market_sim.costs import CostModel
from auspex_backtesting.market_sim.fx import CurrencyConverter
from auspex_backtesting.market_sim.sizing import PositionSizer


class TradeCosts:
    """Prices each event as a long position of `position_eur`, bought at the entry open.

    The gross P&L is the abnormal return on the entry notional; costs come from `CostModel`,
    and both are converted to EUR at the entry date's rate.
    """

    def __init__(self, cost_model: CostModel, fx: CurrencyConverter, position_eur: float) -> None:
        self._cost_model = cost_model
        self._fx = fx
        self._position_eur = position_eur
        self._sizer = PositionSizer()

    def trade(
        self,
        ticker: str,
        entry_date: date,
        exit_date: date,
        entry_price_usd: float,
        abnormal_return: float,
    ) -> TradeRecord:
        eur_per_usd = self._fx.eur_per_usd(entry_date)
        shares = self._sizer.size_shares(self._position_eur, eur_per_usd, entry_price_usd)
        cost = self._cost_model.round_trip_cost_usd(
            ticker,
            entry_price_usd,
            shares,
            is_short=False,
            holding_calendar_days=(exit_date - entry_date).days,
            entry_date=entry_date,
        )
        gross_eur = abnormal_return * entry_price_usd * shares * eur_per_usd
        cost_eur = float(cost) * eur_per_usd
        return TradeRecord(
            ticker=ticker,
            entry_date=entry_date,
            exit_date=exit_date,
            shares=shares,
            entry_price_usd=entry_price_usd,
            abnormal_return=abnormal_return,
            gross_eur=gross_eur,
            cost_eur=cost_eur,
            net_eur=gross_eur - cost_eur,
            costs=cost.components(),
        )
