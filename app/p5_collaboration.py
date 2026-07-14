from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text, bindparam
from sqlalchemy.exc import OperationalError

from app.database import engine
from app.routes_platform import get_current_user_id, get_user_role

router = APIRouter(tags=["p5_collaboration"])


def _templates():
    from app.main import templates
    return templates

STAGE_MAP = {
    "draft": "草稿",
    "pending_validation": "待验证",
    "matching": "匹配中",
    "introduced": "已引荐",
    "negotiation": "商务洽谈",
    "intent": "已达成意向",
    "executing": "执行中",
    "on_hold": "暂停",
    "won": "已成交",
    "lost": "已失败",
    "closed": "已关闭",
}

TASK_STATUS_MAP = {
    "pending": "待处理",
    "in_progress": "进行中",
    "blocked": "已阻塞",
    "completed": "已完成",
    "cancelled": "已取消",
}

LEAD_STATUS_MAP = {
    "new": "新线索",
    "reviewing": "审核中",
    "qualified": "已确认",
    "disqualified": "已否决",
    "converted": "已转化",
}


def _db_has_table(table_name: str) -> bool:
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
                {"name": table_name}
            )
            return result.scalar() is not None
    except OperationalError:
        return False


def _scalar(sql: str, params: dict = None) -> int:
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return int(result.scalar() or 0)
    except OperationalError:
        return 0


def _list(sql: str, params: dict = None) -> list[dict]:
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return [dict(row) for row in result.mappings()]
    except OperationalError:
        return []


def _get_user_id(request: Request) -> Optional[int]:
    try:
        return get_current_user_id(request)
    except Exception:
        return None


def _is_admin(request: Request) -> bool:
    try:
        from app.routes_platform import is_platform_admin
        return is_platform_admin(request)
    except Exception:
        return False


def _is_operator(request: Request) -> bool:
    try:
        role = get_user_role(request)
        return role in ["admin", "operator"]
    except Exception:
        return False


@router.get("/collaboration", response_class=HTMLResponse)
def collaboration_home(request: Request):
    user_id = _get_user_id(request)
    today = date.today().isoformat()
    metrics = {
        "新线索": 0, "待确认线索": 0, "推进中机会": 0, "本周待跟进": 0,
        "已逾期跟进": 0, "待完成任务": 0, "逾期任务": 0, "待召开会议": 0,
        "谈判中机会": 0, "执行中机会": 0, "暂停机会": 0, "本月成交": 0,
        "本月关闭": 0, "高风险机会": 0, "无负责人机会": 0, "无下一步行动机会": 0,
    }

    if _db_has_table("v06_opportunities"):
        metrics["推进中机会"] = _scalar(
            "SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND stage NOT IN ('won','lost','closed')"
        )
        metrics["谈判中机会"] = _scalar(
            "SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND stage='negotiation'"
        )
        metrics["执行中机会"] = _scalar(
            "SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND stage='executing'"
        )
        metrics["暂停机会"] = _scalar(
            "SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND stage='on_hold'"
        )
        metrics["无负责人机会"] = _scalar(
            "SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND owner_id IS NULL"
        )
        metrics["无下一步行动机会"] = _scalar(
            "SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND next_action IS NULL"
        )

    urgent_opportunities = _list(
        "SELECT id, title, stage, priority, next_follow_at, owner_id FROM v06_opportunities WHERE status='active' AND next_follow_at IS NOT NULL AND date(next_follow_at)<=date('now','+3 days') ORDER BY next_follow_at LIMIT 10"
    ) if _db_has_table("v06_opportunities") else []

    overdue_tasks = _list(
        "SELECT id, title, opportunity_id, due_date FROM p5_collab_tasks WHERE status IN ('pending','in_progress') AND due_date IS NOT NULL AND date(due_date)<date('now') ORDER BY due_date LIMIT 10"
    ) if _db_has_table("p5_collab_tasks") else []

    upcoming_meetings = _list(
        "SELECT id, subject, opportunity_id, starts_at FROM p5_collab_meetings WHERE status='scheduled' AND starts_at >= datetime('now') ORDER BY starts_at LIMIT 10"
    ) if _db_has_table("p5_collab_meetings") else []

    return _templates().TemplateResponse(
        request, "collaboration_home.html", {
            "metrics": metrics, "urgent_opportunities": urgent_opportunities,
            "overdue_tasks": overdue_tasks, "upcoming_meetings": upcoming_meetings,
            "stage_map": STAGE_MAP, "task_status_map": TASK_STATUS_MAP,
            "user_id": user_id, "is_admin": _is_admin(request),
        }
    )


