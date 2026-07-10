from __future__ import annotations

from pathlib import Path
from typing import Any

from app.v04c_review import db_connection
from scripts.migrate_v05h import migrate as migrate_v05h


def ensure_schema(db_path: str | Path | None = None) -> None:
    migrate_v05h(Path(db_path) if db_path else None, backup=False) if db_path else migrate_v05h(backup=False)


def list_rules(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM v05h_signal_rules ORDER BY is_enabled DESC, id").fetchall()]


def set_rule_enabled(rule_id: int, enabled: bool, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05h_signal_rules WHERE id=?", (rule_id,)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE v05h_signal_rules SET is_enabled=?, updated_at=datetime('now','localtime') WHERE id=?", (1 if enabled else 0, rule_id))
        return dict(conn.execute("SELECT * FROM v05h_signal_rules WHERE id=?", (rule_id,)).fetchone())


def signal_dashboard(db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        counts = {
            "total": conn.execute("SELECT COUNT(*) FROM v05e_industry_signals").fetchone()[0],
            "new": conn.execute("SELECT COUNT(*) FROM v05e_industry_signals WHERE status='new'").fetchone()[0],
            "important": conn.execute("SELECT COUNT(*) FROM v05e_industry_signals WHERE status='important' OR COALESCE(is_important,0)=1").fetchone()[0],
            "high": conn.execute("SELECT COUNT(*) FROM v05e_industry_signals WHERE signal_level IN ('critical','high')").fetchone()[0],
            "risk": conn.execute("SELECT COUNT(*) FROM v05e_industry_signals WHERE signal_category='risk_exception' OR signal_type='risk'").fetchone()[0],
            "converted": conn.execute("SELECT COUNT(*) FROM v05e_industry_signals WHERE status='converted'").fetchone()[0],
        }
        by_type = [dict(r) for r in conn.execute("SELECT signal_type, COUNT(*) AS count FROM v05e_industry_signals GROUP BY signal_type ORDER BY count DESC LIMIT 12").fetchall()]
        latest = [dict(r) for r in conn.execute("SELECT * FROM v05e_industry_signals ORDER BY discovered_at DESC, id DESC LIMIT 10").fetchall()]
    return {"counts": counts, "by_type": by_type, "latest": latest}
