@echo off
setlocal EnableExtensions

rem Always reopen in a persistent CMD window when double-clicked.
if /I not "%~1"=="__INNER__" (
    start "v0.4D-2 Verification" "%ComSpec%" /k ""%~f0" __INNER__"
    exit /b 0
)

cd /d "%~dp0..\..\..\.."
chcp 65001 >nul 2>&1
title v0.4D-2 Verification

if not exist "logs" mkdir "logs" >nul 2>&1
set "LOG=logs\verify_v04d2_latest.log"
> "%LOG%" echo v0.4D-2 verification started from: %CD%

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY (
    where python.exe >nul 2>&1
    if not errorlevel 1 set "PY=python.exe"
)

if not defined PY (
    echo.
    echo [ERROR] Python was not found.
    echo Expected: .venv\Scripts\python.exe
    echo Current folder: %CD%
    echo.
    echo Put this BAT file in the project root, beside run_windows.bat.
    goto :FAILED
)

for %%F in (
    "app\main.py"
    "app\entity_analyzer.py"
    "app\web_extractor.py"
    "app\services\manual_ingestion.py"
    "scripts\verify_manual_ingestion.py"
    "scripts\verify_v04d_search.py"
    "scripts\audit_suspicious_entities.py"
) do (
    if not exist "%%~F" (
        echo.
        echo [ERROR] Missing file: %%~F
        echo The patch may not have been extracted into the project root.
        goto :FAILED
    )
)

echo Project folder: %CD%
echo Python: %PY%
echo Log: %LOG%
echo.

call :RUN "%PY%" -m py_compile app\main.py app\entity_analyzer.py app\web_extractor.py app\services\manual_ingestion.py scripts\verify_manual_ingestion.py scripts\audit_suspicious_entities.py
if errorlevel 1 goto :FAILED

call :RUN "%PY%" scripts\verify_manual_ingestion.py
if errorlevel 1 goto :FAILED

call :RUN "%PY%" scripts\verify_v04d_search.py
if errorlevel 1 goto :FAILED

call :RUN "%PY%" scripts\audit_suspicious_entities.py --output data\suspicious_entities_review.csv
if errorlevel 1 goto :FAILED

echo.
echo ============================================================
echo [SUCCESS] All v0.4D-2 checks passed.
echo Database was read only; no records were changed.
echo Review CSV: data\suspicious_entities_review.csv
echo Full log: %LOG%
echo ============================================================
echo.
pause
exit /b 0

:RUN
echo [RUN] %*
>> "%LOG%" echo.
>> "%LOG%" echo [RUN] %*
set "TMP=%TEMP%\v04d2_verify_%RANDOM%_%RANDOM%.log"
%* > "%TMP%" 2>&1
set "RC=%ERRORLEVEL%"
type "%TMP%"
type "%TMP%" >> "%LOG%"
del /q "%TMP%" >nul 2>&1
if not "%RC%"=="0" (
    echo [FAILED] Exit code: %RC%
    >> "%LOG%" echo [FAILED] Exit code: %RC%
    exit /b %RC%
)
echo [PASS]
>> "%LOG%" echo [PASS]
echo.
exit /b 0

:FAILED
echo.
echo ============================================================
echo [FAILED] Verification did not complete.
echo The window will remain open.
echo Send a screenshot of the first ERROR block or this log file:
echo %LOG%
echo ============================================================
echo.
pause
exit /b 1
