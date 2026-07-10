@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set LOG=logs\migrate_all_latest.log
if exist ".venv\Scripts\python.exe" (
  set PY=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
  set PY=venv\Scripts\python.exe
) else (
  set PY=python
)
echo Running safe migrations...
%PY% scripts\migrate_all.py
if errorlevel 1 (
  echo.
  echo Migration failed. See %LOG%
  pause
  exit /b 1
)
echo.
echo Migration completed. See %LOG%
pause
