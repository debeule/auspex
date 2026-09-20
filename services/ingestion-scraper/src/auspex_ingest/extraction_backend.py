from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from .identity import compute_event_id, compute_extraction_id
from .models import RawDocument, ResearchSignalEvent

_REQUIRED_FIELDS = frozenset({
    "backend",
    "cutoff_date",
    "cutoff_source",
    "num_ctx",
    "timeout",
    "temperature",
    "seed",
    "structured_output_mode",
})
_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts" / "extraction"
_MAX_CONTENT_CHARS = 4_000
# ~4 characters per token is a rough but consistent estimate; exact tokenisation
# requires the model's tokeniser which is not worth importing at startup.
_CHARS_PER_TOKEN = 4
_RESPONSE_BUDGET_TOKENS = 512

log = logging.getLogger(__name__)


class ConfigurationError(Exception):
    pass


class GateNotPassedError(Exception):
    pass


class ContextLengthError(Exception):
    pass


def _load_registry(registry_path: Path) -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(registry_path.read_text())
    models: dict[str, Any] = raw.get("models", {})
    for model_id, entry in models.items():
        missing = _REQUIRED_FIELDS - set(entry.keys())
        if missing:
            raise ConfigurationError(
                f"registry entry {model_id!r} missing required fields: {sorted(missing)}"
            )
        if entry["backend"] == "local" and "digest" not in entry:
            raise ConfigurationError(
                f"registry entry {model_id!r} has backend=local but no digest field"
            )
    return models


def _check_gate(
    scores_dir: Path, model_id: str, prompt_version: str, prefilter_version: str
) -> None:
    score_file = scores_dir / f"{model_id}.json"
    if not score_file.exists():
        raise GateNotPassedError(
            f"no gate record for model {model_id!r}; "
            f"run score_extraction.py --model {model_id}"
        )
    score = json.loads(score_file.read_text())
    if (
        not score.get("passed")
        or score.get("prompt_version") != prompt_version
        or score.get("prefilter_version") != prefilter_version
    ):
        raise GateNotPassedError(
            f"model {model_id!r} has no passing gate record "
            f"for prompt_version={prompt_version!r} prefilter_version={prefilter_version!r}"
        )


class BackendLLMExtractor:
    def __init__(
        self,
        client: Any,
        model_id: str,
        entry: dict[str, Any],
        schema_version: str,
        prompt_version: str,
        prompt_text: str,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._model_id = model_id
        self._entry = entry
        self._schema_version = schema_version
        self._prompt_version = prompt_version
        self._prompt_text = prompt_text
        self._now = now or (lambda: datetime.now(UTC))

    def extract(
        self, doc: RawDocument, prefilter_version: str, raw_object_key: str
    ) -> ResearchSignalEvent | None:
        from .extractor import _ExtractionResult  # reuse existing Pydantic model

        truncated = doc.raw_content[:_MAX_CONTENT_CHARS]
        content_block = f"---BEGIN DOCUMENT---\n{truncated}\n---END DOCUMENT---"

        prompt_tokens = len(self._prompt_text) // _CHARS_PER_TOKEN
        content_tokens = len(content_block) // _CHARS_PER_TOKEN
        total_tokens = prompt_tokens + content_tokens + _RESPONSE_BUDGET_TOKENS
        num_ctx: int = self._entry["num_ctx"]

        if total_tokens > num_ctx:
            raise ContextLengthError(
                f"prompt too long for model {self._model_id!r}: "
                f"estimated {total_tokens} tokens > num_ctx={num_ctx} "
                f"(prompt={prompt_tokens}, content={content_tokens}, "
                f"response_budget={_RESPONSE_BUDGET_TOKENS})"
            )

        result: _ExtractionResult = self._client.chat.completions.create(
            model=self._model_id,
            response_model=_ExtractionResult,
            messages=[
                {"role": "system", "content": self._prompt_text},
                {"role": "user", "content": content_block},
            ],
            temperature=self._entry["temperature"],
            seed=self._entry["seed"],
        )

        if not result.is_signal:
            return None

        event_id = compute_event_id(doc.canonical_id, doc.source_type, doc.external_id)
        extraction_id = compute_extraction_id(
            event_id,
            self._schema_version,
            self._prompt_version,
            prefilter_version,
            self._model_id,
        )

        return ResearchSignalEvent(
            schema_version=self._schema_version,
            event_id=event_id,
            extraction_id=extraction_id,
            external_id=doc.external_id,
            canonical_id=doc.canonical_id,
            raw_object_key=raw_object_key,
            source_type=doc.source_type,
            source_url=doc.source_url,
            published_date=doc.published_date,
            published_date_field="published_date",
            ingested_at=self._now(),
            title=result.title,
            raw_text_snippet=result.raw_text_snippet,
            gene_targets=result.gene_targets,
            mechanisms=result.mechanisms,
            companies_mentioned=result.companies_mentioned,
            summary=result.summary,
            directionality=result.directionality,
            confidence_score=result.confidence_score,
            prompt_version=self._prompt_version,
            prefilter_version=prefilter_version,
            extraction_model=self._model_id,
        )


class LLMExtractorFactory:
    def __init__(
        self,
        *,
        registry_path: Path,
        scores_dir: Path,
        model_id: str,
        base_url: str | None,
        api_key: str | None,
        prompt_version: str,
        prefilter_version: str,
        model_info_fn: Callable[[str], str] | None = None,
        prompt_dir: Path | None = None,
    ) -> None:
        self.base_url = base_url
        self._api_key = api_key
        self._prompt_version = prompt_version
        self._prefilter_version = prefilter_version
        self._prompt_dir = prompt_dir or _PROMPT_DIR

        registry = _load_registry(registry_path)

        if model_id not in registry:
            raise ConfigurationError(
                f"model {model_id!r} not found in registry {registry_path}; "
                f"available: {sorted(registry)}"
            )

        entry = registry[model_id]

        if entry["backend"] == "local":
            registered_digest: str = entry["digest"]
            model_tag = registered_digest.split("@")[0]
            if model_info_fn is not None:
                live_digest = model_info_fn(model_tag)
                if live_digest != registered_digest:
                    raise ConfigurationError(
                        f"model {model_id!r} digest mismatch: "
                        f"registered={registered_digest!r} live={live_digest!r}"
                    )

        _check_gate(scores_dir, model_id, prompt_version, prefilter_version)

        deprecation_date_str: str | None = entry.get("deprecation_date")
        if deprecation_date_str:
            dep_date = datetime.fromisoformat(deprecation_date_str).replace(tzinfo=UTC)
            if dep_date - datetime.now(UTC) <= timedelta(days=60):
                log.warning(
                    "extraction model approaching deprecation",
                    extra={"model_id": model_id, "deprecation_date": deprecation_date_str},
                )

        self._model_id = model_id
        self._entry = entry

    def make_extractor(
        self,
        schema_version: str,
        prompt_version: str,
        now: Callable[[], datetime] | None = None,
    ) -> BackendLLMExtractor:
        import instructor
        import openai

        prompt_path = self._prompt_dir / f"{prompt_version}.txt"
        prompt_text = prompt_path.read_text()

        raw_client = openai.OpenAI(
            api_key=self._api_key or "sk-dummy",
            base_url=self.base_url,
        )
        client = instructor.from_openai(raw_client)

        return BackendLLMExtractor(
            client=client,
            model_id=self._model_id,
            entry=self._entry,
            schema_version=schema_version,
            prompt_version=prompt_version,
            prompt_text=prompt_text,
            now=now,
        )
