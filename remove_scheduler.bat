@echo off
REM ============================================================
REM  Remove the EU Quota Daily Snapshot scheduled task
REM  Run this script as Administrator (right-click > Run as admin)
REM ============================================================

set TASK_NAME=EU_Quota_Daily_Snapshot

echo Removing scheduled task: %TASK_NAME%
echo.

schtasks /delete /tn "%TASK_NAME%" /f

if %errorlevel% equ 0 (
    echo.
    echo Task removed successfully.
) else (
    echo.
    echo Failed to remove task. It may not exist, or you need Administrator rights.
)

pause
