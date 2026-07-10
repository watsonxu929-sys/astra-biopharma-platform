@echo off
setlocal
cd /d "%~dp0"
echo Running v0.5G processing worker once...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\run_processing_worker.py --once --queued-only --limit 20
) else (
  python scripts\run_processing_worker.py --once --queued-only --limit 20
)
if errorlevel 1 (
  echo.
  echo Processing worker failed.
  pause
  exit /b 1
)
echo.
echo Processing worker completed.
pause
