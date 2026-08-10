@echo off
setlocal
cd /d "%~dp0"
if /i "%~1"=="start" goto start
if /i "%~1"=="stop" goto stop
if /i "%~1"=="status" goto status
echo Usage: web_service_windows.bat start^|stop^|status
exit /b 2

:start
call start_web_windows.bat
exit /b %errorlevel%

:stop
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f='runtime\web.pid'; if(!(Test-Path $f)){Write-Host 'Web is not running.'; exit 0}; $idText=(Get-Content $f | Select-Object -First 1); if($idText -notmatch '^\d+$'){Write-Error 'Invalid Web PID file.'; exit 1}; $all=@(Get-CimInstance Win32_Process); $root=$all | Where-Object ProcessId -eq ([int]$idText); if($root -and $root.CommandLine -notmatch 'uvicorn.+app\.main:app'){Write-Error 'PID is not the RC1 Web process; refusing to stop it.'; exit 1}; $ids=@([int]$idText); do{$new=@($all | Where-Object {$ids -contains [int]$_.ParentProcessId -and $ids -notcontains [int]$_.ProcessId} | ForEach-Object {[int]$_.ProcessId}); $ids += $new}while($new.Count); $ids | Sort-Object -Descending | ForEach-Object {Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue}; Remove-Item -LiteralPath $f -Force; Write-Host ('Web stopped. PID tree '+($ids -join ','))"
exit /b %errorlevel%

:status
powershell -NoProfile -ExecutionPolicy Bypass -Command "$f='runtime\web.pid'; if(!(Test-Path $f)){Write-Host 'Web: stopped'; exit 1}; $idText=(Get-Content $f | Select-Object -First 1); $p=Get-Process -Id ([int]$idText) -ErrorAction SilentlyContinue; if($p){Write-Host ('Web: running PID '+$idText); exit 0}; Write-Host 'Web: stale PID file'; exit 1"
exit /b %errorlevel%
