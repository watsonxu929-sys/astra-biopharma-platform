import sqlite3

conn = sqlite3.connect('data/app.db')
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT id, recommendation_no, title, summary, score, grade, category
    FROM v04h_recommendations
    WHERE status IN ('new', 'accepted', 'snoozed')
    ORDER BY score DESC, updated_at DESC
    LIMIT 20
""").fetchall()

print("推荐列表：")
for row in rows:
    print(f"ID:{row['id']} | Score:{row['score']} | Grade:{row['grade']} | Category:{row['category']}")
    print(f"  Title: {row['title']}")
    print(f"  Summary: {row['summary']}")
    print()

bad_titles = conn.execute("""
    SELECT id, title, summary
    FROM v04h_recommendations
    WHERE title LIKE '%首页%' OR title LIKE '%药明康德%' OR title LIKE '%标题%'
""").fetchall()

print("\n可能存在问题的推荐：")
for row in bad_titles:
    print(f"ID:{row['id']}")
    print(f"  Title: {row['title']}")
    print(f"  Summary: {row['summary']}")
    print()

conn.close()