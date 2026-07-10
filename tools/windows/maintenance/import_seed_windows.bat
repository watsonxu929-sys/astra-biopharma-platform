@echo off
setlocal
cd /d "%~dp0..\..\.."
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Run setup_windows.bat first.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python scripts\init_database.py
if errorlevel 1 goto failed
python scripts\import_seed_data.py
if errorlevel 1 goto failed
python scripts\check_seed_data.py
if errorlevel 1 goto failed
echo.
echo IMPORT SUCCESSFUL
pause
exit /b 0
:failed
echo.
echo IMPORT FAILED
pause
exit /b 1
