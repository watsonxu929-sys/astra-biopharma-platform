from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.v04c_review import db_connection  # noqa: E402
from app.v04c1_ingestion import ingest_payload  # noqa: E402
from app.v04d_structuring import (  # noqa: E402
    create_task_item,
    ensure_source_from_raw_intelligence,
    ensure_v04d_schema,
    get_or_create_task,
    mark_task_ready,
    return_task_for_editing,
    submit_task_to_review,
    task_detail,
    update_task_item,
    validate_task,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def create_raw_table(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_intelligence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source_url TEXT,
                source_type TEXT NOT NULL,
                content TEXT NOT NULL,
                visibility TEXT NOT NULL,
                review_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v04d_verify_") as tmp:
        db_path = Path(tmp) / "verify.db"
        create_raw_table(db_path)
        ensure_v04d_schema(db_path, allow_migration=True)

        with db_connection(db_path) as conn:
            table_count = conn.execute(
                "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v04d_%'"
            ).fetchone()["c"]
        check(table_count == 4, "v0.4D tables created")

        ingest = ingest_payload(
            {
                "batch": {"source_name": "verify-source", "source_type": "manual"},
                "records": [
                    {
                        "external_key": "verify-001",
                        "source_name": "verify-source",
                        "title": "测试公司完成融资并任命创始人",
                        "source_url": "https://example.test/news/1",
                        "content": "测试公司宣布完成1亿元融资。张三为公司创始人。项目预计2027年进入II期临床。",
                        "excerpt": "测试公司宣布完成1亿元融资。张三为公司创始人。",
                    }
                ],
            },
            created_by="verify",
            db_path=db_path,
        )
        source = ingest["results"][0]["record"]
        check(source["status"] == "needs_structuring", "unstructured source enters needs_structuring")

        task = get_or_create_task(int(source["id"]), created_by="verify", db_path=db_path)
        same_task = get_or_create_task(int(source["id"]), created_by="verify", db_path=db_path)
        check(task["id"] == same_task["id"], "one source creates only one task")

        field = create_task_item(
            int(task["id"]),
            actor="verify",
            db_path=db_path,
            item_type="field",
            subject_type="organization",
            subject_id="ORG-VERIFY-001",
            subject_label="测试公司",
            field_name="融资金额",
            candidate_value="1亿元",
            fact_level="fact",
            confidence="0.95",
            evidence_excerpt="测试公司宣布完成1亿元融资。",
            source_url="https://example.test/news/1",
        )
        relation = create_task_item(
            int(task["id"]),
            actor="verify",
            db_path=db_path,
            item_type="relation",
            left_type="person",
            left_label="张三",
            relation_type="创始人",
            right_type="organization",
            right_id="ORG-VERIFY-001",
            right_label="测试公司",
            fact_level="fact",
            confidence="0.9",
            evidence_excerpt="张三为公司创始人。",
        )
        event = create_task_item(
            int(task["id"]),
            actor="verify",
            db_path=db_path,
            item_type="event",
            event_name="测试公司完成融资",
            event_date="2026-06-29",
            event_type="融资",
            related_entity="测试公司",
            event_summary="测试公司宣布完成1亿元融资。",
            fact_level="fact",
            confidence="0.9",
            evidence_excerpt="测试公司宣布完成1亿元融资。",
        )
        check(bool(field and relation and event), "field, relation and event drafts created")

        validation = validate_task(int(task["id"]), db_path)
        check(validation["ok"] and validation["item_count"] == 3, "task validation passes with evidence")

        ready = mark_task_ready(int(task["id"]), actor="verify", db_path=db_path)
        check(ready["status"] == "ready", "draft task enters ready state")
        returned = return_task_for_editing(
            int(task["id"]), reviewer="reviewer", note="补充事件说明", db_path=db_path
        )
        check(returned["status"] == "returned", "ready task can be returned for editing")

        update_task_item(
            int(event["id"]),
            actor="verify",
            db_path=db_path,
            item_type="event",
            event_name="测试公司完成A轮融资",
            event_date="2026-06-29",
            event_type="融资",
            related_entity="测试公司",
            event_summary="测试公司完成A轮融资，金额为1亿元。",
            fact_level="fact",
            confidence="0.92",
            evidence_excerpt="测试公司宣布完成1亿元融资。",
        )
        mark_task_ready(int(task["id"]), actor="verify", db_path=db_path)
        result = submit_task_to_review(int(task["id"]), actor="reviewer", db_path=db_path)
        check(not result["failed"] and len(result["succeeded"]) == 3, "all structured items sent to review")

        detail = task_detail(int(task["id"]), db_path)
        check(detail["task"]["status"] == "submitted", "task becomes submitted")
        check(all(item["status"] == "submitted" for item in detail["items"]), "all items are locked as submitted")

        with db_connection(db_path) as conn:
            candidate_count = conn.execute(
                "SELECT COUNT(*) AS c FROM v04c1_candidates WHERE source_record_id=?",
                (source["id"],),
            ).fetchone()["c"]
            review_count = conn.execute(
                "SELECT COUNT(*) AS c FROM v04c_review_items"
            ).fetchone()["c"]
            canonical_count = conn.execute(
                "SELECT COUNT(*) AS c FROM v04c1_canonical_facts"
            ).fetchone()["c"]
            pending_relation = conn.execute(
                "SELECT fact_level FROM v04c_pending_relations LIMIT 1"
            ).fetchone()
        check(candidate_count >= 7, "event expands into auditable field candidates")
        check(review_count >= 7, "candidates entered the v0.4C review queue")
        check(canonical_count == 0, "structuring does not bypass formal fact review")
        check(pending_relation and pending_relation["fact_level"] == "inference", "relation remains inference until manual approval")

        before_count = candidate_count
        try:
            submit_task_to_review(int(task["id"]), actor="reviewer", db_path=db_path)
            raise AssertionError("submitted task should not be submitted again")
        except ValueError:
            pass
        with db_connection(db_path) as conn:
            after_count = conn.execute(
                "SELECT COUNT(*) AS c FROM v04c1_candidates WHERE source_record_id=?",
                (source["id"],),
            ).fetchone()["c"]
        check(after_count == before_count, "repeat submit does not create duplicate candidates")

        with db_connection(db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO raw_intelligence(
                    title, source_url, source_type, content, visibility, review_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "原始情报直连测试",
                    "https://example.test/raw/1",
                    "人工录入",
                    "这是一条用于验证原始情报直连结构化任务的正文内容。",
                    "内部",
                    "待分析",
                    "2026-06-29T00:00:00",
                ),
            )
            raw_id = int(cursor.lastrowid)
        raw_source, raw_task = ensure_source_from_raw_intelligence(
            raw_id, actor="verify", db_path=db_path
        )
        raw_source_2, raw_task_2 = ensure_source_from_raw_intelligence(
            raw_id, actor="verify", db_path=db_path
        )
        check(raw_source["id"] == raw_source_2["id"], "raw intelligence source import is idempotent")
        check(raw_task["id"] == raw_task_2["id"], "raw intelligence task creation is idempotent")

    print("ALL V0.4D CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        raise
