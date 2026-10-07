#!/usr/bin/env python
# Usage: EXTRACTION_BASE_URL=http://localhost:11434/v1 \
#   uv run python scripts/register_local_model.py <ollama tag>
# Never run in CI — calls the local model server.
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auspex_ingest.extraction_backend import (
    ConfigurationError,
    ollama_digest_lookup,
    register_local_model,
)

_MODELS_DIR = Path(__file__).parent.parent.parent.parent / "config" / "models"


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a pulled Ollama model with its live digest")
    parser.add_argument("model", help="Ollama tag, e.g. llama3.1:8b-instruct-q8_0")
    parser.add_argument("--registry", default=_MODELS_DIR / "registry.yaml", type=Path)
    parser.add_argument("--candidates", default=_MODELS_DIR / "local_candidates.yaml", type=Path)
    args = parser.parse_args()

    base_url = os.environ.get("EXTRACTION_BASE_URL")
    if not base_url:
        print("Set EXTRACTION_BASE_URL to the Ollama endpoint (e.g. http://localhost:11434/v1).")
        sys.exit(1)

    try:
        entry = register_local_model(
            args.registry,
            args.candidates,
            args.model,
            model_info_fn=ollama_digest_lookup(base_url),
        )
    except ConfigurationError as exc:
        print(f"Not registered: {exc}")
        sys.exit(1)
    print(f"Registered {args.model} with digest {entry['digest']} in {args.registry}")


if __name__ == "__main__":
    main()
