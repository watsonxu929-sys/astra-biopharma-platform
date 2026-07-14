import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["DATABASE_URL"] = "sqlite:///data/acceptance/t5_1_mvp.db"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.services.business_collaboration_service import BusinessCollaborationService

engine = create_engine("sqlite:///data/acceptance/t5_1_mvp.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

PILOT_BATCH_ID = "T5-1-WRITE-CLOSURE"
ACTOR_USER_ID = 1


import random

def test_create_lead():
    print("1. 创建线索...")
    unique_id = str(random.randint(10000, 99999))
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.create_lead({
            "title": "测试线索1 - 药企合作需求",
            "source_type": "manual",
            "subject_type": "organization",
            "subject_id": unique_id,
            "demand_organization_id": int(unique_id),
            "supply_organization_id": int(unique_id) + 1,
            "recommendation_reason": "双方业务高度匹配",
            "owner_user_id": ACTOR_USER_ID,
            "priority": "P1",
            "suggested_next_action": "联系需求方确认意向",
            "pilot_batch_id": PILOT_BATCH_ID,
        }, actor_user_id=ACTOR_USER_ID)
        print(f"   线索ID: {result.get('id')}, 状态: {result.get('lifecycle_status')}")
        return result["id"]


def test_review_lead(lead_id):
    print("2. 审核线索（确认为有效）...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.review_lead(lead_id, decision="qualified", actor_user_id=ACTOR_USER_ID, reason="业务匹配度高")
        print(f"   线索ID: {lead_id}, 状态: {result['lead']['lifecycle_status']}")
        return result


def test_convert_lead(lead_id):
    print("3. 转化为合作机会...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.convert_lead(lead_id, actor_user_id=ACTOR_USER_ID, fields={
            "title": "测试合作机会 - 药企战略合作",
            "opp_type": "collaboration",
            "priority": "P1",
            "next_action": "安排双方高层会面",
        })
        print(f"   机会ID: {result['opportunity']['id']}, 线索状态: {result['lead']['lifecycle_status']}")
        return result["opportunity"]["id"]


def test_add_follow_up(opportunity_id):
    print("4. 添加跟进记录...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.add_follow_up(opportunity_id, {
            "follow_type": "phone",
            "content": "与需求方电话沟通，确认合作意向强烈，预计下周安排会面",
            "result": "positive",
            "next_action": "协调日程安排会面",
            "next_follow_at": "2026-07-20T10:00:00",
        }, actor_user_id=ACTOR_USER_ID)
        print(f"   跟进ID: {result.get('id')}")
        return result["id"]


def test_create_task(opportunity_id):
    print("5. 创建任务...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.create_task(opportunity_id, {
            "title": "准备合作方案初稿",
            "owner_id": ACTOR_USER_ID,
            "priority": "P1",
            "due_date": "2026-07-25T18:00:00",
            "completion_criteria": "完成合作方案初稿，包含合作模式、时间计划、预期收益",
        }, actor_user_id=ACTOR_USER_ID)
        print(f"   任务ID: {result.get('id')}, 状态: {result.get('status')}")
        return result["id"]


def test_update_task(task_id):
    print("6. 更新任务状态...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.update_task(task_id, status="in_progress", actor_user_id=ACTOR_USER_ID)
        print(f"   任务ID: {task_id}, 状态: {result.get('status')}")
        return result


def test_create_meeting(opportunity_id):
    print("7. 创建会议...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.schedule_meeting(opportunity_id, {
            "subject": "战略合作推进会议",
            "starts_at": "2026-07-20T14:00:00",
            "ends_at": "2026-07-20T15:30:00",
            "location": "线上会议",
            "online_url": "https://meeting.example.com/xyz",
            "agenda": "1. 合作背景介绍\n2. 双方需求对接\n3. 合作方案讨论\n4. 下一步计划",
        }, actor_user_id=ACTOR_USER_ID)
        print(f"   会议ID: {result.get('id')}, 会议编号: {result.get('meeting_no')}")
        return result["id"]


def test_complete_meeting(meeting_id, opportunity_id):
    print("8. 完成会议并生成任务草稿...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.complete_meeting(meeting_id, {
            "minutes": "双方就合作方案达成初步共识，同意进入下一阶段谈判",
            "decisions": "1. 双方指定专人对接\n2. 下周提交正式合作方案\n3. 月底前完成商务谈判",
            "task_drafts": [{
                "title": "提交正式合作方案",
                "owner_id": ACTOR_USER_ID,
                "priority": "P1",
                "due_date": "2026-07-27T18:00:00",
            }],
        }, actor_user_id=ACTOR_USER_ID)
        print(f"   会议状态: {result['meeting']['status']}, 生成任务数: {len(result.get('tasks', []))}")
        return result


def test_add_participant(opportunity_id):
    print("9. 添加参与者...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.add_participant(opportunity_id, {
            "participant_type": "user",
            "participant_id": "2",
            "role": "collaborator",
        }, actor_user_id=ACTOR_USER_ID)
        print(f"   参与者数量: {len(result['participants'])}")
        return result


def test_update_stage(opportunity_id):
    print("10. 推进阶段...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.update_stage(opportunity_id, stage="validating", actor_user_id=ACTOR_USER_ID, reason="线索已确认，进入验证阶段")
        print(f"   机会ID: {opportunity_id}, 当前阶段: {result['opportunity']['stage']}")
        return result


def test_add_artifact(opportunity_id):
    print("11. 添加材料引用...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        result = svc.add_artifact(opportunity_id, {
            "file_name": "合作方案v1.pdf",
            "artifact_type": "proposal",
            "external_url": "https://docs.example.com/proposal-v1.pdf",
            "visibility": "organization",
        }, actor_user_id=ACTOR_USER_ID)
        print(f"   材料ID: {result.get('id')}")
        return result


def test_idempotency(lead_id):
    print("12. 幂等性测试（重复转化）...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        try:
            result = svc.convert_lead(lead_id, actor_user_id=ACTOR_USER_ID, fields={})
            print(f"   幂等性验证: idempotent={result.get('idempotent')}")
            return result.get("idempotent") == True
        except Exception as e:
            print(f"   幂等性验证失败: {e}")
            return False


def test_calculate_risks(opportunity_id):
    print("13. 风险计算...")
    with SessionLocal() as db:
        svc = BusinessCollaborationService(db)
        risks = svc.calculate_risks(pilot_batch_id=PILOT_BATCH_ID)
        print(f"   检测到风险数: {len(risks)}")
        return risks


def main():
    print("=" * 60)
    print("T5.1 业务协同写入闭环测试")
    print("=" * 60)
    
    lead_id = test_create_lead()
    test_review_lead(lead_id)
    opportunity_id = test_convert_lead(lead_id)
    test_add_follow_up(opportunity_id)
    task_id = test_create_task(opportunity_id)
    test_update_task(task_id)
    meeting_id = test_create_meeting(opportunity_id)
    test_complete_meeting(meeting_id, opportunity_id)
    test_add_participant(opportunity_id)
    test_update_stage(opportunity_id)
    test_add_artifact(opportunity_id)
    test_idempotency(lead_id)
    test_calculate_risks(opportunity_id)
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
