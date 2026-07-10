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
echo [v0.5F] migrate started > logs\migrate_v05f_windows.log
%PY% scripts\migrate_v05f.py >> logs\migrate_v05f_windows.log 2>&1
if errorlevel 1 (
  echo.
  echo v0.5F migration failed. See logs\migrate_v05f_windows.log
  type logs\migrate_v05f_windows.log
  pause
  exit /b 1
)
echo v0.5F migration completed.
type logs\migrate_v05f_windows.log
pause
