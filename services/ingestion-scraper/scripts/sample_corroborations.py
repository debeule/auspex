#!/usr/bin/env python
"""Sample live ticker records for the corroboration hand review (EXT-022).

Reads the live Postgres + Neo4j instances (from .env), draws a deterministic
sample of up to --per-label live ticker records per entity label, enriches each
with its participants' titles, snippets and sources, and writes a JSONL file.

Usage:
    uv run python scripts/sample_corroborations.py \\
        [--seed 42] [--per-label 50] [--output review.jsonl]

Label each line's "verdict" against the statement "these signals report the
same specific finding about the same entity, and the attached ticker is that
finding's company": "genuine" when it holds, otherwise "coincidental",
"wrong_ticker" or "extraction_error". Then run:

    uv run python scripts/score_corroboration_review.py review.jsonl --minimum 50

Never run this in CI — it hits live infrastructure.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auspex_ingest.sampling import sample_ticker_records


def _load_env() -> dict[str, str]:
    env_file = Path(__file__).parent.parent.parent.parent / ".env"
    result: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    result.update({k: v for k, v in os.environ.items() if k in result or k.startswith(("PG", "NEO4J"))})
    return result


def _fetch_corroborations(env: dict[str, str]) -> list[dict]:
    import psycopg2  # type: ignore[import-not-found]

    conn = psycopg2.connect(
        host=env.get("POSTGRES_HOST", "localhost"),
        port=int(env.get("POSTGRES_PORT", "5432")),
        dbname=env.get("POSTGRES_DB", "auspex"),
        user=env.get("POSTGRES_USER", "auspex_app"),
        password=env.get("POSTGRES_PASSWORD", ""),
    )
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT entity_key,
                       ticker,
                       participants_hash,
                       participant_event_ids::text[],
                       distinct_source_count,
                       episode_opened_at,
                       corroborated_at
                FROM corroboration
                WHERE superseded_by IS NULL AND excluded_reason IS NULL AND ticker <> ''
                ORDER BY entity_key, ticker, participants_hash
            """)
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "entity_key": r[0],
            "ticker": r[1],
            "participants_hash": r[2],
            "participant_event_ids": list(r[3]),
            "distinct_source_count": r[4],
            "episode_opened_at": r[5].isoformat(),
            "corroborated_at": r[6].isoformat(),
        }
        for r in rows
    ]


def _enrich_with_signals(records: list[dict], env: dict[str, str]) -> list[dict]:
    from neo4j import GraphDatabase  # type: ignore[import-not-found]

    driver = GraphDatabase.driver(
        env.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(env.get("NEO4J_USER", "neo4j"), env.get("NEO4J_PASSWORD", "")),
    )
    try:
        with driver.session() as session:
            for record in records:
                event_ids = record["participant_event_ids"]
                result = session.run(
                    """
                    MATCH (s:Signal) WHERE s.event_id IN $eventIds
                    RETURN s.event_id AS eventId,
                           s.source_type AS sourceType,
                           s.source_url AS sourceUrl,
                           s.title AS title,
                           s.summary AS summary,
                           s.published_date.epochSeconds AS publishedDateEpoch,
                           s.confidence_score AS confidenceScore
                    """,
                    eventIds=event_ids,
                )
                record["signals"] = [
                    {
                        "event_id": r["eventId"],
                        "source_type": r["sourceType"],
                        "source_url": r["sourceUrl"],
                        "title": r["title"],
                        "summary": r["summary"],
                        "published_date_epoch": r["publishedDateEpoch"],
                        "confidence_score": r["confidenceScore"],
                    }
                    for r in result
                ]
                record["verdict"] = ""  # reviewer fills this in
    finally:
        driver.close()

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for deterministic sampling")
    parser.add_argument("--per-label", type=int, default=50, help="Records to sample per entity label")
    parser.add_argument("--output", default="review.jsonl", help="Output JSONL file path")
    args = parser.parse_args()

    env = _load_env()

    print("Fetching corroboration records from Postgres…", flush=True)
    all_records = _fetch_corroborations(env)
    print(f"  Found {len(all_records)} live ticker records.", flush=True)

    if not all_records:
        print("No live ticker records found.", file=sys.stderr)
        sys.exit(1)

    sample = sample_ticker_records(all_records, args.per_label, seed=args.seed)
    print(f"  Sampled {len(sample)} records (seed={args.seed}).", flush=True)

    print("Enriching with signal details from Neo4j…", flush=True)
    enriched = _enrich_with_signals(sample, env)

    out = Path(args.output)
    with out.open("w") as f:
        for record in enriched:
            f.write(json.dumps(record, default=str) + "\n")

    print(f"\nWrote {len(enriched)} records to {out}")
    print("Next: set each line's 'verdict' (see this script's docstring), then run")
    print(f"      uv run python scripts/score_corroboration_review.py {out} --minimum {args.per_label}")


if __name__ == "__main__":
    main()
