@echo off
setlocal
cd /d "%~dp0..\..\..\.."

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Run setup_windows.bat first.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python scripts\apply_v04b.py
pause
