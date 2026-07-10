@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
echo [v0.5D] migrate started > logs\migrate_v05d_windows.log
python scripts\migrate_v05d.py >> logs\migrate_v05d_windows.log 2>&1
if errorlevel 1 (
  echo.
  echo v0.5D migration failed. See logs\migrate_v05d_windows.log
  type logs\migrate_v05d_windows.log
  pause
  exit /b 1
)
echo v0.5D migration completed.
type logs\migrate_v05d_windows.log
pause
