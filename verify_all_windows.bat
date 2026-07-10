@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set LOG=logs\verify_all_latest.log
if exist ".venv\Scripts\python.exe" (
  set PY=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
  set PY=venv\Scripts\python.exe
) else (
  set PY=python
)
echo Running complete verification...
%PY% scripts\verify_all.py
if errorlevel 1 (
  echo.
  echo Verification failed. See %LOG%
  pause
  exit /b 1
)
echo.
echo Verification completed. See %LOG%
pause
