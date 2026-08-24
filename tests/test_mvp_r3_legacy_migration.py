from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from scripts.migrations import mvp_r3_legacy_to_canonical as migration


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _database(tmp_path: Path) -> Path:
    db_path = (tmp_path / "r3_test.db").resolve()
    assert db_path != migration.FORMAL_DB
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE people(id INTEGER PRIMARY KEY,external_id TEXT UNIQUE,name TEXT,is_active INTEGER DEFAULT 1);
        CREATE TABLE organizations(id INTEGER PRIMARY KEY,external_id TEXT UNIQUE,standard_name TEXT,is_active INTEGER DEFAULT 1);
        CREATE TABLE projects(id INTEGER PRIMARY KEY,external_id TEXT UNIQUE,name TEXT,is_active INTEGER DEFAULT 1);
        CREATE TABLE p3_relationship_type_registry(
          relationship_type TEXT PRIMARY KEY,is_symmetric INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE relations(
          id INTEGER PRIMARY KEY,external_id TEXT,source_external_id TEXT,relation_type TEXT,target_external_id TEXT,
          period TEXT,evidence_source TEXT,visibility TEXT,verification_status TEXT,created_at TEXT,source_url TEXT,
          source_type TEXT,source_title TEXT,source_text TEXT,captured_at TEXT,is_active INTEGER DEFAULT 1
        );
        CREATE TABLE p3_canonical_relationships(
          id INTEGER PRIMARY KEY,relationship_no TEXT NOT NULL,subject_type TEXT NOT NULL,subject_id TEXT NOT NULL,
          relationship_type TEXT NOT NULL,object_type TEXT NOT NULL,object_id TEXT NOT NULL,direction TEXT NOT NULL,
          valid_from TEXT,valid_to TEXT,is_current INTEGER NOT NULL,confidence INTEGER NOT NULL,review_status TEXT NOT NULL,
          evidence_status TEXT NOT NULL,source_count INTEGER NOT NULL,visibility TEXT NOT NULL,legacy_relation_id INTEGER,
          is_pilot INTEGER NOT NULL DEFAULT 0,created_by TEXT NOT NULL,reviewed_by TEXT,reviewed_at TEXT,review_note TEXT,
          created_at TEXT NOT NULL,updated_at TEXT NOT NULL,confidence_level TEXT NOT NULL DEFAULT 'pending_verification'
        );
        CREATE TABLE p3_relationship_evidence(
          id INTEGER PRIMARY KEY,relationship_id INTEGER NOT NULL,evidence_text TEXT NOT NULL,locator_json TEXT NOT NULL,
          source_url TEXT,source_date TEXT,evidence_strength TEXT NOT NULL,evidence_hash TEXT NOT NULL,created_at TEXT NOT NULL
        );
        CREATE TABLE resources(
          id INTEGER PRIMARY KEY,external_id TEXT,owner_external_id TEXT,category TEXT,description TEXT,region TEXT,
          applicable_to TEXT,visibility TEXT,verification_status TEXT,created_at TEXT,is_active INTEGER DEFAULT 1
        );
        CREATE TABLE v04f_club_memberships(
          id INTEGER PRIMARY KEY,person_id INTEGER,organization_id INTEGER,user_id INTEGER,status TEXT
        );
        CREATE TABLE v04f_club_needs(
          id INTEGER PRIMARY KEY,membership_id INTEGER,title TEXT,description TEXT,need_type TEXT,industry_tags TEXT,
          region TEXT,urgency TEXT,status TEXT,created_at TEXT
        );
        CREATE TABLE v04f_club_offerings(
          id INTEGER PRIMARY KEY,membership_id INTEGER,title TEXT,description TEXT,offering_type TEXT,industry_tags TEXT,
          region TEXT,availability TEXT,status TEXT,created_at TEXT
        );
        CREATE TABLE v06_market_resources(
          id INTEGER PRIMARY KEY,title TEXT NOT NULL,direction TEXT NOT NULL,resource_type TEXT NOT NULL,category TEXT,
          summary TEXT,description TEXT,publisher_id INTEGER NOT NULL,organization_id INTEGER,owner_person_id INTEGER,
          region TEXT,industry_direction TEXT,tags TEXT,cooperation_terms TEXT,contact_visibility TEXT,status TEXT,
          is_demo INTEGER,visibility TEXT,legacy_source_type TEXT,legacy_source_id TEXT,created_at TEXT,updated_at TEXT
        );
        INSERT INTO people VALUES(1,'PER-1','甲',1);
        INSERT INTO organizations VALUES(1,'ORG-1','乙机构',1);
        INSERT INTO p3_relationship_type_registry VALUES('employed_by',0,1);
        INSERT INTO relations VALUES(
          1,'OLD-REL-1','PER-1','任职','ORG-1',NULL,'官网任职信息','内部','已确认','2026-01-01',
          'https://example.invalid/team','公开网页','管理团队','甲任职于乙机构','2026-01-01',1
        );
        INSERT INTO relations VALUES(
          2,'OLD-REL-2','PER-MISSING','任职','ORG-1',NULL,'待核','内部','待核验','2026-01-02',
          NULL,NULL,NULL,NULL,NULL,1
        );
        INSERT INTO resources VALUES(
          1,'OLD-RES-1','ORG-1','实验平台','共享实验平台','上海','生物医药','内部','已确认','2026-01-01',1
        );
        INSERT INTO v04f_club_memberships VALUES(1,1,1,0,'active');
        INSERT INTO v04f_club_needs VALUES(1,1,'需要融资','A轮融资','融资','创新药','上海','high','active','2026-01-02');
        INSERT INTO v04f_club_offerings VALUES(1,1,'提供实验服务','药效实验','实验服务','创新药','上海','available','active','2026-01-03');
        """
    )
    conn.commit()
    conn.close()
    return db_path


def _run(db_path: Path, apply: bool):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        result = migration.run(conn, apply=apply)
        if apply:
            conn.commit()
        return result
    finally:
        conn.close()


def test_dry_run_does_not_modify_database(tmp_path: Path):
    db_path = _database(tmp_path)
    before = _hash(db_path)
    result = _run(db_path, apply=False)
    assert result["stats"] == {
        "created": 4, "duplicate_created": 0, "duplicates": 0, "manual_review": 1,
        "relationship_created": 1, "resource_created": 3,
        "match_created": 0, "opportunity_created": 0, "follow_up_created": 0, "task_created": 0,
        "foreign_key_subject_missing": 1, "unresolved": 1,
    }
    assert _hash(db_path) == before


def test_migration_is_idempotent_and_preserves_relationship_evidence(tmp_path: Path):
    db_path = _database(tmp_path)
    first = _run(db_path, apply=True)
    second = _run(db_path, apply=True)
    assert first["stats"]["created"] == 4
    assert second["stats"]["created"] == 0
    assert second["stats"]["duplicate_created"] == 0
    assert second["stats"]["duplicates"] == 4
    with sqlite3.connect(db_path) as conn:
        relationship = conn.execute(
            "SELECT relationship_type,subject_id,object_id,review_status,legacy_relation_id FROM p3_canonical_relationships"
        ).fetchone()
        assert relationship == ("employed_by", "PER-1", "ORG-1", "approved", 1)
        assert conn.execute("SELECT COUNT(*) FROM p3_relationship_evidence").fetchone()[0] == 1
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"



def test_relationship_semantic_duplicate_is_not_created(tmp_path: Path):
    db_path = _database(tmp_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO p3_canonical_relationships(
               id,relationship_no,subject_type,subject_id,relationship_type,object_type,object_id,direction,
               is_current,confidence,review_status,evidence_status,source_count,visibility,legacy_relation_id,
               is_pilot,created_by,created_at,updated_at,confidence_level)
               VALUES(99,'REL-EXISTING','person','PER-1','employed_by','organization','ORG-1','directed',
               1,90,'approved','manual_unverified',0,'internal',NULL,0,'existing','2026-01-01','2026-01-01','verified')"""
        )
        conn.commit()
    result = _run(db_path, apply=True)
    assert result["stats"]["relationship_created"] == 0
    assert result["stats"]["duplicates"] == 1
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM p3_canonical_relationships").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM p3_relationship_evidence WHERE relationship_id=99").fetchone()[0] == 1

