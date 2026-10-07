from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Mapping
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
_REPO_MODELS_DIR = Path(__file__).parents[4] / "config" / "models"
_DEFAULT_PROMPT_VERSION = "v1.0"
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
        if not _is_instructor_mode(entry["structured_output_mode"]):
            raise ConfigurationError(
                f"registry entry {model_id!r} has unknown structured_output_mode "
                f"{entry['structured_output_mode']!r}"
            )
        if entry["backend"] == "local" and "digest" not in entry:
            raise ConfigurationError(
                f"registry entry {model_id!r} has backend=local but no digest field"
            )
    return models


def _is_instructor_mode(name: str) -> bool:
    import instructor

    return name in instructor.Mode.__members__


def make_instructor_client(
    entry: Mapping[str, Any], base_url: str | None, api_key: str | None
) -> Any:
    """Build the instructor client a registry entry describes: mode and timeout come from
    the entry, the endpoint from the caller (which reads it from the environment)."""
    import instructor
    import openai

    raw_client = openai.OpenAI(
        api_key=api_key or "sk-dummy",
        base_url=base_url or None,
        timeout=float(entry["timeout"]),
    )
    return instructor.from_openai(raw_client, mode=instructor.Mode[entry["structured_output_mode"]])


def _ollama_root(base_url: str) -> str:
    root = base_url.rstrip("/")
    return root.removesuffix("/v1")


def ollama_digest_lookup(
    base_url: str, http_client: Any | None = None
) -> Callable[[str], str]:
    """Return a function mapping an Ollama tag to `<tag>@sha256:<hex>`, read from the
    server's native `/api/tags` listing (the OpenAI-compatible API exposes no digest)."""
    import httpx

    tags_url = f"{_ollama_root(base_url)}/api/tags"

    def lookup(tag: str) -> str:
        client = http_client or httpx.Client(timeout=10.0)
        response = client.get(tags_url)
        response.raise_for_status()
        for model in response.json().get("models", []):
            if tag in (model.get("name"), model.get("model")):
                digest = str(model["digest"]).removeprefix("sha256:")
                return f"{tag}@sha256:{digest}"
        raise ConfigurationError(
            f"model {tag!r} is not pulled on the Ollama server at {tags_url}; "
            f"run: ollama pull {tag}"
        )

    return lookup


def _verify_digest(
    model_id: str, registered_digest: str, model_info_fn: Callable[[str], str]
) -> None:
    model_tag = registered_digest.split("@")[0]
    live_digest = model_info_fn(model_tag)
    if live_digest != registered_digest:
        raise ConfigurationError(
            f"model {model_id!r} digest mismatch: "
            f"registered={registered_digest!r} live={live_digest!r}"
        )


def score_file_name(model_id: str) -> str:
    """Gate record file name: the registry key verbatim, so it can be found by eye."""
    return f"{model_id}.json"


def _check_gate(
    scores_dir: Path, model_id: str, prompt_version: str, prefilter_version: str
) -> None:
    score_file = scores_dir / score_file_name(model_id)
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
        gene_vocab: frozenset[str] | None = None,
        pending_check: Callable[[], None] | None = None,
    ) -> None:
        self._client = client
        self._gene_vocab = gene_vocab
        self._pending_check = pending_check
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

        if self._pending_check is not None:
            # Deferred from startup because the model server was unreachable then.
            self._pending_check()
            self._pending_check = None

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

        gene_targets = result.gene_targets
        if self._gene_vocab:
            gene_targets = [g for g in gene_targets if g in self._gene_vocab]

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
            gene_targets=gene_targets,
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

        self._pending_check: Callable[[], None] | None = None
        if entry["backend"] == "local" and model_info_fn is not None:
            registered_digest: str = entry["digest"]
            try:
                _verify_digest(model_id, registered_digest, model_info_fn)
            except (OSError, _transport_errors()) as exc:
                log.warning(
                    "local model server unreachable at startup; "
                    "digest will be verified before the first extraction",
                    extra={"model_id": model_id, "error": str(exc)},
                )
                info_fn = model_info_fn
                self._pending_check = lambda: _verify_digest(model_id, registered_digest, info_fn)

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
        gene_vocab: frozenset[str] | None = None,
    ) -> BackendLLMExtractor:
        prompt_path = self._prompt_dir / f"{prompt_version}.txt"
        prompt_text = prompt_path.read_text()

        return BackendLLMExtractor(
            client=make_instructor_client(self._entry, self.base_url, self._api_key),
            model_id=self._model_id,
            entry=self._entry,
            schema_version=schema_version,
            prompt_version=prompt_version,
            prompt_text=prompt_text,
            now=now,
            gene_vocab=gene_vocab,
            pending_check=self._pending_check,
        )


def _transport_errors() -> type[Exception]:
    import httpx

    return httpx.TransportError


