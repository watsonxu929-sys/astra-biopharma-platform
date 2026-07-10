from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def parser_checks() -> None:
    from app.services.member_import_service import parse_text

    chen = parse_text(
        "本人陈锦辉\n长期深耕创新药领域\n核心工作聚焦于工艺开发（CMC/工艺研究与放大）及部分BD工作"
    )[0]
    check(chen["name"] == "陈锦辉", "陈锦辉姓名去除“本人”")
    check(not chen["organization_name"] and not chen["title"], "陈锦辉案例不猜测机构和职位")
    expertise = chen["expertise_tags"]
    for token in ("创新药", "CMC", "工艺开发", "工艺放大", "BD"):
        check(token in expertise, f"陈锦辉专业能力包含 {token}")
    check("长期深耕创新药领域" in chen["self_introduction"], "陈锦辉个人简介保留原文描述")

    li = parse_text("李明，现任某某生物科技有限公司BD总监，专注创新药商务合作。")[0]
    check(li["name"] == "李明", "显式句首姓名可识别")
    check(li["organization_name"] == "某某生物科技有限公司", "显式任职机构可识别")
    check(li["title"] == "BD总监", "显式职位可识别")
    check("创新药商务合作" in li["expertise_tags"], "专注方向进入专业能力")

    mixed = parse_text("希望对接创新药项目和产业投资机构，可提供CMC工艺开发资源。")[0]
    check("创新药项目" in mixed["cooperation_needs"] and "产业投资机构" in mixed["cooperation_needs"], "需求句进入需求字段")
    check("CMC工艺开发资源" in mixed["offered_resources"], "资源句进入资源字段")

    multi = parse_text("姓名：王一\n公司：甲生物\n\n姓名：赵二\n公司：乙医药")
    check(len(multi) == 2 and multi[0]["name"] == "王一" and multi[1]["name"] == "赵二", "多人 Word 正文可拆分")

    no_name = parse_text("长期深耕创新药领域，希望对接产业投资机构。")[0]
    check(not no_name["name"], "无明确姓名时不编造姓名")
    check(not no_name["organization_name"], "无明确机构时机构留空")

    table = parse_text("陈锦辉\n长期深耕创新药领域\n核心工作聚焦于工艺开发")
    check(table[0]["organization_name"] == "" and table[0]["title"] == "", "无表头连续文本不按行号填机构职位")


