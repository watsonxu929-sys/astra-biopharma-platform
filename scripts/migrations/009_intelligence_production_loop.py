"""Recovered additive migration for the canonical intelligence production loop.

Recovery source: verified schema delta between the surviving pre-009 and
pre-010 SQLite backups. The migration is schema-only and does not rewrite rows.
"""

MIGRATION_ID = "009_intelligence_production_loop"
REQUIRED_TABLES = {"v05f_collection_items", "v06_intelligence_items"}

ADDITIVE_COLUMNS = {
    "v05f_collection_items": {
        "entry_mode": "TEXT",
        "recorded_by_user_id": "INTEGER",
    },
    "v06_intelligence_items": {
        "event_type": "TEXT",
        "occurred_at": "TEXT",
        "region": "TEXT",
        "verification_status": "TEXT NOT NULL DEFAULT 'unverified'",
        "analysis_notes": "TEXT",
    },
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS core_intelligence_subject_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intelligence_item_id INTEGER NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id INTEGER NOT NULL,
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(intelligence_item_id) REFERENCES v06_intelligence_items(id) ON DELETE CASCADE,
    CHECK(subject_type IN ('person','organization','project')),
    UNIQUE(intelligence_item_id, subject_type, subject_id)
);
CREATE INDEX IF NOT EXISTS ix_core_intelligence_subject_item
ON core_intelligence_subject_links(intelligence_item_id, subject_type, subject_id);

CREATE TABLE IF NOT EXISTS core_intelligence_workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intelligence_item_id INTEGER NOT NULL,
    collection_item_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_user_id INTEGER,
    actor_username TEXT NOT NULL,
    decision TEXT,
    note TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(intelligence_item_id) REFERENCES v06_intelligence_items(id) ON DELETE CASCADE,
    FOREIGN KEY(collection_item_id) REFERENCES v05f_collection_items(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_core_intelligence_workflow_item
ON core_intelligence_workflow_events(intelligence_item_id, id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_core_intelligence_source_record
ON v06_intelligence_items(source_record_type, source_record_id)
WHERE source_record_type='v05f_collection_items' AND source_record_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_core_manual_collection_content
ON v05f_collection_items(content_hash)
WHERE entry_mode='manual' AND content_hash IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_core_manual_collection_url
ON v05f_collection_items(normalized_url)
WHERE entry_mode='manual' AND normalized_url IS NOT NULL AND normalized_url<>'';
"""
