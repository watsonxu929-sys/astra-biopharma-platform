import pytest


def test_unconfirmed_opportunity_rejected(temp_db_conn):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from app.services.unified_opportunity_service import UnifiedOpportunityService
    
    db_path = str(temp_db_conn.execute("PRAGMA database_list").fetchone()["file"])
    engine = create_engine(f"sqlite:///{db_path}")
    TestingSessionLocal = sessionmaker(bind=engine)
    
    with TestingSessionLocal() as s:
        uid = s.execute(text("SELECT id FROM v05a_users ORDER BY id LIMIT 1")).scalar()
        assert uid is not None
        
        opportunities = UnifiedOpportunityService(s)
        
        try:
            opportunities.create(actor_user_id=int(uid), fields={"title": "Should be rejected"})
            assert False, "Should have raised an exception"
        except Exception as exc:
            assert hasattr(exc, "status_code") and exc.status_code == 409


def test_confirmed_opportunity_accepted(temp_db_conn):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from app.services.unified_opportunity_service import UnifiedOpportunityService
    
    db_path = str(temp_db_conn.execute("PRAGMA database_list").fetchone()["file"])
    engine = create_engine(f"sqlite:///{db_path}")
    TestingSessionLocal = sessionmaker(bind=engine)
    
    with TestingSessionLocal() as s:
        uid = s.execute(text("SELECT id FROM v05a_users ORDER BY id LIMIT 1")).scalar()
        assert uid is not None
        
        opportunities = UnifiedOpportunityService(s)
        opp = opportunities.create(
            actor_user_id=int(uid),
            fields={
                "title": "Test confirmed opportunity",
                "human_confirmed": True,
                "priority": "P2",
                "visibility": "private",
            }
        )
        
        assert opp.id is not None
        assert opp.human_confirmed_by == int(uid)
        assert opp.human_confirmed_at is not None


def test_confirmation_fields_required():
    from app.models_platform import CooperationOpportunity
    assert hasattr(CooperationOpportunity, "human_confirmed_by")
    assert hasattr(CooperationOpportunity, "human_confirmed_at")
