from collections.abc import Callable
from datetime import datetime
from typing import Any

from .connectors.base import SourceConnector
from .models import RunResult
from .normalizer import EntityNormalizer
from .prefilter import Prefilter


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
    ) -> None:
        self._connector = connector
        self._archive = archive
        self._extractor = extractor
        self._producer = producer
        self._prefilter = prefilter
        self._normalizer = normalizer
        self._now = now
        self._min_confidence = min_confidence_to_publish

    def run(self, source_type: str, cursor: datetime) -> RunResult:
        result = RunResult()

        for doc in self._connector.fetch_since(cursor):
            result.fetched += 1
            try:
                key, _ = self._archive.put(doc)

                if not self._prefilter.passes(doc):
                    result.prefiltered_out += 1
                    continue

                if self._connector.provides_canonical_id and doc.canonical_id is None:
                    raise ValueError(
                        f"Connector declares provides_canonical_id=True but "
                        f"doc {doc.external_id!r} has canonical_id=None"
                    )

                event = self._extractor.extract(doc, self._prefilter.version, key)

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

            except Exception:
                result.failed += 1

        try:
            self._producer.flush()
        except Exception:
            result.failed += 1

        return result
