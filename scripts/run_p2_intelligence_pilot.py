from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ai_analysis_service import AIAnalysisService
from app.services.collectors import PlaywrightAdapter
from app.services.evidence_service import EvidenceService
from app.services.fact_candidate_service import FactCandidateService
from app.services.intelligence_product_service import IntelligenceProductService
from app.services.parsers import DocumentParser
from app.services.parsing_service import ParsingService
from app.services.processing.processing_job_service import create_processing_job
from app.settings import resolved_db_path
from app.v04c_review import db_connection


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def require_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"p2_pilot_batches", "p2_fact_candidate_evidence", "p2_intelligence_product_evidence", "p2_ai_analysis_runs"}
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"p2_schema_required:{','.join(missing)}")


def run(db_path: Path, *, snapshot_id: int, batch_id: str, reviewer: str) -> dict:
    if db_path.resolve() == resolved_db_path().resolve():
        raise RuntimeError("pilot_must_run_on_database_copy")
    require_schema(db_path)
    with db_connection(db_path) as conn:
        snapshot = conn.execute("SELECT * FROM v04g_source_snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if not snapshot:
            raise ValueError("snapshot_not_found")
        manifest = [{"snapshot_id": snapshot_id, "url": snapshot["url"], "source_type": "existing_public_webpage"}]
        conn.execute(
            "INSERT INTO p2_pilot_batches(batch_id,name,status,source_manifest_json,sample_limit,created_by,created_at) VALUES (?,?, 'running', ?,1,?,?)",
            (batch_id, "P2.1 evidence pipeline pilot", json.dumps(manifest, ensure_ascii=False), reviewer, now()),
        )
    content_type = snapshot["content_type"] or ("text/html" if snapshot["raw_html"] else "text/plain")
    parsed = ParsingService().parse({**dict(snapshot), "content_type": content_type})
    raw, raw_created = EvidenceService(db_path).normalize(
        snapshot_id, text=parsed.text, title=snapshot["page_title"] or "",
        language="zh", content_type="text/plain", is_pilot=True,
        pilot_batch_id=batch_id,
    )
    job = create_processing_job(snapshot_id=snapshot_id, trigger_type="p2_pilot", operator=reviewer, queued_only=False, db_path=db_path)
    analysis = AIAnalysisService(db_path).analyze(
        processing_job_id=int(job["id"]), snapshot_id=snapshot_id,
        raw_intelligence_id=int(raw["id"]), text=parsed.text,
        title=snapshot["page_title"] or "", provider_name="rule",
        is_pilot=True, pilot_batch_id=batch_id,
    )
    approved = rejected = pending = 0
    product_ids: list[int] = []
    for candidate_id in analysis["candidate_ids"]:
        FactCandidateService(db_path).review(candidate_id, decision="approved", actor=reviewer, permissions={"review_data"}, reason="P2.1 pilot manual acceptance")
        product = IntelligenceProductService(db_path).publish_candidate(candidate_id, actor=reviewer, permissions={"review_data"})
        product_ids.append(int(product["id"]))
        approved += 1
    if not analysis["candidate_ids"]:
        pending = 1
    manifest[0].update({
        "raw_intelligence_id": int(raw["id"]),
        "candidate_ids": list(analysis["candidate_ids"]),
        "product_ids": product_ids,
    })
    with db_connection(db_path) as conn:
        conn.execute(
            "UPDATE p2_pilot_batches SET status=?,source_manifest_json=?,completed_at=? WHERE batch_id=?",
            ("completed" if product_ids else "needs_review", json.dumps(manifest, ensure_ascii=False), now(), batch_id),
        )
    return {
        "batch_id": batch_id,
        "sample_count": 1,
        "snapshot_id": snapshot_id,
        "raw_intelligence_id": raw["id"],
        "raw_created": raw_created,
        "parser": parsed.parser_name,
        "analysis": analysis,
        "candidate_count": len(analysis["candidate_ids"]),
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "product_ids": product_ids,
        "playwright_available": PlaywrightAdapter().available,
        "docling_available": DocumentParser().available,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded P2.1 pilot on a database copy")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--snapshot-id", type=int, required=True)
    parser.add_argument("--batch-id", default=f"P2P-{uuid.uuid4().hex[:12].upper()}")
    parser.add_argument("--reviewer", default="p2-pilot-reviewer")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = run(args.db.resolve(), snapshot_id=args.snapshot_id, batch_id=args.batch_id, reviewer=args.reviewer)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
