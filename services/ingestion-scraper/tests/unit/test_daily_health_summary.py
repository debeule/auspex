"""The daily health message: built from Prometheus answers, so tested with canned ones."""

import ast
import sys
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Self

import pytest

DAGS = Path(__file__).resolve().parents[2] / "dags"
sys.path.insert(0, str(DAGS))

import health_summary

_NOW = datetime(2026, 10, 10, 7, 0, tzinfo=UTC)
_SOURCES = ["biorxiv", "edgar", "pubmed", "mock"]


def _query(answers: dict[str, list[tuple[dict[str, str], float]]]) -> health_summary.Query:
    def query(expr: str) -> list[tuple[dict[str, str], float]]:
        (name,) = [n for n, e in health_summary.QUERIES.items() if e == expr]
        return answers.get(name, [])

    return query


def _healthy_day() -> dict[str, list[tuple[dict[str, str], float]]]:
    ran = (_NOW - timedelta(hours=6)).timestamp()
    return {
        "last_run": [
            ({"source_type": "biorxiv"}, ran),
            ({"source_type": "edgar"}, ran),
            ({"source_type": "pubmed"}, (_NOW - timedelta(hours=27)).timestamp()),
        ],
        "fetched": [({"source_type": "biorxiv"}, 412.0), ({"source_type": "edgar"}, 38.0)],
        "published": [({"source_type": "biorxiv"}, 9.0), ({"source_type": "edgar"}, 4.0)],
        "failed": [({"source_type": "edgar"}, 2.0)],
        "dlt_depth": [({"topic": "auspex.signals.extracted.dlt"}, 3.0)],
        "consumer_lag": [({"consumergroup": "corehub", "topic": "auspex.raw.ingested"}, 12.0)],
        "price_sessions_behind": [({}, 0.0)],
        "restarts": [({"name": "auspex-core-hub"}, 2.0)],
        "vm_disk_free_pct": [({}, 41.5)],
        "vm_disk_used_growth_bytes": [({}, 1.5 * 2**30)],
        "mac_swap_used_bytes": [({}, 512 * 2**20)],
        "alerts_open": [({}, 1.0)],
        "alerts_peak": [({}, 3.0)],
    }


def test_daily_summary_lists_every_live_source_with_its_counts() -> None:
    summary = health_summary.build_summary(_SOURCES, _query(_healthy_day()), _NOW)
    subject, body = health_summary.render(summary)

    assert subject.startswith("Auspex daily health 2026-10-10")
    by_source = {s.source_type: s for s in summary.sources}
    assert set(by_source) == set(_SOURCES)
    assert (by_source["biorxiv"].fetched, by_source["biorxiv"].published, by_source["biorxiv"].failed) == (
        412,
        9,
        0,
    )
    assert (by_source["edgar"].fetched, by_source["edgar"].published, by_source["edgar"].failed) == (38, 4, 2)
    assert "biorxiv: last run 2026-10-10 01:00 UTC, 412 fetched, 9 published, 0 failed" in body
    assert "edgar: last run 2026-10-10 01:00 UTC, 38 fetched, 4 published, 2 failed" in body
    for line in (
        "auspex.signals.extracted.dlt: 3",
        "corehub on auspex.raw.ingested: 12",
        "Price refresh: 0 sessions behind",
        "auspex-core-hub: 2",
        "VM disk: 41.5% free, 1.5 GiB used since yesterday",
        "Mac swap: 0.5 GiB used",
        "Alerts: 1 open now, at most 3 at once in the last 24 h",
    ):
        assert line in body, line


def test_daily_summary_marks_a_source_without_a_run_in_twenty_six_hours() -> None:
    summary = health_summary.build_summary(_SOURCES, _query(_healthy_day()), _NOW)
    subject, body = health_summary.render(summary)

    stale = {s.source_type for s in summary.sources if s.stale}
    assert stale == {"pubmed"}
    assert "NO RUN IN 26 H pubmed: last run 2026-10-09 04:00 UTC" in body
    # A source with no run in the 30-day lookback is listed as never run, not as stale: its DAG
    # has not been switched on.
    assert "Not run in 30 days: mock" in body
    assert "1 source without a run in 26 h" in subject


def test_daily_summary_reports_missing_answers_as_unknown() -> None:
    summary = health_summary.build_summary(["biorxiv"], _query({}), _NOW)
    _, body = health_summary.render(summary)

    assert "Price refresh: unknown" in body
    assert "VM disk: unknown" in body
    assert "Mac swap: unknown" in body
    assert "Dead letters: none" in body


def test_daily_summary_dag_runs_once_a_day_at_seven_utc() -> None:
    tree = ast.parse((DAGS / "daily_health.py").read_text(encoding="utf-8"))
    dags = [
        call
        for call in ast.walk(tree)
        if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "DAG"
    ]
    assert len(dags) == 1
    kwargs = {k.arg: k.value for k in dags[0].keywords}
    assert ast.literal_eval(kwargs["dag_id"]) == "auspex_daily_health"
    assert ast.literal_eval(kwargs["schedule"]) == "0 7 * * *"
    assert ast.literal_eval(kwargs["catchup"]) is False
    # Runs without anyone unpausing it: its absence is the signal that the stack is down.
    assert ast.literal_eval(kwargs["is_paused_upon_creation"]) is False


def test_summary_is_emailed_to_every_address() -> None:
    sent: list[EmailMessage] = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            assert (host, port) == ("smtp.example.org", 587)

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def starttls(self) -> None:
            return None

        def login(self, user: str, password: str) -> None:
            assert (user, password) == ("auspex", "secret")

        def send_message(self, message: EmailMessage) -> None:
            sent.append(message)

    health_summary.deliver(
        "subject",
        "body",
        {
            "ALERT_CONTACT_TYPE": "email",
            "ALERT_EMAIL_ADDRESSES": "a@example.org, b@example.org",
            "SMTP_HOST": "smtp.example.org:587",
            "SMTP_USER": "auspex",
            "SMTP_PASSWORD": "secret",
            "SMTP_FROM_ADDRESS": "auspex@example.org",
        },
        smtp=FakeSmtp,
    )

    assert len(sent) == 1
    assert sent[0]["To"] == "a@example.org, b@example.org"
    assert sent[0]["Subject"] == "subject"
    assert sent[0].get_content().strip() == "body"


def test_summary_is_posted_to_the_webhook() -> None:
    posts: list[tuple[str, dict[str, str]]] = []

    health_summary.deliver(
        "subject",
        "body",
        {"ALERT_CONTACT_TYPE": "webhook", "ALERT_WEBHOOK_URL": "https://hooks.example.org/x"},
        post=lambda url, payload: posts.append((url, payload)),
    )

    assert posts == [("https://hooks.example.org/x", {"title": "subject", "message": "body"})]


def test_unknown_contact_type_raises() -> None:
    with pytest.raises(ValueError, match="ALERT_CONTACT_TYPE"):
        health_summary.deliver("s", "b", {"ALERT_CONTACT_TYPE": "pager"})
