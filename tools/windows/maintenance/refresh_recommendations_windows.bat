@echo off
setlocal
cd /d "%~dp0\..\..\.."
if exist ".venv\Scripts\python.exe" (set PY=.venv\Scripts\python.exe) else if exist "venv\Scripts\python.exe" (set PY=venv\Scripts\python.exe) else (set PY=python)
%PY% scripts\refresh_v04h_recommendations.py
if errorlevel 1 (echo Refresh failed.& pause & exit /b 1)
echo Recommendations refreshed.
pause
