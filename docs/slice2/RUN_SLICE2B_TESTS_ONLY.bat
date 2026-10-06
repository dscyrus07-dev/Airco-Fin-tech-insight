@echo off
cd /d "%~dp0\..\.."
powershell -ExecutionPolicy Bypass -File ".\docs\slice2\run_slice2b.ps1" -TestsOnly
echo.
echo Finished. Read docs\slice2\out\RUN_STATUS.txt
pause
