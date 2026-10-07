"""Historical backfill runner.

Drives `IngestionPipeline.run(source_type, cursor)` over bounded historical date
windows. Everything specific to a backfill lives here, not in the pipeline or
connectors: the model-cutoff guard, cost/time estimation, ceilings, per-window
checkpoints and the run manifest.

Writes only to MinIO (`backfill/…` objects here; the pipeline writes its own
archive and Kafka). Never reads or writes the live Airflow cursor.
"""
from __future__ import annotations

import calendar
import io
import json
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import httpx
from minio.error import S3Error

from .connectors.base import SourceConnector
from .prefilter import Prefilter

# Same estimate the extraction backend uses for its context-length guard.
_CHARS_PER_TOKEN = 4
_MAX_CONTENT_CHARS = 4_000
_RESPONSE_BUDGET_TOKENS = 512

MANIFEST_PREFIX = "backfill/manifests/"
CHECKPOINT_PREFIX = "backfill/checkpoints/"


class CutoffGuardError(Exception):
    pass


class CeilingExceededError(Exception):
    pass


class MissingLatencyRecordError(Exception):
    pass


class BackfillConfigurationError(Exception):
    pass


def model_slug(model_id: str) -> str:
    """Filename-safe model id; matches evaluate_model.py's latency record naming."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", model_id)


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass(frozen=True)
class Window:
    start: date  # inclusive
    end: date  # inclusive

    @property
    def label(self) -> str:
        return f"{self.start.isoformat()}_{self.end.isoformat()}"


def plan_windows(start: date, end: date, window_days: int) -> list[Window]:
    if end < start:
        raise BackfillConfigurationError(f"end date {end} is before start date {start}")
    if window_days < 1:
        raise BackfillConfigurationError("window_days must be >= 1")
    windows: list[Window] = []
    cur = start
    while cur <= end:
        w_end = min(cur + timedelta(days=window_days - 1), end)
        windows.append(Window(cur, w_end))
        cur = w_end + timedelta(days=1)
    return windows


def _start_of_day(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    entry: Mapping[str, Any]
    prompt_version: str
    prefilter_version: str
    prompt_tokens: int

    @property
    def backend(self) -> str:
        return str(self.entry["backend"])

    @property
    def cutoff_date(self) -> date:
        return date.fromisoformat(str(self.entry["cutoff_date"]))

    @property
    def lineage(self) -> str:
        return f"{model_slug(self.model_id)}__{self.prompt_version}__{self.prefilter_version}"


def check_cutoff(model: ModelProfile, start: date, margin_months: int) -> None:
    earliest = add_months(model.cutoff_date, margin_months)
    if start < earliest:
        raise CutoffGuardError(
            f"backfill window starts {start.isoformat()}, before model {model.model_id!r} "
            f"training cutoff {model.cutoff_date.isoformat()} + margin {margin_months} months "
            f"(earliest allowed start: {earliest.isoformat()})"
        )


class BackfillStore:
    """Manifest and checkpoint objects in MinIO, under `backfill/`."""

    def __init__(self, *, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def _put_json(self, key: str, payload: Mapping[str, Any]) -> None:
        data = json.dumps(payload, indent=2, sort_keys=True, default=str).encode()
        self._client.put_object(
            self._bucket, key, io.BytesIO(data), len(data), content_type="application/json"
        )

    def _get_json(self, key: str) -> dict[str, Any] | None:
        try:
            response = self._client.get_object(self._bucket, key)
        except S3Error as e:
            if e.code in ("NoSuchKey", "NoSuchObject"):
                return None
            raise
        return dict(json.loads(response.read()))

    def write_manifest(self, run_id: str, manifest: Mapping[str, Any]) -> None:
        self._put_json(f"{MANIFEST_PREFIX}{run_id}.json", manifest)

    def read_manifest(self, run_id: str) -> dict[str, Any] | None:
        return self._get_json(f"{MANIFEST_PREFIX}{run_id}.json")

    def _checkpoint_key(self, lineage: str, source_type: str, window: Window) -> str:
        return f"{CHECKPOINT_PREFIX}{lineage}/{source_type}/{window.label}.json"

    def checkpoint(self, lineage: str, source_type: str, window: Window) -> dict[str, Any] | None:
        return self._get_json(self._checkpoint_key(lineage, source_type, window))

    def mark_window_done(
        self, lineage: str, source_type: str, window: Window, payload: Mapping[str, Any]
    ) -> None:
        self._put_json(self._checkpoint_key(lineage, source_type, window), payload)


class ExtractionHistory(Protocol):
    def models_in_window(self, source_type: str, start: date, end: date) -> dict[str, int]:
        """Documents already extracted in [start, end], counted per extraction_model."""
        ...


class CoreHubExtractionHistory:
    """Reads extraction lineage from core-hub's REST API.

    The scraper never touches Postgres (Invariants 1 & 2); core-hub owns
    `signal_extraction_history` and answers for it.
    """

    def __init__(self, *, base_url: str, http: httpx.Client | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=30.0)

    def models_in_window(self, source_type: str, start: date, end: date) -> dict[str, int]:
        resp = self._http.get(
            f"{self._base_url}/api/v1/extractions/models",
            params={"source_type": source_type, "from": start.isoformat(), "to": end.isoformat()},
        )
        resp.raise_for_status()
        return {row["extraction_model"]: int(row["documents"]) for row in resp.json()}


@dataclass
class SourceEstimate:
    source_type: str
    documents: int = 0
    llm_calls: int = 0
    estimated_input_tokens: int = 0
    estimated_cost_usd: float | None = None
    estimated_llm_hours: float | None = None
    fetch_hours: float = 0.0
    overlap: dict[str, int] = field(default_factory=dict)

    @property
    def estimated_total_hours(self) -> float | None:
        if self.estimated_llm_hours is None:
            return None
        return self.estimated_llm_hours + self.fetch_hours


@dataclass
class DryRunReport:
    run_id: str
    model_id: str
    backend: str
    start: date
    end: date
    margin_months: int
    windows: int
    sources: dict[str, SourceEstimate]

    def render(self) -> str:
        header = (
            f"DRY RUN {self.run_id} — model {self.model_id} ({self.backend}), "
            f"{self.start} → {self.end}, {self.windows} window(s), margin {self.margin_months} months"
        )
        lines = [header]
        for est in self.sources.values():
            lines.append(f"  {est.source_type}:")
            lines.append(f"    documents fetched        {est.documents:,}")
            lines.append(f"    LLM calls after prefilter {est.llm_calls:,}")
            lines.append(f"    estimated input tokens   {est.estimated_input_tokens:,}")
            if est.estimated_cost_usd is not None:
                lines.append(f"    estimated cost           ${est.estimated_cost_usd:,.2f}")
            if est.estimated_llm_hours is not None:
                lines.append(f"    estimated LLM time       {est.estimated_llm_hours:.1f} h")
            lines.append(f"    fetch time (this run)    {est.fetch_hours:.2f} h")
            if est.estimated_total_hours is not None:
                lines.append(f"    estimated total          {est.estimated_total_hours:.1f} h")
            others = {m: n for m, n in est.overlap.items() if m != self.model_id}
            same = est.overlap.get(self.model_id, 0)
            if not est.overlap:
                lines.append("    already extracted        none in window")
            else:
                lines.append(f"    already extracted        {same} under {self.model_id}")
                for m, n in sorted(others.items()):
                    lines.append(f"    under a different model  {n} under {m}  ← re-extract before Phase 4")
        return "\n".join(lines)


@dataclass
class BackfillReport:
    run_id: str
    windows_run: int
    windows_skipped: int
    counts: dict[str, dict[str, int]]


_COUNT_FIELDS = ("fetched", "prefiltered_out", "published", "not_signal", "below_threshold", "failed")


class BackfillRunner:
    def __init__(
        self,
        *,
        model: ModelProfile,
        connector_factory: Callable[[str, datetime], SourceConnector],
        pipeline_factory: Callable[[str, SourceConnector], Any],
        prefilter_factory: Callable[[str], Prefilter],
        store: BackfillStore,
        history: ExtractionHistory,
        latency_dir: Path,
        env: Mapping[str, str],
        now: Callable[[], datetime],
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._model = model
        self._connector_factory = connector_factory
        self._pipeline_factory = pipeline_factory
        self._prefilter_factory = prefilter_factory
        self._store = store
        self._history = history
        self._latency_dir = latency_dir
        self._env = env
        self._now = now
        self._run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)

    def _base_manifest(
        self, run_id: str, source_type: str, start: date, end: date, margin_months: int,
        window_days: int, *, dry_run: bool,
    ) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "dry_run": dry_run,
            "status": "running",
            "started_at": self._now().isoformat(),
            "sources": [source_type],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "window_days": window_days,
            "margin_months": margin_months,
            "model_id": self._model.model_id,
            "backend": self._model.backend,
            "prompt_version": self._model.prompt_version,
            "prefilter_version": self._model.prefilter_version,
            "counts": {},
            "checkpoints": {"completed": [], "skipped": []},
        }

    def _mean_latency_s(self) -> float:
        path = self._latency_dir / f"{model_slug(self._model.model_id)}.json"
        if not path.exists():
            raise MissingLatencyRecordError(
                f"no latency record for local model {self._model.model_id!r} at {path}; "
                f"run scripts/evaluate_model.py --model {self._model.model_id} first"
            )
        return float(json.loads(path.read_text())["mean_latency_s"])

    def _prices(self) -> tuple[float, float]:
        try:
            return (
                float(self._model.entry["input_price_per_mtok"]),
                float(self._model.entry["output_price_per_mtok"]),
            )
        except KeyError as exc:
            raise BackfillConfigurationError(
                f"API model {self._model.model_id!r} has no {exc.args[0]} in the model registry; "
                f"cannot estimate cost"
            ) from exc

    def dry_run(
        self, *, source_type: str, start: date, end: date,
        margin_months: int = 3, window_days: int = 30,
    ) -> DryRunReport:
        check_cutoff(self._model, start, margin_months)
        windows = plan_windows(start, end, window_days)
        # Fail on missing estimation inputs before spending hours fetching.
        latency = self._mean_latency_s() if self._model.backend == "local" else None
        prices = self._prices() if self._model.backend == "api" else None

        run_id = self._run_id_factory()
        manifest = self._base_manifest(
            run_id, source_type, start, end, margin_months, window_days, dry_run=True
        )
        self._store.write_manifest(run_id, manifest)

        prefilter = self._prefilter_factory(source_type)
        est = SourceEstimate(source_type=source_type)
        # Asked first so an unreachable core-hub fails before hours of fetching.
        est.overlap = self._history.models_in_window(source_type, start, end)
        fetch_started = self._now()
        for window in windows:
            connector = self._connector_factory(source_type, _start_of_day(window.end))
            for doc in connector.fetch_since(_start_of_day(window.start)):
                est.documents += 1
                if prefilter.passes(doc):
                    est.llm_calls += 1
                    content_tokens = min(len(doc.raw_content), _MAX_CONTENT_CHARS) // _CHARS_PER_TOKEN
                    est.estimated_input_tokens += self._model.prompt_tokens + content_tokens
        est.fetch_hours = (self._now() - fetch_started).total_seconds() / 3600

        if latency is not None:
            est.estimated_llm_hours = est.llm_calls * latency / 3600
        if prices is not None:
            in_price, out_price = prices
            est.estimated_cost_usd = (
                est.estimated_input_tokens * in_price
                + est.llm_calls * _RESPONSE_BUDGET_TOKENS * out_price
            ) / 1_000_000

        manifest.update(
            status="completed",
            completed_at=self._now().isoformat(),
            windows=len(windows),
            estimate={source_type: asdict(est)},
        )
        self._store.write_manifest(run_id, manifest)
        return DryRunReport(
            run_id=run_id, model_id=self._model.model_id, backend=self._model.backend,
            start=start, end=end, margin_months=margin_months, windows=len(windows),
            sources={source_type: est},
        )

    def _approved_estimate(
        self, estimate_run_id: str, source_type: str, start: date, end: date
    ) -> dict[str, Any]:
        dry = self._store.read_manifest(estimate_run_id)
        if dry is None or not dry.get("dry_run") or dry.get("status") != "completed":
            raise BackfillConfigurationError(
                f"no completed dry run {estimate_run_id!r}; run with --dry-run first and pass "
                f"its run id as --estimate-run-id"
            )
        expected = {
            "sources": [source_type],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "model_id": self._model.model_id,
            "prompt_version": self._model.prompt_version,
            "prefilter_version": self._model.prefilter_version,
        }
        for key, value in expected.items():
            if dry.get(key) != value:
                raise BackfillConfigurationError(
                    f"dry run {estimate_run_id!r} does not match this run: "
                    f"{key}={dry.get(key)!r}, expected {value!r}"
                )
        return dict(dry["estimate"][source_type])

    def _ceiling(self, name: str) -> float:
        raw = self._env.get(name, "").strip()
        if not raw:
            raise BackfillConfigurationError(
                f"{name} must be set in .env for a {self._model.backend} backend live run"
            )
        return float(raw)

    def _check_ceiling(self, estimate: Mapping[str, Any]) -> None:
        if self._model.backend == "api":
            ceiling = self._ceiling("BACKFILL_BUDGET_CEILING")
            cost = float(estimate["estimated_cost_usd"] or 0.0)
            if cost > ceiling:
                raise CeilingExceededError(
                    f"estimated cost ${cost:.2f} for model {self._model.model_id!r} exceeds "
                    f"BACKFILL_BUDGET_CEILING ${ceiling:.2f}"
                )
        else:
            ceiling = self._ceiling("BACKFILL_TIME_CEILING_HOURS")
            hours = float(estimate["estimated_llm_hours"] or 0.0) + float(estimate["fetch_hours"])
            if hours > ceiling:
                raise CeilingExceededError(
                    f"estimated {hours:.1f} h for model {self._model.model_id!r} exceeds "
                    f"BACKFILL_TIME_CEILING_HOURS {ceiling:g} h"
                )

    def run(
        self, *, source_type: str, start: date, end: date, estimate_run_id: str,
        margin_months: int = 3, window_days: int = 30,
    ) -> BackfillReport:
        check_cutoff(self._model, start, margin_months)
        windows = plan_windows(start, end, window_days)
        estimate = self._approved_estimate(estimate_run_id, source_type, start, end)

        run_id = self._run_id_factory()
        manifest = self._base_manifest(
            run_id, source_type, start, end, margin_months, window_days, dry_run=False
        )
        manifest["estimate_run_id"] = estimate_run_id
        self._store.write_manifest(run_id, manifest)

        try:
            self._check_ceiling(estimate)
        except (CeilingExceededError, BackfillConfigurationError) as exc:
            manifest.update(status="aborted", reason=str(exc), completed_at=self._now().isoformat())
            self._store.write_manifest(run_id, manifest)
            raise

        totals = dict.fromkeys(_COUNT_FIELDS, 0)
        manifest["counts"] = {source_type: totals}
        run_count = skipped = 0
        lineage = self._model.lineage
        try:
            for window in windows:
                if self._store.checkpoint(lineage, source_type, window) is not None:
                    skipped += 1
                    manifest["checkpoints"]["skipped"].append(window.label)
                    continue
                connector = self._connector_factory(source_type, _start_of_day(window.end))
                pipeline = self._pipeline_factory(source_type, connector)
                result = pipeline.run(source_type, _start_of_day(window.start))
                counts = {f: int(getattr(result, f, 0)) for f in _COUNT_FIELDS}
                for f in _COUNT_FIELDS:
                    totals[f] += counts[f]
                self._store.mark_window_done(lineage, source_type, window, {
                    "run_id": run_id,
                    "source_type": source_type,
                    "window": window.label,
                    "model_id": self._model.model_id,
                    "completed_at": self._now().isoformat(),
                    "counts": counts,
                })
                run_count += 1
                manifest["checkpoints"]["completed"].append(window.label)
                self._store.write_manifest(run_id, manifest)
        except Exception as exc:
            manifest.update(status="failed", reason=f"{type(exc).__name__}: {exc}",
                            completed_at=self._now().isoformat())
            self._store.write_manifest(run_id, manifest)
            raise

        manifest.update(status="completed", completed_at=self._now().isoformat())
        self._store.write_manifest(run_id, manifest)
        return BackfillReport(
            run_id=run_id, windows_run=run_count, windows_skipped=skipped,
            counts={source_type: totals},
        )
