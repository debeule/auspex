"""Historical backfill runner tests.

The runner plans date windows, guards the model cutoff, estimates cost/time in a
dry run, enforces ceilings, checkpoints per (source, window) in MinIO, and calls
`IngestionPipeline.run()` once per window. It never touches the live cursor.
"""

from __future__ import annotations

import hashlib
import io
import itertools
import json
import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest
import respx
from httpx import Response
from minio.error import S3Error

from auspex_ingest.backfill import (
    BackfillConfigurationError,
    BackfillRunner,
    BackfillStore,
    CeilingExceededError,
    CutoffGuardError,
    MissingLatencyRecordError,
    ModelProfile,
    plan_windows,
)
from auspex_ingest.connectors import RateLimitedClient
from auspex_ingest.connectors.base import SourceConnector
from auspex_ingest.connectors.registry import build_connector
from auspex_ingest.extraction_backend import BackendLLMExtractor
from auspex_ingest.extractor import _ExtractionResult
from auspex_ingest.identity import compute_event_id
from auspex_ingest.models import RawDocument
from auspex_ingest.normalizer import IdentityNormalizer
from auspex_ingest.pipeline import IngestionPipeline
from auspex_ingest.prefilter import Prefilter

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
_LOCAL_MODEL = "llama3.1:8b-instruct-q8_0"
_API_MODEL = "gpt-4o-mini-2024-07-18"
_VOCAB = frozenset({"CRISPR", "gene therapy"})


# ---------------------------------------------------------------- fakes


