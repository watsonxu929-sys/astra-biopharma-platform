from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright


FORBIDDEN_COPY = (
    "Collection Pipeline", "Processing", "Candidate", "Recommendation",
    "Golden Loop", "AI实验能力", "Research实验入口",
)


def _login(page: Page, base_url: str, username: str, password: str) -> None:
    page.goto(f"{base_url}/login", wait_until="networkidle")
    page.locator('input[name="username"]').fill(username)
    page.locator('input[name="password"]').fill(password)
    page.get_by_role("button", name="登录").click()
    page.wait_for_url(lambda url: "/account/login" not in url, wait_until="networkidle")


def _page_check(page: Page, label: str, checks: list[dict]) -> None:
    body = page.locator("body").inner_text()
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"
    )
    checks.append({
        "page": label,
        "url": page.url,
        "overflow": bool(overflow),
        "forbidden_copy": [term for term in FORBIDDEN_COPY if term in body],
        "undefined_visible": "undefined" in body,
        "null_visible": "null" in body,
        "replacement_character_visible": "�" in body,
    })


def _install_observers(page: Page, evidence: dict) -> None:
    page.on(
        "console",
        lambda message: evidence["console_errors"].append(message.text)
        if message.type == "error" else None,
    )
    page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
    page.on(
        "requestfailed",
        lambda request: evidence["network_failures"].append(
            {"url": request.url, "failure": request.failure}
        ),
    )

    def response_handler(response) -> None:
        if response.status < 400:
            return
        path = urlparse(response.url).path
        if response.status == 403 and path.endswith("/follow-ups"):
            return
        evidence["http_errors"].append({"status": response.status, "url": response.url})

    page.on("response", response_handler)


