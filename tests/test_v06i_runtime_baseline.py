from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.capability_guard import CapabilityGuardMiddleware
from app.platform.capability_registry import filter_capabilities
from app.security import SecurityMiddleware, auth_disabled_user
from app.services.schema_preflight import CAPABILITY_COLUMNS, CAPABILITY_INDEXES, CAPABILITY_TABLES, run_schema_preflight
from app.settings import Settings, get_settings, sqlite_url_from_path


def _create_tables(path: Path, names: set[str]) -> None:
    with sqlite3.connect(path) as conn:
        for name in sorted(names):
            conn.execute(f'CREATE TABLE "{name}" (id INTEGER PRIMARY KEY)')

def _create_complete_schema(path: Path) -> None:
    required_columns: dict[str, set[str]] = {}
    for capability in CAPABILITY_COLUMNS.values():
        for table, columns in capability.items():
            required_columns.setdefault(table, set()).update(columns)
    all_tables = {table for tables in CAPABILITY_TABLES.values() for table in tables} | set(required_columns)
    with sqlite3.connect(path) as conn:
        for table in sorted(all_tables):
            columns = ["id INTEGER PRIMARY KEY"]
            columns.extend(f'"{name}" TEXT' for name in sorted(required_columns.get(table, set())) if name != "id")
            conn.execute(f'CREATE TABLE "{table}" ({", ".join(columns)})')
        index_names = {name for names in CAPABILITY_INDEXES.values() for name in names}
        for name in sorted(index_names):
            conn.execute(f'CREATE INDEX "{name}" ON people(id)')


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_database_url_priority(monkeypatch, tmp_path: Path) -> None:
    high = tmp_path / "high.db"
    low = tmp_path / "low.db"
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", sqlite_url_from_path(high))
    monkeypatch.setenv("APP_DB_PATH", str(low))
    assert get_settings().sqlite_path == high.resolve()
    monkeypatch.setenv("DATABASE_URL", "")
    assert get_settings().sqlite_path == low.resolve()


def test_production_safety_rejects_missing_secrets_and_bypasses(tmp_path: Path) -> None:
    settings = Settings(
        app_env="production",
        database_url=sqlite_url_from_path(tmp_path / "prod.db"),
        auth_disabled=True,
        enable_scheduler_in_web=True,
    )
    errors = settings.validate()
    assert any("SECRET_KEY" in item for item in errors)
    assert any("SESSION_SECRET" in item for item in errors)
    assert any("APP_AUTH_DISABLED" in item for item in errors)
    assert any("embedded Web scheduler" in item for item in errors)


def test_preflight_is_read_only_and_reports_extension_gaps(tmp_path: Path) -> None:
    db_path = tmp_path / "baseline.db"
    basic = {
        "v05a_users", "people", "organizations", "raw_intelligence", "resources",
        "v06_opportunities", "v04f_club_applications", "v04f_club_memberships",
        "v05c_club_event_profiles", "v05c_club_event_registrations",
        "v05c_club_event_participation", "v04f_club_needs", "v04f_club_offerings",
        "v04f_club_matches", "v04f_lead_records", "v06_follow_ups", "v06_collab_tasks",
    }
    _create_tables(db_path, basic)
    before = _sha256(db_path)
    snapshot = run_schema_preflight(Settings(app_env="testing", database_url=sqlite_url_from_path(db_path)))
    after = _sha256(db_path)
    assert before == after
    assert snapshot.connected
    assert snapshot.capability("people").enabled
    assert not snapshot.capability("industry_relationships").enabled
    assert not snapshot.capability("club_operations").enabled
    assert not snapshot.capability("business_collaboration").enabled


def test_preflight_complete_schema_and_missing_file(tmp_path: Path) -> None:
    complete = tmp_path / "complete.db"
    _create_complete_schema(complete)
    snapshot = run_schema_preflight(Settings(app_env="testing", database_url=sqlite_url_from_path(complete)))
    assert all(item.enabled for item in snapshot.capabilities)

    missing = tmp_path / "missing.db"
    missing_snapshot = run_schema_preflight(Settings(app_env="testing", database_url=sqlite_url_from_path(missing)))
    assert not missing_snapshot.connected
    assert missing_snapshot.error == "database_file_missing"
    assert not missing.exists()


def test_preflight_reports_unavailable_database(tmp_path: Path) -> None:
    directory_instead_of_db = tmp_path / "not-a-database"
    directory_instead_of_db.mkdir()
    snapshot = run_schema_preflight(
        Settings(app_env="testing", database_url=sqlite_url_from_path(directory_instead_of_db))
    )
    assert not snapshot.connected
    assert snapshot.error == "database_unavailable"


def test_capability_guard_returns_page_and_structured_api_503(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "guard.db"
    _create_tables(db_path, {"v05a_users"})
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", sqlite_url_from_path(db_path))
    app = FastAPI()
    app.add_middleware(CapabilityGuardMiddleware)

    @app.get("/network/graph")
    def graph():
        return {"unexpected": True}

    @app.get("/api/v1/entity-network/graph")
    def graph_api():
        return {"unexpected": True}

    with TestClient(app) as client:
        page = client.get("/network/graph")
        api = client.get("/api/v1/entity-network/graph")
    assert page.status_code == 503
    assert "unexpected" not in page.text
    assert api.status_code == 503
    assert api.json()["error"] == "capability_unavailable"
    assert api.json()["capability"] == "industry_relationships"
    assert api.json()["missing_tables"]


def test_navigation_hides_unavailable_schema_capabilities(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "navigation.db"
    _create_tables(db_path, {"v05a_users", "people", "organizations", "raw_intelligence", "resources"})
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", sqlite_url_from_path(db_path))
    permissions = {
        "view_internal", "edit_data", "review_data", "manage_club", "manage_monitoring",
        "use_recommendations", "manage_users", "view_sensitive", "export_data",
        "identity.view_self", "identity.request_link", "membership.view_self", "organization.view_self",
    }
    keys = {item["capability_key"] for item in filter_capabilities(permissions)}
    assert "network.people" in keys
    assert "network.graph" not in keys
    assert "club.operations" not in keys
    assert "collaboration" not in keys


def test_auth_bypass_is_explicit_in_memory_only(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "must-not-exist.db"
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", sqlite_url_from_path(db_path))
    monkeypatch.setenv("APP_AUTH_DISABLED", "true")
    user = auth_disabled_user(db_path)
    assert user["username"] == "development-bypass"
    assert user["is_development_identity"] is True
    assert not db_path.exists()


def test_missing_auth_schema_is_controlled_and_read_only(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    _create_tables(db_path, set())
    before = _sha256(db_path)
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", sqlite_url_from_path(db_path))
    monkeypatch.setenv("APP_AUTH_DISABLED", "false")
    app = FastAPI()
    app.add_middleware(SecurityMiddleware)

    @app.get("/private")
    def private():
        return {"unexpected": True}

    with TestClient(app) as client:
        response = client.get("/private")
    assert response.status_code == 503
    assert _sha256(db_path) == before
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 0


def test_import_does_not_start_embedded_scheduler(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_SCHEDULER_IN_WEB", "false")
    from app.services.collection_scheduler import is_scheduler_running

    assert not is_scheduler_running()
