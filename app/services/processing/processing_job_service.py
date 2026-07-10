from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.v04c_review import create_pending_relation, create_review_item, db_connection, default_db_path
from scripts.migrate_v05g import migrate as migrate_v05g

from .confidence_service import confidence_level, quality_gate
from .content_block_service import split_blocks, text_hash
from .document_classifier import classify_page
from .entity_extraction_service import extract_candidates
from .subject_matching_service import SUBJECT_CONFIG, match_subject

APPLY_FIELD_WHITELIST = {
    "organization": {
        "org_type",
        "region",
        "industry_tags",
        "resources",
        "needs",
        "relationship_source",
        "source_url",
        "source_title",
    },
    "person": {
        "public_role",
        "organization_network",
        "ability_tags",
        "value_provided",
        "relationship_source",
        "source_url",
        "source_title",
    },
    "project": {
        "project_type",
        "owner_external_id",
        "focus_tags",
        "typical_needs",
        "target_actions",
        "source_url",
        "source_title",
    },
}


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    if not allow_migration:
        return path
    migrate_v05g(path, backup=False)
    return path


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


def _hash_payload(*parts: Any) -> str:
    normalized = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _next_no(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v05g_sequence_counters(seq_key, seq_date, seq_value, updated_at)
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


def create_processing_job(
    *,
    item_id: int | None = None,
    snapshot_id: int | None = None,
    trigger_type: str = "manual",
    operator: str = "",
    queued_only: bool = True,
    reprocess: bool = False,
    priority: str = "medium",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_schema(db_path)
    ts = now()
    with db_connection(db_path) as conn:
        item = None
        if item_id:
            item = conn.execute("SELECT * FROM v05f_collection_items WHERE id=?", (item_id,)).fetchone()
            if not item:
                raise ValueError("collection_item_not_found")
            if queued_only and item["processing_status"] not in {"queued", "failed", "needs_review"} and not reprocess:
                raise RuntimeError("collection_item_not_queued")
            snapshot_id = int(item["snapshot_id"] or 0) or snapshot_id
        cur = conn.execute(
            """
            INSERT INTO v05g_processing_jobs(
                job_no, collection_item_id, snapshot_id, trigger_type, status, priority,
                queued_only, reprocess, operator_username, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            """,
            (
                _next_no(conn, "PRC"),
                item_id,
                snapshot_id,
                trigger_type[:40],
                priority if priority in {"critical", "high", "medium", "low"} else "medium",
                int(bool(queued_only)),
                int(bool(reprocess)),
                operator or None,
                ts,
                ts,
            ),
        )
        if item_id:
            conn.execute("UPDATE v05f_collection_items SET processing_status='processing', updated_at=? WHERE id=?", (ts, item_id))
        return dict(conn.execute("SELECT * FROM v05g_processing_jobs WHERE id=?", (cur.lastrowid,)).fetchone())


def _load_job_source(conn: sqlite3.Connection, job_id: int) -> tuple[sqlite3.Row, sqlite3.Row | None, sqlite3.Row | None]:
    job = conn.execute("SELECT * FROM v05g_processing_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        raise ValueError("processing_job_not_found")
    item = conn.execute("SELECT * FROM v05f_collection_items WHERE id=?", (job["collection_item_id"],)).fetchone() if job["collection_item_id"] else None
    snapshot_id = job["snapshot_id"] or (item["snapshot_id"] if item else None)
    snapshot = conn.execute("SELECT * FROM v04g_source_snapshots WHERE id=?", (snapshot_id,)).fetchone() if snapshot_id else None
    return job, item, snapshot


def process_job(job_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        job, item, snapshot = _load_job_source(conn, job_id)
        ts = now()
        conn.execute("UPDATE v05g_processing_jobs SET status='running', started_at=?, updated_at=? WHERE id=?", (ts, ts, job_id))
        try:
            if not snapshot:
                raise ValueError("snapshot_not_found")
            text = (snapshot["cleaned_text"] or snapshot["raw_content"] or "").strip()
            title = snapshot["page_title"] or (item["title"] if item else "") or snapshot["snapshot_no"]
            source_url = snapshot["normalized_url"] or snapshot["url"] or (item["normalized_url"] if item else "")
            page = classify_page(title, text, (item["page_structure"] if item else "") or "")
            blocks = split_blocks(text, str(page["page_type"]))
            if not blocks:
                raise ValueError("empty_content")
            block_ids: list[int] = []
            warning_count = 0
            for block in blocks:
                block_warnings = list(block.get("warnings") or [])
                warning_count += len(block_warnings)
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO v05g_processing_blocks(
                        block_no, processing_job_id, collection_item_id, snapshot_id, block_index,
                        block_type, structure_type, text, text_hash, char_start, char_end,
                        evidence_excerpt, confidence_score, warning_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _next_no(conn, "BLK"),
                        job_id,
                        job["collection_item_id"],
                        job["snapshot_id"],
                        int(block["index"]),
                        block["block_type"],
                        page["page_type"],
                        block["text"],
                        block["hash"],
                        int(block["char_start"]),
                        int(block["char_end"]),
                        block["evidence_excerpt"],
                        int(block["confidence_score"]),
                        _json(block_warnings),
                        ts,
                    ),
                )
                block_id = cur.lastrowid or conn.execute(
                    "SELECT id FROM v05g_processing_blocks WHERE processing_job_id=? AND text_hash=? AND block_index=?",
                    (job_id, block["hash"], int(block["index"])),
                ).fetchone()["id"]
                block_ids.append(int(block_id))
                source = {"source_url": source_url, "source_title": title}
                for raw_candidate in extract_candidates(block, str(page["page_type"]), source):
                    raw_candidate["block_id"] = block_id
                    candidate_id = _insert_candidate(conn, job_id, job, raw_candidate)
                    if candidate_id:
                        _insert_matches(conn, job_id, job["collection_item_id"], candidate_id)
            totals = _job_totals(conn, job_id)
            status = "needs_review" if totals["blocked"] or warning_count else "success"
            conn.execute(
                """
                UPDATE v05g_processing_jobs
                SET status=?, structure_type=?, subject_count=?, block_count=?, candidate_count=?,
                    matched_count=?, warning_count=?, finished_at=?, updated_at=?
                WHERE id=?
                """,
                (
                    status,
                    page["page_type"],
                    totals["subjects"],
                    len(block_ids),
                    totals["candidates"],
                    totals["matches"],
                    warning_count + totals["warnings"],
                    now(),
                    now(),
                    job_id,
                ),
            )
            if job["collection_item_id"]:
                conn.execute(
                    "UPDATE v05f_collection_items SET processing_status=?, updated_at=? WHERE id=?",
                    ("needs_review" if status == "needs_review" else "processed", now(), job["collection_item_id"]),
                )
            return {"job_id": job_id, "status": status, **totals, "blocks": len(block_ids), "structure_type": page["page_type"]}
        except Exception as exc:
            conn.execute(
                "UPDATE v05g_processing_jobs SET status='failed', error_type=?, error_message=?, finished_at=?, updated_at=? WHERE id=?",
                (exc.__class__.__name__, str(exc)[:800], now(), now(), job_id),
            )
            if job["collection_item_id"]:
                conn.execute("UPDATE v05f_collection_items SET processing_status='failed', updated_at=? WHERE id=?", (now(), job["collection_item_id"]))
            return {"job_id": job_id, "status": "failed", "error_type": exc.__class__.__name__, "error": str(exc)[:800]}


def _insert_candidate(conn: sqlite3.Connection, job_id: int, job: sqlite3.Row, candidate: dict[str, Any]) -> int | None:
    status, warnings = quality_gate(candidate)
    score = max(0, min(100, int(candidate.get("confidence_score") or 50)))
    content_hash = _hash_payload(
        candidate.get("candidate_type"),
        candidate.get("subject_type"),
        candidate.get("subject_label"),
        candidate.get("field_name"),
        candidate.get("normalized_value"),
        candidate.get("evidence_excerpt"),
    )
    try:
        cur = conn.execute(
            """
            INSERT INTO v05g_extraction_candidates(
                candidate_no, processing_job_id, collection_item_id, snapshot_id, block_id,
                candidate_type, subject_type, subject_label, field_name, raw_value,
                normalized_value, payload_json, evidence_excerpt, source_url, source_title,
                source_position, extraction_rule, fact_level, confidence_score, confidence_level,
                validation_status, review_status, warning_json, content_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _next_no(conn, "CND"),
                job_id,
                job["collection_item_id"],
                job["snapshot_id"],
                candidate.get("block_id"),
                candidate.get("candidate_type"),
                candidate.get("subject_type"),
                candidate.get("subject_label"),
                candidate.get("field_name"),
                candidate.get("raw_value"),
                candidate.get("normalized_value"),
                _json(candidate.get("payload") or {}),
                candidate.get("evidence_excerpt"),
                candidate.get("source_url"),
                candidate.get("source_title"),
                candidate.get("source_position"),
                candidate.get("extraction_rule"),
                candidate.get("fact_level") or "unknown",
                score,
                confidence_level(score),
                status,
                "needs_review" if status == "blocked" else "pending",
                _json(warnings),
                content_hash,
                now(),
                now(),
            ),
        )
        return int(cur.lastrowid)
    except sqlite3.IntegrityError:
        return None


def _insert_matches(conn: sqlite3.Connection, job_id: int, item_id: int | None, candidate_id: int) -> None:
    candidate = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone()
    if not candidate or candidate["subject_type"] not in SUBJECT_CONFIG:
        return
    result = match_subject(conn, candidate["subject_type"], candidate["subject_label"] or candidate["normalized_value"], candidate["subject_id"] or "")
    matches = result["matches"] or [None]
    for match in matches[:5]:
        matched_id = match[SUBJECT_CONFIG[candidate["subject_type"]][1]] if match else None
        matched_label = match[SUBJECT_CONFIG[candidate["subject_type"]][2]] if match else None
        status = result["status"]
        cur = conn.execute(
            """
            INSERT INTO v05g_subject_match_candidates(
                match_no, processing_job_id, extraction_candidate_id, collection_item_id,
                candidate_subject_type, candidate_label, matched_subject_type, matched_subject_id,
                matched_subject_label, match_method, match_score, status, ambiguity_count,
                evidence_excerpt, warning_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _next_no(conn, "MTCH"),
                job_id,
                candidate_id,
                item_id,
                candidate["subject_type"],
                candidate["subject_label"] or candidate["normalized_value"],
                candidate["subject_type"] if matched_id else None,
                matched_id,
                matched_label,
                result["method"],
                int(result["score"]),
                status,
                int(result["ambiguity_count"]),
                candidate["evidence_excerpt"],
                _json(["ambiguous_subject"] if status == "ambiguous" else []),
                now(),
            ),
        )
        if matched_id and status == "confirmed":
            conn.execute(
                """
                UPDATE v05g_extraction_candidates
                SET matched_subject_id=?, matched_subject_label=?, subject_id=?, updated_at=?
                WHERE id=?
                """,
                (matched_id, matched_label, matched_id, now(), candidate_id),
            )


def _job_totals(conn: sqlite3.Connection, job_id: int) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
          COUNT(*) AS candidates,
          SUM(CASE WHEN candidate_type IN ('organization','person','project') THEN 1 ELSE 0 END) AS subjects,
          SUM(CASE WHEN validation_status='blocked' THEN 1 ELSE 0 END) AS blocked,
          SUM(CASE WHEN warning_json IS NOT NULL AND warning_json NOT IN ('[]','{}','') THEN 1 ELSE 0 END) AS warnings
        FROM v05g_extraction_candidates WHERE processing_job_id=?
        """,
        (job_id,),
    ).fetchone()
    matches = conn.execute("SELECT COUNT(*) FROM v05g_subject_match_candidates WHERE processing_job_id=? AND status='confirmed'", (job_id,)).fetchone()[0]
    return {
        "candidates": int(row["candidates"] or 0),
        "subjects": int(row["subjects"] or 0),
        "blocked": int(row["blocked"] or 0),
        "warnings": int(row["warnings"] or 0),
        "matches": int(matches or 0),
    }


def run_worker(
    *,
    once: bool = True,
    job_id: int | None = None,
    item_id: int | None = None,
    queued_only: bool = True,
    limit: int = 20,
    reprocess: bool = False,
    operator: str = "worker",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_schema(db_path)
    processed: list[dict[str, Any]] = []
    if job_id:
        jobs = [{"id": job_id}]
    elif item_id:
        jobs = [
            create_processing_job(
                item_id=item_id,
                trigger_type="command",
                operator=operator,
                queued_only=queued_only,
                reprocess=reprocess,
                db_path=db_path,
            )
        ]
    else:
        jobs = []
        with db_connection(db_path) as conn:
            statuses = ("queued", "failed", "needs_review") if queued_only else ("queued", "failed", "needs_review", "new")
            rows = conn.execute(
                f"""
                SELECT id FROM v05f_collection_items
                WHERE processing_status IN ({','.join('?' for _ in statuses)})
                ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, id
                LIMIT ?
                """,
                (*statuses, max(1, min(int(limit or 20), 200))),
            ).fetchall()
        for row in rows:
            try:
                jobs.append(create_processing_job(item_id=int(row["id"]), trigger_type="worker", operator=operator, queued_only=queued_only, reprocess=reprocess, db_path=db_path))
            except RuntimeError:
                continue
    for job in jobs:
        processed.append(process_job(int(job["id"]), db_path=db_path))
        if once:
            break
    return {"processed": len(processed), "results": processed}


def list_jobs(db_path: str | Path | None = None, page: int = 1, page_size: int = 20, status: str = "") -> tuple[list[dict[str, Any]], int]:
    ensure_schema(db_path)
    clauses = ["1=1"]
    params: list[Any] = []
    if status:
        clauses.append("j.status=?")
        params.append(status)
    where = " AND ".join(clauses)
    offset = (max(1, page) - 1) * page_size
    with db_connection(db_path) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM v05g_processing_jobs j WHERE {where}", params).fetchone()[0])
        rows = [
            dict(r)
            for r in conn.execute(
                f"""
                SELECT j.*, i.item_no, i.title AS item_title, i.processing_status AS item_processing_status
                FROM v05g_processing_jobs j
                LEFT JOIN v05f_collection_items i ON i.id=j.collection_item_id
                WHERE {where}
                ORDER BY j.id DESC LIMIT ? OFFSET ?
                """,
                [*params, page_size, offset],
            ).fetchall()
        ]
    return rows, total


def list_candidates(
    db_path: str | Path | None = None,
    page: int = 1,
    page_size: int = 20,
    review_status: str = "",
    candidate_type: str = "",
    q: str = "",
) -> tuple[list[dict[str, Any]], int]:
    ensure_schema(db_path)
    clauses = ["1=1"]
    params: list[Any] = []
    if review_status:
        clauses.append("review_status=?")
        params.append(review_status)
    if candidate_type:
        clauses.append("candidate_type=?")
        params.append(candidate_type)
    if q:
        clauses.append("(candidate_no LIKE ? OR subject_label LIKE ? OR normalized_value LIKE ? OR evidence_excerpt LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    where = " AND ".join(clauses)
    offset = (max(1, page) - 1) * page_size
    with db_connection(db_path) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM v05g_extraction_candidates WHERE {where}", params).fetchone()[0])
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM v05g_extraction_candidates WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, offset]).fetchall()]
    for row in rows:
        row["warning_list"] = _loads(row.get("warning_json"), [])
        row["payload"] = _loads(row.get("payload_json"), {})
    return rows, total


def list_subject_matches(db_path: str | Path | None = None, page: int = 1, page_size: int = 20, status: str = "") -> tuple[list[dict[str, Any]], int]:
    ensure_schema(db_path)
    where = "status=?" if status else "1=1"
    params = [status] if status else []
    offset = (max(1, page) - 1) * page_size
    with db_connection(db_path) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM v05g_subject_match_candidates WHERE {where}", params).fetchone()[0])
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM v05g_subject_match_candidates WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, offset]).fetchall()]
    return rows, total


def candidate_detail(candidate_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            return None
        matches = [dict(r) for r in conn.execute("SELECT * FROM v05g_subject_match_candidates WHERE extraction_candidate_id=? ORDER BY match_score DESC", (candidate_id,)).fetchall()]
        history = [dict(r) for r in conn.execute("SELECT * FROM v05g_candidate_review_history WHERE candidate_id=? ORDER BY created_at DESC", (candidate_id,)).fetchall()]
        logs = [dict(r) for r in conn.execute("SELECT * FROM v05g_candidate_application_logs WHERE candidate_id=? ORDER BY applied_at DESC", (candidate_id,)).fetchall()]
    data = dict(row)
    data["warning_list"] = _loads(data.get("warning_json"), [])
    data["payload"] = _loads(data.get("payload_json"), {})
    return {"candidate": data, "matches": matches, "history": history, "logs": logs}


def review_candidate(candidate_id: int, *, decision: str, actor: str, note: str = "", final_value: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    if decision not in {"approved", "rejected", "needs_review"}:
        raise ValueError("unsupported_decision")
    ensure_schema(db_path)
    after: dict[str, Any]
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            raise ValueError("candidate_not_found")
        before = dict(row)
        value = final_value.strip() or row["normalized_value"]
        conn.execute(
            """
            UPDATE v05g_extraction_candidates
            SET review_status=?, normalized_value=?, review_note=?, reviewed_by=?, reviewed_at=?, updated_at=?
            WHERE id=?
            """,
            (decision, value, note or None, actor or "manual", now(), now(), candidate_id),
        )
        after = dict(conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone())
        conn.execute(
            """
            INSERT INTO v05g_candidate_review_history(candidate_id, action, actor, note, before_json, after_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (candidate_id, decision, actor or "manual", note or None, _json(before), _json(after), now()),
        )
    if decision == "approved":
        _send_to_existing_review(after, db_path=db_path)
    return after


def _send_to_existing_review(candidate: dict[str, Any], db_path: str | Path | None = None) -> None:
    if candidate["candidate_type"] == "relationship":
        payload = _loads(candidate.get("payload_json"), {})
        create_pending_relation(
            left_type=payload.get("left_type") or candidate.get("subject_type") or "unknown",
            left_id=payload.get("left_id") or candidate.get("subject_id"),
            left_label=payload.get("left_label") or candidate.get("subject_label"),
            relation_type=payload.get("relation_type") or candidate.get("field_name") or "relationship",
            right_type=payload.get("right_type") or "unknown",
            right_id=payload.get("right_id"),
            right_label=payload.get("right_label"),
            confidence=(int(candidate.get("confidence_score") or 0) / 100),
            basis=candidate.get("evidence_excerpt"),
            source_url=candidate.get("source_url"),
            db_path=db_path,
        )
    elif candidate["candidate_type"] in {"field", "event", "resource", "need", "risk", "opportunity"}:
        create_review_item(
            item_type="fact_check" if candidate["candidate_type"] != "relationship" else "pending_relation",
            subject_type=candidate.get("subject_type") or "unknown",
            subject_id=candidate.get("subject_id") or candidate.get("matched_subject_id"),
            subject_label=candidate.get("subject_label") or candidate.get("matched_subject_label"),
            field_name=candidate.get("field_name"),
            current_value=None,
            proposed_value=candidate.get("normalized_value"),
            fact_level=candidate.get("fact_level") or "unknown",
            priority="high" if int(candidate.get("confidence_score") or 0) < 70 else "medium",
            created_by="v05g_processing",
            evidence=[
                {
                    "source_url": candidate.get("source_url"),
                    "source_title": candidate.get("source_title"),
                    "source_value": candidate.get("normalized_value"),
                    "source_excerpt": candidate.get("evidence_excerpt"),
                    "metadata": {"candidate_no": candidate.get("candidate_no")},
                }
            ],
            db_path=db_path,
        )


def apply_candidate(candidate_id: int, *, actor: str, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            raise ValueError("candidate_not_found")
        candidate = dict(row)
        if candidate["review_status"] != "approved":
            return _application_log(conn, candidate, "skipped", actor, "candidate_not_approved")
        if candidate["candidate_type"] != "field":
            return _application_log(conn, candidate, "skipped", actor, "only_field_candidates_can_apply")
        subject_type = candidate.get("subject_type") or ""
        field_name = candidate.get("field_name") or ""
        if field_name not in APPLY_FIELD_WHITELIST.get(subject_type, set()):
            return _application_log(conn, candidate, "skipped", actor, "field_not_whitelisted")
        config = SUBJECT_CONFIG.get(subject_type)
        subject_id = candidate.get("subject_id") or candidate.get("matched_subject_id")
        if not config or not subject_id:
            return _application_log(conn, candidate, "failed", actor, "matched_subject_required")
        table, id_col, _ = config
        target = conn.execute(f"SELECT * FROM {table} WHERE {id_col}=?", (subject_id,)).fetchone()
        if not target:
            return _application_log(conn, candidate, "failed", actor, "target_subject_not_found")
        old_value = target[field_name] if field_name in target.keys() else None
        new_value = candidate.get("normalized_value") or ""
        if not new_value.strip():
            return _application_log(conn, candidate, "skipped", actor, "empty_value")
        if str(old_value or "").strip() == new_value.strip():
            conn.execute("UPDATE v05g_extraction_candidates SET review_status='applied', applied_at=?, updated_at=? WHERE id=?", (now(), now(), candidate_id))
            return _application_log(conn, candidate, "skipped", actor, "same_value", old_value=old_value, new_value=new_value)
        conn.execute(f"UPDATE {table} SET {field_name}=? WHERE {id_col}=?", (new_value, subject_id))
        conn.execute("UPDATE v05g_extraction_candidates SET review_status='applied', applied_at=?, updated_at=? WHERE id=?", (now(), now(), candidate_id))
        return _application_log(conn, candidate, "success", actor, "", old_value=old_value, new_value=new_value, target_table=table, target_id=subject_id, field_name=field_name)


def _application_log(conn: sqlite3.Connection, candidate: dict[str, Any], result: str, actor: str, message: str, *, old_value: Any = None, new_value: Any = None, target_table: str | None = None, target_id: str | None = None, field_name: str | None = None) -> dict[str, Any]:
    app_no = _next_no(conn, "APL")
    if result == "failed":
        conn.execute("UPDATE v05g_extraction_candidates SET review_status='apply_failed', updated_at=? WHERE id=?", (now(), candidate["id"]))
    conn.execute(
        """
        INSERT INTO v05g_candidate_application_logs(
            candidate_id, application_no, target_table, target_external_id, field_name,
            old_value, new_value, result, error_message, actor, applied_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (candidate["id"], app_no, target_table, target_id, field_name, old_value, new_value, result, message or None, actor or "manual", now()),
    )
    row = conn.execute("SELECT * FROM v05g_candidate_application_logs WHERE application_no=?", (app_no,)).fetchone()
    return dict(row)


def dashboard(db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        counts = {
            "queued_items": conn.execute("SELECT COUNT(*) FROM v05f_collection_items WHERE processing_status='queued'").fetchone()[0],
            "jobs_today": conn.execute("SELECT COUNT(*) FROM v05g_processing_jobs WHERE date(created_at)=date('now','localtime')").fetchone()[0],
            "pending_candidates": conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE review_status IN ('pending','needs_review')").fetchone()[0],
            "confirmed_matches": conn.execute("SELECT COUNT(*) FROM v05g_subject_match_candidates WHERE status='confirmed'").fetchone()[0],
            "ambiguous_matches": conn.execute("SELECT COUNT(*) FROM v05g_subject_match_candidates WHERE status='ambiguous'").fetchone()[0],
            "applied_candidates": conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE review_status='applied'").fetchone()[0],
        }
        latest_jobs = [dict(r) for r in conn.execute("SELECT * FROM v05g_processing_jobs ORDER BY id DESC LIMIT 8").fetchall()]
        latest_candidates = [dict(r) for r in conn.execute("SELECT * FROM v05g_extraction_candidates ORDER BY id DESC LIMIT 8").fetchall()]
    return {"counts": counts, "latest_jobs": latest_jobs, "latest_candidates": latest_candidates}


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
