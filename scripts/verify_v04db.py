from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def create_business_tables(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS organizations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                standard_name TEXT,
                name TEXT
            );
            CREATE TABLE IF NOT EXISTS people(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT
            );
            CREATE TABLE IF NOT EXISTS projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT
            );
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT
            );
            CREATE TABLE IF NOT EXISTS resources(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                description TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO organizations(external_id,standard_name,name) VALUES('ORG-001','华辰生物','华辰生物')"
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    try:
        from app.v04d_structuring import ensure_v04d_schema  # noqa: F401
    except Exception as exc:
        raise RuntimeError(f"v0.4D-A is missing: {exc}") from exc

    with tempfile.TemporaryDirectory(prefix="v04db_verify_") as temp_dir:
        db_path = Path(temp_dir) / "verify.db"
        os.environ["APP_DB_PATH"] = str(db_path)
        create_business_tables(db_path)

        from app.v04c_review import db_connection
        from app.v04c1_ingestion import ingest_payload
        from app.v04db_prestructure import (
            accept_candidate,
            accept_high_confidence,
            ensure_v04db_schema,
            extract_source,
            reject_candidate,
            run_detail,
            update_rule,
        )

        ensure_v04db_schema(db_path, allow_migration=True)
        with db_connection(db_path) as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v04db_%'"
                ).fetchall()
            }
            rules = conn.execute("SELECT COUNT(*) AS c FROM v04db_rules").fetchone()["c"]
        check(len(tables) == 4, "v0.4D-B tables created")
        check(rules >= 6, "default offline rules seeded")

        text = (
            "华辰生物于2026年6月完成B轮融资，融资金额1.2亿元。"
            "张三为华辰生物创始人。华辰生物与远景资本达成战略合作。"
            "项目CM-101计划进入II期临床。"
        )
        ingested = ingest_payload(
            {
                "batch": {"source_name": "verify", "source_type": "manual"},
                "records": [{
                    "external_key": "verify-v04db-001",
                    "title": "华辰生物完成B轮融资",
                    "source_url": "https://example.test/v04db",
                    "content": text,
                    "excerpt": text,
                }],
            },
            created_by="verify",
            db_path=db_path,
        )
        source = ingested["results"][0]["record"]
        check(source["status"] == "needs_structuring", "unstructured source is eligible")

        extracted = extract_source(int(source["id"]), actor="verify", db_path=db_path)
        run = extracted["run"]
        check(run["candidate_count"] >= 5, "offline extractor generates candidates")
        check(run["high_count"] >= 1, "confidence levels are calculated")

        detail = run_detail(int(run["id"]), db_path)
        check(all(row["evidence_excerpt"] for row in detail["candidates"]), "every candidate has evidence")
        check(all(row["evidence_start"] is not None for row in detail["candidates"]), "evidence offsets are stored")
        check(any(row["match_status"] == "exact" for row in detail["candidates"]), "existing subject exact match is suggested")

        field = next(row for row in detail["candidates"] if row["candidate_type"] == "field")
        accepted = accept_candidate(int(field["id"]), actor="verify", db_path=db_path)
        check(accepted["status"] == "accepted" and accepted["accepted_item_id"], "single candidate accepted into v0.4D-A draft")
        accepted_again = accept_candidate(int(field["id"]), actor="verify", db_path=db_path)
        check(accepted_again["accepted_item_id"] == accepted["accepted_item_id"], "candidate acceptance is idempotent")

        another = next(row for row in detail["candidates"] if row["id"] != field["id"] and row["status"] == "suggested")
        rejected = reject_candidate(int(another["id"]), db_path=db_path)
        check(rejected["status"] == "rejected", "candidate can be rejected")

        bulk = accept_high_confidence(int(run["id"]), actor="verify", db_path=db_path)
        check(isinstance(bulk["accepted"], list), "high-confidence batch accept executes")

        with db_connection(db_path) as conn:
            item_count = conn.execute("SELECT COUNT(*) AS c FROM v04d_structure_items").fetchone()["c"]
            review_count = conn.execute("SELECT COUNT(*) AS c FROM v04c_review_items").fetchone()["c"]
            fact_count = conn.execute("SELECT COUNT(*) AS c FROM v04c1_canonical_facts").fetchone()["c"]
            rule = conn.execute("SELECT * FROM v04db_rules ORDER BY id LIMIT 1").fetchone()
        check(item_count >= 1, "accepted suggestions only create structuring drafts")
        check(review_count == 0, "pre-structuring does not bypass v0.4D-A review submission")
        check(fact_count == 0, "pre-structuring never writes canonical facts")

        updated = update_rule(
            int(rule["id"]),
            pattern=rule["pattern"],
            priority=int(rule["priority"]) + 1,
            base_confidence=0.80,
            enabled=True,
            db_path=db_path,
        )
        check(updated["priority"] == int(rule["priority"]) + 1, "rule management works")

        reused = extract_source(int(source["id"]), actor="verify", db_path=db_path)
        check(reused["reused"] is True and reused["run"]["id"] == run["id"], "normal extraction reuses latest run")
        rerun = extract_source(int(source["id"]), actor="verify", force=True, db_path=db_path)
        check(rerun["run"]["id"] != run["id"], "forced re-extraction creates a new run")

    print("ALL V0.4D-B CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        raise
