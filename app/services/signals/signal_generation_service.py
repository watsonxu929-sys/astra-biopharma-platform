from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.signal_service import _next_no
from app.v04c_review import db_connection
from scripts.migrate_v05h import migrate as migrate_v05h


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> None:
    if not allow_migration:
        return
    migrate_v05h(Path(db_path) if db_path else None, backup=False) if db_path else migrate_v05h(backup=False)


def evidence_hash(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p or "") for p in parts).encode("utf-8")).hexdigest()


def generate_signals(*, since: str = "", limit: int = 100, dry_run: bool = False, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    created = skipped = candidate = 0
    preview: list[dict[str, Any]] = []
    with db_connection(db_path) as conn:
        rules = [dict(r) for r in conn.execute("SELECT * FROM v05h_signal_rules WHERE is_enabled=1").fetchall()]
        for rule in rules:
            if rule["source_scope"] == "confirmed_event":
                rows = conn.execute(
                    """
                    SELECT * FROM events
                    WHERE COALESCE(is_active,1)=1 AND (verification_status LIKE '%确认%' OR manually_confirmed=1)
                      AND (?='' OR COALESCE(event_date, created_at)>=?)
                    ORDER BY id DESC LIMIT ?
                    """,
                    (since, since, limit),
                ).fetchall()
                for row in rows:
                    text = f"{row['name'] or ''} {row['event_type'] or ''} {row['fact_summary'] or ''}".lower()
                    if not _rule_hits(rule["signal_type"], text):
                        skipped += 1
                        continue
                    payload = _build_from_event(row, rule)
                    if _exists(conn, payload):
                        skipped += 1
                        continue
                    candidate += 1
                    preview.append(payload)
                    if not dry_run:
                        _insert_signal(conn, payload)
                        created += 1
            elif rule["source_scope"] == "approved_candidate":
                rows = conn.execute(
                    """
                    SELECT * FROM v05g_extraction_candidates
                    WHERE review_status IN ('approved','applied') AND confidence_score>=?
                      AND (?='' OR created_at>=?)
                    ORDER BY id DESC LIMIT ?
                    """,
                    (int(rule["min_confidence"]), since, since, limit),
                ).fetchall()
                for row in rows:
                    if not _candidate_matches_rule(row, rule):
                        skipped += 1
                        continue
                    payload = _build_from_candidate(row, rule)
                    if _exists(conn, payload):
                        skipped += 1
                        continue
                    candidate += 1
                    preview.append(payload)
                    if not dry_run:
                        _insert_signal(conn, payload)
                        created += 1
    return {"created": created, "skipped": skipped, "candidates": candidate, "dry_run": dry_run, "preview": preview[:20]}


def _rule_hits(signal_type: str, text: str) -> bool:
    words = {
        "financing": ["融资", "募资", "投资", "a轮", "b轮", "pre-a", "series", "funding", "ipo"],
        "strategic_cooperation": ["合作", "签约", "授权", "共建", "license", "collaboration"],
        "clinical_progress": ["临床", "申报", "获批", "注册", "上市", "ind", "nda", "入组", "试验"],
        "risk": ["风险", "处罚", "诉讼", "召回", "终止", "失败", "暂停"],
    }.get(signal_type, [])
    return any(w in text for w in words)

def _candidate_matches_rule(row: Any, rule: dict[str, Any]) -> bool:
    if rule["signal_type"] == "resource_need":
        return row["candidate_type"] in {"need", "resource", "opportunity"}
    if rule["signal_type"] == "risk":
        return row["candidate_type"] == "risk" or "risk" in (row["field_name"] or "")
    return False


def _build_from_event(row: Any, rule: dict[str, Any]) -> dict[str, Any]:
    eh = evidence_hash("event", row["id"], rule["signal_type"], row["fact_summary"] or row["name"])
    snapshot_id = None
    try:
        system_use = json.loads(row["system_use"] or "{}") if "system_use" in row.keys() else {}
        snapshot_id = system_use.get("source_snapshot_id")
    except Exception:
        snapshot_id = None
    return {
        "signal_no": "",
        "signal_type": rule["signal_type"],
        "signal_category": rule["signal_category"],
        "signal_level": rule["severity_rule"],
        "severity": rule["severity_rule"],
        "title": f"{rule['name']}: {row['name']}"[:300],
        "summary": (row["fact_summary"] or row["event_type"] or row["name"] or "")[:1000],
        "subject_type": "organization" if row["related_entity"] else None,
        "subject_id": row["related_entity"],
        "occurred_at": row["event_date"] or row["created_at"],
        "source_type": "event",
        "source_id": str(row["id"]),
        "event_id": row["id"],
        "snapshot_id": snapshot_id,
        "evidence_excerpt": (row["fact_summary"] or row["name"] or "")[:1000],
        "confidence": max(60, int(rule["min_confidence"])),
        "rule_no": rule["rule_no"],
        "rule_explanation": f"规则 {rule['rule_no']} 命中已确认事件，等级={rule['severity_rule']}。",
        "missing_data_json": json.dumps([] if row["related_entity"] else ["subject_id"], ensure_ascii=False),
        "conflict_json": "[]",
        "evidence_hash": eh,
    }


def _build_from_candidate(row: Any, rule: dict[str, Any]) -> dict[str, Any]:
    eh = evidence_hash("candidate", row["id"], rule["signal_type"], row["evidence_excerpt"])
    return {
        "signal_no": "",
        "signal_type": rule["signal_type"],
        "signal_category": rule["signal_category"],
        "signal_level": rule["severity_rule"],
        "severity": rule["severity_rule"],
        "title": f"{rule['name']}: {row['subject_label'] or row['normalized_value']}"[:300],
        "summary": (row["normalized_value"] or row["raw_value"] or "")[:1000],
        "subject_type": row["subject_type"],
        "subject_id": row["subject_id"] or row["matched_subject_id"],
        "occurred_at": row["reviewed_at"] or row["created_at"],
        "source_type": "processing_candidate",
        "source_id": str(row["id"]),
        "event_id": None,
        "snapshot_id": row["snapshot_id"],
        "evidence_excerpt": (row["evidence_excerpt"] or row["normalized_value"] or "")[:1000],
        "confidence": int(row["confidence_score"] or rule["min_confidence"]),
        "rule_no": rule["rule_no"],
        "rule_explanation": f"规则 {rule['rule_no']} 命中已审核候选，等级={rule['severity_rule']}。",
        "missing_data_json": json.dumps([] if row["evidence_excerpt"] else ["evidence_excerpt"], ensure_ascii=False),
        "conflict_json": row["warning_json"] or "[]",
        "evidence_hash": eh,
    }


def _exists(conn, payload: dict[str, Any]) -> bool:
    row = conn.execute(
        """
        SELECT id FROM v05e_industry_signals
        WHERE signal_type=? AND source_type=? AND source_id=?
          AND COALESCE(subject_type,'')=COALESCE(?, '')
          AND COALESCE(subject_id,'')=COALESCE(?, '')
        """,
        (payload["signal_type"], payload["source_type"], payload["source_id"], payload.get("subject_type"), payload.get("subject_id")),
    ).fetchone()
    return bool(row)


def _insert_signal(conn, payload: dict[str, Any]) -> int:
    ts = now()
    signal_no = _next_no(conn, "SIG")
    cur = conn.execute(
        """
        INSERT INTO v05e_industry_signals(
            signal_no, signal_type, signal_level, title, summary, subject_type, subject_id,
            occurred_at, discovered_at, source_type, source_id, evidence_excerpt, confidence,
            level_reason, status, is_read, created_at, updated_at, signal_category, severity,
            snapshot_id, event_id, rule_no, rule_explanation, missing_data_json, conflict_json,
            evidence_hash, is_important
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            signal_no,
            payload["signal_type"],
            payload["signal_level"],
            payload["title"],
            payload["summary"],
            payload["subject_type"],
            payload["subject_id"],
            payload["occurred_at"],
            ts,
            payload["source_type"],
            payload["source_id"],
            payload["evidence_excerpt"],
            payload["confidence"],
            payload["rule_explanation"],
            ts,
            ts,
            payload["signal_category"],
            payload["severity"],
            payload["snapshot_id"],
            payload["event_id"],
            payload["rule_no"],
            payload["rule_explanation"],
            payload["missing_data_json"],
            payload["conflict_json"],
            payload["evidence_hash"],
        ),
    )
    conn.execute(
        "INSERT OR IGNORE INTO v05h_signal_evidence(signal_id,source_type,source_id,snapshot_id,event_id,evidence_hash,evidence_excerpt,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (cur.lastrowid, payload["source_type"], payload["source_id"], payload["snapshot_id"], payload["event_id"], payload["evidence_hash"], payload["evidence_excerpt"], ts),
    )
    return int(cur.lastrowid)


