from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml


class ThemeMap:
    """Ticker -> correlated theme, from `config/themes.yaml`. A ticker missing from the map
    has no theme, which the risk layer treats as a rejection, never as uncorrelated."""

    def __init__(self, themes: Mapping[str, str]) -> None:
        self._themes = dict(themes)

    @classmethod
    def load(cls, path: Path) -> ThemeMap:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls({str(k): str(v) for k, v in (data.get("tickers") or {}).items()})

    def theme(self, ticker: str) -> str | None:
        return self._themes.get(ticker)

    def tickers(self) -> frozenset[str]:
        return frozenset(self._themes)
