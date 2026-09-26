from __future__ import annotations

from datetime import datetime


class AsOfViolationError(Exception):
    def __init__(self, corroborated_at: datetime, as_of: datetime, known_at: datetime) -> None:
        super().__init__(
            f"record corroborated_at={corroborated_at.isoformat()} "
            f"not yet known at as_of={as_of.isoformat()} "
            f"(known_at={known_at.isoformat()})"
        )
        self.corroborated_at = corroborated_at
        self.as_of = as_of
        self.known_at = known_at


class HypothesisNotRegisteredError(Exception):
    pass


class VersionConflictError(Exception):
    def __init__(self, name: str, version: str, reason: str) -> None:
        super().__init__(f"{name} v{version}: {reason}")
        self.name = name
        self.version = version
        self.reason = reason


class StrategyRetiredError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"strategy {name!r} is retired and cannot produce trade intents")
        self.name = name