def build_extractor_from_env(
    environ: Mapping[str, str] | None = None,
    *,
    schema_version: str = "1.0",
    prompt_version: str | None = None,
    model_id: str | None = None,
    gene_vocab: frozenset[str] | None = None,
    now: Callable[[], datetime] | None = None,
    model_info_fn: Callable[[str], str] | None = None,
) -> BackendLLMExtractor:
    """The one env-driven construction path for production extraction.

    Reads EXTRACTION_MODEL, EXTRACTION_BASE_URL, EXTRACTION_API_KEY (falls back to
    OPENAI_API_KEY), EXTRACTION_PROMPT_VERSION, EXTRACTION_REGISTRY_PATH and
    EXTRACTION_SCORES_DIR. Fails if the model is unregistered or has no passing gate
    record at these prompt and prefilter versions.
    """
    from .prefilter import PREFILTER_VERSION

    env = os.environ if environ is None else environ
    resolved_model = model_id or env.get("EXTRACTION_MODEL")
    if not resolved_model:
        raise ConfigurationError("EXTRACTION_MODEL is not set")
    resolved_prompt = (
        prompt_version or env.get("EXTRACTION_PROMPT_VERSION") or _DEFAULT_PROMPT_VERSION
    )
    base_url = env.get("EXTRACTION_BASE_URL") or None
    api_key = env.get("EXTRACTION_API_KEY") or env.get("OPENAI_API_KEY") or None
    registry_path = Path(
        env.get("EXTRACTION_REGISTRY_PATH") or _REPO_MODELS_DIR / "registry.yaml"
    )
    scores_dir = Path(env.get("EXTRACTION_SCORES_DIR") or _REPO_MODELS_DIR / "scores")

    if model_info_fn is None and base_url:
        model_info_fn = ollama_digest_lookup(base_url)

    factory = LLMExtractorFactory(
        registry_path=registry_path,
        scores_dir=scores_dir,
        model_id=resolved_model,
        base_url=base_url,
        api_key=api_key,
        prompt_version=resolved_prompt,
        prefilter_version=PREFILTER_VERSION,
        model_info_fn=model_info_fn,
    )
    return factory.make_extractor(
        schema_version=schema_version,
        prompt_version=resolved_prompt,
        now=now,
        gene_vocab=gene_vocab,
    )


def make_evaluation_extractor(
    *,
    registry_path: Path,
    model_id: str,
    prompt_version: str,
    base_url: str | None,
    api_key: str | None,
    schema_version: str = "1.0",
    model_info_fn: Callable[[str], str] | None = None,
) -> BackendLLMExtractor:
    """Extractor for the evaluation scripts: the exact registry configuration production
    runs, without the gate check (these scripts are what write the gate record).
    A local model's digest is verified so the score belongs to the pinned weights."""
    registry = _load_registry(registry_path)
    if model_id not in registry:
        raise ConfigurationError(
            f"model {model_id!r} not found in registry {registry_path}; "
            f"available: {sorted(registry)}"
        )
    entry = registry[model_id]
    if entry["backend"] == "local":
        info_fn = model_info_fn or (ollama_digest_lookup(base_url) if base_url else None)
        if info_fn is None:
            raise ConfigurationError(
                f"model {model_id!r} is local; set EXTRACTION_BASE_URL to the Ollama server"
            )
        _verify_digest(model_id, entry["digest"], info_fn)
    return BackendLLMExtractor(
        client=make_instructor_client(entry, base_url, api_key),
        model_id=model_id,
        entry=entry,
        schema_version=schema_version,
        prompt_version=prompt_version,
        prompt_text=(_PROMPT_DIR / f"{prompt_version}.txt").read_text(),
    )


def register_local_model(
    registry_path: Path,
    candidates_path: Path,
    model_id: str,
    *,
    model_info_fn: Callable[[str], str],
) -> dict[str, Any]:
    """Append a local candidate to the registry with the digest the running server reports.

    Appends text rather than rewriting the file so existing comments survive."""
    candidates: dict[str, Any] = yaml.safe_load(candidates_path.read_text()).get("candidates", {})
    if model_id not in candidates:
        raise ConfigurationError(
            f"model {model_id!r} is not in {candidates_path}; available: {sorted(candidates)}"
        )
    existing = _load_registry(registry_path)
    if model_id in existing:
        raise ConfigurationError(
            f"model {model_id!r} is already registered in {registry_path} "
            f"(digest {existing[model_id].get('digest')!r}); a new digest needs a new "
            "registry key and a new gate record"
        )

    entry = {**candidates[model_id], "backend": "local", "digest": model_info_fn(model_id)}
    block = yaml.safe_dump({model_id: entry}, sort_keys=False, default_flow_style=False)
    indented = "".join(f"  {line}\n" for line in block.splitlines())
    text = registry_path.read_text()
    if not text.endswith("\n"):
        text += "\n"
    registry_path.write_text(text + indented)
    _load_registry(registry_path)  # fail now, not at the next service start
    return entry
