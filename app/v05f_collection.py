from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.services.collection_service import (
    create_collection_source,
    create_job,
    dashboard,
    list_items,
    list_jobs,
    list_sources,
    process_job,
    snapshot_detail,
)
from app.services.collection_scheduler import (
    get_scheduler_info,
    get_sources_with_next_run,
    is_scheduler_running,
    run_scheduler_once,
)

router = APIRouter(tags=["信息采集"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@router.get("/collection", response_class=HTMLResponse)
def collection_home(request: Request):
    data = dashboard()
    data["scheduler_info"] = get_scheduler_info()
    data["scheduler_running"] = is_scheduler_running()
    data["sources_with_next_run"] = get_sources_with_next_run()
    return templates.TemplateResponse(request, "v05f_collection.html", {"mode": "home", **data})


@router.get("/collection/sources", response_class=HTMLResponse)
def collection_sources(request: Request, page: int = 1, q: str = "", status: str = "", message: str = "", error: str = ""):
    rows, total = list_sources(page=page, q=q, status=status)
    return templates.TemplateResponse(
        request,
        "v05f_collection.html",
        {"mode": "sources", "sources": rows, "total": total, "page": page, "q": q, "status": status, "message": message, "error": error},
    )


@router.post("/collection/sources")
def collection_create_source(
    request: Request,
    name: str = Form(...),
    source_type: str = Form("webpage"),
    url: str = Form(...),
    collection_mode: str = Form("auto"),
    allowed_domains: str = Form(""),
    subject_type: str = Form(""),
    subject_id: str = Form(""),
    compliance_note: str = Form(""),
    max_links: int = Form(20),
    crawl_detail_pages: str = Form(""),
):
    try:
        row = create_collection_source(
            name=name,
            source_type=source_type,
            url=url,
            collection_mode=collection_mode,
            allowed_domains=allowed_domains,
            subject_type=subject_type,
            subject_id=subject_id,
            owner=current_username(request),
            compliance_note=compliance_note,
            max_links=max_links,
            crawl_detail_pages=bool(crawl_detail_pages),
        )
    except Exception as exc:
        return RedirectResponse(f"/collection/sources?error={str(exc)[:200]}", status_code=303)
    return RedirectResponse(f"/collection/sources?message=来源已保存：{row['source_no']}", status_code=303)


@router.get("/collection/sources/{source_id}", response_class=HTMLResponse)
def collection_source_detail(request: Request, source_id: int):
    rows, _ = list_sources(page=1, page_size=200)
    source = next((row for row in rows if row["id"] == source_id), None)
    if not source:
        raise HTTPException(status_code=404, detail="采集来源不存在")
    jobs, _ = list_jobs(page=1, page_size=50)
    items, _ = list_items(page=1, page_size=50)
    return templates.TemplateResponse(
        request,
        "v05f_collection.html",
        {
            "mode": "source_detail",
            "source": source,
            "jobs": [job for job in jobs if job["monitoring_source_id"] == source_id],
            "items": [item for item in items if item.get("source_no") == source["source_no"]],
        },
    )


@router.post("/collection/sources/{source_id}/run")
def collection_run_source(request: Request, source_id: int, force: str = Form("")):
    try:
        job = create_job(source_id, trigger_type="manual", operator=current_username(request), force=bool(force))
    except RuntimeError:
        return RedirectResponse("/collection/jobs?error=已有运行中的采集任务", status_code=303)
    return RedirectResponse(f"/collection/jobs?message=任务已创建：{job['run_no']}", status_code=303)


@router.post("/collection/sources/batch-run")
async def collection_batch_run(request: Request):
    form = await request.form()
    created = 0
    conflicts = 0
    for raw in form.getlist("source_ids")[:50]:
        try:
            create_job(int(raw), trigger_type="manual", operator=current_username(request))
            created += 1
        except RuntimeError:
            conflicts += 1
        except (TypeError, ValueError):
            continue
    return RedirectResponse(f"/collection/jobs?message=已创建={created}, 冲突={conflicts}", status_code=303)


@router.get("/collection/jobs", response_class=HTMLResponse)
def collection_jobs(request: Request, page: int = 1, status: str = "", message: str = "", error: str = ""):
    rows, total = list_jobs(page=page, status=status)
    return templates.TemplateResponse(request, "v05f_collection.html", {"mode": "jobs", "jobs": rows, "total": total, "page": page, "status": status, "message": message, "error": error})


@router.post("/collection/jobs/{job_id}/run")
def collection_process_job(job_id: int):
    result = process_job(job_id)
    return RedirectResponse(f"/collection/jobs?message=已执行 {job_id}: {result.get('status')}", status_code=303)


@router.get("/collection/items", response_class=HTMLResponse)
def collection_items(request: Request, page: int = 1, processing_status: str = "", dedup_status: str = "", message: str = ""):
    rows, total = list_items(page=page, processing_status=processing_status, dedup_status=dedup_status)
    return templates.TemplateResponse(
        request,
        "v05f_collection.html",
        {"mode": "items", "items": rows, "total": total, "page": page, "processing_status": processing_status, "dedup_status": dedup_status, "message": message},
    )


@router.get("/collection/items/{item_id}", response_class=HTMLResponse)
def collection_item_detail(request: Request, item_id: int):
    rows, _ = list_items(page=1, page_size=200)
    item = next((row for row in rows if row["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="原始情报不存在")
    snapshot = snapshot_detail(item["snapshot_id"]) if item.get("snapshot_id") else None
    return templates.TemplateResponse(request, "v05f_collection.html", {"mode": "item_detail", "item": item, "snapshot": snapshot})


@router.get("/collection/snapshots/{snapshot_id}", response_class=HTMLResponse)
def collection_snapshot(request: Request, snapshot_id: int):
    snapshot = snapshot_detail(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="来源快照不存在")
    return templates.TemplateResponse(request, "v05f_collection.html", {"mode": "snapshot", "snapshot": snapshot})


@router.post("/collection/run-now")
def collection_run_now(request: Request):
    result = run_scheduler_once()
    processed = result.get("processed", 0)
    msg = f"已执行 {processed} 个采集任务"
    return RedirectResponse(f"/collection?message={msg}", status_code=303)


@router.get("/v05f/health")
def health():
    data = dashboard()
    return {"ok": True, "version": "0.5F", "counts": data["counts"]}

