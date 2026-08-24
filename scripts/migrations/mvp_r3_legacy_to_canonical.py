from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FORMAL_DB = (ROOT / "data" / "app.db").resolve()
MIGRATION_ACTOR = "mvp_r3_legacy_migration"

# These are documented historical identifiers from the 2026-06-26 seed.  They
# point to the same retained subjects; no name-based or fuzzy matching is used.
ENDPOINT_ALIASES = {
    "PER-2026-000001": "PER-20260626-000001",
    "PER-2026-000002": "PER-20260626-000002",
    "PER-GROUP-001": "PER-20260626-000003",
    "ORG-2026-000001": "ORG-20260626-000001",
    "ORG-2026-000002": "ORG-20260626-000002",
    "ORG-2026-000003": "ORG-20260626-000003",
    "ORG-2026-000004": "ORG-20260626-000004",
    "ORG-2026-000005": "ORG-20260626-000005",
    "ORG-2026-000006": "ORG-20260626-000006",
    "ORG-2026-000008": "ORG-20260626-000008",
}

RELATIONSHIP_TYPES = {
    "运营/负责": "executive_of",
    "联合发起/项目负责": "cofounder_of",
    "驻沪招商代表": "contact_for",
    "沪杭协同/项目输送": "strategic_partner_of",
    "产业载体关联": "located_in_park",
    "历史任职/资源来源": "formerly_employed_by",
    "服务与链接": "contact_for",
    "分会/隶属": "member_organization_of",
    "任职": "employed_by",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _endpoint(conn: sqlite3.Connection, external_id: str) -> dict[str, Any] | None:
    canonical_id = ENDPOINT_ALIASES.get(external_id, external_id)
    for subject_type, table in (("person", "people"), ("organization", "organizations"), ("project", "projects")):
        row = conn.execute(
            f'SELECT id,external_id FROM "{table}" WHERE external_id=?', (canonical_id,)
        ).fetchone()
        if row:
            return {"type": subject_type, "external_id": row["external_id"], "row_id": int(row["id"])}
    return None


def _visibility(value: str | None) -> str:
    return "public" if value in {"公开", "public"} else "internal"


def _period(value: str | None) -> tuple[str | None, str | None, int]:
    text = (value or "").strip()
    if len(text) == 9 and text[4] == "-" and text[:4].isdigit() and text[5:].isdigit():
        return f"{text[:4]}-01-01", f"{text[5:]}-12-31", 0
    return None, None, 1


def _review(value: str | None) -> tuple[str, int, str]:
    if value == "已确认":
        return "approved", 90, "confirmed"
    if value == "历史对话明确":
        return "approved", 85, "confirmed"
    if value == "部分待核":
        return "pending_review", 55, "pending_verification"
    return "pending_review", 60, "pending_verification"


def _evidence(row: sqlite3.Row) -> dict[str, Any] | None:
    evidence_text = (row["source_text"] or row["evidence_source"] or "").strip()
    if not evidence_text:
        return None
    payload = {
        "evidence_text": evidence_text,
        "source_url": row["source_url"],
        "source_date": str(row["captured_at"] or row["created_at"] or "")[:10] or None,
        "locator_json": json.dumps(
            {"source_type": row["source_type"], "source_title": row["source_title"]},
            ensure_ascii=False,
            sort_keys=True,
        ),
    }
    payload["evidence_hash"] = hashlib.sha256(
        "|".join(str(payload.get(key) or "") for key in ("evidence_text", "source_url", "source_date")).encode("utf-8")
    ).hexdigest()
    return payload


def _relationship_no(row_id: int) -> str:
    token = hashlib.sha256(f"relations:{row_id}".encode("ascii")).hexdigest()[:12].upper()
    return f"REL-{token}"


def _relationship_plan(conn: sqlite3.Connection, apply: bool) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    if not _table(conn, "relations"):
        return mappings
    for row in conn.execute("SELECT * FROM relations WHERE COALESCE(is_active,1)=1 ORDER BY id"):
        subject = _endpoint(conn, row["source_external_id"])
        target = _endpoint(conn, row["target_external_id"])
        relation_type = RELATIONSHIP_TYPES.get(row["relation_type"])
        if not subject or not target or not relation_type:
            reason = "missing_endpoint" if not subject or not target else "unmapped_relationship_type"
            mappings.append(_mapping("relations", row["id"], "p3_canonical_relationships", None, "MANUAL_REVIEW", reason))
            continue
        type_row = conn.execute(
            "SELECT is_symmetric FROM p3_relationship_type_registry WHERE relationship_type=? AND active=1",
            (relation_type,),
        ).fetchone()
        if not type_row:
            mappings.append(_mapping("relations", row["id"], "p3_canonical_relationships", None, "MANUAL_REVIEW", "type_not_registered"))
            continue
        direction = "symmetric" if type_row["is_symmetric"] else "directed"
        existing = conn.execute(
            """SELECT id,legacy_relation_id FROM p3_canonical_relationships
               WHERE legacy_relation_id=? OR
                 (subject_type=? AND subject_id=? AND relationship_type=? AND object_type=? AND object_id=?
                  AND direction=? AND review_status<>'archived')
               ORDER BY CASE WHEN legacy_relation_id=? THEN 0 ELSE 1 END,id LIMIT 1""",
            (row["id"], subject["type"], subject["external_id"], relation_type,
             target["type"], target["external_id"], direction, row["id"]),
        ).fetchone()
        canonical_id = int(existing["id"]) if existing else None
        action = ("ALREADY_MIGRATED" if existing and existing["legacy_relation_id"] == row["id"] else "DUPLICATE_SKIP") if existing else "MIGRATE"
        if apply and not existing:
            valid_from, valid_to, is_current = _period(row["period"])
            review_status, confidence, confidence_level = _review(row["verification_status"])
            evidence = _evidence(row)
            now = str(row["created_at"] or datetime.now().replace(microsecond=0).isoformat())
            result = conn.execute(
                """INSERT INTO p3_canonical_relationships(
                   relationship_no,subject_type,subject_id,relationship_type,object_type,object_id,direction,
                   valid_from,valid_to,is_current,confidence,review_status,evidence_status,source_count,visibility,
                   legacy_relation_id,is_pilot,created_by,reviewed_by,reviewed_at,review_note,created_at,updated_at,
                   confidence_level)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?,?,?,?)""",
                (_relationship_no(row["id"]), subject["type"], subject["external_id"], relation_type,
                 target["type"], target["external_id"], direction, valid_from, valid_to, is_current,
                 confidence, review_status, "evidence_backed" if evidence else "manual_unverified",
                 1 if evidence else 0, _visibility(row["visibility"]), row["id"], MIGRATION_ACTOR,
                 MIGRATION_ACTOR if review_status == "approved" else None,
                 now if review_status == "approved" else None,
                 f"原关系类型：{row['relation_type']}；原核验状态：{row['verification_status']}；原期间：{row['period'] or '未记录'}",
                 now, now, confidence_level),
            )
            canonical_id = int(result.lastrowid)
        evidence = _evidence(row)
        if apply and canonical_id and evidence:
            found = conn.execute(
                "SELECT id FROM p3_relationship_evidence WHERE relationship_id=? AND evidence_hash=?",
                (canonical_id, evidence["evidence_hash"]),
            ).fetchone()
            if not found:
                conn.execute(
                    """INSERT INTO p3_relationship_evidence(
                       relationship_id,evidence_text,locator_json,source_url,source_date,evidence_strength,evidence_hash,created_at)
                       VALUES (?,?,?,?,?,'supporting',?,?)""",
                    (canonical_id, evidence["evidence_text"], evidence["locator_json"], evidence["source_url"],
                     evidence["source_date"], evidence["evidence_hash"], str(row["created_at"])),
                )
        mappings.append(_mapping("relations", row["id"], "p3_canonical_relationships", canonical_id, action, "semantic_and_endpoint_match"))
    return mappings


def _resource_owner(conn: sqlite3.Connection, row: sqlite3.Row, table: str) -> dict[str, Any] | None:
    if table == "resources":
        return _endpoint(conn, row["owner_external_id"])
    membership = conn.execute(
        "SELECT person_id,organization_id,user_id FROM v04f_club_memberships WHERE id=?", (row["membership_id"],)
    ).fetchone()
    if not membership:
        return None
    return {"type": "membership", "person_id": membership["person_id"], "organization_id": membership["organization_id"], "user_id": membership["user_id"]}


def _resource_fields(row: sqlite3.Row, table: str, direction: str, owner: dict[str, Any]) -> dict[str, Any]:
    if table == "resources":
        title = (row["category"] or row["description"] or f"历史资源 {row['id']}").strip()
        return {
            "title": title, "direction": direction, "resource_type": row["category"] or "其他",
            "category": row["category"], "summary": row["description"], "description": row["description"],
            "publisher_id": 0, "owner_person_id": owner["row_id"] if owner["type"] == "person" else None,
            "organization_id": owner["row_id"] if owner["type"] == "organization" else None,
            "region": row["region"], "industry_direction": row["applicable_to"], "tags": row["applicable_to"],
            "status": "published", "visibility": _visibility(row["visibility"]), "created_at": str(row["created_at"]),
        }
    is_need = table == "v04f_club_needs"
    kind = row["need_type"] if is_need else row["offering_type"]
    terms = row["urgency"] if is_need else row["availability"]
    return {
        "title": row["title"], "direction": direction, "resource_type": kind or "其他", "category": kind,
        "summary": row["description"], "description": row["description"], "publisher_id": int(owner["user_id"] or 0),
        "owner_person_id": owner["person_id"], "organization_id": owner["organization_id"], "region": row["region"],
        "industry_direction": row["industry_tags"], "tags": row["industry_tags"], "cooperation_terms": terms,
        "status": "published" if row["status"] == "active" else "archived", "visibility": "organization",
        "created_at": str(row["created_at"]),
    }


def _resource_plan(conn: sqlite3.Connection, apply: bool) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for table, direction in (("resources", "supply"), ("v04f_club_needs", "demand"), ("v04f_club_offerings", "supply")):
        if not _table(conn, table):
            continue
        for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY id'):
            owner = _resource_owner(conn, row, table)
            if not owner:
                mappings.append(_mapping(table, row["id"], "v06_market_resources", None, "MANUAL_REVIEW", "missing_owner"))
                continue
            fields = _resource_fields(row, table, direction, owner)
            existing = conn.execute(
                """SELECT id,legacy_source_type,legacy_source_id FROM v06_market_resources WHERE
                   (legacy_source_type=? AND legacy_source_id=? AND direction=?) OR
                   (direction=? AND trim(title)=trim(?) AND COALESCE(organization_id,-1)=COALESCE(?,-1)
                    AND COALESCE(owner_person_id,-1)=COALESCE(?,-1) AND COALESCE(category,'')=COALESCE(?,'')
                    AND trim(COALESCE(description,summary,''))=trim(COALESCE(?,'')))
                   ORDER BY CASE WHEN legacy_source_type=? AND legacy_source_id=? THEN 0 ELSE 1 END,id LIMIT 1""",
                (table, str(row["id"]), direction, direction, fields["title"], fields["organization_id"],
                 fields["owner_person_id"], fields["category"], fields["description"], table, str(row["id"])),
            ).fetchone()
            canonical_id = int(existing["id"]) if existing else None
            action = ("ALREADY_MIGRATED" if existing and existing["legacy_source_type"] == table and str(existing["legacy_source_id"]) == str(row["id"]) else "DUPLICATE_SKIP") if existing else "MIGRATE"
            if apply and not existing:
                result = conn.execute(
                    """INSERT INTO v06_market_resources(
                       title,direction,resource_type,category,summary,description,publisher_id,organization_id,
                       owner_person_id,region,industry_direction,tags,cooperation_terms,contact_visibility,status,
                       is_demo,visibility,legacy_source_type,legacy_source_id,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'connected',?,0,?,?,?,?,?)""",
                    (fields["title"], direction, fields["resource_type"], fields["category"], fields["summary"],
                     fields["description"], fields["publisher_id"], fields["organization_id"], fields["owner_person_id"],
                     fields["region"], fields["industry_direction"], fields["tags"], fields.get("cooperation_terms"),
                     fields["status"], fields["visibility"], table, str(row["id"]), fields["created_at"], fields["created_at"]),
                )
                canonical_id = int(result.lastrowid)
            mappings.append(_mapping(table, row["id"], "v06_market_resources", canonical_id, action, "semantic_owner_direction_match"))
    return mappings


def _mapping(legacy_table: str, legacy_id: int, canonical_table: str, canonical_id: int | None, action: str, reason: str) -> dict[str, Any]:
    return {
        "legacy_table": legacy_table, "legacy_id": int(legacy_id), "canonical_table": canonical_table,
        "canonical_id": canonical_id, "migration_action": action,
        "duplicate_of": canonical_id if action == "DUPLICATE_SKIP" else None,
        "status": "already_migrated" if action == "ALREADY_MIGRATED" else ("resolved" if action != "MANUAL_REVIEW" else "manual_review"), "reason": reason,
    }


def run(conn: sqlite3.Connection, *, apply: bool) -> dict[str, Any]:
    relationships = _relationship_plan(conn, apply)
    resources = _resource_plan(conn, apply)
    all_rows = relationships + resources
    return {
        "relationships": relationships,
        "resources": resources,
        "stats": {
            "created": sum(row["migration_action"] == "MIGRATE" for row in all_rows),
            "duplicate_created": 0,
            "duplicates": sum(row["migration_action"] in {"DUPLICATE_SKIP", "ALREADY_MIGRATED"} for row in all_rows),
            "manual_review": sum(row["migration_action"] == "MANUAL_REVIEW" for row in all_rows),
            "relationship_created": sum(row["migration_action"] == "MIGRATE" for row in relationships),
            "resource_created": sum(row["migration_action"] == "MIGRATE" for row in resources),
            "match_created": 0, "opportunity_created": 0, "follow_up_created": 0, "task_created": 0,
            "foreign_key_subject_missing": sum(row["reason"] in {"missing_endpoint", "missing_owner"} for row in all_rows),
            "unresolved": sum(row["migration_action"] == "MANUAL_REVIEW" for row in all_rows),
        },
    }


def _backup(db_path: Path) -> tuple[Path, str]:
    backup_dir = db_path.parent / "migration_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"pre_mvp_r3_{datetime.now():%Y%m%d_%H%M%S}.db"
    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    with sqlite3.connect(f"file:{backup.as_posix()}?mode=ro", uri=True) as check:
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        backup.unlink(missing_ok=True)
        raise RuntimeError(f"backup integrity_check failed: {integrity}")
    return backup, sha256(backup)


def _write_evidence(directory: Path, result: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in (("RELATIONSHIP", result["relationships"]), ("RESOURCE", result["resources"])):
        path = directory / f"MVP_R3_{name}_MAPPING.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(_mapping("", 0, "", None, "", "").keys()))
            writer.writeheader(); writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="MVP-R3 one-time Legacy to Canonical migration")
    parser.add_argument("--db-path", type=Path, default=FORMAL_DB)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-db", type=Path)
    parser.add_argument("--allow-formal-db", action="store_true")
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    db_path = args.db_path.resolve()
    if not db_path.is_file():
        raise SystemExit(f"database not found: {db_path}")
    before_hash = sha256(db_path)
    if args.apply:
        if not args.confirm_db or args.confirm_db.resolve() != db_path:
            raise SystemExit("--apply requires --confirm-db with the exact target database path")
        if db_path == FORMAL_DB and not args.allow_formal_db:
            raise SystemExit("formal database requires --allow-formal-db")
    uri = f"file:{db_path.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as preview_conn:
        preview_conn.row_factory = sqlite3.Row
        preview = run(preview_conn, apply=False)
    backup_path = backup_hash = None
    result = preview
    if args.apply and preview["stats"]["created"]:
        backup_path, backup_hash = _backup(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            result = run(conn, apply=True)
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"post-migration integrity_check failed: {integrity}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    if args.apply:
        with sqlite3.connect(db_path) as checkpoint:
            checkpoint.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    if args.evidence_dir:
        _write_evidence(args.evidence_dir.resolve(), result)
    output = {
        "mode": "apply" if args.apply else "dry-run", "db_path": str(db_path), "formal_db": db_path == FORMAL_DB,
        "before_sha256": before_hash,
        "backup_path": str(backup_path) if backup_path else None, "backup_sha256": backup_hash,
        "stats": result["stats"],
    }
    if args.apply:
        output["after_sha256"] = sha256(db_path)
        with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as check:
            output["integrity_check"] = check.execute("PRAGMA integrity_check").fetchone()[0]
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
