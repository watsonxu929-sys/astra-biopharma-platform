from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.v04c_review import db_connection, default_db_path
from app.web_extractor import fetch_and_extract
from scripts.migrate_v04g import SCHEMA_SQL

SUBJECT_TABLES = {
    "organization": {
        "table": "organizations",
        "id_field": "external_id",
        "name_field": "standard_name",
        "fields": {"standard_name", "org_type", "region", "industry_tags", "resources", "needs", "relationship_source", "source_url", "source_title", "source_text"},
        "url": "/organizations/{id}",
    },
    "person": {
        "table": "people",
        "id_field": "external_id",
        "name_field": "name",
        "fields": {"name", "public_role", "organization_network", "ability_tags", "value_provided", "relationship_source", "source_url", "source_title", "source_text"},
        "url": "/people/{id}",
    },
    "project": {
        "table": "projects",
        "id_field": "external_id",
        "name_field": "name",
        "fields": {"name", "project_type", "focus_tags", "typical_needs", "target_actions", "status", "source_url", "source_title", "source_text"},
        "url": "/projects/{id}",
    },
    "event": {
        "table": "events",
        "id_field": "external_id",
        "name_field": "name",
        "fields": {"name", "event_type", "related_entity", "fact_summary", "system_use", "source_url", "source_title", "source_text"},
        "url": "/events/{id}",
    },
    "resource": {
        "table": "resources",
        "id_field": "external_id",
        "name_field": "category",
        "fields": {"owner_external_id", "category", "description", "region", "applicable_to", "source_url", "source_title", "source_text"},
        "url": "/resources/{id}",
    },
}

SOURCE_TYPES = {
    "official_site",
    "team_page",
    "news",
    "product",
    "project_progress",
    "financing",
    "recruiting",
    "qbay_public",
    "other_web",
    "manual_text",
}


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    if not allow_migration:
        return path
    with db_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
    return path


def text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", "\n", (text or "").strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _next_no(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04g_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
            seq_value = CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
            seq_date = excluded.seq_date,
            updated_at = excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):05d}"


def _subject_row(conn: sqlite3.Connection, subject_type: str, subject_id: str) -> sqlite3.Row | None:
    config = SUBJECT_TABLES.get(subject_type)
    if not config or not subject_id:
        return None
    table = config["table"]
    return conn.execute(
        f"SELECT * FROM {table} WHERE {config['id_field']}=? OR CAST(id AS TEXT)=? LIMIT 1",
        (subject_id, subject_id),
    ).fetchone()


