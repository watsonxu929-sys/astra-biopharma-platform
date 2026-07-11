from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from app.settings import resolved_db_path


@pytest.fixture
def temp_db_conn(temp_database: Path) -> sqlite3.Connection:
    """Alias fixture for tests expecting temp_db_conn."""
    conn = sqlite3.connect(temp_database)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def temp_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a consistent SQLite copy outside data/ and seed one deterministic P2 source."""
    live_db = resolved_db_path().resolve()
    if not live_db.exists():
        pytest.fail("formal database is required as the schema baseline")
    target = tmp_path / "app_test.db"
    with sqlite3.connect(f"file:{live_db.as_posix()}?mode=ro", uri=True) as source:
        with sqlite3.connect(target) as destination:
            source.backup(destination)

    monkeypatch.setenv("APP_DB_PATH", str(target))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{target.as_posix()}")
    stamp = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(target) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("DELETE FROM v04g_monitoring_sources WHERE source_no='SRC-P2-PYTEST'")
        source_id = conn.execute(
            """INSERT INTO v04g_monitoring_sources(
               source_no,name,source_type,url,check_frequency,is_enabled,fetch_mode,created_at,updated_at)
               VALUES ('SRC-P2-PYTEST','P2 pytest source','website','https://example.invalid/p2-fixture',
                       'manual',1,'web',?,?)""",
            (stamp, stamp),
        ).lastrowid
        run_id = conn.execute(
            """INSERT INTO v04g_monitoring_runs(
               run_no,monitoring_source_id,status,started_at,finished_at,http_status,
               content_length,content_hash,changed,created_at)
               VALUES ('RUN-P2-PYTEST',?,'success',?,?,200,48,'p2-fixture-hash',1,?)""",
            (source_id, stamp, stamp, stamp),
        ).lastrowid
        conn.execute(
            """INSERT INTO v04g_source_snapshots(
               snapshot_no,monitoring_source_id,monitoring_run_id,page_title,url,captured_at,
               raw_content,cleaned_text,content_hash,metadata_json,created_at)
               VALUES ('SNP-P2-PYTEST',?,?, 'P2 fixture','https://example.invalid/p2-fixture',?,
                       '某生物医药公司入选产业榜单','某生物医药公司入选产业榜单','p2-fixture-hash','{}',?)""",
            (source_id, run_id, stamp, stamp),
        )
        conn.commit()
    return target
