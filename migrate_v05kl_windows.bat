@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" scripts\migrate_v05kl.py
pause