@router.get("/collaboration/leads", response_class=HTMLResponse)
def collaboration_leads(request: Request, tab: str = "pending"):
    user_id = _get_user_id(request)
    tab_map = {
        "pending": "待确认", "qualified": "已确认",
        "disqualified": "已否决", "converted": "已转化",
    }

    if not _db_has_table("p5_club_leads"):
        return _templates().TemplateResponse(
            request, "collaboration_leads.html", {
                "tab": tab, "tab_map": tab_map, "leads": [],
                "no_table": True, "status_map": LEAD_STATUS_MAP,
                "is_operator": _is_operator(request),
            }
        )

    status_filter = {
        "pending": ["new", "reviewing"],
        "qualified": ["qualified"],
        "disqualified": ["disqualified"],
        "converted": ["converted"],
    }.get(tab, ["new", "reviewing"])

    leads = _list(
        "SELECT id, title, source_type, source_id, priority, owner_user_id, lifecycle_status, converted_opportunity_id, updated_at FROM p5_club_leads WHERE lifecycle_status IN :status ORDER BY updated_at DESC LIMIT 50",
        {"status": status_filter}
    )

    return _templates().TemplateResponse(
        request, "collaboration_leads.html", {
            "tab": tab, "tab_map": tab_map, "leads": leads,
            "no_table": False, "status_map": LEAD_STATUS_MAP,
            "is_operator": _is_operator(request),
        }
    )


@router.get("/collaboration/opportunities", response_class=HTMLResponse)
def collaboration_opportunities(request: Request, tab: str = "all"):
    user_id = _get_user_id(request)
    tab_map = {
        "all": "全部", "my": "我负责的", "active": "推进中",
        "on_hold": "暂停", "won": "已成交", "closed": "已关闭",
    }

    if not _db_has_table("v06_opportunities"):
        return _templates().TemplateResponse(
            request, "collaboration_opportunities.html", {
                "tab": tab, "tab_map": tab_map, "opportunities": [],
                "no_table": True, "stage_map": STAGE_MAP,
            }
        )

    base_sql = "SELECT id, title, stage, priority, estimated_amount, next_action, next_follow_at, owner_id, updated_at FROM v06_opportunities WHERE 1=1"
    params = {}

    if tab == "my" and user_id:
        base_sql += " AND owner_id = :user_id"
        params["user_id"] = user_id
    elif tab == "active":
        base_sql += " AND status='active' AND stage NOT IN ('won','lost','closed','on_hold')"
    elif tab == "on_hold":
        base_sql += " AND stage='on_hold'"
    elif tab == "won":
        base_sql += " AND stage='won'"
    elif tab == "closed":
        base_sql += " AND stage IN ('lost','closed')"

    opportunities = _list(base_sql + " ORDER BY updated_at DESC LIMIT 50", params)

    return _templates().TemplateResponse(
        request, "collaboration_opportunities.html", {
            "tab": tab, "tab_map": tab_map, "opportunities": opportunities,
            "no_table": False, "stage_map": STAGE_MAP,
        }
    )


