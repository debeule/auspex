"""Port of core-hub's corroboration rules loader and episode builder (RES-083).

core-hub (`dev.auspex.corehub.corroboration`) and this module read one rules file,
`config/corroboration/entity-rules.yaml`, and one case file,
`services/core-hub/src/test/resources/corroboration/episode-cases.json`, so the two cannot
drift apart silently. Keep both in step: a change here is a change there.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final, Protocol

import yaml  # type: ignore[import-untyped]

GENE_TARGET: Final = "GeneTarget"
MECHANISM: Final = "Mechanism"
BROAD_ENTITY: Final = "broad_entity"
_LABELS: Final = (GENE_TARGET, MECHANISM)

WINDOW: Final = timedelta(days=90)
"""Between two publication dates, both ends included."""


class InvalidEntityRulesError(ValueError):
    pass


class EpisodeSignal(Protocol):
    @property
    def event_id(self) -> str: ...
    @property
    def source_type(self) -> str: ...
    @property
    def published_date(self) -> datetime: ...
    @property
    def title(self) -> str | None: ...


def _letter_or_digit(ch: str) -> bool:
    # Java's Character.isLetterOrDigit: any letter, or a decimal digit.
    category = unicodedata.category(ch)
    return category.startswith("L") or category == "Nd"


def tokens(lower_cased: str) -> str:
    """Runs of characters that are not letters or digits become one space, trimmed."""
    out: list[str] = []
    gap = False
    for ch in lower_cased:
        if _letter_or_digit(ch):
            if gap and out:
                out.append(" ")
            out.append(ch)
            gap = False
        else:
            gap = True
    return "".join(out)


def normal_form(label: str, name: str) -> str:
    """The canonical key of a name under the label's normalisation, before synonyms."""
    nfkc = unicodedata.normalize("NFKC", name)
    if label == GENE_TARGET:
        return "".join(ch for ch in nfkc.upper() if _letter_or_digit(ch))
    if label == MECHANISM:
        return tokens(nfkc.lower())
    raise ValueError(f"not a corroborating label: {label}")


@dataclass(frozen=True)
class SameFinding:
    source_type_pairs: frozenset[frozenset[str]]
    title_token_jaccard_min: float

    def lists_pair(self, a: str, b: str) -> bool:
        return a != b and frozenset((a, b)) in self.source_type_pairs


@dataclass(frozen=True)
class EntityRules:
    hash: str
    variant_to_canonical: dict[str, dict[str, str]]
    excluded: dict[str, frozenset[str]]
    same_finding: SameFinding

    @staticmethod
    def load(data: bytes, known_source_types: Iterable[str] | None = None) -> EntityRules:
        """Parse and validate the rules file; `known_source_types` None skips that check."""
        try:
            root = yaml.safe_load(data.decode("utf-8"))
        except yaml.YAMLError as exc:
            raise InvalidEntityRulesError(f"rules file is not YAML: {exc}") from exc
        return EntityRules.from_mapping(root, _sha256(data), known_source_types)

    @staticmethod
    def from_mapping(
        root: Any, rules_hash: str, known_source_types: Iterable[str] | None = None
    ) -> EntityRules:
        top = _mapping(root, "the rules file")
        synonyms = _mapping(top.get("synonyms"), "synonyms")
        excluded_raw = _mapping(top.get("excluded"), "excluded")
        same_finding_raw = _mapping(top.get("same_finding"), "same_finding")
        for section, keys in (("synonyms", synonyms), ("excluded", excluded_raw)):
            for key in keys:
                if key not in _LABELS:
                    raise InvalidEntityRulesError(f"{section} names an unknown label {key!r}")

        variants: dict[str, dict[str, str]] = {}
        excluded: dict[str, frozenset[str]] = {}
        for label in _LABELS:
            label_variants: dict[str, str] = {}
            label_synonyms = _mapping(synonyms.get(label) or {}, f"synonyms.{label}")
            for canonical, listed in label_synonyms.items():
                _require_canonical(label, canonical)
                for variant in _list(listed, f"synonyms.{label}.{canonical}"):
                    _require_canonical(label, _text(variant, f"a variant of {canonical}"))
                    if variant in label_variants:
                        raise InvalidEntityRulesError(
                            f"variant {variant!r} is listed under {label_variants[variant]!r}"
                            f" and {canonical!r}"
                        )
                    label_variants[variant] = canonical
            for canonical in label_synonyms:
                if canonical in label_variants:
                    raise InvalidEntityRulesError(f"canonical key {canonical!r} is also a variant")
            names: set[str] = set()
            for name in _list(excluded_raw.get(label) or [], f"excluded.{label}"):
                _require_canonical(label, _text(name, "an excluded name"))
                if name in label_variants:
                    raise InvalidEntityRulesError(f"excluded name {name!r} is a variant")
                names.add(name)
            variants[label] = label_variants
            excluded[label] = frozenset(names)

        known = None if known_source_types is None else set(known_source_types)
        pairs: set[frozenset[str]] = set()
        listed_pairs = same_finding_raw.get("source_type_pairs")
        for pair in _list(listed_pairs, "same_finding.source_type_pairs"):
            entries = _list(pair, "a source type pair")
            if len(entries) != 2:
                raise InvalidEntityRulesError(f"a source type pair has {len(entries)} entries")
            types = {_text(t, "a source type") for t in entries}
            if known is not None and not types <= known:
                raise InvalidEntityRulesError(f"unknown source type in {sorted(types)}")
            if len(types) != 2:
                raise InvalidEntityRulesError("a source type pair names one type twice")
            pairs.add(frozenset(types))
        threshold = same_finding_raw.get("title_token_jaccard_min")
        if isinstance(threshold, bool) or not isinstance(threshold, int | float):
            raise InvalidEntityRulesError("same_finding.title_token_jaccard_min is not a number")
        if not 0.0 < float(threshold) <= 1.0:
            raise InvalidEntityRulesError(
                f"same_finding.title_token_jaccard_min {threshold} is outside (0, 1]"
            )
        return EntityRules(
            rules_hash, variants, excluded, SameFinding(frozenset(pairs), float(threshold))
        )

    def canonical_key(self, label: str, name: str) -> str:
        normal = normal_form(label, name)
        return self.variant_to_canonical[label].get(normal, normal)

    def is_excluded(self, label: str, canonical_key: str) -> bool:
        return canonical_key in self.excluded.get(label, frozenset())