def subject_options(db_path: str | Path | None = None, limit: int = 200) -> dict[str, list[dict[str, Any]]]:
    with db_connection(db_path) as conn:
        data: dict[str, list[dict[str, Any]]] = {}
        for subject_type, config in SUBJECT_TABLES.items():
            table = config["table"]
            name_field = config["name_field"]
            rows = conn.execute(
                f"SELECT id, {config['id_field']} AS external_id, {name_field} AS name FROM {table} WHERE COALESCE(is_active,1)=1 ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            data[subject_type] = [dict(row) for row in rows]
    return data


def create_source(
    name: str,
    source_type: str,
    url: str,
    subject_type: str = "",
    subject_id: str = "",
    check_frequency: str = "manual",
    fetch_mode: str = "web",
    owner: str = "",
    note: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_schema(db_path)
    name = name.strip()
    url = url.strip()
    subject_type = subject_type.strip() or None
    subject_id = subject_id.strip() or None
    source_type = source_type.strip() or "other_web"
    fetch_mode = fetch_mode.strip() or "web"
    if not name:
        raise ValueError("监测源名称不能为空")
    if not url:
        raise ValueError("URL 或手动来源标识不能为空")
    if source_type not in SOURCE_TYPES:
        raise ValueError("监测源类型无效")
    if fetch_mode not in {"web", "manual"}:
        raise ValueError("读取方式无效")
    if subject_type and subject_type not in SUBJECT_TABLES:
        raise ValueError("主体类型无效")
    with db_connection(db_path) as conn:
        if subject_type and subject_id:
            subject = _subject_row(conn, subject_type, subject_id)
            if not subject:
                raise ValueError("关联主体不存在，请先选择唯一主体")
            subject_id = subject[SUBJECT_TABLES[subject_type]["id_field"]]
        existing = conn.execute(
            """
            SELECT * FROM v04g_monitoring_sources
            WHERE url=? AND COALESCE(subject_type,'')=COALESCE(?, '')
              AND COALESCE(subject_id,'')=COALESCE(?, '') AND deactivated_at IS NULL
            """,
            (url, subject_type, subject_id),
        ).fetchone()
        if existing:
            return dict(existing)
        ts = now()
        cur = conn.execute(
            """
            INSERT INTO v04g_monitoring_sources(
                source_no, name, source_type, url, subject_type, subject_id, check_frequency,
                is_enabled, owner, fetch_mode, note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (_next_no(conn, "MON"), name[:200], source_type, url[:2000], subject_type, subject_id, check_frequency[:40], owner[:100] or None, fetch_mode, note[:2000] or None, ts, ts),
        )
        return dict(conn.execute("SELECT * FROM v04g_monitoring_sources WHERE id=?", (cur.lastrowid,)).fetchone())


def _clean_manual_text(text: str) -> str:
    lines = []
    for raw in (text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if len(line) >= 2:
            lines.append(line)
    return "\n".join(lines)[:80_000]


def _diff_summary(old: str, new: str) -> str:
    old_lines = {line.strip() for line in old.splitlines() if len(line.strip()) >= 4}
    new_lines = [line.strip() for line in new.splitlines() if len(line.strip()) >= 4]
    added = [line for line in new_lines if line not in old_lines][:8]
    ratio = 100 if not old_lines else int(len(added) * 100 / max(1, len(old_lines)))
    if not added:
        return "内容哈希变化，但未识别到稳定业务段落新增。"
    return "新增段落：\n" + "\n".join(f"- {line[:220]}" for line in added) + f"\n变化比例约 {ratio}%"


def _is_multi_subject(text: str, title: str = "") -> bool:
    sample = f"{title}\n{text[:6000]}"
    keywords = ["团队", "管理团队", "董事会", "专家委员会", "新闻列表", "产品列表", "全部项目", "成员", "Team", "Leadership"]
    name_like = len(re.findall(r"[\u4e00-\u9fa5]{2,4}\s*(博士|教授|先生|女士|CEO|CFO|CTO|创始人|董事长|总经理)", sample))
    return any(k in sample for k in keywords) and name_like >= 2


def _excerpt(text: str, keyword: str = "") -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if keyword and keyword in text:
        index = max(0, text.find(keyword) - 80)
        return text[index:index + 500]
    return text[:500]


def _proposal_specs(conn: sqlite3.Connection, source: sqlite3.Row, text: str, title: str, snapshot_id: int) -> list[dict[str, str]]:
    subject_type = source["subject_type"]
    subject_id = source["subject_id"]
    if not subject_type or not subject_id:
        return [{
            "proposal_type": "subject_match_required",
            "field_name": "manual_review",
            "proposed_value": title or _excerpt(text),
            "evidence_excerpt": _excerpt(text),
            "confidence_level": "low",
            "conflict_level": "manual_required",
        }]
    if _is_multi_subject(text, title):
        return [{
            "proposal_type": "multi_subject_review",
            "field_name": "manual_review",
            "proposed_value": title or "疑似多主体页面",
            "evidence_excerpt": _excerpt(text),
            "confidence_level": "low",
            "conflict_level": "manual_required",
        }]

    specs: list[dict[str, str]] = []
    lowered = text.lower()
    if subject_type == "organization":
        if any(k in text for k in ["融资", "投资", "合作", "临床", "管线", "落地", "扩张"]):
            specs.append({"proposal_type": "field_update", "field_name": "needs", "proposed_value": _excerpt(text, "融资")[:1000], "confidence_level": "medium"})
        if any(k in lowered for k in ["adc", "cro", "cdmo", "ai", "细胞", "基因", "抗体", "疫苗"]):
            specs.append({"proposal_type": "field_update", "field_name": "industry_tags", "proposed_value": ", ".join(sorted({k.upper() for k in ["adc", "cro", "cdmo", "ai"] if k in lowered})) or "生物医药", "confidence_level": "medium"})
    elif subject_type == "person":
        if any(k in text for k in ["任命", "加入", "担任", "首席", "负责人", "CEO", "CFO", "CTO"]):
            specs.append({"proposal_type": "field_update", "field_name": "public_role", "proposed_value": _excerpt(text)[:800], "confidence_level": "medium"})
            specs.append({"proposal_type": "candidate_relation", "field_name": "relation_candidate", "proposed_value": "人物任职变化候选", "confidence_level": "low"})
    elif subject_type == "project":
        if any(k in text for k in ["临床", "IND", "获批", "完成", "启动", "推进", "里程碑"]):
            specs.append({"proposal_type": "field_update", "field_name": "status", "proposed_value": _excerpt(text)[:500], "confidence_level": "medium"})
    elif subject_type == "resource":
        if any(k in text for k in ["服务", "平台", "可用", "开放", "能力"]):
            specs.append({"proposal_type": "field_update", "field_name": "description", "proposed_value": _excerpt(text)[:1000], "confidence_level": "medium"})
    if any(k in text for k in ["融资", "合作", "获批", "临床", "签约"]):
        specs.append({"proposal_type": "candidate_event", "field_name": "event_candidate", "proposed_value": "候选事件：请人工确认后写入事件库", "confidence_level": "low"})
    if not specs:
        specs.append({"proposal_type": "manual_judgement", "field_name": "manual_review", "proposed_value": title or _excerpt(text)[:500], "confidence_level": "low"})

    row = _subject_row(conn, subject_type, subject_id)
    for spec in specs:
        spec["evidence_excerpt"] = spec.get("evidence_excerpt") or _excerpt(text, str(spec.get("proposed_value", ""))[:20])
        field = spec["field_name"]
        old = row[field] if row and field in row.keys() else ""
        spec["old_value"] = old or ""
        if old and spec.get("proposed_value") and str(old).strip() != str(spec["proposed_value"]).strip() and spec["proposal_type"] == "field_update":
            spec["conflict_level"] = "value_conflict"
        else:
            spec["conflict_level"] = spec.get("conflict_level", "none")
    return specs


def _insert_proposals(conn: sqlite3.Connection, source: sqlite3.Row, run_id: int, snapshot_id: int | None, specs: list[dict[str, str]]) -> int:
    created = 0
    ts = now()
    for spec in specs:
        existing = conn.execute(
            """
            SELECT id FROM v04g_update_proposals
            WHERE monitoring_source_id=? AND COALESCE(subject_type,'')=COALESCE(?, '')
              AND COALESCE(subject_id,'')=COALESCE(?, '') AND proposal_type=?
              AND field_name=? AND COALESCE(proposed_value,'')=COALESCE(?, '')
              AND status IN ('pending','under_review')
            """,
            (source["id"], source["subject_type"], source["subject_id"], spec["proposal_type"], spec["field_name"], spec.get("proposed_value", "")),
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO v04g_update_proposals(
                proposal_no, monitoring_source_id, monitoring_run_id, snapshot_id, subject_type, subject_id,
                proposal_type, field_name, old_value, proposed_value, evidence_excerpt,
                confidence_level, conflict_level, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                _next_no(conn, "PROP"),
                source["id"],
                run_id,
                snapshot_id,
                source["subject_type"],
                source["subject_id"],
                spec["proposal_type"],
                spec["field_name"],
                spec.get("old_value", ""),
                spec.get("proposed_value", ""),
                spec.get("evidence_excerpt", ""),
                spec.get("confidence_level", "medium"),
                spec.get("conflict_level", "none"),
                ts,
                ts,
            ),
        )
        created += 1
    return created


def run_source(source_id: int, manual_text: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        source = conn.execute("SELECT * FROM v04g_monitoring_sources WHERE id=?", (source_id,)).fetchone()
        if not source:
            raise ValueError("监测源不存在")
        ts = now()
        run_no = _next_no(conn, "RUN")
        cur = conn.execute(
            "INSERT INTO v04g_monitoring_runs(run_no, monitoring_source_id, status, started_at, created_at) VALUES (?, ?, 'running', ?, ?)",
            (run_no, source_id, ts, ts),
        )
        run_id = cur.lastrowid
        if not source["is_enabled"]:
            conn.execute(
                "UPDATE v04g_monitoring_runs SET status='skipped', finished_at=?, error_type='disabled', error_message='监测源已停用' WHERE id=?",
                (now(), run_id),
            )
            return {"run_id": run_id, "status": "skipped", "created_proposal_count": 0}
        try:
            if source["fetch_mode"] == "manual" or manual_text.strip():
                text = _clean_manual_text(manual_text)
                if len(text) < 20:
                    raise ValueError("手动文本正文过短")
                title = source["name"]
                url = source["url"]
            else:
                result = fetch_and_extract(source["url"])
                title = result.title
                url = result.url
                text = result.text
            digest = text_hash(text)
            previous = conn.execute(
                "SELECT * FROM v04g_source_snapshots WHERE monitoring_source_id=? ORDER BY id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if previous and previous["content_hash"] == digest:
                conn.execute(
                    """
                    UPDATE v04g_monitoring_runs
                    SET status='unchanged', finished_at=?, content_length=?, content_hash=?, changed=0
                    WHERE id=?
                    """,
                    (now(), len(text), digest, run_id),
                )
                conn.execute(
                    "UPDATE v04g_monitoring_sources SET last_checked_at=?, last_success_at=?, consecutive_failures=0, updated_at=? WHERE id=?",
                    (now(), now(), now(), source_id),
                )
                return {"run_id": run_id, "status": "unchanged", "created_proposal_count": 0}
            snapshot = conn.execute(
                "SELECT * FROM v04g_source_snapshots WHERE monitoring_source_id=? AND content_hash=?",
                (source_id, digest),
            ).fetchone()
            snapshot_id = snapshot["id"] if snapshot else None
            if not snapshot:
                snapshot_no = _next_no(conn, "SNP")
                cur = conn.execute(
                    """
                    INSERT INTO v04g_source_snapshots(
                        snapshot_no, monitoring_source_id, monitoring_run_id, page_title, url, captured_at,
                        raw_content, cleaned_text, content_hash, metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (snapshot_no, source_id, run_id, title[:300], url[:2000], now(), text[:12000], text[:80000], digest, json.dumps({"multi_subject": _is_multi_subject(text, title)}, ensure_ascii=False), now()),
                )
                snapshot_id = cur.lastrowid
            diff = _diff_summary(previous["cleaned_text"] if previous else "", text)
            fresh_source = conn.execute("SELECT * FROM v04g_monitoring_sources WHERE id=?", (source_id,)).fetchone()
            specs = _proposal_specs(conn, fresh_source, text, title, snapshot_id)
            created = _insert_proposals(conn, fresh_source, run_id, snapshot_id, specs)
            status = "partial" if any(s.get("conflict_level") == "manual_required" for s in specs) else "success"
            conn.execute(
                """
                UPDATE v04g_monitoring_runs
                SET status=?, finished_at=?, content_length=?, content_hash=?, changed=1,
                    diff_summary=?, created_snapshot_id=?, created_proposal_count=?
                WHERE id=?
                """,
                (status, now(), len(text), digest, diff, snapshot_id, created, run_id),
            )
            conn.execute(
                """
                UPDATE v04g_monitoring_sources
                SET last_checked_at=?, last_changed_at=?, last_success_at=?, consecutive_failures=0, updated_at=?
                WHERE id=?
                """,
                (now(), now(), now(), now(), source_id),
            )
            return {"run_id": run_id, "status": status, "snapshot_id": snapshot_id, "created_proposal_count": created}
        except Exception as exc:
            message = str(exc)[:800]
            conn.execute(
                """
                UPDATE v04g_monitoring_runs
                SET status='failed', finished_at=?, error_type=?, error_message=?
                WHERE id=?
                """,
                (now(), exc.__class__.__name__, message, run_id),
            )
            conn.execute(
                """
                UPDATE v04g_monitoring_sources
                SET last_checked_at=?, last_error_at=?, consecutive_failures=consecutive_failures+1, updated_at=?
                WHERE id=?
                """,
                (now(), now(), now(), source_id),
            )
            return {"run_id": run_id, "status": "failed", "error": message, "created_proposal_count": 0}


def due_sources(conn: sqlite3.Connection, due_only: bool = False, limit: int = 20) -> list[sqlite3.Row]:
    if not due_only:
        return conn.execute(
            "SELECT * FROM v04g_monitoring_sources WHERE is_enabled=1 AND deactivated_at IS NULL ORDER BY id LIMIT ?",
            (limit,),
        ).fetchall()
    threshold = (datetime.now() - timedelta(days=1)).isoformat()
    return conn.execute(
        """
        SELECT * FROM v04g_monitoring_sources
        WHERE is_enabled=1 AND deactivated_at IS NULL
          AND check_frequency<>'manual'
          AND (last_checked_at IS NULL OR last_checked_at<?)
        ORDER BY COALESCE(last_checked_at,'') ASC, id ASC LIMIT ?
        """,
        (threshold, limit),
    ).fetchall()


def list_data(db_path: str | Path | None = None, page: int = 1, status: str = "") -> dict[str, Any]:
    ensure_schema(db_path)
    offset = (max(1, page) - 1) * 20
    with db_connection(db_path) as conn:
        counts = {
            "enabled_sources": conn.execute("SELECT COUNT(*) AS c FROM v04g_monitoring_sources WHERE is_enabled=1 AND deactivated_at IS NULL").fetchone()["c"],
            "pending_proposals": conn.execute("SELECT COUNT(*) AS c FROM v04g_update_proposals WHERE status IN ('pending','under_review')").fetchone()["c"],
            "failed_sources": conn.execute("SELECT COUNT(*) AS c FROM v04g_monitoring_sources WHERE consecutive_failures>0").fetchone()["c"],
            "changed_runs": conn.execute("SELECT COUNT(*) AS c FROM v04g_monitoring_runs WHERE changed=1").fetchone()["c"],
        }
        sources = [dict(r) for r in conn.execute("SELECT * FROM v04g_monitoring_sources ORDER BY id DESC LIMIT 20 OFFSET ?", (offset,)).fetchall()]
        runs = [dict(r) for r in conn.execute("SELECT r.*, s.name AS source_name FROM v04g_monitoring_runs r JOIN v04g_monitoring_sources s ON s.id=r.monitoring_source_id ORDER BY r.id DESC LIMIT 20 OFFSET ?", (offset,)).fetchall()]
        where = "1=1"
        params: list[Any] = []
        if status:
            where = "p.status=?"
            params.append(status)
        proposals = [dict(r) for r in conn.execute(
            f"SELECT p.*, s.name AS source_name FROM v04g_update_proposals p JOIN v04g_monitoring_sources s ON s.id=p.monitoring_source_id WHERE {where} ORDER BY p.id DESC LIMIT 20 OFFSET ?",
            [*params, offset],
        ).fetchall()]
    return {"counts": counts, "sources": sources, "runs": runs, "proposals": proposals, "page": page, "status": status}


def review_proposal(proposal_id: int, decision: str, reviewer: str = "manual", final_value: str = "", note: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    if decision not in {"approved", "rejected", "ignored", "under_review"}:
        raise ValueError("审核动作无效")
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        proposal = conn.execute("SELECT * FROM v04g_update_proposals WHERE id=?", (proposal_id,)).fetchone()
        if not proposal:
            raise ValueError("更新建议不存在")
        ts = now()
        if decision != "approved":
            conn.execute(
                "UPDATE v04g_update_proposals SET status=?, review_note=?, reviewed_by=?, reviewed_at=?, updated_at=? WHERE id=?",
                (decision, note or None, reviewer or "manual", ts, ts, proposal_id),
            )
            return {"status": decision, "applied": False}
        subject_type = proposal["subject_type"]
        config = SUBJECT_TABLES.get(subject_type or "")
        field_name = proposal["field_name"]
        value = final_value.strip() if final_value.strip() else (proposal["proposed_value"] or "")
        if proposal["proposal_type"] != "field_update" or not config or field_name not in config["fields"]:
            conn.execute(
                "UPDATE v04g_update_proposals SET status='approved', review_note=?, reviewed_by=?, reviewed_at=?, updated_at=? WHERE id=?",
                (note or "候选关系/事件或人工判断建议，未自动写入业务表", reviewer or "manual", ts, ts, proposal_id),
            )
            return {"status": "approved", "applied": False}
        row = _subject_row(conn, subject_type, proposal["subject_id"])
        if not row:
            conn.execute(
                "UPDATE v04g_update_proposals SET status='apply_failed', apply_error=?, reviewed_by=?, reviewed_at=?, updated_at=? WHERE id=?",
                ("主体不存在或无法唯一确认", reviewer or "manual", ts, ts, proposal_id),
            )
            return {"status": "apply_failed", "applied": False}
        existing_log = conn.execute("SELECT id FROM v04g_update_apply_logs WHERE proposal_id=?", (proposal_id,)).fetchone()
        if existing_log:
            return {"status": proposal["status"], "applied": True, "idempotent": True}
        table = config["table"]
        old_value = row[field_name] if field_name in row.keys() else ""
        conn.execute(f"UPDATE {table} SET {field_name}=? WHERE id=?", (value, row["id"]))
        conn.execute(
            """
            INSERT INTO v04g_update_apply_logs(
                proposal_id, subject_type, subject_id, table_name, field_name,
                old_value, new_value, snapshot_id, applied_by, applied_at, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (proposal_id, subject_type, proposal["subject_id"], table, field_name, old_value, value, proposal["snapshot_id"], reviewer or "manual", ts, note or None),
        )
        conn.execute(
            """
            UPDATE v04g_update_proposals
            SET status='applied', review_note=?, reviewed_by=?, reviewed_at=?, applied_at=?, updated_at=?
            WHERE id=?
            """,
            (note or None, reviewer or "manual", ts, ts, ts, proposal_id),
        )
        return {"status": "applied", "applied": True, "old_value": old_value, "new_value": value}
