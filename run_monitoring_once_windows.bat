@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set LOG=logs\run_monitoring_once_%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.log
set LOG=%LOG: =0%
if exist .venv\Scripts\python.exe (
  set PY=.venv\Scripts\python.exe
) else (
  set PY=python
)
echo Running monitoring once... > "%LOG%"
%PY% scripts\run_monitoring_once.py %* >> "%LOG%" 2>&1
if errorlevel 1 (
  type "%LOG%"
  echo.
  echo Monitoring run failed. See %LOG%
  pause
  exit /b 1
)
type "%LOG%"
echo.
echo Monitoring run completed.
pause
