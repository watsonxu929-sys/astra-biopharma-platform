from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
PID_FILE = PROJECT_ROOT / "runtime" / "web.pid"
STARTUP_LOG = PROJECT_ROOT / "logs" / "startup.log"
WEB_STDOUT = PROJECT_ROOT / "logs" / "web_stdout.log"
WEB_STDERR = PROJECT_ROOT / "logs" / "web_stderr.log"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def redact(value: object) -> str:
    text = str(value or "")
    text = re.sub(
        r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+",
        r"\1=***",
        text,
    )
    text = re.sub(r"(?i)bearer\s+\S+", "Bearer ***", text)
    return text[:500]


def log_event(stage: str, *, error: str = "", exit_code: int = 0, detail: str = "") -> None:
    STARTUP_LOG.parent.mkdir(parents=True, exist_ok=True)
    fields = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "python": str(PYTHON_EXE),
        "project_root": str(PROJECT_ROOT),
        "stage": stage,
        "error": redact(error) or "none",
        "exit_code": int(exit_code),
        "detail": redact(detail) or "none",
    }
    with STARTUP_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(fields, ensure_ascii=False) + "\n")


def _env_file_values() -> dict[str, str]:
    path = PROJECT_ROOT / ".env"
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"APP_HOST", "APP_PORT", "APP_RELOAD", "APP_OPEN_BROWSER"}:
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def setting(name: str, default: str) -> str:
    return os.environ.get(name, _env_file_values().get(name, default)).strip() or default


def resolved_port() -> int:
    try:
        port = int(setting("APP_PORT", str(DEFAULT_PORT)))
    except ValueError as exc:
        raise ValueError("APP_PORT_INVALID") from exc
    if not 1 <= port <= 65535:
        raise ValueError("APP_PORT_INVALID")
    return port


def resolved_host() -> str:
    host = setting("APP_HOST", DEFAULT_HOST)
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("APP_HOST_MUST_BE_LOCAL")
    return "127.0.0.1" if host == "localhost" else host


def resolve_database_path() -> Path:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from app.settings import get_settings

    return get_settings().app_db_path.resolve()


