import sqlite3

conn = sqlite3.connect('data/app.db')
conn.row_factory = sqlite3.Row

test_items = conn.execute(
    "SELECT id, title, direction FROM v06_market_resources WHERE title LIKE 'Test%' OR title='demand' OR title='supply'"
).fetchall()

print("找到测试数据:")
for item in test_items:
    print(f"  ID: {item['id']}, Title: {item['title']}, Direction: {item['direction']}")

if test_items:
    conn.execute(
        "DELETE FROM v06_market_resources WHERE title LIKE 'Test%' OR title='demand' OR title='supply'"
    )
    conn.commit()
    print(f"\n已删除 {len(test_items)} 条测试数据")
else:
    print("\n未找到测试数据")

conn.close()