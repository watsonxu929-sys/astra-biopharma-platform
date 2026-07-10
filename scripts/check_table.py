import sqlite3
from pathlib import Path

conn = sqlite3.connect(Path(__file__).parent.parent / "data" / "app.db")
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(membership_user_link_requests)")
print("\n".join(str(r) for r in cursor.fetchall()))