from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from auspex_strategy.abc import AsOfContext, Strategy
from auspex_strategy.errors import (
    HypothesisNotRegisteredError,
    StrategyRetiredError,
    VersionConflictError,
)
from auspex_strategy.models import TradeIntent, Trigger


@dataclass
class RegistryEntry:
    name: str
    module: str
    class_name: str
    version: str
    hypothesis_id: str
    status: str
    parameters_file: str
    strategy_class: type[Strategy]

    def decide(self, context: AsOfContext, trigger: Trigger) -> list[TradeIntent]:
        if self.status == "retired":
            raise StrategyRetiredError(self.name)
        instance = self.strategy_class()
        return instance.decide(context, trigger)


class StrategyRegistry:
    def __init__(self, entries: list[RegistryEntry]) -> None:
        self._entries: dict[str, RegistryEntry] = {e.name: e for e in entries}

    def all(self) -> list[RegistryEntry]:
        return list(self._entries.values())

    def get(self, name: str) -> RegistryEntry | None:
        return self._entries.get(name)

    @classmethod
    def load(
        cls,
        registry_path: Path,
        *,
        hypothesis_registry_path: Path | None = None,
        versions_dir: Path | None = None,
        config_root: Path | None = None,
    ) -> StrategyRegistry:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        entries: list[RegistryEntry] = []

        resolved_config_root = (
            config_root if config_root is not None
            else registry_path.resolve().parent.parent.parent
        )

        for item in raw.get("strategies", []):
            module_name: str = item["module"]
            class_name: str = item["class"]
            name: str = item["name"]
            version: str = item["version"]
            hypothesis_id: str = item["hypothesis_id"]

            module = importlib.import_module(module_name)
            strategy_class: type[Strategy] = getattr(module, class_name)

            if hypothesis_registry_path is not None:
                _verify_hypothesis(hypothesis_id, hypothesis_registry_path)

            if versions_dir is not None:
                parameters_file = resolved_config_root / item["parameters_file"]
                _check_version(name, version, module_name, parameters_file, versions_dir)

            entries.append(RegistryEntry(
                name=name,
                module=module_name,
                class_name=class_name,
                version=version,
                hypothesis_id=hypothesis_id,
                status=item.get("status", "draft"),
                parameters_file=item.get("parameters_file", ""),
                strategy_class=strategy_class,
            ))

        return cls(entries)


def _verify_hypothesis(hypothesis_id: str, registry_path: Path) -> None:
    registered_ids = set()
    if registry_path.exists():
        for line in registry_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entry: dict[str, Any] = json.loads(line)
                registered_ids.add(entry.get("hypothesis_id", ""))
    if hypothesis_id not in registered_ids:
        raise HypothesisNotRegisteredError(hypothesis_id)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_str(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_version(
    name: str,
    version: str,
    module_name: str,
    parameters_file: Path,
    versions_dir: Path,
) -> None:
    spec = importlib.util.find_spec(module_name)
    module_file: Path | None = Path(spec.origin) if spec and spec.origin else None
    code_hash = _sha256_file(module_file) if module_file else None
    params_hash = _sha256_file(parameters_file) if parameters_file.exists() else None

    version_file = versions_dir / name / f"{version}.json"

    if version_file.exists():
        stored: dict[str, Any] = json.loads(version_file.read_text(encoding="utf-8"))
        if code_hash is not None and stored.get("code_hash") != code_hash:
            raise VersionConflictError(name, version, "code changed without version bump")
        if params_hash is not None and stored.get("parameters_hash") != params_hash:
            raise VersionConflictError(name, version, "parameters changed without version bump")
    else:
        version_file.parent.mkdir(parents=True, exist_ok=True)
        version_file.write_text(json.dumps({
            "code_hash": code_hash,
            "parameters_hash": params_hash,
            "created_at": datetime.now(UTC).isoformat(),
        }), encoding="utf-8")
