@echo off
echo ============================================
echo 生物医药产业情报系统 - 演练环境 (认证启用)
echo ============================================
echo 数据库: data/rehearsal/v06j_app_migrated.db
echo 端口: 8001
echo APP_AUTH_DISABLED: false
echo ============================================
echo WARNING: 此为演练环境，数据仅用于测试
echo ============================================
cd /d "%~dp0"
set DATABASE_URL=sqlite:///data/rehearsal/v06j_app_migrated.db
set APP_ENV=testing
set ENABLE_SCHEDULER_IN_WEB=false
set APP_AUTH_DISABLED=false
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
pause