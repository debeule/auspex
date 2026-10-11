from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

import pandas as pd


class CorrelationMatrix:
    @staticmethod
    def compute(
        returns_by_version: Mapping[str, Sequence[tuple[date, float]]],
        min_trades: int,
    ) -> pd.DataFrame:
        """Pairwise Pearson correlation of trade-level abnormal returns, keyed by strategy
        version label, in the mapping's order.

        Returns are aligned on trade close dates (trades closing the same day are summed); a
        version with no trade closing on a date counts 0 there. Versions with fewer than
        `min_trades` closed trades are left out.
        """
        columns = {}
        for label, returns in returns_by_version.items():
            if len(returns) < min_trades:
                continue
            series = pd.Series([v for _, v in returns], index=[d for d, _ in returns], dtype=float)
            columns[label] = series.groupby(level=0).sum()
        if not columns:
            return pd.DataFrame(dtype=float)
        aligned = pd.DataFrame(columns).sort_index().fillna(0.0)
        return aligned.corr(method="pearson")
