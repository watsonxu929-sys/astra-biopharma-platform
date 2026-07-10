from __future__ import annotations

import re


def classify_page(title: str, text: str, source_structure: str = "") -> dict[str, object]:
    haystack = f"{source_structure}\n{title}\n{text[:4000]}".lower()
    chinese = f"{title}\n{text[:4000]}"
    signals: list[str] = []
    if any(k in haystack for k in ["team", "leadership", "management"]) or any(k in chinese for k in ["团队", "管理层", "创始人", "董事", "高管"]):
        page_type = "team_page"
        signals.append("team_keywords")
    elif any(k in haystack for k in ["pipeline", "product"]) or any(k in chinese for k in ["管线", "产品", "适应症", "临床", "注册"]):
        page_type = "product_pipeline"
        signals.append("pipeline_keywords")
    elif any(k in haystack for k in ["career", "jobs", "recruit"]) or any(k in chinese for k in ["招聘", "岗位", "职位", "人才"]):
        page_type = "recruitment"
        signals.append("recruitment_keywords")
    elif any(k in haystack for k in ["policy", "notice", "government"]) or any(k in chinese for k in ["政策", "公告", "申报", "补贴", "园区"]):
        page_type = "policy_resource"
        signals.append("policy_keywords")
    elif any(k in chinese for k in ["融资", "获批", "合作", "并购", "签署", "发布", "宣布"]) or any(k in haystack for k in ["funding", "financing", "approved", "announced"]):
        page_type = "news_event"
        signals.append("event_keywords")
    elif len(re.findall(r"[\n。；;]\s*.{4,80}[\n。；;]", text[:5000])) >= 8:
        page_type = "multi_subject_list"
        signals.append("list_shape")
    else:
        page_type = "single_subject_profile" if len(text) >= 160 else "mixed_uncertain"
        signals.append("fallback")
    if source_structure and source_structure not in {"unknown", page_type}:
        signals.append(f"source_structure:{source_structure}")
    return {"page_type": page_type, "signals": signals, "confidence": 85 if signals[0] != "fallback" else 58}
