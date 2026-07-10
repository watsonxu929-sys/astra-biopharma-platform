from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.services.monitoring_service import (
    create_source,
    due_sources,
    ensure_schema,
    list_data,
    review_proposal,
    run_source,
    subject_options,
)
from app.v04c_review import db_connection, default_db_path

router = APIRouter(tags=["v0.4G 情报监测"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@router.get("/intelligence/monitoring", response_class=HTMLResponse)
def monitoring_home(request: Request):
    data = list_data()
    return templates.TemplateResponse(request, "v04g_monitoring.html", {"mode": "home", **data})


@router.get("/intelligence/monitoring/sources", response_class=HTMLResponse)
def monitoring_sources(request: Request, page: int = 1, message: str = "", error: str = ""):
    data = list_data(page=page)
    return templates.TemplateResponse(
        request,
        "v04g_monitoring.html",
        {"mode": "sources", **data, "subjects": subject_options(), "message": message, "error": error},
    )


@router.post("/intelligence/monitoring/sources")
def create_monitoring_source(
    request: Request,
    name: str = Form(...),
    source_type: str = Form("other_web"),
    url: str = Form(...),
    subject_type: str = Form(""),
    subject_id: str = Form(""),
    check_frequency: str = Form("manual"),
    fetch_mode: str = Form("web"),
    owner: str = Form(""),
    note: str = Form(""),
):
    owner = owner.strip() or current_username(request)
    try:
        row = create_source(name, source_type, url, subject_type, subject_id, check_frequency, fetch_mode, owner, note)
    except ValueError as exc:
        return RedirectResponse(f"/intelligence/monitoring/sources?error={str(exc)}", status_code=303)
    return RedirectResponse(f"/intelligence/monitoring/sources?message=已保存监测源 {row['source_no']}", status_code=303)


@router.post("/intelligence/monitoring/sources/{source_id}/run")
def run_monitoring_source(source_id: int, manual_text: str = Form("")):
    result = run_source(source_id, manual_text=manual_text)
    status = result.get("status", "")
    return RedirectResponse(
        f"/intelligence/monitoring/runs?message=执行完成：{status}",
        status_code=303,
    )


@router.post("/intelligence/monitoring/sources/batch-run")
async def run_monitoring_sources(request: Request):
    form = await request.form()
    ids = []
    for raw in form.getlist("source_ids")[:50]:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    done = 0
    failed = 0
    for source_id in ids:
        result = run_source(source_id)
        done += 1
        if result.get("status") == "failed":
            failed += 1
    return RedirectResponse(f"/intelligence/monitoring/runs?message=已执行 {done} 条，失败 {failed} 条", status_code=303)


@router.get("/intelligence/monitoring/runs", response_class=HTMLResponse)
def monitoring_runs(request: Request, page: int = 1, message: str = ""):
    data = list_data(page=page)
    return templates.TemplateResponse(request, "v04g_monitoring.html", {"mode": "runs", **data, "message": message})


@router.get("/intelligence/monitoring/proposals", response_class=HTMLResponse)
def monitoring_proposals(request: Request, page: int = 1, status: str = "", message: str = ""):
    data = list_data(page=page, status=status)
    return templates.TemplateResponse(request, "v04g_monitoring.html", {"mode": "proposals", **data, "message": message})


@router.post("/intelligence/monitoring/proposals/{proposal_id}/review")
def review_monitoring_proposal(
    request: Request,
    proposal_id: int,
    decision: str = Form(...),
    reviewer: str = Form("manual"),
    final_value: str = Form(""),
    note: str = Form(""),
):
    reviewer = current_username(request)
    try:
        result = review_proposal(proposal_id, decision, reviewer, final_value, note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(
        f"/intelligence/monitoring/proposals?message=处理完成：{result['status']}",
        status_code=303,
    )


@router.get("/intelligence/monitoring/snapshots/{snapshot_id}", response_class=HTMLResponse)
def monitoring_snapshot(snapshot_id: int, request: Request):
    ensure_schema()
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT sn.*, s.name AS source_name
            FROM v04g_source_snapshots sn
            JOIN v04g_monitoring_sources s ON s.id=sn.monitoring_source_id
            WHERE sn.id=?
            """,
            (snapshot_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="快照不存在")
    return templates.TemplateResponse(request, "v04g_monitoring.html", {"mode": "snapshot", "snapshot": dict(row)})


@router.get("/v04g/health")
def health():
    path = default_db_path()
    required = {
        "v04g_monitoring_sources",
        "v04g_monitoring_runs",
        "v04g_source_snapshots",
        "v04g_update_proposals",
        "v04g_update_apply_logs",
    }
    with db_connection(path) as conn:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v04g_%'").fetchall()
        }
    return {"ok": required.issubset(tables), "version": "0.4G", "database": str(path), "v04g_table_count": len(tables)}
