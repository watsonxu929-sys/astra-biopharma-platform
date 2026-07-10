from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import current_username
from app.services.research import (
    add_topic_subject,
    approve_assessment,
    compare_companies,
    convert_assessment_to_lead,
    create_company_compare_report,
    create_topic,
    create_topic_report,
    generate_assessment,
    get_assessment,
    list_assessments,
    list_topics,
    refresh_topic,
    reject_assessment,
    topic_dashboard,
    topic_network,
    topic_signals,
    topic_timeline,
    tracks,
    track_detail,
)

router = APIRouter(tags=["v0.5J research"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@router.get("/research", response_class=HTMLResponse)
def research_home(request: Request):
    return templates.TemplateResponse(request, "v05j_research.html", {"mode": "home", "topics": list_topics(page_size=8), "tracks": tracks()})


@router.get("/research/topics", response_class=HTMLResponse)
def research_topics(request: Request, page: int = 1, status: str = "", message: str = "", error: str = ""):
    return templates.TemplateResponse(request, "v05j_research.html", {"mode": "topics", "result": list_topics(page=page, status=status), "message": message, "error": error})


@router.get("/research/topics/new", response_class=HTMLResponse)
def research_topic_new(request: Request):
    return templates.TemplateResponse(request, "v05j_research.html", {"mode": "new_topic"})


@router.post("/research/topics")
def research_topic_create(name: str = Form(...), description: str = Form(""), topic_type: str = Form("custom"), track_tags: str = Form(""), region_filters: str = Form("")):
    topic = create_topic(name=name, description=description, topic_type=topic_type, track_tags=track_tags, region_filters=region_filters)
    return RedirectResponse(f"/research/topics/{topic['id']}?message=created", status_code=303)


@router.get("/research/topics/{topic_id:int}", response_class=HTMLResponse)
def research_topic_detail(request: Request, topic_id: int, message: str = "", error: str = ""):
    return _topic_response(request, topic_id, "detail", message, error)


@router.get("/research/topics/{topic_id:int}/dashboard", response_class=HTMLResponse)
def research_topic_dashboard(request: Request, topic_id: int):
    return _topic_response(request, topic_id, "dashboard")


@router.get("/research/topics/{topic_id:int}/subjects", response_class=HTMLResponse)
def research_topic_subjects(request: Request, topic_id: int):
    return _topic_response(request, topic_id, "subjects")


@router.post("/research/topics/{topic_id:int}/subjects")
def research_add_subject(request: Request, topic_id: int, subject_type: str = Form(...), subject_id: str = Form(...), reason: str = Form("")):
    try:
        add_topic_subject(topic_id, subject_type, subject_id, reason=reason, added_by=current_username(request))
        return RedirectResponse(f"/research/topics/{topic_id:int}?message=subject-added", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/research/topics/{topic_id:int}?error={str(exc)[:120]}", status_code=303)


@router.post("/research/topics/{topic_id:int}/refresh")
def research_refresh(topic_id: int):
    refresh_topic(topic_id)
    return RedirectResponse(f"/research/topics/{topic_id:int}/dashboard?message=refreshed", status_code=303)


@router.get("/research/topics/{topic_id:int}/events", response_class=HTMLResponse)
def research_topic_events(request: Request, topic_id: int):
    return _topic_response(request, topic_id, "timeline")


@router.get("/research/topics/{topic_id:int}/signals", response_class=HTMLResponse)
def research_topic_signal_page(request: Request, topic_id: int):
    return _topic_response(request, topic_id, "signals")


@router.get("/research/topics/{topic_id:int}/reports", response_class=HTMLResponse)
def research_topic_reports(request: Request, topic_id: int):
    return _topic_response(request, topic_id, "reports")


@router.post("/research/topics/{topic_id:int}/reports")
def research_topic_report_create(request: Request, topic_id: int):
    try:
        report = create_topic_report(topic_id, created_by=current_username(request))
        return RedirectResponse(f"/reports/{report['id']}?message=research-report-generated", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/research/topics/{topic_id:int}?error={str(exc)[:120]}", status_code=303)


@router.get("/research/companies/compare", response_class=HTMLResponse)
def companies_compare_page(request: Request, organization_ids: str = "", error: str = ""):
    result = None
    if organization_ids.strip():
        try:
            ids = [x.strip() for x in organization_ids.replace("；", ",").replace(";", ",").split(",") if x.strip()]
            result = compare_companies(ids)
        except Exception as exc:
            error = str(exc)
    return templates.TemplateResponse(request, "v05j_research.html", {"mode": "compare", "result": result, "organization_ids": organization_ids, "error": error})


@router.post("/research/companies/compare/report")
def companies_compare_report_create(request: Request, organization_ids: str = Form("")):
    try:
        ids = [x.strip() for x in organization_ids.replace("；", ",").replace(";", ",").split(",") if x.strip()]
        report = create_company_compare_report(ids, created_by=current_username(request))
        return RedirectResponse(f"/reports/{report['id']}?message=compare-report-generated", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/research/companies/compare?organization_ids={organization_ids}&error={str(exc)[:120]}", status_code=303)


@router.get("/research/tracks", response_class=HTMLResponse)
def research_tracks(request: Request, window: str = "30d"):
    return templates.TemplateResponse(request, "v05j_research.html", {"mode": "tracks", "tracks": tracks(window=window), "window": window})


@router.get("/research/tracks/{track_key}", response_class=HTMLResponse)
def research_track_detail(request: Request, track_key: str, window: str = "30d"):
    return templates.TemplateResponse(request, "v05j_research.html", {"mode": "track_detail", "track": track_detail(track_key, window=window)})


@router.get("/research/investment", response_class=HTMLResponse)
def investment_page(request: Request, status: str = "", message: str = "", error: str = ""):
    return templates.TemplateResponse(request, "v05j_research.html", {"mode": "investment", "result": list_assessments(status=status), "message": message, "error": error})


@router.post("/research/investment")
def investment_create(organization_id: str = Form(...), topic_id: int = Form(0)):
    try:
        row = generate_assessment(organization_id, topic_id=topic_id or None)
        return RedirectResponse(f"/research/investment/{row['id']}?message=created", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/research/investment?error={str(exc)[:120]}", status_code=303)


@router.get("/research/investment/{assessment_id}", response_class=HTMLResponse)
def investment_detail(request: Request, assessment_id: int, message: str = "", error: str = ""):
    row = get_assessment(assessment_id)
    if not row:
        raise HTTPException(status_code=404, detail="assessment not found")
    return templates.TemplateResponse(request, "v05j_research.html", {"mode": "assessment_detail", "assessment": row, "message": message, "error": error})


@router.post("/research/investment/{assessment_id}/approve")
def investment_approve(request: Request, assessment_id: int):
    approve_assessment(assessment_id, actor=current_username(request))
    return RedirectResponse(f"/research/investment/{assessment_id}?message=ok", status_code=303)


@router.post("/research/investment/{assessment_id}/reject")
def investment_reject(request: Request, assessment_id: int):
    reject_assessment(assessment_id, actor=current_username(request))
    return RedirectResponse(f"/research/investment/{assessment_id}?message=ok", status_code=303)


@router.post("/research/investment/{assessment_id}/convert-lead")
def investment_convert(request: Request, assessment_id: int):
    try:
        convert_assessment_to_lead(assessment_id, actor=current_username(request))
        return RedirectResponse(f"/research/investment/{assessment_id}?message=ok", status_code=303)
    except Exception as exc:
        return RedirectResponse(f"/research/investment/{assessment_id}?error={str(exc)[:120]}", status_code=303)


@router.get("/v05j/health")
def health():
    return {"ok": True, "version": "0.5J"}


def _topic_response(request: Request, topic_id: int, mode: str, message: str = "", error: str = ""):
    topic = topic_dashboard(topic_id)
    timeline = topic_timeline(topic_id)
    signals = topic_signals(topic_id)
    network = topic_network(topic_id)
    return templates.TemplateResponse(request, "v05j_research.html", {"mode": mode, "topic_id": topic_id, "dashboard": topic, "timeline": timeline, "signals": signals, "network": network, "message": message, "error": error})





