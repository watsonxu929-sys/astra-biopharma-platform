@echo off
setlocal
cd /d "%~dp0"

:menu
cls
echo ============================================
echo Biopharma Intelligence - Project Tools
echo ============================================
echo 1. Start system
echo 2. Run safe migrations
echo 3. Run full verification
echo 4. Backup database
echo 5. Run monitoring once
echo 6. Run collection once
echo 7. Run collection worker
echo 8. Open collection center
echo 9. Run processing once
echo 10. Run processing worker
echo 11. Open processing center
echo 12. Run signal worker once
echo 13. Run report worker once
echo 14. Open reports
echo 15. Run pipeline once
echo 16. Run pipeline worker
echo 17. Open pipeline center
echo 18. Refresh smart recommendations
echo 19. Export data
echo 20. Import seed data
echo 21. System self-check
echo 22. Run v0.5J verification
echo 23. Open research center
echo 24. Open company compare
echo 25. Open track analysis
echo 26. Open investment assessment
echo 27. Start all production services
echo 28. Stop all production services
echo 29. Service status
echo 30. Run v0.5K-L verification
echo 31. Open operations center
echo A. Open logs folder
echo B. Open user management
echo C. Open audit log
echo D. Open Q-BAY member import
echo 0. Exit
echo.
set /p CHOICE=Select:

if "%CHOICE%"=="0" exit /b 0
if "%CHOICE%"=="1" call run_windows.bat & goto after_action
if "%CHOICE%"=="2" call migrate_all_windows.bat & goto after_action
if "%CHOICE%"=="3" call verify_all_windows.bat & goto after_action
if "%CHOICE%"=="4" call backup_windows.bat & goto after_action
if "%CHOICE%"=="5" call run_monitoring_once_windows.bat & goto after_action
if "%CHOICE%"=="6" call run_collection_once_windows.bat & goto after_action
if "%CHOICE%"=="7" call run_collection_worker_windows.bat & goto after_action
if "%CHOICE%"=="8" start "" http://127.0.0.1:8000/collection & goto after_action
if "%CHOICE%"=="9" call run_processing_once_windows.bat & goto after_action
if "%CHOICE%"=="10" call run_processing_worker_windows.bat & goto after_action
if "%CHOICE%"=="11" start "" http://127.0.0.1:8000/processing & goto after_action
if "%CHOICE%"=="12" call run_signal_once_windows.bat & goto after_action
if "%CHOICE%"=="13" call run_report_once_windows.bat & goto after_action
if "%CHOICE%"=="14" start "" http://127.0.0.1:8000/reports & goto after_action
if "%CHOICE%"=="15" call run_pipeline_once_windows.bat & goto after_action
if "%CHOICE%"=="16" call run_pipeline_worker_windows.bat & goto after_action
if "%CHOICE%"=="17" start "" http://127.0.0.1:8000/pipeline & goto after_action
if "%CHOICE%"=="18" call tools\windows\maintenance\refresh_recommendations_windows.bat & goto after_action
if "%CHOICE%"=="19" call tools\windows\maintenance\export_windows.bat & goto after_action
if "%CHOICE%"=="20" goto import_seed
if "%CHOICE%"=="21" call tools\windows\diagnostics\self_check_windows.bat & goto after_action
if "%CHOICE%"=="22" call verify_v05j_windows.bat & goto after_action
if "%CHOICE%"=="23" start "" http://127.0.0.1:8000/research & goto after_action
if "%CHOICE%"=="24" start "" http://127.0.0.1:8000/research/companies/compare & goto after_action
if "%CHOICE%"=="25" start "" http://127.0.0.1:8000/research/tracks & goto after_action
if "%CHOICE%"=="26" start "" http://127.0.0.1:8000/research/investment & goto after_action
if "%CHOICE%"=="27" call start_all_windows.bat & goto after_action
if "%CHOICE%"=="28" call stop_all_windows.bat & goto after_action
if "%CHOICE%"=="29" call status_windows.bat & goto after_action
if "%CHOICE%"=="30" call verify_v05kl_windows.bat & goto after_action
if "%CHOICE%"=="31" start "" http://127.0.0.1:8000/system/operations & goto after_action
if /I "%CHOICE%"=="A" start "" "%CD%\logs" & goto after_action
if /I "%CHOICE%"=="B" start "" http://127.0.0.1:8000/admin/users & goto after_action
if /I "%CHOICE%"=="C" start "" http://127.0.0.1:8000/admin/audit & goto after_action
if /I "%CHOICE%"=="D" start "" http://127.0.0.1:8000/club/import & goto after_action
echo Invalid choice.

:after_action
echo.
echo Press any key to return to menu.
pause >nul
goto menu

:import_seed
echo.
echo Importing seed data may change the database.
echo Please run backup first if needed.
choice /c YN /m "Continue"
if errorlevel 2 goto menu
call tools\windows\maintenance\import_seed_windows.bat
goto menu
