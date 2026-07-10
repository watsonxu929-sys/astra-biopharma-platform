from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.services.collection_service import list_sources
from app.services.pipeline import cancel_pipeline, continue_pipeline, create_pipeline_run, dashboard, list_pipeline_runs, pipeline_detail, quality_metrics, retry_pipeline, review_quality_sample

router = APIRouter(tags=["流水线中心"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_home(request: Request):
    return templates.TemplateResponse(request, "v05i_pipeline.html", {"mode": "dashboard", "dashboard": dashboard(), "quality": quality_metrics()})


@router.get("/pipeline/runs", response_class=HTMLResponse)
def pipeline_runs(request: Request, page: int = 1, status: str = "", message: str = "", error: str = ""):
    sources, _ = list_sources(page=1, page_size=100)
    return templates.TemplateResponse(request, "v05i_pipeline.html", {"mode": "runs", "result": list_pipeline_runs(page=page, status=status), "sources": sources, "status": status, "message": message, "error": error})


@router.post("/pipeline/runs")
def pipeline_create(request: Request, source_id: int = Form(...), pilot: str = Form("1"), dry_run: str = Form("1"), run_now: str = Form("")):
    try:
        run = create_pipeline_run(source_id, created_by=current_username(request), pilot=bool(pilot), dry_run=bool(dry_run))
        if run_now:
            run = continue_pipeline(run["id"], actor=current_username(request))
        return RedirectResponse(f"/pipeline/runs/{run['id']}?message=已创建", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/pipeline/runs?error={str(exc)[:160]}", status_code=303)


@router.get("/pipeline/runs/{run_id}", response_class=HTMLResponse)
def pipeline_run_detail(request: Request, run_id: int, message: str = "", error: str = ""):
    data = pipeline_detail(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="流水线运行不存在")
    return templates.TemplateResponse(request, "v05i_pipeline.html", {"mode": "detail", **data, "message": message, "error": error})


@router.post("/pipeline/runs/{run_id}/continue")
def pipeline_continue(request: Request, run_id: int):
    continue_pipeline(run_id, actor=current_username(request))
    return RedirectResponse(f"/pipeline/runs/{run_id}?message=已继续", status_code=303)


@router.post("/pipeline/runs/{run_id}/retry")
def pipeline_retry(request: Request, run_id: int):
    try:
        retry_pipeline(run_id, actor=current_username(request))
        return RedirectResponse(f"/pipeline/runs/{run_id}?message=已重新执行", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/pipeline/runs/{run_id}?error={str(exc)[:160]}", status_code=303)


@router.post("/pipeline/runs/{run_id}/cancel")
def pipeline_cancel(request: Request, run_id: int):
    cancel_pipeline(run_id, actor=current_username(request))
    return RedirectResponse("/pipeline/runs?message=已取消", status_code=303)


@router.get("/pipeline/failures", response_class=HTMLResponse)
def pipeline_failures(request: Request, page: int = 1):
    return templates.TemplateResponse(request, "v05i_pipeline.html", {"mode": "runs", "result": list_pipeline_runs(page=page, status="failed"), "sources": [], "status": "failed"})


@router.get("/pipeline/pilot", response_class=HTMLResponse)
def pipeline_pilot(request: Request):
    sources, _ = list_sources(page=1, page_size=100)
    return templates.TemplateResponse(request, "v05i_pipeline.html", {"mode": "pilot", "sources": sources, "quality": quality_metrics()})


@router.post("/pipeline/samples/{sample_id}/review")
def pipeline_sample_review(request: Request, sample_id: int, run_id: int = Form(...), correctness: str = Form(...), error_type: str = Form(""), note: str = Form("")):
    review_quality_sample(sample_id, correctness=correctness, error_type=error_type, reviewer=current_username(request), note=note)
    return RedirectResponse(f"/pipeline/runs/{run_id}?message=样本已审核", status_code=303)


@router.get("/v05i/health")
def health():
    data = dashboard()
    return {"ok": True, "version": "0.5I", "runs": data["counts"]["today_runs"]}

