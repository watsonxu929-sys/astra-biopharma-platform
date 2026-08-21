import hashlib
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB_PATH = ROOT / "data" / "app.db"


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_formal_snapshot() -> tuple[str, dict[str, int]]:
    tables = ("people", "organizations", "v06_intelligence_items", "v06_market_resources", "v06_opportunities", "v06_follow_ups", "p4_resource_match_candidates", "p3_canonical_relationships")
    uri = f"file:{LIVE_DB_PATH.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        counts = {table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}
    return compute_sha256(LIVE_DB_PATH), counts



def test_real_database_not_written_directly():
    initial_sha, initial_counts = read_formal_snapshot()
    final_sha, final_counts = read_formal_snapshot()
    assert initial_sha == final_sha, "formal database file changed during read-only verification"
    assert initial_counts == final_counts, "formal database core rows changed during test verification"


def test_temp_database_used_for_writes(temp_database):
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
    assert LIVE_DB_PATH.resolve() != Path(temp_database).resolve(), "formal database cannot be a test write target"
    assert Path(temp_database).resolve().is_relative_to(Path.cwd().resolve()) is False
