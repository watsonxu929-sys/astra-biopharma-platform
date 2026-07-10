from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.v04c_review import db_connection, default_db_path
from app.v04c1_ingestion import ensure_v04c1_schema

try:
    from app.v04d_structuring import (
        create_task_item,
        ensure_v04d_schema,
        get_or_create_task,
    )
except ImportError as exc:  # pragma: no cover - installation guard
    raise RuntimeError(
        "v0.4D-B requires v0.4D-A. Missing app/v04d_structuring.py. "
        "Install and verify v0.4D-A before loading this router."
    ) from exc

router = APIRouter(prefix="/review/prestructure", tags=["v0.4D-B 智能预结构化"])
MODULE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = MODULE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

CandidateType = Literal["field", "relation", "event"]
CandidateStatus = Literal["suggested", "accepted", "rejected", "failed"]

RUN_STATUS_LABELS = {
    "processing": "处理中",
    "completed": "已生成草稿",
    "partial": "部分成功",
    "failed": "提取失败",
}
CANDIDATE_STATUS_LABELS = {
    "suggested": "待确认",
    "accepted": "已接受",
    "rejected": "已删除",
    "failed": "接受失败",
}
CONFIDENCE_LABELS = {"high": "高", "medium": "中", "low": "低"}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v04db_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v04db_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key TEXT NOT NULL UNIQUE,
    rule_name TEXT NOT NULL,
    category TEXT NOT NULL,
    pattern TEXT,
    keywords_json TEXT,
    output_field TEXT,
    default_fact_level TEXT NOT NULL DEFAULT 'unknown',
    base_confidence REAL NOT NULL DEFAULT 0.60,
    priority INTEGER NOT NULL DEFAULT 100,
    enabled INTEGER NOT NULL DEFAULT 1,
    builtin INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (default_fact_level IN ('fact','inference','unknown')),
    CHECK (enabled IN (0,1)),
    CHECK (builtin IN (0,1))
);

CREATE INDEX IF NOT EXISTS ix_v04db_rules_enabled
ON v04db_rules(enabled, priority, id);

CREATE TABLE IF NOT EXISTS v04db_extraction_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_no TEXT NOT NULL UNIQUE,
    source_record_id INTEGER NOT NULL,
    task_id INTEGER,
    status TEXT NOT NULL DEFAULT 'processing',
    extractor_version TEXT NOT NULL DEFAULT 'offline-rules-1',
    candidate_count INTEGER NOT NULL DEFAULT 0,
    high_count INTEGER NOT NULL DEFAULT 0,
    medium_count INTEGER NOT NULL DEFAULT 0,
    low_count INTEGER NOT NULL DEFAULT 0,
    accepted_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_by TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY(source_record_id) REFERENCES v04c1_source_records(id) ON DELETE CASCADE,
    FOREIGN KEY(task_id) REFERENCES v04d_structuring_tasks(id) ON DELETE SET NULL,
    CHECK (status IN ('processing','completed','partial','failed'))
);

CREATE INDEX IF NOT EXISTS ix_v04db_runs_source
ON v04db_extraction_runs(source_record_id, created_at DESC);

CREATE TABLE IF NOT EXISTS v04db_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_no TEXT NOT NULL UNIQUE,
    run_id INTEGER NOT NULL,
    candidate_type TEXT NOT NULL,
    rule_key TEXT,
    subject_type TEXT,
    subject_id TEXT,
    subject_label TEXT,
    field_name TEXT,
    candidate_value TEXT,
    left_type TEXT,
    left_id TEXT,
    left_label TEXT,
    relation_type TEXT,
    right_type TEXT,
    right_id TEXT,
    right_label TEXT,
    event_name TEXT,
    event_date TEXT,
    event_type TEXT,
    related_entity TEXT,
    event_summary TEXT,
    fact_level TEXT NOT NULL DEFAULT 'unknown',
    confidence REAL NOT NULL DEFAULT 0.50,
    confidence_level TEXT NOT NULL DEFAULT 'medium',
    confidence_reason TEXT,
    evidence_excerpt TEXT NOT NULL,
    evidence_start INTEGER,
    evidence_end INTEGER,
    source_url TEXT,
    match_status TEXT,
    match_suggestions_json TEXT,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'suggested',
    accepted_item_id INTEGER,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES v04db_extraction_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(accepted_item_id) REFERENCES v04d_structure_items(id) ON DELETE SET NULL,
    CHECK (candidate_type IN ('field','relation','event')),
    CHECK (fact_level IN ('fact','inference','unknown')),
    CHECK (confidence_level IN ('high','medium','low')),
    CHECK (status IN ('suggested','accepted','rejected','failed'))
);

