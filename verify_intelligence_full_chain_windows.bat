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
echo Running intelligence full-chain verification...
%PY% scripts\verify_intelligence_full_chain.py
if errorlevel 1 (
  echo.
  echo Intelligence full-chain verification failed.
  pause
  exit /b 1
)
echo.
echo Intelligence full-chain verification completed.
pause
