"""Verify v0.6 Platform MVP against an isolated temporary SQLite database."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text
from sqlalchemy.orm import close_all_sessions
import gc
import time

from scripts.test_db_utils import foreign_key_check, run_migration_suite, temporary_database

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} - {detail}")


def _create_test_user_and_person(db):
    ts = datetime.now().replace(microsecond=0).isoformat()
    db.execute(text("""
        INSERT INTO people(external_id,name,is_active,manually_confirmed,subject_manually_confirmed,created_at,source_type,visibility,verification_status)
        VALUES (:external_id,:name,1,0,0,:ts,'verify_platform_mvp','internal','verified')
    """), {"external_id": f"PER-V06-MVP-{ts}", "name": "V06 MVP Test Person", "ts": ts})
    person_id = int(db.execute(text("SELECT last_insert_rowid()")).scalar())
    db.execute(text("""
        INSERT INTO v05a_users(username,display_name,password_hash,role,status,created_at,updated_at)
        VALUES (:username,'V06 MVP Test User','test-hash','admin','active',:ts,:ts)
    """), {"username": f"v06_mvp_{ts.replace(':','').replace('-','')}", "ts": ts, "person_id": person_id})
    user_id = int(db.execute(text("SELECT last_insert_rowid()")).scalar())
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS identity_link_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            request_reason TEXT,
            requested_at TEXT,
            reviewed_at TEXT,
            reviewed_by INTEGER,
            review_note TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(user_id) REFERENCES v05a_users(id),
            FOREIGN KEY(person_id) REFERENCES people(id)
        )
    """))
    db.execute(text("""
        INSERT INTO identity_link_requests(user_id,person_id,status,request_reason,requested_at,reviewed_at,created_at,updated_at)
        VALUES (:user_id,:person_id,'approved','verify',:ts,:ts,:ts,:ts)
    """), {"user_id": user_id, "person_id": person_id, "ts": ts})
    db.commit()
    return user_id, person_id


def run() -> bool:
    global PASS, FAIL
    PASS = FAIL = 0
    print("=" * 60)
    print("v0.6 Platform MVP Verification")
    print("=" * 60)

    from app.database import Base, SessionLocal, engine
    from app.models_platform import MarketResource
    from app.services.platform_service import (
        seed_default_tags, list_tags, get_person_tags, upsert_person_profile,
        toggle_favorite, toggle_follow,
        create_contact_intent, list_contact_intents,
        discover_people, recommend_people,
        list_intelligence, personalized_feed,
        list_market_resources, match_resources,
        create_opportunity, update_opportunity_stage, create_follow_up, create_collab_task,
        unified_search,
    )

    Base.metadata.create_all(bind=engine)
    inspector = None
    db = SessionLocal()
    try:
        user_id, person_id = _create_test_user_and_person(db)

        print("\n--- Schema & Migration ---")
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected = ["v06_tags", "v06_person_tags", "v06_person_profiles", "v06_favorites",
                    "v06_follows", "v06_contact_intents", "v06_intelligence_items",
                    "v06_intel_subscriptions", "v06_market_resources", "v06_opportunities",
                    "v06_follow_ups", "v06_collab_tasks", "v06_timeline_entries"]
        for t in expected:
            check(f"Table {t} exists", t in tables)

        print("\n--- Tags ---")
        seed_default_tags(db)
        tags = list_tags(db)
        check("Tags seeded", len(tags) > 0, f"got {len(tags)} tags")
        groups = {t.tag_group for t in tags}
        check("Has user_type tags", "user_type" in groups)
        check("Has industry_direction tags", "industry_direction" in groups)
        check("Has capability tags", "capability" in groups)
        check("Has need tags", "need" in groups)

        print("\n--- People Discovery ---")
        people_result = discover_people(db, page=1, page_size=10)
        check("People discovery returns items", isinstance(people_result, dict))
        check("People total is integer", isinstance(people_result.get("total", 0), int))

        print("\n--- Recommendations ---")
        check("Recommendations returns list", isinstance(recommend_people(db, user_id, limit=5), list))

        print("\n--- Intelligence ---")
        check("Intelligence list returns dict", isinstance(list_intelligence(db, page=1, page_size=10), dict))
        check("Personalized feed returns list", isinstance(personalized_feed(db, user_id, limit=5), list))

        print("\n--- Resources ---")
        check("Resources list returns dict", isinstance(list_market_resources(db, page=1, page_size=10), dict))

        print("\n--- Favorites ---")
        check("Favorite toggle works", isinstance(toggle_favorite(db, user_id, "test", 9999), dict))

        print("\n--- Follows ---")
        check("Follow toggle works", isinstance(toggle_follow(db, user_id, "test", 9999), dict))

        print("\n--- Contact Intents ---")
        ci = create_contact_intent(db, user_id, "person", person_id + 1, "connection", "test")
        check("Contact intent created", ci is not None)
        check("Sent intents retrievable", len(list_contact_intents(db, user_id, "sent")) > 0)

        print("\n--- Unified Search ---")
        result = unified_search(db, "test")
        check("Search returns groups", "groups" in result)
        check("Search returns total", "total" in result)

        print("\n--- Opportunities ---")
        opp = create_opportunity(db, title="Test Opp", opp_type="technology", initiator_id=user_id, owner_id=user_id, status="active")
        check("Opportunity created", opp is not None)
        if opp:
            check("Stage updated", (updated := update_opportunity_stage(db, opp.id, "contacted", user_id)) is not None and updated.stage == "contacted")
            check("Follow-up created", create_follow_up(db, opportunity_id=opp.id, content="test follow-up", created_by=user_id) is not None)
            check("Task created", create_collab_task(db, title="Test Task", opportunity_id=opp.id, owner_id=user_id, created_by=user_id) is not None)

        print("\n--- Resource Matching ---")
        r1 = MarketResource(title="Test Supply", direction="supply", resource_type="CRO", industry_direction="Innovative Drug", region="Shanghai", status="published", publisher_id=user_id)
        r2 = MarketResource(title="Test Demand", direction="demand", resource_type="CRO", industry_direction="Innovative Drug", region="Shanghai", status="published", publisher_id=user_id)
        db.add_all([r1, r2]); db.commit()
        check("Resource matching works", isinstance(match_resources(db, r1.id, limit=5), list))

        print("\n--- Person Profile ---")
        check("Profile upsert works", upsert_person_profile(db, person_id, bio="test bio", is_demo=True) is not None)
        check("Get person tags works", isinstance(get_person_tags(db, person_id), list))

        print("\n--- Database Integrity ---")
        db.commit()
        check("Foreign key check is clean", foreign_key_check(Path(__import__('os').environ['APP_DB_PATH'])) == 0)
    except Exception as e:
        print(f"\n[FATAL] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        FAIL += 1
    finally:
        db.close()
        inspector = None
        close_all_sessions()
        engine.dispose(close=True)
        gc.collect()
        time.sleep(0.2)

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")
    return FAIL == 0


def main() -> int:
    with temporary_database("platform_mvp_verify_") as db_path:
        run_migration_suite(db_path)
        success = run()
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
