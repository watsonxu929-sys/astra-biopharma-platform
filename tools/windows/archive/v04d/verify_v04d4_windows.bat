@echo off
setlocal EnableExtensions
cd /d "%~dp0..\..\..\.."
chcp 65001 >nul

if not exist "logs" mkdir "logs"
set "LOG=logs\verify_v04d4_latest.log"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
  set "PY=venv\Scripts\python.exe"
) else (
  set "PY=python"
)

> "%LOG%" echo V0.4D-4 organization linking and suspicious review verification
>> "%LOG%" echo Project: %CD%
>> "%LOG%" echo.

echo [1/5] Python compile...
%PY% -m py_compile app\main.py app\services\manual_ingestion.py app\services\subject_links.py app\services\suspicious_review.py app\entity_analyzer.py scripts\verify_v04d4_links_and_review.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo [2/5] V0.4D-4 feature verification...
%PY% scripts\verify_v04d4_links_and_review.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo [3/5] V0.4D-3 batch people regression...
%PY% scripts\verify_v04d3_batch_people.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo [4/5] Manual ingestion regression...
%PY% scripts\verify_manual_ingestion.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo [5/5] Search regression...
%PY% scripts\verify_v04d_search.py >> "%LOG%" 2>&1
if errorlevel 1 goto :fail

echo.
echo ========================================
echo V0.4D-4 validation PASSED.
echo Log: %LOG%
echo ========================================
echo.
pause
exit /b 0

:fail
echo.
echo ========================================
echo V0.4D-4 validation FAILED.
echo Please send this file to ChatGPT:
echo %LOG%
echo ========================================
echo.
type "%LOG%"
echo.
pause
exit /b 1
