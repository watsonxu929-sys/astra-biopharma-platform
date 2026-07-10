from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analyzer import analyze_text
from .database import get_db
from .models import ActionItem, HistoricalEvent, Organization, RawIntelligence

router = APIRouter(prefix="/analyze", tags=["paste-analysis"])
templates = Jinja2Templates(directory="app/templates")


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _semi(value: str) -> list[str]:
    return [item.strip() for item in value.replace("；", ";").split(";") if item.strip()]


@router.get("/paste", response_class=HTMLResponse)
def paste_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="paste_analyze.html",
        context={"error": None},
    )


@router.post("/paste/preview", response_class=HTMLResponse)
def paste_preview(
    request: Request,
    text: str = Form(...),
    source_type: str = Form("人工录入"),
    source_url: str = Form(""),
    visibility: str = Form("内部"),
):
    text = text.strip()
    if len(text) < 20:
        return templates.TemplateResponse(
            request=request,
            name="paste_analyze.html",
            context={"error": "请至少粘贴20个字符。"},
            status_code=400,
        )
    result = analyze_text(text, source_type)
    return templates.TemplateResponse(
        request=request,
        name="paste_preview.html",
        context={
            "result": result,
            "raw_text": text,
            "source_type": source_type,
            "source_url": source_url,
            "visibility": visibility,
        },
    )


@router.post("/paste/confirm")
def paste_confirm(
    title: str = Form(...),
    event_date: str = Form(""),
    organizations: str = Form(""),
    event_type: str = Form("其他"),
    industry_tags: str = Form(""),
    amount: str = Form(""),
    facts: str = Form(""),
    potential_needs: str = Form(""),
    recommended_actions: str = Form(""),
    source_grade: str = Form("D"),
    confidence: str = Form("0"),
    review_reasons: str = Form(""),
    raw_text: str = Form(...),
    source_type: str = Form("人工录入"),
    source_url: str = Form(""),
    visibility: str = Form("内部"),
    create_event: str | None = Form(None),
    create_organization: str | None = Form(None),
    create_action: str | None = Form(None),
    db: Session = Depends(get_db),
):
    intelligence = RawIntelligence(
        title=title.strip() or "未命名情报",
        source_url=source_url.strip() or None,
        source_type=source_type,
        content=raw_text,
        visibility=visibility,
        review_status="待审核",
    )
    db.add(intelligence)

    event_external_id = None
    if create_event:
        event_external_id = f"EVT-AUTO-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:4].upper()}"
        fact_list = _lines(facts)
        summary_parts = fact_list[:]
        if amount.strip():
            summary_parts.append(f"涉及金额：{amount.strip()}")
        event = HistoricalEvent(
            external_id=event_external_id,
            event_date=event_date.strip() or None,
            name=title.strip() or "自动分析事件",
            event_type=event_type.strip() or "其他",
            related_entity=None,
            fact_summary="\n".join(summary_parts),
            system_use=(
                "潜在需求：" + "；".join(_semi(potential_needs)) + "\n"
                "建议动作：" + "\n".join(_lines(recommended_actions)) + "\n"
                f"来源等级：{source_grade}；分析置信度：{confidence}\n"
                "人工复核原因：" + "\n".join(_lines(review_reasons))
            ),
            visibility=visibility,
            verification_status="待核验",
        )
        db.add(event)

    if create_organization:
        for org_name in _lines(organizations):
            existing = db.scalar(
                select(Organization).where(Organization.standard_name == org_name)
            )
            if existing:
                continue
            org = Organization(
                external_id=f"ORG-AUTO-{uuid4().hex[:10].upper()}",
                standard_name=org_name,
                org_type="待分类",
                region=None,
                industry_tags="；".join(_semi(industry_tags)) or None,
                resources=None,
                needs="；".join(_semi(potential_needs)) or None,
                relationship_source="粘贴自动分析",
                visibility=visibility,
                verification_status="待核验",
            )
            db.add(org)

    if create_action:
        actions = _lines(recommended_actions)
        if not actions:
            actions = ["人工复核该条情报并确认下一步。"]
        for action_text in actions[:5]:
            db.add(ActionItem(
                external_id=f"ACT-AUTO-{uuid4().hex[:10].upper()}",
                task=action_text,
                target_external_id=event_external_id,
                completion_standard="完成需求核实、证据补充或资源对接，并记录结果。",
                owner="项目负责人",
                priority="P1",
                status="未开始",
                suggested_deadline=None,
            ))

    db.commit()
    return RedirectResponse(url="/intelligence", status_code=303)
