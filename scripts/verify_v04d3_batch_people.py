from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("APP_AUTH_DISABLED", "1")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Person
from app.services.manual_ingestion import extract_person_candidates

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
        check('id="people-batch-toolbar"' in page.text, "人物新增页包含批量候选工具栏")
        check('id="batch-editor-section"' in page.text, "人物新增页包含批量核对区")
        check("?v=04d3" in page.text or "?v=04d4" in page.text, "批量脚本使用新版缓存标记")

        candidates = extract_person_candidates(SAMPLE_TEAM_PAGE)
        check(len(candidates) == 3, "示例团队页拆出3个人物候选")
        analyze_response = client.post(
            "/manage/people/batch-analyze",
            json={
                "candidates": [item.to_dict() for item in candidates],
                "source_url": "https://example.com/about/leadership",
                "source_title": "管理团队 | 示例公司",
            },
        )
        check(analyze_response.status_code == 200, "批量解析接口返回200")
        analyzed = analyze_response.json()
        check(analyzed["count"] == 3, "批量解析返回3条草稿")
        names = [item["fields"]["name"] for item in analyzed["items"]]
        check(names == ["李革", "陈民章", "杨青"], "批量解析姓名顺序正确")
        check(all(item["fields"]["organization_network"] == "药明康德" for item in analyzed["items"]), "批量解析当前机构正确")

        unconfirmed = client.post(
            "/manage/people/batch-save",
            json={"confirmed": False, "items": []},
        )
        check(unconfirmed.status_code == 400, "未人工确认时禁止批量保存")

        save_items = []
        for item in analyzed["items"][:2]:
            fields = item["fields"]
            save_items.append({
                "name": fields["name"],
                "public_role": fields["public_role"],
                "organization_network": fields["organization_network"],
                "ability_tags": fields["ability_tags"],
                "value_provided": fields["value_provided"],
                "source_url": fields["source_url"],
                "source_title": fields["source_title"],
                "source_text": item["source_text"],
                "allow_duplicate": False,
            })

        saved_response = client.post(
            "/manage/people/batch-save",
            json={"confirmed": True, "items": save_items},
        )
        check(saved_response.status_code == 200, "批量保存接口返回200")
        saved = saved_response.json()
        check(saved["created_count"] == 2, "批量保存成功创建2人")
        check(saved["skipped_count"] == 0, "首次批量保存无跳过")
        check(all(item["external_id"].startswith("PER-") for item in saved["created"]), "人物系统编号正常生成")

        with TestingSession() as db:
            count = db.scalar(select(func.count()).select_from(Person)) or 0
            check(count == 2, "测试数据库实际保存2条人物记录")
            rows = db.scalars(select(Person).order_by(Person.id)).all()
            check(all(row.manually_confirmed for row in rows), "批量记录标记为人工确认")
            check(all(row.model_version in {"local-rule-v0.4D3", "local-rule-v0.4D4"} for row in rows), "批量记录写入规则版本")

        duplicate_response = client.post(
            "/manage/people/batch-save",
            json={"confirmed": True, "items": save_items},
        )
        duplicate = duplicate_response.json()
        check(duplicate_response.status_code == 200, "重复批次请求正常返回")
        check(duplicate["created_count"] == 0, "同名记录默认不重复创建")
        check(duplicate["skipped_count"] == 2, "重复人物全部列入跳过结果")

        invalid_response = client.post(
            "/manage/people/batch-save",
            json={
                "confirmed": True,
                "items": [{"name": "管理团队", "source_text": SAMPLE_TEAM_PAGE}],
            },
        )
        invalid = invalid_response.json()
        check(invalid_response.status_code == 200, "无效主体批量保存返回可读结果")
        check(invalid["created_count"] == 0 and invalid["skipped_count"] == 1, "栏目名不会被保存成人物")

        print("\nV0.4D-3 人物批量采集与保存验证：全部通过。")
        return 0
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    raise SystemExit(main())
