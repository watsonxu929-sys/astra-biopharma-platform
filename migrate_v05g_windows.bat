@echo off
setlocal
cd /d "%~dp0"
echo Running v0.5G migration...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\migrate_v05g.py
) else (
  python scripts\migrate_v05g.py
)
if errorlevel 1 (
  echo.
  echo Migration failed.
  pause
  exit /b 1
)
echo.
echo Migration completed.
pause
