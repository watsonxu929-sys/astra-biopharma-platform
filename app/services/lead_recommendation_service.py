from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def generate_lead_recommendations(profile: dict[str, Any], scoring: dict[str, Any]) -> list[dict[str, Any]]:
    subject = profile.get("subject") or {}
    stats = profile.get("stats") or {}
    review = profile.get("review") or {}
    missing = set(scoring.get("missing_data") or [])
    due = (date.today() + timedelta(days=3)).isoformat()
    output: list[dict[str, Any]] = []

    def add(key: str, title: str, basis: str, priority: str = "P2") -> None:
        output.append({
            "key": key,
            "title": title,
            "basis": basis,
            "priority": priority,
            "subject_type": subject.get("type"),
            "subject_id": subject.get("external_id"),
            "recommended_due": due,
        })

    if "核心联系人" in missing:
        add("add_contact", "补充核心联系人", "当前主体缺少可达联系人。", "P1")
    if "主体标签" in missing:
        add("fill_tags", "核实赛道和发展阶段", "主体标签或阶段信息不足。", "P2")
    if stats.get("people", 0):
        add("contact_person", "通过相关人物切入沟通", "已存在人物关系，可人工选择沟通入口。", "P1")
    if stats.get("resources", 0) or stats.get("projects", 0):
        add("match_resource", "评估资源或项目匹配", "主体存在资源/项目关联。", "P2")
    if review.get("open_count", 0):
        add("resolve_review", "处理影响判断的数据审核", "存在待审核或冲突记录。", "P1")
    if int(scoring.get("score", 0)) >= 70:
        add("invite_qbay", "邀请参加 Q-BAY 活动", "线索评分较高，可进入俱乐部运营触达。", "P2")
    if not output:
        add("schedule_followup", "安排一次人工访谈", "当前线索信息基本可用，建议确认下一步合作可能。", "P2")
    return output
