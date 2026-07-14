import sqlite3

conn = sqlite3.connect('data/app.db')
conn.execute("UPDATE v04g_monitoring_sources SET check_frequency='daily' WHERE id IN (4,5)")
conn.execute("UPDATE v04g_monitoring_sources SET check_frequency='hourly' WHERE id=6")
conn.commit()

rows = conn.execute("SELECT id, name, check_frequency FROM v04g_monitoring_sources WHERE id IN (4,5,6)").fetchall()
for r in rows:
    print(f"{r[0]}: {r[1]} -> {r[2]}")

conn.close()
