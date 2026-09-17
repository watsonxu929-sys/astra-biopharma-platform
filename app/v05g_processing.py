from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.services.intelligence_review_service import IntelligenceReviewService
from app.services.intelligence_product_service import IntelligenceProductService
from app.services.processing import (
    apply_candidate,
    candidate_delete_preview,
    candidate_detail,
    create_processing_job,
    delete_candidate_safely,
    dashboard,
    list_candidates,
    list_jobs,
    list_review_queue,
    list_subject_matches,
    process_job,
    run_worker,
)

router = APIRouter(tags=["情报加工"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@router.get("/processing", response_class=HTMLResponse)
def processing_home(request: Request):
    return templates.TemplateResponse(request, "v05g_processing.html", {"mode": "home", **dashboard()})


@router.get("/processing/jobs", response_class=HTMLResponse)
def processing_jobs(request: Request, page: int = 1, status: str = "", item_id: int = 0, message: str = "", error: str = ""):
    rows, total = list_jobs(page=page, status=status)
    recovery_jobs = [row for row in rows if row.get("status") in {"pending", "running", "failed"}]
    return templates.TemplateResponse(request, "v05g_processing.html", {
        "mode": "jobs", "jobs": rows, "recovery_jobs": recovery_jobs,
        "total": total, "page": page, "status": status, "item_id": item_id,
        "message": message, "error": error, **dashboard(),
    })


@router.post("/processing/jobs")
def processing_create_job(
    request: Request,
    item_id: int = Form(0),
    snapshot_id: int = Form(0),
    queued_only: str = Form("1"),
    reprocess: str = Form(""),
    run_now: str = Form(""),
):
    try:
        job = create_processing_job(
            item_id=item_id or None,
            snapshot_id=snapshot_id or None,
            trigger_type="manual",
            operator=current_username(request),
            queued_only=bool(queued_only),
            reprocess=bool(reprocess),
        )
        if run_now:
            result = process_job(job["id"])
            return RedirectResponse(f"/processing/jobs?message=已执行 {job['job_no']}: {result.get('status')}", status_code=303)
        return RedirectResponse(f"/processing/jobs?message=任务已创建：{job['job_no']}", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/processing/jobs?error={str(exc)[:200]}", status_code=303)


@router.post("/processing/jobs/{job_id}/run")
def processing_run_job(job_id: int):
    result = process_job(job_id)
    return RedirectResponse(f"/processing/jobs?message=已执行 {job_id}: {result.get('status')}", status_code=303)


@router.post("/processing/worker/run-once")
def processing_worker_once(request: Request, limit: int = Form(20), queued_only: str = Form("1"), reprocess: str = Form("")):
    result = run_worker(once=True, queued_only=bool(queued_only), limit=limit, reprocess=bool(reprocess), operator=current_username(request))
    return RedirectResponse(f"/processing/jobs?message=执行器已处理 {result.get('processed', 0)} 个任务", status_code=303)


@router.get("/processing/candidates", response_class=HTMLResponse)
def processing_candidates(request: Request, page: int = 1, review_status: str = "", candidate_type: str = "", q: str = "", message: str = "", error: str = ""):
    rows, total = list_candidates(page=page, review_status=review_status, candidate_type=candidate_type, q=q)
    return templates.TemplateResponse(request, "v05g_processing.html", {"mode": "candidates", "candidates": rows, "total": total, "page": page, "review_status": review_status, "candidate_type": candidate_type, "q": q, "message": message, "error": error})


@router.get("/processing/review-queue", response_class=HTMLResponse)
def processing_review_queue(request: Request, page: int = 1, message: str = "", error: str = "", view: str = 'priority', category: str = ''):
    from app.services.processing.article_facts import CATEGORIES, REVIEW_VIEWS
    rows, total = list_review_queue(page=page, view=view, category=category)
    return templates.TemplateResponse(request, "v05g_processing.html", {"mode": "review_queue", "candidates": rows, "total": total, "page": page, "message": message, "error": error, 'view':view,'category':category,'categories':CATEGORIES,'review_views':REVIEW_VIEWS})




@router.get("/processing/candidates/{candidate_id}", response_class=HTMLResponse)
def processing_candidate_detail(request: Request, candidate_id: int, message: str = "", error: str = ""):
    detail = candidate_detail(candidate_id)
    if not detail:
        raise HTTPException(status_code=404, detail="候选数据不存在")
    return templates.TemplateResponse(request, "v05g_processing.html", {"mode": "candidate_detail", "message": message, "error": error, **detail})


def _require_candidate_delete_permission(request: Request) -> None:
    security = request.scope.get("security_context", {})
    permissions = set(security.get("permissions") or [])
    if not (security.get("can_manage_users") or "manage_users" in permissions or "review_data" in permissions):
        raise HTTPException(403, "仅管理员或审核人员可以删除未确认候选")


@router.get("/processing/candidates/{candidate_id:int}/delete", response_class=HTMLResponse)
def processing_candidate_delete_page(request: Request, candidate_id: int):
    _require_candidate_delete_permission(request)
    try:
        preview = candidate_delete_preview(candidate_id)
    except ValueError as exc:
        raise HTTPException(404, "候选数据不存在") from exc
    return templates.TemplateResponse(request, "v05g_processing.html", {"mode": "candidate_delete", "preview": preview})


@router.post("/processing/candidates/{candidate_id:int}/delete")
def processing_candidate_delete_confirm(request: Request, candidate_id: int):
    _require_candidate_delete_permission(request)
    try:
        result = delete_candidate_safely(candidate_id, actor=current_username(request))
    except ValueError as exc:
        raise HTTPException(404, "候选数据不存在") from exc
    if not result["deleted"]:
        reasons = "、".join(f"{key}={value}" for key, value in result["protected"].items())
        return RedirectResponse(f"/processing/candidates/{candidate_id}?error=候选已有正式引用，不能删除：{reasons}", 303)
    return RedirectResponse("/processing/candidates?message=未确认候选已安全删除，原始证据仍保留", 303)


@router.get("/processing/candidates/{candidate_id}/matches", response_class=HTMLResponse)
def processing_candidate_matches(request: Request, candidate_id: int):
    detail = candidate_detail(candidate_id)
    if not detail:
        raise HTTPException(status_code=404, detail="???????")
    return templates.TemplateResponse(request, "v05g_processing.html", {"mode": "candidate_matches", **detail})


@router.get("/processing/candidates/{candidate_id}/evidence", response_class=HTMLResponse)
def processing_candidate_evidence(request: Request, candidate_id: int):
    detail = candidate_detail(candidate_id)
    if not detail:
        raise HTTPException(status_code=404, detail="???????")
    return templates.TemplateResponse(request, "v05g_processing.html", {"mode": "candidate_evidence", **detail})


@router.post("/processing/candidates/{candidate_id}/submit")
def processing_submit_candidate(request: Request, candidate_id: int):
    context = request.scope.get("security_context", {})
    try:
        IntelligenceReviewService().submit_candidate(candidate_id, actor=current_username(request), permissions=set(context.get("permissions") or []))
        return RedirectResponse("/processing/review-queue?message=submitted", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/processing/candidates/{candidate_id}?error={str(exc)[:200]}", status_code=303)


@router.post("/processing/candidates/{candidate_id}/review")
def processing_review_candidate(request: Request, candidate_id: int, decision: str = Form(...), note: str = Form(""), final_value: str = Form(""), return_to: str = Form("")):
    _require_article_review(request)
    try:
        context = request.scope.get("security_context", {})
        row = IntelligenceReviewService().review_candidate(
            candidate_id, decision=decision, actor=current_username(request),
            permissions=set(context.get("permissions") or []), note=note,
            final_value=final_value,
        )
        target = "/processing/review-queue" if return_to == "/processing/review-queue" else f"/processing/candidates/{candidate_id}"
        return RedirectResponse(f"{target}?message=reviewed", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/processing/candidates/{candidate_id}?error={str(exc)[:200]}", status_code=303)


@router.post("/processing/candidates/{candidate_id}/publish")
def processing_publish_candidate(request: Request, candidate_id: int):
    _require_article_review(request)
    context = request.scope.get("security_context", {})
    try:
        detail = candidate_detail(candidate_id)
        if detail and detail['candidate']['field_name'] == 'article_review':
            if detail['candidate']['pipeline_review_status'] == 'rejected':
                raise ValueError('该文章已忽略；请先人工编辑补充后重新审核')
            IntelligenceReviewService().review_candidate(candidate_id, decision='approved', actor=current_username(request), permissions=set(context.get('permissions') or []), note='人工确认文章发布')
        product = IntelligenceProductService().publish_candidate(
            candidate_id,
            actor=current_username(request),
            permissions=set(context.get("permissions") or []),
        )
        return RedirectResponse(f"/intelligence/{product['id']}", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/processing/candidates/{candidate_id}?error={str(exc)[:200]}", status_code=303)


def _require_article_review(request: Request) -> None:
    if 'review_data' not in set(request.scope.get('security_context', {}).get('permissions') or []):
        raise HTTPException(status_code=403, detail='当前账号没有情报审核权限')


@router.post('/processing/candidates/{candidate_id}/edit')
def processing_edit_article(request: Request, candidate_id: int, title: str = Form(...), content: str = Form(...),
                            published_at: str = Form(''), note: str = Form(''), attachments_reviewed: str = Form('')):
    _require_article_review(request)
    try:
        IntelligenceReviewService().edit_article(candidate_id, actor=current_username(request),
            permissions=set(request.scope['security_context'].get('permissions') or []), title=title,
            content=content, published_at=published_at, note=note, attachments_reviewed=bool(attachments_reviewed))
        return RedirectResponse(f'/processing/candidates/{candidate_id}?message=已保存，等待人工审核', status_code=303)
    except ValueError as exc:
        return RedirectResponse(f'/processing/candidates/{candidate_id}?error={str(exc)[:200]}', status_code=303)


@router.post("/processing/candidates/{candidate_id}/apply")
def processing_apply_candidate(request: Request, candidate_id: int):
    result = apply_candidate(candidate_id, actor=current_username(request))
    return RedirectResponse(f"/processing/candidates/{candidate_id}?message=入库 {result.get('result')}", status_code=303)


@router.get("/processing/subject-matches", response_class=HTMLResponse)
def processing_subject_matches(request: Request, page: int = 1, status: str = "", message: str = ""):
    rows, total = list_subject_matches(page=page, status=status)
    return templates.TemplateResponse(request, "v05g_processing.html", {"mode": "matches", "matches": rows, "total": total, "page": page, "status": status, "message": message})


@router.get("/v05g/health")
def health():
    data = dashboard()
    return {"ok": True, "version": "0.5G", "counts": data["counts"]}
