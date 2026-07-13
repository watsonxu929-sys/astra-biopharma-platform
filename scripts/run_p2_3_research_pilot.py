from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.research import add_topic_subject, create_topic
from app.services.research.fusion_service import (
    add_event_evidence,
    add_event_subject,
    create_assertion,
    create_industry_event,
    link_assertion_evidence,
    link_topic_event,
    register_conflict,
    review_assertion,
    review_event,
    submit_event,
)
from app.services.research.research_engine_service import (
    check_report_citations,
    compare_companies_research,
    compare_track_research,
    create_finding,
    create_research_report,
    review_finding,
    submit_finding,
    topic_workspace,
)
from app.settings import resolved_db_path
from app.v04c_review import db_connection

DEFAULT_SOURCE = Path(r"C:\tmp\p2_2_pilot_codex_20260711.db")
PRODUCTS = [
    {
        "name": "Journavx",
        "ingredient": "suzetrigine",
        "company": "Vertex Pharmaceuticals, Inc.",
        "company_id": "ORG-P23-PILOT-VERTEX",
        "date": "2025-01-30",
    },
    {
        "name": "Datroway",
        "ingredient": "datopotamab deruxtecan-dlnk",
        "company": "Daiichi Sankyo, Inc.",
        "company_id": "ORG-P23-PILOT-DAIICHI",
        "date": "2025-01-17",
    },
    {
        "name": "Blujepa",
        "ingredient": "gepotidacin",
        "company": "GlaxoSmithKline, LLC",
        "company_id": "ORG-P23-PILOT-GSK",
        "date": "2025-03-25",
    },
]


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def apply_migration(db_path: Path) -> None:
    path = ROOT / "scripts" / "migrations" / "005_research_fusion_engine.py"
    spec = importlib.util.spec_from_file_location("p2_3_migration_005", path)
    if not spec or not spec.loader:
        raise RuntimeError("migration_005_load_failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        module.apply_schema(conn)
        conn.commit()


def evidence_excerpt(text: str, product: str, radius: int = 360) -> str:
    index = text.casefold().find(product.casefold())
    if index < 0:
        raise ValueError(f"product_not_found_in_evidence:{product}")
    start = max(0, index - radius)
    end = min(len(text), index + len(product) + radius)
    return " ".join(text[start:end].split())


def seed_pilot_organizations(db_path: Path, batch_id: str) -> None:
    ts = now()
    with db_connection(db_path) as conn:
        for item in PRODUCTS:
            conn.execute(
                """INSERT OR IGNORE INTO organizations(
                   external_id,standard_name,org_type,region,industry_tags,relationship_source,
                   visibility,verification_status,created_at,organization_no,name,
                   organization_type,status,source,updated_at,is_active)
                   VALUES (?,?,?,'United States','biopharma;innovative medicine',?,
                           '内部','试点证据待正式主体匹配',?,?,?,?,'active',?,?,1)""",
                (
                    item["company_id"], item["company"], "biopharma company",
                    f"P2.3 controlled pilot {batch_id}", ts, item["company_id"],
                    item["company"], "biopharma company", f"P2.3 pilot:{batch_id}", ts,
                ),
            )


def load_sources(db_path: Path) -> dict[int, dict]:
    result: dict[int, dict] = {}
    with db_connection(db_path) as conn:
        for snapshot_id in (10, 11):
            row = conn.execute(
                """SELECT s.id,s.page_title,s.url,s.published_at,s.captured_at,
                          r.id raw_intelligence_id,r.content
                   FROM v04g_source_snapshots s
                   JOIN raw_intelligence r ON r.evidence_snapshot_id=s.id
                   WHERE s.id=?""",
                (snapshot_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"required_p2_2_evidence_missing:{snapshot_id}")
            result[snapshot_id] = dict(row)
    return result


def run(db_path: Path, *, batch_id: str, reviewer: str, confirm_human_reviewed: bool) -> dict:
    if db_path.resolve() == resolved_db_path().resolve():
        raise RuntimeError("pilot_must_run_on_database_copy")
    if not confirm_human_reviewed:
        raise RuntimeError("human_review_confirmation_required")

    apply_migration(db_path)
    seed_pilot_organizations(db_path, batch_id)
    sources = load_sources(db_path)

    with db_connection(db_path) as conn:
        if conn.execute("SELECT 1 FROM p2_pilot_batches WHERE batch_id=?", (batch_id,)).fetchone():
            raise RuntimeError("pilot_batch_already_exists")
        conn.execute(
            """INSERT INTO p2_pilot_batches(
               batch_id,name,status,source_manifest_json,sample_limit,created_by,created_at)
               VALUES (?,?,'running',?,?,?,?)""",
            (
                batch_id, "P2.3 FDA multi-source research pilot",
                json.dumps(
                    [{"snapshot_id": sid, "url": src["url"], "raw_intelligence_id": src["raw_intelligence_id"]}
                     for sid, src in sources.items()],
                    ensure_ascii=False,
                ),
                len(PRODUCTS), reviewer, now(),
            ),
        )

    topic = create_topic(
        name="2025 FDA 创新药审批多来源研究试点",
        description="基于 P2.2 两份真实 FDA 文档的受控 P2.3 研究试点",
        topic_type="regulatory_track",
        track_tags="FDA;novel drug approvals;2025",
        period_start="2025-01-01",
        period_end="2025-12-31",
        db_path=db_path,
    )
    with db_connection(db_path) as conn:
        conn.execute(
            """UPDATE research_topics SET research_scope=?,keywords=?,responsible_user=?,
               pilot_batch_id=?,updated_at=? WHERE id=?""",
            (
                "FDA 2025 novel drug approvals cross-source validation",
                "FDA;approval;novel drug;CDER", reviewer, batch_id, now(), topic["id"],
            ),
        )
    for item in PRODUCTS:
        add_topic_subject(topic["id"], "organization", item["company_id"], db_path=db_path)

    approved_event_ids: list[int] = []
    pending_event_ids: list[int] = []
    assertion_ids: list[int] = []
    finding_ids: list[int] = []
    evidence_ids: list[int] = []
    conflict_ids: list[int] = []

    for index, item in enumerate(PRODUCTS):
        event = create_industry_event(
            title=f"FDA approved {item['name']} ({item['ingredient']})",
            event_type="regulatory_approval",
            occurred_at=item["date"],
            published_at=item["date"],
            region="United States",
            stage="approved",
            importance=4,
            confidence=95,
            created_by=reviewer,
            fusion_method="deterministic_cross_source",
            is_pilot=True,
            pilot_batch_id=batch_id,
            db_path=db_path,
        )
        add_event_subject(
            event["id"], subject_type="organization", subject_id=item["company_id"],
            subject_label=item["company"], role="applicant", db_path=db_path,
        )
        add_event_subject(
            event["id"], subject_type="product",
            subject_id=f"PRODUCT-P23-{item['name'].upper()}",
            subject_label=item["name"], role="approved_product", db_path=db_path,
        )
        local_evidence = []
        for snapshot_id, source in sources.items():
            excerpt = evidence_excerpt(source["content"], item["name"])
            evidence = add_event_evidence(
                event["id"],
                snapshot_id=snapshot_id,
                raw_intelligence_id=source["raw_intelligence_id"],
                source_organization="U.S. Food and Drug Administration",
                source_title=source["page_title"],
                source_url=source["url"],
                published_at=source["published_at"] or "",
                captured_at=source["captured_at"] or "",
                evidence_excerpt=excerpt,
                locator={"product": item["name"], "document_role": "annual_report" if snapshot_id == 10 else "approval_compilation"},
                db_path=db_path,
            )
            local_evidence.append(evidence)
            evidence_ids.append(int(evidence["id"]))

        if index == 2:
            conflict = register_conflict(
                topic_id=topic["id"],
                event_id=event["id"],
                subject_type="organization",
                subject_id=item["company_id"],
                subject_label=item["company"],
                field_name="approval_date",
                value_a=item["date"],
                value_b="2025-03-26",
                evidence_a=[{"snapshot_id": 11, "excerpt": local_evidence[1]["evidence_excerpt"]}],
                evidence_b=[{"note": "P2.3 simulated conflict for workflow acceptance"}],
                is_simulated=True,
                is_pilot=True,
                pilot_batch_id=batch_id,
                db_path=db_path,
            )
            conflict_ids.append(int(conflict["id"]))
            submit_event(event["id"], actor=reviewer, db_path=db_path)
            pending_event_ids.append(int(event["id"]))
            continue

        submit_event(event["id"], actor=reviewer, db_path=db_path)
        review_event(
            event["id"], decision="approved", actor=reviewer,
            note="P2.3 pilot: human-confirmed against two existing FDA documents",
            db_path=db_path,
        )
        link_topic_event(topic["id"], event["id"], actor=reviewer, db_path=db_path)
        approved_event_ids.append(int(event["id"]))

        assertion = create_assertion(
            event_id=event["id"],
            topic_id=topic["id"],
            subject_type="organization",
            subject_id=item["company_id"],
            subject_label=item["company"],
            predicate="received_fda_approval",
            object_value=f"{item['name']} ({item['ingredient']})",
            valid_time=item["date"],
            confidence=95,
            created_by=reviewer,
            is_pilot=True,
            pilot_batch_id=batch_id,
            db_path=db_path,
        )
        for evidence in local_evidence:
            link_assertion_evidence(assertion["id"], evidence["id"], db_path=db_path)
        assertion = review_assertion(
            assertion["id"], decision="approved", actor=reviewer, db_path=db_path
        )
        assertion_ids.append(int(assertion["id"]))

        finding = create_finding(
            topic["id"],
            finding_type="verified_fact",
            title=f"{item['name']} FDA approval",
            content=(
                f"[事实] FDA records show {item['name']} ({item['ingredient']}) "
                f"was approved on {item['date']} for applicant {item['company']}."
            ),
            assertion_ids=[assertion["id"]],
            confidence=95,
            actor=reviewer,
            is_pilot=True,
            pilot_batch_id=batch_id,
            db_path=db_path,
        )
        submit_finding(finding["id"], actor=reviewer, db_path=db_path)
        finding = review_finding(
            finding["id"], decision="approved", actor=reviewer,
            note="P2.3 pilot human review", db_path=db_path,
        )
        finding_ids.append(int(finding["id"]))

    report = create_research_report(
        topic["id"], report_type="topic_report", created_by=reviewer,
        pilot_batch_id=batch_id, db_path=db_path,
    )
    citation_check = check_report_citations(report["id"], db_path=db_path)
    comparison = compare_companies_research(
        [item["company_id"] for item in PRODUCTS], db_path=db_path
    )
    track = compare_track_research("innovative medicine", db_path=db_path)
    workspace = topic_workspace(topic["id"], db_path=db_path)

    with db_connection(db_path) as conn:
        conn.execute(
            """UPDATE p2_pilot_batches SET status='needs_review',completed_at=?,
               source_manifest_json=? WHERE batch_id=?""",
            (
                now(),
                json.dumps(
                    {
                        "source_snapshot_ids": [10, 11],
                        "source_raw_intelligence_ids": [sources[10]["raw_intelligence_id"], sources[11]["raw_intelligence_id"]],
                        "topic_id": topic["id"],
                        "event_ids": approved_event_ids + pending_event_ids,
                        "report_id": report["id"],
                        "formal_publication_created": False,
                    },
                    ensure_ascii=False,
                ),
                batch_id,
            ),
        )

    result = {
        "pilot_batch_id": batch_id,
        "database_copy": str(db_path),
        "topic_id": int(topic["id"]),
        "company_count": len(PRODUCTS),
        "event_count": len(approved_event_ids) + len(pending_event_ids),
        "approved_event_count": len(approved_event_ids),
        "pending_event_count": len(pending_event_ids),
        "multi_source_event_count": len(PRODUCTS),
        "evidence_count": len(evidence_ids),
        "assertion_count": len(assertion_ids),
        "approved_finding_count": len(finding_ids),
        "conflict_count": len(conflict_ids),
        "simulated_conflict_count": len(conflict_ids),
        "timeline_event_count": len(workspace["timeline"]),
        "comparison_company_count": len(comparison["companies"]),
        "track_evidence_event_count": track["evidence_event_count"],
        "report_id": int(report["id"]),
        "report_status": report["research_status"],
        "report_version_count": len(report["versions"]),
        "citation_completeness": citation_check["rate"],
        "formal_publication_created": False,
        "formal_database_sha256": hashlib.sha256(resolved_db_path().read_bytes()).hexdigest(),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded P2.3 research fusion pilot on a database copy")
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--batch-id", default=f"P23-{datetime.now():%Y%m%d}-CODEX")
    parser.add_argument("--reviewer", default="p2-3-pilot-reviewer")
    parser.add_argument("--confirm-human-reviewed", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--replace-copy", action="store_true")
    args = parser.parse_args()

    source = args.source_db.resolve()
    target = args.db.resolve()
    if target == resolved_db_path().resolve():
        raise RuntimeError("pilot_must_run_on_database_copy")
    if not source.exists():
        raise FileNotFoundError(source)
    if target.exists() and not args.replace_copy:
        raise FileExistsError(f"target_exists:{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

    result = run(
        target,
        batch_id=args.batch_id,
        reviewer=args.reviewer,
        confirm_human_reviewed=args.confirm_human_reviewed,
    )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
