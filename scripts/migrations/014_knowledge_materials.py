"""Additive, bounded material versions and review queue; no seeded content."""
MIGRATION_ID = '014_knowledge_materials'
REQUIRED_TABLES = {'knowledge_items', 'v05a_users', 'v04g_monitoring_sources'}
ADDITIVE_COLUMNS = {
    'knowledge_items': {
        'content_revision': 'INTEGER NOT NULL DEFAULT 0',
        'access_scope': "TEXT NOT NULL DEFAULT 'PUBLIC'",
        'owner_user_id': 'INTEGER REFERENCES v05a_users(id)',
        'policy_json': "TEXT NOT NULL DEFAULT '{}'",
    },
    'user_knowledge_progress': {'knowledge_revision': 'INTEGER'},
    'knowledge_annotations': {'knowledge_revision': 'INTEGER'},
}
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_materials (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 identity_key TEXT NOT NULL UNIQUE,
 title TEXT NOT NULL,
 source_id INTEGER REFERENCES v04g_monitoring_sources(id),
 source_url TEXT NOT NULL DEFAULT '',
 owner_user_id INTEGER NOT NULL REFERENCES v05a_users(id),
 access_scope TEXT NOT NULL CHECK(access_scope IN ('PUBLIC','PRIVATE')),
 config_json TEXT NOT NULL DEFAULT '{}',
 tracking INTEGER NOT NULL DEFAULT 0 CHECK(tracking IN (0,1)),
 latest_version_id INTEGER REFERENCES knowledge_versions(id),
 last_checked_at TEXT, next_check_at TEXT,
 error_summary TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 material_id INTEGER REFERENCES knowledge_materials(id),
 knowledge_id INTEGER REFERENCES knowledge_items(id),
 kind TEXT NOT NULL CHECK(kind IN ('MATERIAL','KNOWLEDGE')),
 content_hash TEXT NOT NULL,
 parser_version TEXT NOT NULL DEFAULT '',
 filename TEXT NOT NULL DEFAULT '',
 payload BLOB,
 content_json TEXT NOT NULL,
 source_version_id INTEGER REFERENCES knowledge_versions(id),
 revision INTEGER,
 created_by INTEGER REFERENCES v05a_users(id),
 created_at TEXT NOT NULL,
 CHECK((kind='MATERIAL' AND material_id IS NOT NULL AND knowledge_id IS NULL) OR
       (kind='KNOWLEDGE' AND knowledge_id IS NOT NULL)),
 UNIQUE(material_id,kind,content_hash,parser_version),
 UNIQUE(knowledge_id,revision)
);
CREATE TABLE IF NOT EXISTS knowledge_candidates (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 material_id INTEGER NOT NULL REFERENCES knowledge_materials(id),
 version_id INTEGER NOT NULL REFERENCES knowledge_versions(id),
 section_key TEXT NOT NULL,
 title TEXT NOT NULL,
 category TEXT NOT NULL DEFAULT '',
 body TEXT NOT NULL,
 mappings_json TEXT NOT NULL,
 metadata_json TEXT NOT NULL DEFAULT '{}',
 issues_json TEXT NOT NULL DEFAULT '[]',
 target_knowledge_id INTEGER REFERENCES knowledge_items(id),
 base_revision INTEGER,
 state TEXT NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','CONFIRMED','IGNORED','SUPERSEDED')),
 edit_revision INTEGER NOT NULL DEFAULT 0,
 decision_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL,
 reviewed_at TEXT,
 UNIQUE(version_id,section_key)
);
CREATE INDEX IF NOT EXISTS ix_knowledge_material_due ON knowledge_materials(tracking,next_check_at);
CREATE INDEX IF NOT EXISTS ix_knowledge_candidate_review ON knowledge_candidates(material_id,state,id);
CREATE INDEX IF NOT EXISTS ix_knowledge_version_history ON knowledge_versions(knowledge_id,revision);
CREATE TRIGGER IF NOT EXISTS knowledge_versions_no_update BEFORE UPDATE ON knowledge_versions
BEGIN SELECT RAISE(ABORT,'knowledge versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_versions_no_delete BEFORE DELETE ON knowledge_versions
BEGIN SELECT RAISE(ABORT,'knowledge versions are immutable'); END;
"""
