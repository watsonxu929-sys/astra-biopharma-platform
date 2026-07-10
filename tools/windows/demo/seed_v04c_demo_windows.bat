@echo off
chcp 65001 >nul
cd /d "%~dp0..\..\.."
".venv\Scripts\python.exe" "scripts\seed_v04c_demo.py"
pause
