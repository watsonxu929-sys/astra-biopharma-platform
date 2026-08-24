@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo Biopharma Intelligence MVP-RC1 - Web only
echo ============================================
call scripts\windows\start_web_windows.bat
if errorlevel 1 exit /b 1
call scripts\windows\status_windows.bat
echo.
echo Scheduler and Worker are disabled for the Web process.
echo Use scripts\windows\start_scheduler_windows.bat or scripts\windows\start_worker_windows.bat when required.
