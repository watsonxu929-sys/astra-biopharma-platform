@echo off
setlocal
cd /d "%~dp0"
echo Running daily report worker once...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\run_report_worker.py --daily
) else (
  python scripts\run_report_worker.py --daily
)
if errorlevel 1 pause & exit /b 1
pause
