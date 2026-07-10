from __future__ import annotations

import re

ORG_SUFFIX = r"(?:公司|集团|基金|园区|医院|大学|学院|研究院|实验室|协会|中心|Biotech|Bio|Pharma|Therapeutics|Inc\.?|Ltd\.?)"
ORG_RE = re.compile(rf"([\u4e00-\u9fa5A-Za-z0-9（）()·.\-& ]{{2,60}}{ORG_SUFFIX})")
PERSON_ROLE_RE = re.compile(r"([\u4e00-\u9fa5]{2,4})\s*(?:，|,|：|:|\||-|—)?\s*(创始人|联合创始人|董事长|总经理|CEO|CTO|CSO|CFO|教授|博士|主任|负责人|合伙人|总监)")
PROJECT_RE = re.compile(r"([A-Z]{2,}[A-Z0-9-]{1,30}|[\u4e00-\u9fa5A-Za-z0-9-]{2,40}(?:项目|平台|产品|药物|疗法|管线))")
AMOUNT_RE = re.compile(r"((?:数)?\d+(?:\.\d+)?\s*(?:万|亿|million|billion)?\s*(?:美元|人民币|元|USD|RMB)?)")
ROUND_RE = re.compile(r"([A-D]\+?轮|天使轮|Pre-A轮|IPO|并购|战略融资)")


def extract_candidates(block: dict, page_type: str, source: dict) -> list[dict]:
    text = str(block.get("text") or "")
    candidates: list[dict] = []
    candidates.extend(_organizations(text, source))
    candidates.extend(_people(text, source, page_type))
    candidates.extend(_projects(text, source, page_type))
    candidates.extend(_events(text, source))
    candidates.extend(_needs_resources(text, source))
    for candidate in candidates:
        candidate.setdefault("evidence_excerpt", str(block.get("evidence_excerpt") or text[:280]))
        candidate.setdefault("source_position", f"block:{block.get('index', 0)}")
        candidate.setdefault("fact_level", "unknown")
    return _dedupe(candidates)


def _organizations(text: str, source: dict) -> list[dict]:
    rows = []
    for match in ORG_RE.finditer(text):
        name = _clean_name(match.group(1))
        if len(name) < 3 or _is_bad_heading(name):
            continue
        rows.append(_candidate("organization", "organization", "standard_name", name, name, "org_suffix", 78, source, subject_label=name))
    return rows


def _people(text: str, source: dict, page_type: str) -> list[dict]:
    rows = []
    for match in PERSON_ROLE_RE.finditer(text):
        name = match.group(1).strip()
        role = match.group(2).strip()
        if name in {"团队", "公司", "项目", "管理"}:
            continue
        score = 84 if page_type == "team_page" else 73
        rows.append(_candidate("person", "person", "name", name, name, "person_role", score, source, subject_label=name, payload={"role": role}))
        rows.append(_candidate("field", "person", "public_role", role, role, "person_role_field", score - 3, source, subject_label=name, payload={"person_name": name}))
    intro = re.search(r"(?:本人|我是)\s*([\u4e00-\u9fa5]{2,4})", text)
    if intro:
        name = intro.group(1)
        rows.append(_candidate("person", "person", "name", name, name, "self_intro_name", 76, source, subject_label=name))
        focus = re.search(r"(?:专注|擅长|从事|负责)\s*([^。；;\n]+)", text)
        if focus:
            value = focus.group(1).strip(" ，")
            rows.append(_candidate("field", "person", "ability_tags", value, value, "self_intro_expertise", 72, source, subject_label=name, payload={"person_name": name}))
    return rows


def _projects(text: str, source: dict, page_type: str) -> list[dict]:
    rows = []
    if page_type not in {"product_pipeline", "news_event", "single_subject_profile"}:
        return rows
    for match in PROJECT_RE.finditer(text):
        value = _clean_name(match.group(1))
        if len(value) < 3 or value in {"产品管线", "技术平台"}:
            continue
        rows.append(_candidate("project", "project", "name", value, value, "project_pattern", 70, source, subject_label=value))
    return rows


def _events(text: str, source: dict) -> list[dict]:
    rows = []
    event_keywords = {
        "financing": ["融资", "募资", "投资", "A轮", "B轮", "Pre-A", "IPO", "funding", "series"],
        "approval": ["获批", "批准", "注册", "IND", "NDA", "上市申请"],
        "cooperation": ["合作", "签约", "授权", "license", "collaboration", "共建"],
        "clinical": ["临床", "入组", "III期", "II期", "I期", "试验"],
        "recruitment": ["招聘", "岗位", "扩招", "任命"],
    }
    lowered = text.lower()
    for event_type, keywords in event_keywords.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            payload = {"event_type": event_type}
            amount = AMOUNT_RE.search(text)
            round_match = ROUND_RE.search(text)
            if amount:
                payload["amount"] = amount.group(1).strip()
            if round_match:
                payload["round"] = round_match.group(1).strip()
            score = 82 if event_type in {"financing", "approval"} else 72
            rows.append(_candidate("event", "event", "event", event_type, event_type, f"event_{event_type}", score, source, payload=payload))
    return rows


def _needs_resources(text: str, source: dict) -> list[dict]:
    rows = []
    patterns = [
        ("need", "organization", "needs", ["需要", "寻求", "希望", "需求", "正在寻找"], 70),
        ("resource", "organization", "resources", ["可提供", "拥有", "资源", "平台", "产能", "渠道"], 68),
        ("risk", "organization", "risk", ["处罚", "诉讼", "召回", "失败", "终止", "安全性"], 76),
        ("opportunity", "organization", "opportunity", ["合作机会", "招商", "落地", "扩产", "融资", "对接"], 70),
    ]
    for ctype, stype, field, keywords, score in patterns:
        if any(keyword in text for keyword in keywords):
            value = _sentence_with_any(text, keywords)
            rows.append(_candidate(ctype, stype, field, value, value, f"{ctype}_keywords", score, source))
    return rows


def _candidate(candidate_type: str, subject_type: str, field_name: str, raw_value: str, normalized_value: str, rule: str, score: int, source: dict, *, subject_label: str = "", payload: dict | None = None) -> dict:
    return {
        "candidate_type": candidate_type,
        "subject_type": subject_type,
        "subject_label": subject_label or normalized_value,
        "field_name": field_name,
        "raw_value": raw_value[:2000],
        "normalized_value": normalized_value[:2000],
        "payload": payload or {},
        "source_url": source.get("source_url") or "",
        "source_title": source.get("source_title") or "",
        "extraction_rule": rule,
        "confidence_score": score,
    }


def _clean_name(value: str) -> str:
    value = re.sub(r"\s+", "", value or "")
    return value.strip("，。；;、（）()[]【】")


def _is_bad_heading(value: str) -> bool:
    return value in {"有限公司", "生物医药公司", "管理团队"} or len(value) > 80


def _sentence_with_any(text: str, keywords: list[str]) -> str:
    for part in re.split(r"[。；;\n]", text):
        if any(keyword in part for keyword in keywords):
            return part.strip()[:500]
    return text[:500]


def _dedupe(rows: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    result = []
    for row in rows:
        key = (row["candidate_type"], row.get("field_name") or "", row.get("normalized_value") or "")
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result
