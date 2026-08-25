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


EVENT_PROFILES = {
    "approval": ("监管审批", 4, "监管结论会直接影响产品上市、注册或市场准入。"),
    "clinical": ("临床进展", 4, "临床阶段变化会影响研发判断、合作节奏和资源需求。"),
    "financing": ("融资事件", 4, "新增资本通常意味着企业进入扩张、研发或合作窗口。"),
    "merger": ("并购交易", 4, "控制权或资产变化可能形成新的合作与整合机会。"),
    "cooperation": ("许可合作", 3, "明确合作信号值得核对双方主体、资源与后续机会。"),
    "product_launch": ("产品发布", 3, "产品进入市场可能带来渠道、服务和产业协同需求。"),
    "tech_progress": ("技术进展", 3, "研发或技术节点变化值得持续关注其产业化进度。"),
    "policy": ("政策发布", 2, "政策变化可能影响准入、合规或区域产业机会。"),
    "corporate": ("企业动态", 2, "企业经营变化可能形成后续主体关注或资源线索。"),
    "conference": ("行业活动", 1, "行业活动可作为人物、企业和合作线索的补充来源。"),
    "recruitment": ("人事变动", 2, "关键人员变化可能影响企业方向与合作窗口。"),
    "expansion": ("企业扩张", 3, "新设研发或运营载体通常会带来招商、空间、服务和合作需求。"),
}


