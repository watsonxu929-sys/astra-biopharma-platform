import sqlite3

conn = sqlite3.connect('data/app.db')
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT id, name, public_role, organization_network, ability_tags, value_provided
    FROM people
    WHERE is_active=1
    ORDER BY id
    LIMIT 50
""").fetchall()

print("人物数据：")
for row in rows:
    name = row['name']
    role = row['public_role'] or ''
    org = row['organization_network'] or ''
    tags = row['ability_tags'] or ''
    value = row['value_provided'] or ''
    
    if '首页' in name or '标题' in name or '药明康德' in name:
        print(f"⚠️ ID:{row['id']} | Name: {name}")
        print(f"   Role: {role}")
        print(f"   Org: {org}")
        print(f"   Tags: {tags}")
        print(f"   Value: {value}")
        print()
    elif len(name) > 50 or len(tags) > 200:
        print(f"⚠️ ID:{row['id']} | Name: {name[:30]}...")
        print()

conn.close()