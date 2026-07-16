from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / "scripts/migrations/006_entity_relationship_network.py",
    ROOT / "scripts/migrations/007_club_operations_mvp.py",
)


@pytest.fixture
def p4_db(temp_database: Path) -> Path:
    for migration in MIGRATIONS:
        subprocess.run(
            [sys.executable, str(migration), "--apply", "--db", str(temp_database)],
            cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
        )
    return temp_database



def _configure_test_db(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("APP_DB_PATH", str(path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path.as_posix()}")
    monkeypatch.setenv("APP_AUTH_DISABLED", "1")
    monkeypatch.setenv("APP_ENABLE_SCHEDULER", "0")
    monkeypatch.setenv("APP_ENABLE_WORKER", "0")


def test_club_home_and_operations_use_distinct_handlers():
    from app.v04f_operations import club_home, club_operations

    assert club_home is not club_operations


def test_p4_http_smoke_and_event_create_on_temporary_database(
    p4_db: Path, monkeypatch: pytest.MonkeyPatch,
):
    _configure_test_db(monkeypatch, p4_db)
    from app.main import app

    with TestClient(app) as client:
        for path, expected_text in (
            ("/club", "Q-BAY俱乐部运营工作台"),
            ("/club/operations", "俱乐部运营处理台"),
            ("/club/applications", "会员申请审核"),
            ("/club/events", "活动"),
            ("/club/resources", "会员供需审核"),
            ("/club/matches", "资源匹配工作台"),
            ("/club/leads", "潜在线索候选"),
        ):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 200, (path, response.text[:500])
            assert expected_text in response.text

        created = client.post(
            "/club/events/create",
            data={
                "name": "CORE-0.6M-R1 HTTP验收活动",
                "event_type": "qbay_club",
                "event_date": "2030-01-01",
                "venue": "临时数据库",
                "capacity": "2",
                "organizer": "Q-BAY",
                "visibility": "controlled",
                "description": "仅写入pytest临时数据库",
            },
            follow_redirects=False,
        )
        assert created.status_code == 303
        assert created.headers["location"].startswith("/club/events/")
        detail = client.get(created.headers["location"], follow_redirects=False)
        assert detail.status_code == 200
        copied = client.post(f"{created.headers['location']}/copy", follow_redirects=False)
        assert copied.status_code == 303
        assert copied.headers["location"].startswith("/club/events/")
        copied_detail = client.get(copied.headers["location"], follow_redirects=False)
        assert copied_detail.status_code == 200
        assert "（复制）" in copied_detail.text
        assert "CORE-0.6M-R1 HTTP验收活动" in detail.text

        assert client.get("/club/resources/999999", follow_redirects=False).status_code == 404
        assert client.get("/club/matches/999999", follow_redirects=False).status_code == 404
        member_entry = client.get("/member/needs", follow_redirects=False)
        assert member_entry.status_code == 303
        assert member_entry.headers["location"] == "/member/login"
