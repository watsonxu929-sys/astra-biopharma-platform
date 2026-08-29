from __future__ import annotations

import importlib.util
import socket
from pathlib import Path

from app.services.ai.openai_provider import OpenAIProvider
from app.services.golden_loop_service import GoldenLoopService


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = ROOT / "scripts" / "windows" / "run_web_launcher.py"
SPEC = importlib.util.spec_from_file_location("rc1_run_launcher", LAUNCHER_PATH)
assert SPEC and SPEC.loader
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


def test_run_project_root_and_python_resolution() -> None:
    assert launcher.PROJECT_ROOT == ROOT
    assert launcher.PYTHON_EXE == ROOT / ".venv" / "Scripts" / "python.exe"
    assert launcher.PYTHON_EXE.is_file()


def test_run_database_preflight_is_read_only(temp_database: Path) -> None:
    before = temp_database.read_bytes()
    launcher.check_database(temp_database)
    assert temp_database.read_bytes() == before


def test_run_port_conflict_probe_detects_bound_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = int(server.getsockname()[1])
        assert launcher.port_is_bound("127.0.0.1", port) is True
        assert launcher.same_project_health("127.0.0.1", port) is False


def test_run_stale_pid_command_is_not_project_web() -> None:
    assert launcher.is_project_web_command(
        r"E:\\repo\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000"
    )
    assert not launcher.is_project_web_command(
        r"C:\\Program Files\\Vendor\\unrelated.exe"
    )


def test_run_secret_redaction() -> None:
    value = launcher.redact(
        "api_key=redaction-sample Bearer sample-token password=sample-password"
    )
    assert "redaction-sample" not in value
    assert "sample-token" not in value
    assert "sample-password" not in value


def test_run_batch_pauses_only_on_failure() -> None:
    batch = (ROOT / "run_windows.bat").read_text(encoding="utf-8")
    assert "if /i not \"%RC1_RUN_NONINTERACTIVE%\"==\"true\" pause" in batch
    success_part = batch.split(":failed", 1)[0].lower()
    assert " pause" not in success_part
    assert "timeout /t 5" in success_part


def test_translation_preflight_has_no_available_paid_provider(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert OpenAIProvider().available is False


def test_translation_language_detection_skip_and_failure_fallback() -> None:
    service = GoldenLoopService(None)
    chinese = service.reading_view(
        1, {"title": "中文产业动态", "summary": "这是已存在的中文摘要。"}
    )
    assert chinese["translation_mode"] == "ORIGINAL_CHINESE"
    english = service.reading_view(
        2,
        {
            "title": "Previously unseen regulatory intelligence",
            "summary": "Original English evidence remains available.",
            "source_url": "https://example.invalid/evidence",
        },
    )
    assert english["translation_mode"] == "MANUAL_ACCEPTANCE_FALLBACK"
    assert english["has_chinese_reading"] is False
    assert english["display_title"] == "英文产业动态（自动中文加工尚未配置）"
    assert english["display_summary"] == "自动中文加工尚未配置，可查看英文原文与公开证据。"
    assert english["original_title"] == "Previously unseen regulatory intelligence"
    assert english["original_summary"] == "Original English evidence remains available."
