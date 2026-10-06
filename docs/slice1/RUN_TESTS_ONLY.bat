@echo off
cd /d "%~dp0\..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "docs\slice1\run_all_slice1.ps1" -TestsOnly
echo.
echo Finished. See docs\slice1\out\RUN_STATUS.txt
pause
