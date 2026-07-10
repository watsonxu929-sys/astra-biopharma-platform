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

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.monitoring_service import (  # noqa: E402
    create_source,
    review_proposal,
    run_source,
)
from app.v04c_review import db_connection  # noqa: E402
from scripts.migrate_v04g import migrate  # noqa: E402


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def create_core_tables(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE organizations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                standard_name TEXT,
                org_type TEXT,
                region TEXT,
                industry_tags TEXT,
                resources TEXT,
                needs TEXT,
                relationship_source TEXT,
                source_url TEXT,
                source_title TEXT,
                source_text TEXT,
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE people(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT,
                public_role TEXT,
                organization_network TEXT,
                ability_tags TEXT,
                value_provided TEXT,
                relationship_source TEXT,
                source_url TEXT,
                source_title TEXT,
                source_text TEXT,
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT,
                project_type TEXT,
                focus_tags TEXT,
                typical_needs TEXT,
                target_actions TEXT,
                status TEXT,
                source_url TEXT,
                source_title TEXT,
                source_text TEXT,
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT,
                event_type TEXT,
                related_entity TEXT,
                fact_summary TEXT,
                system_use TEXT,
                source_url TEXT,
                source_title TEXT,
                source_text TEXT,
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE resources(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                owner_external_id TEXT,
                category TEXT,
                description TEXT,
                region TEXT,
                applicable_to TEXT,
                source_url TEXT,
                source_title TEXT,
                source_text TEXT,
                is_active INTEGER DEFAULT 1
            );
            CREATE TABLE relations(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE);
            CREATE TABLE actions(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE);
            INSERT INTO organizations(external_id, standard_name, org_type, region, industry_tags, needs, is_active)
            VALUES ('ORG-T-001','澄明生物','Biotech','上海','ADC','原始需求',1);
            INSERT INTO people(external_id, name, public_role, organization_network, is_active)
            VALUES ('PER-T-001','张明','研发负责人','澄明生物',1);
            INSERT INTO projects(external_id, name, status, is_active)
            VALUES ('PRJ-T-001','SRC-20260629-0005','立项',1);
            """
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "v04g_verify.db"
        create_core_tables(db_path)
        migrate(db_path, backup=False)
        migrate(db_path, backup=False)
        with db_connection(db_path) as conn:
            table_count = conn.execute("SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v04g_%'").fetchone()["c"]
        check(table_count >= 5, "迁移可重复执行并创建 v04G 表")

        source = create_source(
            "澄明生物新闻页",
            "news",
            "manual:chengming-news",
            "organization",
            "ORG-T-001",
            fetch_mode="manual",
            db_path=db_path,
        )
        duplicate = create_source(
            "澄明生物新闻页重复",
            "news",
            "manual:chengming-news",
            "organization",
            "ORG-T-001",
            fetch_mode="manual",
            db_path=db_path,
        )
        check(source["id"] == duplicate["id"], "同一 URL 和同一主体不会重复创建有效监测源")

        text1 = "澄明生物宣布推进 ADC 管线，并计划开展合作。该页面为企业新闻内容。"
        first = run_source(source["id"], manual_text=text1, db_path=db_path)
        check(first["status"] in {"success", "partial"} and first["snapshot_id"], "首次执行生成快照")
        same = run_source(source["id"], manual_text=text1, db_path=db_path)
        check(same["status"] == "unchanged" and same["created_proposal_count"] == 0, "相同内容再次执行标记 unchanged 且不重复建议")

        text2 = text1 + "\n澄明生物完成新一轮融资，并在上海扩建研发平台。"
        changed = run_source(source["id"], manual_text=text2, db_path=db_path)
        check(changed["status"] in {"success", "partial"}, "内容变化后生成新执行结果")
        with db_connection(db_path) as conn:
            snapshots = conn.execute("SELECT COUNT(*) AS c FROM v04g_source_snapshots WHERE monitoring_source_id=?", (source["id"],)).fetchone()["c"]
            proposals = conn.execute("SELECT * FROM v04g_update_proposals WHERE monitoring_source_id=? ORDER BY id", (source["id"],)).fetchall()
            org = conn.execute("SELECT needs FROM organizations WHERE external_id='ORG-T-001'").fetchone()
        check(snapshots == 2, "不同内容保存两版快照")
        check(any(p["proposal_type"] == "field_update" for p in proposals), "内容变化可生成字段级更新建议")
        check(org["needs"] == "原始需求", "更新建议不会自动修改主体")

        rejected_id = proposals[0]["id"]
        review_proposal(rejected_id, "rejected", "tester", note="测试拒绝", db_path=db_path)
        with db_connection(db_path) as conn:
            org = conn.execute("SELECT needs FROM organizations WHERE external_id='ORG-T-001'").fetchone()
        check(org["needs"] == "原始需求", "拒绝建议不修改主体")

        approved = next(p for p in proposals if p["proposal_type"] == "field_update" and p["field_name"] in {"needs", "industry_tags"})
        result = review_proposal(approved["id"], "approved", "tester", final_value="融资合作需求已确认", note="测试批准", db_path=db_path)
        check(result["applied"] is True, "批准字段级建议后写入白名单字段")
        again = review_proposal(approved["id"], "approved", "tester", final_value="融资合作需求已确认", db_path=db_path)
        check(again.get("idempotent") is True, "重复批准保持幂等")
        with db_connection(db_path) as conn:
            log = conn.execute("SELECT * FROM v04g_update_apply_logs WHERE proposal_id=?", (approved["id"],)).fetchone()
        check(log and log["old_value"] is not None and log["new_value"] == "融资合作需求已确认", "旧值和新值均保留")

        people_source = create_source("团队页", "team_page", "manual:team", "person", "PER-T-001", fetch_mode="manual", db_path=db_path)
        multi = run_source(people_source["id"], manual_text="管理团队\n张明 博士 CEO\n李华 博士 CFO\n王强 博士 CTO", db_path=db_path)
        with db_connection(db_path) as conn:
            person = conn.execute("SELECT public_role FROM people WHERE external_id='PER-T-001'").fetchone()
            multi_prop = conn.execute("SELECT * FROM v04g_update_proposals WHERE monitoring_source_id=? ORDER BY id DESC LIMIT 1", (people_source["id"],)).fetchone()
        check(multi["status"] == "partial" and multi_prop["proposal_type"] == "multi_subject_review", "多主体页面不自动写入单一主体")
        check(person["public_role"] == "研发负责人", "多主体保护未覆盖人物字段")

        bad = create_source("失败源", "other_web", "manual:bad", "", "", fetch_mode="manual", db_path=db_path)
        failed = run_source(bad["id"], manual_text="太短", db_path=db_path)
        check(failed["status"] == "failed", "单个失败来源被记录为 failed")
        with db_connection(db_path) as conn:
            failures = conn.execute("SELECT consecutive_failures FROM v04g_monitoring_sources WHERE id=?", (bad["id"],)).fetchone()["consecutive_failures"]
            conn.execute("UPDATE v04g_monitoring_sources SET is_enabled=0 WHERE id=?", (bad["id"],))
        check(failures == 1, "连续失败次数正确增加")
        skipped = run_source(bad["id"], db_path=db_path)
        check(skipped["status"] == "skipped", "禁用来源执行时会跳过")

        try:
            create_source("非法类型", "news", "manual:bad-type", "illegal", "1", fetch_mode="manual", db_path=db_path)
            raise AssertionError("非法主体类型未拦截")
        except ValueError:
            print("[PASS] 非法主体类型不会导致 500")

        client = TestClient(app)
        for url in ["/v04g/health", "/intelligence/monitoring", "/intelligence/monitoring/sources", "/intelligence/monitoring/runs", "/intelligence/monitoring/proposals"]:
            response = client.get(url)
            check(response.status_code == 200, f"页面/健康检查可访问：{url}")

    print("v0.4G verification completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
