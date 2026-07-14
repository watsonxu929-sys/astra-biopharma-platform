from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.collection_service import list_jobs, list_items, list_sources, run_worker
from app.services.intelligence_flow_service import schedule_due_collection_jobs


def log(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")


def get_source_stats(db_path: str):
    sources, _ = list_sources(db_path=db_path)
    stats = []
    for s in sources:
        stats.append({
            "id": s["id"],
            "name": s["name"],
            "source_type": s["source_type"],
            "is_enabled": s["is_enabled"],
            "collected_item_count": s.get("collected_item_count", 0),
            "latest_job_status": s.get("latest_job_status"),
            "latest_result_summary": s.get("latest_result_summary"),
        })
    return stats


def get_job_summary(db_path: str):
    jobs, _ = list_jobs(db_path=db_path)
    summary = []
    for j in jobs[:10]:
        summary.append({
            "id": j["id"],
            "run_no": j["run_no"],
            "source_name": j["source_name"],
            "status": j["status"],
            "status_label": j.get("status_label"),
            "created_at": j["created_at"],
            "finished_at": j["finished_at"],
            "new_content_count": j.get("new_content_count", 0),
            "duplicate_content_count": j.get("duplicate_content_count", 0),
            "changed_content_count": j.get("changed_content_count", 0),
            "failed_content_count": j.get("failed_content_count", 0),
            "error_type": j.get("error_type"),
        })
    return summary


def run_test(db_path: str):
    results = []
    
    for run_num in range(1, 4):
        log(f"=== 第 {run_num} 次运行 ===")
        
        start_time = time.time()
        
        log("调度到期任务...")
        scheduled = schedule_due_collection_jobs(limit=10, db_path=db_path, operator="t1-test")
        log(f"创建了 {scheduled['created']} 个任务，跳过 {scheduled['skipped']} 个")
        
        log("执行采集任务...")
        worker_result = run_worker(once=False, limit=20, db_path=db_path, operator="t1-test")
        
        elapsed = time.time() - start_time
        
        log("收集统计...")
        source_stats = get_source_stats(db_path)
        job_summary = get_job_summary(db_path)
        items, total_items = list_items(db_path=db_path)
        
        result = {
            "run": run_num,
            "start_time": datetime.now().isoformat(),
            "elapsed_seconds": round(elapsed, 2),
            "scheduled_created": scheduled["created"],
            "scheduled_skipped": scheduled["skipped"],
            "processed_jobs": worker_result.get("processed", 0),
            "job_results": worker_result.get("results", []),
            "source_stats": source_stats,
            "job_summary": job_summary,
            "total_items": total_items,
        }
        
        results.append(result)
        
        log(f"本次运行耗时 {elapsed:.2f} 秒")
        log(f"共处理 {worker_result.get('processed', 0)} 个任务")
        log(f"当前原始情报总数: {total_items}")
        
        for job in worker_result.get("results", []):
            status = job.get("status")
            new = job.get("new", 0)
            dup = job.get("duplicate", 0)
            changed = job.get("changed", 0)
            error = job.get("error_type")
            log(f"  任务 {job.get('run_id')}: {status} - 新增={new} 重复={dup} 变化={changed} {'错误='+error if error else ''}")
        
        if run_num < 3:
            log("等待 5 秒后进行下一次运行...")
            time.sleep(5)
    
    return results


def main():
    db_path = "data/t1_test.db"
    
    log(f"使用数据库: {db_path}")
    log("开始三次连续运行验证...")
    
    try:
        results = run_test(db_path)
        
        log("\n=== 验证报告 ===")
        for r in results:
            log(f"第 {r['run']} 次运行:")
            log(f"  耗时: {r['elapsed_seconds']} 秒")
            log(f"  创建任务: {r['scheduled_created']}")
            log(f"  处理任务: {r['processed_jobs']}")
            log(f"  原始情报总数: {r['total_items']}")
        
        report_path = "docs/trae/T1_THREE_RUN_ACCEPTANCE.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# T1 三次连续运行验证报告\n\n")
            f.write(f"验证时间: {datetime.now().isoformat()}\n")
            f.write(f"数据库: {db_path}\n\n")
            f.write("## 验证结果\n\n")
            
            for i, result in enumerate(results, 1):
                f.write(f"### 第 {i} 次运行\n\n")
                f.write(f"- 开始时间: {result['start_time']}\n")
                f.write(f"- 耗时: {result['elapsed_seconds']} 秒\n")
                f.write(f"- 创建任务: {result['scheduled_created']}\n")
                f.write(f"- 处理任务: {result['processed_jobs']}\n")
                f.write(f"- 原始情报总数: {result['total_items']}\n\n")
                
                f.write("**来源状态:**\n")
                for s in result["source_stats"]:
                    f.write(f"- {s['name']} ({s['source_type']}): {s['latest_job_status'] or '无'} | 已采内容: {s['collected_item_count']}\n")
                
                f.write("\n**任务结果:**\n")
                for j in result["job_summary"]:
                    f.write(f"- {j['run_no']}: {j['status']} | 新增={j['new_content_count']} 重复={j['duplicate_content_count']} 变化={j['changed_content_count']}\n")
        
        log(f"验证报告已写入: {report_path}")
        log("验证完成!")
        
        return 0
    except Exception as exc:
        log(f"验证失败: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
