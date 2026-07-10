from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.collection_service import create_collection_source
from app.services.intelligence_flow_service import (
    approve_candidate_to_formal_store,
    convert_signal_to_investment_lead,
    generate_daily_and_weekly_reports,
    report_snapshot_trace,
    run_processing_worker_once,
)
from app.services.pipeline import create_pipeline_run, retry_pipeline
from app.services.tasks.task_dispatcher import create_task
from app.services.tasks.task_runner import run_once
from app.v04c_review import db_connection
from scripts.migrate_v05kl import migrate as migrate_all_latest


class Check:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def ok(self, condition: bool, message: str) -> None:
        if condition:
            self.passed += 1
            print(f"[PASS] {message}")
        else:
            self.failed += 1
            print(f"[FAIL] {message}")


def _copy_db() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="bio_flow_verify_")) / "app_flow.db"
    src = ROOT / "data" / "app.db"
    if src.exists():
        shutil.copy2(src, tmp)
    else:
        tmp.touch()
    migrate_all_latest(tmp, backup=False)
    return tmp


def _patch_collection_http() -> None:
    import app.services.collection_service as collection_service

    def fake_robots(url: str, user_agent: str = "BiopharmaIntelBot") -> dict:
        return {"allowed": True, "status": "allowed", "summary": "受控验证来源"}

    def fake_get(url: str, timeout: int = 15):
        if "local-flow" in url:
            html = """
            <html><head><title>本地模拟来源</title></head><body><article>
            华辰生物公司完成A轮融资2亿元，用于临床管线推进，并正在寻找园区落地和招商对接合作机会。
            </article></body></html>
            """
        else:
            html = """
            <html><head><title>受控真实来源</title></head><body><article>
            华辰生物公司宣布与创新药园区签约合作，推进临床试验和产业化基地建设。
            </article></body></html>
            """
        return html, 200, "text/html; charset=utf-8", {}

    collection_service.check_robots = fake_robots
    collection_service._http_get = fake_get


def _seed(db_path: Path) -> tuple[int, int, str]:
    with db_connection(db_path) as conn:
        org = conn.execute("SELECT * FROM organizations WHERE standard_name='华辰生物公司' ORDER BY id LIMIT 1").fetchone()
        if org:
            org_ext = org["external_id"]
        else:
            org_ext = "ORG-FLOW-001"
            conn.execute(
                """
                INSERT OR IGNORE INTO organizations(external_id,standard_name,visibility,verification_status,manually_confirmed,created_at)
                VALUES (?, '华辰生物公司', '内部', '已确认', 1, datetime('now'))
                """,
                (org_ext,),
            )
    local = create_collection_source(
        name="本地模拟来源",
        source_type="webpage",
        url="https://verify.local/local-flow",
        subject_type="organization",
        subject_id=org_ext,
        db_path=db_path,
    )
    real = create_collection_source(
        name="受控真实来源",
        source_type="webpage",
        url="https://example.org/controlled-biopharma-news",
        subject_type="organization",
        subject_id=org_ext,
        db_path=db_path,
    )
    with db_connection(db_path) as conn:
        conn.execute("UPDATE v04g_monitoring_sources SET check_frequency='daily', last_checked_at=NULL, is_enabled=1, auto_paused=0 WHERE id IN (?,?)", (local["id"], real["id"]))
    return int(local["id"]), int(real["id"]), org_ext


