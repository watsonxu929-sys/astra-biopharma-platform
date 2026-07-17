from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / "scripts/migrations/006_entity_relationship_network.py",
    ROOT / "scripts/migrations/007_club_operations_mvp.py",
)
CRITICAL_TABLES = (
    "v06_opportunities",
    "v05a_users",
    "people",
    "organizations",
    "v04f_club_memberships",
    "events",
    "v06_market_resources",
)


def _source_copy() -> Path:
    value = os.getenv("CORE06M_R2_PRODUCTION_COPY", "").strip()
    if not value:
        pytest.skip("CORE06M_R2_PRODUCTION_COPY is required for production compatibility acceptance")
    source = Path(value).resolve()
    if not source.is_file():
        pytest.fail(f"production acceptance copy does not exist: {source.name}")
    return source


def _clone(source: Path, target: Path) -> None:
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as src:
        with sqlite3.connect(target) as dst:
            src.backup(dst)


def _migrate(path: Path, *, repeat: int = 1) -> None:
    for _ in range(repeat):
        for migration in MIGRATIONS:
            subprocess.run(
                [sys.executable, str(migration), "--apply", "--db", str(path)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) for table in CRITICAL_TABLES}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def production_copy(tmp_path: Path) -> Path:
    target = tmp_path / "core06m_r2_production_copy.db"
    _clone(_source_copy(), target)
    return target


@pytest.fixture
def migrated_production_copy(production_copy: Path) -> Path:
    _migrate(production_copy)
    return production_copy


def _configure_app(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("APP_DB_PATH", str(path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path.as_posix()}")
    monkeypatch.setenv("APP_AUTH_DISABLED", "1")
    monkeypatch.setenv("APP_ENABLE_SCHEDULER", "0")
    monkeypatch.setenv("APP_ENABLE_WORKER", "0")


def test_production_copy_uses_events_as_authoritative_date_and_migrations_are_idempotent(
    production_copy: Path,
):
    with sqlite3.connect(production_copy) as conn:
        before = _counts(conn)
        before_foreign_keys = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        assert "event_date" not in _columns(conn, "v05c_club_event_profiles")
        assert "event_date" in _columns(conn, "events")
        assert conn.execute("SELECT COUNT(*) FROM v06_opportunities").fetchone()[0] == 11

    _migrate(production_copy, repeat=2)

    with sqlite3.connect(production_copy) as conn:
        assert "event_date" not in _columns(conn, "v05c_club_event_profiles")
        assert "event_date" in _columns(conn, "events")
        assert _counts(conn) == before
        assert len(conn.execute("PRAGMA foreign_key_check").fetchall()) == before_foreign_keys
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    source = (ROOT / "app/v04f_operations.py").read_text(encoding="utf-8")
    assert "v05c_club_event_profiles WHERE event_date" not in source
    assert "FROM v05c_club_event_profiles p" in source
    assert "JOIN events e ON e.id=p.event_id" in source


def test_known_historical_variant_with_profile_event_date_remains_repeatable(production_copy: Path):
    with sqlite3.connect(production_copy) as conn:
        conn.execute("ALTER TABLE v05c_club_event_profiles ADD COLUMN event_date TEXT")
        conn.execute("UPDATE v05c_club_event_profiles SET event_date=NULL")
        conn.commit()
    _migrate(production_copy, repeat=2)
    with sqlite3.connect(production_copy) as conn:
        assert "event_date" in _columns(conn, "v05c_club_event_profiles")
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM v06_opportunities").fetchone()[0] == 11


def test_007_forced_failure_rolls_back_the_production_copy(production_copy: Path, monkeypatch: pytest.MonkeyPatch):
    migration = MIGRATIONS[1]
    spec = importlib.util.spec_from_file_location("core06m_r2_migration_007", migration)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.apply_schema

    def fail_after_schema(conn: sqlite3.Connection) -> None:
        original(conn)
        conn.execute("CREATE TABLE core06m_r2_forced_failure(id INTEGER PRIMARY KEY)")
        raise RuntimeError("CORE-0.6M-R2 forced rollback")

    before = _sha256(production_copy)
    monkeypatch.setattr(module, "apply_schema", fail_after_schema)
    monkeypatch.setattr(sys, "argv", [str(migration), "--apply", "--db", str(production_copy)])
    with pytest.raises(RuntimeError, match="forced rollback"):
        module.main()
    assert _sha256(production_copy) == before
    with sqlite3.connect(production_copy) as conn:
        assert "core06m_r2_forced_failure" not in {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def test_p4_http_on_migrated_production_copy(
    migrated_production_copy: Path, monkeypatch: pytest.MonkeyPatch,
):
    _configure_app(monkeypatch, migrated_production_copy)
    from app.main import app

    with TestClient(app) as client:
        for path in (
            "/club/operations?tab=members",
            "/club/operations?tab=activities",
            "/club/operations?tab=registrations",
            "/club/operations?tab=checkin",
            "/club/operations?tab=feedback",
            "/club/operations?tab=resources",
            "/club/members",
            "/club/members/1",
            "/club/events",
            "/club/events/1",
            "/club/events/1/registrations",
            "/club/registrations",
            "/club/matches?tab=demands",
            "/club/matches?tab=supplies",
            "/club/matches",
            "/club/resources",
            "/club/resources/3",
            "/club/leads",
        ):
            response = client.get(path, follow_redirects=True)
            assert response.status_code == 200, (path, response.status_code, response.text[:500])
            assert response.url.path.startswith("/club/"), (path, response.url)

        archived = client.get("/club/events/1", follow_redirects=True)
        archived_registrations = client.get("/club/events/1/registrations", follow_redirects=True)
        assert "原关联活动已删除或不可用" in archived.text
        assert "原关联活动已删除或不可用" in archived_registrations.text
        assert "归档" in archived_registrations.text

        generated = client.post("/club/matches/generate", follow_redirects=True)
        assert generated.status_code == 200
        with sqlite3.connect(migrated_production_copy) as conn:
            match = conn.execute("SELECT id FROM p4_resource_match_candidates ORDER BY id LIMIT 1").fetchone()
        if match:
            detail = client.get(f"/club/matches/{match[0]}", follow_redirects=True)
            assert detail.status_code == 200
            assert detail.url.path.startswith("/club/matches/")
