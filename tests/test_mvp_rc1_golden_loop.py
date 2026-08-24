from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mvp_rc1_three_golden_cases_are_persistent_idempotent_and_cleaned(
    temp_database: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "verify_mvp_rc1_golden_loop.py"),
            "--database",
            str(temp_database),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    report = json.loads(result.stdout)
    assert report["case_a"]["outcome"] == "won"
    assert report["case_a"]["relationship_id"]
    assert report["case_b"]["outcome"] == "lost"
    assert report["case_b"]["relationship_id"] is None
    assert report["case_c"]["outcome"] == "paused"
    assert report["case_c"]["relationship_id"] is None
    assert report["viewer_write_status"] == 403
    assert report["operator_write_allowed"] is True
    assert report["restart_persistence"] is True
    assert report["cleanup"] == "complete"
    assert report["marker_residue"] == 0
    assert report["foreign_key_state"]["unchanged"] is True
    assert report["integrity"] == "ok"


def test_rc1_web_runtime_defaults_are_safe() -> None:
    config = (ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
    start_web = (ROOT / "scripts" / "windows" / "start_web_windows.bat").read_text(encoding="utf-8")
    assert 'app_reload: bool = False' in config
    assert 'scheduler_enabled: bool = False' in config
    assert 'worker_enabled: bool = False' in config
    assert "set SCHEDULER_ENABLED=false" in start_web
    assert "set WORKER_ENABLED=false" in start_web
    assert "--reload" not in start_web.split("if /i \"!APP_RELOAD!\"==\"true\"")[0]


def test_rc1_lifecycle_entrypoints_are_explicit() -> None:
    web = (ROOT / "scripts" / "windows" / "web_service_windows.bat").read_text(encoding="utf-8")
    scheduler = (ROOT / "scripts" / "windows" / "start_scheduler_windows.bat").read_text(encoding="utf-8")
    worker = (ROOT / "scripts" / "windows" / "start_worker_windows.bat").read_text(encoding="utf-8")
    for action in ("start", "stop", "status"):
        assert f'if /i "%~1"=="{action}"' in web
    assert "scripts\\run_scheduler.py" in scheduler
    assert "--sleep" not in scheduler
    assert "scripts\\run_worker.py" in worker