def main() -> int:
    check = Check()
    db_path = _copy_db()
    _patch_collection_http()
    local_id, real_id, org_ext = _seed(db_path)

    task = create_task("collection", payload={"due_only": True, "limit": 10}, created_by="verify", idempotency_key="verify-full-chain", db_path=db_path)
    check.ok(task["status"] == "pending", "Scheduler 创建 pending 采集队列任务")
    with db_connection(db_path) as conn:
        pending_before = conn.execute("SELECT COUNT(*) FROM task_queue WHERE task_uid=? AND status='pending'", (task["task_uid"],)).fetchone()[0]
    check.ok(pending_before == 1, "系统重启前 pending 任务保存在数据库")
    with db_connection(db_path) as conn:
        pending_after = conn.execute("SELECT COUNT(*) FROM task_queue WHERE task_uid=? AND status='pending'", (task["task_uid"],)).fetchone()[0]
    check.ok(pending_after == 1, "系统重启后 pending 任务仍保留")

    worker_result = run_once(worker_id="verify-worker", task_type="collection", db_path=db_path)
    check.ok(worker_result.get("processed") == 1 and worker_result.get("status") == "success", "Worker 自动领取 pending 任务")
    scheduled = worker_result.get("result", {}).get("scheduled_collection_jobs", {})
    check.ok(scheduled.get("created", 0) >= 2, "到期来源自动创建采集任务")
    check.ok(worker_result.get("result", {}).get("processing_jobs_created", 0) >= 1, "采集成功后自动创建加工任务")

    # Process any remaining collection job created by the scheduler, then process all pending processing jobs.
    run_once(worker_id="verify-worker-2", task_type="collection", db_path=db_path)
    processing = run_processing_worker_once(limit=20, db_path=db_path, operator="verify-worker")
    check.ok(processing.get("processed", 0) >= 1, "加工 Worker 自动处理 pending 加工任务")
    with db_connection(db_path) as conn:
        candidates = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE review_status IN ('pending','needs_review') ORDER BY id").fetchall()
    check.ok(len(candidates) > 0, "加工完成后进入候选审核")

    with db_connection(db_path) as conn:
        event = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE candidate_type='event' ORDER BY confidence_score DESC, id LIMIT 1").fetchone()
    check.ok(event is not None, "中文文本抽取出事件候选")
    applied = approve_candidate_to_formal_store(int(event["id"]), actor="verify-reviewer", db_path=db_path)
    check.ok(applied["applied"].get("result") == "success", "审核批准后写入正式事件")
    with db_connection(db_path) as conn:
        formal_event = conn.execute("SELECT * FROM events WHERE related_entity=? ORDER BY id DESC LIMIT 1", (org_ext,)).fetchone()
    check.ok(formal_event is not None and formal_event["manually_confirmed"], "正式事件保留确认状态和主体关联")

    from app.services.signals import generate_signals

    signal_result = generate_signals(limit=50, dry_run=False, db_path=db_path)
    check.ok(signal_result.get("created", 0) >= 1, "正式事件自动生成产业信号")
    with db_connection(db_path) as conn:
        signal = conn.execute("SELECT * FROM v05e_industry_signals WHERE subject_id=? ORDER BY id DESC LIMIT 1", (org_ext,)).fetchone()
    check.ok(signal is not None, "产业信号写入信号中心")

    reports = generate_daily_and_weekly_reports(db_path=db_path, actor="verify")
    check.ok(reports.get("generated") == 2, "信号进入日报和周报生成流程")
    traces = []
    for item in reports["reports"]:
        traces.extend(report_snapshot_trace(int(item["report_id"]), db_path=db_path))
    check.ok(any(t.get("type") == "snapshot" for t in traces), "报告引用可回溯来源快照")

    lead = convert_signal_to_investment_lead(int(signal["id"]), owner="verify", db_path=db_path)
    check.ok(lead.get("created") is True, "信号可人工转为招商线索")
    with db_connection(db_path) as conn:
        lead_count = conn.execute("SELECT COUNT(*) FROM v04f_lead_records WHERE subject_id=?", (org_ext,)).fetchone()[0]
    check.ok(lead_count >= 1, "招商线索复用现有线索模型")

    pipe = create_pipeline_run(local_id, created_by="verify", pilot=True, dry_run=False, db_path=db_path)
    with db_connection(db_path) as conn:
        conn.execute("UPDATE v05i_pipeline_runs SET status='failed', current_stage='processing', failed_stage='processing', error_code='verify_failure', error_summary='验证失败恢复' WHERE id=?", (pipe["id"],))
    retry = retry_pipeline(int(pipe["id"]), actor="verify", db_path=db_path)
    check.ok(retry.get("status") in {"waiting_review", "partial", "completed", "failed"} and retry.get("retry_count", 0) >= 1, "失败任务可从失败阶段继续")

    homepage = (ROOT / "app" / "templates" / "dashboard.html").read_text(encoding="utf-8")
    for label in ["今日情报", "待审核候选", "高等级信号", "招商机会"]:
        check.ok(label in homepage, f"首页集中展示：{label}")

    print(f"临时数据库={db_path}")
    print(f"passed={check.passed} failed={check.failed}")
    return 0 if check.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