CREATE INDEX IF NOT EXISTS ix_v04db_candidates_run
ON v04db_candidates(run_id, status, confidence DESC, id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04db_candidate_dedupe
ON v04db_candidates(run_id, candidate_type, COALESCE(field_name,''),
                     COALESCE(candidate_value,''), COALESCE(relation_type,''),
                     COALESCE(event_name,''), evidence_start, evidence_end);
"""

DEFAULT_RULES = [
    {
        "rule_key": "financing_amount",
        "rule_name": "融资金额",
        "category": "field_regex",
        "pattern": r"(?:融资|募资|投资|交易金额|总额)[^。；，,]{0,18}?((?:人民币|美元|港元)?\s*\d+(?:\.\d+)?\s*(?:亿元|万元|亿|万|亿美元|万美元))",
        "keywords": ["融资", "募资", "投资", "金额"],
        "output_field": "融资金额",
        "fact_level": "fact",
        "confidence": 0.88,
        "priority": 10,
        "description": "提取融资或投资语境中的金额。",
    },
    {
        "rule_key": "financing_round",
        "rule_name": "融资轮次",
        "category": "field_regex",
        "pattern": r"(?:完成|获得|宣布|启动)?\s*((?:Pre-)?[A-Ha-h]\+?轮|天使轮|种子轮|战略融资|股权融资|债权融资|IPO|上市融资)",
        "keywords": ["融资", "轮"],
        "output_field": "融资轮次",
        "fact_level": "fact",
        "confidence": 0.90,
        "priority": 20,
        "description": "提取融资轮次。",
    },
    {
        "rule_key": "clinical_stage",
        "rule_name": "临床阶段",
        "category": "field_regex",
        "pattern": r"((?:临床前|IND(?:申报|获批)?|I期|Ⅰ期|II期|Ⅱ期|III期|Ⅲ期|I/II期|II/III期|注册性临床|NDA(?:申报|获批)?|BLA(?:申报|获批)?))",
        "keywords": ["临床", "IND", "NDA", "BLA"],
        "output_field": "临床阶段",
        "fact_level": "fact",
        "confidence": 0.84,
        "priority": 30,
        "description": "提取研发或注册阶段。",
    },
    {
        "rule_key": "employee_count",
        "rule_name": "员工人数",
        "category": "field_regex",
        "pattern": r"(?:员工|团队|人员|研发人员)[^。；，,]{0,10}?((?:约|超过|近)?\s*\d+\s*(?:人|名))",
        "keywords": ["员工", "团队", "人员"],
        "output_field": "员工人数",
        "fact_level": "fact",
        "confidence": 0.76,
        "priority": 40,
        "description": "提取明确陈述的员工或团队规模。",
    },
    {
        "rule_key": "valuation",
        "rule_name": "估值",
        "category": "field_regex",
        "pattern": r"(?:估值|投后估值|市值)[^。；，,]{0,12}?((?:人民币|美元|港元)?\s*\d+(?:\.\d+)?\s*(?:亿元|万元|亿|万|亿美元|万美元))",
        "keywords": ["估值", "市值"],
        "output_field": "估值",
        "fact_level": "fact",
        "confidence": 0.82,
        "priority": 50,
        "description": "提取估值或市值。",
    },
    {
        "rule_key": "founded_year",
        "rule_name": "成立时间",
        "category": "field_regex",
        "pattern": r"(?:成立于|创立于|始建于)\s*(\d{4}年(?:\d{1,2}月(?:\d{1,2}日)?)?)",
        "keywords": ["成立", "创立", "始建"],
        "output_field": "成立时间",
        "fact_level": "fact",
        "confidence": 0.91,
        "priority": 60,
        "description": "提取明确成立时间。",
    },
]

ORG_SUFFIX_RE = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9·（）()\-]{2,30}?(?:生物|医药|制药|医疗|科技|集团|公司|资本|基金|研究院|实验室|中心))"
)
PERSON_TITLE_RE = re.compile(
    r"([\u4e00-\u9fa5]{2,4})(?:先生|女士)?(?:为|是|担任|出任)?[^。；，,]{0,20}?(创始人|联合创始人|董事长|总经理|首席执行官|CEO|首席科学官|CSO|首席医学官|CMO)"
)
DRUG_CODE_RE = re.compile(r"\b([A-Z]{1,6}[- ]?\d{2,5}[A-Z]?)\b")
DATE_RE = re.compile(r"(?<!\d)(20\d{2})[年\-/\.](\d{1,2})[月\-/\.]?(\d{1,2})?日?")
SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?", re.MULTILINE)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        loaded = json.loads(str(value))
        return loaded if isinstance(loaded, dict) else {"value": loaded}
    except (TypeError, json.JSONDecodeError):
        return {"raw": str(value)}


def _text(value: Any, limit: int | None = None) -> str:
    result = "" if value is None else str(value).strip()
    return result[:limit] if limit else result


def _next_number(conn: sqlite3.Connection, prefix: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04db_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
            seq_value = CASE WHEN v04db_sequence_counters.seq_date=excluded.seq_date
                             THEN v04db_sequence_counters.seq_value+1 ELSE 1 END,
            seq_date=excluded.seq_date,
            updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, today, utc_now()),
    ).fetchone()
    return f"{prefix}-{today}-{int(row['seq_value']):04d}"


def ensure_v04db_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    path = ensure_v04d_schema(db_path, allow_migration=allow_migration)
    if not allow_migration:
        return path
    with db_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
        now = utc_now()
        for rule in DEFAULT_RULES:
            conn.execute(
                """
                INSERT INTO v04db_rules(
                    rule_key,rule_name,category,pattern,keywords_json,output_field,
                    default_fact_level,base_confidence,priority,enabled,builtin,
                    description,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,1,1,?,?,?)
                ON CONFLICT(rule_key) DO NOTHING
                """,
                (
                    rule["rule_key"], rule["rule_name"], rule["category"],
                    rule["pattern"], _json(rule["keywords"]), rule["output_field"],
                    rule["fact_level"], rule["confidence"], rule["priority"],
                    rule["description"], now, now,
                ),
            )
    return path


def _source_text(source: sqlite3.Row | dict[str, Any]) -> str:
    payload = _load_json(source["payload_json"])
    keys = ("content", "excerpt", "raw_text", "body", "summary", "description", "text")
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    legacy = payload.get("legacy_row")
    if isinstance(legacy, dict):
        for key in keys:
            value = legacy.get(key)
            if value not in (None, ""):
                return str(value)
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group(0).strip()) for m in SENTENCE_RE.finditer(text) if m.group(0).strip()]


def _sentence_for_span(spans: list[tuple[int, int, str]], start: int, end: int) -> tuple[int, int, str]:
    for s, e, sentence in spans:
        if s <= start < e or s < end <= e:
            return s, e, sentence
    left = max(0, start - 40)
    right = min(max(end + 40, start + 1), spans[-1][1] if spans else end + 40)
    return left, right, ""


def _confidence_level(score: float) -> str:
    if score >= 0.82:
        return "high"
    if score >= 0.62:
        return "medium"
    return "low"


def _normalize_stage(value: str) -> str:
    value = value.replace("Ⅰ", "I").replace("Ⅱ", "II").replace("Ⅲ", "III")
    return re.sub(r"\s+", "", value)


def _normalize_date(value: str) -> str:
    m = DATE_RE.search(value)
    if not m:
        return value.strip()
    year, month, day = m.groups()
    return f"{year}-{int(month):02d}" + (f"-{int(day):02d}" if day else "")


def _candidate_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        candidate.get("candidate_type"), candidate.get("field_name"),
        candidate.get("candidate_value"), candidate.get("relation_type"),
        candidate.get("left_label"), candidate.get("right_label"),
        candidate.get("event_name"), candidate.get("evidence_start"),
        candidate.get("evidence_end"),
    )


def _find_orgs(sentence: str) -> list[str]:
    found: list[str] = []
    for match in ORG_SUFFIX_RE.finditer(sentence):
        name = match.group(1).strip("，。；、:：()（）")
        # 清除句首关系词带入的前缀，例如“张三为华辰生物”。
        parts = re.split(r"(?:由|与|和|为|是)", name)
        if len(parts) > 1 and 2 <= len(parts[-1]) <= 40:
            name = parts[-1]
        if 2 <= len(name) <= 40 and name not in found:
            found.append(name)
    return found


def _subject_guess(sentence: str, source_title: str | None = None) -> tuple[str | None, str | None]:
    orgs = _find_orgs(sentence)
    if orgs:
        return "organization", orgs[0]
    if source_title:
        title_orgs = _find_orgs(source_title)
        if title_orgs:
            return "organization", title_orgs[0]
    codes = DRUG_CODE_RE.findall(sentence)
    if codes:
        return "project", codes[0]
    return None, None


def _entity_matches(conn: sqlite3.Connection, subject_type: str | None, label: str | None) -> tuple[str, list[dict[str, Any]]]:
    if not subject_type or not label:
        return "unmatched", []
    mapping = {
        "organization": ("organizations", "external_id", "standard_name"),
        "person": ("people", "external_id", "name"),
        "project": ("projects", "external_id", "name"),
        "event": ("events", "external_id", "name"),
        "resource": ("resources", "external_id", "description"),
    }.get(subject_type)
    if not mapping:
        return "unmatched", []
    table, id_col, name_col = mapping
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        return "unmatched", []
    rows = conn.execute(
        f'''SELECT "{id_col}" AS subject_id, "{name_col}" AS subject_label
            FROM "{table}"
            WHERE LOWER(TRIM(COALESCE(CAST("{name_col}" AS TEXT),''))) = LOWER(TRIM(?))
               OR COALESCE(CAST("{name_col}" AS TEXT),'') LIKE ?
            ORDER BY CASE WHEN LOWER(TRIM(COALESCE(CAST("{name_col}" AS TEXT),'')))=LOWER(TRIM(?)) THEN 0 ELSE 1 END
            LIMIT 5''',
        (label, f"%{label}%", label),
    ).fetchall()
    suggestions = [dict(row) for row in rows]
    if not suggestions:
        return "new_subject", []
    exact = [row for row in suggestions if _text(row["subject_label"]).lower() == label.lower()]
    return ("exact" if len(exact) == 1 else "suggested"), suggestions


@dataclass
class ExtractContext:
    text: str
    title: str
    source_url: str | None
    spans: list[tuple[int, int, str]]


def _regex_field_candidates(ctx: ExtractContext, rules: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for rule in rules:
        pattern = rule["pattern"]
        if not pattern:
            continue
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            continue
        for match in regex.finditer(ctx.text):
            value = (match.group(1) if match.lastindex else match.group(0)).strip()
            if rule["rule_key"] == "clinical_stage":
                value = _normalize_stage(value)
            elif rule["rule_key"] == "founded_year":
                value = _normalize_date(value)
            s, e, sentence = _sentence_for_span(ctx.spans, match.start(), match.end())
            evidence = sentence or ctx.text[s:e]
            subject_type, subject_label = _subject_guess(evidence, ctx.title)
            confidence = float(rule["base_confidence"])
            reasons = [f"命中规则：{rule['rule_name']}", "候选值位于明确语义句中"]
            if subject_label:
                confidence = min(0.98, confidence + 0.04)
                reasons.append("同句识别到主体")
            output.append({
                "candidate_type": "field",
                "rule_key": rule["rule_key"],
                "subject_type": subject_type,
                "subject_label": subject_label,
                "field_name": rule["output_field"],
                "candidate_value": value,
                "fact_level": rule["default_fact_level"],
                "confidence": confidence,
                "confidence_reason": "；".join(reasons),
                "evidence_excerpt": evidence,
                "evidence_start": s,
                "evidence_end": e,
                "source_url": ctx.source_url,
            })
    return output


def _relation_candidates(ctx: ExtractContext) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for s, e, sentence in ctx.spans:
        orgs = _find_orgs(sentence)
        for match in PERSON_TITLE_RE.finditer(sentence):
            person, title = match.groups()
            right = orgs[0] if orgs else None
            if not right:
                continue
            output.append({
                "candidate_type": "relation",
                "rule_key": "person_title_relation",
                "left_type": "person",
                "left_label": person,
                "relation_type": title,
                "right_type": "organization",
                "right_label": right,
                "fact_level": "inference",
                "confidence": 0.78,
                "confidence_reason": "同句出现人物、任职称谓和机构；关系仍需人工确认",
                "evidence_excerpt": sentence,
                "evidence_start": s,
                "evidence_end": e,
                "source_url": ctx.source_url,
            })

        if len(orgs) >= 2:
            relation_patterns = [
                (r"(.+?)(?:领投|投资|参投)(.+)", "投资"),
                (r"(.+?)(?:与|和)(.+?)(?:达成合作|签署合作|战略合作)", "合作"),
                (r"(.+?)(?:收购|并购)(.+)", "收购"),
                (r"(.+?)(?:授权给|授予)(.+)", "授权"),
            ]
            for pattern, relation_type in relation_patterns:
                if re.search(pattern, sentence):
                    output.append({
                        "candidate_type": "relation",
                        "rule_key": f"org_relation_{relation_type}",
                        "left_type": "organization",
                        "left_label": orgs[0],
                        "relation_type": relation_type,
                        "right_type": "organization",
                        "right_label": orgs[1],
                        "fact_level": "inference",
                        "confidence": 0.68,
                        "confidence_reason": f"同句识别到两个机构和“{relation_type}”触发词；主体方向需人工核对",
                        "evidence_excerpt": sentence,
                        "evidence_start": s,
                        "evidence_end": e,
                        "source_url": ctx.source_url,
                    })
                    break
    return output


def _event_candidates(ctx: ExtractContext) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    event_map = {
        "融资": ["融资", "募资", "领投", "参投"],
        "合作": ["合作", "签署", "联合开发"],
        "获批": ["获批", "批准", "IND", "NDA", "BLA"],
        "临床进展": ["进入I期", "进入II期", "进入III期", "启动临床", "完成入组"],
        "并购": ["收购", "并购"],
        "授权": ["授权", "license", "licensing"],
        "处罚": ["处罚", "警告信", "罚款", "立案"],
        "任职": ["任命", "出任", "担任"],
    }
    for s, e, sentence in ctx.spans:
        event_type = next((kind for kind, words in event_map.items() if any(word.lower() in sentence.lower() for word in words)), None)
        if not event_type:
            continue
        subject_type, subject_label = _subject_guess(sentence, ctx.title)
        date_match = DATE_RE.search(sentence)
        event_date = _normalize_date(date_match.group(0)) if date_match else None
        confidence = 0.72 + (0.08 if subject_label else 0) + (0.05 if event_date else 0)
        event_name = f"{subject_label or '相关主体'}{event_type}事件"
        output.append({
            "candidate_type": "event",
            "rule_key": f"event_{event_type}",
            "event_name": event_name,
            "event_date": event_date,
            "event_type": event_type,
            "related_entity": subject_label,
            "event_summary": sentence,
            "fact_level": "fact" if event_type in {"融资", "合作", "获批", "并购", "授权", "处罚", "任职"} else "unknown",
            "confidence": min(0.95, confidence),
            "confidence_reason": f"命中事件词“{event_type}”" + ("；同句识别到主体" if subject_label else "") + ("；同句识别到日期" if event_date else ""),
            "evidence_excerpt": sentence,
            "evidence_start": s,
            "evidence_end": e,
            "source_url": ctx.source_url,
        })
    return output


def _drug_candidates(ctx: ExtractContext) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in DRUG_CODE_RE.finditer(ctx.text):
        code = match.group(1).replace(" ", "-")
        if code in seen:
            continue
        seen.add(code)
        s, e, sentence = _sentence_for_span(ctx.spans, match.start(), match.end())
        output.append({
            "candidate_type": "field",
            "rule_key": "drug_project_code",
            "subject_type": "project",
            "subject_label": code,
            "field_name": "项目代号",
            "candidate_value": code,
            "fact_level": "fact",
            "confidence": 0.74,
            "confidence_reason": "识别到符合药物或项目代号格式的英文数字组合",
            "evidence_excerpt": sentence or ctx.text[s:e],
            "evidence_start": s,
            "evidence_end": e,
            "source_url": ctx.source_url,
        })
    return output


def _prepare_candidate_matches(conn: sqlite3.Connection, candidate: dict[str, Any]) -> dict[str, Any]:
    pairs: list[tuple[str, str, str]] = []
    if candidate["candidate_type"] == "field":
        pairs.append(("subject", candidate.get("subject_type") or "", candidate.get("subject_label") or ""))
    elif candidate["candidate_type"] == "relation":
        pairs.extend([
            ("left", candidate.get("left_type") or "", candidate.get("left_label") or ""),
            ("right", candidate.get("right_type") or "", candidate.get("right_label") or ""),
        ])
    elif candidate["candidate_type"] == "event" and candidate.get("related_entity"):
        pairs.append(("related", "organization", candidate.get("related_entity") or ""))

    suggestions: dict[str, Any] = {}
    statuses: list[str] = []
    for key, subject_type, label in pairs:
        status, items = _entity_matches(conn, subject_type, label)
        statuses.append(status)
        suggestions[key] = items
        if status == "exact" and items:
            if key == "subject":
                candidate["subject_id"] = items[0]["subject_id"]
            elif key == "left":
                candidate["left_id"] = items[0]["subject_id"]
            elif key == "right":
                candidate["right_id"] = items[0]["subject_id"]
    candidate["match_status"] = "exact" if statuses and all(s == "exact" for s in statuses) else ("suggested" if any(s == "suggested" for s in statuses) else "new_subject")
    candidate["match_suggestions"] = suggestions
    return candidate


def extract_source(
    source_record_id: int,
    *,
    actor: str = "manual",
    force: bool = False,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04db_schema(db_path)
    with db_connection(db_path) as conn:
        source = conn.execute("SELECT * FROM v04c1_source_records WHERE id=?", (source_record_id,)).fetchone()
        if not source:
            raise ValueError("来源记录不存在")
        if not force:
            existing = conn.execute(
                "SELECT * FROM v04db_extraction_runs WHERE source_record_id=? AND status IN ('completed','partial') ORDER BY id DESC LIMIT 1",
                (source_record_id,),
            ).fetchone()
            if existing:
                return {"run": dict(existing), "reused": True}
        task = get_or_create_task(source_record_id, created_by=f"v04db:{actor}", db_path=db_path)
        run_no = _next_number(conn, "EXT")
        now = utc_now()
        cursor = conn.execute(
            """
            INSERT INTO v04db_extraction_runs(
                run_no,source_record_id,task_id,status,created_by,created_at
            ) VALUES (?,?,?,'processing',?,?)
            """,
            (run_no, source_record_id, task["id"], actor or "manual", now),
        )
        run_id = int(cursor.lastrowid)
        rules = conn.execute(
            "SELECT * FROM v04db_rules WHERE enabled=1 ORDER BY priority,id"
        ).fetchall()

    text = _source_text(source)
    if not text.strip():
        with db_connection(db_path) as conn:
            conn.execute(
                "UPDATE v04db_extraction_runs SET status='failed',error_message=?,completed_at=? WHERE id=?",
                ("来源正文为空", utc_now(), run_id),
            )
        raise ValueError("来源正文为空")

    ctx = ExtractContext(
        text=text,
        title=_text(source["title"]),
        source_url=source["source_url"],
        spans=_sentence_spans(text),
    )
    raw_candidates = (
        _regex_field_candidates(ctx, rules)
        + _relation_candidates(ctx)
        + _event_candidates(ctx)
        + _drug_candidates(ctx)
    )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for candidate in raw_candidates:
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)

    counts = {"high": 0, "medium": 0, "low": 0}
    inserted = 0
    with db_connection(db_path) as conn:
        for candidate in deduped:
            candidate = _prepare_candidate_matches(conn, candidate)
            score = max(0.0, min(1.0, float(candidate.get("confidence", 0.5))))
            level = _confidence_level(score)
            counts[level] += 1
            candidate_no = _next_number(conn, "PRC")
            payload = dict(candidate)
            try:
                columns = [
                    "candidate_no", "run_id", "candidate_type", "rule_key",
                    "subject_type", "subject_id", "subject_label", "field_name", "candidate_value",
                    "left_type", "left_id", "left_label", "relation_type", "right_type", "right_id", "right_label",
                    "event_name", "event_date", "event_type", "related_entity", "event_summary",
                    "fact_level", "confidence", "confidence_level", "confidence_reason",
                    "evidence_excerpt", "evidence_start", "evidence_end", "source_url",
                    "match_status", "match_suggestions_json", "payload_json", "status",
                    "created_at", "updated_at",
                ]
                values = [
                    candidate_no, run_id, candidate["candidate_type"], candidate.get("rule_key"),
                    candidate.get("subject_type"), candidate.get("subject_id"), candidate.get("subject_label"), candidate.get("field_name"), candidate.get("candidate_value"),
                    candidate.get("left_type"), candidate.get("left_id"), candidate.get("left_label"), candidate.get("relation_type"), candidate.get("right_type"), candidate.get("right_id"), candidate.get("right_label"),
                    candidate.get("event_name"), candidate.get("event_date"), candidate.get("event_type"), candidate.get("related_entity"), candidate.get("event_summary"),
                    candidate.get("fact_level", "unknown"), score, level, candidate.get("confidence_reason"),
                    candidate["evidence_excerpt"], candidate.get("evidence_start"), candidate.get("evidence_end"), candidate.get("source_url"),
                    candidate.get("match_status"), _json(candidate.get("match_suggestions", {})), _json(payload), "suggested",
                    utc_now(), utc_now(),
                ]
                conn.execute(
                    f"INSERT INTO v04db_candidates({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                    values,
                )
                inserted += 1
            except sqlite3.IntegrityError:
                continue
        status = "completed" if inserted > 0 else "partial"
        conn.execute(
            """
            UPDATE v04db_extraction_runs
            SET status=?,candidate_count=?,high_count=?,medium_count=?,low_count=?,
                error_message=?,completed_at=? WHERE id=?
            """,
            (
                status, inserted, counts["high"], counts["medium"], counts["low"],
                None if inserted else "未识别到可用候选", utc_now(), run_id,
            ),
        )
        run = conn.execute("SELECT * FROM v04db_extraction_runs WHERE id=?", (run_id,)).fetchone()
    return {"run": dict(run), "reused": False}


def batch_extract(
    source_ids: Iterable[int],
    *,
    actor: str = "manual",
    force: bool = False,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for source_id in source_ids:
        try:
            result = extract_source(int(source_id), actor=actor, force=force, db_path=db_path)
            results.append({"source_id": int(source_id), "ok": True, **result})
        except Exception as exc:
            results.append({"source_id": int(source_id), "ok": False, "error": str(exc)})
    return {
        "results": results,
        "success": sum(1 for row in results if row["ok"]),
        "failed": sum(1 for row in results if not row["ok"]),
    }


def _candidate_row(conn: sqlite3.Connection, candidate_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM v04db_candidates WHERE id=?", (candidate_id,)
    ).fetchone()
    if not row:
        raise ValueError("候选不存在")
    return row


def accept_candidate(
    candidate_id: int,
    *,
    actor: str = "manual",
    overrides: dict[str, Any] | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04db_schema(db_path)
    with db_connection(db_path) as conn:
        candidate = _candidate_row(conn, candidate_id)
        if candidate["status"] == "accepted":
            return dict(candidate)
        if candidate["status"] == "rejected":
            raise ValueError("已删除候选不能直接接受，请重新提取")
        run = conn.execute(
            "SELECT * FROM v04db_extraction_runs WHERE id=?", (candidate["run_id"],)
        ).fetchone()
        if not run:
            raise ValueError("提取批次不存在")
    values = dict(candidate)
    if overrides:
        for key, value in overrides.items():
            if value not in (None, ""):
                values[key] = value
    item_kwargs = {
        "item_type": values["candidate_type"],
        "fact_level": values["fact_level"],
        "confidence": values["confidence"],
        "evidence_excerpt": values["evidence_excerpt"],
        "source_url": values["source_url"],
        "subject_type": values.get("subject_type"),
        "subject_id": values.get("subject_id"),
        "subject_label": values.get("subject_label"),
        "field_name": values.get("field_name"),
        "candidate_value": values.get("candidate_value"),
        "left_type": values.get("left_type"),
        "left_id": values.get("left_id"),
        "left_label": values.get("left_label"),
        "relation_type": values.get("relation_type"),
        "right_type": values.get("right_type"),
        "right_id": values.get("right_id"),
        "right_label": values.get("right_label"),
        "event_name": values.get("event_name"),
        "event_date": values.get("event_date"),
        "event_type": values.get("event_type"),
        "related_entity": values.get("related_entity"),
        "event_summary": values.get("event_summary"),
    }
    try:
        item = create_task_item(
            int(run["task_id"]),
            actor=f"v04db:{actor}",
            db_path=db_path,
            **item_kwargs,
        )
    except Exception as exc:
        with db_connection(db_path) as conn:
            conn.execute(
                "UPDATE v04db_candidates SET status='failed',error_message=?,updated_at=? WHERE id=?",
                (str(exc), utc_now(), candidate_id),
            )
        raise
    with db_connection(db_path) as conn:
        conn.execute(
            "UPDATE v04db_candidates SET status='accepted',accepted_item_id=?,error_message=NULL,updated_at=? WHERE id=?",
            (item["id"], utc_now(), candidate_id),
        )
        conn.execute(
            "UPDATE v04db_extraction_runs SET accepted_count=(SELECT COUNT(*) FROM v04db_candidates WHERE run_id=? AND status='accepted') WHERE id=?",
            (run["id"], run["id"]),
        )
        row = _candidate_row(conn, candidate_id)
    return dict(row)


def reject_candidate(candidate_id: int, *, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04db_schema(db_path)
    with db_connection(db_path) as conn:
        row = _candidate_row(conn, candidate_id)
        if row["status"] == "accepted":
            raise ValueError("已接受候选已生成结构化条目，请到结构化工作台处理")
        conn.execute(
            "UPDATE v04db_candidates SET status='rejected',updated_at=? WHERE id=?",
            (utc_now(), candidate_id),
        )
        conn.execute(
            "UPDATE v04db_extraction_runs SET rejected_count=(SELECT COUNT(*) FROM v04db_candidates WHERE run_id=? AND status='rejected') WHERE id=?",
            (row["run_id"], row["run_id"]),
        )
        return dict(_candidate_row(conn, candidate_id))


def accept_high_confidence(run_id: int, *, actor: str = "manual", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04db_schema(db_path)
    with db_connection(db_path) as conn:
        ids = [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM v04db_candidates WHERE run_id=? AND status='suggested' AND confidence_level='high' ORDER BY id",
                (run_id,),
            ).fetchall()
        ]
    accepted: list[int] = []
    failed: list[dict[str, Any]] = []
    for candidate_id in ids:
        try:
            accept_candidate(candidate_id, actor=actor, db_path=db_path)
            accepted.append(candidate_id)
        except Exception as exc:
            failed.append({"candidate_id": candidate_id, "error": str(exc)})
    return {"accepted": accepted, "failed": failed}


def update_rule(
    rule_id: int,
    *,
    pattern: str,
    priority: int,
    base_confidence: float,
    enabled: bool,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04db_schema(db_path)
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"正则表达式无效：{exc}") from exc
    score = max(0.05, min(0.99, float(base_confidence)))
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v04db_rules WHERE id=?", (rule_id,)).fetchone()
        if not row:
            raise ValueError("规则不存在")
        conn.execute(
            "UPDATE v04db_rules SET pattern=?,priority=?,base_confidence=?,enabled=?,updated_at=? WHERE id=?",
            (pattern, int(priority), score, 1 if enabled else 0, utc_now(), rule_id),
        )
        return dict(conn.execute("SELECT * FROM v04db_rules WHERE id=?", (rule_id,)).fetchone())


def dashboard_data(db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04db_schema(db_path)
    with db_connection(db_path) as conn:
        counts = {
            "sources": conn.execute("SELECT COUNT(*) AS c FROM v04c1_source_records WHERE status='needs_structuring'").fetchone()["c"],
            "runs": conn.execute("SELECT COUNT(*) AS c FROM v04db_extraction_runs").fetchone()["c"],
            "suggested": conn.execute("SELECT COUNT(*) AS c FROM v04db_candidates WHERE status='suggested'").fetchone()["c"],
            "accepted": conn.execute("SELECT COUNT(*) AS c FROM v04db_candidates WHERE status='accepted'").fetchone()["c"],
            "high": conn.execute("SELECT COUNT(*) AS c FROM v04db_candidates WHERE status='suggested' AND confidence_level='high'").fetchone()["c"],
        }
        sources = [dict(row) for row in conn.execute(
            """
            SELECT s.*, t.id AS task_id, t.task_no,
                   (SELECT id FROM v04db_extraction_runs r WHERE r.source_record_id=s.id ORDER BY r.id DESC LIMIT 1) AS latest_run_id,
                   (SELECT status FROM v04db_extraction_runs r WHERE r.source_record_id=s.id ORDER BY r.id DESC LIMIT 1) AS latest_run_status
            FROM v04c1_source_records s
            LEFT JOIN v04d_structuring_tasks t ON t.source_record_id=s.id
            WHERE s.status='needs_structuring'
            ORDER BY s.id DESC LIMIT 100
            """
        ).fetchall()]
        runs = [dict(row) for row in conn.execute(
            """
            SELECT r.*, s.record_no, s.title, s.source_name, t.task_no
            FROM v04db_extraction_runs r
            JOIN v04c1_source_records s ON s.id=r.source_record_id
            LEFT JOIN v04d_structuring_tasks t ON t.id=r.task_id
            ORDER BY r.id DESC LIMIT 100
            """
        ).fetchall()]
        rules = [dict(row) for row in conn.execute("SELECT * FROM v04db_rules ORDER BY priority,id").fetchall()]
    return {"counts": counts, "sources": sources, "runs": runs, "rules": rules}


def run_detail(run_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04db_schema(db_path)
    with db_connection(db_path) as conn:
        run = conn.execute(
            """
            SELECT r.*,s.record_no,s.title,s.source_name,s.source_url,s.payload_json,t.task_no
            FROM v04db_extraction_runs r
            JOIN v04c1_source_records s ON s.id=r.source_record_id
            LEFT JOIN v04d_structuring_tasks t ON t.id=r.task_id
            WHERE r.id=?
            """,
            (run_id,),
        ).fetchone()
        if not run:
            raise ValueError("提取批次不存在")
        candidates = [dict(row) for row in conn.execute(
            "SELECT * FROM v04db_candidates WHERE run_id=? ORDER BY status,confidence DESC,id",
            (run_id,),
        ).fetchall()]
    for candidate in candidates:
        candidate["match_suggestions"] = _load_json(candidate.get("match_suggestions_json"))
    source_dict = dict(run)
    source_dict["display_text"] = _source_text(run)
    return {"run": dict(run), "source": source_dict, "candidates": candidates}


def _redirect(message: str, level: str = "ok", run_id: int | None = None) -> RedirectResponse:
    target = f"/review/prestructure/runs/{run_id}" if run_id else "/review/prestructure"
    return RedirectResponse(
        url=f"{target}?message={quote(message)}&level={quote(level)}",
        status_code=303,
    )


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def prestructure_dashboard(request: Request, message: str | None = None, level: str = "ok"):
    return templates.TemplateResponse(
        request=request,
        name="v04db_prestructure.html",
        context={
            "mode": "dashboard",
            **dashboard_data(),
            "message": message,
            "message_level": level,
            "run_status_labels": RUN_STATUS_LABELS,
        },
    )


@router.post("/extract/{source_record_id}")
def ui_extract_source(
    source_record_id: int,
    actor: str = Form("manual"),
    force: bool = Form(False),
):
    try:
        result = extract_source(source_record_id, actor=actor or "manual", force=force)
        run = result["run"]
        message = f"{'复用已有' if result['reused'] else '已生成'}提取批次 {run['run_no']}，候选 {run['candidate_count']} 条"
        return _redirect(message, run_id=int(run["id"]))
    except Exception as exc:
        return _redirect(f"提取失败：{exc}", "error")


@router.post("/batch")
def ui_batch_extract(
    source_ids: list[int] = Form(default=[]),
    actor: str = Form("manual"),
    force: bool = Form(False),
):
    if not source_ids:
        return _redirect("请至少选择一条来源", "error")
    result = batch_extract(source_ids, actor=actor or "manual", force=force)
    return _redirect(f"批量提取完成：成功 {result['success']}，失败 {result['failed']}", "error" if result["failed"] else "ok")


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def prestructure_run(
    run_id: int,
    request: Request,
    message: str | None = None,
    level: str = "ok",
):
    try:
        detail = run_detail(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request=request,
        name="v04db_prestructure.html",
        context={
            "mode": "run",
            **detail,
            "message": message,
            "message_level": level,
            "candidate_status_labels": CANDIDATE_STATUS_LABELS,
            "confidence_labels": CONFIDENCE_LABELS,
        },
    )


@router.post("/candidates/{candidate_id}/accept")
def ui_accept_candidate(
    candidate_id: int,
    actor: str = Form("manual"),
    fact_level: str = Form(""),
    subject_id: str = Form(""),
    subject_label: str = Form(""),
    candidate_value: str = Form(""),
):
    with db_connection() as conn:
        row = _candidate_row(conn, candidate_id)
        run_id = int(row["run_id"])
    try:
        accept_candidate(
            candidate_id,
            actor=actor or "manual",
            overrides={
                "fact_level": fact_level,
                "subject_id": subject_id,
                "subject_label": subject_label,
                "candidate_value": candidate_value,
            },
        )
        return _redirect("候选已接受并写入 v0.4D-A 草稿", run_id=run_id)
    except Exception as exc:
        return _redirect(f"接受失败：{exc}", "error", run_id=run_id)


@router.post("/candidates/{candidate_id}/reject")
def ui_reject_candidate(candidate_id: int):
    with db_connection() as conn:
        row = _candidate_row(conn, candidate_id)
        run_id = int(row["run_id"])
    try:
        reject_candidate(candidate_id)
        return _redirect("候选已删除", run_id=run_id)
    except Exception as exc:
        return _redirect(f"删除失败：{exc}", "error", run_id=run_id)


@router.post("/runs/{run_id}/accept-high")
def ui_accept_high(run_id: int, actor: str = Form("manual")):
    result = accept_high_confidence(run_id, actor=actor or "manual")
    return _redirect(
        f"高置信度候选接受完成：成功 {len(result['accepted'])}，失败 {len(result['failed'])}",
        "error" if result["failed"] else "ok",
        run_id=run_id,
    )


@router.post("/runs/{run_id}/rerun")
def ui_rerun(run_id: int, actor: str = Form("manual")):
    with db_connection() as conn:
        run = conn.execute("SELECT * FROM v04db_extraction_runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            return _redirect("提取批次不存在", "error")
    try:
        result = extract_source(int(run["source_record_id"]), actor=actor or "manual", force=True)
        new_run = result["run"]
        return _redirect(f"重新提取完成：{new_run['candidate_count']} 条候选", run_id=int(new_run["id"]))
    except Exception as exc:
        return _redirect(f"重新提取失败：{exc}", "error", run_id=run_id)


@router.post("/rules/{rule_id}")
def ui_update_rule(
    rule_id: int,
    pattern: str = Form(...),
    priority: int = Form(100),
    base_confidence: float = Form(0.60),
    enabled: bool = Form(False),
):
    try:
        rule = update_rule(
            rule_id,
            pattern=pattern,
            priority=priority,
            base_confidence=base_confidence,
            enabled=enabled,
        )
        return _redirect(f"规则已保存：{rule['rule_name']}")
    except Exception as exc:
        return _redirect(f"规则保存失败：{exc}", "error")


@router.get("/api/runs/{run_id}")
def api_run(run_id: int):
    try:
        return JSONResponse(run_detail(run_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/health")
def v04db_health():
    path = ensure_v04db_schema()
    with db_connection(path) as conn:
        tables = conn.execute(
            "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v04db_%'"
        ).fetchone()["c"]
        rules = conn.execute("SELECT COUNT(*) AS c FROM v04db_rules").fetchone()["c"]
        runs = conn.execute("SELECT COUNT(*) AS c FROM v04db_extraction_runs").fetchone()["c"]
    return {
        "ok": tables >= 4 and rules >= len(DEFAULT_RULES),
        "version": "0.4D-B",
        "database": str(path),
        "v04db_table_count": tables,
        "rules": rules,
        "runs": runs,
        "extractor": "offline-rules-1",
    }
