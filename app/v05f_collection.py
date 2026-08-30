from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.services.collection_service import (
    collection_item_delete_preview,
    collection_chain_delete_preview,
    create_collection_source,
    create_job,
    dashboard,
    delete_collection_item_safely,
    delete_collection_chain_safely,
    delete_or_retire_source,
    discover_source_candidates,
    list_items,
    list_jobs,
    list_sources,
    process_job,
    preview_source_import,
    snapshot_detail,
    save_source_import,
    set_source_enabled,
    source_detail,
    test_source_url,
    update_collection_source,
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

@router.get("/collection/sources/new", response_class=HTMLResponse)
def collection_source_new(request: Request):
    return templates.TemplateResponse(
        request, "v05f_collection.html",
        {"mode": "source_form", "form_data": {"source_type": "webpage", "collection_mode": "auto",
         "check_frequency": "weekly", "is_enabled": True}, "test_result": None},
    )


@router.post("/collection/sources/test", response_class=HTMLResponse)
async def collection_test_source(request: Request):
    form = await request.form()
    data = {key: form.get(key, "") for key in (
        "name", "url", "source_type", "collection_mode", "check_frequency", "subject_type", "subject_id"
    )}
    data["is_enabled"] = bool(form.get("is_enabled"))
    result = test_source_url(str(data["url"]))
    if result.get("ok"):
        data["source_type"] = "rss" if result.get("is_rss") else ("dynamic_page" if result.get("needs_playwright") else "webpage")
        data["collection_mode"] = "rss" if result.get("is_rss") else ("playwright" if result.get("needs_playwright") else "http")
    return templates.TemplateResponse(
        request, "v05f_collection.html",
        {"mode": "source_form", "form_data": data, "test_result": result},
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
    check_frequency: str = Form("weekly"),
    is_enabled: str = Form(""),
    tested: str = Form(""),
):
    if tested != "1":
        return RedirectResponse("/collection/sources/new?error=请先测试来源URL", status_code=303)
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
            check_frequency=check_frequency,
            is_enabled=bool(is_enabled),
        )
    except Exception as exc:
        return RedirectResponse(f"/collection/sources?error={str(exc)[:200]}", status_code=303)
    return RedirectResponse(f"/collection/sources?message=来源已保存：{row['source_no']}", status_code=303)


@router.get("/collection/sources/{source_id:int}", response_class=HTMLResponse)
def collection_source_detail(request: Request, source_id: int):
    try:
        source = source_detail(source_id)
    except ValueError:
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

@router.get("/collection/sources/{source_id:int}/edit", response_class=HTMLResponse)
def collection_source_edit(request: Request, source_id: int):
    try:
        source = source_detail(source_id)
    except ValueError as exc:
        raise HTTPException(404, "采集来源不存在") from exc
    return templates.TemplateResponse(
        request, "v05f_collection.html",
        {"mode": "source_form", "form_data": source, "source": source, "test_result": None},
    )


@router.post("/collection/sources/{source_id:int}/edit")
async def collection_update_source(request: Request, source_id: int):
    form = await request.form()
    try:
        update_collection_source(source_id, dict(form))
    except ValueError as exc:
        return RedirectResponse(f"/collection/sources/{source_id}?error={str(exc)}", status_code=303)
    return RedirectResponse(f"/collection/sources/{source_id}?message=来源已更新", status_code=303)

@router.post("/collection/sources/{source_id:int}/test", response_class=HTMLResponse)
def collection_test_existing_source(request: Request, source_id: int):
    source = source_detail(source_id)
    return templates.TemplateResponse(
        request, "v05f_collection.html",
        {"mode": "source_detail", "source": source, "jobs": [], "items": [],
         "test_result": test_source_url(source["url"])},
    )

@router.post("/collection/sources/{source_id:int}/enabled")
def collection_toggle_source(source_id: int, enabled: str = Form("")):
    row = set_source_enabled(source_id, bool(enabled))
    message = "来源已启用" if row["is_enabled"] else "来源已停用"
    return RedirectResponse(f"/collection/sources?message={message}", status_code=303)

@router.post("/collection/sources/{source_id:int}/delete")
def collection_delete_source(source_id: int, confirm: str = Form("")):
    if confirm != "1":
        raise HTTPException(400, "请确认删除或退役")
    result = delete_or_retire_source(source_id)
    message = "来源已退役，历史情报保留" if result["action"] == "retired" else "来源已删除"
    return RedirectResponse(f"/collection/sources?message={message}", status_code=303)

