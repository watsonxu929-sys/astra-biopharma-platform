from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_AUTH_DISABLED", "1")

from fastapi.testclient import TestClient

from app.i18n import translate_status, translate_type
from app.main import app
from app.services.research import add_topic_subject, approve_assessment, compare_companies, convert_assessment_to_lead, create_company_compare_report, create_topic, create_topic_report, generate_assessment, refresh_topic, topic_dashboard, topic_network, topic_timeline, tracks
from app.v04c_review import db_connection
from scripts.migrate_v05j import migrate


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def seed_core(db_path: Path) -> None:
    with db_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS organizations(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, standard_name TEXT, org_type TEXT, region TEXT, industry_tags TEXT, verification_status TEXT, is_active INTEGER DEFAULT 1, created_at TEXT);
            CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, name TEXT, ability_tags TEXT, verification_status TEXT, is_active INTEGER DEFAULT 1, created_at TEXT);
            CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, name TEXT, focus_tags TEXT, status TEXT, owner_external_id TEXT, owner_organization_id INTEGER, is_active INTEGER DEFAULT 1, created_at TEXT);
            CREATE TABLE IF NOT EXISTS resources(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, name TEXT, owner_external_id TEXT, owner_organization_id INTEGER, is_active INTEGER DEFAULT 1, created_at TEXT);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, event_date TEXT, name TEXT, event_type TEXT, related_entity TEXT, related_organization_id INTEGER, fact_summary TEXT, verification_status TEXT, is_active INTEGER DEFAULT 1, created_at TEXT);
            CREATE TABLE IF NOT EXISTS relations(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, source_external_id TEXT, relation_type TEXT, target_external_id TEXT, verification_status TEXT, is_active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS actions(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, target_external_id TEXT, task TEXT, status TEXT, is_active INTEGER DEFAULT 1);
            """
        )
        conn.execute("INSERT INTO organizations(external_id,standard_name,org_type,region,industry_tags,verification_status,is_active,created_at) VALUES ('ORG-J-001','Alpha Bio','早期研发','上海','细胞与基因治疗;创新药','confirmed',1,'2026-07-01')")
        conn.execute("INSERT INTO organizations(external_id,standard_name,org_type,region,industry_tags,verification_status,is_active,created_at) VALUES ('ORG-J-002','Beta Therapeutics','产业化','杭州钱塘','细胞与基因治疗','confirmed',1,'2026-07-01')")
        conn.execute("INSERT INTO events(external_id,event_date,name,event_type,related_entity,fact_summary,verification_status,is_active,created_at) VALUES ('EVT-J-001','2026-06-10','Alpha Bio 完成融资','融资','ORG-J-001','公开披露融资事件','confirmed',1,'2026-06-10')")
        conn.execute("INSERT INTO events(external_id,event_date,name,event_type,related_entity,fact_summary,verification_status,is_active,created_at) VALUES ('EVT-J-002','2026-06-20','Beta Therapeutics 落地园区','园区落地','ORG-J-002','公开披露园区落地','confirmed',1,'2026-06-20')")
        conn.execute("INSERT INTO relations(external_id,source_external_id,relation_type,target_external_id,verification_status,is_active) VALUES ('REL-J-001','ORG-J-001','合作','ORG-J-002','confirmed',1)")
        conn.execute("INSERT INTO v05e_industry_signals(signal_no,signal_type,signal_level,title,summary,subject_type,subject_id,occurred_at,discovered_at,source_type,source_id,evidence_excerpt,confidence,status,is_read,created_at,updated_at) VALUES ('SIG-J-001','financing','high','Alpha Bio 融资信号','融资后可能存在扩张窗口','organization','ORG-J-001','2026-06-10','2026-06-10','event','EVT-J-001','融资公开信息',80,'new',0,'2026-06-10','2026-06-10')")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="verify_v05j_") as tmp:
        db_path = Path(tmp) / "app.db"
        migrate(db_path, backup=False)
        migrate(db_path, backup=False)
        seed_core(db_path)

        check(translate_status("waiting_review") == "等待人工审核", "中文状态映射可用")
        check(translate_type("organization") == "企业/机构", "中文类型映射可用")
        check(translate_status("not_a_real_value") == "未知", "未知值安全回退")

        topic = create_topic(name="细胞与基因治疗", topic_type="track", track_tags="细胞与基因治疗", db_path=db_path)
        add_topic_subject(topic["id"], "organization", "ORG-J-001", reason="人工验收加入", db_path=db_path)
        add_topic_subject(topic["id"], "organization", "ORG-J-001", reason="重复加入", db_path=db_path)
        metrics = refresh_topic(topic["id"], db_path=db_path)
        check(metrics["counts"]["subjects"] == 1 and metrics["counts"]["events"] >= 1, "专题可加入企业并刷新统计且不重复")
        timeline = topic_timeline(topic["id"], db_path=db_path)
        network = topic_network(topic["id"], db_path=db_path)
        check(timeline["data"] and network["edges"], "专题时间线和关系网络复用正式数据")
        with db_connection(db_path) as conn:
            snapshots = conn.execute("SELECT COUNT(*) FROM research_snapshots WHERE topic_id=?", (topic["id"],)).fetchone()[0]
        check(snapshots == 1, "专题快照只保存统计和引用")

        compare = compare_companies(["ORG-J-001", "ORG-J-002"], db_path=db_path)
        check(len(compare["companies"]) == 2 and "notes" in compare and "scores" in compare["companies"][0], "企业对比支持2家企业和独立维度评分")
        check(any("未披露" in note or "无公开信息" in note for note in compare["notes"]), "企业对比不把未知解释为没有")
        topic_report = create_topic_report(topic["id"], created_by="verify", db_path=db_path)
        compare_report = create_company_compare_report(["ORG-J-001", "ORG-J-002"], created_by="verify", db_path=db_path)
        check(topic_report["status"] == "draft" and compare_report["status"] == "draft", "专题和企业对比可生成现有报告草稿")
        track_rows = tracks(db_path=db_path)
        check(track_rows["data"], "赛道分析使用真实主体聚合")

        a1 = generate_assessment("ORG-J-002", db_path=db_path)
        check(a1["grade"] == "R", "本地资源型输出R")
        with db_connection(db_path) as conn:
            conn.execute("INSERT INTO organizations(external_id,standard_name,verification_status,is_active,created_at) VALUES ('ORG-J-003','Unknown Bio','confirmed',1,'2026-07-01')")
        a2 = generate_assessment("ORG-J-003", db_path=db_path)
        check(a2["grade"] == "UNVERIFIED", "信息不足输出UNVERIFIED")
        before_leads = _count(db_path, "v04f_lead_records")
        approved = approve_assessment(a1["id"], actor="verify", db_path=db_path)
        converted = convert_assessment_to_lead(a1["id"], actor="verify", db_path=db_path)
        after_leads = _count(db_path, "v04f_lead_records")
        actions = _count(db_path, "actions")
        check(approved["status"] == "approved" and after_leads == before_leads + 1 and actions == 0, "批准后可转线索且不自动创建行动")

    client = TestClient(app)
    for path in ["/research", "/research/topics", "/research/topics/new", "/research/companies/compare", "/research/tracks", "/research/investment", "/v05j/health", "/api/v1/research/topics", "/api/v1/research/tracks", "/api/v1/investment-assessments"]:
        response = client.get(path)
        check(response.status_code == 200, f"{path} returns 200")
    api = client.get("/api/v1/research/topics").json()
    check("data" in api, "API keeps stable English machine fields")
    print("v0.5J verification completed")
    return 0


def _count(db_path: Path, table: str) -> int:
    with db_connection(db_path) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            return 0
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


if __name__ == "__main__":
    raise SystemExit(main())
