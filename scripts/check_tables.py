import sqlite3

conn = sqlite3.connect('data/app.db')
conn.row_factory = sqlite3.Row

c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [t[0] for t in c.fetchall()]

print("会员相关表：")
for t in tables:
    if 'member' in t.lower() or 'user' in t.lower():
        print(f"  - {t}")

print("\n会员表数据：")
if 'v04f_club_memberships' in tables:
    c.execute("SELECT COUNT(*) FROM v04f_club_memberships WHERE status='active'")
    print(f"  活跃会员数: {c.fetchone()[0]}")

if 'v05a_users' in tables:
    c.execute("SELECT COUNT(*) FROM v05a_users")
    print(f"  用户数: {c.fetchone()[0]}")

conn.close()