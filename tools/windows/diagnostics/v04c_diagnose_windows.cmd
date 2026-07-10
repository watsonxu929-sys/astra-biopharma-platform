cd /d "%~dp0..\..\.."
@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "ROOT=%CD%\\"
pushd "%ROOT%" >nul 2>&1
if errorlevel 1 goto END

if not exist "logs" mkdir "logs"
set "LOG=%CD%\logs\v04c_diagnose.log"

echo v0.4C diagnostic report >"%LOG%"
echo Time: %DATE% %TIME% >>"%LOG%"
echo Root: %CD% >>"%LOG%"
echo. >>"%LOG%"

echo [Files] >>"%LOG%"
if exist "app\v04c_review.py" (echo OK app\v04c_review.py>>"%LOG%") else (echo MISSING app\v04c_review.py>>"%LOG%")
if exist "scripts\migrate_v04c.py" (echo OK scripts\migrate_v04c.py>>"%LOG%") else (echo MISSING scripts\migrate_v04c.py>>"%LOG%")
if exist "scripts\verify_v04c.py" (echo OK scripts\verify_v04c.py>>"%LOG%") else (echo MISSING scripts\verify_v04c.py>>"%LOG%")
if exist ".venv\Scripts\python.exe" (echo OK .venv\Scripts\python.exe>>"%LOG%") else (echo MISSING .venv\Scripts\python.exe>>"%LOG%")
echo. >>"%LOG%"

if exist ".venv\Scripts\python.exe" goto CHECK_VENV
goto CHECK_SYSTEM

:CHECK_VENV
echo [Python] >>"%LOG%"
".venv\Scripts\python.exe" -X utf8 --version >>"%LOG%" 2>&1
".venv\Scripts\python.exe" -X utf8 -c "import fastapi,jinja2; print('FastAPI/Jinja2 import OK')" >>"%LOG%" 2>&1
".venv\Scripts\python.exe" -X utf8 -c "from app.v04c_review import ensure_v04c_schema; print('v04c module import OK')" >>"%LOG%" 2>&1
goto SHOW

:CHECK_SYSTEM
echo [Python] >>"%LOG%"
where python >>"%LOG%" 2>&1
python -X utf8 --version >>"%LOG%" 2>&1
python -X utf8 -c "import fastapi,jinja2; print('FastAPI/Jinja2 import OK')" >>"%LOG%" 2>&1
python -X utf8 -c "from app.v04c_review import ensure_v04c_schema; print('v04c module import OK')" >>"%LOG%" 2>&1

:SHOW
type "%LOG%"
echo.
echo Diagnostic log:
echo %LOG%
popd >nul 2>&1

:END
echo.
echo The window will remain open. Press any key to close it.
pause >nul
exit /b 0