@router.get("/collection/sources/import", response_class=HTMLResponse)
def collection_import_page(request: Request):
    return templates.TemplateResponse(
        request, "v05f_collection.html",
        {"mode": "source_import", "preview": [], "source_text": ""},
    )

@router.post("/collection/sources/import/preview", response_class=HTMLResponse)
async def collection_import_preview(
    request: Request, source_text: str = Form(""), csv_file: UploadFile | None = File(None),
):
    raw = source_text
    if csv_file and csv_file.filename:
        raw = (await csv_file.read()).decode("utf-8-sig", errors="replace")
    preview = preview_source_import(raw)
    return templates.TemplateResponse(
        request, "v05f_collection.html",
        {"mode": "source_import", "preview": preview, "source_text": raw},
    )

@router.post("/collection/sources/import/confirm")
def collection_import_confirm(request: Request, source_text: str = Form(...)):
    preview = preview_source_import(source_text)
    result = save_source_import(preview, current_username(request))
    message = (
        f"成功新增：{result['created']}；已存在：{result['exists']}；"
        f"无效URL：{result['invalid']}；测试失败：{result['failed']}"
    )
    return RedirectResponse(f"/collection/sources?message={message}", status_code=303)

@router.get("/collection/sources/discovery", response_class=HTMLResponse)
def collection_discovery_page(request: Request):
    return templates.TemplateResponse(
        request, "v05f_collection.html", {"mode": "source_discovery", "discovery": None},
    )

@router.post("/collection/sources/discovery", response_class=HTMLResponse)
def collection_discovery_run(
    request: Request, homepage_url: str = Form(...), organization_id: int = Form(0),
    organization_name: str = Form(""),
):
    result = discover_source_candidates(
        homepage_url, organization_id or None, organization_name,
        owner=current_username(request),
    )
    return templates.TemplateResponse(
        request, "v05f_collection.html", {"mode": "source_discovery", "discovery": result},
    )
@router.post("/collection/sources/{source_id:int}/run")
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


def _require_collection_delete_permission(request: Request) -> None:
    security = request.scope.get("security_context", {})
    permissions = set(security.get("permissions") or [])
    if not (security.get("can_manage_users") or "manage_users" in permissions or "manage_monitoring" in permissions):
        raise HTTPException(403, "仅管理员或采集运营人员可以删除原始采集记录")


@router.get("/collection/items/{item_id:int}/delete", response_class=HTMLResponse)
def collection_item_delete_page(request: Request, item_id: int, error: str = ""):
    _require_collection_delete_permission(request)
    try:
        preview = collection_chain_delete_preview(item_id)
    except ValueError as exc:
        raise HTTPException(404, "原始采集记录不存在") from exc
    return templates.TemplateResponse(request, "v05f_collection.html", {"mode": "item_delete", "preview": preview, "error": error})


@router.post("/collection/items/{item_id:int}/delete")
def collection_item_delete_confirm(request: Request, item_id: int):
    _require_collection_delete_permission(request)
    try:
        result = delete_collection_item_safely(item_id, actor=current_username(request))
    except ValueError as exc:
        raise HTTPException(404, "原始采集记录不存在") from exc
    if not result["deleted"]:
        reasons = "、".join(f"{key}={value}" for key, value in result["protected"].items())
        return RedirectResponse(f"/collection/items/{item_id}/delete?error=存在下游引用：{reasons}", 303)
    return RedirectResponse("/collection/items?message=原始采集记录已安全删除；Source和Snapshot均保留", 303)


@router.post("/collection/items/{item_id:int}/cleanup-chain")
def collection_item_cleanup_chain(request: Request, item_id: int, confirm: str = Form("")):
    _require_collection_delete_permission(request)
    if confirm != "1":
        raise HTTPException(400, "必须确认这是错误或测试采集链")
    try:
        result = delete_collection_chain_safely(item_id, actor=current_username(request))
    except ValueError as exc:
        raise HTTPException(404, "原始采集记录不存在") from exc
    if not result["deleted"]:
        reasons = "、".join(f"{key}={value}" for key, value in result["chain_protected"].items())
        return RedirectResponse(f"/collection/items/{item_id}/delete?error=整条链已有正式引用，不能清理：{reasons}", 303)
    return RedirectResponse("/collection/items?message=错误采集链已安全清理；Source和Snapshot均保留", 303)


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
