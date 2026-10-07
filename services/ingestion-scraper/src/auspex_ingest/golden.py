import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GoldenDocument:
    source_type: str
    external_id: str
    source_url: str
    published_date: str
    raw_content: str
    labels: dict[str, Any] = field(default_factory=dict)


def load_golden_set(golden_dir: Path) -> list[GoldenDocument]:
    docs = []
    for f in sorted(golden_dir.glob("*.json")):
        data = json.loads(f.read_text())
        docs.append(
            GoldenDocument(
                source_type=data["source_type"],
                external_id=data["external_id"],
                source_url=data["source_url"],
                published_date=data["published_date"],
                raw_content=data["raw_content"],
                labels=data["labels"],
            )
        )
    return docs


def score_field(predicted: list[str], expected: list[str]) -> dict[str, float]:
    pred_set = set(predicted)
    exp_set = set(expected)
    if not exp_set and not pred_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not pred_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    if not exp_set:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0}
    tp = len(pred_set & exp_set)
    precision = tp / len(pred_set)
    recall = tp / len(exp_set)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _macro(field_results: list[dict[str, float]]) -> dict[str, float]:
    if not field_results:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    n = len(field_results)
    return {
        "precision": sum(r["precision"] for r in field_results) / n,
        "recall": sum(r["recall"] for r in field_results) / n,
        "f1": sum(r["f1"] for r in field_results) / n,
    }


_LABELLED_SCALAR_FIELDS = ("event_type", "primary_company")
_LABELLED_LIST_FIELDS = ("program_identifiers", "trial_ids")


def _same_label(predicted: object, expected: object) -> bool:
    if isinstance(predicted, str) and isinstance(expected, str):
        return predicted.strip().casefold() == expected.strip().casefold()
    return predicted == expected


def _score_labelled_fields(
    golden: list[GoldenDocument], results: list[dict[str, Any] | None]
) -> dict[str, dict[str, float]]:
    # Older golden documents predate these labels, so each field is scored only where labelled.
    out: dict[str, dict[str, float]] = {}
    for f in _LABELLED_SCALAR_FIELDS:
        hits = [
            _same_label((pred or {}).get(f), doc.labels[f])
            for doc, pred in zip(golden, results)
            if doc.labels.get("is_signal") and f in doc.labels
        ]
        out[f] = {"accuracy": sum(hits) / len(hits) if hits else 0.0, "labelled": len(hits)}
    for f in _LABELLED_LIST_FIELDS:
        per_doc = [
            score_field(list((pred or {}).get(f, [])), list(doc.labels[f]))
            for doc, pred in zip(golden, results)
            if doc.labels.get("is_signal") and f in doc.labels
        ]
        out[f] = {**_macro(per_doc), "labelled": len(per_doc)}
    return out


def score_batch(
    golden: list[GoldenDocument],
    results: list[dict[str, Any] | None],
) -> dict[str, Any]:
    """
    Compute aggregate extraction quality metrics.

    results[i] is a dict with keys {is_signal, gene_targets, mechanisms,
    companies_mentioned, directionality} when the extractor returned a signal,
    or None when it returned no signal.

    Returns a dict with:
      - "is_signal": {"tp", "fp", "fn", "tn"}
      - per list field: macro {"precision", "recall", "f1"} over signal-labeled docs
      - "event_type", "primary_company": {"accuracy", "labelled"} over signal docs carrying
        that label; "program_identifiers", "trial_ids": macro scores plus "labelled"
      - "prefilter_fn_rate": fraction of prefilter_should_pass=True docs that were rejected
        (requires "prefilter_passed" key in each result dict; omitted if not present)
    """
    _list_fields = ["gene_targets", "mechanisms", "companies_mentioned"]

    is_signal_cm: dict[str, int] = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    field_acc: dict[str, list[dict[str, float]]] = {f: [] for f in _list_fields}

    for doc, pred in zip(golden, results):
        label_signal: bool = bool(doc.labels.get("is_signal", False))
        pred_signal = pred is not None

        if label_signal and pred_signal:
            is_signal_cm["tp"] += 1
        elif label_signal and not pred_signal:
            is_signal_cm["fn"] += 1
        elif not label_signal and pred_signal:
            is_signal_cm["fp"] += 1
        else:
            is_signal_cm["tn"] += 1

        if label_signal:
            for f in _list_fields:
                predicted_list: list[str] = list(pred.get(f, [])) if pred else []
                expected_list: list[str] = list(doc.labels.get(f, []))
                field_acc[f].append(score_field(predicted_list, expected_list))

    out: dict[str, Any] = {"is_signal": is_signal_cm}
    for f in _list_fields:
        out[f] = _macro(field_acc[f])
    out.update(_score_labelled_fields(golden, results))

    return out
