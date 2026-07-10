from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.membership_person_link_service import get_person_candidates


def _mask_phone(phone: str | None) -> str:
    if not phone:
        return "未填写"
    return phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone


def _mask_email(email: str | None) -> str:
    if not email:
        return "未填写"
    parts = email.split("@")
    return parts[0][:2] + "****@" + parts[1] if len(parts) == 2 else email


def main() -> int:
    settings = get_settings()
    db_path = settings.sqlite_path
    
    print("=== 会员-人物候选匹配报告 ===")
    print(f"数据库路径: {db_path}")
    print(f"生成时间: {__import__('datetime').datetime.now().isoformat()}")
    print("=" * 80)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    unlinked_memberships = conn.execute(
        """
        SELECT m.id, m.member_no, m.member_level, m.status, m.member_role, m.owner, m.joined_at
        FROM v04f_club_memberships m
        WHERE m.person_id IS NULL OR m.person_id = 0
        ORDER BY m.joined_at DESC
        """
    ).fetchall()
    
    total = len(unlinked_memberships)
    print(f"未绑定人物档案的会员总数: {total}")
    print("-" * 80)
    
    stats = {
        "high_confidence": 0,
        "needs_review": 0,
        "no_candidate": 0,
        "multiple_candidates": 0,
    }
    
    for row in unlinked_memberships:
        m = {k: row[k] for k in row.keys()}
        
        contact = conn.execute(
            "SELECT mobile, email FROM v05b_member_contacts WHERE membership_id=?",
            (m["id"],)
        ).fetchone()
        contact = dict(contact) if contact else {}
        
        print(f"\n会员编号: {m['member_no']}")
        print(f"会员等级: {m['member_level']}")
        print(f"会员状态: {m['status']}")
        print(f"会员姓名: {m['member_role'] or '未填写'}")
        print(f"所属机构: {m['owner'] or '未填写'}")
        print(f"入会时间: {m['joined_at']}")
        print(f"手机: {_mask_phone(contact.get('mobile'))}")
        print(f"邮箱: {_mask_email(contact.get('email'))}")
        
        try:
            candidates = get_person_candidates(m["id"])
        except Exception:
            candidates = []
        
        candidate_count = len(candidates)
        print(f"候选人物数量: {candidate_count}")
        
        if candidate_count == 0:
            stats["no_candidate"] += 1
            print("建议: 无候选，请先在人物档案中创建")
        else:
            if candidate_count > 1:
                stats["multiple_candidates"] += 1
            
            for i, c in enumerate(candidates[:3], 1):
                print(f"\n  候选 {i}:")
                print(f"    姓名: {c['name']}")
                print(f"    人物编号: {c['external_id']}")
                print(f"    机构: {c['organization_network'] or '暂无'}")
                print(f"    职位: {c['public_role'] or '暂无'}")
                print(f"    匹配依据: {', '.join(c['match_basis'])}")
                print(f"    匹配分数: {c['match_score']}")
                print(f"    风险等级: {c['risk_label']}")
            
            if candidates and all(c["match_score"] >= 70 for c in candidates):
                stats["high_confidence"] += 1
                print("建议: 高可信候选，可直接关联")
            else:
                stats["needs_review"] += 1
                print("建议: 需要人工核验")
        
        print("-" * 80)
    
    conn.close()
    
    print("\n=== 统计汇总 ===")
    print(f"高可信候选: {stats['high_confidence']}")
    print(f"需要人工核验: {stats['needs_review']}")
    print(f"无候选: {stats['no_candidate']}")
    print(f"多候选冲突: {stats['multiple_candidates']}")
    print(f"总计: {total}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
