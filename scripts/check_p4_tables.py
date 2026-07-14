import sqlite3
conn = sqlite3.connect('data/app.db')
tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'p4_%'").fetchall()]
print(tables)
for table in tables:
    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    print(f"{table}: {cols}")
conn.close()