@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
echo [v0.5D] verify started > logs\verify_v05d_windows.log
python scripts\verify_v05d.py >> logs\verify_v05d_windows.log 2>&1
if errorlevel 1 (
  echo.
  echo v0.5D verification failed. See logs\verify_v05d_windows.log
  type logs\verify_v05d_windows.log
  pause
  exit /b 1
)
echo v0.5D verification completed.
type logs\verify_v05d_windows.log
pause
