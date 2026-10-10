import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
import instructor
import pytest
import respx
import yaml

from auspex_ingest.extraction_backend import (
    DEFAULT_PROMPT_VERSION,
    ConfigurationError,
    GateNotPassedError,
    LLMExtractorFactory,
    _load_registry,
    build_extractor_from_env,
    make_instructor_client,
    ollama_digest_lookup,
    register_local_model,
    score_file_name,
)
from auspex_ingest.model_evaluation import GATE_PRECISION, gate_record
from auspex_ingest.models import RawDocument
from auspex_ingest.prefilter import PREFILTER_VERSION

_TAG = "mistral-small:24b-instruct-2501-q4_K_M"
_HEX = "a" * 64
_DIGEST = f"{_TAG}@sha256:{_HEX}"
_BASE_URL = "http://ollama.test:11434/v1"

_LOCAL_ENTRY = {
    "backend": "local",
    "cutoff_date": "2023-10-01",
    "cutoff_source": "https://huggingface.co/mistralai/Mistral-Small-24B-Instruct-2501",
    "num_ctx": 8192,
    "timeout": 180,
    "temperature": 0,
    "seed": 42,
    "structured_output_mode": "JSON",
}


def _tags_payload(name: str = _TAG, hex_digest: str = _HEX) -> dict:
    return {"models": [{"name": name, "model": name, "digest": hex_digest, "size": 1}]}


def _write_registry(tmp_path: Path, entries: dict) -> Path:
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"models": entries}))
    return path


def _write_score(scores_dir: Path, model_id: str, prompt_version: str, prefilter_version: str) -> None:
    scores_dir.mkdir(parents=True, exist_ok=True)
    (scores_dir / score_file_name(model_id)).write_text(json.dumps({
        "model_id": model_id,
        "prompt_version": prompt_version,
        "prefilter_version": prefilter_version,
        "precision": 0.9,
        "passed": True,
        "scored_at": "2026-10-07T00:00:00Z",
    }))


