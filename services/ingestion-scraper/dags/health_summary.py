"""The daily health message: asks Prometheus for the day's numbers, formats them, and sends them
through the same email or webhook settings as Grafana's alerts.

No Airflow import, so it is tested on its own. The message arriving is itself the check: when it
does not come, the stack or the Mac is down, which no alert running on that stack can report.
"""

from __future__ import annotations

import smtplib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any

import requests

Sample = tuple[dict[str, str], float]
Query = Callable[[str], list[Sample]]

# A source runs daily; 26 hours leaves two hours for a slow run before it is marked.
STALE_AFTER = timedelta(hours=26)

_DISK = 'node_filesystem_{0}_bytes{{job="node-exporter", fstype=~"ext4|xfs|btrfs"}}'
_ALERTING = 'sum(grafana_alerting_alerts{state="alerting"})'

QUERIES: dict[str, str] = {
    # 30 days back, so a run from before a scraper restart (which drops the gauge) still counts.
    "last_run": "max by (source_type) (max_over_time(auspex_pipeline_run_last_timestamp[30d]))",
    "fetched": "sum by (source_type) (increase(auspex_pipeline_documents_fetched_total[24h]))",
    "published": "sum by (source_type) (increase(auspex_pipeline_signals_published_total[24h]))",
    "failed": "sum by (source_type) (increase(auspex_pipeline_documents_failed_total[24h]))",
    "dlt_depth": "max by (topic) (auspex_dlt_depth)",
    "consumer_lag": "sum by (consumergroup, topic) (kafka_consumergroup_lag)",
    "price_sessions_behind": "max(auspex_price_refresh_sessions_since_success)",
    "restarts": 'max by (name) (changes(container_start_time_seconds{name=~"auspex-.+"}[24h])) > 0',
    "vm_disk_free_pct": f"100 * min({_DISK.format('avail')} / {_DISK.format('size')})",
    "vm_disk_used_growth_bytes": (
        f"min({_DISK.format('avail')} offset 1d) - min({_DISK.format('avail')})"
    ),
    "mac_swap_used_bytes": 'max(node_memory_swap_used_bytes{job="mac-host"})',
    "alerts_open": _ALERTING,
    "alerts_peak": f"max_over_time({_ALERTING}[24h:5m])",
}


@dataclass(frozen=True)
class SourceLine:
    source_type: str
    last_run: datetime | None
    fetched: int
    published: int
    failed: int
    stale: bool


@dataclass(frozen=True)
class Summary:
    day: datetime
    sources: list[SourceLine]
    dlt_depth: dict[str, int]
    consumer_lag: dict[str, int]
    price_sessions_behind: int | None
    restarts: dict[str, int]
    vm_disk_free_pct: float | None
    vm_disk_used_growth_bytes: float | None
    mac_swap_used_bytes: float | None
    alerts_open: int | None
    alerts_peak: int | None


def build_summary(sources: list[str], query: Query, now: datetime) -> Summary:
    """`sources` are the configured source types; each gets a line whether or not it ran."""
    answers = {name: query(expr) for name, expr in QUERIES.items()}

    def by(name: str, label: str) -> dict[str, float]:
        return {labels.get(label, ""): value for labels, value in answers[name]}

    def single(name: str) -> float | None:
        values = [value for _, value in answers[name]]
        return values[0] if values else None

    last_runs = by("last_run", "source_type")
    fetched, published, failed = by("fetched", "source_type"), by("published", "source_type"), by(
        "failed", "source_type"
    )
    lines = []
    for source in sources:
        last = last_runs.get(source)
        last_run = datetime.fromtimestamp(last, UTC) if last is not None else None
        lines.append(
            SourceLine(
                source_type=source,
                last_run=last_run,
                fetched=round(fetched.get(source, 0)),
                published=round(published.get(source, 0)),
                failed=round(failed.get(source, 0)),
                stale=last_run is not None and now - last_run > STALE_AFTER,
            )
        )
    lag = {
        f"{labels.get('consumergroup', '?')} on {labels.get('topic', '?')}": round(value)
        for labels, value in answers["consumer_lag"]
    }
    sessions = single("price_sessions_behind")
    alerts_open, alerts_peak = single("alerts_open"), single("alerts_peak")
    return Summary(
        day=now,
        sources=lines,
        dlt_depth={topic: round(v) for topic, v in by("dlt_depth", "topic").items()},
        consumer_lag=lag,
        price_sessions_behind=round(sessions) if sessions is not None else None,
        restarts={name: round(v) for name, v in by("restarts", "name").items()},
        vm_disk_free_pct=single("vm_disk_free_pct"),
        vm_disk_used_growth_bytes=single("vm_disk_used_growth_bytes"),
        mac_swap_used_bytes=single("mac_swap_used_bytes"),
        alerts_open=round(alerts_open) if alerts_open is not None else None,
        alerts_peak=round(alerts_peak) if alerts_peak is not None else None,
    )


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _gib(value: float) -> str:
    return f"{value / 2**30:.1f} GiB"


