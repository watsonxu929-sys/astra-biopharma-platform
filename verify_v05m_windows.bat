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
echo Running productization verification...
%PY% scripts\verify_v05m.py
if errorlevel 1 (
  echo.
  echo Productization verification failed.
  pause
  exit /b 1
)
echo.
echo Productization verification completed.
pause
