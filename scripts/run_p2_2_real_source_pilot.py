from __future__ import annotations

import argparse
import json
import mimetypes
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.collection_service import USER_AGENT, check_robots, create_collection_source, create_job, process_job
from app.services.evidence_service import EvidenceService
from app.services.parsers import DocumentParser, ParserUnavailable
from app.services.processing import create_processing_job, process_job as process_processing_job
from app.settings import resolved_db_path
from app.v04c_review import db_connection


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _download(url: str, target: Path, max_bytes: int) -> tuple[str, int]:
    robots = check_robots(url)
    if not robots.get("allowed", True):
        raise PermissionError("robots_denied")
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with httpx.stream(
                "GET", url, follow_redirects=True, timeout=30,
                headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.5"},
            ) as response:
                response.raise_for_status()
                length = int(response.headers.get("content-length") or 0)
                if length and length > max_bytes:
                    raise ValueError("document_too_large")
                size = 0
                with target.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError("document_too_large")
                        handle.write(chunk)
                return response.headers.get("content-type", "").split(";", 1)[0], response.status_code
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
            if attempt == 2:
                raise
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("document_download_failed")


def _normalize_run(db_path: Path, run_id: int, batch_id: str) -> tuple[list[int], list[int]]:
    evidence = EvidenceService(db_path)
    snapshot_ids: list[int] = []
    raw_ids: list[int] = []
    with db_connection(db_path) as conn:
        rows = [dict(row) for row in conn.execute(
            "SELECT * FROM v04g_source_snapshots WHERE monitoring_run_id=? ORDER BY id", (run_id,)
        )]
    for snapshot in rows:
        quality = snapshot.get("quality_status") or "accepted"
        with db_connection(db_path) as conn:
            conn.execute(
                "UPDATE v04g_source_snapshots SET is_pilot=1,pilot_batch_id=? WHERE id=?",
                (batch_id, snapshot["id"]),
            )
        snapshot_ids.append(int(snapshot["id"]))
        if quality != "accepted":
            continue
        raw, _ = evidence.normalize(
            int(snapshot["id"]), text=snapshot.get("cleaned_text") or snapshot.get("raw_content") or "",
            title=snapshot.get("page_title") or "", language="unknown",
            content_type=snapshot.get("content_type") or "text/plain", is_pilot=True,
            pilot_batch_id=batch_id,
        )
        raw_ids.append(int(raw["id"]))
    return snapshot_ids, raw_ids


def _process_snapshots(db_path: Path, snapshot_ids: list[int], batch_id: str) -> list[dict]:
    results: list[dict] = []
    for snapshot_id in snapshot_ids:
        with db_connection(db_path) as conn:
            snapshot = conn.execute(
                "SELECT quality_status,parse_status FROM v04g_source_snapshots WHERE id=?",
                (snapshot_id,),
            ).fetchone()
        if snapshot and (snapshot["quality_status"] not in {None, "accepted"} or snapshot["parse_status"] in {"ocr_required", "parse_failed"}):
            results.append(
                {"snapshot_id": snapshot_id, "status": "skipped", "reason": "quality_gate_rejected"}
            )
            continue
        job = create_processing_job(
            snapshot_id=snapshot_id, trigger_type="p2_2_pilot", operator="p2_2_pilot",
            queued_only=False, db_path=db_path,
        )
        results.append(process_processing_job(int(job["id"]), db_path=db_path))
    with db_connection(db_path) as conn:
        placeholders = ",".join("?" for _ in snapshot_ids) or "NULL"
        conn.execute(
            f"UPDATE v05g_extraction_candidates SET is_pilot=1,pilot_batch_id=?,pipeline_review_status='pending' WHERE snapshot_id IN ({placeholders})",
            (batch_id, *snapshot_ids),
        )
    return results


