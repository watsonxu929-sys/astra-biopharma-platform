@echo off
setlocal
for %%I in ("%~dp0..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$files=@('runtime\web.pid','runtime\worker.pid','runtime\scheduler.pid'); foreach($f in $files){ if(Test-Path $f){ $pidText=(Get-Content $f -ErrorAction SilentlyContinue | Select-Object -First 1); if($pidText -match '^\d+$'){ $p=Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue; if($p){ Stop-Process -Id $p.Id -Force; Write-Host ('已停止 '+$f+' PID '+$pidText) } }; Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue } }"
echo 已处理本项目 PID 文件中的进程。
