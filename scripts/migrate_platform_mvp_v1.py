"""v0.6 Platform MVP migration -- raw SQL, idempotent, safe for repeat execution."""
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine
from app.settings import resolved_db_path
from sqlalchemy import text

DB_PATH = resolved_db_path()

SCHEMA_SQL = """
-- Tags
CREATE TABLE IF NOT EXISTS v06_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_key TEXT NOT NULL UNIQUE,
    tag_group TEXT NOT NULL,
    label TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_tags_group ON v06_tags(tag_group);
CREATE INDEX IF NOT EXISTS ix_v06_tags_key ON v06_tags(tag_key);

-- Person tags (M2M)
CREATE TABLE IF NOT EXISTS v06_person_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id),
    tag_id INTEGER NOT NULL REFERENCES v06_tags(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_pt_person ON v06_person_tags(person_id);
CREATE INDEX IF NOT EXISTS ix_v06_pt_tag ON v06_person_tags(tag_id);

-- Organization tags (M2M)
CREATE TABLE IF NOT EXISTS v06_organization_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    tag_id INTEGER NOT NULL REFERENCES v06_tags(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_ot_org ON v06_organization_tags(organization_id);
CREATE INDEX IF NOT EXISTS ix_v06_ot_tag ON v06_organization_tags(tag_id);

-- Person profiles (1:1 with people)
CREATE TABLE IF NOT EXISTS v06_person_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL UNIQUE REFERENCES people(id),
    title TEXT,
    bio TEXT,
    city TEXT,
    province TEXT,
    cooperation_preferences TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    contact_wechat TEXT,
    contact_visibility TEXT NOT NULL DEFAULT 'private',
    avatar_url TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_pp_person ON v06_person_profiles(person_id);

-- Favorites
CREATE TABLE IF NOT EXISTS v06_favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_fav_user ON v06_favorites(user_id);
CREATE INDEX IF NOT EXISTS ix_v06_fav_target ON v06_favorites(target_type, target_id);

-- Follows
CREATE TABLE IF NOT EXISTS v06_follows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_fol_user ON v06_follows(user_id);
CREATE INDEX IF NOT EXISTS ix_v06_fol_target ON v06_follows(target_type, target_id);

-- Contact intents
CREATE TABLE IF NOT EXISTS v06_contact_intents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    intent_type TEXT NOT NULL DEFAULT 'connection',
    message TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    response_message TEXT,
    responded_at TEXT,
    responded_by INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_ci_from ON v06_contact_intents(from_user_id);
CREATE INDEX IF NOT EXISTS ix_v06_ci_status ON v06_contact_intents(status);

-- Intelligence items
CREATE TABLE IF NOT EXISTS v06_intelligence_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    intel_type TEXT NOT NULL,
    companies TEXT,
    people_involved TEXT,
    industry_directions TEXT,
    tags TEXT,
    source_name TEXT,
    source_url TEXT,
    published_at TEXT,
    collected_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    credibility INTEGER NOT NULL DEFAULT 3,
    importance INTEGER NOT NULL DEFAULT 2,
    visibility TEXT NOT NULL DEFAULT 'public',
    status TEXT NOT NULL DEFAULT 'published',
    created_by INTEGER,
    organization_id INTEGER,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_ii_type ON v06_intelligence_items(intel_type);
CREATE INDEX IF NOT EXISTS ix_v06_ii_status ON v06_intelligence_items(status);
CREATE INDEX IF NOT EXISTS ix_v06_ii_title ON v06_intelligence_items(title);

-- Intelligence subscriptions
CREATE TABLE IF NOT EXISTS v06_intel_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    intel_types TEXT,
    industry_directions TEXT,
    companies TEXT,
    tags TEXT,
    regions TEXT,
    min_importance INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_is_user ON v06_intel_subscriptions(user_id);

-- Market resources (supply & demand)
CREATE TABLE IF NOT EXISTS v06_market_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    direction TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    summary TEXT,
    description TEXT,
    publisher_id INTEGER NOT NULL,
    organization_id INTEGER,
    region TEXT,
    industry_direction TEXT,
    tags TEXT,
    cooperation_mode TEXT,
    budget_note TEXT,
    valid_until TEXT,
    contact_visibility TEXT NOT NULL DEFAULT 'connected',
    status TEXT NOT NULL DEFAULT 'published',
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_mr_dir ON v06_market_resources(direction);
CREATE INDEX IF NOT EXISTS ix_v06_mr_type ON v06_market_resources(resource_type);
CREATE INDEX IF NOT EXISTS ix_v06_mr_status ON v06_market_resources(status);
CREATE INDEX IF NOT EXISTS ix_v06_mr_pub ON v06_market_resources(publisher_id);
CREATE INDEX IF NOT EXISTS ix_v06_mr_title ON v06_market_resources(title);

-- Cooperation opportunities
CREATE TABLE IF NOT EXISTS v06_opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    opp_type TEXT NOT NULL,
    source_type TEXT,
    source_id INTEGER,
    initiator_id INTEGER NOT NULL,
    organization_id INTEGER,
    target_person_id INTEGER,
    target_organization_id INTEGER,
    related_resource_id INTEGER,
    description TEXT,
    expected_outcome TEXT,
    stage TEXT NOT NULL DEFAULT 'lead',
    owner_id INTEGER,
    participants TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    visibility TEXT NOT NULL DEFAULT 'organization',
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_opp_type ON v06_opportunities(opp_type);
CREATE INDEX IF NOT EXISTS ix_v06_opp_stage ON v06_opportunities(stage);
CREATE INDEX IF NOT EXISTS ix_v06_opp_status ON v06_opportunities(status);
CREATE INDEX IF NOT EXISTS ix_v06_opp_initiator ON v06_opportunities(initiator_id);
CREATE INDEX IF NOT EXISTS ix_v06_opp_title ON v06_opportunities(title);

-- Follow-up records
CREATE TABLE IF NOT EXISTS v06_follow_ups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES v06_opportunities(id),
    follow_type TEXT NOT NULL DEFAULT 'note',
    content TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    followed_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    next_follow_at TEXT,
    visibility TEXT NOT NULL DEFAULT 'organization',
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_fu_opp ON v06_follow_ups(opportunity_id);

-- Collaboration tasks
CREATE TABLE IF NOT EXISTS v06_collab_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    opportunity_id INTEGER REFERENCES v06_opportunities(id),
    owner_id INTEGER NOT NULL,
    participants TEXT,
    due_date TEXT,
    priority TEXT NOT NULL DEFAULT 'P2',
    status TEXT NOT NULL DEFAULT 'todo',
    created_by INTEGER NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_ct_opp ON v06_collab_tasks(opportunity_id);
CREATE INDEX IF NOT EXISTS ix_v06_ct_owner ON v06_collab_tasks(owner_id);
CREATE INDEX IF NOT EXISTS ix_v06_ct_status ON v06_collab_tasks(status);

-- Timeline entries (for opportunities)
CREATE TABLE IF NOT EXISTS v06_timeline_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES v06_opportunities(id),
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    actor_id INTEGER,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_v06_te_opp ON v06_timeline_entries(opportunity_id);
"""


