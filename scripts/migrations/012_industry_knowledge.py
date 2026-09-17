"""Additive knowledge and learning persistence; no seeded business content."""

MIGRATION_ID = "012_industry_knowledge"
REQUIRED_TABLES = {"v05a_users"}
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT NOT NULL, category TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '',
 body TEXT NOT NULL DEFAULT '', key_points TEXT NOT NULL DEFAULT '',
 difficulty TEXT NOT NULL DEFAULT '入门', tags TEXT NOT NULL DEFAULT '',
 source_name TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '',
 region TEXT NOT NULL DEFAULT '', effective_version TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','PUBLISHED','ARCHIVED')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 knowledge_id INTEGER NOT NULL REFERENCES knowledge_items(id),
 target_type TEXT NOT NULL CHECK(target_type IN ('intelligence','organization','person')),
 target_id INTEGER NOT NULL,
 UNIQUE(knowledge_id,target_type,target_id)
);
CREATE INDEX IF NOT EXISTS ix_knowledge_link_target ON knowledge_links(target_type,target_id);
CREATE TABLE IF NOT EXISTS learning_paths (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','PUBLISHED','ARCHIVED')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learning_path_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 path_id INTEGER NOT NULL REFERENCES learning_paths(id),
 knowledge_id INTEGER NOT NULL REFERENCES knowledge_items(id),
 position INTEGER NOT NULL CHECK(position>0),
 UNIQUE(path_id,knowledge_id), UNIQUE(path_id,position)
);
CREATE TABLE IF NOT EXISTS user_knowledge_progress (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES v05a_users(id),
 knowledge_id INTEGER NOT NULL REFERENCES knowledge_items(id),
 status TEXT NOT NULL CHECK(status IN ('NOT_STARTED','LEARNING','MASTERED','REVIEW_LATER')),
 note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
 UNIQUE(user_id,knowledge_id)
);
"""
