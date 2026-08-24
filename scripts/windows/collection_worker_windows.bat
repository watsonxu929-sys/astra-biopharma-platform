@echo off
setlocal
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"
if /i "%~1"=="start" goto start
if /i "%~1"=="stop" goto stop
if /i "%~1"=="status" goto status
echo Usage: collection_worker_windows.bat start^|stop^|status
exit /b 2

:start
if not exist "runtime\worker.pid" goto launch
set /p OLD_PID=<"runtime\worker.pid"
tasklist /FI "PID eq %OLD_PID%" 2>NUL | findstr /R /C:" %OLD_PID% " >NUL
if errorlevel 1 goto launch
echo Worker is already running. PID %OLD_PID%
exit /b 1

:launch
call scripts\windows\start_worker_windows.bat
exit /b %errorlevel%

:stop
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f='runtime\worker.pid'; if(!(Test-Path $f)){Write-Host 'Worker is not running.'; exit 0}; $idText=(Get-Content $f | Select-Object -First 1); if($idText -notmatch '^\d+$'){Write-Error 'Invalid Worker PID file.'; exit 1}; $all=@(Get-CimInstance Win32_Process); $root=$all | Where-Object ProcessId -eq ([int]$idText); if($root -and $root.CommandLine -notmatch 'scripts[\\/]run_worker\.py'){Write-Error 'PID is not the RC1 Worker process; refusing to stop it.'; exit 1}; $ids=@([int]$idText); do{$new=@($all | Where-Object {$ids -contains [int]$_.ParentProcessId -and $ids -notcontains [int]$_.ProcessId} | ForEach-Object {[int]$_.ProcessId}); $ids += $new}while($new.Count); $ids | Sort-Object -Descending | ForEach-Object {Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue}; Remove-Item -LiteralPath $f -Force; Write-Host ('Worker stopped. PID tree '+($ids -join ','))"
exit /b %errorlevel%

:status
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f='runtime\worker.pid'; if(!(Test-Path $f)){Write-Host 'Worker: stopped'; exit 1}; $idText=(Get-Content $f | Select-Object -First 1); $p=Get-Process -Id ([int]$idText) -ErrorAction SilentlyContinue; if($p){Write-Host ('Worker: running PID '+$idText); exit 0}; Write-Host 'Worker: stale PID file'; exit 1"
exit /b %errorlevel%
