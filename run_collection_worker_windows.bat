@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
if exist ".venv\Scripts\python.exe" (
  set PY=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
  set PY=venv\Scripts\python.exe
) else (
  set PY=python
)
echo [v0.5F] collection worker started > logs\collection_worker_latest.log
%PY% scripts\run_collection_worker.py --limit 20 >> logs\collection_worker_latest.log 2>&1
if errorlevel 1 (
  echo.
  echo Collection worker failed. See logs\collection_worker_latest.log
  type logs\collection_worker_latest.log
  pause
  exit /b 1
)
echo Collection worker completed.
type logs\collection_worker_latest.log
pause
