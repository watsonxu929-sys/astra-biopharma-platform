from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.canonical_relationship_service import RelationshipNetworkService

REQUIRED_TABLES = {
    "p3_product_assets", "p3_entity_aliases", "p3_entity_external_identifiers",
    "p3_entity_resolution_candidates", "p3_entity_redirects", "p3_entity_merge_records",
    "p3_relationship_type_registry", "p3_canonical_relationships", "p3_relationship_evidence",
    "p3_relationship_candidates", "p3_relationship_audit", "p3_connection_candidates",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P3 on an isolated pilot database")
    parser.add_argument("--db", type=Path, default=Path(r"C:\tmp\p3_entity_network_pilot.db"))
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    db = args.db.resolve()
    if not db.exists():
        print(json.dumps({"status": "failed", "error": "database_not_found", "database": str(db)}, ensure_ascii=False))
        return 2
    checks: dict[str, object] = {}
    failures: list[str] = []
    path_seed = None
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        checks["missing_tables"] = sorted(REQUIRED_TABLES - tables)
        checks["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if checks["missing_tables"]:
            failures.append("missing_tables")
        if checks["integrity_check"] != "ok":
            failures.append("integrity_check")
        if not checks["missing_tables"]:
            checks["relationship_type_count"] = conn.execute("SELECT COUNT(*) FROM p3_relationship_type_registry WHERE active=1").fetchone()[0]
            checks["relationship_categories"] = sorted(row[0] for row in conn.execute("SELECT DISTINCT category FROM p3_relationship_type_registry"))
            if int(checks["relationship_type_count"]) < 40 or len(checks["relationship_categories"]) != 5:
                failures.append("relationship_type_registry")
            invariants = {
                "orphan_relationship_evidence": "SELECT COUNT(*) FROM p3_relationship_evidence e LEFT JOIN p3_canonical_relationships r ON r.id=e.relationship_id WHERE r.id IS NULL",
                "invalid_periods": "SELECT COUNT(*) FROM p3_canonical_relationships WHERE valid_from IS NOT NULL AND valid_to IS NOT NULL AND date(valid_from)>date(valid_to)",
                "sensitive_identifiers": "SELECT COUNT(*) FROM p3_entity_external_identifiers WHERE is_sensitive<>0",
            }
            for key, sql in invariants.items():
                checks[key] = conn.execute(sql).fetchone()[0]
            redirects = {(row["entity_type"], row["source_entity_id"]): row["target_entity_id"] for row in conn.execute("SELECT * FROM p3_entity_redirects WHERE status='active'")}
            cycles = 0
            for start in redirects:
                seen, current = set(), start
                while current in redirects:
                    if current in seen:
                        cycles += 1
                        break
                    seen.add(current)
                    current = (current[0], redirects[current])
            checks["redirect_cycles"] = cycles
            if any(int(checks[key]) for key in (*invariants, "redirect_cycles")):
                failures.append("data_invariants")
            batch = args.batch_id
            if not batch:
                row = conn.execute("SELECT pilot_batch_id FROM p3_canonical_relationships WHERE is_pilot=1 AND pilot_batch_id IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
                batch = str(row[0]) if row else ""
            checks["pilot_batch_id"] = batch
            if batch:
                pilot = {
                    "products": conn.execute("SELECT COUNT(*) FROM p3_product_assets WHERE pilot_batch_id=?", (batch,)).fetchone()[0],
                    "relationships": conn.execute("SELECT COUNT(*) FROM p3_canonical_relationships WHERE pilot_batch_id=?", (batch,)).fetchone()[0],
                    "historical": conn.execute("SELECT COUNT(*) FROM p3_canonical_relationships WHERE pilot_batch_id=? AND is_current=0", (batch,)).fetchone()[0],
                    "multi_source": conn.execute("SELECT COUNT(*) FROM p3_canonical_relationships WHERE pilot_batch_id=? AND source_count>=2", (batch,)).fetchone()[0],
                    "resolution_candidates": conn.execute("SELECT COUNT(*) FROM p3_entity_resolution_candidates WHERE pilot_batch_id=?", (batch,)).fetchone()[0],
                    "connection_candidates": conn.execute("SELECT COUNT(*) FROM p3_connection_candidates WHERE pilot_batch_id=?", (batch,)).fetchone()[0],
                }
                checks["pilot"] = pilot
                if not (5 <= pilot["products"] <= 10 and 20 <= pilot["relationships"] <= 40 and pilot["historical"] >= 3 and pilot["multi_source"] >= 2 and pilot["resolution_candidates"] >= 2 and pilot["connection_candidates"] >= 3):
                    failures.append("pilot_ranges")
                path_seed = conn.execute("SELECT source_person_id,recommended_person_id FROM p3_connection_candidates WHERE pilot_batch_id=? ORDER BY id LIMIT 1", (batch,)).fetchone()
    if path_seed:
        result = RelationshipNetworkService(db).find_paths("person", path_seed[0], "person", path_seed[1], max_depth=3)
        checks["path_check"] = {"path_count": len(result["paths"]), "elapsed_ms": result["elapsed_ms"], "max_depth": result["limits"]["max_depth"], "truncated": result["truncated"]}
        if not result["paths"] or result["elapsed_ms"] > 1000 or result["limits"]["max_depth"] > 3:
            failures.append("path_engine")
    report = {"status": "passed" if not failures else "failed", "database": str(db), "checks": checks, "failures": failures}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
