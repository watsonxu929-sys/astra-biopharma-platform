@echo off
chcp 65001 >nul
echo ============================================
echo    v0.6 Platform MVP — Migration
echo ============================================
echo.
echo This script will:
echo   1. Back up the database
echo   2. Create 14 new platform tables
echo   3. Seed 72 industry tags
echo   4. Verify all tables exist
echo.
echo Press Ctrl+C to cancel, or
pause

python scripts\migrate_platform_mvp_v1.py
if %errorlevel% neq 0 (
    echo.
    echo [FAIL] Migration failed. Check the error above.
    pause
    exit /b 1
)

echo.
echo [OK] Migration completed successfully.
echo.
pause
