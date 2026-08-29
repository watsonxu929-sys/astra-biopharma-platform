@echo off
setlocal
chcp 65001 >nul
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"
if not exist "runtime" mkdir "runtime"
if not exist "logs" mkdir "logs"

set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
set SCHEDULER_ENABLED=false
set WORKER_ENABLED=false
if not exist "%PYTHON_EXE%" (
  >>"logs\startup.log" echo %DATE% %TIME% stage=python error=PYTHON_NOT_FOUND exit_code=10 project_root="%PROJECT_ROOT%"
  echo Startup failed
  echo Reason: Project Python environment was not found.
  echo Action: Run scripts\windows\setup_windows.bat first.
  echo Log: logs\startup.log
  exit /b 10
)

"%PYTHON_EXE%" "%PROJECT_ROOT%\scripts\windows\run_web_launcher.py" start
exit /b %ERRORLEVEL%
