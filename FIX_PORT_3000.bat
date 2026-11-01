@echo off
REM Restore the app to http://localhost:3000 AND keep it working across restarts.
REM Double-click this file and approve the UAC prompt. That's all.
REM ORDER MATTERS: winnat must release its dynamic ranges BEFORE we can
REM claim port 3000 as a persistent exclusion.
net session >nul 2>&1 || (powershell -Command "Start-Process '%~f0' -Verb RunAs" & exit /b)

echo Step 1: Releasing winnat's dynamic port reservations...
net stop winnat

echo Step 2: Permanently reserving port 3000 for Docker (one-time fix)...
netsh int ipv4 delete excludedportrange protocol=tcp startport=3000 numberofports=1 >nul 2>&1
netsh int ipv4 add excludedportrange protocol=tcp startport=3000 numberofports=1 store=persistent

echo Step 3: Restarting winnat (it will pick ranges that avoid :3000)...
net start winnat

echo Step 4: Recreating frontend + nginx on :3000 ...
docker rm -f airco_frontend airco_nginx
cd /d "X:\Airco Projects\wt-r5\infra\docker"
docker compose -p airco -f docker-compose.yml -f docker-compose.local.yml -f docker-compose.ocr.yml -f docker-compose.ocr-vllm.yml --env-file .env up -d frontend nginx

echo.
echo Done. Open http://localhost:3000
echo (Port 3000 is now permanently protected - this survives future restarts.)
pause
