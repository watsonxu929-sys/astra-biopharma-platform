@echo off
setlocal
cd /d "%~dp0\..\..\..\.."
if exist ".venv\Scripts\python.exe" (set PY=.venv\Scripts\python.exe) else if exist "venv\Scripts\python.exe" (set PY=venv\Scripts\python.exe) else (set PY=python)
%PY% scripts\migrate_v05a.py
if errorlevel 1 (echo Migration failed.& pause & exit /b 1)
echo v0.5A migration completed.
pause
