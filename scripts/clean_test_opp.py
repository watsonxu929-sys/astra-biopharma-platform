"""Remove only reviewed GROUP-01 test orphans; never infer tests from titles.

Default is a dry run. Formal execution requires a maintenance window, verified
backup, --allow-formal-db and --confirm-db matching the exact target path.
Existing Opportunity parents are deliberately refused, not deleted.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.test_db_utils import assert_not_live_db

TABLES = {"v06_collab_tasks", "v06_follow_ups", "v06_timeline_entries"}
PARENTS = {1, 12, 13, 14}
FORMAL = ROOT / "data" / "app.db"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def same_path(left, right):
    return left.resolve() == right.resolve() or (
        left.exists() and right.exists() and left.samefile(right)
    )


def snapshot(conn):
    schema = conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
    ).fetchall()
    data = {}
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        data[table] = sorted(repr(tuple(row)) for row in conn.execute("SELECT * FROM " + quote(table)))
    return schema, data


def clean(args):
    target = args.db.resolve(strict=True)
    formal = same_path(target, FORMAL)
    if formal:
        require(args.allow_formal_db and args.confirm_db is not None
                and same_path(args.confirm_db, target), "REFUSE: formal DB requires explicit path confirmation")
    else:
        assert_not_live_db(target)
    reference = args.reference_db.resolve(strict=True)
    require(not same_path(target, reference), "REFUSE: reference must be a separate reviewed snapshot")
    with args.audit_csv.open(encoding="utf-8-sig", newline="") as stream:
        audit = list(csv.DictReader(stream))
    selected = [r for r in audit if r["root_cause_group"] == "GROUP-01"]
    require(len(audit) == 25 and len(selected) == 24, "REFUSE: unexpected audit scope")
    keys = {(r["child_table"], int(r["child_row_id"])) for r in selected}
    require(len(keys) == 24, "REFUSE: duplicate whitelist")
    require(all(r["classification"] == "CONFIRMED_TEST_DEMO_ORPHAN"
                and r["recommended_action"] == "DELETE_TEST_CHAIN"
                and r["child_table"] in TABLES and r["parent_table"] == "v06_opportunities"
                and r["fk_column"] == "opportunity_id" and int(r["fk_value"]) in PARENTS
                for r in selected), "REFUSE: unapproved record")
    mode = "rw" if args.apply else "ro"
    with closing(sqlite3.connect(target.as_uri() + "?mode=" + mode, uri=True, isolation_level=None)) as conn, closing(
        sqlite3.connect(reference.as_uri() + "?mode=ro", uri=True)
    ) as ref:
        conn.execute("PRAGMA foreign_keys=ON")
        require(conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1, "REFUSE: foreign keys not ON")
        conn.execute("BEGIN IMMEDIATE" if args.apply else "BEGIN")
        try:
            before_schema, before_data = snapshot(conn)
            before_fk = set(conn.execute("PRAGMA foreign_key_check"))
            audit_fk = set()
            for row in audit:
                fks = [fk for fk in conn.execute("PRAGMA foreign_key_list(" + quote(row["child_table"]) + ")")
                       if fk[2] == row["parent_table"] and fk[3] == row["fk_column"]]
                require(len(fks) == 1, "REFUSE: FK definition changed")
                audit_fk.add((row["child_table"], int(row["child_row_id"]), row["parent_table"], fks[0][0]))
            require(len(before_fk) == 25 and before_fk == audit_fk, "REFUSE: FK baseline changed")
            require(conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "REFUSE: integrity failed")
            expected_data = dict(before_data)
            for table in before_data:
                for fk in conn.execute("PRAGMA foreign_key_list(" + quote(table) + ")"):
                    # Reviewed tables have no inbound FK. Any new topology needs re-audit;
                    # do not risk implicit CASCADE or SET NULL outside the whitelist.
                    require(fk[2] not in TABLES, "REFUSE: incoming dependency needs re-audit")
            for table in TABLES:
                expected_data[table] = list(before_data[table])
            chains = {}
            for parent in sorted(PARENTS):
                require(not conn.execute("SELECT 1 FROM v06_opportunities WHERE id=?", (parent,)).fetchone(),
                        "REFUSE: parent exists; this command handles audited orphans only")
                chain = [r for r in selected if int(r["fk_value"]) == parent]
                require(sorted(r["child_table"] for r in chain) ==
                        sorted(["v06_collab_tasks", "v06_follow_ups"] + ["v06_timeline_entries"] * 4),
                        "REFUSE: incomplete chain")
                for table in TABLES:
                    ids = {r[0] for r in conn.execute("SELECT id FROM " + quote(table) + " WHERE opportunity_id=?", (parent,))}
                    require(ids == {int(r["child_row_id"]) for r in chain if r["child_table"] == table},
                            "REFUSE: extra or missing chain records")
                for row in chain:
                    table, rid = row["child_table"], int(row["child_row_id"])
                    columns = conn.execute("PRAGMA table_info(" + quote(table) + ")").fetchall()
                    require(columns == ref.execute("PRAGMA table_info(" + quote(table) + ")").fetchall(),
                            "REFUSE: reference schema changed")
                    sql = "SELECT * FROM " + quote(table) + " WHERE id=?"
                    current = conn.execute(sql, (rid,)).fetchone()
                    require(current is not None and current == ref.execute(sql, (rid,)).fetchone(),
                            "REFUSE: reviewed row changed")
                    expected_data[table].remove(repr(tuple(current)))
                chains[str(parent)] = [{"table": r["child_table"], "id": int(r["child_row_id"])} for r in chain]
            remaining = {fk for fk in before_fk if (fk[0], fk[1]) not in keys}
            require(remaining == {("v05c_club_event_profiles", 1, "events", 0)},
                    "REFUSE: GROUP-02 changed")
            if args.apply:
                # FK topology was read above: no inbound edges to these three tables.
                for chain in chains.values():
                    for item in chain:
                        result = conn.execute("DELETE FROM " + quote(item["table"]) + " WHERE id=?", (item["id"],))
                        require(result.rowcount == 1, "REFUSE: unexpected delete count")
                schema, data = snapshot(conn)
                require(schema == before_schema and data == expected_data, "REFUSE: non-whitelisted change")
                require(set(conn.execute("PRAGMA foreign_key_check")) == remaining, "REFUSE: unexpected residual FK")
                require(conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "REFUSE: integrity failed")
                conn.commit()
            else:
                conn.rollback()
            return {"applied": args.apply, "foreign_keys": 1, "before_fk": 25,
                    "after_fk": 1 if args.apply else 25, "deleted": 24 if args.apply else 0, "chains": chains}
        except Exception:
            conn.rollback()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--reference-db", type=Path, required=True)
    parser.add_argument("--audit-csv", type=Path, default=ROOT / "docs/audit/ASTRA_R1_REMAINING_FK_DECISIONS.csv")
    parser.add_argument("--allow-formal-db", action="store_true")
    parser.add_argument("--confirm-db", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(clean(args), ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError, OSError, sqlite3.Error, KeyError) as exc:
        print("REFUSE: cleanup not completed (" + type(exc).__name__ + "). " +
              (str(exc) if isinstance(exc, ValueError) else "Check target, whitelist and reviewed snapshot."),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
