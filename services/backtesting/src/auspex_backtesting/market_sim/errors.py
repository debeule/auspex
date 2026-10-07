class PriceDataAbsentError(LookupError):
    """No snapshot row for the requested ticker and date. Never filled in from a live source."""


class MissingPriceDataError(LookupError):
    """A ticker in the backtest universe has no snapshot covering the requested range."""


class PositionTooSmallError(ValueError):
    """The capital cannot buy a single whole share at the given FX rate and price."""
