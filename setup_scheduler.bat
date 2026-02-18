@echo off
REM ============================================================
REM  Setup Windows Task Scheduler for daily EU Quota snapshot
REM  Run this script as Administrator (right-click > Run as admin)
REM ============================================================

set TASK_NAME=EU_Quota_Daily_Snapshot
set SCRIPT_DIR=%~dp0

echo Setting up scheduled task: %TASK_NAME%
echo Working directory: %SCRIPT_DIR%
echo.

schtasks /create /tn "%TASK_NAME%" /tr "pythonw \"%SCRIPT_DIR%daily_snapshot.py\"" /sc onlogon /rl highest /f

if %errorlevel% equ 0 (
    echo.
    echo Task created successfully!
    echo   Name:    %TASK_NAME%
    echo   Trigger: At log on
    echo   Action:  pythonw daily_snapshot.py
    echo.
    echo To verify: open taskschd.msc and look for %TASK_NAME%
    echo To remove: run remove_scheduler.bat
) else (
    echo.
    echo Failed to create task. Make sure you ran this as Administrator.
)

pause
