"""Builds the catalyst panel for a date range from both sources and reports its coverage.
Safe to repeat: documents already read come from MinIO and rows already stored are skipped."""

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

from auspex_backtesting.catalysts.adcom import AdvisoryCommitteeNotices
from auspex_backtesting.catalysts.panel import CatalystPanel
from auspex_backtesting.catalysts.press_releases import PressReleaseCatalystExtractor
from auspex_backtesting.universe.model import UniverseMember
from auspex_backtesting.universe.store import UniverseStore


class UniverseNotBuiltError(Exception):
    """No universe listings are stored for the rules version, so there is nothing to match."""


def universe_members(store: UniverseStore, rules_version: int) -> list[UniverseMember]:
    """Every company the universe has listed under `rules_version`, once per CIK."""
    stored = store.read_listings(rules_version)
    if stored is None:
        raise UniverseNotBuiltError(
            f"no universe listings under rules version {rules_version}; build the universe first"
        )
    return list({m.cik: m for m in stored[0]}.values())


class CatalystPanelBuild:
    def __init__(
        self,
        panel: CatalystPanel,
        press_releases: PressReleaseCatalystExtractor,
        adcom_notices: AdvisoryCommitteeNotices,
        members: Callable[[], Sequence[UniverseMember]],
    ) -> None:
        self._panel = panel
        self._press_releases = press_releases
        self._adcom_notices = adcom_notices
        self._members = members

    def run(self, since: date, until: date) -> dict[str, Any]:
        """Extracts both sources for `since`..`until`, appends the rows and returns counters
        per source with the panel's coverage. `complete` is false when a source refused
        requests; running again continues from the stored documents."""
        members = self._members()
        edgar = self._press_releases.collect({m.cik for m in members}, since, until)
        added_edgar = self._panel.append(edgar.rows)
        notices = self._adcom_notices.collect(members, since, until)
        added_notices = self._panel.append(notices.rows)
        return {
            "since": since.isoformat(),
            "until": until.isoformat(),
            "complete": not (edgar.stats.get("blocked") or notices.stats.get("blocked")),
            "added": {"edgar": added_edgar, "federal_register": added_notices},
            "edgar": edgar.stats,
            "federal_register": notices.stats,
            "coverage": self._panel.coverage(members),
        }
