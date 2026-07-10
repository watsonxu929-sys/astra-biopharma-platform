from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.v04c_review import db_connection


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


class EvidenceService:
    """Owns immutable EvidenceSnapshot creation and structured evidence links."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path

    def get_or_create_snapshot(
        self,
        *,
        source_id: int,
        job_id: int,
        url: str,
        raw_content: str,
        raw_html: str = "",
        page_title: str = "",
        content_type: str = "text/html",
        http_status: int | None = 200,
        published_at: str | None = None,
        metadata: dict[str, Any] | None = None,
        attachment_path: str | None = None,
        attachment_page_count: int | None = None,
        is_pilot: bool = False,
        pilot_batch_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        digest = sha256_text(raw_html or raw_content)
        ts = now()
        with db_connection(self.db_path) as conn:
            existing = conn.execute("SELECT * FROM v04g_source_snapshots WHERE monitoring_source_id=? AND content_hash=? ORDER BY id LIMIT 1", (source_id, digest)).fetchone()
            if existing:
                return dict(existing), False
            previous = conn.execute("SELECT id FROM v04g_source_snapshots WHERE monitoring_source_id=? AND COALESCE(normalized_url,url)=? ORDER BY id DESC LIMIT 1", (source_id, url)).fetchone()
            cur = conn.execute(
                """
                INSERT INTO v04g_source_snapshots(
                    snapshot_no, monitoring_source_id, monitoring_run_id, page_title, url,
                    captured_at, raw_content, cleaned_text, content_hash, metadata_json, created_at,
                    original_url, normalized_url, canonical_url, published_at, http_status,
                    raw_html, cleaned_html, content_type, content_length, is_changed,
                    previous_snapshot_id, attachment_path, attachment_page_count, evidence_status,
                    is_pilot, pilot_batch_id, immutable_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, 'captured', ?, ?, ?)
                """,
                (
                    f"SNP-P2-{uuid.uuid4().hex[:16].upper()}", source_id, job_id, page_title or None,
                    url, ts, raw_content, digest, json.dumps(metadata or {}, ensure_ascii=False), ts,
                    url, url, url, published_at, http_status, raw_html, content_type,
                    len((raw_html or raw_content).encode("utf-8")), int(previous is not None),
                    int(previous["id"]) if previous else None, attachment_path, attachment_page_count,
                    int(is_pilot), pilot_batch_id, ts,
                ),
            )
            row = conn.execute("SELECT * FROM v04g_source_snapshots WHERE id=?", (cur.lastrowid,)).fetchone()
            return dict(row), True

    def normalize(
        self,
        snapshot_id: int,
        *,
        text: str,
        title: str = "",
        language: str = "zh",
        content_type: str = "text/plain",
        is_pilot: bool | None = None,
        pilot_batch_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        digest = sha256_text(" ".join((text or "").split()))
        with db_connection(self.db_path) as conn:
            snapshot = conn.execute("SELECT * FROM v04g_source_snapshots WHERE id=?", (snapshot_id,)).fetchone()
            if not snapshot:
                raise ValueError("snapshot_not_found")
            existing = conn.execute("SELECT * FROM raw_intelligence WHERE evidence_snapshot_id=? AND content_hash=? ORDER BY id LIMIT 1", (snapshot_id, digest)).fetchone()
            if existing:
                return dict(existing), False
            cur = conn.execute(
                """
                INSERT INTO raw_intelligence(
                    title, source_url, source_type, content, visibility, review_status, created_at,
                    evidence_snapshot_id, content_hash, published_at, language, content_type,
                    processing_status, is_pilot, pilot_batch_id
                ) VALUES (?, ?, 'evidence_snapshot', ?, '内部', '待审核', ?, ?, ?, ?, ?, ?, 'normalized', ?, ?)
                """,
                (
                    title or snapshot["page_title"] or "未命名情报", snapshot["url"], text, now(),
                    snapshot_id, digest, snapshot["published_at"], language, content_type,
                    int(snapshot["is_pilot"] or 0) if is_pilot is None else int(is_pilot),
                    snapshot["pilot_batch_id"] if is_pilot is None else pilot_batch_id,
                ),
            )
            row = conn.execute("SELECT * FROM raw_intelligence WHERE id=?", (cur.lastrowid,)).fetchone()
            return dict(row), True

    def link_candidate(
        self,
        candidate_id: int,
        snapshot_id: int,
        *,
        excerpt: str,
        char_start: int | None = None,
        char_end: int | None = None,
        page_number: int | None = None,
        table_number: str | None = None,
        locator: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not excerpt.strip():
            raise ValueError("evidence_excerpt_required")
        digest = sha256_text(excerpt)
        with db_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO p2_fact_candidate_evidence(
                    candidate_id,snapshot_id,evidence_excerpt,char_start,char_end,page_number,
                    table_number,locator_json,evidence_hash,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (candidate_id, snapshot_id, excerpt, char_start, char_end, page_number, table_number, json.dumps(locator or {}, ensure_ascii=False), digest, now()),
            )
            row = conn.execute(
                """SELECT * FROM p2_fact_candidate_evidence
                   WHERE candidate_id=? AND snapshot_id=? AND evidence_hash=?
                     AND COALESCE(char_start,-1)=COALESCE(?,-1) AND COALESCE(char_end,-1)=COALESCE(?,-1)
                     AND COALESCE(page_number,-1)=COALESCE(?,-1) AND COALESCE(table_number,'')=COALESCE(?,'')""",
                (candidate_id, snapshot_id, digest, char_start, char_end, page_number, table_number),
            ).fetchone()
            return dict(row)

    def candidate_trace(self, candidate_id: int) -> list[dict[str, Any]]:
        with db_connection(self.db_path) as conn:
            rows = conn.execute(
                """SELECT e.*, s.url, s.captured_at, s.content_hash AS snapshot_hash, s.page_title,
                          s.published_at, s.content_type
                   FROM p2_fact_candidate_evidence e JOIN v04g_source_snapshots s ON s.id=e.snapshot_id
                   WHERE e.candidate_id=? ORDER BY e.id""",
                (candidate_id,),
            ).fetchall()
            return [dict(row) for row in rows]
