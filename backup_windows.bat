@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set LOG=logs\backup_latest.log
if exist ".venv\Scripts\python.exe" (
  set PY=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
  set PY=venv\Scripts\python.exe
) else (
  set PY=python
)
%PY% scripts\backup_database.py > "%LOG%" 2>&1
if errorlevel 1 (
  type "%LOG%"
  echo.
  echo Backup failed. See %LOG%
  pause
  exit /b 1
)
type "%LOG%"
pause
