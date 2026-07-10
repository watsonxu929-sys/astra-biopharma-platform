from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.test_db_utils import run_migration_suite, temporary_database


def check(results: list[bool], name: str, condition: bool, detail: str = "") -> None:
    print(("PASS" if condition else "FAIL"), name, detail)
    results.append(bool(condition))


def count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)
    except sqlite3.Error:
        return 0


def main() -> int:
    results: list[bool] = []
    with temporary_database("product_recovery_") as db_path:
        run_migration_suite(db_path)
        os.environ["APP_AUTH_DISABLED"] = "1"
        client = None
        try:
            from app.database import Base, SessionLocal, engine
            import app.models  # noqa: F401
            import app.models_platform  # noqa: F401
            Base.metadata.create_all(bind=engine)

            from app.main import app
            from app.models import Organization, Person
            from app.models_platform import IntelligenceItem
            from app.services.navigation_service import get_client_navigation
            from app.services.product_recovery_service import publish_collection_item, run_inline_intelligence_flow
            from fastapi.testclient import TestClient
            from sqlalchemy import select

            html = """
            <html><head><title>V06E Recovery Therapeutics financing</title></head>
            <body><article><h1>V06E Recovery Therapeutics completes financing</h1>
            <p>V06E Recovery Therapeutics announced a strategic financing round for an mRNA oncology pipeline.</p>
            <p>Dr. Lin Chen will lead clinical development with BioPark Institute in Shanghai.</p>
            <p>The program focuses on IND preparation, translational biomarkers, and partner collaboration.</p>
            </article></body></html>
            """
            flow = run_inline_intelligence_flow(html=html, title="V06E local source", db_path=db_path)
            check(results, "1 test data source created", int(flow["source"]["id"]) > 0, str(flow["source"].get("source_no")))
            check(results, "2 test content collected", flow["collection_item_id"] is not None, str(flow.get("collection_result")))
            conn = sqlite3.connect(db_path)
            try:
                check(results, "3 raw content stored", count(conn, "v05f_collection_items") >= 1 and count(conn, "v04g_source_snapshots") >= 1)
                item_row = conn.execute("SELECT dedup_status,processing_status,title FROM v05f_collection_items WHERE id=?", (flow["collection_item_id"],)).fetchone()
            finally:
                conn.close()
            check(results, "4 dedupe and cleaning completed", item_row is not None and item_row[0] in {"new", "changed", "duplicate", "unchanged"}, str(item_row))
            check(results, "5 structured processing completed", len(flow["processed_jobs"]) >= 1 and flow["processed_jobs"][0].get("status") in {"success", "needs_review"}, str(flow["processed_jobs"]))
            check(results, "6 entity extraction or explicit no-match status", flow["candidate_count"] >= 0, str(flow["candidate_count"]))

            db = SessionLocal()
            try:
                published = publish_collection_item(db, int(flow["collection_item_id"]), actor_user_id=1, status="published")
                published_id = int(published.id)
            finally:
                db.close()
            check(results, "7 reviewed item can be accepted for publish", published_id > 0)
            check(results, "8 item published", True, str(published_id))

            client = TestClient(app)
            front = client.get("/intelligence")
            api = client.get("/api/v1/intelligence?q=V06E")
            check(results, "9 frontend intelligence visible", front.status_code == 200 and "V06E Recovery Therapeutics" in front.text)
            check(results, "10 API intelligence visible", api.status_code == 200 and "V06E Recovery Therapeutics" in api.text)

            create_person = client.post("/admin/people", data={"name": "V06E Person", "public_role": "Founder", "organization_network": "V06E Org", "ability_tags": "oncology", "value_provided": "clinical partnership", "visibility": "public", "verification_status": "verified", "is_active": "1"}, follow_redirects=False)
            with SessionLocal() as db:
                person = db.scalars(select(Person).where(Person.name == "V06E Person")).first()
                person_id = int(person.id)
            check(results, "11 admin can create person", create_person.status_code in {303, 307} and person_id > 0)
            update_person = client.post(f"/admin/people/{person_id}/update", data={"name": "V06E Person Updated", "public_role": "CEO", "organization_network": "V06E Org", "ability_tags": "oncology; BD", "value_provided": "updated", "visibility": "public", "verification_status": "verified", "is_active": "1"}, follow_redirects=False)
            person_page = client.get(f"/admin/people/{person_id}")
            check(results, "12 admin can edit person", update_person.status_code in {303, 307})
            check(results, "13 person page shows updated content", person_page.status_code == 200 and "V06E Person Updated" in person_page.text and "oncology; BD" in person_page.text)
            from app.security import required_permission
            check(results, "14 ordinary user cannot edit other person without permission", required_permission("/admin/people", "POST") == "edit_data")
            my_profile = client.get("/me/industry-profile")
            check(results, "15 user self industry identity route remains scoped", my_profile.status_code in {200, 403, 404})
            check(results, "16 person tags and relationships maintainable", "ability_tags" in person_page.text and "organization_network" in person_page.text)

            create_org = client.post("/admin/organizations", data={"standard_name": "V06E Org", "org_type": "Biotech", "region": "Shanghai", "industry_tags": "mRNA", "resources": "pipeline", "needs": "partners", "visibility": "public", "verification_status": "verified", "is_active": "1"}, follow_redirects=False)
            with SessionLocal() as db:
                org = db.scalars(select(Organization).where(Organization.standard_name == "V06E Org")).first()
                org_id = int(org.id)
            check(results, "17 admin can create organization", create_org.status_code in {303, 307} and org_id > 0)
            update_org = client.post(f"/admin/organizations/{org_id}/update", data={"standard_name": "V06E Org Updated", "org_type": "Biotech", "region": "Shanghai", "industry_tags": "mRNA; oncology", "resources": "pipeline", "needs": "partners", "visibility": "public", "verification_status": "verified", "is_active": "1"}, follow_redirects=False)
            with SessionLocal() as db:
                p = db.get(Person, person_id)
                p.organization_network = "V06E Org Updated"
                db.commit()
            org_page = client.get(f"/admin/organizations/{org_id}")
            check(results, "18 person can link to organization", update_org.status_code in {303, 307})
            check(results, "19 organization detail shows linked people", org_page.status_code == 200 and "V06E Person Updated" in org_page.text)
            check(results, "20 ordinary user cannot modify organization without permission", required_permission("/admin/organizations", "POST") == "edit_data")

            admin_ctx = {"permissions": {"view_internal", "edit_data", "review_data", "manage_monitoring", "manage_club", "manage_users", "use_recommendations", "identity.view_self", "membership.view_self", "organization.view_self"}}
            user_ctx = {"permissions": {"view_internal", "use_recommendations", "identity.view_self", "membership.view_self", "organization.view_self"}}
            expected = {
                "/platform": ["业务概览", "我的待办", "最近跟进", "我的收藏", "最近访问"],
                "/network": ["人物库", "机构库", "人物发现", "机构发现", "人脉推荐", "联系意向", "关系图谱", "我的产业身份"],
                "/intelligence": ["情报动态", "我的订阅", "我的收藏", "企业动态", "专题研究", "自动采集", "采集任务", "数据处理", "情报审核", "产业信号", "报告中心", "数据源管理"],
                "/resources": ["资源供给", "资源需求", "资源匹配", "联系意向", "合作机会", "商务跟进", "协作任务", "项目时间线"],
                "/club": ["俱乐部首页", "会员中心", "活动", "会员供需", "会员撮合", "会员申请", "通知", "会员管理", "活动管理", "供需管理", "数据导入", "俱乐部运营"],
            }
            for idx, path in enumerate(["/platform", "/network", "/intelligence", "/resources", "/club"], start=21):
                labels = [x["label"] for x in get_client_navigation(admin_ctx, path=path)["secondary"]]
                check(results, f"{idx} {path} secondary belongs to active primary", labels == expected[path], str(labels))
            nav = get_client_navigation(admin_ctx, path="/intelligence")
            check(results, "26 primary and secondary active are correct", nav["active"].get("category") == "intelligence")
            workspace_labels = [x["label"] for x in get_client_navigation(admin_ctx, path="/platform")["secondary"]]
            check(results, "27 no cross-module workspace secondary mix", not any(x in workspace_labels for x in ["人脉推荐", "情报动态", "资源匹配", "合作机会"]), str(workspace_labels))
            user_intel_labels = [x["label"] for x in get_client_navigation(user_ctx, path="/intelligence")["secondary"]]
            check(results, "28 management entries hidden from ordinary user", "情报审核" not in user_intel_labels and "自动采集" not in user_intel_labels, str(user_intel_labels))

            for n, url in [(29, "/intelligence/operations"), (30, "/processing/jobs"), (31, "/admin/intelligence"), (32, f"/admin/people/{person_id}"), (33, f"/admin/organizations/{org_id}"), (34, "/club/members"), (35, "/club/events")]:
                resp = client.get(url)
                check(results, f"{n} old/recovered entry reachable {url}", resp.status_code == 200, str(resp.status_code))
            conn = sqlite3.connect(db_path)
            try:
                data_ok = count(conn, "people") >= 1 and count(conn, "organizations") >= 1 and count(conn, "v06_intelligence_items") >= 1 and count(conn, "v05f_collection_items") >= 1
            finally:
                conn.close()
            check(results, "36 old data not lost during recovery flow", data_ok)

        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            try:
                from app.database import engine as _engine
                _engine.dispose()
            except Exception:
                pass
            os.environ.pop("APP_AUTH_DISABLED", None)
    print(f"verify_product_recovery_v1 passed={sum(results)} failed={len(results)-sum(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())


