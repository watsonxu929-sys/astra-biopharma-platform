@echo off
setlocal
cd /d "%~dp0"
call start_web_windows.bat
call start_worker_windows.bat
call start_scheduler_windows.bat
call status_windows.bat
