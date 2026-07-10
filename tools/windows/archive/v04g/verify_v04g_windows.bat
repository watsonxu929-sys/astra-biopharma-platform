@echo off
setlocal
cd /d "%~dp0..\..\..\.."
if not exist logs mkdir logs
set LOG=logs\verify_v04g_%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.log
set LOG=%LOG: =0%
if exist .venv\Scripts\python.exe (
  set PY=.venv\Scripts\python.exe
) else (
  set PY=python
)
echo Running v0.4G verification... > "%LOG%"
%PY% scripts\verify_v04g.py >> "%LOG%" 2>&1
if errorlevel 1 (
  type "%LOG%"
  echo.
  echo v0.4G verification failed. See %LOG%
  pause
  exit /b 1
)
type "%LOG%"
echo.
echo v0.4G verification completed.
pause
