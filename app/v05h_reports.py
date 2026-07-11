from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.intelligence_product_service import IntelligenceProductService
from app.services.unified_intelligence_service import UnifiedIntelligenceService

from app.security import current_username
from app.services.reports import archive_report, approve_report, create_report_job, generate_report, get_report, list_report_jobs, list_reports, report_citations, submit_report, update_report

router = APIRouter(tags=["报告中心"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, page: int = 1, status: str = "", report_type: str = "", message: str = "", error: str = "", db: Session = Depends(get_db)):
    result = list_reports(page=page, status=status, report_type=report_type)
    jobs = list_report_jobs(page=1, page_size=10)
    products = UnifiedIntelligenceService(db).list(page=1, page_size=100)["items"]
    return templates.TemplateResponse(request, "v05h_reports.html", {"mode": "list", "result": result, "jobs": jobs, "products": products, "status": status, "report_type": report_type, "message": message, "error": error})


@router.post("/reports/jobs")
def reports_create(request: Request, report_type: str = Form("daily"), period_start: str = Form(""), period_end: str = Form(""), run_now: str = Form("1")):
    try:
        job = create_report_job(report_type=report_type, period_start=period_start, period_end=period_end, generated_by=current_username(request))
        if run_now:
            report = generate_report(job["id"])
            return RedirectResponse(f"/reports/{report['id']}?message=已生成", status_code=303)
        return RedirectResponse("/reports?message=任务已创建", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/reports?error={str(exc)[:200]}", status_code=303)


@router.get("/reports/jobs", response_class=HTMLResponse)
def report_jobs_page(request: Request, page: int = 1, status: str = "", message: str = ""):
    jobs = list_report_jobs(page=page, status=status)
    return templates.TemplateResponse(request, "v05h_reports.html", {"mode": "jobs", "jobs": jobs, "status": status, "message": message})


@router.get("/reports/{report_id:int}", response_class=HTMLResponse)

@router.get("/reports/products/{product_id:int}", response_class=HTMLResponse)
def intelligence_product_detail(request: Request, product_id: int, db: Session = Depends(get_db)):
    item = UnifiedIntelligenceService(db).detail(product_id)
    trace = IntelligenceProductService().trace(product_id)
    return templates.TemplateResponse(
        request,
        "platform/intelligence_detail.html",
        {"item": item, "evidence": trace["evidence"], "candidates": trace["candidates"], "is_favorited": False, "product_context": True},
    )

def report_detail(request: Request, report_id: int, message: str = "", error: str = ""):
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return templates.TemplateResponse(request, "v05h_reports.html", {"mode": "detail", "report": report, "citations": report_citations(report_id), "message": message, "error": error})


@router.post("/reports/{report_id:int}/edit")
def report_edit(report_id: int, title: str = Form(""), summary: str = Form(""), content_markdown: str = Form("")):
    update_report(report_id, title=title, summary=summary, content_markdown=content_markdown)
    return RedirectResponse(f"/reports/{report_id:int}?message=已保存", status_code=303)


@router.post("/reports/{report_id:int}/submit")
def report_submit(request: Request, report_id: int):
    submit_report(report_id, actor=current_username(request))
    return RedirectResponse(f"/reports/{report_id:int}?message=已提交审核", status_code=303)


@router.post("/reports/{report_id:int}/approve")
def report_approve(request: Request, report_id: int):
    approve_report(report_id, actor=current_username(request))
    return RedirectResponse(f"/reports/{report_id:int}?message=已批准", status_code=303)


@router.post("/reports/{report_id:int}/archive")
def report_archive(request: Request, report_id: int):
    archive_report(report_id, actor=current_username(request))
    return RedirectResponse("/reports?message=已归档", status_code=303)


@router.get("/v05h/health")
def health():
    data = list_reports(page=1, page_size=1)
    return {"ok": True, "version": "0.5H", "report_count": data["pagination"]["total"]}


