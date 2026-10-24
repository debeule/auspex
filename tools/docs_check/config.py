"""Loading and validating `docs-check.toml`. Any problem is a `ConfigError`, which the CLI turns into exit 2.

Ownership rules live under `[[ownership.rules]]`: TOML cannot hold both an `[ownership]` table and an
`[[ownership]]` array, and `[ownership] unowned_ok` is part of the same table.
"""

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import globs


class ConfigError(Exception):
    """A configuration or usage error; the CLI prints it and exits 2."""


_NAMESPACE = re.compile(r"^[A-Z]{3}$")
_STR_LIST = "list of strings"

# Table → key → expected type. A key marked optional may be absent; every other key is required.
_SCHEMA: dict[str, dict] = {
    "namespaces": {"invariant": str, "ids": _STR_LIST, "frozen_paths": _STR_LIST},
    "living_docs": {"include": _STR_LIST, "non_normative": _STR_LIST, "required_sections": _STR_LIST},
    "specs": {
        "include": _STR_LIST,
        "exclude": _STR_LIST,
        "statuses": _STR_LIST,
        "required_fields": _STR_LIST,
        "required_sections": _STR_LIST,
    },
    "budgets": {"root_agents_bytes": int, "nested_agents_bytes": int, "chain_bytes": int, "claude_md_bytes": int},
}
_CHECKS_SCHEMA: dict[str, dict] = {
    "A": {"include": _STR_LIST, "exclude": _STR_LIST},
    "B": {"include": _STR_LIST, "exclude": _STR_LIST, "prefixes": _STR_LIST},
    "D": {"include": _STR_LIST, "exclude": _STR_LIST},
    "H": {"file": str},
    "J": {"index": str, "exclude": _STR_LIST},
    "K": {"bare_test_dirs": _STR_LIST},
}
_ROLLOUT_KEYS = {"base": str, "planned_domains": _STR_LIST, "matrix": str}
_TOP_LEVEL = set(_SCHEMA) | {"checks", "rollout", "domains", "ownership"}


def _check_value(where: str, value, expected) -> None:
    if expected == _STR_LIST:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ConfigError(f"{where} must be a list of strings")
    elif expected is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ConfigError(f"{where} must be an integer")
    elif not isinstance(value, expected):
        raise ConfigError(f"{where} must be a {expected.__name__}")


def _check_table(where: str, table, schema: dict, required: bool = True) -> None:
    if not isinstance(table, dict):
        raise ConfigError(f"[{where}] must be a table")
    for key in table:
        if key not in schema:
            raise ConfigError(f"unknown key {where}.{key}")
    for key, expected in schema.items():
        if key in table:
            _check_value(f"{where}.{key}", table[key], expected)
        elif required:
            raise ConfigError(f"missing key {where}.{key}")


@dataclass
class Rule:
    glob: str
    domains: list[str]
    override: bool = False


@dataclass
class Domain:
    name: str
    namespaces: list[str]
    owners: list[str]


@dataclass
class Config:
    raw: dict
    invariant: str
    ids: list[str]
    frozen_paths: list[str]
    domains: dict[str, Domain]
    rules: list[Rule]
    unowned_ok: list[str]
    rollout: dict | None
    planned: list[str] = field(default_factory=list)

    def section(self, *keys: str):
        value = self.raw
        for key in keys:
            value = value[key]
        return value

    @property
    def namespaces(self) -> list[str]:
        return [self.invariant, *self.ids]

    def id_pattern(self) -> str:
        """The ID alternation without anchors: the invariant namespace with 1–2 digits, the rest with 3."""
        others = "|".join(re.escape(ns) for ns in self.ids)
        return rf"{re.escape(self.invariant)}-\d{{1,2}}|(?:{others})-\d{{3}}"

    def reference_regex(self) -> re.Pattern[str]:
        """References to IDs; `(?<!M-)` keeps migration-matrix row ids from reading as references."""
        return re.compile(rf"(?<!M-)\b({self.id_pattern()})\b")

    def full_id_regex(self) -> re.Pattern[str]:
        return re.compile(rf"(?:{self.id_pattern()})")

    def placeholder_regex(self) -> re.Pattern[str]:
        names = "|".join(re.escape(ns) for ns in self.namespaces)
        return re.compile(rf"(?<!M-)\b((?:{names})-\?)")

    def alias_regex(self) -> re.Pattern[str]:
        return re.compile(r"[Ii]nvariants? #?(\d{1,2})( and #?(\d{1,2}))?")

    def namespace_of(self, ident: str) -> str:
        return ident.split("-", 1)[0]

    def domain_of_namespace(self, namespace: str) -> str | None:
        for domain in self.domains.values():
            if namespace in domain.namespaces:
                return domain.name
        return None

    @property
    def planned_namespaces(self) -> set[str]:
        return {ns for name in self.planned for ns in self.domains[name].namespaces}

    def is_living_doc(self, path: str) -> bool:
        living = self.raw["living_docs"]
        return globs.match_any(living["include"], path) and path not in living["non_normative"]

    def in_scope(self, check: str, path: str) -> bool:
        table = self.raw["checks"][check]
        return globs.match_any(table["include"], path) and not globs.match_any(table.get("exclude", []), path)

    def is_spec(self, path: str) -> bool:
        specs = self.raw["specs"]
        return globs.match_any(specs["include"], path) and path not in specs["exclude"]

    def is_unowned_ok(self, path: str) -> bool:
        return globs.match_any(self.unowned_ok, path)

    def rule_domains(self, path: str) -> list[str] | None:
        """Domains of `path` from the ownership rules, in rule order; None when no rule matches.

        The union of every matching rule, unless some matching rule has `override = true`: then only the
        override rules count.
        """
        matching = [rule for rule in self.rules if globs.match(rule.glob, path)]
        if not matching:
            return None
        overriding = [rule for rule in matching if rule.override]
        chosen = overriding or matching
        domains: list[str] = []
        for rule in chosen:
            for name in rule.domains:
                if name not in domains:
                    domains.append(name)
        return domains

    def path_domains(self, path: str) -> list[str] | None:
        """Domains a change to `path` touches: none for an `unowned_ok` path, None when nothing maps it."""
        if self.is_unowned_ok(path):
            return []
        return self.rule_domains(path)


