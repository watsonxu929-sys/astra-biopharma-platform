@echo off
setlocal
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"

echo ============================================
echo Biopharma Intelligence - Setup
echo Project folder: %CD%
echo ============================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set PYTHON_CMD=py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set PYTHON_CMD=python
    ) else (
        echo ERROR: Python was not found.
        echo Install Python 3.11 or newer and enable Add Python to PATH.
        pause
        exit /b 1
    )
)

%PYTHON_CMD% --version
if errorlevel 1 goto failed

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto failed
) else (
    echo Virtual environment already exists.
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto failed
python -m pip install -r requirements.txt
if errorlevel 1 goto failed
python scripts\init_database.py
if errorlevel 1 goto failed
python scripts\self_check.py
if errorlevel 1 goto failed

echo.
echo SETUP SUCCESSFUL
pause
exit /b 0

:failed
echo.
echo SETUP FAILED
echo Copy the complete error message and send it to ChatGPT.
pause
exit /b 1
