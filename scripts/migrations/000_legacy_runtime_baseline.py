from __future__ import annotations

MIGRATION_ID = "000_legacy_runtime_baseline"

# Explicit schema-only baseline for a genuinely empty database.  It contains no
# seed or demo rows and exists solely to make the numbered 001-008 chain
# independent from ORM metadata.create_all and historical test fixtures.
REQUIRED_COLUMNS = {
    "people": {"id", "external_id", "name"},
    "organizations": {"id", "external_id", "standard_name"},
    "projects": {"id", "external_id", "name"},
    "resources": {"id", "external_id"},
    "events": {"id", "external_id", "name"},
    "relations": {"id", "external_id"},
    "raw_intelligence": {"id", "title", "source_url"},
    "v04e_duplicate_candidates": {"id"},
    "v04e_entity_aliases": {"id"},
    "v04g_monitoring_sources": {"id", "source_no", "name", "url"},
    "v04g_monitoring_runs": {"id", "run_no", "monitoring_source_id"},
    "v04g_source_snapshots": {"id", "snapshot_no", "url"},
    "v05g_processing_jobs": {"id"},
    "v05g_extraction_candidates": {"id", "candidate_no"},
    "v05h_generated_reports": {"id", "report_no"},
    "research_topics": {"id", "topic_no", "name"},
    "v05a_users": {"id", "username"},
    "v04f_club_applications": {"id", "application_no"},
    "v04f_club_memberships": {"id", "member_no"},
    "v05c_club_event_profiles": {"id", "event_no"},
    "v05c_club_event_registrations": {"id", "registration_no"},
    "v05c_club_event_participation": {"id", "club_event_id"},
    "v06_intelligence_items": {"id", "title", "source_url"},
    "v06_market_resources": {"id", "title", "direction"},
    "v06_opportunities": {"id", "title", "source_type", "source_id"},
    "v06_follow_ups": {"id", "opportunity_id"},
    "v06_collab_tasks": {"id", "opportunity_id"},
    "v06_timeline_entries": {"id", "opportunity_id"},
    "v04f_lead_records": {"id", "lead_no", "subject_type", "subject_id"},
}

BASE_TABLES = set(REQUIRED_COLUMNS)