def check_database(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError("DATABASE_NOT_FOUND")
    uri = f"file:{path.as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            connection.execute("PRAGMA query_only=ON")
            result = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise RuntimeError("DATABASE_UNAVAILABLE") from exc
    if not result or result[0] != "ok":
        raise RuntimeError("DATABASE_INTEGRITY_FAILED")


def port_is_bound(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def _http_status(url: str, timeout: float = 1.5) -> tuple[int, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            return int(response.status), response.read(300).decode("utf-8", errors="replace")
    except HTTPError as exc:
        return int(exc.code), exc.read(300).decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError):
        return 0, ""


def same_project_health(host: str, port: int) -> bool:
    status, body = _http_status(f"http://{host}:{port}/health")
    if status != 200:
        return False
    try:
        return json.loads(body).get("status") == "ok"
    except (json.JSONDecodeError, AttributeError):
        return False


def full_health(host: str, port: int) -> bool:
    if not same_project_health(host, port):
        return False
    login_status, _ = _http_status(f"http://{host}:{port}/login")
    platform_status, _ = _http_status(f"http://{host}:{port}/platform")
    return 200 <= login_status < 400 and 200 <= platform_status < 400


def read_pid() -> int | None:
    try:
        value = PID_FILE.read_text(encoding="ascii").strip()
        return int(value) if value.isdigit() else None
    except OSError:
        return None


def process_command(pid: int) -> str:
    powershell = shutil.which("powershell.exe")
    if not powershell:
        return ""
    command = (
        f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\" "
        "-ErrorAction SilentlyContinue; if($p){$p.CommandLine}"
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    )
    return completed.stdout.strip()


def is_project_web_command(command: str) -> bool:
    normalized = command.lower().replace("\\", "/")
    return "uvicorn" in normalized and "app.main:app" in normalized


def clear_stale_pid() -> None:
    if not PID_FILE.exists():
        return
    pid = read_pid()
    command = process_command(pid) if pid else ""
    if not pid or not is_project_web_command(command):
        PID_FILE.unlink(missing_ok=True)
        log_event("pid_cleanup", detail="stale_or_reused_pid_removed")


def stop_process(pid: int) -> bool:
    command = process_command(pid)
    if not is_project_web_command(command):
        return False
    completed = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )
    return completed.returncode == 0


def failure(code: int, reason: str, advice: str, *, detail: str = "") -> int:
    log_event("failed", error=reason, exit_code=code, detail=detail)
    print("----------------------------------------")
    print("启动失败")
    print(f"原因：{reason}")
    print(f"建议：{advice}")
    print("日志：logs\\startup.log")
    print("----------------------------------------")
    return code


def start() -> int:
    os.chdir(PROJECT_ROOT)
    (PROJECT_ROOT / "runtime").mkdir(exist_ok=True)
    (PROJECT_ROOT / "logs").mkdir(exist_ok=True)
    log_event("preflight")
    if Path(sys.executable).resolve() != PYTHON_EXE.resolve():
        return failure(10, "PYTHON_INTERPRETER_MISMATCH", "请使用项目 RUN 入口启动。")
    try:
        host = resolved_host()
        port = resolved_port()
        database_path = resolve_database_path()
        check_database(database_path)
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
    except (ValueError, FileNotFoundError, RuntimeError, ImportError) as exc:
        reason = str(exc) or type(exc).__name__
        return failure(12, reason, "检查 .env、项目 Python 环境和数据库文件。")

    print("环境：OK")
    print("数据库：OK")
    clear_stale_pid()
    if port_is_bound(host, port):
        if full_health(host, port):
            print("Web服务：RUNNING（系统已经在运行）")
            print(f"地址：http://{host}:{port}")
            log_event("already_running", detail=f"port={port}")
            return 0
        return failure(
            13,
            "PORT_IN_USE_BY_OTHER_PROCESS",
            f"关闭占用端口 {port} 的其他程序后重新运行。",
            detail=f"port={port}",
        )

    old_pid = read_pid()
    if old_pid and is_project_web_command(process_command(old_pid)):
        return failure(
            16,
            "STALE_PROJECT_PROCESS",
            "先运行 scripts\\windows\\web_service_windows.bat stop，再重新启动。",
        )
    PID_FILE.unlink(missing_ok=True)

    env = os.environ.copy()
    env.update({
        "APP_HOST": host,
        "APP_PORT": str(port),
        "SCHEDULER_ENABLED": "false",
        "WORKER_ENABLED": "false",
        "PYTHONUTF8": "1",
    })
    arguments = [
        str(PYTHON_EXE), "-m", "uvicorn", "app.main:app",
        "--host", host, "--port", str(port),
    ]
    if setting("APP_RELOAD", "false").lower() in {"1", "true", "yes", "on"}:
        arguments.append("--reload")
    creation_flags = (
        subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NO_WINDOW
    )
    with WEB_STDOUT.open("a", encoding="utf-8") as stdout, WEB_STDERR.open(
        "a", encoding="utf-8"
    ) as stderr:
        try:
            process = subprocess.Popen(
                arguments,
                cwd=PROJECT_ROOT,
                env=env,
                stdout=stdout,
                stderr=stderr,
                creationflags=creation_flags,
            )
        except OSError as exc:
            return failure(
                14, "UVICORN_START_FAILED", "检查项目 Python 环境和日志。",
                detail=type(exc).__name__,
            )
    PID_FILE.write_text(str(process.pid), encoding="ascii")
    log_event("process_started", detail=f"pid={process.pid};port={port}")

    try:
        timeout = int(setting("RC1_STARTUP_TIMEOUT", "20"))
    except ValueError:
        timeout = 20
    timeout = max(15, min(timeout, 30))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            PID_FILE.unlink(missing_ok=True)
            return failure(
                14,
                "UVICORN_EXITED",
                "查看 logs\\web_stderr.log 修复启动错误。",
                detail=f"exit_code={process.returncode}",
            )
        if full_health(host, port):
            print("Web服务：RUNNING")
            print(f"地址：http://{host}:{port}")
            print("RUN_STATUS=READY")
            log_event("ready", detail=f"pid={process.pid};port={port}")
            if setting("APP_OPEN_BROWSER", "false").lower() in {"1", "true", "yes", "on"}:
                os.startfile(f"http://{host}:{port}/login")  # type: ignore[attr-defined]
            return 0
        time.sleep(0.4)

    stop_process(process.pid)
    PID_FILE.unlink(missing_ok=True)
    return failure(
        15,
        "STARTUP_TIMEOUT",
        f"服务未在 {timeout} 秒内就绪，请查看 Web 错误日志。",
    )


def stop() -> int:
    pid = read_pid()
    if not pid:
        PID_FILE.unlink(missing_ok=True)
        print("Web服务：STOPPED")
        return 0
    if not is_project_web_command(process_command(pid)):
        PID_FILE.unlink(missing_ok=True)
        print("Web服务：STOPPED（已清理失效 PID）")
        log_event("pid_cleanup", detail="stop_removed_stale_pid")
        return 0
    if not stop_process(pid):
        return failure(16, "STOP_FAILED", "检查进程权限后重试。")
    PID_FILE.unlink(missing_ok=True)
    log_event("stopped", detail=f"pid={pid}")
    print("Web服务：STOPPED")
    return 0


def status() -> int:
    try:
        host, port = resolved_host(), resolved_port()
    except ValueError as exc:
        print(f"Web服务：FAILED（{exc}）")
        return 12
    if full_health(host, port):
        print(f"Web服务：RUNNING http://{host}:{port}")
        return 0
    clear_stale_pid()
    print("Web服务：STOPPED")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "stop", "status"), nargs="?", default="start")
    args = parser.parse_args()
    return {"start": start, "stop": stop, "status": status}[args.action]()


if __name__ == "__main__":
    raise SystemExit(main())
