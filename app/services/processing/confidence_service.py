from __future__ import annotations


HIGH_RISK_FIELDS = {"amount", "round", "clinical_stage", "approval", "registration_result", "relationship", "event"}


def confidence_level(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    return "low"


def quality_gate(candidate: dict) -> tuple[str, list[str]]:
    warnings = list(candidate.get("warnings") or [])
    score = int(candidate.get("confidence_score") or 0)
    field_name = str(candidate.get("field_name") or "")
    if not candidate.get("evidence_excerpt"):
        warnings.append("missing_evidence")
    if score < 60:
        warnings.append("low_confidence")
    if field_name in HIGH_RISK_FIELDS and score < 85:
        warnings.append("high_risk_field_requires_review")
    if candidate.get("candidate_type") in {"event", "relationship"}:
        warnings.append("formal_write_blocked_until_manual_review")
    if candidate.get("candidate_type") == "person" and str(candidate.get("normalized_value") or "") in {"团队", "管理团队", "核心团队"}:
        warnings.append("heading_as_person_blocked")
    status = "valid"
    if warnings:
        status = "blocked" if "heading_as_person_blocked" in warnings else "needs_review"
    return status, list(dict.fromkeys(warnings))
