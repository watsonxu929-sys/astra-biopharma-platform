import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "data" / "app.db"

with sqlite3.connect(db_path) as conn:
    conn.execute("PRAGMA foreign_keys = OFF")
    
    conn.execute("DELETE FROM v04f_club_memberships WHERE member_no LIKE 'QBM-ui_%'")
    conn.execute("DELETE FROM v04f_club_memberships WHERE member_no LIKE 'QBM-e2e_%'")
    
    conn.execute("DELETE FROM people WHERE source_type='system_e2e'")
    conn.execute("DELETE FROM people WHERE external_id LIKE 'PER-E2E-%'")
    
    conn.execute("DELETE FROM membership_person_link_audit WHERE membership_id IN (SELECT id FROM v04f_club_memberships WHERE member_no LIKE 'QBM-ui_%' OR member_no LIKE 'QBM-e2e_%')")
    
    conn.commit()
    print("清理完成")