@router.get("/collaboration/opportunities/{opp_id}", response_class=HTMLResponse)
def collaboration_opportunity_detail(request: Request, opp_id: int):
    user_id = _get_user_id(request)

    if not _db_has_table("v06_opportunities"):
        return _templates().TemplateResponse(
            request, "collaboration_opportunity_detail.html", {
                "opportunity": {}, "participants": [], "followups": [],
                "stage_history": [], "tasks": [], "meetings": [], "artifacts": [],
                "risks": [], "stage_map": STAGE_MAP, "task_status_map": TASK_STATUS_MAP,
                "is_admin": _is_admin(request),
            }
        )

    opportunity = _list(
        "SELECT * FROM v06_opportunities WHERE id = :opp_id", {"opp_id": opp_id}
    )
    if not opportunity:
        return _templates().TemplateResponse(
            request, "collaboration_opportunity_detail.html", {
                "opportunity": {}, "participants": [], "followups": [],
                "stage_history": [], "tasks": [], "meetings": [], "artifacts": [],
                "risks": [], "stage_map": STAGE_MAP, "task_status_map": TASK_STATUS_MAP,
                "is_admin": _is_admin(request),
            }
        )
    opportunity = opportunity[0]

    participants = _list(
        "SELECT participant_type, participant_id, role FROM p5_opportunity_participants WHERE opportunity_id = :opp_id",
        {"opp_id": opp_id}
    ) if _db_has_table("p5_opportunity_participants") else []

    followups = _list(
        "SELECT follow_type, followed_at, content, next_action, next_follow_at FROM p5_opportunity_followups WHERE opportunity_id = :opp_id ORDER BY followed_at DESC",
        {"opp_id": opp_id}
    ) if _db_has_table("p5_opportunity_followups") else []

    stage_history = _list(
        "SELECT old_stage, new_stage, reason, created_at FROM p5_opportunity_stage_history WHERE opportunity_id = :opp_id ORDER BY created_at DESC",
        {"opp_id": opp_id}
    ) if _db_has_table("p5_opportunity_stage_history") else []

    tasks = _list(
        "SELECT title, status, due_date, priority, owner_id FROM p5_collab_tasks WHERE opportunity_id = :opp_id ORDER BY due_date",
        {"opp_id": opp_id}
    ) if _db_has_table("p5_collab_tasks") else []

    meetings = _list(
        "SELECT subject, starts_at, ends_at, location, online_url, organizer_user_id, status FROM p5_collab_meetings WHERE opportunity_id = :opp_id ORDER BY starts_at DESC",
        {"opp_id": opp_id}
    ) if _db_has_table("p5_collab_meetings") else []

    artifacts = _list(
        "SELECT file_name, artifact_type, version, visibility, uploaded_by_user_id FROM p5_collab_artifacts WHERE opportunity_id = :opp_id",
        {"opp_id": opp_id}
    ) if _db_has_table("p5_collab_artifacts") else []

    risks = []
    if opportunity.get("next_follow_at") and date.fromisoformat(opportunity["next_follow_at"]) < date.today():
        risks.append({"risk_level": "high", "reason": "下次跟进已过期", "suggested_action": "尽快安排跟进"})
    if not opportunity.get("next_action"):
        risks.append({"risk_level": "medium", "reason": "没有下一步行动", "suggested_action": "设置下一步行动"})
    if not opportunity.get("owner_id"):
        risks.append({"risk_level": "high", "reason": "缺少负责人", "suggested_action": "分配负责人"})

    return _templates().TemplateResponse(
        request, "collaboration_opportunity_detail.html", {
            "opportunity": opportunity, "participants": participants,
            "followups": followups, "stage_history": stage_history,
            "tasks": tasks, "meetings": meetings, "artifacts": artifacts,
            "risks": risks, "stage_map": STAGE_MAP, "task_status_map": TASK_STATUS_MAP,
            "is_admin": _is_admin(request),
        }
    )


@router.get("/collaboration/tasks", response_class=HTMLResponse)
def collaboration_tasks(request: Request, tab: str = "my"):
    user_id = _get_user_id(request)
    tab_map = {"my": "我的", "overdue": "超期", "all": "全部"}

    if not _db_has_table("p5_collab_tasks"):
        return _templates().TemplateResponse(
            request, "collaboration_tasks.html", {
                "tab": tab, "tab_map": tab_map, "tasks": [], "followups": [],
                "no_table": True, "task_status_map": TASK_STATUS_MAP,
                "user_id": user_id, "is_admin": _is_admin(request),
            }
        )

    base_sql = "SELECT id, title, opportunity_id, owner_id, due_date, priority, status, created_at FROM p5_collab_tasks WHERE 1=1"
    params = {}

    if tab == "my" and user_id:
        base_sql += " AND owner_id = :user_id"
        params["user_id"] = user_id
    elif tab == "overdue":
        base_sql += " AND status IN ('pending','in_progress') AND due_date IS NOT NULL AND date(due_date)<date('now')"

    tasks = _list(base_sql + " ORDER BY due_date, priority DESC LIMIT 50", params)

    followups = _list(
        "SELECT follow_type, followed_at, content, opportunity_id FROM p5_opportunity_followups ORDER BY followed_at DESC LIMIT 20"
    ) if _db_has_table("p5_opportunity_followups") else []

    return _templates().TemplateResponse(
        request, "collaboration_tasks.html", {
            "tab": tab, "tab_map": tab_map, "tasks": tasks, "followups": followups,
            "no_table": False, "task_status_map": TASK_STATUS_MAP,
            "user_id": user_id, "is_admin": _is_admin(request),
        }
    )


@router.get("/collaboration/meetings", response_class=HTMLResponse)
def collaboration_meetings(request: Request, tab: str = "meetings"):
    user_id = _get_user_id(request)

    meetings = []
    artifacts = []

    if tab == "meetings" and _db_has_table("p5_collab_meetings"):
        meetings = _list(
            "SELECT id, subject, opportunity_id, starts_at, ends_at, location, online_url, organizer_user_id, status FROM p5_collab_meetings ORDER BY starts_at DESC LIMIT 50"
        )

    if tab == "materials" and _db_has_table("p5_collab_artifacts"):
        artifacts = _list(
            "SELECT id, file_name, artifact_type, opportunity_id, uploaded_by_user_id, version, visibility FROM p5_collab_artifacts ORDER BY uploaded_at DESC LIMIT 50"
        )

    return _templates().TemplateResponse(
        request, "collaboration_meetings.html", {
            "tab": tab, "meetings": meetings, "artifacts": artifacts,
            "is_admin": _is_admin(request),
        }
    )
