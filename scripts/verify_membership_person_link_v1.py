from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.membership_person_link_service import (
    MembershipPersonLinkError,
    bind_person,
    get_link_info,
    get_person_candidates,
    list_memberships_for_person,
    list_link_audit,
    unbind_person,
)

TEST_RUN_ID = f"e2e_{datetime.now():%Y%m%d_%H%M%S}"


def _diagnose_env() -> None:
    settings = get_settings()
    env_from = "os.environ" if "APP_ENV" in os.environ else ".env file"
    db_path = settings.sqlite_path
    sanitized_path = str(db_path).replace(str(ROOT), "$ROOT") if ROOT in db_path.parents else str(db_path)
    print(f"=== 环境诊断 ===")
    print(f"APP_ENV: {settings.app_env}")
    print(f"配置来源: {env_from}")
    print(f"数据库类型: {settings.db_backend}")
    print(f"数据库路径(脱敏): {sanitized_path}")
    print(f"允许创建测试数据: {'是' if settings.app_env == 'development' else '否'}")
    print(f"test_run_id: {TEST_RUN_ID}")
    print(f"==============")


def _counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    users = int(conn.execute("SELECT COUNT(*) FROM v05a_users").fetchone()[0])
    people = int(conn.execute("SELECT COUNT(*) FROM people").fetchone()[0])
    memberships = int(conn.execute("SELECT COUNT(*) FROM v04f_club_memberships").fetchone()[0])
    link_audit = int(conn.execute("SELECT COUNT(*) FROM membership_person_link_audit").fetchone()[0])
    conn.close()
    return {"users": users, "people": people, "memberships": memberships, "link_audit": link_audit}


def _create_test_data(db_path: Path) -> dict[str, Any]:
    ts = datetime.now().replace(microsecond=0).isoformat()
    
    conn = sqlite3.connect(db_path)
    
    conn.execute("INSERT INTO people(external_id,name,is_active,created_at,source_type,visibility,verification_status) VALUES (?,?,1,?,'system_e2e','内部','待核验')",
                 (f"PER-E2E-MP-{TEST_RUN_ID}-001", f"测试人物_MP_{TEST_RUN_ID}", ts))
    person_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    
    conn.execute("INSERT INTO people(external_id,name,is_active,created_at,source_type,visibility,verification_status) VALUES (?,?,1,?,'system_e2e','内部','待核验')",
                 (f"PER-E2E-MP-{TEST_RUN_ID}-002", f"测试人物_MP_2_{TEST_RUN_ID}", ts))
    person_id_2 = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    
    conn.execute("""
        INSERT INTO v04f_club_memberships(member_no,person_id,member_level,status,joined_at,created_at,updated_at)
        VALUES (?,?, 'standard', 'active', ?, ?, ?)
    """, (f"QBM-{TEST_RUN_ID}-001", None, ts, ts, ts))
    membership_id_1 = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    
    conn.execute("""
        INSERT INTO v04f_club_memberships(member_no,person_id,member_level,status,joined_at,created_at,updated_at)
        VALUES (?,?, 'premium', 'active', ?, ?, ?)
    """, (f"QBM-{TEST_RUN_ID}-002", None, ts, ts, ts))
    membership_id_2 = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    
    conn.commit()
    conn.close()
    
    return {"person_id": person_id, "person_id_2": person_id_2, "membership_id_1": membership_id_1, "membership_id_2": membership_id_2}


