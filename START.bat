@echo off
setlocal enabledelayedexpansion

REM Always run from the repo root (this script's directory)
cd /d "%~dp0"

set "COMPOSE_BASE=docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.local.yml --env-file local.env"
set "ENV_FILE=local.env"
set "KEYCLOAK_SETUP=scripts\setup\setup-local-keycloak.ps1"
set "EC2_SCRIPT=scripts\deploy\manage-ec2-instance.ps1"
if not exist "%EC2_SCRIPT%" set "EC2_SCRIPT=manage-ec2-instance.ps1"

echo ============================================================
echo   Airco Insights - Local Docker Manager
echo   DB: Supabase (cloud)  ^|  Auth: Keycloak (local)
echo   Excel: Lite 9-sheet export
echo ============================================================
echo.

:menu
echo  DOCKER SETUP ^& LIFECYCLE
echo  ------------------------
echo   1. Setup + Start stack   (first-time / recommended)
echo   2. Start stack
echo   3. Restart stack
echo   4. Rebuild + Start       (full image rebuild)
echo   5. Stop stack
echo   6. Stop + purge volumes  (wipe MinIO/RabbitMQ/Redis data)
echo.
echo  LOGS ^& STATUS
echo  -------------
echo   7. Backend logs   (live)
echo   8. Frontend logs  (live)
echo   9. All logs       (live)
echo  10. Service status
echo  11. Health check
echo.
echo  AUTH SETUP
echo  ----------
echo  12. Setup Keycloak  (realm + test user)
echo.
echo  EC2 PRODUCTION
echo  --------------
echo  13. EC2 start + deploy
echo  14. EC2 stop
echo  15. EC2 status
echo  16. EC2 rebuild
echo.
echo   0. Exit
echo.
set /p choice="Enter your choice: "

if "%choice%"=="1"  goto setup_start
if "%choice%"=="2"  goto start
if "%choice%"=="3"  goto restart
if "%choice%"=="4"  goto rebuild
if "%choice%"=="5"  goto stop
if "%choice%"=="6"  goto purge
if "%choice%"=="7"  goto logs_backend
if "%choice%"=="8"  goto logs_frontend
if "%choice%"=="9"  goto logs_all
if "%choice%"=="10" goto status
if "%choice%"=="11" goto health
if "%choice%"=="12" goto keycloak
if "%choice%"=="13" goto ec2_start
if "%choice%"=="14" goto ec2_stop
if "%choice%"=="15" goto ec2_status
if "%choice%"=="16" goto ec2_rebuild
if "%choice%"=="0"  goto exit
echo.
echo  Invalid choice. Please try again.
echo.
goto menu

REM ------------------------------------------------------------
REM Preflight: Docker + env files
REM ------------------------------------------------------------
:preflight
where docker >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Docker is not installed or not on PATH.
    echo         Install Docker Desktop and try again.
    echo.
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Docker daemon is not running.
    echo         Start Docker Desktop, wait until it is ready, then retry.
    echo.
    exit /b 1
)

if not exist "%ENV_FILE%" (
    echo.
    echo [ERROR] %ENV_FILE% not found in project root.
    echo         Expected: %cd%\%ENV_FILE%
    echo.
    exit /b 1
)

if not exist "infra\docker\docker-compose.yml" (
    echo.
    echo [ERROR] docker-compose.yml not found.
    echo         Expected: %cd%\infra\docker\docker-compose.yml
    echo.
    exit /b 1
)

if not exist "infra\docker\docker-compose.local.yml" (
    echo.
    echo [ERROR] docker-compose.local.yml not found.
    echo         Expected: %cd%\infra\docker\docker-compose.local.yml
    echo.
    exit /b 1
)

exit /b 0

REM ------------------------------------------------------------
REM 1) First-time setup + start
REM ------------------------------------------------------------
:setup_start
echo.
echo [Setup] Checking Docker and environment...
call :preflight
if errorlevel 1 (
    pause
    goto menu
)

echo.
echo [Setup] Pulling/building and starting local stack...
echo         Compose: infra/docker/docker-compose.yml + docker-compose.local.yml
echo         Env:     local.env
echo         DB:      Supabase (no local app-postgres)
echo.
%COMPOSE_BASE% up -d --build
if errorlevel 1 (
    echo.
    echo [ERROR] Stack failed to start. Check Docker Desktop and logs.
    echo.
    pause
    goto menu
)

echo.
echo [Setup] Waiting for services to settle...
timeout /t 8 /nobreak >nul

echo.
echo [Setup] Keycloak realm/user bootstrap (optional but recommended once)...
if exist "%KEYCLOAK_SETUP%" (
    powershell -ExecutionPolicy Bypass -File "%KEYCLOAK_SETUP%"
) else (
    echo [WARN] Keycloak setup script not found: %KEYCLOAK_SETUP%
    echo        You can run option 12 later.
)

echo.
call :print_urls
echo Login (after Keycloak setup): test@airco.com / Test123!
echo.
pause
goto menu

REM ------------------------------------------------------------
REM 2) Start
REM ------------------------------------------------------------
:start
echo.
echo Starting local development stack...
call :preflight
if errorlevel 1 (
    pause
    goto menu
)

echo.
%COMPOSE_BASE% up -d
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start stack.
    echo.
    pause
    goto menu
)

echo.
call :print_urls
pause
goto menu

REM ------------------------------------------------------------
REM 3) Restart
REM ------------------------------------------------------------
:restart
echo.
echo Restarting local development stack...
call :preflight
if errorlevel 1 (
    pause
    goto menu
)

echo.
echo Stopping containers...
%COMPOSE_BASE% stop
echo.
echo Starting containers...
%COMPOSE_BASE% up -d
if errorlevel 1 (
    echo.
    echo [ERROR] Restart failed.
    echo.
    pause
    goto menu
)

