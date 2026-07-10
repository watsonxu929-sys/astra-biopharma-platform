from __future__ import annotations

from datetime import datetime
from typing import Any


GRADE_ORDER = {"C": 1, "B": 2, "A": 3, "S": 4}


def score_to_grade(score: int) -> str:
    if score >= 85:
        return "S"
    if score >= 70:
        return "A"
    if score >= 50:
        return "B"
    return "C"


def manual_grade_requires_reason(system_grade: str, manual_grade: str, reason: str) -> bool:
    return GRADE_ORDER.get(manual_grade, 0) > GRADE_ORDER.get(system_grade, 0) and not reason.strip()


def score_lead(profile: dict[str, Any]) -> dict[str, Any]:
    subject = profile.get("subject") or {}
    stats = profile.get("stats") or {}
    completeness = profile.get("completeness") or {}
    review = profile.get("review") or {}
    lead = profile.get("lead") or {}

    dimensions = {
        "business_fit": 0,
        "recent_activity": 0,
        "relationship_reach": 0,
        "resource_need_fit": 0,
        "data_completeness": 0,
        "followup_urgency": 0,
        "risk_adjustment": 0,
    }
    positive: list[str] = []
    negative: list[str] = []
    used: list[str] = []
    missing: list[str] = []

    tags = str(subject.get("tags") or "")
    if tags:
        dimensions["business_fit"] += 15
        positive.append("主体已有赛道或能力标签。")
        used.append("subject.tags")
    else:
        missing.append("主体标签")
    if subject.get("type") == "project":
        dimensions["business_fit"] += 5
        positive.append("项目类线索具备明确业务对象。")
    if stats.get("events", 0):
        dimensions["recent_activity"] += min(15, 6 + int(stats["events"]) * 3)
        positive.append("近期存在关联事件。")
        used.append("events")
    else:
        missing.append("近期事件")
    if stats.get("people", 0):
        dimensions["relationship_reach"] += min(20, 8 + int(stats["people"]) * 4)
        positive.append("存在可切入的相关人物。")
        used.append("relations.people")
    else:
        missing.append("核心联系人")
    if stats.get("resources", 0) or stats.get("projects", 0):
        dimensions["resource_need_fit"] += min(20, 8 + (int(stats.get("resources", 0)) + int(stats.get("projects", 0))) * 4)
        positive.append("存在资源或项目匹配线索。")
        used.append("resources/projects")
    else:
        missing.append("资源/需求")
    dimensions["data_completeness"] = min(10, int(completeness.get("percent", 0)) // 10)
    used.append("completeness")
    if lead.get("next_action_at"):
        dimensions["followup_urgency"] += 7
        positive.append("已设置下一步跟进时间。")
        used.append("lead.next_action_at")
    if review.get("open_count", 0):
        penalty = min(20, int(review["open_count"]) * 5 + int(review.get("conflict_count", 0)) * 5)
        dimensions["risk_adjustment"] -= penalty
        negative.append("存在待审核或冲突，影响业务判断。")
        used.append("review")
    if subject.get("is_active") is False:
        dimensions["risk_adjustment"] -= 20
        negative.append("主体已停用。")

    raw_score = sum(dimensions.values())
    total = max(0, min(100, raw_score))
    return {
        "score": total,
        "grade": score_to_grade(total),
        "dimensions": dimensions,
        "positive_reasons": positive,
        "negative_reasons": negative,
        "used_data": used,
        "missing_data": missing,
        "scored_at": datetime.now().replace(microsecond=0).isoformat(),
    }
