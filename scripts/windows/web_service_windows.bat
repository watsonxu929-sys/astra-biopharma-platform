@echo off
setlocal
chcp 65001 >nul
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PYTHON_EXE%" (
  echo Project Python environment was not found. Run setup_windows.bat first.
  exit /b 10
)
if /i "%~1"=="start" (
  call scripts\windows\start_web_windows.bat
  exit /b %ERRORLEVEL%
)
if /i "%~1"=="stop" (
  "%PYTHON_EXE%" "%PROJECT_ROOT%\scripts\windows\run_web_launcher.py" stop
  exit /b %ERRORLEVEL%
)
if /i "%~1"=="status" (
  "%PYTHON_EXE%" "%PROJECT_ROOT%\scripts\windows\run_web_launcher.py" status
  exit /b %ERRORLEVEL%
)
echo Usage: web_service_windows.bat start^|stop^|status
exit /b 2
