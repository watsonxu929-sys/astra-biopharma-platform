@echo off
setlocal
chcp 65001 >nul
for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"

echo Starting Biopharma Intelligence...
call scripts\windows\start_web_windows.bat
set "RUN_RC=%ERRORLEVEL%"
if not "%RUN_RC%"=="0" goto failed

echo.
echo Startup completed. Closing this window will not stop the Web service.
echo To stop: scripts\windows\web_service_windows.bat stop
if /i not "%RC1_RUN_NONINTERACTIVE%"=="true" timeout /t 5 /nobreak >nul
exit /b 0

:failed
echo.
echo Startup failed. Follow the message above.
echo Log: logs\startup.log
if /i not "%RC1_RUN_NONINTERACTIVE%"=="true" pause
exit /b %RUN_RC%
