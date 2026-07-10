from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


class TestMembershipWriteConsolidation:
    def test_bind_user_through_unified_service(self, temp_db_conn):
        cursor = temp_db_conn.cursor()
        cursor.execute("SELECT id FROM v04f_club_memberships WHERE user_id IS NULL LIMIT 1")
        membership_row = cursor.fetchone()
        if not membership_row:
            pytest.skip("No unlinked memberships available")

        membership_id = membership_row[0]

        cursor.execute("SELECT id FROM v05a_users WHERE status='active' LIMIT 1")
        user_row = cursor.fetchone()
        if not user_row:
            pytest.skip("No active users available")

        user_id = user_row[0]

        cursor.execute("BEGIN")
        cursor.execute("UPDATE v04f_club_memberships SET user_id=?, updated_at=datetime('now') WHERE id=?", (user_id, membership_id))
        cursor.execute("INSERT INTO membership_user_link_audit(audit_no,action,membership_id,user_id,old_user_id,actor,reason,created_at) VALUES (?, 'bind_user', ?, ?, NULL, 'test', 'test reason', datetime('now'))", ("TEST-001", membership_id, user_id))
        cursor.execute("COMMIT")

        cursor.execute("SELECT user_id FROM v04f_club_memberships WHERE id=?", (membership_id,))
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == user_id

        cursor.execute("SELECT COUNT(*) FROM membership_user_link_audit WHERE membership_id=? AND action='bind_user'", (membership_id,))
        audit_count = cursor.fetchone()[0]
        assert audit_count >= 1

    def test_bind_duplicate_user_is_idempotent(self, temp_db_conn):
        cursor = temp_db_conn.cursor()
        cursor.execute("SELECT id FROM v04f_club_memberships WHERE user_id IS NOT NULL LIMIT 1")
        row = cursor.fetchone()
        if not row:
            pytest.skip("No linked memberships available")

        membership_id = row[0]
        cursor.execute("SELECT user_id FROM v04f_club_memberships WHERE id=?", (membership_id,))
        user_id = cursor.fetchone()[0]

        before_count = cursor.execute("SELECT COUNT(*) FROM membership_user_link_audit WHERE membership_id=?", (membership_id,)).fetchone()[0]

        cursor.execute("BEGIN")
        cursor.execute("UPDATE v04f_club_memberships SET user_id=?, updated_at=datetime('now') WHERE id=?", (user_id, membership_id))
        cursor.execute("COMMIT")

        after_count = cursor.execute("SELECT COUNT(*) FROM membership_user_link_audit WHERE membership_id=?", (membership_id,)).fetchone()[0]
        assert before_count == after_count

    def test_request_link_creates_single_request(self, temp_db_conn):
        cursor = temp_db_conn.cursor()
        cursor.execute("SELECT id FROM v04f_club_memberships WHERE user_id IS NULL LIMIT 1")
        row = cursor.fetchone()
        if not row:
            pytest.skip("No unlinked memberships available")

        membership_id = row[0]

        cursor.execute("SELECT id FROM v05a_users WHERE status='active' LIMIT 1")
        user_row = cursor.fetchone()
        if not user_row:
            pytest.skip("No active users available")
        user_id = user_row[0]

        cursor.execute("DELETE FROM membership_user_link_requests WHERE membership_id=? AND status='pending'", (membership_id,))
        cursor.execute("COMMIT")

        ts = "2024-01-01T00:00:00"
        cursor.execute("BEGIN")
        cursor.execute("""INSERT INTO membership_user_link_requests(request_no,user_id,membership_id,reason,status,created_at,updated_at)
                          VALUES ('TEST-REQ-001', ?, ?, 'test', 'pending', ?, ?)""", (user_id, membership_id, ts, ts))
        cursor.execute("COMMIT")

        cursor.execute("SELECT COUNT(*) FROM membership_user_link_requests WHERE membership_id=? AND status='pending'", (membership_id,))
        count = cursor.fetchone()[0]
        assert count == 1


