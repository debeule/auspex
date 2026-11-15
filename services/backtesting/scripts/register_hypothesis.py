#!/usr/bin/env python3

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: register_hypothesis.py <hypothesis_id | corroboration_rules> [...]", file=sys.stderr)
        sys.exit(1)

    sys.path.insert(0, str(_REPO_ROOT / "services" / "backtesting" / "src"))
    from auspex_backtesting.hypothesis import (
        CORROBORATION_RULES_ID,
        corroboration_rules_path,
        register_corroboration_rules,
        register_hypothesis,
    )

    config_dir = _REPO_ROOT / "config" / "hypotheses"
    registry_path = config_dir / "registry.jsonl"

    for hypothesis_id in sys.argv[1:]:
        if hypothesis_id == CORROBORATION_RULES_ID:
            register_corroboration_rules(
                corroboration_rules_path(config_dir), registry_path=registry_path
            )
            print(f"registered: {hypothesis_id}")
            continue
        yaml_path = config_dir / f"{hypothesis_id}.yaml"
        if not yaml_path.exists():
            print(f"error: {yaml_path} not found", file=sys.stderr)
            sys.exit(1)
        content = yaml_path.read_text(encoding="utf-8")
        register_hypothesis(
            hypothesis_id,
            content,
            config_dir=config_dir,
            registry_path=registry_path,
        )
        print(f"registered: {hypothesis_id}")


if __name__ == "__main__":
    main()
