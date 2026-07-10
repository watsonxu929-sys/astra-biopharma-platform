@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not exist runtime mkdir runtime
if not exist logs mkdir logs

set APP_ENV=development
set APP_HOST=127.0.0.1
set APP_PORT=8000
set APP_RELOAD=false
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="APP_ENV" set APP_ENV=%%B
    if /i "%%A"=="APP_HOST" set APP_HOST=%%B
    if /i "%%A"=="APP_PORT" set APP_PORT=%%B
    if /i "%%A"=="APP_RELOAD" set APP_RELOAD=%%B
  )
)
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 setup_windows.bat
  exit /b 1
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":!APP_PORT! .*LISTENING"') do set PORT_PID=%%P
if defined PORT_PID (
  echo 端口 !APP_PORT! 已被 PID !PORT_PID! 占用。
  exit /b 1
)
set RELOAD_ARG=
if /i "!APP_RELOAD!"=="true" set RELOAD_ARG=--reload
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList @('-m','uvicorn','app.main:app','--host','%APP_HOST%','--port','%APP_PORT%','%RELOAD_ARG%') -WorkingDirectory '%CD%' -WindowStyle Hidden -PassThru; $p.Id | Set-Content -Encoding ASCII 'runtime\web.pid'"
echo Web 服务已启动：http://!APP_HOST!:!APP_PORT!/
