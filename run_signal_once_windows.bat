@echo off
setlocal
cd /d "%~dp0"
echo Running signal worker once...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\run_signal_worker.py --once --limit 100 --confirm
) else (
  python scripts\run_signal_worker.py --once --limit 100 --confirm
)
if errorlevel 1 pause & exit /b 1
pause