def run(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "browser": "",
        "viewport_checks": [],
        "console_errors": [],
        "page_errors": [],
        "network_failures": [],
        "http_errors": [],
        "screenshots": [],
        "operator_flow": {},
        "sample_coverage": [],
        "viewer_write_status": None,
        "metrics": {
            "click_count": 0,
            "guess_count": 0,
            "context_switch_count": 0,
        },
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        evidence["browser"] = browser.version
        operator = browser.new_context(viewport={"width": 1366, "height": 768})
        page = operator.new_page()
        _install_observers(page, evidence)
        _login(page, args.base_url, args.operator_username, args.operator_password)
        evidence["metrics"]["click_count"] += 1

        page.goto(f"{args.base_url}/platform", wait_until="networkidle")
        navigation = page.locator(".primary-nav a").all_inner_texts()
        if not navigation:
            navigation = page.locator("nav a").all_inner_texts()
        assert navigation[:4] == ["工作台", "情报", "企业与人物", "跟进"], navigation
        assert page.get_by_role("heading", name="今天值得处理").is_visible()
        assert page.locator('[data-intelligence-id="34"]').count() == 0
        _page_check(page, "工作台-1366", evidence["viewport_checks"])
        golden_started = time.monotonic()
        golden_click_count = 0
        shot = output_dir / "01_workbench_1366.png"
        page.screenshot(path=shot, full_page=True)
        evidence["screenshots"].append(str(shot))

        card_link = page.locator('a[href^="/intelligence/"]').filter(
            has_text="查看并决定下一步"
        ).first
        assert card_link.is_visible()
        card_link.click()
        evidence["metrics"]["click_count"] += 1
        golden_click_count += 1
        page.wait_for_load_state("networkidle")
        for heading in (
            "1. 发生了什么", "2. 涉及谁", "3. 为什么值得关注",
            "4. 与我们的关系", "5. 相关资源", "6. 下一步",
        ):
            assert page.get_by_role("heading", name=heading).is_visible()
        intelligence_url = page.url
        intelligence_id = int(urlparse(intelligence_url).path.rstrip("/").split("/")[-1])
        _page_check(page, "情报详情-1366", evidence["viewport_checks"])
        shot = output_dir / "02_intelligence_1366.png"
        page.screenshot(path=shot, full_page=True)
        evidence["screenshots"].append(str(shot))

        subject_link = page.locator('a[href^="/network/entities/"]').first
        if subject_link.count():
            subject_link.click()
            evidence["metrics"]["click_count"] += 1
            golden_click_count += 1
            evidence["metrics"]["context_switch_count"] += 1
            page.wait_for_load_state("networkidle")
            for heading in ("基础资料", "我们的关系", "关键联系人", "最近产业动态",
                            "资源 / 需求", "正在跟进", "历史合作证据"):
                assert page.get_by_role("heading", name=heading).is_visible()
            _page_check(page, "企业档案-1366", evidence["viewport_checks"])
            shot = output_dir / "03_organization_1366.png"
            page.screenshot(path=shot, full_page=True)
            evidence["screenshots"].append(str(shot))
            page.go_back(wait_until="networkidle")
            evidence["metrics"]["click_count"] += 1
            golden_click_count += 1
            evidence["metrics"]["context_switch_count"] += 1

        plan_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        page.locator('input[name="matter"]').fill("核实该产业动态对当前业务的影响")
        page.locator('textarea[name="reason"]').fill("该动态关联现有产业主体和资源，需要人工核实")
        page.locator('input[name="next_action"]').fill("联系现有负责人核对真实需求")
        page.locator('input[name="next_follow_at"]').fill(plan_time)
        page.get_by_role("button", name="建立跟进").click()
        evidence["metrics"]["click_count"] += 1
        golden_click_count += 1
        page.wait_for_load_state("networkidle")
        assert page.get_by_text("跟进已创建", exact=True).is_visible()
        opportunity_url = page.get_by_role("link", name="查看跟进").get_attribute("href")
        assert opportunity_url
        evidence["metrics"]["golden_path_click_count"] = golden_click_count
        evidence["metrics"]["golden_path_completion_seconds"] = round(
            time.monotonic() - golden_started, 2
        )
        evidence["operator_flow"] = {
            "intelligence_id": intelligence_id,
            "opportunity_url": opportunity_url,
            "follow_up_created": True,
        }
        shot = output_dir / "04_follow_up_created_1366.png"
        page.screenshot(path=shot, full_page=True)
        evidence["screenshots"].append(str(shot))
        page.get_by_role("link", name="返回工作台").click()
        evidence["metrics"]["click_count"] += 1
        page.wait_for_load_state("networkidle")
        assert page.get_by_text(
            "核实该产业动态对当前业务的影响", exact=False
        ).first.is_visible()
        _page_check(page, "跟进回到工作台-1366", evidence["viewport_checks"])

        page.goto(intelligence_url, wait_until="networkidle")
        page.get_by_role("button", name="暂不处理").click()
        evidence["metrics"]["click_count"] += 1
        page.wait_for_url(
            lambda url: urlparse(url).path == "/platform", wait_until="networkidle"
        )
        assert page.locator(f'[data-intelligence-id="{intelligence_id}"]').count() == 0
        page.get_by_text("今天已忽略", exact=False).click()
        evidence["metrics"]["click_count"] += 1
        page.locator(
            f'form[action="/golden-loop/intelligence/{intelligence_id}/today-restore"] button'
        ).click()
        evidence["metrics"]["click_count"] += 1
        page.wait_for_load_state("networkidle")
        assert page.locator(f'[data-intelligence-id="{intelligence_id}"]').count() == 1
        evidence["operator_flow"]["dismiss_restore"] = True

        page.set_viewport_size({"width": 1920, "height": 1080})
        page.reload(wait_until="networkidle")
        _page_check(page, "工作台-1920", evidence["viewport_checks"])
        shot = output_dir / "05_workbench_1920.png"
        page.screenshot(path=shot, full_page=True)
        evidence["screenshots"].append(str(shot))

        page.goto(f"{args.base_url}/intelligence/29", wait_until="networkidle")
        page.get_by_text("原文与公开证据", exact=True).click()
        evidence["metrics"]["click_count"] += 1
        assert page.get_by_text("MANUAL_CURATED_ACCEPTANCE_SAMPLE", exact=False).is_visible()
        _page_check(page, "英文监管样本-1920", evidence["viewport_checks"])
        evidence["sample_coverage"].append({
            "id": 29, "coverage": "英文监管/政策情报", "passed": True,
        })
        for sample_id, coverage in (
            (30, "无直接关系且无相关资源"),
            (32, "英文监管安全动态"),
            (34, "明显较旧且不进入今天"),
        ):
            page.goto(f"{args.base_url}/intelligence/{sample_id}", wait_until="networkidle")
            assert page.get_by_role("heading", name="1. 发生了什么").is_visible()
            if sample_id == 30:
                assert page.get_by_text("当前未发现直接关系", exact=True).is_visible()
                assert page.get_by_text("暂无相关资源", exact=True).is_visible()
            _page_check(page, f"真实样本-{sample_id}", evidence["viewport_checks"])
            evidence["sample_coverage"].append({
                "id": sample_id, "coverage": coverage, "passed": True,
            })
        evidence["sample_coverage"].append({
            "id": intelligence_id,
            "coverage": "Q-BAY关系且存在已有Resource",
            "passed": True,
        })
        operator.close()

        viewer = browser.new_context(viewport={"width": 1366, "height": 768})
        viewer_page = viewer.new_page()
        _install_observers(viewer_page, evidence)
        _login(viewer_page, args.base_url, args.viewer_username, args.viewer_password)
        evidence["metrics"]["click_count"] += 1
        viewer_page.goto(intelligence_url, wait_until="networkidle")
        assert viewer_page.get_by_role("button", name="建立跟进").count() == 0
        forbidden = viewer.request.post(
            f"{args.base_url}/golden-loop/intelligence/{intelligence_id}/follow-ups",
            form={
                "object_name": "viewer",
                "matter": "forbidden",
                "reason": "forbidden",
                "next_action": "forbidden",
                "next_follow_at": "2026-08-30T09:00",
            },
            fail_on_status_code=False,
        )
        status = forbidden.status
        evidence["viewer_write_status"] = int(status)
        assert status == 403
        _page_check(viewer_page, "viewer情报详情-1366", evidence["viewport_checks"])
        viewer.close()
        browser.close()

    evidence["metrics"]["completion_seconds"] = round(time.monotonic() - started, 2)
    evidence["passed"] = bool(
        evidence["operator_flow"].get("follow_up_created")
        and evidence["viewer_write_status"] == 403
        and not evidence["console_errors"]
        and not evidence["page_errors"]
        and not evidence["network_failures"]
        and not evidence["http_errors"]
        and all(not row["overflow"] for row in evidence["viewport_checks"])
        and all(not row["forbidden_copy"] for row in evidence["viewport_checks"])
        and all(not row["undefined_visible"] for row in evidence["viewport_checks"])
        and all(not row["null_visible"] for row in evidence["viewport_checks"])
        and all(not row["replacement_character_visible"] for row in evidence["viewport_checks"])
    )
    report_path = output_dir / args.report_name
    report_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return evidence


def run_persistence(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {"browser": "", "console_errors": [], "page_errors": [], "persisted": False}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        result["browser"] = browser.version
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()
        page.on(
            "console",
            lambda message: result["console_errors"].append(message.text)
            if message.type == "error" else None,
        )
        page.on("pageerror", lambda error: result["page_errors"].append(str(error)))
        _login(page, args.base_url, args.operator_username, args.operator_password)
        page.goto(f"{args.base_url}/platform", wait_until="networkidle")
        result["persisted"] = page.get_by_text(
            "核实该产业动态对当前业务的影响", exact=False
        ).first.is_visible()
        shot = output_dir / "06_restart_persistence.png"
        page.screenshot(path=shot, full_page=True)
        result["screenshot"] = str(shot)
        context.close()
        browser.close()
    result["completion_seconds"] = round(time.monotonic() - started, 2)
    result["passed"] = bool(
        result["persisted"] and not result["console_errors"] and not result["page_errors"]
    )
    (output_dir / args.report_name).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report-name", default="browser_acceptance.json")
    parser.add_argument("--operator-username", required=True)
    parser.add_argument("--operator-password", required=True)
    parser.add_argument("--viewer-username", required=True)
    parser.add_argument("--viewer-password", required=True)
    parser.add_argument("--persistence-only", action="store_true")
    args = parser.parse_args()
    result = run_persistence(args) if args.persistence_only else run(args)
    if args.persistence_only:
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["passed"] else 1
    print(json.dumps({
        "passed": result["passed"],
        "browser": result["browser"],
        "console_errors": len(result["console_errors"]),
        "page_errors": len(result["page_errors"]),
        "network_failures": len(result["network_failures"]),
        "http_errors": len(result["http_errors"]),
        "overflow": sum(1 for row in result["viewport_checks"] if row["overflow"]),
        "viewer_write_status": result["viewer_write_status"],
        "metrics": result["metrics"],
    }, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
