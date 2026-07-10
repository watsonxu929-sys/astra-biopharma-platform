from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from app.services.recommendation_service import (  # noqa: E402
    create_action_from_recommendation,
    ensure_schema,
    refresh_recommendations,
    update_decision,
)
from app.services.relationship_path_service import find_qbay_paths  # noqa: E402
from scripts.migrate_v04f import SCHEMA_SQL as V04F_SCHEMA  # noqa: E402
from scripts.migrate_v04h import SCHEMA_SQL as V04H_SCHEMA  # noqa: E402


BASE_SCHEMA = """
CREATE TABLE organizations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, standard_name TEXT,
 org_type TEXT, region TEXT, industry_tags TEXT, resources TEXT, needs TEXT,
 verification_status TEXT DEFAULT '待核验', is_active INTEGER DEFAULT 1, created_at TEXT
);
CREATE TABLE people (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, name TEXT,
 public_role TEXT, organization_network TEXT, ability_tags TEXT, value_provided TEXT,
 verification_status TEXT DEFAULT '待核验', is_active INTEGER DEFAULT 1, created_at TEXT
);
CREATE TABLE projects (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, name TEXT,
 project_type TEXT, owner_external_id TEXT, owner_organization_id INTEGER,
 focus_tags TEXT, typical_needs TEXT, target_actions TEXT, status TEXT,
 is_active INTEGER DEFAULT 1, created_at TEXT
);
CREATE TABLE relations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, source_external_id TEXT,
 relation_type TEXT, target_external_id TEXT, evidence_source TEXT,
 verification_status TEXT DEFAULT '已核验', is_active INTEGER DEFAULT 1, created_at TEXT
);
CREATE TABLE actions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, task TEXT,
 target_external_id TEXT, target_organization_id INTEGER, completion_standard TEXT,
 owner TEXT, priority TEXT, status TEXT, suggested_deadline TEXT, source_url TEXT,
 source_type TEXT, source_title TEXT, source_text TEXT, manually_confirmed INTEGER DEFAULT 0,
 is_active INTEGER DEFAULT 1, created_at TEXT
);
CREATE TABLE v04c_review_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id TEXT, item_type TEXT,
 status TEXT, created_at TEXT
);
"""