echo.
echo Stack restarted.
call :print_urls
pause
goto menu

REM ------------------------------------------------------------
REM 4) Rebuild + start
REM ------------------------------------------------------------
:rebuild
echo.
echo Rebuilding local development stack (full image rebuild)...
call :preflight
if errorlevel 1 (
    pause
    goto menu
)

echo.
%COMPOSE_BASE% up -d --build
if errorlevel 1 (
    echo.
    echo [ERROR] Rebuild failed.
    echo.
    pause
    goto menu
)

echo.
call :print_urls
pause
goto menu

REM ------------------------------------------------------------
REM 5) Stop
REM ------------------------------------------------------------
:stop
echo.
echo Stopping local development stack...
call :preflight
if errorlevel 1 (
    pause
    goto menu
)

echo.
%COMPOSE_BASE% down
echo.
echo Stack stopped.
echo.
pause
goto menu

REM ------------------------------------------------------------
REM 6) Purge
REM ------------------------------------------------------------
:purge
echo.
echo WARNING: This will stop all containers AND delete all local volumes.
echo          MinIO data, RabbitMQ queues and Redis cache will be wiped.
echo          Supabase cloud data is NOT affected.
echo.
set /p confirm="Type YES to confirm: "
if /i not "%confirm%"=="YES" (
    echo Cancelled.
    echo.
    pause
    goto menu
)

call :preflight
if errorlevel 1 (
    pause
    goto menu
)

%COMPOSE_BASE% down -v
echo.
echo Stack purged (containers + volumes removed).
echo.
pause
goto menu

REM ------------------------------------------------------------
REM Logs / status / health
REM ------------------------------------------------------------
:logs_backend
echo.
echo Streaming backend logs (Ctrl+C to stop)...
echo.
%COMPOSE_BASE% logs -f backend
echo.
pause
goto menu

:logs_frontend
echo.
echo Streaming frontend logs (Ctrl+C to stop)...
echo.
%COMPOSE_BASE% logs -f frontend
echo.
pause
goto menu

:logs_all
echo.
echo Streaming all service logs (Ctrl+C to stop)...
echo.
%COMPOSE_BASE% logs -f
echo.
pause
goto menu

:status
echo.
echo Current container status:
echo.
%COMPOSE_BASE% ps
echo.
pause
goto menu

:health
echo.
echo Running quick health checks...
echo.
echo [backend]  http://localhost:8000/health
curl -s -o NUL -w "  HTTP %%{http_code}\n" http://localhost:8000/health 2>nul || echo   unreachable
echo [frontend] http://localhost:3000
curl -s -o NUL -w "  HTTP %%{http_code}\n" http://localhost:3000 2>nul || echo   unreachable
echo [keycloak] http://localhost:8080
curl -s -o NUL -w "  HTTP %%{http_code}\n" http://localhost:8080 2>nul || echo   unreachable
echo.
%COMPOSE_BASE% ps
echo.
pause
goto menu

REM ------------------------------------------------------------
REM Keycloak
REM ------------------------------------------------------------
:keycloak
echo.
echo Setting up Keycloak realm and test user...
echo Make sure the stack is running first (option 1 or 2).
echo.
if not exist "%KEYCLOAK_SETUP%" (
    echo [ERROR] Setup script not found: %KEYCLOAK_SETUP%
    echo.
    pause
    goto menu
)
powershell -ExecutionPolicy Bypass -File "%KEYCLOAK_SETUP%"
echo.
echo Keycloak setup complete!
echo Login with: test@airco.com / Test123!
echo.
pause
goto menu

REM ------------------------------------------------------------
REM EC2
REM ------------------------------------------------------------
:ec2_start
echo.
if not exist "%EC2_SCRIPT%" (
    echo [ERROR] EC2 script not found.
    echo         Looked for: scripts\deploy\manage-ec2-instance.ps1
    echo                     manage-ec2-instance.ps1
    echo.
    pause
    goto menu
)
powershell -ExecutionPolicy Bypass -File "%EC2_SCRIPT%" -Action start
echo.
pause
goto menu

:ec2_stop
echo.
if not exist "%EC2_SCRIPT%" (
    echo [ERROR] EC2 script not found.
    pause
    goto menu
)
powershell -ExecutionPolicy Bypass -File "%EC2_SCRIPT%" -Action stop
echo.
pause
goto menu

:ec2_status
echo.
if not exist "%EC2_SCRIPT%" (
    echo [ERROR] EC2 script not found.
    pause
    goto menu
)
powershell -ExecutionPolicy Bypass -File "%EC2_SCRIPT%" -Action status
echo.
pause
goto menu

:ec2_rebuild
echo.
if not exist "%EC2_SCRIPT%" (
    echo [ERROR] EC2 script not found.
    pause
    goto menu
)
powershell -ExecutionPolicy Bypass -File "%EC2_SCRIPT%" -Action rebuild
echo.
pause
goto menu

REM ------------------------------------------------------------
REM Helpers
REM ------------------------------------------------------------
:print_urls
echo ----------------------------------------
echo  Stack is up!
echo ----------------------------------------
echo  Frontend:           http://localhost:3000
echo  Backend API:        http://localhost:8000
echo  Backend API Docs:   http://localhost:8000/docs
echo  Auth Service:       http://localhost:8001
echo  Keycloak:           http://localhost:8080
echo  MinIO Console:      http://localhost:9001
echo  RabbitMQ Mgmt:      http://localhost:15672
echo  Redis:              localhost:6379
echo ----------------------------------------
echo  Database: Supabase cloud (DATABASE_URL in local.env)
echo ----------------------------------------
echo.
goto :eof

:exit
echo.
echo Goodbye!
exit /b 0

