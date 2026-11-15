import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from auspex_backtesting.backtest.episodes import (
    EntityRules,
    IndependentSources,
    build_episodes,
)
from auspex_backtesting.backtest.runner import BacktestEvent, BacktestRunner

_REPO = Path(__file__).resolve().parents[4]
_CASES = json.loads(
    (_REPO / "services/core-hub/src/test/resources/corroboration/episode-cases.json").read_text(
        encoding="utf-8"
    )
)
_RULES_FILE = _REPO / "config" / "corroboration" / "entity-rules.yaml"


@dataclass(frozen=True)
class _Signal:
    event_id: str
    source_type: str
    published_date: datetime
    title: str | None


def _case_rules() -> EntityRules:
    return EntityRules.from_mapping(_CASES["rules"], "case-file")


def _instant(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=UTC)


def _event(
    event_id: str, source_type: str, published: str, gene_target: str = "DMD",
    title: str | None = None, ticker: str = "SRPT",
) -> BacktestEvent:
    return BacktestEvent(
        event_id=event_id,
        ticker=ticker,
        published_date=_dt(published),
        raw_object_key=f"raw/{source_type}/{event_id}.json",
        gene_target=gene_target,
        source_type=source_type,
        directionality="positive",
        confidence_score=0.8,
        title=title,
    )


@pytest.mark.parametrize("case", _CASES["key_cases"], ids=lambda c: f"{c['label']}:{c['name']}")
def test_shared_key_cases_produce_their_expected_keys(case: dict[str, str]) -> None:
    assert _case_rules().canonical_key(case["label"], case["name"]) == case["key"]


@pytest.mark.parametrize("case", _CASES["episode_cases"], ids=lambda c: c["name"])
def test_shared_episode_cases_produce_their_expected_episodes(case: dict[str, object]) -> None:
    independence = IndependentSources(_case_rules().same_finding)
    signals = [
        _Signal(s["event_id"], s["source_type"], _instant(s["published_date"]), s["title"])
        for s in case["signals"]  # type: ignore[attr-defined]
    ]

    episodes = build_episodes(signals, independence)

    assert [
        {
            "episode_opened_at": e.opened_at,
            "participants": sorted(p.event_id for p in e.participants),
            "distinct_source_count": independence.count(e.participants),
        }
        for e in episodes
    ] == [
        {**expected, "episode_opened_at": _instant(expected["episode_opened_at"])}
        for expected in case["episodes"]  # type: ignore[attr-defined]
    ]


def test_backtest_event_fires_at_the_episode_opening_not_at_a_later_joiner() -> None:
    events = [
        _event("a", "pubmed", "2023-01-09T00:00:00"),
        _event("b", "clinicaltrials", "2023-02-09T00:00:00"),
        _event("c", "edgar", "2023-03-09T00:00:00"),
    ]

    report = BacktestRunner(windows=(5,), rules=_case_rules()).run(events, {})

    assert report.entity_only is not None
    (group,) = report.entity_only.groups
    assert group.corroborated_at == _dt("2023-02-09T00:00:00")
    assert group.participant_event_ids == ("a", "b")


def test_joiner_evidence_is_not_reused_to_open_the_next_event() -> None:
    events = [
        _event("a", "biorxiv", "2023-01-09T00:00:00"),
        _event("b", "edgar", "2023-02-01T00:00:00"),
        _event("c", "clinicaltrials", "2023-04-20T00:00:00"),  # joins the episode opened at b
        _event("d", "pubmed", "2023-06-01T00:00:00"),  # after the episode closed; c is spent
    ]

    report = BacktestRunner(windows=(5,), rules=_case_rules()).run(events, {})

    assert report.entity_only is not None
    assert [g.participant_event_ids for g in report.entity_only.groups] == [("a", "b")]


def test_excluded_entity_produces_no_backtest_event() -> None:
    rules = EntityRules.from_mapping(
        {**_CASES["rules"], "excluded": {"GeneTarget": ["DMD"], "Mechanism": []}}, "excludes-dmd"
    )
    events = [
        _event("a", "pubmed", "2023-01-09T00:00:00", gene_target="dmd"),
        _event("b", "clinicaltrials", "2023-02-09T00:00:00", gene_target="D-M-D"),
    ]

    report = BacktestRunner(windows=(5,), rules=rules).run(events, {})

    assert report.entity_only is not None
    assert report.entity_only.groups == ()
    assert BacktestRunner(windows=(5,), rules=_case_rules()).run(events, {}).entity_only.groups


def test_preprint_and_its_paper_alone_produce_no_backtest_event() -> None:
    rules = EntityRules.load(_RULES_FILE.read_bytes())
    events = [
        _event("a", "biorxiv", "2023-01-09T00:00:00",
               title="CRISPR base editing restores HBB expression in mice"),
        _event("b", "pubmed", "2023-02-09T00:00:00",
               title="CRISPR Base-Editing Restores HBB Expression in Mice."),
    ]

    report = BacktestRunner(windows=(5,), rules=rules).run(events, {})

    assert report.entity_only is not None
    assert report.entity_only.groups == ()
