from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from app.settings import resolved_db_path
from app.v04c_review import db_connection


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


class IntelligenceProductService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path

    def create_manual_draft(self, fields: dict, *, actor: str) -> dict:
        ts = now()
        with db_connection(self.db_path) as conn:
            cur = conn.execute("""INSERT INTO v06_intelligence_items(
                title,summary,content,intel_type,companies,industry_directions,tags,source_name,source_url,
                visibility,status,credibility,importance,created_by,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,'manual',?,?,'draft',?,?,?,?,?)""", (
                str(fields.get("title") or "").strip(), fields.get("summary"), fields.get("content"),
                fields.get("intel_type") or "manual", fields.get("companies"), fields.get("industry_directions"),
                fields.get("tags"), fields.get("source_url"), fields.get("visibility") or "public",
                int(fields.get("credibility") or 3), int(fields.get("importance") or 2), fields.get("created_by"), ts, ts))
            product_id = int(cur.lastrowid)
            conn.execute("INSERT INTO p2_intelligence_audit_log(entity_type,entity_id,action,actor,after_json,created_at) VALUES ('intelligence_product',?,'manual_draft_created',?,?,?)",
                         (product_id, actor, json.dumps({"status": "draft"}, ensure_ascii=False), ts))
            return dict(conn.execute("SELECT * FROM v06_intelligence_items WHERE id=?", (product_id,)).fetchone())

    def update_product(self, product_id: int, fields: dict, *, actor: str) -> dict:
        with db_connection(self.db_path) as conn:
            current = conn.execute("SELECT * FROM v06_intelligence_items WHERE id=?", (product_id,)).fetchone()
            if not current:
                raise ValueError("product_not_found")
            requested_status = str(fields.get("status") or current["status"])
            if current["status"] != "published" and requested_status == "published":
                raise ValueError("approved_candidate_publication_required")
            values = {key: fields.get(key, current[key]) for key in (
                "title", "summary", "content", "intel_type", "companies", "industry_directions", "tags",
                "source_url", "visibility", "credibility", "importance")}
            values.update({"status": requested_status, "updated_at": now(), "id": product_id})
            conn.execute("""UPDATE v06_intelligence_items SET title=:title,summary=:summary,content=:content,
                intel_type=:intel_type,companies=:companies,industry_directions=:industry_directions,tags=:tags,
                source_url=:source_url,visibility=:visibility,credibility=:credibility,importance=:importance,
                status=:status,updated_at=:updated_at WHERE id=:id""", values)
            conn.execute("INSERT INTO p2_intelligence_audit_log(entity_type,entity_id,action,actor,after_json,created_at) VALUES ('intelligence_product',?,'updated',?,?,?)",
                         (product_id, actor, json.dumps({"status": requested_status}, ensure_ascii=False), values["updated_at"]))
            return dict(conn.execute("SELECT * FROM v06_intelligence_items WHERE id=?", (product_id,)).fetchone())

    def publish_existing(self, product_id: int, *, actor: str, permissions: set[str]) -> dict:
        if "review_data" not in permissions:
            raise PermissionError("review_data_required")
        with db_connection(self.db_path) as conn:
            product = conn.execute("SELECT * FROM v06_intelligence_items WHERE id=?", (product_id,)).fetchone()
            if not product:
                raise ValueError("product_not_found")
            if product["status"] == "published":
                return dict(product)
            candidate = conn.execute("""SELECT c.id FROM p2_intelligence_product_candidates pc
                JOIN v05g_extraction_candidates c ON c.id=pc.candidate_id
                WHERE pc.product_id=? AND c.pipeline_review_status='approved'
                  AND EXISTS (SELECT 1 FROM p2_fact_candidate_evidence e WHERE e.candidate_id=c.id)""", (product_id,)).fetchone()
        if not candidate:
            raise ValueError("approved_candidate_publication_required")
        return self.publish_candidate(int(candidate["id"]), actor=actor, permissions=permissions)

    def publish_candidate(self, candidate_id: int, *, actor: str, permissions: set[str], product_type: str = "brief", title: str = "", summary: str = "", visibility: str = "organization") -> dict:
        if "review_data" not in permissions:
            raise PermissionError("review_data_required")
        with db_connection(self.db_path) as conn:
            candidate = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone()
            if not candidate:
                raise ValueError("candidate_not_found")
            if candidate["pipeline_review_status"] != "approved":
                raise ValueError("candidate_not_approved")
            evidence = conn.execute("SELECT * FROM p2_fact_candidate_evidence WHERE candidate_id=? ORDER BY id", (candidate_id,)).fetchall()
            if not evidence:
                raise ValueError("candidate_evidence_required")
            existing = conn.execute("SELECT p.* FROM v06_intelligence_items p JOIN p2_intelligence_product_candidates pc ON pc.product_id=p.id WHERE pc.candidate_id=? ORDER BY p.id LIMIT 1", (candidate_id,)).fetchone()
            if existing:
                return dict(existing)
            published_title = title.strip() or candidate["source_title"] or candidate["subject_label"] or f"情报候选 {candidate['candidate_no']}"
            published_summary = summary.strip() or candidate["evidence_excerpt"] or candidate["normalized_value"] or ""
            cur = conn.execute(
                """INSERT INTO v06_intelligence_items(
                   title,summary,content,intel_type,source_name,source_url,source_record_type,
                   source_record_id,evidence_hash,published_at,collected_at,credibility,importance,
                   visibility,status,created_at,updated_at,is_pilot,pilot_batch_id)
                   VALUES (?,?,?,?,? ,?,?,?,?,?,?,?,?,?,'published',?,?,?,?)""",
                (
                    published_title[:400], published_summary[:2000], published_summary, product_type,
                    "v05g_extraction_candidates", candidate["source_url"], "fact_candidate", candidate_id,
                    evidence[0]["evidence_hash"], now(), now(), max(1, min(5, round(int(candidate["confidence_score"] or 50) / 20))),
                    2, visibility, now(), now(), int(candidate["is_pilot"] or 0), candidate["pilot_batch_id"],
                ),
            )
            product_id = int(cur.lastrowid)
            conn.execute("INSERT INTO p2_intelligence_product_candidates(product_id,candidate_id,created_at) VALUES (?,?,?)", (product_id, candidate_id, now()))
            for item in evidence:
                conn.execute(
                    """INSERT OR IGNORE INTO p2_intelligence_product_evidence(
                       product_id,snapshot_id,candidate_id,evidence_excerpt,locator_json,evidence_hash,created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (product_id, item["snapshot_id"], candidate_id, item["evidence_excerpt"], item["locator_json"], item["evidence_hash"], now()),
                )
            conn.execute("INSERT INTO p2_intelligence_audit_log(entity_type,entity_id,action,actor,after_json,created_at) VALUES ('intelligence_product',?,'published',?,?,?)", (product_id, actor, json.dumps({"candidate_id": candidate_id}, ensure_ascii=False), now()))
            return dict(conn.execute("SELECT * FROM v06_intelligence_items WHERE id=?", (product_id,)).fetchone())

    def _read_connection(self) -> sqlite3.Connection:
        path = (Path(self.db_path) if self.db_path else resolved_db_path()).resolve()
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def trace(self, product_id: int) -> dict:
        with closing(self._read_connection()) as conn:
            product = conn.execute("SELECT * FROM v06_intelligence_items WHERE id=?", (product_id,)).fetchone()
            if not product:
                raise ValueError("product_not_found")
            try:
                candidates = [dict(row) for row in conn.execute("SELECT c.* FROM p2_intelligence_product_candidates pc JOIN v05g_extraction_candidates c ON c.id=pc.candidate_id WHERE pc.product_id=?", (product_id,)).fetchall()]
                evidence = [dict(row) for row in conn.execute("SELECT pe.*,s.url,s.captured_at,s.content_hash AS snapshot_hash,s.page_title FROM p2_intelligence_product_evidence pe JOIN v04g_source_snapshots s ON s.id=pe.snapshot_id WHERE pe.product_id=? ORDER BY pe.id", (product_id,)).fetchall()]
            except sqlite3.OperationalError as exc:
                if "no such table" not in str(exc).lower():
                    raise
                candidates, evidence = [], []
            return {"product": dict(product), "candidates": candidates, "evidence": evidence}

    def delete(self, product_id: int, *, actor: str, permissions: set[str]) -> None:
        if "review_data" not in permissions:
            raise PermissionError("review_data_required")
        with db_connection(self.db_path) as conn:
            conn.execute("DELETE FROM v06_intelligence_items WHERE id=?", (product_id,))
