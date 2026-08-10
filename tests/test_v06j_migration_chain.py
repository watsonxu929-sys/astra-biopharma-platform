from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from app.services.schema_preflight import run_schema_preflight
from app.settings import Settings, resolved_db_path, sqlite_url_from_path
from scripts.migrate_db import MIGRATIONS, build_plan, inspect_database, run_upgrade


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_readonly(source: Path, target: Path) -> None:
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as src:
        with sqlite3.connect(target) as destination:
            src.backup(destination)


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _row_counts(conn: sqlite3.Connection, tables: set[str]) -> dict[str, int]:
    return {table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) for table in sorted(tables)}


def test_migration_registry_discovers_unique_ordered_000_through_011() -> None:
    numbers = [migration.number for migration in MIGRATIONS]
    ids = [migration.migration_id for migration in MIGRATIONS]
    assert numbers == [f"{number:03d}" for number in range(12)]
    assert len(ids) == len(set(ids))
    assert ids[-3:] == [
        "009_intelligence_production_loop",
        "010_intelligence_opportunity_loop",
        "011_feedback_outcome_loop",
    ]
    assert all(migration.path.exists() for migration in MIGRATIONS)


def test_plan_is_readonly_and_does_not_create_database(tmp_path: Path) -> None:
    database = tmp_path / "plan_only.db"
    result = inspect_database(database, "008")
    assert result["database_exists"] is False
    assert result["plan"]["target"] == "008_business_collaboration_mvp"
    assert not database.exists()


def test_empty_database_upgrades_to_008_without_business_seed_and_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "empty_chain.db"
    result = run_upgrade(database, target="008")
    assert result["status"] == "success"
    with sqlite3.connect(database) as conn:
        plan = build_plan(conn, "008")
        assert plan["has_drift"] is False
        assert all(step["action"] == "skip" for step in plan["steps"])
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        business_tables = {
            table for table in _tables(conn)
            if table.startswith(("p2_3_", "p4_", "p5_"))
        }
        assert all(count == 0 for count in _row_counts(conn, business_tables).values())
        assert conn.execute("SELECT COUNT(*) FROM p3_relationship_type_registry").fetchone()[0] > 0
        assert conn.execute(
            "SELECT COUNT(*) FROM platform_migration_runs WHERE status='success'"
        ).fetchone()[0] == len([item for item in MIGRATIONS if item.number <= "008"])
    before = _hash(database)
    second = run_upgrade(database, target="008")
    assert second["status"] == "up_to_date"
    assert _hash(database) == before


def test_failed_migration_rolls_back_and_is_not_marked_success(tmp_path: Path) -> None:
    database = tmp_path / "failure.db"

    def fail_004(migration, _conn) -> None:
        if migration.number == "004":
            raise RuntimeError("intentional_failure")

    with pytest.raises(RuntimeError, match="intentional_failure"):
        run_upgrade(database, target="004", failure_hook=fail_004)
    with sqlite3.connect(database) as conn:
        assert "p2_2_evaluation_runs" not in _tables(conn)
        assert conn.execute(
            "SELECT COUNT(*) FROM platform_migration_runs WHERE migration_id=? AND status='success'",
            ("004_real_source_quality_evaluation",),
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM platform_migration_runs WHERE migration_id=? AND status='failed'",
            ("004_real_source_quality_evaluation",),
        ).fetchone()[0] == 1
    assert run_upgrade(database, target="004")["status"] == "success"


def test_formal_database_copy_upgrades_without_changing_old_rows(tmp_path: Path) -> None:
    formal = resolved_db_path().resolve()
    if not formal.exists():
        pytest.skip("formal database is unavailable")
    database = tmp_path / "formal_copy.db"
    _copy_readonly(formal, database)
    with sqlite3.connect(database) as conn:
        old_tables = _tables(conn) - {"sqlite_sequence", "platform_migration_runs"}
        before_counts = _row_counts(conn, old_tables)
        before_fk = {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")}
    result = run_upgrade(database, target="008")
    assert result["status"] == "success"
    with sqlite3.connect(database) as conn:
        assert _row_counts(conn, old_tables) == before_counts
        assert {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")} == before_fk
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute(
            "SELECT COUNT(*) FROM platform_migration_runs WHERE status='success'"
        ).fetchone()[0] == len([item for item in MIGRATIONS if item.number <= "008"])
    settings = Settings(app_env="testing", database_url=sqlite_url_from_path(database))
    preflight = run_schema_preflight(settings)
    for capability in ("research_fusion", "industry_relationships", "club_operations", "business_collaboration"):
        assert preflight.capability(capability).enabled, preflight.capability(capability).public_dict()


def test_runtime_entrypoints_do_not_reference_migration_runner() -> None:
    for relative in ("app/main.py", "scripts/run_scheduler.py", "scripts/run_worker.py"):
        source = (Path(__file__).parents[1] / relative).read_text(encoding="utf-8")
        assert "migrate_db" not in source
        assert "migrate_all" not in source
        assert "metadata.create_all" not in source
