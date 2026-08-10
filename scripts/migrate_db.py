from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import resolved_db_path


@dataclass(frozen=True)
class Migration:
    number: str
    name: str
    module_name: str

    @property
    def migration_id(self) -> str:
        return f"{self.number}_{self.name}"

    @property
    def path(self) -> Path:
        return ROOT / "scripts" / "migrations" / f"{self.migration_id}.py"

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def module(self):
        return importlib.import_module(self.module_name)


MIGRATIONS: tuple[Migration, ...] = (
    Migration("000", "legacy_runtime_baseline", "scripts.migrations.000_legacy_runtime_baseline"),
    Migration("001", "core_domain_unification", "scripts.migrations.001_core_domain_unification"),
    Migration("002", "repair_domain_integrity", "scripts.migrations.002_repair_domain_integrity"),
    Migration("003", "intelligence_evidence_pipeline", "scripts.migrations.003_intelligence_evidence_pipeline"),
    Migration("004", "real_source_quality_evaluation", "scripts.migrations.004_real_source_quality_evaluation"),
    Migration("005", "research_fusion_engine", "scripts.migrations.005_research_fusion_engine"),
    Migration("006", "entity_relationship_network", "scripts.migrations.006_entity_relationship_network"),
    Migration("007", "club_operations_mvp", "scripts.migrations.007_club_operations_mvp"),
    Migration("008", "business_collaboration_mvp", "scripts.migrations.008_business_collaboration_mvp"),
    Migration("009", "intelligence_production_loop", "scripts.migrations.009_intelligence_production_loop"),
    Migration("010", "intelligence_opportunity_loop", "scripts.migrations.010_intelligence_opportunity_loop"),
    Migration("011", "feedback_outcome_loop", "scripts.migrations.011_feedback_outcome_loop"),
)


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _resolve_database(value: str) -> Path:
    raw = value.strip()
    if raw.startswith("sqlite:///"):
        raw = raw[len("sqlite:///"):]
        if re.match(r"^/[A-Za-z]:/", raw):
            raw = raw[1:]
    elif "://" in raw:
        raise ValueError("only_sqlite_databases_are_supported")
    path = Path(raw)
    return (path if path.is_absolute() else ROOT / path).resolve()


def _target_index(target: str) -> int:
    normalized = target.strip()
    for index, migration in enumerate(MIGRATIONS):
        if normalized in {migration.number, migration.migration_id}:
            return index
    raise ValueError(f"unknown_target:{target}")


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    if table not in _table_names(conn):
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _index_names(conn: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}


def _source(migration: Migration) -> str:
    return migration.path.read_text(encoding="utf-8")


