@echo off
setlocal
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"
call scripts\windows\start_web_windows.bat
call scripts\windows\start_worker_windows.bat
call scripts\windows\start_scheduler_windows.bat
call scripts\windows\status_windows.bat
