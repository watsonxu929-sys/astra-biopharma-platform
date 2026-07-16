from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.settings import resolved_db_path

from app.security import required_permission
from scripts.verify_p4_club_operations_mvp import PILOT_BATCH_ID, run_pilot


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / "scripts/migrations/006_entity_relationship_network.py",
    ROOT / "scripts/migrations/007_club_operations_mvp.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def p4_db(temp_database: Path) -> Path:
    for migration in MIGRATIONS:
        subprocess.run(
            [sys.executable, str(migration), "--apply", "--db", str(temp_database)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    return temp_database


def test_007_defaults_to_dry_run_and_does_not_mutate(temp_database: Path):
    before = _sha256(temp_database)
    completed = subprocess.run(
        [sys.executable, str(MIGRATIONS[1]), "--db", str(temp_database)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert '"mode": "dry-run"' in completed.stdout
    assert _sha256(temp_database) == before


def test_007_is_idempotent_and_keeps_integrity(p4_db: Path):
    subprocess.run(
        [sys.executable, str(MIGRATIONS[1]), "--apply", "--db", str(p4_db)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    with sqlite3.connect(p4_db) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'p4_%'"
            )
        }
    assert {
        "p4_membership_history",
        "p4_event_feedback",
        "p4_checkin_tokens",
        "p4_checkin_audit",
        "p4_event_relationship_candidates",
        "p4_resource_match_candidates",
        "p4_club_lead_candidates",
        "p4_domain_events",
        "p4_operation_audit",
    } <= tables


def test_controlled_pilot_closes_the_workflow_without_formal_mutation():
    report = run_pilot(resolved_db_path())
    assert report["status"] == "passed"
    assert report["pilot_batch_id"] == PILOT_BATCH_ID
    assert all(report["validations"].values())
    assert report["counts"] == {
        "members": 5,
        "organizations": 2,
        "events": 2,
        "registrations": 10,
        "waitlisted": 0,
        "checkins": 6,
        "cancelled": 1,
        "waitlist_promotions": 1,
        "rejected_matches": 1,
        "cancelled_participations": 0,
        "feedback": 3,
        "demands": 3,
        "supplies": 3,
        "matches": 4,
        "relationship_candidates": 3,
        "lead_candidates": 4,
        "opportunities": 11,
    }
    assert report["formal_sha256_unchanged"] is True
    assert report["formal_counts_unchanged"] is True


def test_p4_review_and_operations_paths_require_manage_club():
    protected = (
        ("/api/v1/club/events/1/transition", "POST"),
        ("/api/v1/club/events/1/registrations/1/review", "POST"),
        ("/api/v1/club/events/1/checkin", "POST"),
        ("/api/v1/club/resources/1/review", "POST"),
        ("/api/v1/club/resource-matches/generate", "POST"),
        ("/api/v1/club/relationship-candidates/1/review", "POST"),
        ("/api/v1/club/operations", "GET"),
    )
    assert {required_permission(path, method) for path, method in protected} == {"manage_club"}


def test_unauthenticated_user_cannot_run_club_review(p4_db: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_AUTH_DISABLED", "0")
    from app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/club/events/1/registrations/1/review",
            json={"decision": "approved", "note": "must not run"},
            follow_redirects=False,
        )
    assert response.status_code in {401, 403}