TABLE_SQL = r"""
CREATE TABLE people (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, name TEXT,
 ability_tags TEXT, verification_status TEXT, is_active INTEGER DEFAULT 1,
 created_at TEXT, updated_at TEXT
);
CREATE TABLE organizations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, standard_name TEXT,
 org_type TEXT, region TEXT, industry_tags TEXT, verification_status TEXT,
 is_active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT
);
CREATE TABLE projects (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, name TEXT,
 focus_tags TEXT, status TEXT, owner_external_id TEXT, owner_organization_id INTEGER,
 is_active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT
);
CREATE TABLE resources (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, name TEXT, title TEXT,
 owner_external_id TEXT, owner_organization_id INTEGER, is_active INTEGER DEFAULT 1,
 created_at TEXT, updated_at TEXT
);
CREATE TABLE events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, event_date TEXT,
 name TEXT, event_type TEXT, related_entity TEXT, related_organization_id INTEGER,
 fact_summary TEXT, verification_status TEXT, is_active INTEGER DEFAULT 1,
 created_at TEXT, updated_at TEXT
);
CREATE TABLE relations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT UNIQUE, source_external_id TEXT,
 relation_type TEXT, target_external_id TEXT, verification_status TEXT,
 is_active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT
);
CREATE TABLE raw_intelligence (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, source_url TEXT, source_type TEXT,
 content TEXT, visibility TEXT, review_status TEXT, created_at TEXT
);
CREATE TABLE v04e_duplicate_candidates (
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_no TEXT UNIQUE
);
CREATE TABLE v04e_entity_aliases (
 id INTEGER PRIMARY KEY AUTOINCREMENT, alias_no TEXT UNIQUE
);
CREATE TABLE v04g_monitoring_sources (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_no TEXT UNIQUE, name TEXT,
 source_type TEXT, url TEXT, check_frequency TEXT, is_enabled INTEGER DEFAULT 1,
 fetch_mode TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE v04g_monitoring_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, run_no TEXT UNIQUE, monitoring_source_id INTEGER,
 status TEXT, started_at TEXT, finished_at TEXT, created_at TEXT
);
CREATE TABLE v04g_source_snapshots (
 id INTEGER PRIMARY KEY AUTOINCREMENT, snapshot_no TEXT UNIQUE,
 monitoring_source_id INTEGER, monitoring_run_id INTEGER, page_title TEXT, url TEXT,
 captured_at TEXT, raw_content TEXT, cleaned_text TEXT, content_hash TEXT,
 metadata_json TEXT, created_at TEXT
);
CREATE TABLE v05g_processing_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_no TEXT UNIQUE, status TEXT, created_at TEXT
);
CREATE TABLE v05g_extraction_candidates (
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_no TEXT UNIQUE,
 processing_job_id INTEGER, snapshot_id INTEGER, candidate_type TEXT,
 review_status TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE v05h_generated_reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT, report_no TEXT UNIQUE, report_job_id INTEGER,
 title TEXT, report_type TEXT, status TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE research_topics (
 id INTEGER PRIMARY KEY AUTOINCREMENT, topic_no TEXT UNIQUE, name TEXT,
 description TEXT, topic_type TEXT, status TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE v05a_users (
 id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT,
 role TEXT, status TEXT DEFAULT 'active', created_at TEXT, updated_at TEXT
);
CREATE TABLE v04f_club_applications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, application_no TEXT UNIQUE, applicant_name TEXT,
 status TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE v04f_club_memberships (
 id INTEGER PRIMARY KEY AUTOINCREMENT, member_no TEXT UNIQUE, person_id INTEGER,
 organization_id INTEGER, user_id INTEGER, status TEXT, owner TEXT,
 created_at TEXT, updated_at TEXT
);
CREATE TABLE v05c_club_event_profiles (
 id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, event_no TEXT UNIQUE,
 event_type TEXT, status TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE v05c_club_event_registrations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, registration_no TEXT UNIQUE,
 club_event_id INTEGER, membership_id INTEGER, applicant_name TEXT, status TEXT,
 registered_at TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE v05c_club_event_participation (
 id INTEGER PRIMARY KEY AUTOINCREMENT, club_event_id INTEGER, registration_id INTEGER,
 membership_id INTEGER, attendance_status TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE v06_intelligence_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, source_url TEXT,
 source_name TEXT, status TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE v06_market_resources (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, direction TEXT, resource_type TEXT,
 publisher_id INTEGER, status TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE v06_opportunities (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, opp_type TEXT, source_type TEXT,
 source_id INTEGER, initiator_id INTEGER, organization_id INTEGER, description TEXT,
 expected_outcome TEXT, stage TEXT DEFAULT 'lead', owner_id INTEGER,
 status TEXT DEFAULT 'active', visibility TEXT, is_demo INTEGER DEFAULT 0,
 created_at TEXT, updated_at TEXT
);
CREATE TABLE v06_follow_ups (
 id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER, follow_type TEXT,
 content TEXT, created_by INTEGER, followed_at TEXT, next_follow_at TEXT,
 visibility TEXT, created_at TEXT
);
CREATE TABLE v06_collab_tasks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, opportunity_id INTEGER,
 owner_id INTEGER, participants TEXT, due_date TEXT, priority TEXT, status TEXT,
 created_by INTEGER, is_demo INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT
);
CREATE TABLE v06_timeline_entries (
 id INTEGER PRIMARY KEY AUTOINCREMENT, opportunity_id INTEGER, event_type TEXT,
 description TEXT, actor_id INTEGER, metadata_json TEXT, created_at TEXT
);
CREATE TABLE v04f_lead_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lead_no TEXT UNIQUE, subject_type TEXT,
 subject_id TEXT, funnel_stage TEXT, system_score INTEGER DEFAULT 0,
 system_grade TEXT DEFAULT 'C', owner TEXT, next_action TEXT,
 status TEXT DEFAULT 'active', created_at TEXT, updated_at TEXT
);
CREATE TABLE v04f_club_needs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TEXT
);
CREATE TABLE v04f_club_offerings (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TEXT
);
CREATE TABLE v04f_club_matches (
 id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT
);
"""
