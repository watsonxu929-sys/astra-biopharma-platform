from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v04c1_verify_", ignore_cleanup_errors=True) as temp_dir:
        db_path = Path(temp_dir) / "verify.db"
        os.environ["APP_DB_PATH"] = str(db_path)

        from app.v04c1_ingestion import (  # noqa: E402
            create_sync_mapping,
            ensure_v04c1_schema,
            ingest_payload,
            router as intake_router,
            sync_approved_reviews,
        )
        from app.v04c_review import create_pending_relation, db_connection, resolve_review_item, router as review_router  # noqa: E402
        from fastapi import FastAPI  # noqa: E402
        from fastapi.testclient import TestClient  # noqa: E402

        ensure_v04c1_schema(db_path)
        ensure_v04c1_schema(db_path)
        with sqlite3.connect(db_path) as conn:
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {
            "v04c1_ingest_batches",
            "v04c1_source_records",
            "v04c1_candidates",
            "v04c1_canonical_facts",
            "v04c1_canonical_relations",
            "v04c1_fact_evidence",
            "v04c1_sync_mappings",
            "v04c1_sync_logs",
        }
        check(required.issubset(names), "v0.4C-1 数据表完整")
        check(True, "migration is repeatable")

        app = FastAPI()
        app.include_router(review_router)
        app.include_router(intake_router)
        client = TestClient(app)
        check(client.get("/review/health").status_code == 200, "review health route")
        check(client.get("/review/intake/health").status_code == 200, "intake health route")

        payload = {
            "batch": {"source_name": "verify", "source_type": "test"},
            "records": [
                {
                    "external_key": "V-001",
                    "title": "第一来源",
                    "source_url": "https://example.com/v1",
                    "subject_type": "org",
                    "subject_id": "ORG-V-001",
                    "subject_label": "验证企业",
                    "fields": [
                        {"name": "临床阶段", "value": "I期", "fact_level": "fact", "excerpt": "进入I期"},
                        {"name": "员工人数", "value": "约80人", "fact_level": "inference", "excerpt": "估算"},
                    ],
                },
                {
                    "external_key": "V-002",
                    "title": "第二来源",
                    "source_url": "https://example.com/v2",
                    "subject_type": "org",
                    "subject_id": "ORG-V-001",
                    "subject_label": "验证企业",
                    "fields": [
                        {"name": "临床阶段", "value": "I期", "fact_level": "fact", "excerpt": "同值复核"},
                    ],
                },
            ],
        }
        result = ingest_payload(payload, created_by="verify", db_path=db_path)
        check(result["batch"]["processed_records"] == 2, "结构化来源接入")

        duplicate = ingest_payload(payload, created_by="verify", db_path=db_path)
        check(duplicate["batch"]["duplicate_records"] == 2, "相同来源重复保护")

        text_only = ingest_payload(
            {
                "batch": {"source_name": "verify-text"},
                "records": [
                    {
                        "external_key": "TXT-001",
                        "title": "plain text",
                        "content": "only unstructured text, no fields or relations",
                    }
                ],
            },
            created_by="verify",
            db_path=db_path,
        )
        check(text_only["batch"]["needs_structuring_records"] == 1, "plain text is marked needs_structuring")
        with db_connection(db_path) as conn:
            no_text_review = conn.execute(
                "SELECT COUNT(*) AS c FROM v04c_review_items WHERE batch_tag='TXT-001'"
            ).fetchone()["c"]
        check(no_text_review == 0, "plain text does not create formal fact review")

        with db_connection(db_path) as conn:
            stage_candidates = conn.execute("SELECT * FROM v04c1_candidates WHERE field_name='临床阶段'").fetchall()
            check(len(stage_candidates) == 2, "同值多来源候选均保留")
            review_ids = {row["review_item_id"] for row in stage_candidates}
            check(len(review_ids) == 1, "同值来源合并到同一审核项")
            evidence_count = conn.execute("SELECT COUNT(*) AS c FROM v04c_review_evidence WHERE review_item_id=?", (next(iter(review_ids)),)).fetchone()["c"]
            check(evidence_count == 2, "同一审核项保留两条证据")
            inference = conn.execute("SELECT * FROM v04c1_candidates WHERE field_name='员工人数'").fetchone()
            stage_review_id = int(next(iter(review_ids)))
            inference_review_id = int(inference["review_item_id"])

        resolve_review_item(
            stage_review_id,
            decision="approved",
            actor="verify",
            note="官方与权威来源一致",
            resolved_value="I期",
            fact_level="fact",
            db_path=db_path,
        )
        resolve_review_item(
            inference_review_id,
            decision="approved",
            actor="verify",
            note="仅允许保留为推测",
            resolved_value="约80人",
            fact_level="inference",
            db_path=db_path,
        )

        sync_result = sync_approved_reviews(actor="verify", db_path=db_path)
        check(stage_review_id in sync_result["synced"], "已通过且定为事实可同步")
        check(inference_review_id in sync_result["waiting_fact"], "推测禁止同步为正式事实")

        with db_connection(db_path) as conn:
            fact = conn.execute("SELECT * FROM v04c1_canonical_facts WHERE field_name='临床阶段' AND is_current=1").fetchone()
            check(fact is not None and fact["fact_value"] == "I期", "正式事实库写入正确")
            inferred_fact = conn.execute("SELECT * FROM v04c1_canonical_facts WHERE field_name='员工人数' AND is_current=1").fetchone()
            check(inferred_fact is None, "推测未进入正式事实库")

            conn.execute("CREATE TABLE organizations (id TEXT PRIMARY KEY, name TEXT, clinical_stage TEXT)")
            conn.execute("INSERT INTO organizations(id,name,clinical_stage) VALUES ('ORG-V-001','验证企业','临床前')")
            conn.commit()

        create_sync_mapping(
            subject_type="org",
            field_name="临床阶段",
            target_table="organizations",
            target_id_column="id",
            target_field_column="clinical_stage",
            target_label_column="name",
            allow_insert=False,
            enabled=True,
            db_path=db_path,
        )

        # 新来源制造正式事实冲突，审核通过后验证版本升级和业务表映射。
        conflict = ingest_payload(
            {
                "batch": {"source_name": "verify-conflict"},
                "records": [{
                    "external_key": "V-003",
                    "subject_type": "org",
                    "subject_id": "ORG-V-001",
                    "subject_label": "验证企业",
                    "source_url": "https://example.com/v3",
                    "fields": [{"name": "临床阶段", "value": "II期", "fact_level": "fact", "excerpt": "进入II期"}],
                }],
            },
            created_by="verify",
            db_path=db_path,
        )
        candidate = conflict["results"][0]["candidates"][0]
        check(candidate["comparison_result"] == "conflict_fact", "新值与正式事实冲突自动识别")
        conflict_review_id = int(candidate["review_item_id"])
        resolve_review_item(
            conflict_review_id,
            decision="approved",
            actor="verify",
            note="新来源发布时间更晚且为官方披露",
            resolved_value="II期",
            fact_level="fact",
            db_path=db_path,
        )
        sync_approved_reviews(actor="verify", db_path=db_path)

        with db_connection(db_path) as conn:
            current = conn.execute("SELECT * FROM v04c1_canonical_facts WHERE field_name='临床阶段' AND is_current=1").fetchone()
            history_count = conn.execute("SELECT COUNT(*) AS c FROM v04c1_canonical_facts WHERE field_name='临床阶段'").fetchone()["c"]
            mapped = conn.execute("SELECT clinical_stage FROM organizations WHERE id='ORG-V-001'").fetchone()["clinical_stage"]
            log_count = conn.execute("SELECT COUNT(*) AS c FROM v04c1_sync_logs WHERE status='success'").fetchone()["c"]
        check(current["fact_value"] == "II期" and current["version"] == 2, "正式事实版本升级")
        check(history_count == 2, "旧事实历史版本保留")
        check(mapped == "II期", "启用映射后更新现有业务表字段")
        check(log_count >= 3, "同步操作留有审计日志")

        pending_relation = create_pending_relation(
            left_type="person",
            left_id="PER-PENDING",
            left_label="Pending Person",
            relation_type="任职",
            right_type="org",
            right_id="ORG-PENDING",
            right_label="Pending Org",
            confidence=0.5,
            basis="unconfirmed",
            db_path=db_path,
        )
        relation_sync = sync_approved_reviews(actor="verify", db_path=db_path)
        with db_connection(db_path) as conn:
            relation_count = conn.execute(
                "SELECT COUNT(*) AS c FROM v04c1_canonical_relations WHERE source_pending_relation_id=?",
                (pending_relation["id"],),
            ).fetchone()["c"]
        check(relation_sync["relations"]["inserted"] == [] and relation_count == 0, "待确认关联不能提前进正式关联库")

        print("-" * 68)
        print("ALL V0.4C-1 CHECKS PASSED")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        raise
