from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("APP_AUTH_DISABLED", "1")

# Keep app import and any startup database initialization away from the user's real data/app.db.
TEMP_ROOT = tempfile.TemporaryDirectory(prefix="v04d4_verify_")
os.chdir(TEMP_ROOT.name)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, engine as app_engine, get_db
from app.main import app
from app.models import Organization, Person, Relation
from app.services.suspicious_review import suspicious_records


SAMPLE_TEAM_PAGE = """标题：管理团队 | 药明康德
李革 博士
董事长兼首席执行官
科学家、企业家。李革博士于 2000 年创建药明康德，他开创了开放式研发服务平台。
陈民章 博士
联席首席执行官
拥有二十多年新药研发和生产管理经验。加入药明康德前，担任美国福泰制药公司技术运营总监。
杨青 博士
联席首席执行官
在建立医药研发及服务能力方面经验丰富。加入药明康德之前曾任阿斯利康副总裁。
"""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def main() -> int:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        org = Organization(
            external_id="ORG-20260629-000001",
            standard_name="药明康德",
            org_type="CRO/CDMO",
            region="上海",
            visibility="内部",
            verification_status="已确认",
            is_active=True,
        )
        bad_person = Person(
            external_id="PER-20260629-999999",
            name="管理团队",
            public_role="董事长；总经理；总监",
            visibility="内部",
            verification_status="待核验",
            is_active=True,
        )
        db.add_all([org, bad_person])
        db.commit()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        page = client.get("/manage/people/new")
        check(page.status_code == 200, "人物新增页返回200")
        check('id="batch-organization-reference"' in page.text, "批量核对区包含统一关联机构输入框")
        check('id="batch-create-relations"' in page.text, "批量核对区包含同步创建关系开关")
        check("?v=04d4" in page.text, "前端脚本使用v0.4D-4缓存标记")

        lookup = client.get("/manage/organizations/lookup", params={"q": "药明康德"})
        check(lookup.status_code == 200, "机构匹配接口返回200")
        lookup_data = lookup.json()
        check(lookup_data["count"] == 1, "机构名称唯一匹配")
        check(lookup_data["items"][0]["external_id"] == "ORG-20260629-000001", "机构匹配返回正确系统编号")

        candidates = [
            {
                "label": "李革",
                "subtitle": "董事长兼首席执行官",
                "text": "李革 博士\n董事长兼首席执行官\n科学家、企业家。李革博士于 2000 年创建药明康德。",
            },
            {
                "label": "陈民章",
                "subtitle": "联席首席执行官",
                "text": "陈民章 博士\n联席首席执行官\n拥有二十多年新药研发和生产管理经验。",
            },
        ]
        analyzed_response = client.post(
            "/manage/people/batch-analyze",
            json={
                "candidates": candidates,
                "source_url": "https://example.com/about/leadership",
                "source_title": "管理团队 | 药明康德",
                "organization_hint": "药明康德",
            },
        )
        check(analyzed_response.status_code == 200, "批量人物解析接口返回200")
        analyzed = analyzed_response.json()
        check(analyzed["organization_match"]["external_id"] == "ORG-20260629-000001", "批量解析匹配统一机构")
        check(all(item["fields"]["organization_network"] == "药明康德" for item in analyzed["items"]), "统一机构写入全部人物草稿")

        save_items = []
        for item in analyzed["items"]:
            fields = item["fields"]
            save_items.append({
                "name": fields["name"],
                "public_role": fields["public_role"],
                "organization_network": fields["organization_network"],
                "ability_tags": fields.get("ability_tags", ""),
                "value_provided": fields.get("value_provided", ""),
                "source_url": fields["source_url"],
                "source_title": fields["source_title"],
                "source_text": item["source_text"],
                "allow_duplicate": False,
            })

        saved_response = client.post(
            "/manage/people/batch-save",
            json={
                "confirmed": True,
                "items": save_items,
                "organization_reference": "ORG-20260629-000001",
                "relation_type": "任职",
                "create_relations": True,
            },
        )
        check(saved_response.status_code == 200, "批量人物保存接口返回200")
        saved = saved_response.json()
        check(saved["created_count"] == 2, "成功保存2个人物")
        check(saved["relations_created"] == 2, "同步创建2条人物-机构关系")

        with TestingSession() as db:
            people_count = db.scalar(select(func.count()).select_from(Person).where(Person.name.in_(["李革", "陈民章"]))) or 0
            relation_count = db.scalar(
                select(func.count()).select_from(Relation).where(
                    Relation.target_external_id == "ORG-20260629-000001",
                    Relation.relation_type == "任职",
                )
            ) or 0
            check(people_count == 2, "测试数据库存在2条新人物")
            check(relation_count == 2, "测试数据库存在2条任职关系")

            suspicious = suspicious_records(db)
            check(any(row.title == "管理团队" for row in suspicious), "疑似错误复核规则识别栏目名人物")

        first_person_id = saved["created"][0]["id"]
        person_page = client.get(f"/people/{first_person_id}")
        check(person_page.status_code == 200, "人物详情页返回200")
        check("药明康德" in person_page.text and "任职" in person_page.text, "人物详情显示可点击机构关系")

        organization_page = client.get("/organizations/1")
        check(organization_page.status_code == 200, "机构详情页返回200")
        check("李革" in organization_page.text and "陈民章" in organization_page.text, "机构详情汇总团队人物")

        suspicious_page = client.get("/review/suspicious-entities")
        check(suspicious_page.status_code == 200, "疑似错误主体复核页返回200")
        check("管理团队" in suspicious_page.text, "复核页显示异常人物")

        deactivate = client.post(
            "/review/suspicious-entities/people/1/deactivate",
            data={"reason": "验证脚本人工复核停用"},
            follow_redirects=False,
        )
        check(deactivate.status_code == 303, "单条停用操作返回303")
        with TestingSession() as db:
            bad = db.get(Person, 1)
            check(bad is not None and bad.is_active is False, "异常人物执行软停用而非物理删除")

        duplicate_response = client.post(
            "/manage/people/batch-save",
            json={
                "confirmed": True,
                "items": save_items,
                "organization_reference": "药明康德",
                "relation_type": "任职",
                "create_relations": True,
            },
        )
        duplicate = duplicate_response.json()
        check(duplicate_response.status_code == 200, "重复批次请求正常返回")
        check(duplicate["created_count"] == 0 and duplicate["skipped_count"] == 2, "同名同机构人物按高概率重复跳过")

        print("\nV0.4D-4 人物机构关联与疑似数据复核验证：全部通过。")
        return 0
    finally:
        app.dependency_overrides.clear()
        try:
            client.close()
        except Exception:
            pass
        engine.dispose()
        app_engine.dispose()
        os.chdir(PROJECT_ROOT)
        TEMP_ROOT.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
