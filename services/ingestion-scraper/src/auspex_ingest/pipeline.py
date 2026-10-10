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
    # The cursor the caller saves for the next run: never later than a document this run failed
    # to process, and the input cursor when the run stopped early. None when nothing was fetched.
    next_cursor: datetime | None = None
    # The run stopped at the extraction cap with documents left to fetch.
    capped: bool = False


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
        extraction_identity: str | None = None,
        max_extractions_per_run: int | None = None,
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
        # Model and prompt that produce this pipeline's extractions. When set, a document whose
        # identical content was already fully processed under the same identity is not
        # re-extracted (requirements §7.1 step 3). None disables the check.
        self._extraction_identity = extraction_identity
        self._max_extractions = max_extractions_per_run

    def run(self, source_type: str, cursor: datetime) -> RunResult:
        log = structlog.get_logger().bind(**{
            "auspex.source_type": source_type,
            "auspex.run_id": str(uuid.uuid4()),
        })
        result = RunResult()
        start = time.monotonic()
        identity = (
            f"{self._extraction_identity}|{self._prefilter.version}"
            if self._extraction_identity is not None
            else None
        )
        completed: list[Any] = []
        extractions = 0
        earliest_failed: datetime | None = None

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

                if identity is not None and self._archive.has_processed_marker(doc, identity):
                    result.prefiltered_out += 1
                    log.info("unchanged re-fetch skipped", **{"auspex.external_id": doc.external_id})
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

                if self._max_extractions is not None and extractions >= self._max_extractions:
                    result.capped = True
                    log.info("extraction cap reached", **{"auspex.cap": self._max_extractions})
                    break
                extractions += 1

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
                    completed.append(doc)
                    continue

                if event.confidence_score < self._min_confidence:
                    result.below_threshold += 1
                    completed.append(doc)
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
                completed.append(doc)
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
                if earliest_failed is None or doc.published_date < earliest_failed:
                    earliest_failed = doc.published_date
                if self._metrics:
                    self._metrics["documents_failed"].labels(source_type=source_type).inc()
                log.error("document processing failed", **{
                    "auspex.external_id": doc.external_id,
                    "exception_class": type(exc).__name__,
                })

        delivered = True
        try:
            self._producer.flush()
        except Exception:  # noqa: BLE001
            result.failed += 1
            delivered = False
            completed.clear()  # delivery unconfirmed: leave unmarked so the next fetch retries

        if result.capped or not delivered:
            result.next_cursor = cursor if result.fetched else None
        elif earliest_failed is not None:
            result.next_cursor = earliest_failed
        else:
            result.next_cursor = result.max_published_date_processed

        if identity is not None:
            for doc in completed:
                try:
                    self._archive.put_processed_marker(doc, identity)
                except Exception as exc:  # noqa: BLE001
                    # Costs one repeat extraction on the next fetch; nothing is lost.
                    log.warning("processed marker write failed", **{
                        "auspex.external_id": doc.external_id,
                        "exception_class": type(exc).__name__,
                    })

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
                 failed=result.failed,
                 capped=result.capped)

        return result
