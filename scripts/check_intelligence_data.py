import sqlite3

conn = sqlite3.connect('data/app.db')
conn.row_factory = sqlite3.Row

tables = ['intelligence_items', 'events', 'news_items', 'collection_items']

for table in tables:
    try:
        rows = conn.execute(f"""
            SELECT id, title, summary
            FROM {table}
            WHERE title LIKE '%首页%' OR title LIKE '%药明康德%' OR title LIKE '%标题%'
            LIMIT 10
        """).fetchall()
        if rows:
            print(f"\n=== {table} ===")
            for row in rows:
                print(f"ID:{row['id']}")
                print(f"  Title: {row['title']}")
                print(f"  Summary: {row['summary']}")
                print()
    except sqlite3.Error as e:
        pass

conn.close()