def _created_tables(migration: Migration, module) -> set[str]:
    if migration.number == "000":
        return set(module.BASE_TABLES)
    if migration.number == "001":
        return {"platform_entity_mappings", "platform_migration_conflicts"}
    created = set(re.findall(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+[\"`]?([A-Za-z0-9_]+)",
        _source(migration), re.IGNORECASE,
    ))
    return created - set(getattr(module, "REQUIRED_TABLES", set()))


def _required_indexes(migration: Migration) -> set[str]:
    if migration.number == "000":
        return set()
    return set(re.findall(
        r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+[\"`]?([A-Za-z0-9_]+)",
        _source(migration), re.IGNORECASE,
    ))


def _additive_columns(migration: Migration, module) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for attribute in ("REQUIRED_COLUMNS", "COLUMN_PLAN", "COLUMNS", "ADDITIVE_COLUMNS"):
        for table, definitions in getattr(module, attribute, {}).items():
            target = result.setdefault(str(table), {})
            if isinstance(definitions, dict):
                target.update({str(name): str(ddl) for name, ddl in definitions.items()})
            else:
                target.update({str(name): "" for name in definitions})
    if migration.number == "006":
        result.setdefault("p3_relationship_candidates", {})["visibility"] = (
            "TEXT NOT NULL DEFAULT 'internal' CHECK(visibility IN ('public','internal','restricted','private'))"
        )
    return result


def _ddl_strings(migration: Migration) -> list[str]:
    tree = ast.parse(_source(migration), filename=str(migration.path))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if re.search(r"\bCREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX|TRIGGER)\b", node.value, re.IGNORECASE):
                values.append(node.value)
    return values


def _execute_atomic_sql(conn: sqlite3.Connection, sql: str) -> None:
    buffer = ""
    for character in sql:
        buffer += character
        if character == ";" and sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            buffer = ""
            if statement:
                conn.execute(statement)
    if buffer.strip():
        conn.execute(buffer.strip())


def _apply_columns(conn: sqlite3.Connection, columns: dict[str, dict[str, str]]) -> None:
    tables = _table_names(conn)
    for table, definitions in columns.items():
        if table not in tables:
            continue
        existing = _column_names(conn, table)
        for name, ddl in definitions.items():
            if name not in existing:
                if not ddl:
                    raise RuntimeError(f"missing_column_definition:{table}.{name}")
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}')
                existing.add(name)


def _structure_state(conn: sqlite3.Connection, migration: Migration) -> dict[str, object]:
    module = migration.module()
    tables = _table_names(conn)
    indexes = _index_names(conn)
    expected_tables = _created_tables(migration, module)
    expected_indexes = _required_indexes(migration)
    expected_columns = _additive_columns(migration, module)
    present = 0
    total = len(expected_tables) + len(expected_indexes) + sum(len(item) for item in expected_columns.values())
    missing_tables = sorted(expected_tables - tables)
    present += len(expected_tables & tables)
    missing_indexes = sorted(expected_indexes - indexes)
    present += len(expected_indexes & indexes)
    missing_columns: dict[str, list[str]] = {}
    for table, definitions in expected_columns.items():
        actual = _column_names(conn, table)
        missing = sorted(set(definitions) - actual)
        if missing:
            missing_columns[table] = missing
        present += len(set(definitions) & actual)
    missing_seed: list[str] = []
    if migration.number == "006" and "p3_relationship_type_registry" in tables:
        expected_seed = {str(row[0]) for row in module.RELATIONSHIP_TYPES}
        actual_seed = {str(row[0]) for row in conn.execute("SELECT relationship_type FROM p3_relationship_type_registry")}
        missing_seed = sorted(expected_seed - actual_seed)
        total += 1
        if not missing_seed:
            present += 1
    elif migration.number == "006":
        total += 1
    if total == 0:
        state = "complete"
    elif present == total:
        state = "complete"
    elif present == 0:
        state = "absent"
    else:
        state = "partial"
    return {
        "state": state,
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "missing_indexes": missing_indexes,
        "missing_seed": missing_seed,
    }


def _required_tables(migration: Migration, module) -> set[str]:
    required = set(getattr(module, "REQUIRED_TABLES", set()))
    if migration.number == "004":
        required.update(getattr(module, "COLUMNS", {}).keys())
    return required


def _apply_migration(conn: sqlite3.Connection, migration: Migration) -> None:
    module = migration.module()
    missing_required = _required_tables(migration, module) - _table_names(conn)
    if missing_required:
        raise RuntimeError("missing_required_tables:" + ",".join(sorted(missing_required)))
    if migration.number == "002":
        module.analyze_orphan_fks(conn)
        module.analyze_resource_conflicts(conn)
        module.check_legacy_mappings(conn)
        return
    columns = _additive_columns(migration, module)
    _apply_columns(conn, columns)
    for sql in _ddl_strings(migration):
        _execute_atomic_sql(conn, sql)
    _apply_columns(conn, columns)
    if migration.number == "001":
        mappings, conflicts = module.collect_mappings(conn)
        conn.executemany(
            "INSERT OR IGNORE INTO platform_entity_mappings(domain,source_system,source_entity_type,source_entity_id,canonical_entity_type,canonical_entity_id,metadata_json) VALUES (?,?,?,?,?,?,?)",
            mappings,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO platform_migration_conflicts(migration_id,domain,source_entity_type,source_entity_id,reason,details_json) VALUES (?,?,?,?,?,?)",
            conflicts,
        )
    if migration.number == "006":
        timestamp = _now()
        for key, display, reverse, category, subjects, objects, symmetric, risk in module.RELATIONSHIP_TYPES:
            conn.execute(
                """INSERT INTO p3_relationship_type_registry(
                relationship_type,display_name,reverse_display_name,category,subject_types_json,
                object_types_json,is_symmetric,risk_level,active,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,1,?,?)
                ON CONFLICT(relationship_type) DO UPDATE SET
                display_name=excluded.display_name,reverse_display_name=excluded.reverse_display_name,
                category=excluded.category,subject_types_json=excluded.subject_types_json,
                object_types_json=excluded.object_types_json,is_symmetric=excluded.is_symmetric,
                risk_level=excluded.risk_level,active=1,updated_at=excluded.updated_at""",
                (key, display, reverse, category, json.dumps(subjects), json.dumps(objects), symmetric, risk, timestamp, timestamp),
            )


HISTORY_TABLE_SQL = """
CREATE TABLE platform_migration_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 migration_id TEXT NOT NULL,
 mode TEXT NOT NULL,
 stats_json TEXT NOT NULL,
 backup_path TEXT,
 backup_sha256 TEXT,
 created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
 migration_name TEXT,
 checksum TEXT,
 status TEXT NOT NULL DEFAULT 'success',
 started_at TEXT,
 finished_at TEXT,
 error_message TEXT,
 execution_ms REAL
)
"""

HISTORY_COLUMNS = {
    "migration_name": "TEXT",
    "checksum": "TEXT",
    "status": "TEXT NOT NULL DEFAULT 'success'",
    "started_at": "TEXT",
    "finished_at": "TEXT",
    "error_message": "TEXT",
    "execution_ms": "REAL",
}


def _ensure_history_schema(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        if "platform_migration_runs" not in _table_names(conn):
            conn.execute(HISTORY_TABLE_SQL)
        else:
            existing = _column_names(conn, "platform_migration_runs")
            for name, ddl in HISTORY_COLUMNS.items():
                if name not in existing:
                    conn.execute(f'ALTER TABLE platform_migration_runs ADD COLUMN "{name}" {ddl}')
        duplicates = conn.execute(
            "SELECT migration_id,COUNT(*) FROM platform_migration_runs WHERE status='success' GROUP BY migration_id HAVING COUNT(*)>1"
        ).fetchall()
        if duplicates:
            raise RuntimeError("duplicate_success_history")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_platform_migration_success "
            "ON platform_migration_runs(migration_id) WHERE status='success'"
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _success_history(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    if "platform_migration_runs" not in _table_names(conn):
        return {}
    columns = _column_names(conn, "platform_migration_runs")
    rows = conn.execute("SELECT * FROM platform_migration_runs ORDER BY id").fetchall()
    result: dict[str, sqlite3.Row] = {}
    for row in rows:
        status = row["status"] if "status" in columns else ("success" if row["mode"] in {"apply", "upgrade", "adopt"} else "unknown")
        if status == "success":
            migration_id = str(row["migration_id"])
            if migration_id in result:
                raise RuntimeError(f"duplicate_success_history:{migration_id}")
            result[migration_id] = row
    return result


def _history_value(row: sqlite3.Row, name: str) -> object | None:
    return row[name] if name in row.keys() else None


def build_plan(conn: sqlite3.Connection, target: str = "011", start: str = "000") -> dict[str, object]:
    target_index = _target_index(target)
    start_index = _target_index(start)
    if start_index > target_index:
        raise ValueError(f"start_after_target:{start}>{target}")
    conn.row_factory = sqlite3.Row
    history = _success_history(conn)
    steps: list[dict[str, object]] = []
    for migration in MIGRATIONS[start_index:target_index + 1]:
        structure = _structure_state(conn, migration)
        recorded = history.get(migration.migration_id)
        stored_checksum = str(_history_value(recorded, "checksum") or "") if recorded else ""
        if recorded and stored_checksum and stored_checksum != migration.checksum:
            action, reason = "drift", "recorded_checksum_mismatch"
        elif recorded and structure["state"] != "complete":
            action, reason = "drift", "history_schema_mismatch"
        elif recorded and not stored_checksum:
            action, reason = "adopt", "backfill_legacy_history_checksum"
        elif recorded:
            action, reason = "skip", "already_successful"
        elif structure["state"] == "complete":
            action, reason = "adopt", "verified_existing_structure"
        elif structure["state"] == "absent":
            action, reason = "apply", "migration_not_applied"
        else:
            action, reason = "drift", "partial_unrecorded_structure"
        steps.append({
            "number": migration.number,
            "migration_id": migration.migration_id,
            "checksum": migration.checksum,
            "action": action,
            "reason": reason,
            "structure": structure,
        })
    recorded_ids = [migration.migration_id for migration in MIGRATIONS[start_index:target_index + 1] if migration.migration_id in history]
    structural = [step["number"] for step in steps if step["structure"]["state"] == "complete"]
    return {
        "target": MIGRATIONS[target_index].migration_id,
        "recorded_success": recorded_ids,
        "highest_structurally_complete": structural[-1] if structural else None,
        "pending_count": sum(1 for step in steps if step["action"] in {"apply", "adopt"}),
        "has_drift": any(step["action"] == "drift" for step in steps),
        "steps": steps,
    }


def _connect_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _backup_database(path: Path, target: str) -> tuple[Path, str]:
    directory = path.parent / ".migration_backups"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{path.stem}_before_{target}_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    with _connect_readonly(path) as source, sqlite3.connect(destination) as backup:
        source.backup(backup)
    with _connect_readonly(destination) as check:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("backup_integrity_check_failed")
    return destination, hashlib.sha256(destination.read_bytes()).hexdigest()


def _restore_database(backup_path: Path, database: Path) -> None:
    with _connect_readonly(backup_path) as source, sqlite3.connect(database) as destination:
        source.backup(destination)
    with _connect_readonly(database) as check:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("automatic_restore_integrity_check_failed")

def _foreign_key_failures(conn: sqlite3.Connection) -> set[tuple[object, ...]]:
    return {tuple(row) for row in conn.execute("PRAGMA foreign_key_check")}


def _record_success(
    conn: sqlite3.Connection,
    migration: Migration,
    *,
    mode: str,
    started_at: str,
    execution_ms: float,
    backup_path: Path | None,
    backup_sha256: str,
) -> None:
    existing = conn.execute(
        "SELECT id FROM platform_migration_runs WHERE migration_id=? AND status='success'",
        (migration.migration_id,),
    ).fetchone()
    values = (
        migration.name, migration.checksum, _now(), execution_ms,
        str(backup_path) if backup_path else None, backup_sha256,
    )
    if existing:
        conn.execute(
            """UPDATE platform_migration_runs SET migration_name=?,checksum=?,status='success',
            finished_at=?,execution_ms=?,backup_path=COALESCE(backup_path,?),
            backup_sha256=COALESCE(backup_sha256,?) WHERE id=?""",
            (*values, int(existing[0])),
        )
    else:
        conn.execute(
            """INSERT INTO platform_migration_runs(
            migration_id,migration_name,checksum,status,mode,stats_json,started_at,finished_at,
            execution_ms,backup_path,backup_sha256) VALUES (?,?,?,'success',?,'{}',?,?,?,?,?)""",
            (
                migration.migration_id, migration.name, migration.checksum, mode,
                started_at, _now(), execution_ms,
                str(backup_path) if backup_path else None, backup_sha256,
            ),
        )


def _record_failure(conn: sqlite3.Connection, migration: Migration, started_at: str, error: str, elapsed_ms: float) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            """INSERT INTO platform_migration_runs(
            migration_id,migration_name,checksum,status,mode,stats_json,started_at,finished_at,
            execution_ms,error_message) VALUES (?,?,?,'failed','upgrade','{}',?,?,?,?)""",
            (migration.migration_id, migration.name, migration.checksum, started_at, _now(), elapsed_ms, error[:1000]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def run_upgrade(
    database: Path,
    *,
    target: str = "011",
    start: str = "000",
    confirm_formal: bool = False,
    failure_hook: Callable[[Migration, sqlite3.Connection], None] | None = None,
) -> dict[str, object]:
    target_index = _target_index(target)
    formal = resolved_db_path().resolve()
    if database.resolve() == formal and not confirm_formal:
        raise RuntimeError("formal_database_requires_--confirm-formal")
    if database.exists():
        with _connect_readonly(database) as read_conn:
            initial_plan = build_plan(read_conn, target, start)
    else:
        memory = sqlite3.connect(":memory:")
        memory.row_factory = sqlite3.Row
        try:
            initial_plan = build_plan(memory, target, start)
        finally:
            memory.close()
    if initial_plan["has_drift"]:
        raise RuntimeError("schema_drift_detected")
    pending = [step for step in initial_plan["steps"] if step["action"] in {"apply", "adopt"}]
    if not pending:
        return {"status": "up_to_date", "database": str(database), "target": initial_plan["target"], "steps": []}
    database.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    backup_sha = ""
    if database.exists():
        backup_path, backup_sha = _backup_database(database, MIGRATIONS[target_index].number)
    conn = sqlite3.connect(database, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    results: list[dict[str, object]] = []
    try:
        _ensure_history_schema(conn)
        plan = build_plan(conn, target, start)
        if plan["has_drift"]:
            raise RuntimeError("schema_drift_detected_after_history_bootstrap")
        for item in plan["steps"]:
            if item["action"] == "skip":
                continue
            migration = next(m for m in MIGRATIONS if m.migration_id == item["migration_id"])
            started_at = _now()
            started = time.perf_counter()
            if item["action"] == "adopt":
                conn.execute("BEGIN IMMEDIATE")
                try:
                    state = _structure_state(conn, migration)
                    if state["state"] != "complete":
                        raise RuntimeError("adoption_structure_changed")
                    elapsed = (time.perf_counter() - started) * 1000
                    _record_success(
                        conn, migration, mode="adopt", started_at=started_at, execution_ms=elapsed,
                        backup_path=backup_path, backup_sha256=backup_sha,
                    )
                    conn.commit()
                    results.append({"migration_id": migration.migration_id, "action": "adopt", "result": "success", "elapsed_ms": round(elapsed, 3)})
                except Exception:
                    conn.rollback()
                    raise
                continue
            before_fk = _foreign_key_failures(conn)
            conn.execute("BEGIN IMMEDIATE")
            try:
                _apply_migration(conn, migration)
                if failure_hook:
                    failure_hook(migration, conn)
                state = _structure_state(conn, migration)
                if state["state"] != "complete":
                    raise RuntimeError("post_migration_schema_verification_failed")
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("integrity_check_failed")
                after_fk = _foreign_key_failures(conn)
                added_fk = after_fk - before_fk
                if added_fk:
                    raise RuntimeError(f"new_foreign_key_failures:{len(added_fk)}")
                elapsed = (time.perf_counter() - started) * 1000
                _record_success(
                    conn, migration, mode="upgrade", started_at=started_at, execution_ms=elapsed,
                    backup_path=backup_path, backup_sha256=backup_sha,
                )
                conn.commit()
                results.append({"migration_id": migration.migration_id, "action": "apply", "result": "success", "elapsed_ms": round(elapsed, 3)})
            except Exception as exc:
                conn.rollback()
                elapsed = (time.perf_counter() - started) * 1000
                _record_failure(conn, migration, started_at, f"{type(exc).__name__}:{exc}", elapsed)
                raise
        final_plan = build_plan(conn, target, start)
        if final_plan["has_drift"] or any(step["action"] != "skip" for step in final_plan["steps"]):
            raise RuntimeError("final_migration_state_not_clean")
        checkpoint = tuple(conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
        return {
            "status": "success",
            "database": str(database),
            "target": final_plan["target"],
            "backup": str(backup_path) if backup_path else None,
            "backup_sha256": backup_sha or None,
            "steps": results,
            "foreign_key_failure_count": len(_foreign_key_failures(conn)),
            "wal_checkpoint": checkpoint,
        }
    except Exception:
        conn.close()
        if backup_path is not None:
            _restore_database(backup_path, database)
        raise
    finally:
        conn.close()


def inspect_database(database: Path, target: str, start: str = "000") -> dict[str, object]:
    if database.exists():
        with _connect_readonly(database) as conn:
            plan = build_plan(conn, target, start)
            history_rows = 0
            if "platform_migration_runs" in _table_names(conn):
                history_rows = int(conn.execute("SELECT COUNT(*) FROM platform_migration_runs").fetchone()[0])
            return {
                "database": str(database), "database_exists": True,
                "history_rows": history_rows, "plan": plan,
            }
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        return {"database": str(database), "database_exists": False, "history_rows": 0, "plan": build_plan(conn, target, start)}
    finally:
        conn.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Explicit-only 000-011 SQLite migration runner")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "plan"):
        child = subparsers.add_parser(command)
        child.add_argument("--database", required=True)
        child.add_argument("--target", default="011")
        child.add_argument("--start", default="000")
    upgrade = subparsers.add_parser("upgrade")
    upgrade.add_argument("--database", required=True)
    upgrade.add_argument("--target", default="011")
    upgrade.add_argument("--start", default="000")
    upgrade.add_argument("--confirm-formal", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        database = _resolve_database(args.database)
        if args.command in {"status", "plan"}:
            result = inspect_database(database, args.target, args.start)
            if args.command == "status":
                result = {
                    "database": result["database"],
                    "database_exists": result["database_exists"],
                    "history_rows": result["history_rows"],
                    "target": result["plan"]["target"],
                    "recorded_success": result["plan"]["recorded_success"],
                    "highest_structurally_complete": result["plan"]["highest_structurally_complete"],
                    "pending_count": result["plan"]["pending_count"],
                    "has_drift": result["plan"]["has_drift"],
                }
        else:
            result = run_upgrade(
                database, target=args.target, start=args.start, confirm_formal=bool(args.confirm_formal),
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": f"{type(exc).__name__}:{exc}"}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
