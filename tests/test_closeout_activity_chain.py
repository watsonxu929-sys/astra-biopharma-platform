"""CLOSEOUT-03 continuation: one real role-separated chain, offline isolated DB."""
import importlib.util
from pathlib import Path
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

import test_closeout_event_write_guard as base
from fastapi.staticfiles import StaticFiles
from app.services import club_operations_service as club
from scripts import repair_club_registration_fk_v1 as migration


class ActivityChain(unittest.TestCase):
    member = base.EventWriteGuard.member
    snapshot = base.EventWriteGuard.snapshot
    assert_no_fk_disable = base.EventWriteGuard.assert_no_fk_disable

    def setUp(self):
        base.EventWriteGuard.setUp(self)
        self.client.app.mount('/static', StaticFiles(directory=base.ROOT / 'app/static'), name='static')
        migration.repair(self.db, apply=True, table=migration.PARTICIPATION)
        self.admin_uid, _ = self.member('admin')
        with club.db_connection(self.db) as c:
            c.execute("UPDATE v05a_users SET role='admin' WHERE id=?", (self.admin_uid,))
        self.as_admin()

    def as_admin(self):
        self.identity = {'id': self.admin_uid, 'username': 'closeout_admin', 'role': 'admin'}

    def as_member(self, other=False):
        self.identity = {'id': self.other_uid if other else self.uid, 'username': 'closeout_member', 'role': 'viewer'}

    def create(self):
        self.as_admin()
        response = self.client.post('/club/events/create', data={'name': '隔离完整活动链', 'visibility': 'public', 'member_only': '1'}, follow_redirects=False)
        self.assertEqual(response.status_code, 303, response.text)
        eid = int(response.headers['location'].split('/')[3].split('?')[0])
        self.assertEqual(self.client.post(f'/club/events/{eid}/status', data={'action': 'publish'}, follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.post(f'/api/v1/club/events/{eid}/transition', json={'action': 'open'}).status_code, 200)
        return eid

    def register(self, eid, **extra):
        return self.client.post(f'/api/v1/club/events/{eid}/registrations', json={'membership_id': self.mid, 'applicant_name': '普通会员完整链', **extra})

    def registered(self):
        eid = self.create()
        self.as_member()
        response = self.register(eid)
        self.assertEqual(response.status_code, 200, response.text)
        return eid, response.json()['data']['id']

    def approve(self, eid, rid):
        return self.client.post(f'/api/v1/club/events/{eid}/registrations/{rid}/review', json={'decision': 'approved'})

    def checked(self, eid, rid, **extra):
        return self.client.post(f'/api/v1/club/events/{eid}/checkin', json={'registration_id': rid, **extra})

    def test_continuous_normal_member_chain_and_retries(self):
        eid, rid = self.registered()
        self.as_admin()
        approved = self.approve(eid, rid)
        self.assertEqual(approved.status_code, 200, approved.text)
        with club.db_connection(self.db) as c:
            participation = dict(c.execute('SELECT * FROM v05c_club_event_participation WHERE registration_id=?', (rid,)).fetchone())
            self.assertEqual((participation['club_event_id'], participation['membership_id'], participation['canonical_membership_id']), (eid, self.mid, self.mid))
            self.assertEqual(participation['attendance_status'], 'registered')
        before = self.snapshot()
        self.assertTrue(self.approve(eid, rid).json()['data']['idempotent'])
        self.assertEqual(before, self.snapshot())
        token = self.client.post(f'/api/v1/club/events/{eid}/checkin-token', json={'registration_id': rid}).json()['data']['token']
        response = self.checked(eid, rid, token=token)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['registration']['lifecycle_status'], 'checked_in')
        self.assertTrue(self.checked(eid, rid, token=token).json()['data']['idempotent'])
        self.assertTrue(self.checked(eid, rid).json()['data']['idempotent'])
        self.assertTrue(self.approve(eid, rid).json()['data']['idempotent'])
        with club.db_connection(self.db) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM v05c_club_event_participation WHERE registration_id=?', (rid,)).fetchone()[0], 1)
            self.assertEqual(c.execute('SELECT attendance_status FROM v05c_club_event_participation WHERE registration_id=?', (rid,)).fetchone()[0], 'checked_in')
            for kind in ('registration.approved', 'registration.checked_in'):
                self.assertEqual(c.execute('SELECT COUNT(*) FROM p4_domain_events WHERE event_type=? AND aggregate_id=?', (kind, str(rid))).fetchone()[0], 1)
            self.assertEqual([tuple(r) for r in c.execute('PRAGMA foreign_key_check')], migration.ALLOWED_EXCEPTION)
        admin_page = self.client.get(f'/club/events/{eid}/registrations')
        self.assertEqual(admin_page.status_code, 200, admin_page.text)
        self.assertIn('已签到', admin_page.text)
        self.as_member()
        for _ in range(2):
            page = self.client.get('/club/events?tab=my')
            self.assertEqual(page.status_code, 200, page.text)
            self.assertIn('普通会员完整链', self.register(eid).text)  # real retry, same record
            self.assertIn('隔离完整活动链', page.text)
            self.assertIn('已签到', page.text)
        self.as_member(other=True)
        self.assertNotIn('隔离完整活动链', self.client.get('/club/events?tab=my').text)

    def test_orphan_open_profile_blocks_all_chain_writes(self):
        eid, rid = self.registered()
        self.as_admin()
        self.assertEqual(self.approve(eid, rid).status_code, 200)
        with club.db_connection(self.db) as c:
            c.execute("UPDATE v05c_club_event_profiles SET status='registration_open',lifecycle_status='registration_open',registration_status='open' WHERE id=1")
            c.execute('UPDATE v05c_club_event_registrations SET club_event_id=1 WHERE id=?', (rid,))
            c.execute('UPDATE v05c_club_event_participation SET club_event_id=1 WHERE registration_id=?', (rid,))
        before = self.snapshot()
        for action in ('publish', 'open'):
            self.assertEqual(self.client.post('/api/v1/club/events/1/transition', json={'action': action}).status_code, 404)
        self.assertEqual(self.approve(1, rid).status_code, 404)
        self.assertEqual(self.checked(1, rid).status_code, 404)
        self.assertEqual(self.client.post('/club/events/1/registrations/bulk-checkin', data={'registration_ids': [rid]}, follow_redirects=False).status_code, 404)
        self.assertEqual(self.client.post('/api/v1/club/events/1/checkin-token', json={'registration_id': rid}).status_code, 404)
        self.as_member()
        self.assertEqual(self.register(1).status_code, 404)
        self.assertEqual(before, self.snapshot())

    def test_permissions_membership_and_mismatched_token(self):
        eid, rid = self.registered()
        before = self.snapshot()
        self.assertEqual(self.approve(eid, rid).status_code, 403)
        self.assertEqual(self.checked(eid, rid).status_code, 403)
        self.assertEqual(self.register(eid, membership_id=self.other_mid).status_code, 403)
        self.assertEqual(self.register(eid, membership_id=999999).status_code, 400)
        self.identity = None
        self.assertEqual(self.register(eid).status_code, 401)
        self.assertEqual(before, self.snapshot())
        self.as_admin()
        self.assertEqual(self.approve(eid, rid).status_code, 200)
        token = self.client.post(f'/api/v1/club/events/{eid}/checkin-token', json={'registration_id': rid}).json()['data']['token']
        other_eid = self.create()
        before = self.snapshot()
        self.assertEqual(self.checked(eid, rid, token='not-valid').status_code, 404)
        self.assertEqual(self.checked(other_eid, rid, token=token).status_code, 409)
        self.assertEqual(self.checked(eid, rid + 100, token=token).status_code, 409)
        self.assertEqual(self.approve(other_eid, rid).status_code, 404)
        self.assertEqual(before, self.snapshot())
        with club.db_connection(self.db) as c: c.execute("UPDATE v04f_club_memberships SET status='suspended' WHERE id=?", (self.mid,))
        before = self.snapshot()
        self.assertEqual(self.checked(eid, rid, token=token).status_code, 400)
        self.assertEqual(before, self.snapshot())

    def test_participation_failure_and_checkin_event_failure_rollback(self):
        eid, rid = self.registered(); self.as_admin()
        with club.db_connection(self.db) as c:
            c.execute("CREATE TRIGGER isolated_fail_participation BEFORE INSERT ON v05c_club_event_participation BEGIN SELECT RAISE(ABORT,'injected participation failure'); END")
        before = self.snapshot()
        with self.assertRaises(sqlite3.IntegrityError): self.approve(eid, rid)
        self.assertEqual(before, self.snapshot())
        with club.db_connection(self.db) as c: c.execute('DROP TRIGGER isolated_fail_participation')
        self.assertEqual(self.approve(eid, rid).status_code, 200)
        with club.db_connection(self.db) as c:
            c.execute("CREATE TRIGGER isolated_fail_event BEFORE INSERT ON p4_domain_events WHEN NEW.event_type='registration.checked_in' BEGIN SELECT RAISE(ABORT,'injected event failure'); END")
        before = self.snapshot()
        with self.assertRaises(sqlite3.IntegrityError): self.checked(eid, rid)
        self.assertEqual(before, self.snapshot())

    def test_cancelled_event_or_registration_cannot_advance(self):
        eid, rid = self.registered(); self.as_admin()
        self.assertEqual(self.client.post(f'/api/v1/club/events/{eid}/transition', json={'action': 'cancel'}).status_code, 200)
        before = self.snapshot()
        self.assertEqual(self.approve(eid, rid).status_code, 409)
        self.assertEqual(self.checked(eid, rid).status_code, 409)
        self.assertEqual(before, self.snapshot())

    def test_migration_preservation_idempotence_rollback_and_nonempty(self):
        old = Path(self.tmp.name) / 'old-participation.db'
        with closing(sqlite3.connect(base.SEED)) as src, closing(sqlite3.connect(old)) as dst: src.backup(dst)
        with closing(sqlite3.connect(old)) as c:
            before_schema, before_data = migration._schema(c), migration._data(c)
        calls = []
        original = migration._data
        def failure(conn):
            value = original(conn); calls.append(1)
            return value if len(calls) == 1 else {**value, 'injected': (1, 'failure')}
        with patch.object(migration, '_data', side_effect=failure):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected schema/data delta'):
                migration.repair(old, apply=True, table=migration.PARTICIPATION)
        with closing(sqlite3.connect(old)) as c:
            self.assertEqual(before_schema, migration._schema(c)); self.assertEqual(before_data, migration._data(c))
        self.assertTrue(migration.repair(old, apply=True, table=migration.PARTICIPATION)['applied'])
        self.assertFalse(migration.repair(old, apply=True, table=migration.PARTICIPATION)['applied'])
        with closing(sqlite3.connect(old)) as c:
            self.assertEqual(before_data, migration._data(c))
            self.assertEqual(c.execute("SELECT seq FROM sqlite_sequence WHERE name='v05c_club_event_participation'").fetchone()[0], 3)
        nonempty = Path(self.tmp.name) / 'nonempty.db'
        with closing(sqlite3.connect(base.SEED)) as src, closing(sqlite3.connect(nonempty)) as dst: src.backup(dst)
        with closing(sqlite3.connect(nonempty)) as c:
            c.execute("INSERT INTO v05c_club_event_participation(club_event_id,created_at,updated_at) VALUES (1,'isolated','isolated')"); c.commit()
            before_data = migration._data(c)
        with self.assertRaisesRegex(ValueError, 'nonempty'): migration.repair(nonempty, apply=True, table=migration.PARTICIPATION)
        with closing(sqlite3.connect(nonempty)) as c: self.assertEqual(before_data, migration._data(c))

    def test_supported_fresh_initialization_and_upgrade(self):
        fresh = Path(self.tmp.name) / 'fresh.db'
        base.migrate(fresh, backup=False)
        spec = importlib.util.spec_from_file_location('club_init', base.ROOT / 'scripts/migrations/007_club_operations_mvp.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with closing(sqlite3.connect(fresh)) as c:
            for table in module.ADDITIVE_COLUMNS:
                if not c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
                    c.execute('CREATE TABLE "' + table + '" (id INTEGER PRIMARY KEY)')
            module.apply_schema(c)
            for table in (migration.TABLE, migration.PARTICIPATION, 'p4_checkin_tokens', 'p4_checkin_audit', 'p4_domain_events', 'p4_operation_audit'):
                self.assertNotIn(migration.OLD, [r[2] for r in c.execute('PRAGMA foreign_key_list(' + table + ')')])
            for table in (migration.TABLE, migration.PARTICIPATION):
                self.assertIn(migration.MEMBERS, [r[2] for r in c.execute('PRAGMA foreign_key_list(' + table + ')')])


if __name__ == '__main__':
    unittest.main(defaultTest='ActivityChain')
