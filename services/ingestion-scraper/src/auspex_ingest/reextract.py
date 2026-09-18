from typing import Any


class ReextractionRunner:
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
        raise NotImplementedError
