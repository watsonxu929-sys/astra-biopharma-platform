@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not exist logs mkdir logs
set LOG=logs\run_windows_latest.log
set APP_HOST=127.0.0.1
set APP_PORT=8000
set APP_RELOAD=true
set APP_OPEN_BROWSER=true
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="APP_HOST" set APP_HOST=%%B
    if /i "%%A"=="APP_PORT" set APP_PORT=%%B
    if /i "%%A"=="APP_RELOAD" set APP_RELOAD=%%B
    if /i "%%A"=="APP_OPEN_BROWSER" set APP_OPEN_BROWSER=%%B
  )
)
echo Host=!APP_HOST! Port=!APP_PORT! > "%LOG%"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Run setup_windows.bat first.
  echo ERROR: Run setup_windows.bat first. >> "%LOG%"
  pause
  exit /b 1
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":!APP_PORT! .*LISTENING"') do set PORT_PID=%%P
if defined PORT_PID (
  echo Port !APP_PORT! is already in use by PID !PORT_PID!.
  echo Port !APP_PORT! is already in use by PID !PORT_PID!. >> "%LOG%"
  echo If this is the current project, open http://!APP_HOST!:!APP_PORT!/ in your browser.
  pause
  exit /b 1
)
if /i "!APP_OPEN_BROWSER!"=="true" start "" http://!APP_HOST!:!APP_PORT!/
set RELOAD_ARG=
if /i "!APP_RELOAD!"=="true" set RELOAD_ARG=--reload
".venv\Scripts\python.exe" -m uvicorn app.main:app !RELOAD_ARG! --host !APP_HOST! --port !APP_PORT! >> "%LOG%" 2>&1
pause
