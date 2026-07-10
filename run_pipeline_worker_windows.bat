@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" scripts\run_pipeline_worker.py --due-only --limit 10 --pilot
pause
