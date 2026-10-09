#!/usr/bin/env python
"""Standalone pipeline runner — no Airflow dependency.

Reads config/sources.yaml, builds one pipeline per source type, and runs a
one-shot lookback (default 30 days). Skips fixture sources such as mock. Safe to re-run:
MinIO archive dedup prevents duplicate extraction.

Usage:
    cd services/ingestion-scraper
    uv run python scripts/run_pipeline.py
    uv run python scripts/run_pipeline.py --days 30 --sources biorxiv clinicaltrials
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))


def _load_env() -> None:
    env_file = _ROOT.parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k not in os.environ:
            os.environ[k] = v.strip()


_load_env()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days")
    parser.add_argument(
        "--sources", nargs="+",
        help="Source types to run (default: every live entry in sources.yaml)"
    )
    args = parser.parse_args()

    from auspex_ingest.connectors.registry import ConnectorConfigurationError, default_registry
    from auspex_ingest.pipeline_factory import make_env_pipeline_factory
    from auspex_ingest.sources import load_sources_config

    config = load_sources_config(_ROOT / "config" / "sources.yaml")
    connectors = default_registry()

    cursor = datetime.now(UTC) - timedelta(days=args.days)
    requested = set(args.sources) if args.sources else None
    pipeline_for = make_env_pipeline_factory(
        {e.source_type: e for e in config.sources}, metrics_registry=None
    )

    for entry in config.sources:
        source_type = entry.source_type
        if requested is None and not connectors.registration(source_type).live:
            continue
        if requested and source_type not in requested:
            continue

        print(f"\n{'=' * 60}", flush=True)
        print(
            f"Source: {source_type}  |  cursor: {cursor.date()}  |  window: {args.days}d",
            flush=True,
        )
        print(f"{'=' * 60}", flush=True)

        try:
            pipeline = pipeline_for(source_type)
            result = pipeline.run(source_type, cursor)
            print(
                f"  fetched={result.fetched}  published={result.published}"
                f"  prefiltered_out={result.prefiltered_out}"
                f"  not_signal={result.not_signal}  failed={result.failed}",
                flush=True,
            )
        except ConnectorConfigurationError as exc:
            print(f"  SKIP: {exc}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR in {source_type}: {exc}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()