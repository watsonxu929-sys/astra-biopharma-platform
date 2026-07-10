from __future__ import annotations

from datetime import datetime
from typing import Any


def _tokens(value: str | None) -> set[str]:
    text = (value or "").replace("；", ";").replace("，", ";").replace(",", ";")
    return {item.strip().casefold() for item in text.split(";") if item.strip()}


def match_need_offering(need: dict[str, Any], offering: dict[str, Any], allow_self: bool = False) -> dict[str, Any] | None:
    if not allow_self and need.get("membership_id") == offering.get("membership_id"):
        return None

    score = 0
    reasons: list[str] = []
    missing: list[str] = []
    if need.get("need_type") and offering.get("offering_type") and need["need_type"].casefold() == offering["offering_type"].casefold():
        score += 25
        reasons.append("需求类型与供给类型一致。")
    else:
        missing.append("类型不完全一致")
    overlap = _tokens(need.get("industry_tags")) & _tokens(offering.get("industry_tags"))
    if overlap:
        score += min(25, 10 + len(overlap) * 5)
        reasons.append("命中标签：" + "、".join(sorted(overlap)))
    else:
        missing.append("赛道标签未命中")
    if need.get("region") and offering.get("region") and need["region"] == offering["region"]:
        score += 10
        reasons.append("地区匹配。")
    elif need.get("region") and offering.get("region"):
        score += 4
    else:
        missing.append("地区信息不足")
    if need.get("urgency") in {"high", "urgent"}:
        score += 8
        reasons.append("需求紧急度较高。")
    if need.get("description") and offering.get("description"):
        score += 12
        reasons.append("双方描述信息完整。")
    else:
        missing.append("描述信息不足")
    score = max(0, min(100, score))
    if score < 20:
        return None
    grade = "S" if score >= 85 else ("A" if score >= 70 else ("B" if score >= 50 else "C"))
    return {
        "score": score,
        "grade": grade,
        "matched_tags": sorted(overlap),
        "reasons": reasons,
        "missing": missing,
        "scored_at": datetime.now().replace(microsecond=0).isoformat(),
    }
