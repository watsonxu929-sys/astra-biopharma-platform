@echo off
setlocal
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"
if not exist runtime mkdir runtime
if not exist logs mkdir logs
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 setup_windows.bat
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList @('scripts\run_scheduler.py','--sleep','30') -WorkingDirectory '%CD%' -WindowStyle Hidden -PassThru; $p.Id | Set-Content -Encoding ASCII 'runtime\scheduler.pid'"
echo 调度器已启动。
