cd /d "%~dp0..\..\..\.."
@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "ROOT=%CD%\\"
pushd "%ROOT%" >nul 2>&1
if errorlevel 1 goto ROOT_ERROR

echo ==================================================
echo v0.4D Context Collector
echo Project root: %CD%
echo ==================================================
echo.

if not exist "scripts\collect_v04d_context.py" goto MISSING_FILE
if not exist "logs" mkdir "logs"
set "LOG=%CD%\logs\v04d_context_collect.log"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -X utf8 "scripts\collect_v04d_context.py" >"%LOG%" 2>&1
    set "RC=%ERRORLEVEL%"
    goto SHOW_RESULT
)

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -X utf8 "scripts\collect_v04d_context.py" >"%LOG%" 2>&1
    set "RC=%ERRORLEVEL%"
    goto SHOW_RESULT
)

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -X utf8 "scripts\collect_v04d_context.py" >"%LOG%" 2>&1
    set "RC=%ERRORLEVEL%"
    goto SHOW_RESULT
)

where python >nul 2>&1
if not errorlevel 1 (
    python -X utf8 "scripts\collect_v04d_context.py" >"%LOG%" 2>&1
    set "RC=%ERRORLEVEL%"
    goto SHOW_RESULT
)

goto PYTHON_MISSING

:SHOW_RESULT
type "%LOG%"
echo.
if not "%RC%"=="0" goto FAILED
echo [OK] Context bundle created under:
echo %CD%\handoff
goto FINISH

:FAILED
echo [ERROR] Collection failed. Exit code: %RC%
echo Log:
echo %LOG%
goto FINISH

:MISSING_FILE
echo [ERROR] Missing scripts\collect_v04d_context.py
set "RC=2"
goto FINISH

:PYTHON_MISSING
echo [ERROR] Python was not found.
set "RC=3"
goto FINISH

:ROOT_ERROR
echo [ERROR] Cannot enter the script directory.
set "RC=4"
goto FINISH_NO_POPD

:FINISH
popd >nul 2>&1

:FINISH_NO_POPD
echo.
echo Press any key to close.
pause >nul
exit /b %RC%
