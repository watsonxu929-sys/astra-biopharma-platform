import sqlite3

conn = sqlite3.connect('data/acceptance/t5_1_mvp.db')
cursor = conn.cursor()

cursor.execute('PRAGMA table_info(v06_opportunities)')
existing_cols = [row[1] for row in cursor.fetchall()]

new_cols = [
    ('opportunity_no', 'TEXT'),
    ('currency', 'TEXT'),
    ('success_probability', 'TEXT'),
    ('target_complete_at', 'TEXT'),
    ('risk_summary', 'TEXT'),
    ('last_stage_changed_at', 'TEXT'),
    ('pilot_batch_id', 'TEXT'),
]

for name, definition in new_cols:
    if name not in existing_cols:
        try:
            cursor.execute(f'ALTER TABLE v06_opportunities ADD COLUMN {name} {definition}')
            print(f'添加列: {name}')
        except Exception as e:
            print(f'添加列失败 {name}: {e}')

conn.commit()
cursor.execute('PRAGMA table_info(v06_opportunities)')
cols = [row[1] for row in cursor.fetchall()]
print(f'\n更新后列数: {len(cols)}')

conn.close()
