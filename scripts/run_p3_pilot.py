from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.canonical_relationship_service import CanonicalRelationshipService, ConnectionRecommendationService, RelationshipNetworkService
from app.services.entity_governance_service import EntityMergeService, EntityRegistryService, EntityResolutionService
from app.settings import resolved_db_path


def copy_database(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as src:
        with sqlite3.connect(output) as dst:
            src.backup(dst)


def apply_migration(output: Path) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/migrations/006_entity_relationship_network.py"), "--apply", "--db", str(output)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an isolated P3 acceptance pilot database")
    parser.add_argument("--source-db", type=Path, default=resolved_db_path())
    parser.add_argument("--output-db", type=Path, default=Path(r"C:\tmp\p3_entity_network_pilot.db"))
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p3/P3_PILOT_RUN.json")
    parser.add_argument("--batch-id", default=f"P3-PILOT-{date.today():%Y%m%d}")
    args = parser.parse_args()
    source, output = args.source_db.resolve(), args.output_db.resolve()
    if not source.exists():
        raise SystemExit("source database does not exist")
    if output == source or output == resolved_db_path().resolve():
        raise SystemExit("pilot output must not be the formal database")
    copy_database(source, output)
    apply_migration(output)
    batch, actor = args.batch_id, "p3_pilot"
    registry, resolver = EntityRegistryService(output), EntityResolutionService(output)
    relationship = CanonicalRelationshipService(output)
    with sqlite3.connect(output) as conn:
        conn.row_factory = sqlite3.Row
        people = [dict(row) for row in conn.execute("SELECT external_id,name FROM people WHERE external_id IS NOT NULL AND COALESCE(is_active,1)=1 ORDER BY id LIMIT 12")]
        organizations = [dict(row) for row in conn.execute("SELECT external_id,COALESCE(NULLIF(name,''),standard_name) AS name,short_name FROM organizations WHERE external_id IS NOT NULL AND COALESCE(is_active,1)=1 ORDER BY id LIMIT 12")]
        projects = [dict(row) for row in conn.execute("SELECT external_id,name,owner_external_id,owner_organization_id FROM projects WHERE external_id IS NOT NULL AND COALESCE(is_active,1)=1 ORDER BY id LIMIT 5")]
        snapshots = [dict(row) for row in conn.execute("SELECT id,url,page_title,captured_at FROM v04g_source_snapshots ORDER BY id LIMIT 2")]
    if len(people) < 10 or len(organizations) < 10 or len(projects) < 5:
        raise SystemExit("pilot requires at least 10 people, 10 organizations and 5 projects")

    products = []
    for index in range(6):
        products.append(registry.create_product(
            f"P3 试点产品资产 {index + 1}", asset_type="drug" if index < 4 else "technology_platform",
            actor=actor, permissions={"edit_data"}, owner_organization_id=organizations[index]["external_id"],
            development_code=f"P3-DEV-{index + 1:02d}", source="P3 isolated pilot",
            is_pilot=True, pilot_batch_id=batch,
        ))

    registry.add_alias(
        "organization", organizations[0]["external_id"], f"{organizations[0]['name']}（试点简称）",
        alias_type="short_name", actor=actor, permissions={"review_data"}, source="P3 isolated pilot",
        is_pilot=True, pilot_batch_id=batch,
    )
    same_name_candidates = resolver.propose(
        "person", people[0]["name"], actor=actor, source_record_type="p3_pilot_same_name",
        source_record_id=batch, is_pilot=True, pilot_batch_id=batch,
    )
    organization_candidates = resolver.propose(
        "organization", f"{organizations[0]['name']}（试点简称）", actor=actor,
        source_record_type="p3_pilot_short_full_name", source_record_id=batch,
        is_pilot=True, pilot_batch_id=batch,
    )
    merge_preview = EntityMergeService(output).preview(
        "organization", organizations[1]["external_id"], organizations[0]["external_id"],
        reason="P3 隔离试点仅验证合并影响预览，不提交、不执行", actor=actor,
        evidence=[{"pilot_batch_id": batch, "note": "preview only"}], is_pilot=True, pilot_batch_id=batch,
    )

    def evidence(label: str, *, multi: bool = False) -> list[dict]:
        rows = snapshots[:2] if multi else snapshots[:1]
        if not rows:
            return [{"evidence_text": f"{label}；P3 隔离试点人工确认", "source_url": "https://example.invalid/p3-pilot", "evidence_strength": "supporting"}]
        return [{"evidence_snapshot_id": row["id"], "evidence_text": f"{label}；来源快照 {row['id']}", "source_url": row["url"], "source_date": str(row["captured_at"] or "")[:10], "evidence_strength": "supporting"} for row in rows]

    approved = []
    def approve(subject_type: str, subject_id: str, rel_type: str, object_type: str, object_id: str, *, index: int, valid_from: str | None = None, valid_to: str | None = None, multi: bool = False) -> dict:
        candidate = relationship.create_candidate(
            subject_type=subject_type, subject_id=subject_id, relationship_type=rel_type,
            object_type=object_type, object_id=object_id, actor=actor, valid_from=valid_from,
            valid_to=valid_to, confidence=82 if multi else 72, evidence=evidence(f"P3 试点关系 {index}", multi=multi),
            source_record_type="p3_isolated_pilot", source_record_id=f"{batch}:{index}", is_pilot=True, pilot_batch_id=batch,
        )
        reviewed = relationship.review_candidate(candidate["id"], "approved", actor="p3_pilot_reviewer", permissions={"review_data"}, note="隔离试点人工审核")
        approved.append(reviewed["relationship"])
        return reviewed["relationship"]

    relation_index = 0
    for index, person in enumerate(people):
        relation_index += 1
        historical = index < 3
        approve("person", person["external_id"], "formerly_employed_by" if historical else "employed_by", "organization", organizations[index // 4]["external_id"],
                index=relation_index, valid_from="2018-01-01" if historical else "2024-01-01", valid_to="2020-12-31" if historical else None)
    for index, product in enumerate(products):
        for rel_type in ("develops", "owns"):
            relation_index += 1
            approve("organization", organizations[index]["external_id"], rel_type, "product", product["external_id"], index=relation_index, valid_from="2023-01-01", multi=relation_index in {13, 14})
    for index, project in enumerate(projects):
        relation_index += 1
        owner = project.get("owner_organization_id") or project.get("owner_external_id")
        if not owner or not registry.get("organization", str(owner)):
            owner = organizations[index]["external_id"]
        approve("project", project["external_id"], "initiated_by", "organization", str(owner), index=relation_index, valid_from="2022-01-01")

    network = RelationshipNetworkService(output)
    path_queries = [
        network.find_paths("person", people[4]["external_id"], "person", people[5]["external_id"]),
        network.find_paths("person", people[8]["external_id"], "product", products[2]["external_id"]),
        network.find_paths("person", people[4]["external_id"], "product", products[1]["external_id"]),
    ]
    connection_candidates = ConnectionRecommendationService(output).recommend(
        people[4]["external_id"], limit=5, actor=actor, persist=True, is_pilot=True, pilot_batch_id=batch,
    )
    with sqlite3.connect(output) as conn:
        counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table} WHERE pilot_batch_id=?", (batch,)).fetchone()[0] for table in (
            "p3_product_assets", "p3_entity_aliases", "p3_entity_resolution_candidates", "p3_entity_merge_records",
            "p3_canonical_relationships", "p3_relationship_candidates", "p3_connection_candidates",
        )}
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        historical = conn.execute("SELECT COUNT(*) FROM p3_canonical_relationships WHERE pilot_batch_id=? AND is_current=0", (batch,)).fetchone()[0]
        multi_source = conn.execute("SELECT COUNT(*) FROM p3_canonical_relationships WHERE pilot_batch_id=? AND source_count>=2", (batch,)).fetchone()[0]
    report = {
        "status": "passed", "batch_id": batch, "database": str(output), "source_database_name": source.name,
        "integrity_check": integrity, "selected": {"people": len(people), "organizations": len(organizations), "projects": len(projects)},
        "counts": counts, "historical_relationships": historical, "multi_source_relationships": multi_source,
        "same_name_candidate_strength": same_name_candidates[0]["match_strength"],
        "organization_alias_candidate_strength": organization_candidates[0]["match_strength"],
        "merge_preview_id": merge_preview["id"], "merge_executed": False,
        "path_queries": [{"path_count": len(item["paths"]), "elapsed_ms": item["elapsed_ms"]} for item in path_queries],
        "connection_candidate_count": len(connection_candidates), "formal_database_modified": False,
        "generated_at": datetime.now().isoformat(),
    }
    required = counts["p3_canonical_relationships"] >= 20 and historical >= 3 and multi_source >= 2 and all(item["path_count"] >= 1 for item in report["path_queries"]) and len(connection_candidates) >= 3
    if not required:
        report["status"] = "failed"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if required else 1


if __name__ == "__main__":
    raise SystemExit(main())
