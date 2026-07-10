import pytest


def test_fastapi_app_importable():
    from app.main import app
    assert app is not None


def test_routes_registered():
    from app.main import app
    routes = [r.path for r in app.routes]
    assert "/" in routes
    assert "/health" in routes
    assert "/api/v1/" in routes or any("/api/v1/" in r for r in routes)


def test_app_import_does_not_modify_db(temp_db_conn):
    initial_count = temp_db_conn.execute("SELECT COUNT(*) FROM v05a_users").fetchone()[0]
    from app.main import app
    assert app is not None
    final_count = temp_db_conn.execute("SELECT COUNT(*) FROM v05a_users").fetchone()[0]
    assert initial_count == final_count


def test_core_services_importable():
    from app.services.unified_resource_service import UnifiedResourceService
    from app.services.unified_opportunity_service import UnifiedOpportunityService
    from app.services.unified_intelligence_service import UnifiedIntelligenceService
    assert UnifiedResourceService is not None
    assert UnifiedOpportunityService is not None
    assert UnifiedIntelligenceService is not None
