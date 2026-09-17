"""Explicit, offline single-table repair. Stop writers and take a SQLite backup first.

python scripts/repair_club_registration_fk_v1.py --db ABSOLUTE_PATH [--apply]
Only the inspected empty registration schema is eligible; no request-time migration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3

TABLE = "v05c_club_event_registrations"
TEMP = TABLE + "_fk_repair"
MEMBERS = "v04f_club_memberships"
OLD = MEMBERS + "_old"
KNOWN_DEFINITION = "47b4b1f3d9b463abfaf76fdacb522a87ee6981bb5301527d15ce44f912093e20"
PARTICIPATION = "v05c_club_event_participation"
KNOWN_DEFINITIONS = {TABLE: KNOWN_DEFINITION, PARTICIPATION: "d8f62e3bb815ead471003870c88c29f0fb8dc8a8860e7ca438a862e26a4ce602"}
ALLOWED_EXCEPTION = [("v05c_club_event_profiles", 1, "events", 0)]


def _schema(conn):
    return conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()


def _canonical_sql(sql):
    return (sql or "").replace('"' + TABLE + '"', TABLE).replace('"' + MEMBERS + '"', MEMBERS).replace('"' + PARTICIPATION + '"', PARTICIPATION)


def _data(conn):
    result = {}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        rows = conn.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY rowid').fetchall()
        result[name] = (len(rows), hashlib.sha256(repr(rows).encode()).hexdigest())
    return result


def inspect(conn, *, table=TABLE):
    if table not in KNOWN_DEFINITIONS:
        raise ValueError("Table outside the approved activity-chain allowlist")
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not row:
        raise ValueError("Registration table missing; use the existing initialization first")
    sql = row[0]
    fixed = sql.replace('"' + OLD + '"', MEMBERS).replace(OLD, MEMBERS)
    body = _canonical_sql(fixed[fixed.index('('):])
    if hashlib.sha256(body.encode()).hexdigest() != KNOWN_DEFINITIONS[table]:
        raise ValueError("Unknown registration definition; manual mapping required")
    fks = conn.execute('PRAGMA foreign_key_list(' + table + ')').fetchall()
    member_fk = [r for r in fks if r[3] == 'membership_id']
    if len(member_fk) != 1 or member_fk[0][2] not in {OLD, MEMBERS} or member_fk[0][4:] != ('id', 'NO ACTION', 'NO ACTION', 'NONE'):
        raise ValueError("Unknown membership FK")
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (MEMBERS,)).fetchone():
        raise ValueError("Canonical membership table missing")
    state = 'already_correct' if member_fk[0][2] == MEMBERS else 'eligible'
    if state == 'eligible' and conn.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]:
        raise ValueError("Registration table is nonempty; automatic repair refused")
    issues = conn.execute('PRAGMA foreign_key_check').fetchall()
    if issues not in ([], ALLOWED_EXCEPTION):
        raise ValueError("Foreign key exception set changed: " + repr(issues))
    if conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise ValueError("Integrity check failed")
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table + "_fk_repair",)).fetchone():
        raise ValueError("Unknown concurrent/incomplete migration table")
    return state, fixed, issues


def repair(db_path: str | Path, *, apply: bool = False, table=TABLE):
    if table not in KNOWN_DEFINITIONS:
        raise ValueError("Table outside the approved activity-chain allowlist")
    temporary_name = table + "_fk_repair"
    path = Path(db_path).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise ValueError("Explicit existing absolute database path required")
    conn = sqlite3.connect(path.resolve().as_uri() + '?mode=rw', uri=True, timeout=5)
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        if conn.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
            raise RuntimeError('FK enforcement unavailable')
        state, _, issues = inspect(conn, table=table)
        if not apply or state == 'already_correct':
            return {'status': state, 'applied': False, 'fk': issues}
        # Dedicated maintenance connection only. Recheck everything after acquiring write lock.
        conn.execute('PRAGMA foreign_keys=OFF')
        if conn.execute('PRAGMA foreign_keys').fetchone()[0] != 0:
            raise RuntimeError('Maintenance FK switch failed')
        conn.execute('BEGIN IMMEDIATE')
        state, fixed, issues = inspect(conn, table=table)
        if state != 'eligible':
            raise ValueError('Concurrent migration detected')
        before_schema, before_data = _schema(conn), _data(conn)
        sequence = conn.execute('SELECT rowid,seq FROM sqlite_sequence WHERE name=?', (table,)).fetchone()
        dependencies = conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type,name", (table,)).fetchall()
        columns = [r[1] for r in conn.execute('PRAGMA table_info(' + table + ')')]
        column_sql = ','.join('"' + c.replace('"', '""') + '"' for c in columns)
        temporary = re.sub(r'^CREATE TABLE\s+"?' + table + r'"?', 'CREATE TABLE ' + temporary_name, fixed, count=1)
        if temporary == fixed:
            raise ValueError('Unexpected CREATE TABLE syntax')
        conn.execute(temporary)
        conn.execute(f'INSERT INTO {temporary_name} ({column_sql}) SELECT {column_sql} FROM {table}')
        if conn.execute('SELECT COUNT(*) FROM ' + temporary_name).fetchone()[0] != 0:
            raise ValueError('Unexpected registration data')
        conn.execute('DROP TABLE ' + table)
        conn.execute(f'ALTER TABLE {temporary_name} RENAME TO {table}')
        for (statement,) in dependencies:
            conn.execute(statement)
        conn.execute('DELETE FROM sqlite_sequence WHERE name=?', (table,))
        if sequence is not None:
            conn.execute('INSERT INTO sqlite_sequence(rowid,name,seq) VALUES (?,?,?)', (sequence[0], table, sequence[1]))
        expected = [(kind, name, owner, _canonical_sql(fixed if kind == 'table' and name == table else sql))
                    for kind, name, owner, sql in before_schema]
        actual = [(kind, name, table, _canonical_sql(sql)) for kind, name, table, sql in _schema(conn)]
        if expected != actual or before_data != _data(conn):
            raise RuntimeError('Unexpected schema/data delta; rolling back')
        if conn.execute('PRAGMA foreign_key_check').fetchall() != issues:
            raise RuntimeError('FK exception set changed; rolling back')
        if inspect(conn, table=table)[0] != 'already_correct':
            raise RuntimeError('Post-migration constraint verification failed')
        conn.commit()
        return {'status': 'repaired', 'applied': True, 'fk': issues, 'preserved_sequence': sequence}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute('PRAGMA foreign_keys=ON')
        enabled = conn.execute('PRAGMA foreign_keys').fetchone()[0]
        conn.close()
        if enabled != 1:
            raise RuntimeError('Maintenance connection FK restoration failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(repair(args.db, apply=args.apply), ensure_ascii=False))


if __name__ == '__main__':
    main()