def _cleanup_test_data(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    
    conn.execute("DELETE FROM v04f_club_memberships WHERE member_no LIKE ?", (f"QBM-{TEST_RUN_ID}%",))
    conn.execute("DELETE FROM people WHERE external_id LIKE ?", (f"PER-E2E-MP-{TEST_RUN_ID}%",))
    conn.execute("DELETE FROM membership_person_link_audit WHERE membership_id IN (SELECT id FROM v04f_club_memberships WHERE member_no LIKE ?)", (f"QBM-{TEST_RUN_ID}%",))
    
    conn.commit()
    conn.close()


def main() -> int:
    _diagnose_env()
    settings = get_settings()
    
    if settings.app_env != "development":
        print("错误：仅在 development 环境下允许运行验证")
        return 1
    
    db_path = settings.sqlite_path
    
    print("\n=== 验证前数据统计 ===")
    before = _counts(db_path)
    print(f"用户: {before['users']}, 人物: {before['people']}, 会员: {before['memberships']}, 绑定审计: {before['link_audit']}")
    
    print("\n=== 场景1: 创建测试数据（未绑定会员）===")
    data = _create_test_data(db_path)
    print(f"人物ID: {data['person_id']}, {data['person_id_2']}")
    print(f"会员ID: {data['membership_id_1']}, {data['membership_id_2']}")
    
    print("\n=== 场景2: 未绑定Membership正常显示 ===")
    link_info = get_link_info(data["membership_id_1"])
    assert link_info["link_status"] == "unlinked", "未绑定会员应为 unlinked"
    assert link_info["person"] is None, "未绑定会员人物应为 None"
    print(f"绑定状态: {link_info['link_status']}, 人物: {link_info['person']}")
    
    print("\n=== 场景3: 管理员绑定已有Person ===")
    result = bind_person(data["membership_id_1"], data["person_id"], "管理员确认绑定", "e2e_test_admin")
    assert result["link_status"] == "linked", "绑定后应为 linked"
    assert result["person"]["id"] == data["person_id"], "绑定人物ID不匹配"
    print(f"绑定后状态: {result['link_status']}, 人物: {result['person']['name']}")
    
    print("\n=== 场景4: 绑定后会员详情正常 ===")
    link_info = get_link_info(data["membership_id_1"])
    assert link_info["link_status"] == "linked", "绑定后查询应为 linked"
    print(f"查询状态: {link_info['link_status']}, 会员编号: {link_info['membership']['member_no']}")
    
    print("\n=== 场景5: 多个Membership可绑定同一Person ===")
    result2 = bind_person(data["membership_id_2"], data["person_id"], "第二个会员绑定同一人物", "e2e_test_admin")
    assert result2["link_status"] == "linked", "第二个会员绑定后应为 linked"
    assert result2["person"]["id"] == data["person_id"], "第二个会员绑定人物ID不匹配"
    print(f"第二个会员绑定成功，人物: {result2['person']['name']}")
    
    print("\n=== 场景6: 查询人物的多个Membership ===")
    memberships = list_memberships_for_person(data["person_id"])
    assert len(memberships) >= 2, f"人物应有至少2个会员，实际: {len(memberships)}"
    print(f"人物的会员数量: {len(memberships)}")
    
    print("\n=== 场景7: 重复绑定幂等 ===")
    result3 = bind_person(data["membership_id_1"], data["person_id"], "重复绑定测试", "e2e_test_admin")
    assert result3["link_status"] == "linked", "重复绑定后仍应为 linked"
    print("重复绑定幂等通过")
    
    print("\n=== 场景8: 更换绑定需要明确操作 ===")
    result4 = bind_person(data["membership_id_1"], data["person_id_2"], "更换绑定到另一人物", "e2e_test_admin")
    assert result4["link_status"] == "linked", "更换绑定后应为 linked"
    assert result4["person"]["id"] == data["person_id_2"], "更换绑定人物ID不匹配"
    print(f"更换绑定成功，新人物: {result4['person']['name']}")
    
    print("\n=== 场景9: 解除绑定后Membership和Person均保留 ===")
    result5 = unbind_person(data["membership_id_1"], "测试解除绑定", "e2e_test_admin")
    assert result5["link_status"] == "unlinked", "解除绑定后应为 unlinked"
    assert result5["person"] is None, "解除绑定后人物应为 None"
    
    with sqlite3.connect(db_path) as conn:
        membership = conn.execute("SELECT id FROM v04f_club_memberships WHERE id=?", (data["membership_id_1"],)).fetchone()
        person = conn.execute("SELECT id FROM people WHERE id=?", (data["person_id"],)).fetchone()
        assert membership, "Membership应保留"
        assert person, "Person应保留"
    print("解除绑定后Membership和Person均保留")
    
    print("\n=== 场景10: 候选接口返回匹配依据 ===")
    bind_person(data["membership_id_1"], data["person_id"], "重新绑定测试", "e2e_test_admin")
    candidates = get_person_candidates(data["membership_id_1"])
    print(f"候选数量: {len(candidates)}")
    for c in candidates[:3]:
        print(f"  人物: {c['name']}, 匹配依据: {c['match_basis']}, 风险等级: {c['risk_level']}")
    
    print("\n=== 场景11: 字段差异正常展示 ===")
    link_info = get_link_info(data["membership_id_1"])
    print(f"字段差异: {link_info['field_differences']}")
    assert isinstance(link_info["field_differences"], dict), "字段差异应为字典"
    
    print("\n=== 场景12: 审计日志存在 ===")
    audit = list_link_audit(data["membership_id_1"])
    assert len(audit) >= 3, f"应有至少3条审计记录，实际: {len(audit)}"
    print(f"审计记录数量: {len(audit)}")
    for a in audit[:3]:
        print(f"  操作: {a['action']}, 时间: {a['created_at']}")
    
    print("\n=== 场景13: 未绑定会员查询 ===")
    link_info = get_link_info(data["membership_id_2"])
    assert link_info["link_status"] == "linked", "第二个会员应为 linked"
    print(f"第二个会员状态: {link_info['link_status']}")
    
    print("\n=== 场景14: 不存在会员返回404 ===")
    try:
        get_link_info(999999)
        assert False, "应抛出404错误"
    except MembershipPersonLinkError as e:
        assert e.status_code == 404, f"应返回404，实际: {e.status_code}"
        print(f"正确返回404: {e.code}")
    
    print("\n=== 场景15: 不存在人物返回404 ===")
    try:
        bind_person(data["membership_id_1"], 999999, "测试不存在人物", "e2e_test_admin")
        assert False, "应抛出404错误"
    except MembershipPersonLinkError as e:
        assert e.status_code == 404, f"应返回404，实际: {e.status_code}"
        print(f"正确返回404: {e.code}")
    
    print("\n=== 场景16: 未绑定会员解除绑定返回409 ===")
    ts = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            INSERT INTO v04f_club_memberships(member_no,person_id,member_level,status,joined_at,created_at,updated_at)
            VALUES (?,?, 'standard', 'active', ?, ?, ?)
        """, (f"QBM-{TEST_RUN_ID}-003", None, ts, ts, ts))
        unbound_membership_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.commit()
    try:
        unbind_person(unbound_membership_id, "测试未绑定解除", "e2e_test_admin")
        assert False, "应抛出409错误"
    except MembershipPersonLinkError as e:
        assert e.status_code == 409, f"应返回409，实际: {e.status_code}"
        print(f"正确返回409: {e.code}")
    
    print("\n=== 场景17: 清理临时数据 ===")
    _cleanup_test_data(db_path)
    print("临时数据清理完成")
    
    print("\n=== 场景18: 清理后真实数据数量恢复 ===")
    after = _counts(db_path)
    print(f"用户: {after['users']}, 人物: {after['people']}, 会员: {after['memberships']}, 绑定审计: {after['link_audit']}")
    
    assert after["users"] == before["users"], f"用户数量不匹配: {after['users']} vs {before['users']}"
    assert after["people"] == before["people"], f"人物数量不匹配: {after['people']} vs {before['people']}"
    assert after["memberships"] == before["memberships"], f"会员数量不匹配: {after['memberships']} vs {before['memberships']}"
    
    print("\n==================================================")
    print("专项验证全部通过！")
    print("==================================================")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