class _FakeMinio:
    """Just enough of `minio.Minio` for BackfillStore."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_order: list[str] = []

    def put_object(self, bucket: str, key: str, data: io.BytesIO, length: int, **_: Any) -> None:
        self.objects[key] = data.read()
        self.put_order.append(key)

    def get_object(self, bucket: str, key: str) -> io.BytesIO:
        if key not in self.objects:
            raise S3Error(MagicMock(), "NoSuchKey", "missing", key, "req", "host")
        return io.BytesIO(self.objects[key])


class _FakeHistory:
    def __init__(self, models: dict[str, int] | None = None) -> None:
        self.models = models or {}
        self.calls: list[tuple[str, date, date]] = []

    def models_in_window(self, source_type: str, start: date, end: date) -> dict[str, int]:
        self.calls.append((source_type, start, end))
        return dict(self.models)


class _ListConnector(SourceConnector):
    """Yields the docs whose published_date falls in [cursor, until]."""

    def __init__(self, docs: list[RawDocument], until: datetime) -> None:
        self._docs = docs
        self._until = until

    def fetch_since(self, cursor: datetime) -> Iterator[RawDocument]:
        for d in self._docs:
            if cursor.date() <= d.published_date.date() <= self._until.date():
                yield d


def _doc(n: int, published: date, content: str = "CRISPR editing of BCL11A") -> RawDocument:
    return RawDocument(
        schema_version="1.0",
        external_id=f"biorxiv:10.1101/doc{n}:v1",
        canonical_id=f"doi:10.1101/doc{n}",
        source_type="biorxiv",
        source_url=f"https://example.com/{n}",
        published_date=datetime(published.year, published.month, published.day, tzinfo=UTC),
        raw_content=content,
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        retrieved_at=_NOW,
    )


def _local_profile() -> ModelProfile:
    return ModelProfile(
        model_id=_LOCAL_MODEL,
        entry={"backend": "local", "cutoff_date": "2023-12-01", "digest": "llama3.1@sha256:abc"},
        prompt_version="v1.0",
        prefilter_version="v1.0",
        prompt_tokens=900,
    )


def _api_profile() -> ModelProfile:
    return ModelProfile(
        model_id=_API_MODEL,
        entry={
            "backend": "api",
            "cutoff_date": "2023-10-01",
            "input_price_per_mtok": 0.15,
            "output_price_per_mtok": 0.60,
        },
        prompt_version="v1.0",
        prefilter_version="v1.0",
        prompt_tokens=900,
    )


def _latency_dir(tmp_path: Path, model_id: str = _LOCAL_MODEL, mean: float = 5.0) -> Path:
    d = tmp_path / "latency"
    d.mkdir(exist_ok=True)
    slug = model_id.replace(":", "_")
    (d / f"{slug}.json").write_text(json.dumps({"model_id": model_id, "mean_latency_s": mean}))
    return d


class _Harness:
    """Builds a runner with recording fakes around it."""

    def __init__(
        self,
        tmp_path: Path,
        *,
        docs: list[RawDocument] | None = None,
        profile: ModelProfile | None = None,
        env: dict[str, str] | None = None,
        latency_dir: Path | None = None,
        history: _FakeHistory | None = None,
    ) -> None:
        self.docs = docs if docs is not None else [_doc(1, date(2025, 1, 10)), _doc(2, date(2025, 2, 10))]
        self.minio = _FakeMinio()
        self.store = BackfillStore(client=self.minio, bucket="auspex-raw")
        self.history = history or _FakeHistory()
        self.pipeline_runs: list[tuple[str, datetime]] = []
        self.events: list[str] = []
        self.connector_untils: list[datetime] = []
        self.extractor = MagicMock()
        ids = iter(f"run{i}" for i in range(100))
        self.runner = BackfillRunner(
            model=profile or _local_profile(),
            connector_factory=self._connector_factory,
            pipeline_factory=self._pipeline_factory,
            prefilter_factory=lambda source_type: Prefilter(_VOCAB, version="v1.0"),
            store=self.store,
            history=self.history,
            latency_dir=latency_dir if latency_dir is not None else _latency_dir(tmp_path),
            env=env or {},
            now=lambda: _NOW,
            run_id_factory=lambda: next(ids),
        )

    def _connector_factory(self, source_type: str, until: datetime) -> SourceConnector:
        self.connector_untils.append(until)
        return _ListConnector(self.docs, until)

    def _pipeline_factory(self, source_type: str, connector: SourceConnector) -> Any:
        harness = self

        class _RecordingPipeline:
            def run(self, st: str, cursor: datetime) -> Any:
                harness.events.append("pipeline.run")
                harness.pipeline_runs.append((st, cursor))
                docs = list(connector.fetch_since(cursor))
                result = MagicMock()
                result.fetched = len(docs)
                result.published = len(docs)
                result.prefiltered_out = result.not_signal = result.below_threshold = result.failed = 0
                return result

        return _RecordingPipeline()

    def manifest_keys(self) -> list[str]:
        return [k for k in self.minio.objects if k.startswith("backfill/manifests/")]


_WINDOW = {"source_type": "biorxiv", "start": date(2025, 1, 1), "end": date(2025, 2, 28)}


# ---------------------------------------------------------------- windows


def test_plan_windows_are_contiguous_inclusive_and_cover_the_range() -> None:
    windows = plan_windows(date(2025, 1, 1), date(2025, 3, 5), window_days=30)
    assert windows[0].start == date(2025, 1, 1)
    assert windows[-1].end == date(2025, 3, 5)
    for a, b in itertools.pairwise(windows):
        assert (b.start - a.end).days == 1


# ---------------------------------------------------------------- cutoff guard


def test_cutoff_guard_refuses_window_starting_before_model_cutoff_plus_margin(tmp_path: Path) -> None:
    h = _Harness(tmp_path)
    with pytest.raises(CutoffGuardError) as exc:
        h.runner.dry_run(source_type="biorxiv", start=date(2024, 1, 15), end=date(2024, 6, 30),
                         margin_months=3)
    msg = str(exc.value)
    assert _LOCAL_MODEL in msg
    assert "2023-12-01" in msg
    assert "3" in msg
    assert "2024-01-15" in msg
    assert h.pipeline_runs == []


def test_cutoff_guard_margin_defaults_to_three_months(tmp_path: Path) -> None:
    h = _Harness(tmp_path, docs=[])
    # cutoff 2023-12-01 + 3 months = 2024-03-01
    with pytest.raises(CutoffGuardError):
        h.runner.dry_run(source_type="biorxiv", start=date(2024, 2, 29), end=date(2024, 3, 31))
    report = h.runner.dry_run(source_type="biorxiv", start=date(2024, 3, 1), end=date(2024, 3, 31))
    assert report.margin_months == 3


def test_cutoff_guard_lives_in_runner_not_pipeline() -> None:
    # The pipeline accepts a cursor years before any model's training cutoff.
    connector = _ListConnector([_doc(1, date(2019, 5, 1))], until=datetime(2019, 12, 31, tzinfo=UTC))
    archive = MagicMock()
    archive.put.return_value = ("raw/biorxiv/k.json", True)
    archive.get_canonical_marker.return_value = None
    extractor = MagicMock()
    extractor.extract.return_value = None
    pipeline = IngestionPipeline(
        connector=connector, archive=archive, extractor=extractor, producer=MagicMock(),
        prefilter=Prefilter(_VOCAB), normalizer=IdentityNormalizer(), now=lambda: _NOW,
    )
    result = pipeline.run("biorxiv", datetime(2019, 1, 1, tzinfo=UTC))
    assert result.fetched == 1
    assert result.failed == 0


# ---------------------------------------------------------------- dry run


def test_backfill_dry_run_reports_document_and_call_estimates_without_calling_the_llm(tmp_path: Path) -> None:
    docs = [
        _doc(1, date(2025, 1, 10)),
        _doc(2, date(2025, 1, 20), content="unrelated cardiology paper"),
        _doc(3, date(2025, 2, 10)),
    ]
    h = _Harness(tmp_path, docs=docs, profile=_api_profile())
    report = h.runner.dry_run(**_WINDOW)
    est = report.sources["biorxiv"]
    assert est.documents == 3
    assert est.llm_calls == 2
    assert est.estimated_cost_usd is not None and est.estimated_cost_usd > 0
    assert h.pipeline_runs == []
    h.extractor.assert_not_called()


def test_dry_run_reports_already_extracted_documents_by_model_id(tmp_path: Path) -> None:
    history = _FakeHistory({"gpt-4o-mini-2024-07-18": 7, _LOCAL_MODEL: 2})
    h = _Harness(tmp_path, history=history)
    report = h.runner.dry_run(**_WINDOW)
    overlap = report.sources["biorxiv"].overlap
    assert overlap == {"gpt-4o-mini-2024-07-18": 7, _LOCAL_MODEL: 2}
    assert history.calls == [("biorxiv", date(2025, 1, 1), date(2025, 2, 28))]
    rendered = report.render()
    assert "gpt-4o-mini-2024-07-18" in rendered and "7" in rendered
    assert "different model" in rendered.lower()


def test_dry_run_uses_latency_record_for_local_backend_wall_clock_estimate(tmp_path: Path) -> None:
    h = _Harness(tmp_path, latency_dir=_latency_dir(tmp_path, mean=3600.0))
    report = h.runner.dry_run(**_WINDOW)
    est = report.sources["biorxiv"]
    assert est.llm_calls == 2
    assert est.estimated_llm_hours == pytest.approx(2.0)
    assert est.estimated_cost_usd is None
    assert "2.0" in report.render()
    assert h.pipeline_runs == []


def test_dry_run_fails_loudly_when_no_latency_record_exists_for_local_backend(tmp_path: Path) -> None:
    empty = tmp_path / "no-latency"
    empty.mkdir()
    h = _Harness(tmp_path, latency_dir=empty)
    with pytest.raises(MissingLatencyRecordError) as exc:
        h.runner.dry_run(**_WINDOW)
    assert _LOCAL_MODEL in str(exc.value)
    assert "evaluate_model.py" in str(exc.value)


# ---------------------------------------------------------------- manifest


def test_run_manifest_written_to_minio_at_run_start(tmp_path: Path) -> None:
    h = _Harness(tmp_path, env={"BACKFILL_TIME_CEILING_HOURS": "48"})
    dry = h.runner.dry_run(**_WINDOW)

    seen_at_first_run: list[str] = []
    original = h._pipeline_factory

    def factory(source_type: str, connector: SourceConnector) -> Any:
        if not seen_at_first_run:
            seen_at_first_run.extend(h.manifest_keys())
        return original(source_type, connector)

    h.runner._pipeline_factory = factory
    report = h.runner.run(**_WINDOW, estimate_run_id=dry.run_id)

    key = f"backfill/manifests/{report.run_id}.json"
    assert key in seen_at_first_run
    manifest = json.loads(h.minio.objects[key])
    assert manifest["model_id"] == _LOCAL_MODEL
    assert manifest["prompt_version"] == "v1.0"
    assert manifest["prefilter_version"] == "v1.0"
    assert manifest["margin_months"] == 3
    assert manifest["sources"] == ["biorxiv"]
    assert manifest["start_date"] == "2025-01-01" and manifest["end_date"] == "2025-02-28"
    assert manifest["status"] == "completed"
    assert manifest["counts"]["biorxiv"]["published"] == 2


# ---------------------------------------------------------------- ceilings


def test_backfill_aborts_when_estimate_exceeds_configured_budget(tmp_path: Path) -> None:
    h = _Harness(tmp_path, profile=_api_profile(), env={"BACKFILL_BUDGET_CEILING": "0.00001"})
    dry = h.runner.dry_run(**_WINDOW)
    with pytest.raises(CeilingExceededError) as exc:
        h.runner.run(**_WINDOW, estimate_run_id=dry.run_id)
    assert _API_MODEL in str(exc.value)
    assert h.pipeline_runs == []


def test_backfill_fails_at_startup_without_budget_ceiling_for_api_backend(tmp_path: Path) -> None:
    h = _Harness(tmp_path, profile=_api_profile(), env={})
    dry = h.runner.dry_run(**_WINDOW)
    with pytest.raises(BackfillConfigurationError, match="BACKFILL_BUDGET_CEILING"):
        h.runner.run(**_WINDOW, estimate_run_id=dry.run_id)
    assert h.pipeline_runs == []


def test_backfill_aborts_when_local_time_estimate_exceeds_ceiling(tmp_path: Path) -> None:
    h = _Harness(
        tmp_path,
        latency_dir=_latency_dir(tmp_path, mean=3600.0),  # 2 calls → 2 h
        env={"BACKFILL_TIME_CEILING_HOURS": "1.5"},
    )
    dry = h.runner.dry_run(**_WINDOW)
    with pytest.raises(CeilingExceededError) as exc:
        h.runner.run(**_WINDOW, estimate_run_id=dry.run_id)
    msg = str(exc.value)
    assert _LOCAL_MODEL in msg
    assert "1.5" in msg
    assert "2.0" in msg
    assert h.pipeline_runs == []


def test_live_run_requires_a_matching_completed_dry_run(tmp_path: Path) -> None:
    h = _Harness(tmp_path, env={"BACKFILL_TIME_CEILING_HOURS": "48"})
    with pytest.raises(BackfillConfigurationError, match="dry run"):
        h.runner.run(**_WINDOW, estimate_run_id="does-not-exist")
    dry = h.runner.dry_run(**_WINDOW)
    with pytest.raises(BackfillConfigurationError, match="end_date"):
        h.runner.run(source_type="biorxiv", start=date(2025, 1, 1), end=date(2025, 6, 30),
                     estimate_run_id=dry.run_id)
    assert h.pipeline_runs == []


# ---------------------------------------------------------------- checkpoint + cursor


def test_backfill_is_resumable_from_its_checkpoint(tmp_path: Path) -> None:
    h = _Harness(tmp_path, env={"BACKFILL_TIME_CEILING_HOURS": "48"})
    dry = h.runner.dry_run(**_WINDOW, window_days=31)
    original = h._pipeline_factory
    calls = {"n": 0}

    def flaky(source_type: str, connector: SourceConnector) -> Any:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("model server went away")
        return original(source_type, connector)

    h.runner._pipeline_factory = flaky
    with pytest.raises(RuntimeError):
        h.runner.run(**_WINDOW, window_days=31, estimate_run_id=dry.run_id)
    assert [c.date() for _, c in h.pipeline_runs] == [date(2025, 1, 1)]

    h.runner._pipeline_factory = original
    h.pipeline_runs.clear()
    h.runner.run(**_WINDOW, window_days=31, estimate_run_id=dry.run_id)
    assert [c.date() for _, c in h.pipeline_runs] == [date(2025, 2, 1)]


def test_backfill_does_not_advance_the_live_cursor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sdk = ModuleType("airflow.sdk")
    variable = MagicMock()
    fake_sdk.Variable = variable  # type: ignore[attr-defined]
    fake_airflow = ModuleType("airflow")
    fake_airflow.sdk = fake_sdk  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow", fake_airflow)
    monkeypatch.setitem(sys.modules, "airflow.sdk", fake_sdk)

    h = _Harness(tmp_path, env={"BACKFILL_TIME_CEILING_HOURS": "48"})
    dry = h.runner.dry_run(**_WINDOW)
    h.runner.run(**_WINDOW, estimate_run_id=dry.run_id)

    variable.set.assert_not_called()
    variable.get.assert_not_called()
    assert h.pipeline_runs  # it did run
    assert all(k.startswith("backfill/") for k in h.minio.objects)


# ---------------------------------------------------------------- rate limiter


@respx.mock
def test_backfill_respects_the_shared_rate_limiter(tmp_path: Path) -> None:
    page = json.loads((_FIXTURES / "biorxiv_page1.json").read_text())
    page["collection"] = [dict(page["collection"][0], date="2025-01-10")]
    page["messages"][0].update(count=1, total=1)
    route = respx.get(url__regex=r"https://api\.biorxiv\.org/details/biorxiv/.*").mock(
        return_value=Response(200, json=page)
    )

    clock = {"t": 0.0}
    sleeps: list[float] = []

    def fake_sleep(s: float) -> None:
        sleeps.append(s)
        clock["t"] += s

    shared = RateLimitedClient(
        {"api.biorxiv.org": 1.0}, _clock=lambda: clock["t"], _sleep=fake_sleep, block=True
    )
    built: list[SourceConnector] = []

    def factory(source_type: str, until: datetime) -> SourceConnector:
        c = build_connector(source_type, client=shared, source_config={}, env={}, until=until)
        built.append(c)
        return c

    h = _Harness(tmp_path, env={"BACKFILL_TIME_CEILING_HOURS": "48"})
    h.runner._connector_factory = factory
    dry = h.runner.dry_run(source_type="biorxiv", start=date(2025, 1, 1), end=date(2025, 3, 31),
                           window_days=31)

    assert route.call_count == 3  # one request per window, none dropped
    assert all(c._client is shared for c in built)  # type: ignore[attr-defined]
    assert sleeps, "the second and third requests must wait for a token, not burst"
    assert dry.sources["biorxiv"].documents == 3
    ends = [r.request.url.path.split("/")[4] for r in route.calls]
    assert ends == ["2025-01-31", "2025-03-03", "2025-03-31"]


def test_rate_limited_client_still_raises_when_not_blocking() -> None:
    from auspex_ingest.connectors import RateLimitExceeded

    client = RateLimitedClient({"example.org": 1.0}, _clock=lambda: 0.0, _httpx_client=MagicMock())
    client.get("https://example.org/a")
    with pytest.raises(RateLimitExceeded):
        client.get("https://example.org/b")


# ---------------------------------------------------------------- identity


def test_backfilled_document_reuses_existing_event_id_when_already_ingested_live(tmp_path: Path) -> None:
    doc = _doc(42, date(2025, 1, 15))
    live_event_id = compute_event_id(doc.canonical_id, doc.source_type, doc.external_id)

    llm = MagicMock()
    llm.chat.completions.create.return_value = _ExtractionResult(
        is_signal=True, title="t", raw_text_snippet="s", gene_targets=["BCL11A"],
        mechanisms=["CRISPR"], companies_mentioned=["Beam"], summary="s",
        directionality="positive", confidence_score=0.9,
    )
    extractor = BackendLLMExtractor(
        client=llm, model_id=_LOCAL_MODEL,
        entry={"num_ctx": 8192, "temperature": 0, "seed": 42},
        schema_version="1.0", prompt_version="v1.0", prompt_text="prompt", now=lambda: _NOW,
    )
    archive = MagicMock()
    archive.put.return_value = ("raw/biorxiv/k.json", True)
    archive.get_canonical_marker.return_value = None
    producer = MagicMock()

    h = _Harness(tmp_path, docs=[doc], env={"BACKFILL_TIME_CEILING_HOURS": "48"})

    def real_pipeline(source_type: str, connector: SourceConnector) -> IngestionPipeline:
        return IngestionPipeline(
            connector=connector, archive=archive, extractor=extractor, producer=producer,
            prefilter=Prefilter(_VOCAB, version="v1.0"), normalizer=IdentityNormalizer(),
            now=lambda: _NOW,
        )

    h.runner._pipeline_factory = real_pipeline
    dry = h.runner.dry_run(**_WINDOW)
    h.runner.run(**_WINDOW, estimate_run_id=dry.run_id)

    published = producer.publish_signal.call_args.args[0]
    assert published.event_id == live_event_id
    assert published.extraction_model == _LOCAL_MODEL


@respx.mock
def test_core_hub_extraction_history_reads_lineage_endpoint() -> None:
    from auspex_ingest.backfill import CoreHubExtractionHistory

    route = respx.get("http://core-hub.test/api/v1/extractions/models").mock(
        return_value=Response(200, json=[
            {"extraction_model": "gpt-4o-mini-2024-07-18", "documents": 7},
            {"extraction_model": _LOCAL_MODEL, "documents": 2},
        ])
    )
    history = CoreHubExtractionHistory(base_url="http://core-hub.test/")
    result = history.models_in_window("biorxiv", date(2025, 1, 1), date(2025, 1, 31))
    assert result == {"gpt-4o-mini-2024-07-18": 7, _LOCAL_MODEL: 2}
    params = dict(route.calls[0].request.url.params)
    assert params == {"source_type": "biorxiv", "from": "2025-01-01", "to": "2025-01-31"}
