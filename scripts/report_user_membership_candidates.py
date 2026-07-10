from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.v04c_review import db_connection, default_db_path


def _mask_value(value: str | None, max_len: int = 4) -> str:
    if not value:
        return ""
    value = str(value)
    if len(value) <= max_len:
        return "*" * len(value)
    return value[:max_len] + "*" * (len(value) - max_len)


def main():
    db_path = default_db_path()
    print(f"数据库路径: {db_path}")
    print("=" * 80)
    print(f"{'用户编号':<10} {'用户名':<15} {'会员编号':<12} {'会员姓名':<15} {'匹配依据':<20} {'冲突项':<20} {'风险等级':<10} {'建议':<20}")
    print("-" * 80)
    
    with db_connection(db_path) as conn:
        users = conn.execute("SELECT id,username,display_name,mobile,email FROM v05a_users WHERE status='active'").fetchall()
        
        for user in users:
            user_id, username, display_name, user_mobile, user_email = user
            
            candidates = []
            
            if user_mobile:
                mask_mobile = _mask_value(user_mobile)
                rows = conn.execute(
                    "SELECT id,member_no,name,user_id FROM v04f_club_memberships WHERE status='active' AND mobile=? AND (user_id IS NULL OR user_id=?)",
                    (user_mobile, user_id)
                ).fetchall()
                for row in rows:
                    mid, m_no, m_name, m_user_id = row
                    conflict = "已有其他绑定" if m_user_id and m_user_id != user_id else ""
                    risk = "低" if not conflict else "高"
                    advice = "建议绑定" if not conflict else "需人工确认"
                    candidates.append((mid, m_no, m_name, "手机号匹配", conflict, risk, advice))
            
            if user_email:
                mask_email = _mask_value(user_email)
                rows = conn.execute(
                    "SELECT id,member_no,name,user_id FROM v04f_club_memberships WHERE status='active' AND email=? AND (user_id IS NULL OR user_id=?)",
                    (user_email, user_id)
                ).fetchall()
                for row in rows:
                    mid, m_no, m_name, m_user_id = row
                    exists = any(c[0] == mid for c in candidates)
                    if exists:
                        continue
                    conflict = "已有其他绑定" if m_user_id and m_user_id != user_id else ""
                    risk = "低" if not conflict else "高"
                    advice = "建议绑定" if not conflict else "需人工确认"
                    candidates.append((mid, m_no, m_name, "邮箱匹配", conflict, risk, advice))
            
            if display_name:
                rows = conn.execute(
                    "SELECT id,member_no,name,user_id FROM v04f_club_memberships WHERE status='active' AND name=? AND (user_id IS NULL OR user_id=?)",
                    (display_name, user_id)
                ).fetchall()
                for row in rows:
                    mid, m_no, m_name, m_user_id = row
                    exists = any(c[0] == mid for c in candidates)
                    if exists:
                        continue
                    conflict = "已有其他绑定" if m_user_id and m_user_id != user_id else ""
                    risk = "中" if not conflict else "高"
                    advice = "需人工确认"
                    candidates.append((mid, m_no, m_name, "姓名匹配", conflict, risk, advice))
            
            if not candidates:
                rows = conn.execute(
                    "SELECT id,member_no,name,user_id FROM v04f_club_memberships WHERE status='active' AND user_id=?",
                    (user_id,)
                ).fetchall()
                for row in rows:
                    mid, m_no, m_name, m_user_id = row
                    candidates.append((mid, m_no, m_name, "已绑定", "", "低", "已确认"))
            
            for _, m_no, m_name, match_by, conflict, risk, advice in candidates:
                print(f"{user_id:<10} {username:<15} {m_no:<12} {m_name:<15} {match_by:<20} {conflict:<20} {risk:<10} {advice:<20}")
    
    print("=" * 80)
    print("注意：此报告仅用于参考，不会自动写入数据。")
    print("请管理员根据风险等级和建议进行人工确认后再执行绑定。")


if __name__ == "__main__":
    main()