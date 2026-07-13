from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.services.research import (
    ResearchAgentService,
    add_research_question,
    compare_companies_research,
    compare_track_research,
    create_finding,
    create_research_report,
    event_timeline,
    get_event,
    get_research_report,
    list_conflicts,
    publish_research_report,
    resolve_conflict,
    review_finding,
    review_research_report,
    submit_finding,
    submit_research_report,
    topic_workspace,
)

router = APIRouter(tags=["P2.3 research fusion"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@router.get("/research/topics/{topic_id}/workspace", response_class=HTMLResponse)
def workspace_page(request: Request, topic_id: int, message: str = "", error: str = ""):
    try:
        workspace = topic_workspace(topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request,
        "p2_3_research.html",
        {"mode": "workspace", "workspace": workspace, "topic_id": topic_id, "message": message, "error": error},
    )


@router.post("/research/topics/{topic_id}/questions")
def question_create(request: Request, topic_id: int, question: str = Form(...)):
    add_research_question(topic_id, question, actor=current_username(request))
    return RedirectResponse(f"/research/topics/{topic_id}/workspace?message=question-added", status_code=303)


@router.post("/research/topics/{topic_id}/findings")
def finding_create(
    request: Request,
    topic_id: int,
    finding_type: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    assertion_ids: str = Form(""),
):
    ids = [int(value.strip()) for value in assertion_ids.replace("，", ",").split(",") if value.strip().isdigit()]
    create_finding(
        topic_id,
        finding_type=finding_type,
        title=title,
        content=content,
        assertion_ids=ids,
        actor=current_username(request),
    )
    return RedirectResponse(f"/research/topics/{topic_id}/workspace?message=finding-created", status_code=303)


@router.post("/research/findings/{finding_id}/submit")
def finding_submit(request: Request, finding_id: int, topic_id: int = Form(...)):
    submit_finding(finding_id, actor=current_username(request))
    return RedirectResponse(f"/research/topics/{topic_id}/workspace?message=finding-submitted", status_code=303)


@router.post("/research/findings/{finding_id}/review")
def finding_review(
    request: Request,
    finding_id: int,
    topic_id: int = Form(...),
    decision: str = Form(...),
    note: str = Form(""),
):
    review_finding(finding_id, decision=decision, actor=current_username(request), note=note)
    return RedirectResponse(f"/research/topics/{topic_id}/workspace?message=finding-reviewed", status_code=303)


@router.post("/research/topics/{topic_id}/agent-draft")
def agent_draft(request: Request, topic_id: int, provider_name: str = Form("rule")):
    result = ResearchAgentService().generate_draft(
        topic_id, provider_name=provider_name, actor=current_username(request)
    )
    return RedirectResponse(
        f"/research/topics/{topic_id}/workspace?message=agent-{result['status']}", status_code=303
    )


@router.get("/research/events", response_class=HTMLResponse)
def timeline_page(request: Request, event_type: str = ""):
    return templates.TemplateResponse(
        request,
        "p2_3_research.html",
        {"mode": "timeline", "events": event_timeline(event_type=event_type), "event_type": event_type},
    )


@router.get("/research/events/{event_id}", response_class=HTMLResponse)
def event_detail_page(request: Request, event_id: int):
    event = get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="industry event not found")
    return templates.TemplateResponse(request, "p2_3_research.html", {"mode": "event", "event": event})


@router.get("/research/conflicts", response_class=HTMLResponse)
def conflict_page(request: Request, topic_id: int = 0, status: str = "", message: str = ""):
    return templates.TemplateResponse(
        request,
        "p2_3_research.html",
        {
            "mode": "conflicts",
            "conflicts": list_conflicts(topic_id=topic_id or None, status=status),
            "topic_id": topic_id,
            "status": status,
            "message": message,
        },
    )


@router.post("/research/conflicts/{conflict_id}/resolve")
def conflict_resolve(
    request: Request,
    conflict_id: int,
    adopted_value: str = Form(...),
    reason: str = Form(...),
):
    resolve_conflict(
        conflict_id,
        adopted_value=adopted_value,
        reason=reason,
        actor=current_username(request),
    )
    return RedirectResponse("/research/conflicts?message=conflict-resolved", status_code=303)


@router.get("/research/findings", response_class=HTMLResponse)
def findings_page(request: Request, topic_id: int):
    return templates.TemplateResponse(
        request,
        "p2_3_research.html",
        {"mode": "findings", "workspace": topic_workspace(topic_id), "topic_id": topic_id},
    )


@router.get("/research/companies/compare-v2", response_class=HTMLResponse)
def compare_page(request: Request, organization_ids: str = "", error: str = ""):
    result = None
    if organization_ids.strip():
        try:
            ids = [value.strip() for value in organization_ids.replace("，", ",").replace(";", ",").split(",") if value.strip()]
            result = compare_companies_research(ids)
        except ValueError as exc:
            error = str(exc)
    return templates.TemplateResponse(
        request,
        "p2_3_research.html",
        {"mode": "compare", "result": result, "organization_ids": organization_ids, "error": error},
    )


@router.get("/research/tracks/{track_key}/comparison", response_class=HTMLResponse)
def track_comparison_page(request: Request, track_key: str):
    return templates.TemplateResponse(
        request,
        "p2_3_research.html",
        {"mode": "track", "track": compare_track_research(track_key)},
    )


@router.post("/research/topics/{topic_id}/research-reports")
def report_create(request: Request, topic_id: int, report_type: str = Form("topic_report")):
    report = create_research_report(
        topic_id, report_type=report_type, created_by=current_username(request)
    )
    return RedirectResponse(
        f"/research/reports/{report['id']}/review?message=report-created", status_code=303
    )


@router.get("/research/reports/{report_id}/review", response_class=HTMLResponse)
def report_review_page(request: Request, report_id: int, message: str = "", error: str = ""):
    report = get_research_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="research report not found")
    return templates.TemplateResponse(
        request,
        "p2_3_research.html",
        {"mode": "report", "report": report, "message": message, "error": error},
    )


@router.post("/research/reports/{report_id}/submit")
def report_submit(request: Request, report_id: int):
    submit_research_report(report_id, actor=current_username(request))
    return RedirectResponse(
        f"/research/reports/{report_id}/review?message=report-submitted", status_code=303
    )


@router.post("/research/reports/{report_id}/review")
def report_review(
    request: Request,
    report_id: int,
    decision: str = Form(...),
    note: str = Form(""),
):
    review_research_report(
        report_id, decision=decision, actor=current_username(request), note=note
    )
    return RedirectResponse(
        f"/research/reports/{report_id}/review?message=report-reviewed", status_code=303
    )


@router.post("/research/reports/{report_id}/publish")
def report_publish(request: Request, report_id: int):
    publish_research_report(report_id, actor=current_username(request))
    return RedirectResponse(f"/reports/{report_id}?message=report-published", status_code=303)
