"""Offline CLOSEOUT-03 checks; explicit isolated seed required, no global conftest."""
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, contextmanager
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SEED = Path(os.environ['CLOSEOUT_TEST_DB']).resolve()
if not SEED.is_relative_to(ROOT / 'data' / 'acceptance') or not SEED.is_file():
    raise RuntimeError('Explicit isolated seed required')
os.environ.update(APP_DB_PATH=str(SEED), DATABASE_URL='sqlite:///' + SEED.as_posix(),
                  SCHEDULER_ENABLED='false', WORKER_ENABLED='false', APP_AUTH_DISABLED='false')

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.services import club_operations_service as club
from app.api.v1 import club_operations as api
from app import v05c_club_events as web
from scripts.repair_club_registration_fk_v1 import repair, TABLE, MEMBERS, ALLOWED_EXCEPTION, _data, _schema
from scripts.migrate_v05c import migrate


class EventWriteGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='closeout03_', dir=SEED.parent)
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'isolated.db'
        with closing(sqlite3.connect(SEED.as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(self.db)) as dst:
            src.backup(dst)
        for target in ('socket.getaddrinfo', 'socket.create_connection'):
            guard = patch(target, side_effect=AssertionError('Unexpected network'))
            guard.start(); self.addCleanup(guard.stop)
        repair(self.db, apply=True)
        self.traces = []
        real_connection = club.db_connection

        @contextmanager
        def connection(path=None):
            self.assertIn(path, (None, self.db))
            with real_connection(self.db) as conn:
                self.assertEqual(conn.execute('PRAGMA foreign_keys').fetchone()[0], 1)
                conn.set_trace_callback(self.traces.append)
                try:
                    yield conn
                finally:
                    self.assertEqual(conn.execute('PRAGMA foreign_keys').fetchone()[0], 1)

        for module in (club, web):
            guard = patch.object(module, 'db_connection', connection)
            guard.start(); self.addCleanup(guard.stop)
        self.svc = club.ClubEventService(self.db)
        factory = patch.object(api, 'ClubEventService', return_value=self.svc)
        factory.start(); self.addCleanup(factory.stop)
        factory = patch.object(web, 'ClubEventService', return_value=self.svc)
        factory.start(); self.addCleanup(factory.stop)
        self.uid, self.mid = self.member('member')
        self.other_uid, self.other_mid = self.member('other')
        self.identity = {'id': self.uid, 'username': 'closeout03', 'role': 'admin'}
        app = FastAPI()

        @app.middleware('http')
        async def identity(request: Request, call_next):
            request.state.current_user = self.identity
            return await call_next(request)

        app.include_router(api.router, prefix='/api/v1')
        app.include_router(web.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.addCleanup(self.assert_no_fk_disable)

    def assert_no_fk_disable(self):
        self.assertFalse(any('FOREIGN_KEYS=OFF' in s.upper().replace(' ', '') for s in self.traces))

    def member(self, suffix):
        with club.db_connection(self.db) as c:
            uid = c.execute("INSERT INTO v05a_users(username,display_name,password_hash,role,status,created_at,updated_at) VALUES (?,?,'not-a-login','viewer','active','2026-09-17','2026-09-17')", ('closeout03_' + suffix, suffix)).lastrowid
            mid = c.execute("INSERT INTO v04f_club_memberships(member_no,status,joined_at,created_at,updated_at,user_id) VALUES (?,'active','2026-09-17','2026-09-17','2026-09-17',?)", ('C03-' + suffix, uid)).lastrowid
            return uid, mid

    def snapshot(self):
        with closing(sqlite3.connect(self.db)) as c:
            return _data(c)

    def event(self, *, open=True):
        event = self.svc.create_event({'name': '隔离活动', 'visibility': 'public', 'member_only': True}, actor='admin', actor_user_id=self.uid)
        if open:
            self.svc.transition_event(event['id'], action='publish', actor='admin', actor_user_id=self.uid)
            self.svc.transition_event(event['id'], action='open', actor='admin', actor_user_id=self.uid)
        return event['id']

    def register(self, eid, **fields):
        return self.client.post(f'/api/v1/club/events/{eid}/registrations', json={'membership_id': self.mid, 'applicant_name': '隔离会员', **fields})

    def test_a_orphan_real_profile_write_routes(self):
        before = self.snapshot()
        for action in ('publish', 'open'):
            response = self.client.post('/api/v1/club/events/1/transition', json={'action': action})
            self.assertEqual(response.status_code, 404, response.text)
            response = self.client.post('/club/events/1/status', data={'action': action}, follow_redirects=False)
            self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(before, self.snapshot())

    def test_b_open_orphan_rejects_valid_member_and_side_effects(self):
        with club.db_connection(self.db) as c:
            c.execute("UPDATE v05c_club_event_profiles SET status='registration_open',lifecycle_status='registration_open',registration_status='open' WHERE id=1")
        before = self.snapshot()
        self.assertEqual(self.register(1).status_code, 404)
        for action in (lambda: self.svc.issue_checkin_token(1, 999),
                       lambda: self.svc.review_registration(1, 999, decision='approved', actor='admin'),
                       lambda: self.svc.check_in(1, registration_id=999, actor='admin'),
                       lambda: self.svc.undo_checkin(1, 999, actor='admin'),
                       lambda: self.svc.submit_feedback(1, 999, {}, actor_user_id=self.uid)):
            with self.assertRaises(club.ClubOperationError) as caught: action()
            self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(before, self.snapshot())

    def test_c_normal_service_http_registration_persists(self):
        eid = self.event()
        response = self.register(eid)
        self.assertEqual(response.status_code, 200, response.text)
        row = response.json()['data']
        self.assertGreater(row['id'], 2)
        self.assertEqual((row['membership_id'], row['canonical_membership_id']), (self.mid, self.mid))
        with club.db_connection(self.db) as c:
            persisted = dict(c.execute('SELECT * FROM ' + TABLE + ' WHERE id=?', (row['id'],)).fetchone())
            self.assertEqual(persisted, row)
            self.assertEqual([tuple(r) for r in c.execute('PRAGMA foreign_key_check')], ALLOWED_EXCEPTION)
            self.assertIsNotNone(web._event_detail(c, eid))
        # A new service/connection sees the same row; repeat submission is idempotent.
        before = self.snapshot()
        fresh = club.ClubEventService(self.db).register(eid, {'membership_id': self.mid, 'applicant_name': '隔离会员'}, actor_user_id=self.uid)
        self.assertEqual(fresh['id'], row['id'])
        self.assertEqual(before, self.snapshot())

    def test_d_membership_identity_and_permission_failures(self):
        eid = self.event()
        before = self.snapshot()
        self.assertEqual(self.register(eid, membership_id=999999).status_code, 400)
        self.assertEqual(self.register(eid, membership_id=self.other_mid).status_code, 403)
        self.assertEqual(self.register(eid, membership_id=None).status_code, 403)
        self.identity = None
        self.assertEqual(self.register(eid).status_code, 401)
        self.identity = {'id': self.uid, 'role': 'unknown'}
        self.assertEqual(self.register(eid).status_code, 403)
        self.identity = {'id': self.uid, 'role': 'viewer'}
        self.assertEqual(self.client.post(f'/api/v1/club/events/{eid}/transition', json={'action': 'close'}).status_code, 403)
        self.assertEqual(before, self.snapshot())
        with club.db_connection(self.db) as c:
            c.execute("UPDATE v04f_club_memberships SET expired_at='2000-01-01' WHERE id=?", (self.mid,))
        before = self.snapshot()
        self.assertEqual(self.register(eid).status_code, 400)
        self.assertEqual(before, self.snapshot())

    def test_d_status_and_deadline(self):
        eid = self.event(open=False)
        before = self.snapshot()
        self.assertEqual(self.register(eid).status_code, 409)
        self.assertEqual(before, self.snapshot())
        self.svc.transition_event(eid, action='publish', actor='admin')
        self.svc.transition_event(eid, action='open', actor='admin')
        with club.db_connection(self.db) as c:
            c.execute("UPDATE v05c_club_event_profiles SET registration_deadline='2000-01-01' WHERE id=?", (eid,))
        before = self.snapshot()
        self.assertEqual(self.register(eid).status_code, 409)
        self.assertEqual(before, self.snapshot())

    def test_e_publish_and_registration_failure_atomic(self):
        eid = self.event(open=False)
        original = club.emit_domain_event
        def fail_after_event(*args, **kwargs):
            original(*args, **kwargs)
            raise sqlite3.IntegrityError('injected after domain event')
        before = self.snapshot()
        with patch.object(club, 'emit_domain_event', side_effect=fail_after_event):
            with self.assertRaises(sqlite3.IntegrityError):
                self.svc.transition_event(eid, action='publish', actor='admin')
        self.assertEqual(before, self.snapshot())
        self.svc.transition_event(eid, action='publish', actor='admin')
        self.svc.transition_event(eid, action='open', actor='admin')
        before = self.snapshot()
        with patch.object(club, 'record_audit', side_effect=sqlite3.IntegrityError('injected audit failure')):
            with self.assertRaises(sqlite3.IntegrityError):
                self.svc.register(eid, {'membership_id': self.mid, 'applicant_name': 'isolated'}, actor_user_id=self.uid)
        self.assertEqual(before, self.snapshot())

    def test_f_migration_idempotent_and_initialization(self):
        before = self.snapshot()
        with closing(sqlite3.connect(self.db)) as c: schema = _schema(c)
        self.assertFalse(repair(self.db, apply=True)['applied'])
        self.assertEqual(before, self.snapshot())
        with closing(sqlite3.connect(self.db)) as c: self.assertEqual(schema, _schema(c))
        fresh = Path(self.tmp.name) / 'fresh.db'
        migrate(fresh, backup=False)
        with closing(sqlite3.connect(fresh)) as c:
            self.assertIn(MEMBERS, [r[2] for r in c.execute('PRAGMA foreign_key_list(' + TABLE + ')')])
            self.assertNotIn(MEMBERS + '_old', [r[2] for r in c.execute('PRAGMA foreign_key_list(' + TABLE + ')')])

    def test_f_old_schema_maintenance_then_repair(self):
        old = Path(self.tmp.name) / 'old.db'
        with closing(sqlite3.connect(SEED)) as src, closing(sqlite3.connect(old)) as dst: src.backup(dst)
        with closing(sqlite3.connect(old)) as c:
            with self.assertRaises(club.ClubOperationError) as caught: club._require_registration_schema(c)
            self.assertEqual(caught.exception.status_code, 503)
            data, schema = _data(c), _schema(c)
        self.assertTrue(repair(old, apply=True)['applied'])
        with closing(sqlite3.connect(old)) as c:
            self.assertEqual(data, _data(c))
            club._require_registration_schema(c)
            # CHECK, NOT NULL, UNIQUE, explicit indexes and all inbound FKs are checked by migration.
            self.assertEqual(c.execute('SELECT seq FROM sqlite_sequence WHERE name=?', (TABLE,)).fetchone()[0], 2)
        self.assertFalse(repair(old, apply=True)['applied'])

    def test_f_unknown_schema_refused(self):
        with club.db_connection(self.db) as c: c.execute('ALTER TABLE ' + TABLE + ' ADD COLUMN unexpected TEXT')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Unknown registration definition'): repair(self.db, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_d_participation_debt_is_explicit_and_atomic(self):
        eid = self.event()
        rid = self.register(eid).json()['data']['id']
        before = self.snapshot()
        response = self.client.post(f'/api/v1/club/events/{eid}/registrations/{rid}/review', json={'decision': 'approved'})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn('待维护', response.text)
        self.assertEqual(before, self.snapshot())
        # The existing capacity rule still produces a waitlist, not a new participation row.
        with club.db_connection(self.db) as c:
            c.execute('UPDATE v05c_club_event_profiles SET capacity=1 WHERE id=?', (eid,))
            c.execute("UPDATE " + TABLE + " SET lifecycle_status='approved',status='approved' WHERE id=?", (rid,))
        self.identity = {'id': self.other_uid, 'role': 'admin'}
        second = self.register(eid, membership_id=self.other_mid).json()['data']['id']
        response = self.client.post(f'/api/v1/club/events/{eid}/registrations/{second}/review', json={'decision': 'approved'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['registration']['lifecycle_status'], 'waitlisted')

    def test_f_nonempty_old_schema_refused_and_migration_rollback(self):
        from scripts import repair_club_registration_fk_v1 as migration
        old = Path(self.tmp.name) / 'nonempty.db'
        with closing(sqlite3.connect(SEED)) as src, closing(sqlite3.connect(old)) as dst: src.backup(dst)
        with closing(sqlite3.connect(old)) as c:
            before_schema = _schema(c)
            before_data = _data(c)
        real_data = migration._data
        calls = []
        def mismatching_data(conn):
            value = real_data(conn)
            calls.append(1)
            return value if len(calls) == 1 else {**value, 'injected': (1, 'failure')}
        with patch.object(migration, '_data', side_effect=mismatching_data):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected schema/data delta'): repair(old, apply=True)
        with closing(sqlite3.connect(old)) as c:
            self.assertEqual(before_schema, _schema(c))
            self.assertEqual(before_data, _data(c))
            # Deliberately construct an old nonempty fixture, never a production request.
            c.execute("INSERT INTO " + TABLE + " (registration_no,club_event_id,applicant_name,registered_at,created_at,updated_at) VALUES ('isolated-old',1,'isolated','2026-09-17','2026-09-17','2026-09-17')")
            c.commit()
            before_data = _data(c)
        with self.assertRaisesRegex(ValueError, 'nonempty'): repair(old, apply=True)
        with closing(sqlite3.connect(old)) as c:
            self.assertEqual(before_schema, _schema(c))
            self.assertEqual(before_data, _data(c))


if __name__ == '__main__':
    unittest.main()
