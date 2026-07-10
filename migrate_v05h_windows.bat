@echo off
setlocal
cd /d "%~dp0"
echo Running v0.5H migration...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\migrate_v05h.py
) else (
  python scripts\migrate_v05h.py
)
if errorlevel 1 pause & exit /b 1
pause
