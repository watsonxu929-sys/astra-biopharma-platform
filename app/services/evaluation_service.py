from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _set(values: Iterable[Any]) -> set[str]:
    return {_norm(value) for value in values if _norm(value)}


def precision_recall_f1(predicted: Iterable[Any], expected: Iterable[Any]) -> dict[str, float]:
    predicted_set, expected_set = _set(predicted), _set(expected)
    matches = len(predicted_set & expected_set)
    precision = matches / len(predicted_set) if predicted_set else (1.0 if not expected_set else 0.0)
    recall = matches / len(expected_set) if expected_set else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _facts(record: dict[str, Any]) -> set[str]:
    facts: set[str] = set()
    for field in ("products", "indications", "targets", "regions", "dates", "amounts", "stages"):
        for value in record.get(field) or []:
            facts.add(f"{field}:{_norm(value)}")
    return facts


def evaluate_records(gold: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(item.get("sample_id")): item for item in predictions}
    event_hits = 0
    organizations_expected: list[str] = []
    organizations_predicted: list[str] = []
    people_expected: list[str] = []
    people_predicted: list[str] = []
    fact_hits = fact_total = evidence_total = evidence_present = evidence_correct = 0
    unsupported = predicted_fact_total = reviewable = 0
    collection_ms: list[float] = []
    parsing_ms: list[float] = []
    ai_ms: list[float] = []
    costs: list[float] = []

    for expected in gold:
        predicted = by_id.get(str(expected.get("sample_id")), {})
        event_hits += int(_norm(predicted.get("event_type")) == _norm(expected.get("event_type")))
        organizations_expected.extend(expected.get("organizations") or [])
        organizations_predicted.extend(predicted.get("organizations") or [])
        people_expected.extend(expected.get("people") or [])
        people_predicted.extend(predicted.get("people") or [])
        expected_facts, predicted_facts = _facts(expected), _facts(predicted)
        fact_hits += len(expected_facts & predicted_facts)
        fact_total += len(expected_facts)
        predicted_fact_total += len(predicted_facts)
        unsupported += len(predicted_facts - expected_facts)

        candidates = predicted.get("candidates") or []
        evidence_total += len(candidates)
        for candidate in candidates:
            excerpt = _norm(candidate.get("evidence_excerpt"))
            has_locator = any(candidate.get(key) is not None for key in ("char_start", "page_number", "table_number"))
            evidence_present += int(bool(excerpt and has_locator))
            source_text = _norm(expected.get("text"))
            supported = bool(excerpt and excerpt in source_text)
            evidence_correct += int(supported)
        reviewable += int(bool(candidates) and all(
            _norm(item.get("evidence_excerpt")) in _norm(expected.get("text"))
            for item in candidates
        ))
        timings = predicted.get("latency_ms") or {}
        for bucket, target in (("collection", collection_ms), ("parsing", parsing_ms), ("ai", ai_ms)):
            if timings.get(bucket) is not None:
                target.append(float(timings[bucket]))
        if predicted.get("estimated_cost_usd") is not None:
            costs.append(float(predicted["estimated_cost_usd"]))

    count = len(gold)
    average = lambda values: sum(values) / len(values) if values else 0.0
    return {
        "sample_count": count,
        "event_classification_accuracy": event_hits / count if count else 0.0,
        "organization": precision_recall_f1(organizations_predicted, organizations_expected),
        "person": precision_recall_f1(people_predicted, people_expected),
        "key_fact_accuracy": fact_hits / fact_total if fact_total else 1.0,
        "evidence_coverage": evidence_present / evidence_total if evidence_total else 0.0,
        "evidence_correctness": evidence_correct / evidence_total if evidence_total else 0.0,
        "hallucination_rate": unsupported / predicted_fact_total if predicted_fact_total else 0.0,
        "reviewability_rate": reviewable / count if count else 0.0,
        "average_latency_ms": {
            "collection": average(collection_ms),
            "parsing": average(parsing_ms),
            "ai": average(ai_ms),
        },
        "total_estimated_cost_usd": sum(costs),
        "average_cost_per_item_usd": average(costs),
    }


def compare_modes(gold: list[dict[str, Any]], results: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {mode: evaluate_records(gold, predictions) for mode, predictions in results.items()}
