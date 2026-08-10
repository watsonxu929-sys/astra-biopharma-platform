import sqlite3

conn = sqlite3.connect('data/rehearsal/v06j_app_migrated.db')

c = conn.cursor()
c.execute("PRAGMA table_info(platform_migration_runs)")
columns = [col[1] for col in c.fetchall()]
print("platform_migration_runs列:", columns)

rows = c.execute("SELECT * FROM platform_migration_runs ORDER BY id DESC LIMIT 5").fetchall()
for row in rows:
    print(row)

conn.close()