﻿﻿﻿from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import resolved_db_path
DB_PATH = resolved_db_path()
BACKUP_DIR = DB_PATH.parent / "backups" if (ROOT / "data").resolve() not in DB_PATH.resolve().parents else ROOT / "data" / "backups"


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = BACKUP_DIR / f"app_before_user_membership_link_{stamp}.db"
        shutil.copy2(db_path, target)
        backup_path = str(target)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        
        exists = conn.execute("""
            SELECT 1 FROM sqlite_master 
            WHERE type='table' AND name='v04f_club_memberships'
        """).fetchone()
        if exists:
            col_exists = conn.execute("""
                SELECT 1 FROM pragma_table_info('v04f_club_memberships') 
                WHERE name='user_id'
            """).fetchone()
            if not col_exists:
                conn.execute("ALTER TABLE v04f_club_memberships ADD COLUMN user_id INTEGER")
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_v04f_member_user_id
            ON v04f_club_memberships(user_id)
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS membership_user_link_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_no TEXT NOT NULL UNIQUE,
                action TEXT NOT NULL,
                membership_id INTEGER NOT NULL,
                user_id INTEGER,
                old_user_id INTEGER,
                actor TEXT,
                reason TEXT,
                request_id INTEGER,
                created_at TEXT NOT NULL
            )
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_membership_user_audit_membership
            ON membership_user_link_audit(membership_id, created_at DESC)
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS membership_user_link_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_no TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                membership_id INTEGER NOT NULL,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_by TEXT,
                reviewed_at TEXT,
                review_note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS ix_membership_user_request_status
            ON membership_user_link_requests(status, created_at DESC)
        """)
        
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_membership_user_request_pending
            ON membership_user_link_requests(user_id, membership_id)
            WHERE status='pending'
        """)
        
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("User-Membership link migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