def _event_profile(candidate: sqlite3.Row) -> tuple[str, str, int, str]:
    try:
        payload = json.loads(candidate["payload_json"] or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}
    labels = {value[0]: key for key, value in EVENT_PROFILES.items()}
    reviewed_type = labels.get(str(candidate["normalized_value"] or "").strip())
    event_type = str(reviewed_type or payload.get("event_type") or candidate["field_name"] or "").strip().lower()
    if event_type not in EVENT_PROFILES:
        event_type = labels.get(str(candidate["normalized_value"] or "").strip(), "other")
    label, importance, reason = EVENT_PROFILES.get(
        event_type, ("其他", 1, "规则未识别出明确事件类型，需要人工结合公开证据判断。")
    )
    return event_type, label, importance, reason


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
                "title", "summary", "content", "intel_type", "companies", "people_involved", "industry_directions", "tags",
                "source_url", "visibility", "credibility", "importance")}
            values.update({"status": requested_status, "updated_at": now(), "id": product_id})
            conn.execute("""UPDATE v06_intelligence_items SET title=:title,summary=:summary,content=:content,
                intel_type=:intel_type,companies=:companies,people_involved=:people_involved,industry_directions=:industry_directions,tags=:tags,
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

    @staticmethod
    def _attach_evidence(conn: sqlite3.Connection, product_id: int, candidate_id: int, evidence, *, action: str, actor: str) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO p2_intelligence_product_candidates(product_id,candidate_id,created_at) VALUES (?,?,?)",
            (product_id, candidate_id, now()),
        )
        for item in evidence:
            conn.execute(
                """INSERT OR IGNORE INTO p2_intelligence_product_evidence(
                   product_id,snapshot_id,candidate_id,evidence_excerpt,locator_json,evidence_hash,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (product_id, item["snapshot_id"], candidate_id, item["evidence_excerpt"], item["locator_json"], item["evidence_hash"], now()),
            )
        conn.execute(
            "INSERT INTO p2_intelligence_audit_log(entity_type,entity_id,action,actor,after_json,created_at) VALUES ('intelligence_product',?,?,?,?,?)",
            (
                product_id, action, actor,
                json.dumps({"candidate_id": candidate_id}, ensure_ascii=False),
                now(),
            ),
        )

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
            context = conn.execute(
                """
                SELECT ci.id AS collection_item_id,ci.published_at,s.name AS source_name,
                       s.source_credibility,sn.captured_at
                FROM v05g_extraction_candidates c
                LEFT JOIN v05f_collection_items ci ON ci.id=c.collection_item_id
                LEFT JOIN v04g_monitoring_sources s ON s.id=ci.monitoring_source_id
                LEFT JOIN v04g_source_snapshots sn ON sn.id=c.snapshot_id
                WHERE c.id=?
                """,
                (candidate_id,),
            ).fetchone()
            event_type, event_label, importance, importance_reason = _event_profile(candidate)
            published_title = title.strip() or candidate["source_title"] or candidate["subject_label"] or f"情报候选 {candidate['candidate_no']}"
            published_summary = summary.strip() or candidate["evidence_excerpt"] or candidate["normalized_value"] or ""
            exact = conn.execute(
                """
                SELECT * FROM v06_intelligence_items
                WHERE status='published' AND (
                    evidence_hash=? OR (
                        COALESCE(source_url,'')=COALESCE(?, '')
                        AND lower(trim(title))=lower(trim(?))
                    )
                )
                ORDER BY id LIMIT 1
                """,
                (evidence[0]["evidence_hash"], candidate["source_url"], published_title[:400]),
            ).fetchone()
            if exact:
                self._attach_evidence(conn, int(exact["id"]), candidate_id, evidence, action="exact_duplicate_evidence_linked", actor=actor)
                return dict(conn.execute("SELECT * FROM v06_intelligence_items WHERE id=?", (exact["id"],)).fetchone())
            related = []
            if context and context["collection_item_id"]:
                related = conn.execute(
                    """
                    SELECT candidate_type,subject_label,normalized_value
                    FROM v05g_extraction_candidates
                    WHERE collection_item_id=? AND candidate_type IN ('organization','person')
                      AND COALESCE(NULLIF(pipeline_review_status,''),review_status) IN ('approved','applied')
                    ORDER BY confidence_score DESC,id
                    """,
                    (context["collection_item_id"],),
                ).fetchall()
            companies = "; ".join(dict.fromkeys(
                str(row["subject_label"] or row["normalized_value"] or "").strip()
                for row in related if row["candidate_type"] == "organization"
                and str(row["subject_label"] or row["normalized_value"] or "").strip()
            ))
            people = "; ".join(dict.fromkeys(
                str(row["subject_label"] or row["normalized_value"] or "").strip()
                for row in related if row["candidate_type"] == "person"
                and str(row["subject_label"] or row["normalized_value"] or "").strip()
            ))
            source_credibility = int(context["source_credibility"] or 3) if context else 3
            published_at = (context["published_at"] if context else None) or now()
            collected_at = (context["captured_at"] if context else None) or now()
            source_name = (context["source_name"] if context else None) or "人工审核候选"
            cur = conn.execute(
                """INSERT INTO v06_intelligence_items(
                   title,summary,content,intel_type,companies,people_involved,event_type,
                   source_name,source_url,source_record_type,
                   source_record_id,evidence_hash,published_at,collected_at,credibility,importance,
                   visibility,status,verification_status,analysis_notes,created_at,updated_at,
                   is_pilot,pilot_batch_id)
                   VALUES (
                     :title,:summary,:content,:intel_type,:companies,:people,:event_type,
                     :source_name,:source_url,'fact_candidate',:candidate_id,:evidence_hash,
                     :published_at,:collected_at,:credibility,:importance,:visibility,'published',
                     'verified',:analysis_notes,:created_at,:updated_at,:is_pilot,:pilot_batch_id
                   )""",
                {
                    "title": published_title[:400], "summary": published_summary[:2000],
                    "content": published_summary,
                    "intel_type": event_label if candidate["candidate_type"] == "event" else product_type,
                    "companies": companies or None, "people": people or None, "event_type": event_type,
                    "source_name": source_name, "source_url": candidate["source_url"],
                    "candidate_id": candidate_id, "evidence_hash": evidence[0]["evidence_hash"],
                    "published_at": published_at, "collected_at": collected_at,
                    "credibility": max(1, min(5, source_credibility)), "importance": importance,
                    "visibility": visibility,
                    "analysis_notes": json.dumps({"method": "deterministic_rules", "importance_reason": importance_reason}, ensure_ascii=False),
                    "created_at": now(), "updated_at": now(),
                    "is_pilot": int(candidate["is_pilot"] or 0), "pilot_batch_id": candidate["pilot_batch_id"],
                },
            )
            product_id = int(cur.lastrowid)
            self._attach_evidence(conn, product_id, candidate_id, evidence, action="published", actor=actor)
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
