@echo off
setlocal
cd /d "%~dp0"
if not exist runtime mkdir runtime
if not exist logs mkdir logs
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 setup_windows.bat
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList @('scripts\run_worker.py','--sleep','5') -WorkingDirectory '%CD%' -WindowStyle Hidden -PassThru; $p.Id | Set-Content -Encoding ASCII 'runtime\worker.pid'"
echo 后台任务 Worker 已启动。
