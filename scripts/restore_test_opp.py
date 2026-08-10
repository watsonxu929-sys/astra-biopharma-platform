import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/app.db')
conn.row_factory = sqlite3.Row

exists = conn.execute("SELECT COUNT(*) FROM v06_opportunities WHERE title='Test Opp'").fetchone()[0]
if exists > 0:
    print("Test Opp已存在")
else:
    ts = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO v06_opportunities(
            title, opp_type, source_type, description, stage, status, 
            initiator_id, owner_id, is_demo, created_at, updated_at
        ) VALUES (
            'Test Opp', '合作开发', 'manual', 'Test opportunity for verification', 
            'contacted', 'active', 1, 1, 1, ?, ?
        )
    """, (ts, ts))
    conn.commit()
    print("已恢复Test Opp")

conn.close()