def seed(conn: sqlite3.Connection) -> None:
    conn.executescript(BASE_SCHEMA)
    conn.executescript(V04F_SCHEMA)
    conn.executescript(V04H_SCHEMA)
    conn.execute("INSERT INTO organizations(external_id,standard_name,org_type,region,industry_tags,resources,needs,is_active,created_at) VALUES ('ORG-TARGET','目标药企','创新药企业','上海','创新药;临床;融资','','融资;临床资源',1,'2026-06-30')")
    conn.execute("INSERT INTO organizations(external_id,standard_name,org_type,region,industry_tags,resources,needs,is_active,created_at) VALUES ('ORG-QBAY','Q-BAY','产业平台','上海','园区;投资;临床','园区;投资资源','',1,'2026-06-30')")
    conn.execute("INSERT INTO people(external_id,name,public_role,organization_network,ability_tags,value_provided,is_active,created_at) VALUES ('PER-CONTACT','王顾问','投资负责人','Q-BAY','融资;投资','投资机构资源',1,'2026-06-30')")
    conn.execute("INSERT INTO people(external_id,name,public_role,organization_network,ability_tags,value_provided,is_active,created_at) VALUES ('PER-NEED','李需求','创始人','目标药企','创新药','寻找融资',1,'2026-06-30')")
    conn.execute("INSERT INTO relations(external_id,source_external_id,relation_type,target_external_id,is_active,created_at) VALUES ('REL-1','PER-CONTACT','任职','ORG-QBAY',1,'2026-06-30')")
    conn.execute("INSERT INTO relations(external_id,source_external_id,relation_type,target_external_id,is_active,created_at) VALUES ('REL-2','ORG-TARGET','合作','ORG-QBAY',1,'2026-06-30')")
    conn.execute("INSERT INTO v04f_lead_records(lead_no,subject_type,subject_id,funnel_stage,system_score,system_grade,scoring_json,owner,status,created_at,updated_at) VALUES ('LED-TEST','organization','ORG-TARGET','待联系',72,'A',?, 'Watson','active','2026-06-30','2026-06-30')", (json.dumps({'positive_reasons':['属于重点创新药赛道。'],'negative_reasons':[],'missing_data':['近期事件']}, ensure_ascii=False),))
    conn.execute("INSERT INTO v04f_club_memberships(member_no,person_id,organization_id,member_level,status,joined_at,industry_tags,expertise_tags,cooperation_preferences,created_at,updated_at) VALUES ('MEM-1',1,2,'core','active','2026-06-30','投资;创新药','融资','寻找优质项目','2026-06-30','2026-06-30')")
    conn.execute("INSERT INTO v04f_club_memberships(member_no,person_id,organization_id,member_level,status,joined_at,industry_tags,expertise_tags,cooperation_preferences,created_at,updated_at) VALUES ('MEM-2',2,1,'standard','active','2026-06-30','创新药;临床','研发','融资需求','2026-06-30','2026-06-30')")
    conn.execute("INSERT INTO v04f_club_needs(need_no,membership_id,title,description,need_type,industry_tags,region,urgency,status,created_at,updated_at) VALUES ('N-1',2,'寻找融资与投资机构','创新药项目寻求融资','融资','创新药;融资','上海','high','active','2026-06-30','2026-06-30')")
    conn.execute("INSERT INTO v04f_club_offerings(offering_no,membership_id,title,description,offering_type,industry_tags,region,availability,status,created_at,updated_at) VALUES ('O-1',1,'投资机构与融资对接','可提供创新药投资机构资源','融资','创新药;融资','上海','available','active','2026-06-30','2026-06-30')")
    conn.execute("INSERT INTO v04c_review_items(subject_id,item_type,status,created_at) VALUES ('ORG-TARGET','conflict','pending','2026-06-30')")
    conn.commit()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v04h_verify_") as temp:
        db_path = Path(temp) / "test.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        seed(conn)
        conn.close()

        ensure_schema(db_path)
        result = refresh_recommendations(db_path, lead_limit=20, pair_limit=100)
        check(result["candidate_count"] >= 4, "generated multiple recommendation categories")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM v04h_recommendations ORDER BY id").fetchall()
        categories = {row["category"] for row in rows}
        check({"lead", "club_match", "resource", "data_quality", "relationship"}.issubset(categories), "all v0.4H categories generated")
        check(all(0 <= row["score"] <= 100 for row in rows), "all scores are in 0-100")
        check(all(json.loads(row["reasons_json"] or "[]") for row in rows), "recommendations contain explanations")

        paths = find_qbay_paths(conn, "organization", "ORG-TARGET", max_edges=3, max_paths=20)["paths"]
        check(bool(paths), "real Q-BAY relationship path found")
        check(all(path["edge_count"] <= 3 for path in paths), "paths are limited to three edges")
        check(all(len({node["external_id"] for node in path["nodes"]}) == len(path["nodes"]) for path in paths), "paths contain no cycles")
        before = conn.execute("SELECT COUNT(*) FROM v04h_recommendations").fetchone()[0]
        conn.close()

        refresh_recommendations(db_path, lead_limit=20, pair_limit=100)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        after = conn.execute("SELECT COUNT(*) FROM v04h_recommendations").fetchone()[0]
        check(before == after, "refresh is idempotent")

        lead_rec = conn.execute("SELECT id FROM v04h_recommendations WHERE category='lead' LIMIT 1").fetchone()
        rec_id = int(lead_rec["id"])
        conn.close()
        update_decision(rec_id, "accepted", actor="tester", reason="人工确认", db_path=db_path)
        action_result = create_action_from_recommendation(rec_id, owner="tester", db_path=db_path)
        check(action_result["created"] is True, "accepted recommendation converts to action")
        duplicate_action = create_action_from_recommendation(rec_id, owner="tester", db_path=db_path)
        check(duplicate_action["created"] is False, "action conversion is idempotent")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        status = conn.execute("SELECT status,action_id FROM v04h_recommendations WHERE id=?", (rec_id,)).fetchone()
        feedback_count = conn.execute("SELECT COUNT(*) FROM v04h_feedback_events WHERE recommendation_id=?", (rec_id,)).fetchone()[0]
        check(status["status"] == "converted" and status["action_id"], "recommendation status tracks action conversion")
        check(feedback_count >= 2, "feedback history is retained")
        conn.close()

        # Router smoke test with the isolated database.
        os.environ["APP_DB_PATH"] = str(db_path)
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from fastapi.testclient import TestClient
        from app.v04h_recommendations import router

        app = FastAPI()
        app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")
        app.include_router(router)
        client = TestClient(app)
        check(client.get("/v04h/health").status_code == 200, "v0.4H health route returns 200")
        check(client.get("/recommendations").status_code == 200, "recommendation center returns 200")
        check(client.get(f"/recommendations/{rec_id}").status_code == 200, "recommendation detail returns 200")
        check(client.get("/recommendations/path?subject_type=organization&subject_id=ORG-TARGET").status_code == 200, "relationship path page returns 200")

    print("v0.4H verification PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
