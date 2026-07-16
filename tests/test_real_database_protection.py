import hashlib
from pathlib import Path

from app.settings import resolved_db_path

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB_PATH = resolved_db_path()


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_database_not_written_directly():
    initial_sha = compute_sha256(LIVE_DB_PATH)
    
    import sqlite3
    with sqlite3.connect(str(LIVE_DB_PATH)) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM v05a_users")
        count = cursor.fetchone()[0]
    
    final_sha = compute_sha256(LIVE_DB_PATH)
    
    assert initial_sha == final_sha, "Real database was modified during read operation"


def test_temp_database_used_for_writes(temp_database):
    import sqlite3
    from datetime import datetime
    
    with sqlite3.connect(str(temp_database)) as conn:
        initial_count = conn.execute("SELECT COUNT(*) FROM v05a_users").fetchone()[0]
        now_str = datetime.now().isoformat()
        conn.execute("INSERT INTO v05a_users (username, password_hash, display_name, role, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     ("test_user", "dummy_hash", "Test User", "viewer", "active", now_str, now_str))
        conn.commit()
        final_count = conn.execute("SELECT COUNT(*) FROM v05a_users").fetchone()[0]
    
    assert final_count == initial_count + 1, "Write operation should affect temp database"


def test_real_database_path_is_not_temp(temp_database):
    live_path = str(LIVE_DB_PATH).lower()
    temp_path = str(temp_database).lower()
    assert live_path != temp_path, "Temp database should be different from real database"
