import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ["DATABASE_URL"] = "sqlite:///data/acceptance/t5_1_mvp.db"

from sqlalchemy import create_engine, text


def run_migration_008():
    engine = create_engine("sqlite:///data/acceptance/t5_1_mvp.db", connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        print("执行008业务协同迁移...")
        
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='v04f_lead_records'"))
        if result.first():
            print("v04f_lead_records已存在，添加缺失列...")
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(v04f_lead_records)"))]
            def add_col_if_not_exists(name, definition):
                if name not in cols:
                    try:
                        conn.execute(text(f"ALTER TABLE v04f_lead_records ADD COLUMN {name} {definition}"))
                        print(f"  添加列: {name}")
                    except Exception as e:
                        print(f"  添加列失败 {name}: {e}")
            add_col_if_not_exists("lifecycle_status", "TEXT DEFAULT 'new'")
            add_col_if_not_exists("decision_reason", "TEXT")
            add_col_if_not_exists("converted_opportunity_id", "INTEGER")
            add_col_if_not_exists("pilot_batch_id", "TEXT")
            add_col_if_not_exists("owner_user_id", "INTEGER")
            add_col_if_not_exists("priority", "TEXT DEFAULT 'P2'")
            add_col_if_not_exists("suggested_next_action", "TEXT")
            add_col_if_not_exists("demand_organization_id", "INTEGER")
            add_col_if_not_exists("supply_organization_id", "INTEGER")
            add_col_if_not_exists("person_ids_json", "TEXT")
            add_col_if_not_exists("organization_ids_json", "TEXT")
            add_col_if_not_exists("recommendation_reason", "TEXT")
            add_col_if_not_exists("relationship_path_json", "TEXT")
            add_col_if_not_exists("evidence_json", "TEXT")
            add_col_if_not_exists("source_type", "TEXT")
            add_col_if_not_exists("source_record_id", "TEXT")
            add_col_if_not_exists("title", "TEXT")
        else:
            conn.execute(text("""
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

        conn.execute(text("""
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

        conn.execute(text("""
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

        conn.execute(text("""
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

        conn.execute(text("""
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

        conn.execute(text("""
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

        conn.execute(text("""
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

        conn.execute(text("""
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

        conn.execute(text("""
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

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_v04f_lifecycle_status ON v04f_lead_records(lifecycle_status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_v04f_source_type ON v04f_lead_records(source_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_p5_participants_opp ON p5_opportunity_participants(opportunity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_p5_stage_history_opp ON p5_opportunity_stage_history(opportunity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_p5_sources_opp ON p5_opportunity_sources(opportunity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_p5_meetings_opp ON p5_opportunity_meetings(opportunity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_p5_artifacts_opp ON p5_opportunity_artifacts(opportunity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_p5_risks_opp ON p5_opportunity_risks(opportunity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_p5_domain_events_aggregate ON p5_domain_events(aggregate_type, aggregate_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_p5_audit_target ON p5_operation_audit(target_type, target_id)"))

        conn.commit()
        print("008迁移执行成功")


def verify_tables():
    engine = create_engine("sqlite:///data/acceptance/t5_1_mvp.db", connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'p5_%' OR name='v04f_lead_records'"))
        tables = [row[0] for row in result]
        print(f"\n已创建的P5表: {tables}")
        print(f"总计: {len(tables)}个表")


def main():
    print("开始在验收数据库上执行008迁移...")
    
    print("\n首次执行:")
    run_migration_008()
    
    print("\n再次执行验证幂等性:")
    run_migration_008()
    
    verify_tables()
    
    print("\n迁移完成！")


if __name__ == "__main__":
    main()
