from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from urllib.parse import quote
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes_platform import get_current_user_id, get_user_role
from app.services.golden_loop_service import GoldenLoopService


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _identity(request: Request) -> tuple[int, str]:
    user_id = get_current_user_id(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return int(user_id), get_user_role(request)


def _writer(request: Request) -> tuple[int, str]:
    user_id, role = _identity(request)
    GoldenLoopService.require_writer(role)
    return user_id, role


def _redirect(path: str, message: str) -> RedirectResponse:
    separator = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{separator}message={quote(message)}", status_code=303)


@router.get("/platform/golden-loop", response_class=HTMLResponse)
def golden_loop_workbench(
    request: Request,
    intelligence_id: int | None = Query(None),
    subject_q: str = Query(""),
    message: str = Query(""),
    match_status: str = Query(""),
    db: Session = Depends(get_db),
):
    user_id, role = _identity(request)
    service = GoldenLoopService(db)
    data = service.workbench()
    trace = service.trace(intelligence_id) if intelligence_id else None
    query = subject_q.strip()
    pattern = f"%{query}%"
    if match_status == "pending":
        data["matches"] = [item for item in data["matches"] if item["status"] in {"pending", "reviewed"}]
    people = db.execute(text("SELECT id,name FROM people WHERE COALESCE(is_active,1)=1 AND (:q='' OR name LIKE :pattern) ORDER BY name LIMIT 80"), {"q": query, "pattern": pattern}).mappings().all()
    organizations = db.execute(text("SELECT id,standard_name FROM organizations WHERE COALESCE(is_active,1)=1 AND (:q='' OR standard_name LIKE :pattern) ORDER BY standard_name LIMIT 80"), {"q": query, "pattern": pattern}).mappings().all()
    projects = db.execute(text("SELECT id,name FROM projects WHERE (:q='' OR name LIKE :pattern) ORDER BY name LIMIT 80"), {"q": query, "pattern": pattern}).mappings().all()
    demands = db.execute(text("SELECT id,title FROM v06_market_resources WHERE direction='demand' AND status='published' ORDER BY id DESC LIMIT 80")).mappings().all()
    supplies = db.execute(text("SELECT id,title FROM v06_market_resources WHERE direction='supply' AND status='published' ORDER BY id DESC LIMIT 80")).mappings().all()
    return templates.TemplateResponse(
        request=request,
        name="platform/golden_loop.html",
        context={
            "data": data,
            "trace": trace,
            "selected_intelligence_id": intelligence_id,
            "people": people,
            "organizations": organizations,
            "projects": projects,
            "demands": demands,
            "supplies": supplies,
            "subject_q": query,
            "message": message,
            "user_id": user_id,
            "role": role,
            "match_status": match_status,
            "can_write": role in {"operator", "reviewer", "admin"},
        },
    )


@router.post("/golden-loop/intelligence/{intelligence_id}/subjects")
async def link_intelligence_subject(
    intelligence_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _writer(request)
    form = await request.form()
    subject_ref = str(form.get("subject_ref") or "")
    try:
        subject_type, subject_id_text = subject_ref.split(":", 1)
        subject_id = int(subject_id_text)
    except (TypeError, ValueError):
        subject_type = str(form.get("subject_type") or "")
        subject_id = int(form.get("subject_id") or 0)
    GoldenLoopService(db).link_subject(
        intelligence_id,
        subject_type=subject_type,
        subject_id=subject_id,
        actor_user_id=user_id,
    )
    return _redirect(f"/intelligence/{intelligence_id}", "主体关联已保存")


@router.post("/golden-loop/intelligence/{intelligence_id}/subject-candidates/ignore")
async def ignore_intelligence_subject_candidate(
    intelligence_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _writer(request)
    form = await request.form()
    try:
        subject_type = str(form.get("subject_type") or "")
        subject_id = int(form.get("subject_id") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="主体候选参数无效")
    GoldenLoopService(db).ignore_subject_candidate(
        intelligence_id,
        subject_type=subject_type,
        subject_id=subject_id,
        actor_user_id=user_id,
    )
    return _redirect(f"/intelligence/{intelligence_id}", "已忽略该主体候选")


@router.post("/golden-loop/intelligence/{intelligence_id}/today-dismiss")
def dismiss_intelligence_today(
    intelligence_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _writer(request)
    GoldenLoopService(db).set_today_disposition(
        intelligence_id, actor_user_id=user_id, dismissed=True
    )
    return _redirect("/platform", "已从今天值得处理中暂时隐藏")


@router.post("/golden-loop/intelligence/{intelligence_id}/today-restore")
def restore_intelligence_today(
    intelligence_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _writer(request)
    GoldenLoopService(db).set_today_disposition(
        intelligence_id, actor_user_id=user_id, dismissed=False
    )
    return _redirect("/platform", "已恢复到今天值得处理")


@router.post("/golden-loop/intelligence/{intelligence_id}/follow-ups")
async def create_intelligence_follow_up(
    intelligence_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _writer(request)
    form = await request.form()
    result = GoldenLoopService(db).create_follow_up_from_intelligence(
        intelligence_id,
        actor_user_id=user_id,
        object_name=str(form.get("object_name") or ""),
        matter=str(form.get("matter") or ""),
        reason=str(form.get("reason") or ""),
        next_action=str(form.get("next_action") or ""),
        next_follow_at=str(form.get("next_follow_at") or ""),
    )
    return RedirectResponse(
        f"/intelligence/{intelligence_id}?message={quote('跟进已创建')}"
        f"&follow_up_id={int(result['id'])}&opportunity_id={int(result['opportunity_id'])}",
        status_code=303,
    )


@router.post("/golden-loop/intelligence/{intelligence_id}/resources")
async def create_resource_from_intelligence(
    intelligence_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _writer(request)
    form = await request.form()
    resource = GoldenLoopService(db).create_resource_from_intelligence(
        intelligence_id,
        direction=str(form.get("direction") or ""),
        actor_user_id=user_id,
        fields={
            "title": form.get("title"),
            "resource_type": form.get("resource_type"),
            "summary": form.get("summary"),
            "description": form.get("description"),
            "cooperation_mode": form.get("cooperation_mode"),
            "cooperation_terms": form.get("cooperation_terms"),
            "valid_until": form.get("valid_until"),
            "organization_id": form.get("organization_id"),
        },
    )
    return RedirectResponse(f"/resources/{resource['id']}", status_code=303)


@router.post("/golden-loop/matches")
async def confirm_resource_match(request: Request, db: Session = Depends(get_db)):
    user_id, _ = _writer(request)
    form = await request.form()
    service = GoldenLoopService(db)
    match = service.confirm_match(
        demand_resource_id=int(form.get("demand_resource_id") or 0),
        supply_resource_id=int(form.get("supply_resource_id") or 0),
        actor_user_id=user_id,
        note=str(form.get("note") or ""),
    )
    if str(form.get("decision") or "confirm") == "reject":
        match = service.set_match_intention(
            int(match["id"]), actor_user_id=user_id, intention="not_interested",
            reason_code="conditions_not_met", note=str(form.get("note") or "暂不匹配"),
        )
    return RedirectResponse(f"/matches/{match['id']}", status_code=303)


@router.post("/golden-loop/matches/{match_id:int}/intention")
async def set_match_intention(
    match_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _writer(request)
    form = await request.form()
    GoldenLoopService(db).set_match_intention(
        match_id,
        actor_user_id=user_id,
        intention=str(form.get("intention") or ""),
        reason_code=str(form.get("reason_code") or ""),
        note=str(form.get("note") or ""),
    )
    return _redirect(f"/matches/{match_id}", "匹配处理结果已保存")

@router.get("/matches/{match_id:int}", response_class=HTMLResponse)
def golden_match_detail(
    match_id: int,
    request: Request,
    message: str = Query(""),
    db: Session = Depends(get_db),
):
    _, role = _identity(request)
    match = GoldenLoopService(db).match_detail(match_id)
    return templates.TemplateResponse(
        request=request,
        name="platform/golden_match_detail.html",
        context={
            "match": match,
            "message": message,
            "can_write": role in {"operator", "reviewer", "admin"},
        },
    )


@router.post("/golden-loop/matches/{match_id:int}/convert")
def convert_match_to_opportunity(
    match_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, _ = _writer(request)
    opportunity = GoldenLoopService(db).convert_match_to_opportunity(
        match_id,
        actor_user_id=user_id,
    )
    return RedirectResponse(f"/opportunities/{opportunity['id']}", status_code=303)


@router.post("/golden-loop/opportunities/{opportunity_id:int}/follow-ups")
async def add_golden_follow_up(
    opportunity_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, role = _writer(request)
    service = GoldenLoopService(db)
    opportunity = service._opportunity(opportunity_id)
    if not service.can_manage_opportunity(opportunity, user_id, role):
        raise HTTPException(status_code=403, detail="无权跟进该合作机会")
    form = await request.form()
    service.add_follow_up(
        opportunity_id,
        actor_user_id=user_id,
        content=str(form.get("content") or ""),
        next_action=str(form.get("next_action") or ""),
        contact_result=str(form.get("contact_result") or ""),
        stage_after=str(form.get("stage_after") or ""),
        next_follow_at=str(form.get("next_follow_at") or ""),
    )
    return _redirect(f"/opportunities/{opportunity_id}", "跟进已登记")


@router.post("/golden-loop/opportunities/{opportunity_id:int}/tasks")
async def create_golden_task(
    opportunity_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, role = _writer(request)
    service = GoldenLoopService(db)
    opportunity = service._opportunity(opportunity_id)
    if not service.can_manage_opportunity(opportunity, user_id, role):
        raise HTTPException(status_code=403, detail="无权为该合作机会创建任务")
    form = await request.form()
    service.create_task(
        opportunity_id,
        actor_user_id=user_id,
        title=str(form.get("title") or ""),
        due_date=str(form.get("due_date") or ""),
        priority=str(form.get("priority") or "P2"),
    )
    return _redirect(f"/opportunities/{opportunity_id}", "协作任务已创建")

@router.post("/golden-loop/opportunities/{opportunity_id:int}/outcome")
async def close_golden_outcome(
    opportunity_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id, role = _writer(request)
    service = GoldenLoopService(db)
    opportunity = service._opportunity(opportunity_id)
    if not service.can_manage_opportunity(opportunity, user_id, role):
        raise HTTPException(status_code=403, detail="无权关闭该合作机会")
    form = await request.form()
    result = service.close_outcome(
        opportunity_id,
        actor_user_id=user_id,
        outcome=str(form.get("outcome") or ""),
        reason=str(form.get("reason") or ""),
        result_note=str(form.get("result_note") or ""),
        cooperation_scale=str(form.get("cooperation_scale") or ""),
        evidence_text=str(form.get("evidence_text") or ""),
    )
    suffix = "，正式合作关系已形成" if result["relationship_created"] else "，未形成正式合作关系"
    return _redirect(f"/opportunities/{opportunity_id}", f"商务结果已保存{suffix}")
