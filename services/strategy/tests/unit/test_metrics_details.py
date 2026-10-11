from auspex_strategy.metrics import TradeMetrics, version_trades
from auspex_strategy.runtime import BookMode

from .metrics_fakes import ToyMarket


def test_a_break_even_trade_counts_as_a_loss_not_a_win() -> None:
    market = ToyMarket()
    # Exit at the entry price with no costs: exactly zero P&L.
    market.trade("toy", "1.0", BookMode.PAPER, ticker="FLAT", exit_price=100.0, costs_usd=0.0)
    market.trade("toy", "1.0", BookMode.PAPER, ticker="UP", exit_price=110.0)

    metrics = TradeMetrics.compute(
        version_trades(market.objects, "toy", "1.0", BookMode.PAPER), min_trades=2
    )

    assert (metrics.n_wins, metrics.n_losses, metrics.hit_rate) == (1, 1, 0.5)
    assert metrics.avg_loss_eur == 0.0
