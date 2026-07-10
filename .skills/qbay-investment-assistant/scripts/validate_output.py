#!/usr/bin/env python3
"""Validate Q-BAY assessment JSON without requiring third-party packages."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ALLOWED_GRADES = {"A", "B", "C", "D", "R", "OUT_OF_SCOPE", "UNVERIFIED"}
REQUIRED = {
    "company_name",
    "identity_status",
    "region_type",
    "track",
    "business_type",
    "facts",
    "score_breakdown",
    "grade",
    "grade_reason",
    "qbay_fit",
    "qiantang_fit",
    "sources",
    "data_gaps",
}
SCORE_LIMITS = {
    "track_fit": (0, 20),
    "development_signal": (0, 25),
    "space_fit": (0, 20),
    "window": (0, 15),
    "reachability": (0, 10),
    "data_completeness": (0, 10),
    "resistance": (-30, 0),
    "total": (0, 100),
}


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED - data.keys()
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")
    if data.get("grade") not in ALLOWED_GRADES:
        errors.append(f"Invalid grade: {data.get('grade')!r}")
    scores = data.get("score_breakdown") or {}
    for key, (low, high) in SCORE_LIMITS.items():
        value = scores.get(key)
        if not isinstance(value, (int, float)):
            errors.append(f"score_breakdown.{key} must be numeric")
        elif not low <= value <= high:
            errors.append(f"score_breakdown.{key} must be between {low} and {high}")
    if all(isinstance(scores.get(k), (int, float)) for k in SCORE_LIMITS if k != "total"):
        computed = sum(scores[k] for k in SCORE_LIMITS if k != "total")
        total = scores.get("total")
        if isinstance(total, (int, float)) and abs(computed - total) > 0.01:
            errors.append(f"score total mismatch: expected {computed}, got {total}")
    for i, source in enumerate(data.get("sources") or []):
        if not source.get("title") or not source.get("url"):
            errors.append(f"sources[{i}] requires title and url")
        if source.get("source_level") not in {"S", "A", "B", "C"}:
            errors.append(f"sources[{i}].source_level invalid")
    if data.get("region_type") == "local_resource" and data.get("grade") != "R":
        errors.append("local_resource must use grade R")
    if data.get("identity_status") != "confirmed" and data.get("grade") not in {"UNVERIFIED", "OUT_OF_SCOPE"}:
        errors.append("unconfirmed identity should not receive A/B/C/D/R")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_output.py assessment.json", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Failed to read JSON: {exc}", file=sys.stderr)
        return 2
    errors = validate(data)
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