def test_resource_need_and_offering_use_canonical_directions(tmp_path: Path):
    db_path = _database(tmp_path)
    _run(db_path, apply=True)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT legacy_source_type,direction,title FROM v06_market_resources ORDER BY legacy_source_type"
        ).fetchall()
    assert ("resources", "supply", "实验平台") in rows
    assert ("v04f_club_needs", "demand", "需要融资") in rows
    assert ("v04f_club_offerings", "supply", "提供实验服务") in rows


def test_formal_product_read_contract_is_canonical_only():
    root = Path(__file__).resolve().parents[1]
    checks = {
        "app/api/v1/relationships.py": ("FROM relations",),
        "app/services/api_subject_service.py": ("FROM relations", "FROM actions"),
        "app/services/club_operations_service.py": ("FROM actions",),
        "app/services/dashboard_service.py": ("FROM actions", "v04f_lead_records"),
        "app/p5_collaboration.py": ("v04f_lead_records",),
        "app/services/business_collaboration_service.py": ("v04f_lead_records",),
        "app/services/relationship_path_service.py": ("FROM relations",),
        "app/services/unified_resource_service.py": ("v04f_club_needs", "v04f_club_offerings", "legacy_resources("),
        "app/v05c_club_events.py": ("SELECT COUNT(*) FROM v04f_club_needs", "SELECT COUNT(*) FROM v04f_club_offerings", "FROM actions"),
        "app/v05d_member_portal.py": ("FROM v04f_club_matches", "JOIN v04f_club_needs", "JOIN v04f_club_offerings"),
    }
    for relative, forbidden in checks.items():
        source = (root / relative).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{relative} still contains product Legacy read: {token}"
