from __future__ import annotations

import re

ORG_SUFFIX = r"(?:公司|集团|基金|园区|医院|大学|学院|研究院|实验室|协会|中心|Biotech|Bio|Pharma|Therapeutics|Inc\.?|Ltd\.?)"
ORG_RE = re.compile(rf"([\u4e00-\u9fa5A-Za-z0-9（）()·.\-& ]{{2,60}}{ORG_SUFFIX})")
PERSON_ROLE_RE = re.compile(r"([\u4e00-\u9fa5]{2,4})\s*(?:，|,|：|:|\||-|—)?\s*(创始人|联合创始人|董事长|总经理|CEO|CTO|CSO|CFO|教授|博士|主任|负责人|合伙人|总监)")
PROJECT_RE = re.compile(r"([A-Z]{2,}[A-Z0-9-]{1,30}|[\u4e00-\u9fa5A-Za-z0-9-]{2,40}(?:项目|平台|产品|药物|疗法|管线))")
AMOUNT_RE = re.compile(r"((?:数)?\d+(?:\.\d+)?\s*(?:万|亿|million|billion)?\s*(?:美元|人民币|元|USD|RMB)?)")
ROUND_RE = re.compile(r"([A-D]\+?轮|天使轮|Pre-A轮|IPO|并购|战略融资)")

EVENT_TYPE_MAP = {
    "financing": "融资事件",
    "approval": "监管审批",
    "cooperation": "许可合作",
    "clinical": "临床进展",
    "recruitment": "人事变动",
    "product_launch": "产品发布",
    "tech_progress": "技术进展",
    "merger": "并购交易",
    "policy": "政策发布",
    "conference": "行业活动",
    "corporate": "企业动态",
}

MAX_CANDIDATES_PER_TYPE = {
    "organization": 5,
    "person": 5,
    "project": 3,
    "event": 1,
    "field": 3,
    "relationship": 3,
    "risk": 2,
    "opportunity": 2,
    "need": 1,
    "resource": 1,
}

def extract_candidates(block: dict, page_type: str, source: dict) -> list[dict]:
    text = str(block.get("text") or "")
    candidates: list[dict] = []
    candidates.extend(_organizations(text, source))
    candidates.extend(_people(text, source, page_type))
    candidates.extend(_projects(text, source, page_type))
    candidates.extend(_events(text, source))
    for candidate in candidates:
        candidate.setdefault("evidence_excerpt", str(block.get("evidence_excerpt") or text[:280]))
        candidate.setdefault("source_position", f"block:{block.get('index', 0)}")
        candidate.setdefault("fact_level", "unknown")
    return _dedupe(candidates)

def _organizations(text: str, source: dict) -> list[dict]:
    rows = []
    seen_names = set()
    for match in ORG_RE.finditer(text):
        name = _clean_name(match.group(1))
        if len(name) < 3 or _is_bad_heading(name) or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(_candidate("organization", "organization", "standard_name", name, name, "org_suffix", 78, source, subject_label=name))
        if len(rows) >= MAX_CANDIDATES_PER_TYPE["organization"]:
            break
    return rows

def _people(text: str, source: dict, page_type: str) -> list[dict]:
    rows = []
    seen_names = set()
    for match in PERSON_ROLE_RE.finditer(text):
        name = match.group(1).strip()
        role = match.group(2).strip()
        if name in {"团队", "公司", "项目", "管理"} or name in seen_names:
            continue
        seen_names.add(name)
        score = 84 if page_type == "team_page" else 73
        rows.append(_candidate("person", "person", "name", name, name, "person_role", score, source, subject_label=name, payload={"role": role}))
        if len(rows) >= MAX_CANDIDATES_PER_TYPE["person"]:
            break
    return rows

def _projects(text: str, source: dict, page_type: str) -> list[dict]:
    rows = []
    seen_names = set()
    if page_type not in {"product_pipeline", "news_event", "single_subject_profile"}:
        return rows
    for match in PROJECT_RE.finditer(text):
        value = _clean_name(match.group(1))
        if len(value) < 3 or value in {"产品管线", "技术平台"} or value in seen_names:
            continue
        seen_names.add(value)
        rows.append(_candidate("project", "project", "name", value, value, "project_pattern", 70, source, subject_label=value))
        if len(rows) >= MAX_CANDIDATES_PER_TYPE["project"]:
            break
    return rows

