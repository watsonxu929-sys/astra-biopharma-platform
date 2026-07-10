cd /d "%~dp0..\..\..\.."
@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "ROOT=%CD%\\"
cd /d "%~dp0..\..\..\.."
if not exist "logs" mkdir "logs"
set "LOG=%CD%\logs\v04f_migrate.log"
echo v0.4F migration started > "%LOG%"

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY set "PY=python"

"%PY%" -X utf8 "scripts\migrate_v04f.py" >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
type "%LOG%"
if not "%RC%"=="0" (
  echo [ERROR] v0.4F migration failed. Log: %LOG%
) else (
  echo [OK] v0.4F migration completed. Log: %LOG%
)
echo.
pause
exit /b %RC%
