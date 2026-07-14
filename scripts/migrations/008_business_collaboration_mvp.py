from __future__ import annotations

from typing import Any

from sqlalchemy import text


def upgrade(db) -> None:
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS v04f_lead_records(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_no TEXT UNIQUE,
            subject_type TEXT,
            subject_id TEXT,
            funnel_stage TEXT,
            system_score INTEGER DEFAULT 0,
            system_grade TEXT DEFAULT 'C',
            owner TEXT,
            next_action TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT,
            title TEXT,
            source_type TEXT,
            source_record_id TEXT,
            demand_organization_id INTEGER,
            supply_organization_id INTEGER,
            person_ids_json TEXT,
            organization_ids_json TEXT,
            recommendation_reason TEXT,
            relationship_path_json TEXT,
            evidence_json TEXT,
            owner_user_id INTEGER,
            priority TEXT DEFAULT 'P2',
            suggested_next_action TEXT,
            lifecycle_status TEXT DEFAULT 'new',
            decision_reason TEXT,
            converted_opportunity_id INTEGER,
            pilot_batch_id TEXT
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS p5_opportunity_participants(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER,
            participant_type TEXT,
            participant_id TEXT,
            role TEXT,
            is_internal INTEGER DEFAULT 0,
            visibility TEXT DEFAULT 'organization',
            started_at TEXT,
            ended_at TEXT,
            added_by_user_id INTEGER,
            pilot_batch_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(opportunity_id, participant_type, participant_id, role)
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS p5_opportunity_stage_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER,
            old_stage TEXT,
            new_stage TEXT,
            reason TEXT,
            actor_user_id INTEGER,
            unresolved_task_count INTEGER DEFAULT 0,
            pilot_batch_id TEXT,
            created_at TEXT
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS p5_opportunity_sources(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER,
            source_type TEXT,
            source_record_id TEXT,
            source_label TEXT,
            evidence_json TEXT,
            relationship_path_json TEXT,
            added_by_user_id INTEGER,
            pilot_batch_id TEXT,
            created_at TEXT,
            UNIQUE(opportunity_id, source_type, source_record_id)
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS p5_opportunity_meetings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_no TEXT UNIQUE,
            opportunity_id INTEGER,
            subject TEXT,
            starts_at TEXT,
            ends_at TEXT,
            location TEXT,
            online_url TEXT,
            organizer_user_id INTEGER,
            participants_json TEXT,
            agenda TEXT,
            status TEXT DEFAULT 'scheduled',
            minutes TEXT,
            decisions TEXT,
            external_calendar_id TEXT,
            calendar_sync_status TEXT DEFAULT 'not_started',
            visibility TEXT DEFAULT 'organization',
            completed_at TEXT,
            pilot_batch_id TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS p5_opportunity_artifacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artifact_no TEXT UNIQUE,
            opportunity_id INTEGER,
            follow_up_id INTEGER,
            meeting_id INTEGER,
            file_name TEXT,
            artifact_type TEXT DEFAULT 'other',
            local_path TEXT,
            external_url TEXT,
            file_hash TEXT,
            uploaded_by_user_id INTEGER,
            visibility TEXT DEFAULT 'organization',
            version INTEGER DEFAULT 1,
            pilot_batch_id TEXT,
            created_at TEXT
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS p5_opportunity_risks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER,
            risk_type TEXT,
            risk_level TEXT,
            reason TEXT,
            suggested_action TEXT,
            status TEXT DEFAULT 'open',
            detected_at TEXT,
            pilot_batch_id TEXT,
            UNIQUE(opportunity_id, risk_type, status)
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS p5_domain_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            event_type TEXT,
            aggregate_type TEXT,
            aggregate_id TEXT,
            payload_json TEXT,
            actor_user_id INTEGER,
            occurred_at TEXT,
            status TEXT DEFAULT 'pending',
            pilot_batch_id TEXT
        )
    """))

    db.execute(text("""
        CREATE TABLE IF NOT EXISTS p5_operation_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_no TEXT UNIQUE,
            action TEXT,
            target_type TEXT,
            target_id TEXT,
            before_json TEXT,
            after_json TEXT,
            actor_user_id INTEGER,
            reason TEXT,
            result TEXT DEFAULT 'success',
            pilot_batch_id TEXT,
            created_at TEXT
        )
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_v04f_lifecycle_status ON v04f_lead_records(lifecycle_status)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_v04f_source_type ON v04f_lead_records(source_type)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_p5_participants_opp ON p5_opportunity_participants(opportunity_id)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_p5_stage_history_opp ON p5_opportunity_stage_history(opportunity_id)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_p5_sources_opp ON p5_opportunity_sources(opportunity_id)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_p5_meetings_opp ON p5_opportunity_meetings(opportunity_id)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_p5_artifacts_opp ON p5_opportunity_artifacts(opportunity_id)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_p5_risks_opp ON p5_opportunity_risks(opportunity_id)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_p5_domain_events_aggregate ON p5_domain_events(aggregate_type, aggregate_id)
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_p5_audit_target ON p5_operation_audit(target_type, target_id)
    """))

    db.commit()


def downgrade(db) -> None:
    pass


def migrate(db) -> dict[str, Any]:
    upgrade(db)
    return {"status": "ok", "message": "P5 business collaboration tables created"}