def _doc() -> RawDocument:
    content = "BCL11A base editing trial"
    return RawDocument(
        schema_version="1.0",
        external_id="ext-1",
        source_type="biorxiv",
        source_url="https://example.com/1",
        published_date=datetime(2025, 1, 1, tzinfo=UTC),
        raw_content=content,
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        retrieved_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


@respx.mock
def test_ollama_digest_lookup_reads_native_tags_endpoint():
    route = respx.get("http://ollama.test:11434/api/tags").mock(
        return_value=httpx.Response(200, json=_tags_payload())
    )
    lookup = ollama_digest_lookup(_BASE_URL)
    assert lookup(_TAG) == _DIGEST
    assert route.called


@respx.mock
def test_ollama_digest_lookup_fails_when_tag_not_pulled():
    respx.get("http://ollama.test:11434/api/tags").mock(
        return_value=httpx.Response(200, json=_tags_payload(name="llama3.1:8b-instruct-q8_0"))
    )
    lookup = ollama_digest_lookup(_BASE_URL)
    with pytest.raises(ConfigurationError, match=r"ollama pull mistral-small"):
        lookup(_TAG)


def test_unreachable_model_server_warns_at_startup_and_checks_digest_on_first_extraction(
    tmp_path, mocker, caplog
):
    registry = _write_registry(tmp_path, {_TAG: {**_LOCAL_ENTRY, "digest": _DIGEST}})
    scores = tmp_path / "scores"
    _write_score(scores, _TAG, "v1", "v1")

    calls = {"n": 0}

    def info(tag: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("connection refused")
        return f"{tag}@sha256:{'b' * 64}"  # server came back with different weights

    with caplog.at_level(logging.WARNING):
        factory = LLMExtractorFactory(
            registry_path=registry,
            scores_dir=scores,
            model_id=_TAG,
            base_url=_BASE_URL,
            api_key="ollama",
            prompt_version="v1",
            prefilter_version="v1",
            model_info_fn=info,
        )
    assert any("unreachable" in r.getMessage() for r in caplog.records)

    extractor = factory.make_extractor(schema_version="1.0", prompt_version="v1")
    extractor._client = mocker.MagicMock()
    with pytest.raises(ConfigurationError, match="digest mismatch"):
        extractor.extract(_doc(), prefilter_version="v1", raw_object_key="k")
    extractor._client.chat.completions.create.assert_not_called()


def test_unknown_structured_output_mode_is_rejected(tmp_path):
    registry = _write_registry(
        tmp_path, {_TAG: {**_LOCAL_ENTRY, "digest": _DIGEST, "structured_output_mode": "XML"}}
    )
    with pytest.raises(ConfigurationError, match="structured_output_mode"):
        _load_registry(registry)


def test_instructor_client_uses_registry_mode_timeout_and_base_url():
    client = make_instructor_client(_LOCAL_ENTRY, _BASE_URL, "ollama")
    assert client.mode == instructor.Mode.JSON
    assert client.client.timeout == _LOCAL_ENTRY["timeout"]
    assert str(client.client.base_url).rstrip("/") == _BASE_URL


def test_extractor_from_env_targets_configured_model_and_base_url(tmp_path):
    registry = _write_registry(tmp_path, {_TAG: {**_LOCAL_ENTRY, "digest": _DIGEST}})
    scores = tmp_path / "scores"
    _write_score(scores, _TAG, DEFAULT_PROMPT_VERSION, PREFILTER_VERSION)
    env = {
        "EXTRACTION_MODEL": _TAG,
        "EXTRACTION_BASE_URL": _BASE_URL,
        "EXTRACTION_API_KEY": "ollama",
        "EXTRACTION_REGISTRY_PATH": str(registry),
        "EXTRACTION_SCORES_DIR": str(scores),
    }
    extractor = build_extractor_from_env(env, model_info_fn=lambda tag: _DIGEST)
    assert extractor._model_id == _TAG
    assert extractor._prompt_version == DEFAULT_PROMPT_VERSION
    assert str(extractor._client.client.base_url).rstrip("/") == _BASE_URL


def test_extractor_from_env_refuses_gate_record_for_other_prompt_version(tmp_path):
    registry = _write_registry(tmp_path, {_TAG: {**_LOCAL_ENTRY, "digest": _DIGEST}})
    scores = tmp_path / "scores"
    _write_score(scores, _TAG, "v0", PREFILTER_VERSION)
    env = {
        "EXTRACTION_MODEL": _TAG,
        "EXTRACTION_BASE_URL": _BASE_URL,
        "EXTRACTION_REGISTRY_PATH": str(registry),
        "EXTRACTION_SCORES_DIR": str(scores),
    }
    with pytest.raises(GateNotPassedError, match=_TAG):
        build_extractor_from_env(env, model_info_fn=lambda tag: _DIGEST)


def test_gate_record_passes_at_documented_precision_threshold():
    now = datetime(2026, 10, 7, tzinfo=UTC)
    assert GATE_PRECISION == 0.85
    passing = gate_record("m", "v1", "v1", precision=0.86, now=now)
    failing = gate_record("m", "v1", "v1", precision=0.84, now=now)
    assert passing["passed"] is True
    assert failing["passed"] is False
    assert passing["scored_at"] == "2026-10-07T00:00:00Z"
    assert set(passing) == {
        "model_id", "prompt_version", "prefilter_version", "precision", "passed", "scored_at"
    }


def test_register_local_model_appends_loadable_entry_with_live_digest(tmp_path):
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "models:\n"
        "  gpt-4o-mini-2024-07-18:\n"
        "    backend: api\n"
        "    cutoff_date: \"2023-10-01\"\n"
        "    cutoff_source: \"https://example.com\"\n"
        "    num_ctx: 8192\n"
        "    timeout: 30\n"
        "    temperature: 0\n"
        "    seed: 42\n"
        "    structured_output_mode: \"JSON\"\n"
        "    # deprecation_date: \"YYYY-MM-DD\"\n"
    )
    candidates = tmp_path / "local_candidates.yaml"
    candidates.write_text(yaml.safe_dump({"candidates": {_TAG: _LOCAL_ENTRY}}))

    register_local_model(registry, candidates, _TAG, model_info_fn=lambda tag: _DIGEST)

    models = _load_registry(registry)
    assert models[_TAG]["digest"] == _DIGEST
    assert models[_TAG]["backend"] == "local"
    assert "gpt-4o-mini-2024-07-18" in models
    assert "# deprecation_date" in registry.read_text()


def test_register_local_model_refuses_tag_already_registered(tmp_path):
    registry = _write_registry(tmp_path, {_TAG: {**_LOCAL_ENTRY, "digest": _DIGEST}})
    candidates = tmp_path / "local_candidates.yaml"
    candidates.write_text(yaml.safe_dump({"candidates": {_TAG: _LOCAL_ENTRY}}))
    with pytest.raises(ConfigurationError, match="already registered"):
        register_local_model(registry, candidates, _TAG, model_info_fn=lambda tag: _DIGEST)


_CANDIDATES_FILE = Path(__file__).resolve().parents[4] / "config" / "models" / "local_candidates.yaml"


@pytest.mark.parametrize(
    "tag",
    [
        "llama3.1:8b-instruct-q8_0",
        "llama3.1:8b-instruct-q4_K_M",
        "phi3:14b-medium-128k-instruct-q4_K_M",
    ],
)
def test_gated_local_candidate_registers_into_a_loadable_registry(tmp_path, tag):
    registry = _write_registry(tmp_path, {"gpt-4o-mini-2024-07-18": {**_LOCAL_ENTRY, "backend": "api"}})
    register_local_model(registry, _CANDIDATES_FILE, tag, model_info_fn=lambda t: f"{t}@sha256:{_HEX}")
    entry = _load_registry(registry)[tag]
    assert entry["backend"] == "local"
    assert entry["num_ctx"] >= 8192
