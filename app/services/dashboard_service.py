from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.signal_service import ensure_schema
from app.v04c_review import db_connection


def _count(conn, sql: str, params: tuple[Any, ...] = ()) -> int:
    try:
        return int(conn.execute(sql, params).fetchone()[0] or 0)
    except Exception:
        return 0


def dashboard_data(*, days: int = 7, industry: str = "", region: str = "", signal_level: str = "", watchlist_id: int | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    days = max(1, min(int(days or 7), 90))
    since = (datetime.now() - timedelta(days=days)).replace(microsecond=0).isoformat()
    with db_connection(db_path) as conn:
        industry_like = f"%{industry.strip()}%"
        region_like = f"%{region.strip()}%"
        org_filter = []
        params: list[Any] = []
        if industry.strip():
            org_filter.append("COALESCE(industry_tags,'') LIKE ?")
            params.append(industry_like)
        if region.strip():
            org_filter.append("COALESCE(region,'') LIKE ?")
            params.append(region_like)
        org_where = " AND ".join(org_filter) if org_filter else "1=1"
        signal_where = "discovered_at>=?"
        signal_params: list[Any] = [since]
        if signal_level:
            signal_where += " AND signal_level=?"
            signal_params.append(signal_level)
        counts = {
            "today_intelligence": _count(conn, "SELECT COUNT(*) FROM raw_intelligence WHERE date(created_at)=date('now','localtime')"),
            "today_changes": _count(conn, "SELECT COUNT(*) FROM v04g_monitoring_runs WHERE changed=1 AND date(created_at)=date('now','localtime')"),
            "recent_events": _count(conn, "SELECT COUNT(*) FROM events WHERE COALESCE(is_active,1)=1 AND created_at>=?", (since,)),
            "high_signals": _count(conn, f"SELECT COUNT(*) FROM v05e_industry_signals WHERE {signal_where} AND signal_level IN ('critical','high')", tuple(signal_params)),
            "pending_proposals": _count(conn, "SELECT COUNT(*) FROM v04g_update_proposals WHERE status IN ('pending','under_review')"),
            "failed_sources": _count(conn, "SELECT COUNT(*) FROM v04g_monitoring_sources WHERE consecutive_failures>0"),
            "new_organizations": _count(conn, f"SELECT COUNT(*) FROM organizations WHERE created_at>=? AND {org_where}", tuple([since, *params])),
            "new_people": _count(conn, "SELECT COUNT(*) FROM people WHERE created_at>=?", (since,)),
            "new_projects": _count(conn, "SELECT COUNT(*) FROM projects WHERE created_at>=?", (since,)),
            "new_leads": _count(conn, "SELECT COUNT(*) FROM v04f_lead_records WHERE created_at>=?", (since,)),
            "conflicts": _count(conn, "SELECT COUNT(*) FROM v04c_review_items WHERE item_type='conflict' AND status IN ('pending','in_review','deferred')"),
            "overdue_actions": _count(conn, "SELECT COUNT(*) FROM actions WHERE COALESCE(is_active,1)=1 AND suggested_deadline IS NOT NULL AND suggested_deadline<date('now') AND status NOT IN ('已完成','completed','done')"),
        }
        signal_rows = [dict(r) for r in conn.execute("SELECT signal_type,COUNT(*) AS count FROM v05e_industry_signals WHERE discovered_at>=? GROUP BY signal_type ORDER BY count DESC", (since,)).fetchall()]
        active_regions = [dict(r) for r in conn.execute("SELECT region,COUNT(*) AS count FROM organizations WHERE region IS NOT NULL AND region<>'' GROUP BY region ORDER BY count DESC LIMIT 10").fetchall()]
        active_industries = [dict(r) for r in conn.execute("SELECT industry_tags AS industry,COUNT(*) AS count FROM organizations WHERE industry_tags IS NOT NULL AND industry_tags<>'' GROUP BY industry_tags ORDER BY count DESC LIMIT 10").fetchall()]
        recent_signals = [dict(r) for r in conn.execute("SELECT * FROM v05e_industry_signals ORDER BY discovered_at DESC,id DESC LIMIT 10").fetchall()]
        pending = [dict(r) for r in conn.execute("SELECT proposal_no,subject_type,subject_id,field_name,status,created_at FROM v04g_update_proposals WHERE status IN ('pending','under_review') ORDER BY id DESC LIMIT 10").fetchall()]
    return {
        "filters": {"days": days, "industry": industry, "region": region, "signal_level": signal_level, "watchlist_id": watchlist_id},
        "counts": counts,
        "trends": {"signal_types": signal_rows, "active_regions": active_regions, "active_industries": active_industries},
        "drilldowns": {
            "high_signals": "/signals?signal_level=high",
            "pending_proposals": "/intelligence/monitoring/proposals?status=pending",
            "overdue_actions": "/actions",
            "failed_sources": "/intelligence/monitoring/sources",
        },
        "recent_signals": recent_signals,
        "pending_proposals": pending,
    }
