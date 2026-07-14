@echo off
echo ============================================
echo 生物医药产业情报系统 - 验收环境
echo ============================================
echo 数据库: data/acceptance/t5_1_mvp.db
echo 端口: 8001
echo ============================================
echo WARNING: 此为验收环境，数据仅用于测试
echo ============================================
cd /d "%~dp0"
set DATABASE_URL=sqlite:///data/acceptance/t5_1_mvp.db
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
pause