def _events(text: str, source: dict) -> list[dict]:
    rows = []
    event_keywords = {
        "approval": ["获批", "批准", "注册", "IND", "NDA", "上市申请", "approved", "approval", "marketing authorization"],
        "clinical": ["临床", "入组", "III期", "II期", "I期", "试验", "clinical trial", "phase"],
        "financing": ["融资", "募资", "投资", "A轮", "B轮", "Pre-A", "IPO", "funding", "series"],
        "merger": ["并购", "收购", "M&A", "acquisition", "merger"],
        "cooperation": ["合作", "签约", "授权", "license", "collaboration", "共建", "partnership"],
        "product_launch": ["上市", "发布", "推出", "launch", "release"],
        "tech_progress": ["突破", "进展", "研究发现", "技术", "研发", "breakthrough"],
        "corporate": ["成立", "更名", "重组", "退市", "入选", "榜单", "corporate"],
        "policy": ["政策", "通知", "办法", "规定", "regulation", "policy"],
        "conference": ["会议", "论坛", "峰会", "研讨会", "conference", "summit"],
        "recruitment": ["任命", "聘任", "离职", "人事", "appointment", "resignation"],
    }
    priority_order = ["approval", "clinical", "financing", "merger", "cooperation", "product_launch", "tech_progress", "corporate", "policy", "conference", "recruitment"]
    lowered = text.lower()
    for event_type in priority_order:
        keywords = event_keywords.get(event_type, [])
        if any(keyword.lower() in lowered for keyword in keywords):
            payload = {"event_type": event_type, "event_label": EVENT_TYPE_MAP.get(event_type, event_type)}
            amount = AMOUNT_RE.search(text)
            round_match = ROUND_RE.search(text)
            if amount:
                payload["amount"] = amount.group(1).strip()
            if round_match:
                payload["round"] = round_match.group(1).strip()
            score = 82 if event_type in {"approval", "financing", "clinical"} else 72
            rows.append(_candidate("event", "event", "event", EVENT_TYPE_MAP.get(event_type, event_type), EVENT_TYPE_MAP.get(event_type, event_type), f"event_{event_type}", score, source, payload=payload))
            break
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
    if value in {"有限公司", "生物医药公司", "管理团队"} or len(value) > 36:
        return True
    lowered = value.lower()
    sentence_markers = (
        "另一方面", "助力", "通达", "致力", "推动", "开展", "通过",
        "相关话题", "可以", "我们", "our ", "we ", "for ",
    )
    if any(marker in lowered for marker in sentence_markers):
        return True
    if len(value) > 20 and lowered.endswith(("bio", "pharma")):
        return True
    return False

def _sentence_with_any(text: str, keywords: list[str]) -> str:
    for part in re.split(r"[。；;\n]", text):
        if any(keyword in part for keyword in keywords):
            return part.strip()[:500]
    return text[:500]

def _dedupe(rows: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    result = []
    for row in rows:
        key = (row["candidate_type"], row.get("field_name") or "", row.get("subject_label") or row.get("normalized_value") or "")
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result

def apply_global_limits(all_candidates: list[dict]) -> list[dict]:
    by_type: dict[str, list[dict]] = {}
    for c in all_candidates:
        ctype = c["candidate_type"]
        by_type.setdefault(ctype, []).append(c)
    result = []
    for ctype, items in by_type.items():
        limit = MAX_CANDIDATES_PER_TYPE.get(ctype, 5)
        sorted_items = sorted(items, key=lambda x: int(x.get("confidence_score") or 0), reverse=True)
        result.extend(sorted_items[:limit])
    subject_labels = {}
    for c in result:
        if c["candidate_type"] in {"organization", "person", "project"}:
            label = c["subject_label"].lower()
            if label not in subject_labels:
                subject_labels[label] = c
            else:
                existing = subject_labels[label]
                if int(c.get("confidence_score") or 0) > int(existing.get("confidence_score") or 0):
                    subject_labels[label] = c
    deduplicated = []
    for c in result:
        if c["candidate_type"] in {"organization", "person", "project"}:
            label = c["subject_label"].lower()
            if c is subject_labels.get(label):
                deduplicated.append(c)
        else:
            deduplicated.append(c)
    return deduplicated