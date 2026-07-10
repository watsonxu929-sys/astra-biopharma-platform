@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set LOG=logs\migrate_v05c_latest.log
if exist ".venv\Scripts\python.exe" (
  set PY=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
  set PY=venv\Scripts\python.exe
) else (
  set PY=python
)
echo Running v0.5C migration...
%PY% scripts\migrate_v05c.py > "%LOG%" 2>&1
if errorlevel 1 (
  type "%LOG%"
  echo.
  echo v0.5C migration failed. See %LOG%
  pause
  exit /b 1
)
type "%LOG%"
echo.
echo v0.5C migration completed. See %LOG%
pause
