@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" scripts\migrate_v05j.py
pause
