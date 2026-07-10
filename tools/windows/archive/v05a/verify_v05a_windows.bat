@echo off
setlocal
cd /d "%~dp0\..\..\..\.."
if not exist logs mkdir logs
if exist ".venv\Scripts\python.exe" (set PY=.venv\Scripts\python.exe) else if exist "venv\Scripts\python.exe" (set PY=venv\Scripts\python.exe) else (set PY=python)
%PY% scripts\verify_v05a.py > logs\verify_v05a_latest.log 2>&1
set RC=%ERRORLEVEL%
type logs\verify_v05a_latest.log
if not "%RC%"=="0" (echo Verification failed.& pause & exit /b %RC%)
echo v0.5A verification completed.
pause
