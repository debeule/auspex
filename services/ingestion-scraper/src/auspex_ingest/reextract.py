import json
from datetime import UTC, datetime
from typing import Any

from .models import RawDocument


class ReextractionRunner:
    def __init__(self, *, archive: Any, extractor: Any, producer: Any) -> None:
        self._archive = archive
        self._extractor = extractor
        self._producer = producer

    def run(
        self,
        *,
        source_type: str | None = None,
        since: str | None = None,
        until: str | None = None,
        prompt_version: str | None = None,
        model: str | None = None,
        schema_version: str | None = None,
        prefilter_version: str | None = None,
        skip_prefilter: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        since_dt = datetime.fromisoformat(since).replace(tzinfo=UTC) if since else None
        until_dt = datetime.fromisoformat(until).replace(tzinfo=UTC) if until else None

        scanned = 0
        skipped_by_filter = 0
        not_signal = 0
        published = 0
        failed = 0

        for key in self._archive.list_raw_keys(source_type):
            raw_data = json.loads(self._archive.get_raw(key))
            doc = RawDocument.model_validate(raw_data)
            scanned += 1

            if since_dt and doc.published_date < since_dt:
                skipped_by_filter += 1
                continue
            if until_dt and doc.published_date > until_dt:
                skipped_by_filter += 1
                continue

            if dry_run:
                continue

            try:
                signal = self._extractor.extract(doc, prefilter_version, key)
                if signal is None:
                    not_signal += 1
                else:
                    self._producer.publish_signal(signal)
                    published += 1
            except Exception:  # noqa: BLE001
                failed += 1

        if not dry_run:
            self._producer.flush()

        return {
            "scanned": scanned,
            "skipped_by_filter": skipped_by_filter,
            "not_signal": not_signal,
            "published": published,
            "failed": failed,
        }
