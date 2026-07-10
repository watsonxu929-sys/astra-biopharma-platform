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
echo [v0.5E] migrate started > logs\migrate_v05e_windows.log
%PY% scripts\migrate_v05e.py >> logs\migrate_v05e_windows.log 2>&1
if errorlevel 1 (
  echo.
  echo v0.5E migration failed. See logs\migrate_v05e_windows.log
  type logs\migrate_v05e_windows.log
  pause
  exit /b 1
)
echo v0.5E migration completed.
type logs\migrate_v05e_windows.log
pause
