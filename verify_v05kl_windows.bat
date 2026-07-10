@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 请先运行 setup_windows.bat
  exit /b 1
)
".venv\Scripts\python.exe" scripts\verify_v05kl.py
pause
