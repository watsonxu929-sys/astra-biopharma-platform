@echo off
setlocal EnableExtensions
cd /d "%~dp0..\..\..\.."
chcp 65001 >nul

if not exist "logs" mkdir "logs"
set "LOG=logs\verify_v04d3_latest.log"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
  set "PY=venv\Scripts\python.exe"
) else (
  set "PY=python"
)

> "%LOG%" echo V0.4D-3 batch people verification
>> "%LOG%" echo Project: %CD%
>> "%LOG%" echo.

echo [1/4] Python compile...
%PY% -m py_compile app\main.py app\services\manual_ingestion.py app\entity_analyzer.py scripts\verify_v04d3_batch_people.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo [2/4] Batch people verification...
%PY% scripts\verify_v04d3_batch_people.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo [3/4] Manual ingestion regression...
%PY% scripts\verify_manual_ingestion.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo [4/4] Search regression...
%PY% scripts\verify_v04d_search.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo.
echo ========================================
echo V0.4D-3 validation PASSED.
echo Log: %LOG%
echo ========================================
echo.
pause
exit /b 0

:fail
echo.
echo ========================================
echo V0.4D-3 validation FAILED.
echo Please send this file to ChatGPT:
echo %LOG%
echo ========================================
echo.
type "%LOG%"
echo.
pause
exit /b 1
