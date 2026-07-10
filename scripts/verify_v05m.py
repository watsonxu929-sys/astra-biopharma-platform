from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(condition: bool, message: str, failures: list[str]) -> None:
    if condition:
        print(f"[PASS] {message}")
    else:
        print(f"[FAIL] {message}")
        failures.append(message)


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    failures: list[str] = []
    core_templates = {
        "app/templates/base.html": ["生物医药产业情报系统", "内部使用"],
        "app/templates/dashboard.html": ["产业情报工作台", "今日情报", "核心入口"],
        "app/templates/v05e_dashboard.html": ["情报总览", "信息采集", "情报加工", "人工审核", "报告分析"],
        "app/templates/v05f_collection.html": ["信息采集中心", "新增采集来源", "暂无采集任务"],
        "app/templates/v05g_processing.html": ["情报加工中心", "新建加工任务", "加工执行器", "暂无加工任务"],
        "app/templates/v05h_reports.html": ["报告中心", "生成报告", "草稿", "暂无报告"],
        "app/templates/v05i_pipeline.html": ["流水线中心", "质量指标", "来源采集成功率", "暂无数据"],
        "app/templates/v04c_review_queue.html": ["数据审核中心"],
    }
    forbidden = ["Collection Center", "Processing Center", "Pipeline Center", "Weekly Industry Report", "Executive Summary", "Core Signals", "Create Job", "Run once", "No jobs"]
    version_pattern = re.compile(r"v0\.(?:4C(?:-1)?|4D|5[FGHIJKLM]|5K-L)")
    for rel, required in core_templates.items():
        text = read(rel)
        check(all(item in text for item in required), f"{rel} has required Chinese product text", failures)
        check(not any(item in text for item in forbidden), f"{rel} has no legacy English titles/buttons", failures)
        check(not version_pattern.search(text), f"{rel} has no user-visible development version", failures)

    nav_text = read("app/navigation.py")
    from app.navigation import NAV_ITEMS, navigation_for
    check(len(NAV_ITEMS) <= 7, "primary navigation has no more than 7 items", failures)
    labels = [item.label for item in NAV_ITEMS]
    check(labels == ["首页", "情报中心", "主体中心", "产业分析", "业务经营", "Q-BAY俱乐部", "系统管理"], "primary navigation labels are unified", failures)
    nav = navigation_for({"auth_disabled": True, "permissions": []}, "/intelligence/dashboard")
    secondary = [item["label"] for item in nav["secondary"]]
    check(secondary == ["情报总览", "信息采集", "情报加工", "流水线中心", "产业信号", "报告中心"], "intelligence secondary navigation is unified and deduplicated", failures)
    check("采集" not in labels and "加工" not in labels and "报告" not in labels and "审核" not in labels, "forbidden module names are not primary navigation entries", failures)

    from app.i18n.helpers import format_metric, with_labels
    labeled = with_labels({"status": "waiting_review", "report_type": "weekly", "candidate_type": "organization"})
    check(labeled["status_label"] == "等待人工审核", "API helper keeps machine status and adds Chinese status_label", failures)
    check(labeled["report_type_label"] == "产业情报周报", "API helper adds Chinese report_type_label", failures)
    check(format_metric("source_success_rate", None)["display_value"] == "暂无数据", "metric helper shows no-sample state", failures)
    check(format_metric("candidate_per_item", 2)["display_value"].endswith("条"), "quantity metric has unit", failures)

    report_service = read("app/services/reports/report_generation_service.py")
    check("产业情报周报" in report_service and "执行摘要" in report_service and "核心产业信号" in report_service, "report generator uses Chinese title and sections", failures)
    check("Weekly Industry Report" not in report_service and "Executive Summary" not in report_service, "report generator has no legacy English section titles", failures)

    api_text = read("app/api/v1/collection.py") + read("app/api/v1/processing.py") + read("app/api/v1/pipeline.py") + read("app/api/v1/reports.py")
    check("add_labels" in api_text, "API endpoints add Chinese label fields while preserving machine fields", failures)

    port_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in ROOT.glob("*.bat"))
    check("8001" not in port_text and "8002" not in port_text, "root Windows scripts do not expose extra web ports", failures)
    check("8000" in port_text or "APP_PORT" in port_text, "root Windows scripts keep default web access on APP_PORT/8000", failures)

    scan = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_user_visible_english.py")], cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
    print((scan.stdout or "").rstrip())
    if scan.stderr:
        print(scan.stderr.rstrip())
    check(scan.returncode == 0, "user-visible English scan has no must-fix findings", failures)

    print(f"verify_v05m completed passed={0 if failures else 1} failed={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())


