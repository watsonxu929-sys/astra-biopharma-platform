@echo off
chcp 65001 >nul
echo ============================================
echo    v0.6 Platform MVP — Verification
echo ============================================
echo.
echo This script runs 15 integration test sections:
echo   - Schema check (14 tables)
echo   - Tags (4 group checks)
echo   - People discovery & recommendations
echo   - Intelligence feed & search
echo   - Resources & matching
echo   - Favorites, follows, contact intents
echo   - Opportunities, follow-ups, tasks
echo   - Person profiles & database integrity
echo.

python scripts\verify_platform_mvp_v1.py
if %errorlevel% neq 0 (
    echo.
    echo [FAIL] Some verification checks failed.
    pause
    exit /b 1
)

echo.
echo [OK] All verification checks passed.
echo.
pause
