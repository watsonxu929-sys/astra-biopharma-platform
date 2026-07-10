cd /d "%~dp0..\..\..\.."
@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "ROOT=%CD%\\"
pushd "%ROOT%" >nul 2>&1
if errorlevel 1 goto ROOT_ERROR

echo ==================================================
echo v0.4C-1 migrate_v04c1_windows.cmd
echo Project root: %CD%
echo ==================================================
echo.

if not exist "app\v04c1_ingestion.py" goto MISSING_FILES
if not exist "scripts\migrate_v04c1.py" goto MISSING_FILES

set "PY="
set "PY_KIND="
if exist ".venv\Scripts\python.exe" (
    set "PY=%CD%\.venv\Scripts\python.exe"
    set "PY_KIND=exe"
    goto PYTHON_OK
)
if exist "venv\Scripts\python.exe" (
    set "PY=%CD%\venv\Scripts\python.exe"
    set "PY_KIND=exe"
    goto PYTHON_OK
)
where py >nul 2>&1
if not errorlevel 1 (
    set "PY=py"
    set "PY_KIND=launcher"
    goto PYTHON_OK
)
for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PY set "PY=%%P"
)
if defined PY (
    set "PY_KIND=exe"
    goto PYTHON_OK
)
goto PYTHON_MISSING

:PYTHON_OK
if not exist "logs" mkdir "logs"
set "LOG=%CD%\logs\migrate_v04c1.log"
echo Python: %PY%
echo Log: %LOG%
echo.

if "%PY_KIND%"=="launcher" goto RUN_LAUNCHER
goto RUN_EXE

:RUN_LAUNCHER
py -3 -X utf8 "scripts\migrate_v04c1.py" >"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
goto SHOW_RESULT

:RUN_EXE
"%PY%" -X utf8 "scripts\migrate_v04c1.py" >"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
goto SHOW_RESULT

:SHOW_RESULT
type "%LOG%"
echo.
if not "%RC%"=="0" goto FAILED
echo [OK] v0.4C-1 migration completed.
goto FINISH

:FAILED
echo [ERROR] Task failed. Exit code: %RC%
echo Open this log file in Notepad:
echo %LOG%
goto FINISH

:MISSING_FILES
echo [ERROR] Required files were not found.
echo This CMD file must be placed in the project root.
echo Required:
echo   app\v04c1_ingestion.py
echo   scripts\migrate_v04c1.py
set "RC=2"
goto FINISH

:PYTHON_MISSING
echo [ERROR] Python was not found.
echo Expected .venv\Scripts\python.exe in the project root.
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
echo The window will remain open. Press any key to close it.
pause >nul
exit /b %RC%
