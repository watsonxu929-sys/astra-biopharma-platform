@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set LOG=logs\verify_v05c_latest.log
if exist ".venv\Scripts\python.exe" (
  set PY=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
  set PY=venv\Scripts\python.exe
) else (
  set PY=python
)
echo Running v0.5C verification...
%PY% scripts\verify_v05c.py > "%LOG%" 2>&1
if errorlevel 1 (
  type "%LOG%"
  echo.
  echo v0.5C verification failed. See %LOG%
  pause
  exit /b 1
)
type "%LOG%"
echo.
echo v0.5C verification completed. See %LOG%
pause
