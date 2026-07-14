import os
import sys
from pathlib import Path
import random

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["DATABASE_URL"] = "sqlite:///data/acceptance/t5_1_mvp.db"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.services.business_collaboration_service import BusinessCollaborationService

engine = create_engine("sqlite:///data/acceptance/t5_1_mvp.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

PILOT_BATCH_ID = "T5-1-WRITE-CLOSURE"
ACTOR_USER_ID = 1


def create_denied_lead():
    print("创建已否决线索...")
    unique_id = str(random.randint(100000, 999999))
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.create_lead({
            "title": "测试线索2 - 低质量线索（已否决）",
            "source_type": "manual",
            "subject_type": "organization",
            "subject_id": unique_id,
            "demand_organization_id": int(unique_id),
            "supply_organization_id": int(unique_id) + 1,
            "recommendation_reason": "线索质量低，信息不全",
            "owner_user_id": ACTOR_USER_ID,
            "priority": "P3",
            "suggested_next_action": "重新核实信息",
            "pilot_batch_id": PILOT_BATCH_ID,
        }, actor_user_id=ACTOR_USER_ID)
        lead_id = result["id"]
        svc.review_lead(lead_id, decision="disqualified", actor_user_id=ACTOR_USER_ID, reason="信息不足，无法评估")
        print(f"   线索ID: {lead_id}, 状态: rejected")
        return lead_id


def add_second_follow_up(opportunity_id):
    print("添加第二条跟进记录...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.add_follow_up(opportunity_id, {
            "follow_type": "meeting",
            "content": "双方高层会面，讨论合作细节和时间表",
            "result": "positive",
            "next_action": "准备正式合作方案",
            "next_follow_at": "2026-07-27T10:00:00",
        }, actor_user_id=ACTOR_USER_ID)
        print(f"   跟进ID: {result.get('id')}")
        return result["id"]


def create_overdue_task(opportunity_id):
    print("创建超期任务（用于风险检测）...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.create_task(opportunity_id, {
            "title": "超期任务 - 市场调研报告",
            "owner_id": ACTOR_USER_ID,
            "priority": "P2",
            "due_date": "2026-06-01T18:00:00",
            "completion_criteria": "完成市场调研报告",
        }, actor_user_id=ACTOR_USER_ID)
        print(f"   任务ID: {result.get('id')}, 状态: {result.get('status')}, 截止日期已过期")
        return result["id"]


def add_stage_history(opportunity_id):
    print("添加阶段变化记录...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.update_stage(opportunity_id, stage="matching", actor_user_id=ACTOR_USER_ID, reason="进入匹配阶段")
        print(f"   机会ID: {opportunity_id}, 当前阶段: {result['opportunity']['stage']}")
        return result


def verify_data():
    print("\n验证验收数据...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        leads = svc.db.execute(text("SELECT id, lifecycle_status FROM v04f_lead_records WHERE pilot_batch_id = :batch"), {"batch": PILOT_BATCH_ID}).fetchall()
        opportunities = svc.db.execute(text("SELECT id, stage FROM v06_opportunities WHERE pilot_batch_id = :batch"), {"batch": PILOT_BATCH_ID}).fetchall()
        followups = svc.db.execute(text("SELECT id FROM v06_follow_ups WHERE pilot_batch_id = :batch"), {"batch": PILOT_BATCH_ID}).fetchall()
        tasks = svc.db.execute(text("SELECT id, status FROM v06_collab_tasks WHERE pilot_batch_id = :batch"), {"batch": PILOT_BATCH_ID}).fetchall()
        meetings = svc.db.execute(text("SELECT id, status FROM p5_opportunity_meetings WHERE pilot_batch_id = :batch"), {"batch": PILOT_BATCH_ID}).fetchall()
        artifacts = svc.db.execute(text("SELECT id FROM p5_opportunity_artifacts WHERE pilot_batch_id = :batch"), {"batch": PILOT_BATCH_ID}).fetchall()
        participants = svc.db.execute(text("SELECT id FROM p5_opportunity_participants WHERE pilot_batch_id = :batch"), {"batch": PILOT_BATCH_ID}).fetchall()
        stage_history = svc.db.execute(text("SELECT id FROM p5_opportunity_stage_history")).fetchall()
        
        print(f"  线索数: {len(leads)} (状态: {[l[1] for l in leads]})")
        print(f"  机会数: {len(opportunities)}")
        print(f"  跟进数: {len(followups)}")
        print(f"  任务数: {len(tasks)}")
        print(f"  会议数: {len(meetings)}")
        print(f"  材料数: {len(artifacts)}")
        print(f"  参与方数: {len(participants)}")
        print(f"  阶段历史数: {len(stage_history)}")
        
        risks = svc.calculate_risks(pilot_batch_id=PILOT_BATCH_ID)
        print(f"  风险数: {len(risks)}")


def main():
    print("=" * 60)
    print("创建额外验收数据")
    print("=" * 60)
    
    create_denied_lead()
    add_second_follow_up(16)
    create_overdue_task(16)
    add_stage_history(16)
    
    verify_data()
    
    print("\n" + "=" * 60)
    print("数据创建完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
