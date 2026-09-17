"""Additive training and room booking storage, without demo data."""
REQUIRED_TABLES = {"knowledge_items", "learning_paths", "user_knowledge_progress", "v05a_users", "v04f_club_memberships"}
ADDITIVE_COLUMNS = {
    "knowledge_items": {"knowledge_type": "TEXT NOT NULL DEFAULT 'INDUSTRY'", "source_file": "TEXT NOT NULL DEFAULT ''", "source_version": "TEXT NOT NULL DEFAULT ''", "source_section": "TEXT NOT NULL DEFAULT ''", "effective_date": "TEXT NOT NULL DEFAULT ''", "expiry_date": "TEXT NOT NULL DEFAULT ''", "applicable_to": "TEXT NOT NULL DEFAULT ''"},
    "learning_paths": {"learning_type": "TEXT NOT NULL DEFAULT 'GENERAL_LEARNING'", "version": "TEXT NOT NULL DEFAULT '1'", "effective_date": "TEXT NOT NULL DEFAULT ''", "audience": "TEXT NOT NULL DEFAULT 'ALL_USERS'", "requires_exam": "INTEGER NOT NULL DEFAULT 0"},
    "user_knowledge_progress": {"training_history_json": "TEXT NOT NULL DEFAULT '{}'"},
}
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_annotations (
 id INTEGER PRIMARY KEY AUTOINCREMENT, knowledge_id INTEGER NOT NULL REFERENCES knowledge_items(id),
 user_id INTEGER NOT NULL REFERENCES v05a_users(id), type TEXT NOT NULL CHECK(type IN ('NOTE','VIEWPOINT','COMMENT')),
 content TEXT NOT NULL, visibility TEXT NOT NULL CHECK(visibility IN ('PRIVATE','INTERNAL')),
 parent_id INTEGER REFERENCES knowledge_annotations(id), deleted INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_questions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, knowledge_id INTEGER NOT NULL REFERENCES knowledge_items(id),
 title TEXT NOT NULL, question_type TEXT NOT NULL CHECK(question_type IN ('SINGLE_CHOICE','MULTIPLE_CHOICE','TRUE_FALSE')),
 options_json TEXT NOT NULL, correct_json TEXT NOT NULL, explanation TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL CHECK(status IN ('ACTIVE','INACTIVE')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_exams (
 id INTEGER PRIMARY KEY AUTOINCREMENT, path_id INTEGER NOT NULL UNIQUE REFERENCES learning_paths(id),
 title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', pass_score INTEGER NOT NULL CHECK(pass_score BETWEEN 1 AND 100),
 max_attempts INTEGER NOT NULL CHECK(max_attempts BETWEEN 1 AND 100), random_order INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL CHECK(status IN ('DRAFT','PUBLISHED','ARCHIVED')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_exam_questions (
 exam_id INTEGER NOT NULL REFERENCES knowledge_exams(id), question_id INTEGER NOT NULL REFERENCES knowledge_questions(id),
 position INTEGER NOT NULL, PRIMARY KEY(exam_id,question_id), UNIQUE(exam_id,position)
);
CREATE TABLE IF NOT EXISTS knowledge_exam_attempts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, exam_id INTEGER NOT NULL REFERENCES knowledge_exams(id),
 user_id INTEGER NOT NULL REFERENCES v05a_users(id), path_version TEXT NOT NULL, attempt_no INTEGER NOT NULL,
 started_at TEXT NOT NULL, submitted_at TEXT, score REAL, passed INTEGER, answers_json TEXT NOT NULL,
 UNIQUE(exam_id,user_id,path_version,attempt_no)
);
CREATE INDEX IF NOT EXISTS ix_knowledge_attempt_user ON knowledge_exam_attempts(user_id,exam_id,path_version);
CREATE TABLE IF NOT EXISTS club_facilities (
 id INTEGER PRIMARY KEY AUTOINCREMENT, facility_type TEXT NOT NULL DEFAULT 'MEETING_ROOM' CHECK(facility_type='MEETING_ROOM'),
 name TEXT NOT NULL, location TEXT NOT NULL, capacity INTEGER NOT NULL CHECK(capacity>0),
 facilities TEXT NOT NULL DEFAULT '', instructions TEXT NOT NULL DEFAULT '', is_open INTEGER NOT NULL DEFAULT 1,
 open_start TEXT NOT NULL, open_end TEXT NOT NULL, min_minutes INTEGER NOT NULL, max_minutes INTEGER NOT NULL,
 advance_days INTEGER NOT NULL, allow_members INTEGER NOT NULL DEFAULT 1, tenant_auto_confirm INTEGER NOT NULL DEFAULT 0,
 non_tenant_review INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(min_minutes>0 AND max_minutes>=min_minutes AND advance_days>=0)
);
CREATE TABLE IF NOT EXISTS club_facility_bookings (
 id INTEGER PRIMARY KEY AUTOINCREMENT, facility_id INTEGER NOT NULL REFERENCES club_facilities(id),
 user_id INTEGER NOT NULL REFERENCES v05a_users(id), person_id INTEGER REFERENCES people(id),
 organization_id INTEGER REFERENCES organizations(id), membership_id INTEGER NOT NULL REFERENCES v04f_club_memberships(id),
 member_type TEXT NOT NULL, start_at TEXT NOT NULL, end_at TEXT NOT NULL, attendee_count INTEGER NOT NULL CHECK(attendee_count>0),
 purpose TEXT NOT NULL, contact_name TEXT NOT NULL, contact_method TEXT NOT NULL, remark TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL CHECK(status IN ('PENDING','CONFIRMED','REJECTED','CANCELLED','COMPLETED')),
 review_note TEXT NOT NULL DEFAULT '', reviewed_by INTEGER REFERENCES v05a_users(id), reviewed_at TEXT,
 request_token TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, CHECK(end_at>start_at)
);
CREATE INDEX IF NOT EXISTS ix_club_booking_interval ON club_facility_bookings(facility_id,status,start_at,end_at);
"""