class IndependentSources:
    """Two participants are the same finding when the rules list their source-type pair and their
    titles' token sets overlap (Jaccard) at least the threshold; independent when their source
    types differ and they are not the same finding. The count is the largest pairwise
    independent set."""

    def __init__(self, same_finding: SameFinding) -> None:
        self._same_finding = same_finding

    def same_finding(self, a: EpisodeSignal, b: EpisodeSignal) -> bool:
        if not self._same_finding.lists_pair(a.source_type, b.source_type):
            return False
        ta, tb = title_tokens(a.title), title_tokens(b.title)
        if not ta or not tb:
            return False
        return len(ta & tb) / len(ta | tb) >= self._same_finding.title_token_jaccard_min

    def independent(self, a: EpisodeSignal, b: EpisodeSignal) -> bool:
        return a.source_type != b.source_type and not self.same_finding(a, b)

    def count(self, participants: Sequence[EpisodeSignal]) -> int:
        # At most one participant per source type can be chosen, so search over source types.
        by_type: dict[str, list[EpisodeSignal]] = {}
        for s in participants:
            by_type.setdefault(s.source_type, []).append(s)
        return self._best(list(by_type.values()), 0, [])

    def _best(
        self, types: list[list[EpisodeSignal]], index: int, chosen: list[EpisodeSignal]
    ) -> int:
        if index == len(types):
            return len(chosen)
        upper = len(chosen) + len(types) - index
        best = self._best(types, index + 1, chosen)
        for candidate in types[index]:
            if best == upper:
                break
            if all(self.independent(c, candidate) for c in chosen):
                chosen.append(candidate)
                best = max(best, self._best(types, index + 1, chosen))
                chosen.pop()
        return best


def title_tokens(title: str | None) -> set[str]:
    if title is None:
        return set()
    text = normal_form(MECHANISM, title)
    return set(text.split(" ")) if text else set()


@dataclass(frozen=True)
class Episode:
    """Opened at the publication of the signal that completed its first independent pair, with
    every signal that joined it, in replay order."""

    opened_at: datetime
    participants: tuple[EpisodeSignal, ...]

    def published_by_opening(self) -> tuple[EpisodeSignal, ...]:
        return tuple(p for p in self.participants if p.published_date <= self.opened_at)


def build_episodes(
    signals: Iterable[EpisodeSignal], independence: IndependentSources
) -> list[Episode]:
    """Replay in `(published_date, event_id)` order. A signal published no later than the window
    after an open episode's opening joins it. Otherwise the open episode closes, candidates
    published more than the window before the signal are dropped, and the signal becomes a
    candidate; two independent candidates open an episode at this signal's publication and the
    candidate list is emptied."""
    ordered = sorted(signals, key=lambda s: (s.published_date, s.event_id))
    episodes: list[Episode] = []
    opened_at: datetime | None = None
    open_: list[EpisodeSignal] = []
    candidates: list[EpisodeSignal] = []
    for signal in ordered:
        if opened_at is not None and signal.published_date <= opened_at + WINDOW:
            open_.append(signal)
            continue
        if opened_at is not None:
            episodes.append(Episode(opened_at, tuple(open_)))
            opened_at = None
            open_ = []
        oldest = signal.published_date - WINDOW
        candidates = [c for c in candidates if c.published_date >= oldest]
        candidates.append(signal)
        if independence.count(candidates) >= 2:
            opened_at = signal.published_date
            open_ = list(candidates)
            candidates = []
    if opened_at is not None:
        episodes.append(Episode(opened_at, tuple(open_)))
    return episodes


def _require_canonical(label: str, name: str) -> None:
    normal = normal_form(label, name)
    if normal != name:
        raise InvalidEntityRulesError(
            f"{label} name {name!r} is not in canonical form ({normal!r})"
        )


def _mapping(value: Any, what: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise InvalidEntityRulesError(f"{what} is not a mapping")
    for key in value:
        if not isinstance(key, str):
            raise InvalidEntityRulesError(f"{what} has a key that is not text: {key!r}")
    return value


def _list(value: Any, what: str) -> list[Any]:
    if value is None:
        raise InvalidEntityRulesError(f"{what} is missing")
    if not isinstance(value, list):
        raise InvalidEntityRulesError(f"{what} is not a list")
    return value


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str):
        raise InvalidEntityRulesError(f"{what} is not text: {value!r}")
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
