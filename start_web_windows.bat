@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not exist runtime mkdir runtime
if not exist logs mkdir logs

set APP_ENV=development
set APP_HOST=127.0.0.1
set APP_PORT=8000
set APP_RELOAD=false
set APP_OPEN_BROWSER=false
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="APP_ENV" set APP_ENV=%%B
    if /i "%%A"=="APP_HOST" set APP_HOST=%%B
    if /i "%%A"=="APP_PORT" set APP_PORT=%%B
    if /i "%%A"=="APP_RELOAD" set APP_RELOAD=%%B
    if /i "%%A"=="APP_OPEN_BROWSER" set APP_OPEN_BROWSER=%%B
  )
)

rem Web only: collection scheduler and task worker are separate processes.
set SCHEDULER_ENABLED=false
set WORKER_ENABLED=false

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Run setup_windows.bat first.
  exit /b 1
)
if exist "runtime\web.pid" (
  set /p OLD_PID=<"runtime\web.pid"
  tasklist /FI "PID eq !OLD_PID!" 2>NUL | findstr /R /C:" !OLD_PID! " >NUL
  if not errorlevel 1 (
    echo Web is already running. PID !OLD_PID!
    exit /b 1
  )
  del /q "runtime\web.pid"
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":!APP_PORT! .*LISTENING"') do set PORT_PID=%%P
if defined PORT_PID (
  echo ERROR: Port !APP_PORT! is already used by PID !PORT_PID!.
  exit /b 1
)

if /i "!APP_RELOAD!"=="true" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList @('-m','uvicorn','app.main:app','--host','!APP_HOST!','--port','!APP_PORT!','--reload') -WorkingDirectory '%CD%' -WindowStyle Hidden -RedirectStandardOutput 'logs\web_stdout.log' -RedirectStandardError 'logs\web_stderr.log' -PassThru; $p.Id | Set-Content -Encoding ASCII 'runtime\web.pid'"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList @('-m','uvicorn','app.main:app','--host','!APP_HOST!','--port','!APP_PORT!') -WorkingDirectory '%CD%' -WindowStyle Hidden -RedirectStandardOutput 'logs\web_stdout.log' -RedirectStandardError 'logs\web_stderr.log' -PassThru; $p.Id | Set-Content -Encoding ASCII 'runtime\web.pid'"
)
if errorlevel 1 exit /b 1
echo Web started: http://!APP_HOST!:!APP_PORT!/  reload=!APP_RELOAD! scheduler=false worker=false
if /i "!APP_OPEN_BROWSER!"=="true" start "" http://!APP_HOST!:!APP_PORT!/