def app_checks(work: Path) -> None:
    os.chdir(work)
    os.environ["APP_DB_PATH"] = str(work / "data" / "app.db")
    os.environ["APP_AUTH_DISABLED"] = "1"

    import scripts.apply_v04b as apply_v04b_module

    apply_v04b_module.apply_v04b.__defaults__ = (work / "data" / "app.db",)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.v05c_club_events import ensure_schema
    from app.v04c_review import db_connection

    ensure_schema(work / "data" / "app.db")
    client = TestClient(app)
    check(client.get("/v05c/health").status_code == 200, "v0.5C 健康检查可访问")

    with db_connection(work / "data" / "app.db") as conn:
        ts = "2026-06-30T10:00:00"
        conn.execute(
            """
            INSERT INTO people(
              external_id,name,visibility,verification_status,created_at,manually_confirmed,is_active,subject_manually_confirmed
            ) VALUES ('PER-T-000001','测试会员','internal','已确认',?,1,1,1)
            """,
            (ts,),
        )
        conn.execute(
            """
            INSERT INTO organizations(
              external_id,standard_name,visibility,verification_status,created_at,manually_confirmed,is_active,subject_manually_confirmed
            ) VALUES ('ORG-T-000001','测试生物','internal','已确认',?,1,1,1)
            """,
            (ts,),
        )
        conn.execute(
            """
            INSERT INTO v04f_club_memberships(member_no,person_id,organization_id,member_role,member_level,status,joined_at,source,owner,created_at,updated_at)
            VALUES ('QBM-T-0001',1,1,'BD总监','standard','active',?,'verify','tester',?,?)
            """,
            (ts, ts, ts),
        )
        conn.execute(
            "INSERT INTO v05b_member_contacts(membership_id,mobile,email,created_at,updated_at) VALUES (1,'13800000001','member@example.com',?,?)",
            (ts, ts),
        )

    create = client.post(
        "/club/events/create",
        data={
            "name": "Q-BAY创新药闭门会",
            "event_type": "salon",
            "event_date": "2026-07-01 14:00",
            "venue": "上海",
            "capacity": "50",
            "organizer": "Q-BAY",
            "visibility": "public",
            "description": "创新药合作交流",
        },
        follow_redirects=False,
    )
    check(create.status_code == 303 and "/club/events/" in create.headers["location"], "活动可创建")
    event_url = create.headers["location"]
    club_event_id = int(event_url.rstrip("/").split("/")[-1])
    check(client.get(event_url).status_code == 200, "活动详情可访问")
    check(client.post(f"/club/events/{club_event_id}/status", data={"action": "publish"}, follow_redirects=False).status_code == 303, "活动可发布")
    check(client.post(f"/club/events/{club_event_id}/status", data={"action": "open"}, follow_redirects=False).status_code == 303, "活动可开放报名")

    public_page = client.get(f"/club/events/{club_event_id}/register")
    check(public_page.status_code == 200 and "member@example.com" not in public_page.text and "13800000001" not in public_page.text, "公开报名页不泄露联系方式")

    reg = client.post(
        f"/club/events/{club_event_id}/register",
        data={"applicant_name": "测试会员", "organization_name": "测试生物", "title": "BD总监", "mobile": "13800000001", "email": "member@example.com"},
        follow_redirects=False,
    )
    check(reg.status_code == 303 and "submitted=QBR-" in reg.headers["location"], "公开报名可提交并返回编号")
    duplicate = client.post(
        f"/club/events/{club_event_id}/register",
        data={"applicant_name": "测试会员", "mobile": "13800000001"},
        follow_redirects=False,
    )
    check(duplicate.status_code == 303 and "error=" in duplicate.headers["location"], "重复报名被拦截")

    with sqlite3.connect(work / "data" / "app.db") as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM v05c_club_event_registrations ORDER BY id DESC LIMIT 1").fetchone()
        registration_id = int(row["id"])
        registration_no = row["registration_no"]
        check(row["membership_id"] == 1, "报名可匹配唯一会员但不创建新会员")

    review = client.post(
        f"/club/events/{club_event_id}/registrations/{registration_id}/review",
        data={"status": "approved", "review_note": "ok"},
        follow_redirects=False,
    )
    check(review.status_code == 303, "报名可审核通过")
    checkin = client.post(f"/club/events/{club_event_id}/checkin", data={"identifier": registration_no, "method": "manual"}, follow_redirects=False)
    check(checkin.status_code == 303, "报名编号可手动签到")
    feedback = client.post(
        f"/club/events/{club_event_id}/registrations/{registration_id}/feedback",
        data={"attendance_status": "attended", "satisfaction_score": "5", "feedback": "愿意继续对接", "follow_up_note": "会后跟进"},
        follow_redirects=False,
    )
    check(feedback.status_code == 303, "参与反馈可记录")
    action = client.post(
        f"/club/events/{club_event_id}/followup-action",
        data={"registration_ids": str(registration_id), "task": "跟进创新药合作", "owner": "tester"},
        follow_redirects=False,
    )
    check(action.status_code == 303, "会后可为选中报名创建行动")

    with sqlite3.connect(work / "data" / "app.db") as conn:
        conn.row_factory = sqlite3.Row
        participation = conn.execute("SELECT * FROM v05c_club_event_participation WHERE registration_id=?", (registration_id,)).fetchone()
        activity = conn.execute("SELECT * FROM v05c_member_activity_scores WHERE membership_id=1").fetchone()
        actions = conn.execute("SELECT COUNT(*) FROM actions WHERE source_type='v0.5C Q-BAY活动'").fetchone()[0]
        check(participation and participation["attendance_status"] == "attended", "参与记录已保存")
        check(activity and activity["score"] > 0, "会员活跃度明细已生成")
        check(actions == 1, "会后行动只为人工选中对象创建")

    from app.security import is_public_path, required_permission

    check(is_public_path(f"/club/events/{club_event_id}/register"), "公开报名路由无需登录")
    check(required_permission("/club/events/create", "POST") == "manage_club", "只读角色不能写入活动管理")


def main() -> int:
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="v05c_verify_", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        (work / "data").mkdir(parents=True, exist_ok=True)
        parser_checks()
        app_checks(work)
    os.chdir(original_cwd)
    print("v0.5C verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