def backup_database() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{DB_PATH}.backup_v06m_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"[BACKUP] Created: {backup_path}")
    return backup_path


def run_migration():
    print(f"[MIGRATE] v0.6 Platform MVP migration starting...")
    print(f"[MIGRATE] Database: {DB_PATH}")
    if not DB_PATH.exists():
        print(f"[MIGRATE] ERROR: Database file not found at {DB_PATH}")
        return False

    backup_database()

    # Execute raw SQL 鈥?use raw sqlite3 connection's executescript for multi-statement DDL
    import sqlite3
    raw_conn = sqlite3.connect(str(DB_PATH))
    try:
        raw_conn.executescript(SCHEMA_SQL)
        raw_conn.commit()
        print("[MIGRATE] All DDL statements executed successfully.")
    except Exception as e:
        raw_conn.rollback()
        print(f"[MIGRATE] ERROR: {e}")
        return False
    finally:
        raw_conn.close()

    # Seed default tags using the service
    from app.database import get_db
    from app.services.platform_service import seed_default_tags
    db = next(get_db())
    try:
        seed_default_tags(db)
        print("[MIGRATE] Default industry tags seeded.")
    except Exception as e:
        print(f"[MIGRATE] ERROR seeding tags: {e}")
        return False
    finally:
        db.close()

    # Verify
    from sqlalchemy import inspect
    inspector = inspect(engine)
    expected_tables = [
        "v06_tags", "v06_person_tags", "v06_organization_tags",
        "v06_person_profiles", "v06_favorites", "v06_follows",
        "v06_contact_intents", "v06_intelligence_items", "v06_intel_subscriptions",
        "v06_market_resources", "v06_opportunities",
        "v06_follow_ups", "v06_collab_tasks", "v06_timeline_entries",
    ]
    existing = inspector.get_table_names()
    missing = [t for t in expected_tables if t not in existing]
    if missing:
        print(f"[MIGRATE] WARNING: Missing tables: {missing}")
    else:
        print(f"[MIGRATE] All {len(expected_tables)} tables verified.")

    # Verify tag count
    db = next(get_db())
    try:
        from sqlalchemy import text as stext
        tag_count = db.execute(stext("SELECT COUNT(*) FROM v06_tags")).scalar()
        print(f"[MIGRATE] Tag count: {tag_count}")
    finally:
        db.close()

    print("[MIGRATE] v0.6 Platform MVP migration completed successfully.")
    return True


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)