def run(db_path: Path, manifest_path: Path, batch_id: str, max_total: int = 30) -> dict:
    if db_path.resolve() == resolved_db_path().resolve():
        raise RuntimeError("pilot_must_run_on_database_copy")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = list(manifest.get("sources") or [])
    declared = sum(int(item.get("max_items") or 1) for item in sources)
    hard_limit = min(int(max_total), int(manifest.get("total_content_limit") or 30), 30)
    if declared > hard_limit:
        raise ValueError("pilot_content_limit_exceeded")
    with db_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO p2_pilot_batches(batch_id,name,status,source_manifest_json,sample_limit,created_by,created_at) VALUES (?,?, 'running', ?,?,?,?)",
            (batch_id, "P2.2 real-source controlled pilot", json.dumps(sources, ensure_ascii=False), min(hard_limit, 20), "codex-p2-2", now()),
        )

    started = time.perf_counter()
    source_results: list[dict] = []
    all_snapshots: list[int] = []
    all_raw: list[int] = []
    attachments_dir = db_path.parent / f"{db_path.stem}_p2_2_attachments"
    for spec in sources:
        source = create_collection_source(
            name=spec["name"], source_type="webpage" if spec["source_type"] == "document" else spec["source_type"],
            url=spec["url"], collection_mode=spec["collection_mode"], max_links=min(int(spec.get("max_items") or 1), 30),
            crawl_detail_pages=bool(spec.get("crawl_detail_pages")), compliance_note="P2.2 controlled public-source pilot",
            db_path=db_path,
        )
        source_id = int(source["id"])
        with db_connection(db_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(v04g_monitoring_sources)")}
            if "wait_selector" in columns:
                conn.execute(
                    "UPDATE v04g_monitoring_sources SET wait_selector=?,max_file_bytes=?,source_credibility=? WHERE id=?",
                    (spec.get("wait_selector"), 20 * 1024 * 1024, int(spec.get("credibility") or 3), source_id),
                )
        job = create_job(source_id, trigger_type="p2_2_pilot", operator="codex-p2-2", db_path=db_path)
        run_id = int(job["id"])
        if spec["source_type"] != "document":
            result = process_job(run_id, db_path=db_path)
            snapshots, raw_ids = _normalize_run(db_path, run_id, batch_id)
            all_snapshots.extend(snapshots)
            all_raw.extend(raw_ids)
            source_results.append({"source_id": spec["id"], **result, "snapshot_ids": snapshots})
            continue

        extension = ".pdf" if spec.get("mime_type") == "application/pdf" else ".xlsx"
        target = attachments_dir / f"{spec['id']}{extension}"
        try:
            content_type, status = _download(spec["url"], target, 20 * 1024 * 1024)
            content_type = spec.get("mime_type") or content_type or mimetypes.guess_type(target.name)[0]
            parsed = DocumentParser().parse({
                "attachment_path": str(target), "content_type": content_type,
                "source_url": spec["url"], "max_file_bytes": 20 * 1024 * 1024,
            })
            snapshot, _ = EvidenceService(db_path).get_or_create_snapshot(
                source_id=source_id, job_id=run_id, url=spec["url"], raw_content=parsed.text,
                page_title=spec["name"], content_type=content_type, http_status=status,
                metadata=parsed.metadata, attachment_path=str(target),
                attachment_page_count=parsed.metadata.get("page_count"), is_pilot=True, pilot_batch_id=batch_id,
            )
            raw, _ = EvidenceService(db_path).normalize(
                int(snapshot["id"]), text=parsed.text, title=spec["name"], language="unknown",
                content_type=content_type, is_pilot=True, pilot_batch_id=batch_id,
            )
            with db_connection(db_path) as conn:
                conn.execute(
                    "UPDATE v04g_source_snapshots SET parse_status=?,quality_status=?,sections_json=?,tables_json=?,attachment_filename=?,attachment_hash=? WHERE id=?",
                    (parsed.status, "accepted" if parsed.status == "success" else "needs_manual_review", json.dumps(parsed.sections, ensure_ascii=False), json.dumps(parsed.tables, ensure_ascii=False), parsed.metadata.get("filename"), parsed.metadata.get("file_hash"), snapshot["id"]),
                )
                conn.execute(
                    "UPDATE raw_intelligence SET sections_json=?,tables_json=?,quality_status=? WHERE id=?",
                    (json.dumps(parsed.sections, ensure_ascii=False), json.dumps(parsed.tables, ensure_ascii=False), "accepted" if parsed.status == "success" else "needs_manual_review", raw["id"]),
                )
                conn.execute("UPDATE v04g_monitoring_runs SET status='success',finished_at=?,snapshot_count=1 WHERE id=?", (now(), run_id))
            all_snapshots.append(int(snapshot["id"]))
            all_raw.append(int(raw["id"]))
            source_results.append({"source_id": spec["id"], "status": "success", "snapshot_ids": [int(snapshot["id"])], "parser": parsed.parser_name})
        except ParserUnavailable as exc:
            with db_connection(db_path) as conn:
                conn.execute("UPDATE v04g_monitoring_runs SET status='failed',finished_at=?,error_type='parser_or_collector_unavailable',error_stage='parse',error_message=? WHERE id=?", (str(exc), run_id))
            source_results.append({"source_id": spec["id"], "status": "failed", "error_type": "parser_or_collector_unavailable"})
        except Exception as exc:
            stage = "download" if not target.exists() else "parse"
            with db_connection(db_path) as conn:
                conn.execute(
                    "UPDATE v04g_monitoring_runs SET status='failed',finished_at=?,error_type=?,error_stage=?,error_message=? WHERE id=?",
                    (exc.__class__.__name__, stage, str(exc)[:800], run_id),
                )
            source_results.append({
                "source_id": spec["id"], "status": "failed",
                "error_type": exc.__class__.__name__, "error_stage": stage,
            })

    processing = _process_snapshots(db_path, all_snapshots, batch_id) if all_snapshots else []
    with db_connection(db_path) as conn:
        candidate_count = int(conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE pilot_batch_id=?", (batch_id,)).fetchone()[0])
        pending = int(conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE pilot_batch_id=? AND pipeline_review_status='pending'", (batch_id,)).fetchone()[0])
        low_quality = int(conn.execute("SELECT COUNT(*) FROM v04g_source_snapshots WHERE pilot_batch_id=? AND quality_status IS NOT NULL AND quality_status<>'accepted'", (batch_id,)).fetchone()[0])
        conn.execute("UPDATE p2_pilot_batches SET status='needs_review',completed_at=? WHERE batch_id=?", (now(), batch_id))
    return {
        "pilot_batch_id": batch_id, "source_count": len(sources), "declared_content_limit": declared,
        "snapshot_count": len(set(all_snapshots)), "raw_intelligence_count": len(set(all_raw)),
        "low_quality_filtered": low_quality, "candidate_count": candidate_count,
        "pending_review_count": pending, "approved_count": 0, "rejected_count": 0,
        "ai_call_count": 0, "estimated_cost_usd": 0.0,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "sources": source_results, "processing": processing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded P2.2 pilot on a database copy")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / "config" / "p2_2_source_pilot.json")
    parser.add_argument("--batch-id", default=f"P22-{uuid.uuid4().hex[:12].upper()}")
    parser.add_argument("--max-total", type=int, default=30)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = run(args.db.resolve(), args.manifest.resolve(), args.batch_id, args.max_total)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
