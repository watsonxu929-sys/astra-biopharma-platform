@echo off
setlocal
cd /d "%~dp0"
echo Running v0.5G verification...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\verify_v05g.py
) else (
  python scripts\verify_v05g.py
)
if errorlevel 1 (
  echo.
  echo Verification failed.
  pause
  exit /b 1
)
echo.
echo Verification completed.
pause
