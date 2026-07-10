@echo off
setlocal
cd /d "%~dp0\..\..\..\.."
if not exist logs mkdir logs
if exist ".venv\Scripts\python.exe" (set PY=.venv\Scripts\python.exe) else if exist "venv\Scripts\python.exe" (set PY=venv\Scripts\python.exe) else (set PY=python)
%PY% scripts\verify_v04h.py > logs\verify_v04h_latest.log 2>&1
type logs\verify_v04h_latest.log
if errorlevel 1 (echo Verification failed.& pause & exit /b 1)
echo v0.4H verification completed.
pause
