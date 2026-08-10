@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo Biopharma Intelligence MVP-RC1 - Web only
echo ============================================
call start_web_windows.bat
if errorlevel 1 exit /b 1
call status_windows.bat
echo.
echo Scheduler and Worker are disabled for the Web process.
echo Use start_scheduler_windows.bat or start_worker_windows.bat explicitly when required.
