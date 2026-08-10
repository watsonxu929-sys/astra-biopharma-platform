import sqlite3

def count_tables(path):
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = c.fetchall()
        conn.close()
        return len(tables), [t[0] for t in tables]
    except Exception as e:
        return 0, [str(e)]

formal_count, formal_tables = count_tables('data/app.db')
acceptance_count, acceptance_tables = count_tables('data/acceptance/t5_1_mvp.db')

print(f"正式库 (data/app.db): {formal_count} 张表")
print(f"验收库 (data/acceptance/t5_1_mvp.db): {acceptance_count} 张表")
print("\n验收库额外表:")
for t in acceptance_tables:
    if t not in formal_tables:
        print(f"  - {t}")