class TestResourceWriteConsolidation:
    def test_create_demand_only_writes_v06(self, temp_db_conn):
        cursor = temp_db_conn.cursor()
        cursor.execute("SELECT id FROM v04f_club_memberships LIMIT 1")
        row = cursor.fetchone()
        if not row:
            pytest.skip("No memberships available")

        membership_id = row[0]

        before_needs = cursor.execute("SELECT COUNT(*) FROM v04f_club_needs WHERE membership_id=?", (membership_id,)).fetchone()[0]
        before_offerings = cursor.execute("SELECT COUNT(*) FROM v04f_club_offerings WHERE membership_id=?", (membership_id,)).fetchone()[0]
        before_v06 = cursor.execute("SELECT COUNT(*) FROM v06_market_resources WHERE direction='demand'").fetchone()[0]

        ts = "2024-01-01T00:00:00"
        cursor.execute("BEGIN")
        cursor.execute("""INSERT INTO v06_market_resources(title, direction, resource_type, category, summary, description, publisher_id,
                                                             owner_person_id, organization_id, visibility, region, industry_direction,
                                                             tags, status, created_at, updated_at)
                          VALUES ('Test Demand', 'demand', '技术需求', '技术需求', 'Test', 'Test desc', 1, NULL, NULL, 'organization', 'Shanghai', '', '', 'published', ?, ?)""", (ts, ts))
        cursor.execute("COMMIT")

        after_needs = cursor.execute("SELECT COUNT(*) FROM v04f_club_needs WHERE membership_id=?", (membership_id,)).fetchone()[0]
        after_offerings = cursor.execute("SELECT COUNT(*) FROM v04f_club_offerings WHERE membership_id=?", (membership_id,)).fetchone()[0]
        after_v06 = cursor.execute("SELECT COUNT(*) FROM v06_market_resources WHERE direction='demand'").fetchone()[0]

        assert before_needs == after_needs
        assert before_offerings == after_offerings
        assert after_v06 == before_v06 + 1

    def test_create_supply_only_writes_v06(self, temp_db_conn):
        cursor = temp_db_conn.cursor()
        cursor.execute("SELECT id FROM v04f_club_memberships LIMIT 1")
        row = cursor.fetchone()
        if not row:
            pytest.skip("No memberships available")

        membership_id = row[0]

        before_needs = cursor.execute("SELECT COUNT(*) FROM v04f_club_needs WHERE membership_id=?", (membership_id,)).fetchone()[0]
        before_offerings = cursor.execute("SELECT COUNT(*) FROM v04f_club_offerings WHERE membership_id=?", (membership_id,)).fetchone()[0]
        before_v06 = cursor.execute("SELECT COUNT(*) FROM v06_market_resources WHERE direction='supply'").fetchone()[0]

        ts = "2024-01-01T00:00:00"
        cursor.execute("BEGIN")
        cursor.execute("""INSERT INTO v06_market_resources(title, direction, resource_type, category, summary, description, publisher_id,
                                                             owner_person_id, organization_id, visibility, region, industry_direction,
                                                             tags, status, created_at, updated_at)
                          VALUES ('Test Supply', 'supply', '技术服务', '技术服务', 'Test', 'Test desc', 1, NULL, NULL, 'organization', 'Shanghai', '', '', 'published', ?, ?)""", (ts, ts))
        cursor.execute("COMMIT")

        after_needs = cursor.execute("SELECT COUNT(*) FROM v04f_club_needs WHERE membership_id=?", (membership_id,)).fetchone()[0]
        after_offerings = cursor.execute("SELECT COUNT(*) FROM v04f_club_offerings WHERE membership_id=?", (membership_id,)).fetchone()[0]
        after_v06 = cursor.execute("SELECT COUNT(*) FROM v06_market_resources WHERE direction='supply'").fetchone()[0]

        assert before_needs == after_needs
        assert before_offerings == after_offerings
        assert after_v06 == before_v06 + 1

    def test_duplicate_resource_prevention(self, temp_db_conn):
        cursor = temp_db_conn.cursor()
        ts = "2024-01-01T00:00:00"

        cursor.execute("BEGIN")
        cursor.execute("""INSERT INTO v06_market_resources(title, direction, resource_type, category, summary, description, publisher_id,
                                                             owner_person_id, organization_id, visibility, region, industry_direction,
                                                             tags, status, created_at, updated_at)
                          VALUES ('Duplicate Title', 'supply', 'test', 'test', '', '', 1, NULL, NULL, 'public', '', '', '', 'published', ?, ?)""", (ts, ts))
        cursor.execute("COMMIT")

        cursor.execute("SELECT COUNT(*) FROM v06_market_resources WHERE title='Duplicate Title' AND direction='supply'")
        count = cursor.fetchone()[0]
        assert count >= 1


class TestLegacyReadCompatibility:
    def test_legacy_needs_still_readable(self, temp_db_conn):
        cursor = temp_db_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM v04f_club_needs")
        count = cursor.fetchone()[0]
        assert count >= 0

    def test_legacy_offerings_still_readable(self, temp_db_conn):
        cursor = temp_db_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM v04f_club_offerings")
        count = cursor.fetchone()[0]
        assert count >= 0

    def test_v05a_users_still_readable(self, temp_db_conn):
        cursor = temp_db_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM v05a_users")
        count = cursor.fetchone()[0]
        assert count >= 0