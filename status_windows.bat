@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$files=@('web','worker','scheduler'); foreach($name in $files){ $f='runtime\'+$name+'.pid'; if(Test-Path $f){ $pidText=(Get-Content $f -ErrorAction SilentlyContinue | Select-Object -First 1); $p=$null; if($pidText -match '^\d+$'){ $p=Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue }; if($p){ Write-Host ($name+': 运行中 PID '+$pidText) } else { Write-Host ($name+': PID 文件存在但进程不在运行') } } else { Write-Host ($name+': 未启动') } }"
