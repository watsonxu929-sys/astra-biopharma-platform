@echo off
setlocal
cd /d "%~dp0"
echo Starting v0.5G processing worker loop. Press Ctrl+C to stop.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\run_processing_worker.py --queued-only --limit 20 --sleep 30
) else (
  python scripts\run_processing_worker.py --queued-only --limit 20 --sleep 30
)
pause
