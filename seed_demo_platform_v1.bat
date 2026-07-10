@echo off
chcp 65001 >nul
echo ============================================
echo    v0.6 Platform MVP — Demo Data Seeder
echo ============================================
echo.
if "%1"=="--clean" goto clean

echo This script will seed demo data:
echo   - 10 organizations
echo   - 20 people with profiles and tags
echo   - 20 intelligence items
echo   - 20 market resources (10 supply + 10 demand)
echo   - 10 cooperation opportunities
echo.
echo Options:
echo   --run    : Seed demo data (default)
echo   --clean  : Remove all demo data
echo.
echo Press Ctrl+C to cancel, or
pause

python scripts\seed_demo_platform_v1.py --run
goto end

:clean
echo Cleaning all demo-marked data...
python scripts\seed_demo_platform_v1.py --clean
goto end

:end
if %errorlevel% neq 0 (
    echo.
    echo [FAIL] Operation failed. Check the error above.
    pause
    exit /b 1
)

echo.
echo [OK] Operation completed successfully.
echo.
pause
