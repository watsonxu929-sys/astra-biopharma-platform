from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path


def _fk_rows(path: Path) -> set[tuple[object, ...]]:
    with sqlite3.connect(path) as conn:
        return {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")}


def _scalar(conn, sql: str, params: dict | None = None) -> int:
    from sqlalchemy import text
    return int(conn.execute(text(sql), params or {}).scalar() or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and clean the MVP-RC1 canonical golden loop")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--keep-data", action="store_true")
    args = parser.parse_args()
    database = args.database.resolve()
    if not database.exists():
        raise SystemExit("database_not_found")
    if not any(token in database.name.lower() for token in ("test", "copy", "rehearsal", "acceptance")):
        raise SystemExit("refusing_non_test_database")

    os.environ["APP_DB_PATH"] = str(database)
    os.environ["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    os.environ["APP_ENV"] = "testing"
    os.environ["SCHEDULER_ENABLED"] = "false"
    os.environ["WORKER_ENABLED"] = "false"

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from fastapi import HTTPException
    from sqlalchemy import text
    from app.database import SessionLocal, engine
    from app.services.golden_loop_service import GoldenLoopService
    from app.services.unified_resource_service import UnifiedResourceService

    marker = f"MVP-RC1-ACCEPT-{uuid.uuid4().hex[:10].upper()}"
    before_fk = _fk_rows(database)
    created = {
        "resources": [],
        "matches": [],
        "opportunities": [],
        "relationships": [],
        "subject_links": [],
    }
    results: dict[str, object] = {"marker": marker}

    with SessionLocal() as db:
        actor = db.execute(
            text(
                """
                SELECT id,role FROM v05a_users
                WHERE status='active' AND role IN ('operator','admin')
                ORDER BY CASE role WHEN 'operator' THEN 0 ELSE 1 END,id LIMIT 1
                """
            )
        ).mappings().first()
        intelligence = db.execute(
            text("SELECT id,title FROM v06_intelligence_items WHERE status='published' ORDER BY id LIMIT 1")
        ).mappings().first()
        organizations = db.execute(
            text(
                """
                SELECT id,standard_name FROM organizations
                WHERE COALESCE(is_active,1)=1 ORDER BY id LIMIT 12
                """
            )
        ).mappings().all()
        if not actor or not intelligence or len(organizations) < 2:
            raise RuntimeError("missing_acceptance_prerequisites")
        demand_org = supply_org = None
        for left in organizations:
            for right in organizations:
                if left["id"] == right["id"]:
                    continue
                exists = db.execute(
                    text(
                        """
                        SELECT 1 FROM p3_canonical_relationships
                        WHERE relationship_type='cooperates_with' AND review_status='approved'
                          AND ((subject_id=:left_id AND object_id=:right_id)
                            OR (subject_id=:right_id AND object_id=:left_id))
                        LIMIT 1
                        """
                    ),
                    {"left_id": str(left["id"]), "right_id": str(right["id"])},
                ).first()
                if not exists:
                    demand_org, supply_org = left, right
                    break
            if demand_org:
                break
        if not demand_org or not supply_org:
            raise RuntimeError("no_clean_organization_pair")

        actor_id = int(actor["id"])
        intelligence_id = int(intelligence["id"])
        original_opportunity_count = _scalar(db, "SELECT COUNT(*) FROM v06_opportunities")
        original_marker_count = _scalar(
            db,
            "SELECT COUNT(*) FROM v06_market_resources WHERE title LIKE :marker",
            {"marker": f"%{marker}%"},
        )
        service = GoldenLoopService(db)

        try:
            service.require_writer("viewer")
            raise AssertionError("viewer_write_guard_missing")
        except HTTPException as exc:
            assert exc.status_code == 403
            results["viewer_write_status"] = 403
        service.require_writer(str(actor["role"]))
        results["operator_write_allowed"] = True

        for organization in (demand_org, supply_org):
            existed = db.execute(
                text(
                    """
                    SELECT id FROM core_intelligence_subject_links
                    WHERE intelligence_item_id=:item_id
                      AND subject_type='organization' AND subject_id=:subject_id
                    """
                ),
                {"item_id": intelligence_id, "subject_id": int(organization["id"])},
            ).first()
            service.link_subject(
                intelligence_id,
                subject_type="organization",
                subject_id=int(organization["id"]),
                actor_user_id=actor_id,
            )
            if not existed:
                created["subject_links"].append(
                    (intelligence_id, "organization", int(organization["id"]))
                )

        def run_case(case: str, outcome: str, evidence: str = "") -> dict:
            demand = service.create_resource_from_intelligence(
                intelligence_id,
                direction="demand",
                actor_user_id=actor_id,
                fields={
                    "title": f"{marker}-{case}-需求",
                    "resource_type": "产业合作",
                    "summary": "寻找可验证的产业合作方",
                    "organization_id": int(demand_org["id"]),
                },
            )
            supply = service.create_resource_from_intelligence(
                intelligence_id,
                direction="supply",
                actor_user_id=actor_id,
                fields={
                    "title": f"{marker}-{case}-供给",
                    "resource_type": "产业合作",
                    "summary": "提供可验证的产业合作能力",
                    "organization_id": int(supply_org["id"]),
                },
            )
            created["resources"].extend([int(demand["id"]), int(supply["id"])])
            suggested = UnifiedResourceService(db).match(int(demand["id"]), limit=10)
            assert int(supply["id"]) in {int(item["resource"].id) for item in suggested}
            results.setdefault("candidate_generation", {})[case] = {
                "generated": True,
                "explained": any(item["reasons"] for item in suggested if int(item["resource"].id) == int(supply["id"])),
            }
            match = service.confirm_match(
                demand_resource_id=int(demand["id"]),
                supply_resource_id=int(supply["id"]),
                actor_user_id=actor_id,
                note=f"{marker}-{case}-人工确认",
            )
            created["matches"].append(int(match["id"]))
            repeated = service.confirm_match(
                demand_resource_id=int(demand["id"]),
                supply_resource_id=int(supply["id"]),
                actor_user_id=actor_id,
                note=f"{marker}-{case}-重复确认",
            )
            assert int(repeated["id"]) == int(match["id"])
            opportunity = service.convert_match_to_opportunity(
                int(match["id"]), actor_user_id=actor_id
            )
            created["opportunities"].append(int(opportunity["id"]))
            repeated_opportunity = service.convert_match_to_opportunity(
                int(match["id"]), actor_user_id=actor_id
            )
            assert int(repeated_opportunity["id"]) == int(opportunity["id"])
            service.add_follow_up(
                int(opportunity["id"]),
                actor_user_id=actor_id,
                content=f"{marker}-{case}-首次商务跟进",
                next_action="安排双方进一步沟通",
                contact_result="已联系",
                stage_after="contacted",
            )
            task = service.create_task(
                int(opportunity["id"]),
                actor_user_id=actor_id,
                title=f"{marker}-{case}-下一步任务",
                priority="P1",
            )
            assert int(task["opportunity_id"]) == int(opportunity["id"])
            closed = service.close_outcome(
                int(opportunity["id"]),
                actor_user_id=actor_id,
                outcome=outcome,
                reason=f"{marker}-{case}-{outcome}",
                result_note=f"{case} 案例结果",
                cooperation_scale="验收规模" if outcome == "won" else "",
                evidence_text=evidence,
            )
            if closed.get("result_relationship_id"):
                created["relationships"].append(int(closed["result_relationship_id"]))
            return {
                "resource_ids": [int(demand["id"]), int(supply["id"])],
                "match_id": int(match["id"]),
                "opportunity_id": int(opportunity["id"]),
                "outcome": closed["outcome_status"],
                "relationship_id": closed.get("result_relationship_id"),
            }

        results["case_a"] = run_case(
            "A",
            "won",
            evidence=f"{marker} 双方已签署合作确认文件，人工核验通过。",
        )
        results["case_b"] = run_case("B", "lost")
        results["case_c"] = run_case("C", "paused")
        assert results["case_a"]["relationship_id"]
        assert results["case_b"]["relationship_id"] is None
        assert results["case_c"]["relationship_id"] is None

        trace = service.trace(intelligence_id)
        assert set(created["opportunities"]).issubset(
            {int(row["id"]) for row in trace["opportunities"]}
        )
        results["trace_counts"] = {
            key: len(trace[key])
            for key in ("subjects", "resources", "matches", "opportunities", "follow_ups", "relationships")
        }
        results["original_opportunity_count"] = original_opportunity_count
        results["original_marker_count"] = original_marker_count

    engine.dispose()
    with sqlite3.connect(database) as persisted:
        persisted.row_factory = sqlite3.Row
        for opportunity_id in created["opportunities"]:
            row = persisted.execute(
                "SELECT outcome_status FROM v06_opportunities WHERE id=?",
                (opportunity_id,),
            ).fetchone()
            assert row is not None
        results["restart_persistence"] = True

    if not args.keep_data:
        with sqlite3.connect(database) as cleanup:
            cleanup.execute("PRAGMA foreign_keys=ON")
            cleanup.execute("BEGIN IMMEDIATE")
            for relationship_id in created["relationships"]:
                cleanup.execute(
                    "DELETE FROM p3_relationship_evidence WHERE relationship_id=?",
                    (relationship_id,),
                )
                cleanup.execute(
                    "DELETE FROM p3_canonical_relationships WHERE id=?",
                    (relationship_id,),
                )
            for opportunity_id in created["opportunities"]:
                cleanup.execute(
                    "DELETE FROM v06_timeline_entries WHERE opportunity_id=?",
                    (opportunity_id,),
                )
                cleanup.execute(
                    "DELETE FROM v06_follow_ups WHERE opportunity_id=?",
                    (opportunity_id,),
                )
                cleanup.execute(
                    "DELETE FROM v06_collab_tasks WHERE opportunity_id=?",
                    (opportunity_id,),
                )
                cleanup.execute(
                    "DELETE FROM v06_opportunities WHERE id=?",
                    (opportunity_id,),
                )
            for match_id in created["matches"]:
                cleanup.execute(
                    "DELETE FROM p4_resource_match_candidates WHERE id=?",
                    (match_id,),
                )
            for resource_id in created["resources"]:
                cleanup.execute(
                    "DELETE FROM core_intelligence_workflow_events WHERE action='resource_created' AND note IN (?,?)",
                    (f"demand:{resource_id}", f"supply:{resource_id}"),
                )
                cleanup.execute(
                    "DELETE FROM v06_market_resources WHERE id=?",
                    (resource_id,),
                )
            for item_id, subject_type, subject_id in created["subject_links"]:
                cleanup.execute(
                    """
                    DELETE FROM core_intelligence_subject_links
                    WHERE intelligence_item_id=? AND subject_type=? AND subject_id=?
                    """,
                    (item_id, subject_type, subject_id),
                )
                cleanup.execute(
                    """
                    DELETE FROM core_intelligence_workflow_events
                    WHERE intelligence_item_id=? AND action='subject_linked' AND note=?
                    """,
                    (item_id, f"{subject_type}:{subject_id}"),
                )
            cleanup.commit()
            assert cleanup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            marker_count = cleanup.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM v06_market_resources WHERE title LIKE ?)
                + (SELECT COUNT(*) FROM v06_follow_ups WHERE content LIKE ?)
                + (SELECT COUNT(*) FROM p3_relationship_evidence WHERE evidence_text LIKE ?)
                """,
                (f"%{marker}%", f"%{marker}%", f"%{marker}%"),
            ).fetchone()[0]
            assert marker_count == 0
            final_opportunity_count = cleanup.execute(
                "SELECT COUNT(*) FROM v06_opportunities"
            ).fetchone()[0]
            assert final_opportunity_count == results["original_opportunity_count"]
        results["cleanup"] = "complete"
        results["marker_residue"] = 0

    after_fk = _fk_rows(database)
    if after_fk != before_fk:
        raise AssertionError(
            f"foreign_key_state_changed:before={len(before_fk)} after={len(after_fk)}"
        )
    results["foreign_key_state"] = {
        "before": len(before_fk),
        "after": len(after_fk),
        "unchanged": True,
    }
    results["integrity"] = "ok"
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
