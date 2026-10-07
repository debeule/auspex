import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog

from .connectors.base import SourceConnector
from .metrics import make_metrics
from .normalizer import EntityNormalizer
from .prefilter import Prefilter


@dataclass
class RunResult:
    fetched: int = 0
    prefiltered_out: int = 0
    published: int = 0
    not_signal: int = 0
    below_threshold: int = 0
    failed: int = 0
    max_published_date_processed: datetime | None = None


class IngestionPipeline:
    def __init__(
        self,
        *,
        connector: SourceConnector,
        archive: Any,
        extractor: Any,
        producer: Any,
        prefilter: Prefilter,
        normalizer: EntityNormalizer,
        now: Callable[[], datetime],
        min_confidence_to_publish: float = 0.0,
        metrics_registry: Any = None,
    ) -> None:
        self._connector = connector
        self._archive = archive
        self._extractor = extractor
        self._producer = producer
        self._prefilter = prefilter
        self._normalizer = normalizer
        self._now = now
        self._min_confidence = min_confidence_to_publish
        self._metrics = make_metrics(metrics_registry) if metrics_registry is not None else None

    def run(self, source_type: str, cursor: datetime) -> RunResult:
        log = structlog.get_logger().bind(**{
            "auspex.source_type": source_type,
            "auspex.run_id": str(uuid.uuid4()),
        })
        result = RunResult()
        start = time.monotonic()

        for doc in self._connector.fetch_since(cursor):
            result.fetched += 1
            if self._metrics:
                self._metrics["documents_fetched"].labels(source_type=source_type).inc()
            try:
                key, is_new = self._archive.put(doc)

                if (
                    result.max_published_date_processed is None
                    or doc.published_date > result.max_published_date_processed
                ):
                    result.max_published_date_processed = doc.published_date

                if not is_new:
                    result.prefiltered_out += 1
                    continue

                if doc.canonical_id is not None:
                    marker = self._archive.get_canonical_marker(doc.canonical_id)
                    if marker is not None and marker.get("source_type") != doc.source_type:
                        result.prefiltered_out += 1
                        continue

                if not self._prefilter.passes(doc):
                    result.prefiltered_out += 1
                    continue

                if self._connector.provides_canonical_id and doc.canonical_id is None:
                    raise ValueError(
                        f"Connector declares provides_canonical_id=True but "
                        f"doc {doc.external_id!r} has canonical_id=None"
                    )

                extract_start = time.monotonic()
                try:
                    event = self._extractor.extract(doc, self._prefilter.version, key)
                    if self._metrics:
                        self._metrics["llm_calls"].labels(source_type=source_type, result="success").inc()
                except Exception:
                    if self._metrics:
                        self._metrics["llm_calls"].labels(source_type=source_type, result="error").inc()
                    raise
                finally:
                    if self._metrics:
                        self._metrics["llm_duration"].labels(source_type=source_type).observe(
                            time.monotonic() - extract_start
                        )

                if event is None:
                    result.not_signal += 1
                    continue

                if event.confidence_score < self._min_confidence:
                    result.below_threshold += 1
                    continue

                normalized_genes = [
                    self._normalizer.normalize_gene(g) for g in event.gene_targets
                ]
                normalized_companies = [
                    self._normalizer.normalize_company(c) for c in event.companies_mentioned
                ]
                event = event.model_copy(update={
                    "gene_targets": normalized_genes,
                    "companies_mentioned": normalized_companies,
                })

                self._producer.publish_raw(doc, key, doc.schema_version)
                self._producer.publish_signal(event)
                result.published += 1
                if self._metrics:
                    self._metrics["signals_published"].labels(source_type=source_type).inc()

                if doc.canonical_id is not None:
                    try:
                        self._archive.put_canonical_marker(doc.canonical_id, {
                            "canonical_id": doc.canonical_id,
                            "source_type": doc.source_type,
                            "external_id": doc.external_id,
                        })
                    except Exception:  # noqa: BLE001, S110
                        pass  # Acceptable failure: next observation re-extracts once

            except Exception as exc:  # noqa: BLE001
                result.failed += 1
                if self._metrics:
                    self._metrics["documents_failed"].labels(source_type=source_type).inc()
                log.error("document processing failed", **{
                    "auspex.external_id": doc.external_id,
                    "exception_class": type(exc).__name__,
                })

        try:
            self._producer.flush()
        except Exception:  # noqa: BLE001
            result.failed += 1

        if self._metrics:
            self._metrics["run_duration"].labels(source_type=source_type).observe(
                time.monotonic() - start
            )
            self._metrics["run_last_timestamp"].labels(source_type=source_type).set(
                time.time()
            )

        log.info("run complete",
                 fetched=result.fetched,
                 prefiltered_out=result.prefiltered_out,
                 published=result.published,
                 not_signal=result.not_signal,
                 below_threshold=result.below_threshold,
                 failed=result.failed)

        return result