def load(path: Path) -> Config:
    try:
        with open(path, "rb") as handle:
            raw = tomllib.load(handle)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"cannot read {path}: {error}") from None

    for key in raw:
        if key not in _TOP_LEVEL:
            raise ConfigError(f"unknown table [{key}]")
    for key in [*_SCHEMA, "checks", "domains", "ownership"]:
        if key not in raw:
            raise ConfigError(f"missing table [{key}]")
    for key, schema in _SCHEMA.items():
        _check_table(key, raw[key], schema)
    checks = raw["checks"]
    if not isinstance(checks, dict):
        raise ConfigError("[checks] must be a table")
    for name in checks:
        if name not in _CHECKS_SCHEMA:
            raise ConfigError(f"unknown table [checks.{name}]")
    for name, schema in _CHECKS_SCHEMA.items():
        if name not in checks:
            raise ConfigError(f"missing table [checks.{name}]")
        _check_table(f"checks.{name}", checks[name], schema)

    namespaces = raw["namespaces"]
    for ns in [namespaces["invariant"], *namespaces["ids"]]:
        if not _NAMESPACE.match(ns):
            raise ConfigError(f"namespace {ns!r} does not match ^[A-Z]{{3}}$")
    if len(set(namespaces["ids"]) | {namespaces["invariant"]}) != len(namespaces["ids"]) + 1:
        raise ConfigError("namespaces are not distinct")
    known_namespaces = {namespaces["invariant"], *namespaces["ids"]}

    domains: dict[str, Domain] = {}
    if not isinstance(raw["domains"], dict):
        raise ConfigError("[domains] must be a table")
    for name, table in raw["domains"].items():
        _check_table(f"domains.{name}", table, {"namespaces": _STR_LIST, "owners": _STR_LIST})
        for ns in table["namespaces"]:
            if ns not in known_namespaces:
                raise ConfigError(f"domains.{name} names unknown namespace {ns!r}")
        domains[name] = Domain(name, table["namespaces"], table["owners"])

    ownership = raw["ownership"]
    _check_table("ownership", ownership, {"unowned_ok": _STR_LIST, "rules": list})
    rules = []
    for position, rule in enumerate(ownership["rules"], 1):
        where = f"ownership.rules[{position}]"
        _check_table(where, rule, {"glob": str, "domains": _STR_LIST, "override": bool}, required=False)
        if "glob" not in rule or "domains" not in rule:
            raise ConfigError(f"{where} needs glob and domains")
        for name in rule["domains"]:
            if name not in domains:
                raise ConfigError(f"{where} names unknown domain {name!r}")
        rules.append(Rule(rule["glob"], rule["domains"], rule.get("override", False)))

    rollout = raw.get("rollout")
    planned: list[str] = []
    if rollout is not None:
        _check_table("rollout", rollout, _ROLLOUT_KEYS, required=False)
        planned = list(rollout.get("planned_domains", []))
        for name in planned:
            if name not in domains:
                raise ConfigError(f"rollout.planned_domains names unknown domain {name!r}")

    return Config(
        raw=raw,
        invariant=namespaces["invariant"],
        ids=list(namespaces["ids"]),
        frozen_paths=list(namespaces["frozen_paths"]),
        domains=domains,
        rules=rules,
        unowned_ok=list(ownership["unowned_ok"]),
        rollout=rollout,
        planned=planned,
    )
