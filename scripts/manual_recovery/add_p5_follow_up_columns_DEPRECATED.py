import sqlite3

conn = sqlite3.connect('data/acceptance/t5_1_mvp.db')
cursor = conn.cursor()

cursor.execute('PRAGMA table_info(v06_follow_ups)')
existing_cols = [row[1] for row in cursor.fetchall()]

new_cols = [
    ('participants_json', 'TEXT'),
    ('result', 'TEXT'),
    ('next_action', 'TEXT'),
    ('shared_summary', 'TEXT'),
    ('internal_note', 'TEXT'),
    ('artifact_ids_json', 'TEXT'),
    ('pilot_batch_id', 'TEXT'),
]

for name, definition in new_cols:
    if name not in existing_cols:
        try:
            cursor.execute(f'ALTER TABLE v06_follow_ups ADD COLUMN {name} {definition}')
            print(f'添加列: {name}')
        except Exception as e:
            print(f'添加列失败 {name}: {e}')

cursor.execute('PRAGMA table_info(v06_collab_tasks)')
existing_cols = [row[1] for row in cursor.fetchall()]
print(f'\nv06_collab_tasks现有列: {existing_cols}')

new_cols = [
    ('task_type', 'TEXT DEFAULT "other"'),
    ('completion_criteria', 'TEXT'),
    ('related_follow_up_id', 'INTEGER'),
    ('related_meeting_id', 'INTEGER'),
    ('visibility', 'TEXT DEFAULT "organization"'),
    ('blocked_reason', 'TEXT'),
    ('completed_at', 'TEXT'),
    ('pilot_batch_id', 'TEXT'),
]

for name, definition in new_cols:
    if name not in existing_cols:
        try:
            cursor.execute(f'ALTER TABLE v06_collab_tasks ADD COLUMN {name}')
            print(f'添加列: {name}')
        except Exception as e:
            print(f'添加列失败 {name}: {e}')

cursor.execute('PRAGMA table_info(v06_timeline_entries)')
existing_cols = [row[1] for row in cursor.fetchall()]
print(f'\nv06_timeline_entries现有列: {existing_cols}')

new_cols = [
    ('pilot_batch_id', 'TEXT'),
]

for name, definition in new_cols:
    if name not in existing_cols:
        try:
            cursor.execute(f'ALTER TABLE v06_timeline_entries ADD COLUMN {name} {definition}')
            print(f'添加列: {name}')
        except Exception as e:
            print(f'添加列失败 {name}: {e}')

conn.commit()
conn.close()