def render(summary: Summary) -> tuple[str, str]:
    """Subject and plain-text body."""
    stale = [s for s in summary.sources if s.stale]
    never = [s.source_type for s in summary.sources if s.last_run is None]
    subject = f"Auspex daily health {summary.day:%Y-%m-%d}"
    if stale:
        subject += f": {len(stale)} source{'s' if len(stale) > 1 else ''} without a run in 26 h"

    body = ["Sources (last 24 h)"]
    for s in summary.sources:
        if s.last_run is None:
            continue
        mark = "NO RUN IN 26 H " if s.stale else ""
        body.append(
            f"  {mark}{s.source_type}: last run {_utc(s.last_run)}, {s.fetched} fetched, "
            f"{s.published} published, {s.failed} failed"
        )
    if never:
        body.append(f"  Not run in 30 days: {', '.join(never)}")

    body.append("")
    if summary.dlt_depth and any(summary.dlt_depth.values()):
        body.append("Dead letters not replayed")
        body += [f"  {topic}: {depth}" for topic, depth in sorted(summary.dlt_depth.items())]
    else:
        body.append("Dead letters: none")
    body.append("Consumer lag")
    body += [f"  {key}: {lag}" for key, lag in sorted(summary.consumer_lag.items())] or ["  unknown"]
    body.append(
        "Price refresh: unknown"
        if summary.price_sessions_behind is None
        else f"Price refresh: {summary.price_sessions_behind} sessions behind"
    )
    body.append("Container restarts in 24 h")
    body += [f"  {name}: {n}" for name, n in sorted(summary.restarts.items())] or ["  none"]
    if summary.vm_disk_free_pct is None:
        body.append("VM disk: unknown")
    else:
        growth = summary.vm_disk_used_growth_bytes
        since = f", {_gib(growth)} used since yesterday" if growth is not None else ""
        body.append(f"VM disk: {summary.vm_disk_free_pct:.1f}% free{since}")
    body.append(
        "Mac swap: unknown"
        if summary.mac_swap_used_bytes is None
        else f"Mac swap: {_gib(summary.mac_swap_used_bytes)} used"
    )
    body.append(
        "Alerts: unknown"
        if summary.alerts_open is None
        else f"Alerts: {summary.alerts_open} open now, "
        f"at most {summary.alerts_peak if summary.alerts_peak is not None else '?'} at once in the last 24 h"
    )
    return subject, "\n".join(body) + "\n"


def prometheus_query(base_url: str) -> Query:
    """Instant queries against Prometheus' HTTP API."""

    def query(expr: str) -> list[Sample]:
        resp = requests.get(f"{base_url}/api/v1/query", params={"query": expr}, timeout=30)
        resp.raise_for_status()
        return [
            (item["metric"], float(item["value"][1]))
            for item in resp.json()["data"]["result"]
        ]

    return query


def _post_json(url: str, payload: dict[str, str]) -> None:
    requests.post(url, json=payload, timeout=30).raise_for_status()


def deliver(
    subject: str,
    body: str,
    env: Mapping[str, str],
    *,
    smtp: Callable[..., Any] = smtplib.SMTP,
    post: Callable[[str, dict[str, str]], None] = _post_json,
) -> None:
    """Sends through the contact Grafana uses: `ALERT_CONTACT_TYPE` email or webhook."""
    kind = env.get("ALERT_CONTACT_TYPE", "")
    if kind == "webhook":
        post(env["ALERT_WEBHOOK_URL"], {"title": subject, "message": body})
        return
    if kind != "email":
        raise ValueError(f"ALERT_CONTACT_TYPE must be email or webhook, not {kind!r}")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = env["SMTP_FROM_ADDRESS"]
    message["To"] = ", ".join(a.strip() for a in env["ALERT_EMAIL_ADDRESSES"].split(",") if a.strip())
    message.set_content(body)
    host, _, port = env["SMTP_HOST"].partition(":")
    with smtp(host, int(port or 587), timeout=60) as server:
        server.starttls()
        if env.get("SMTP_USER"):
            server.login(env["SMTP_USER"], env.get("SMTP_PASSWORD", ""))
        server.send_message(message)
