@echo off
REM ============================================================
REM AgentRAG — Full-stack launcher (Docker-only)
REM All services run inside Docker containers.
REM Prerequisites: Docker Desktop with WSL2 backend, NVIDIA Docker
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   AgentRAG — Multi-Agent RAG System
echo   GPU Embedding via Xinference (bge-m3)
echo ============================================================
echo.

REM ---------- Pre-flight checks ----------

REM Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH.
    echo         Install Docker Desktop (WSL2 backend) first.
    pause
    exit /b 1
)
echo [OK] Docker installed

REM Check Docker Compose
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose plugin not found.
    echo         Make sure Docker Desktop is installed with Compose plugin.
    pause
    exit /b 1
)
echo [OK] Docker Compose available

REM Check if .env exists
if not exist .env (
    echo [WARN] .env not found. Copying .env.example → .env
    echo        Please edit .env with your API keys before starting.
    copy .env.example .env >nul
)

REM Check NVIDIA Docker support
docker info 2>&1 | findstr /C:"NVIDIA" >nul
if errorlevel 1 (
    echo [WARN] NVIDIA Docker runtime not detected.
    echo        GPU acceleration will NOT be available.
    echo        To enable GPU: install nvidia-container-toolkit + Docker Desktop GPU support.
    set GPU_ENABLED=false
) else (
    echo [OK] NVIDIA Docker runtime detected — GPU enabled
    set GPU_ENABLED=true
)

echo.
echo ---------- Starting services ----------
echo.

REM Build and start all services
docker compose up --build -d

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start services. Check docker compose logs:
    echo         docker compose logs -f
    pause
    exit /b 1
)

echo.
echo ---------- Waiting for services to be ready ----------
echo.

REM Wait for infrastructure to stabilize
echo Waiting for PostgreSQL, Milvus, Neo4j, Elasticsearch...
call :wait_services 90

echo.
echo ============================================================
echo   AgentRAG is starting up!
echo ============================================================
echo.
echo   Frontend:     http://localhost:3000
echo   Backend API:  http://localhost:8000/docs
echo   Neo4j Browser: http://localhost:7474
echo   Elasticsearch: http://localhost:9200
echo.
echo   Default login: admin / admin
echo   (Reset password: python scripts\reset_admin_pwd.py)
echo.
echo   View logs:      docker compose logs -f
echo   Stop services:  docker compose down
echo   Stop + remove:  docker compose down -v
echo.
echo   Xinference bge-m3 model loads automatically on first access.
echo   If GPU is available, embedding will be fast.
echo.
pause
exit /b

REM ---------- Helper: wait for core services to become reachable ----------
:wait_services
set TIMEOUT=%1
set ELAPSED=0
set INTERVAL=5

echo (Waiting up to %TIMEOUT%s for services...)

:wait_loop
if !ELAPSED! GEQ %TIMEOUT% (
    echo [WARN] Some services may not be fully ready yet.
    echo        This is normal on first start — models need to download.
    goto :wait_done
)

set /a REMAINING=%TIMEOUT% - !ELAPSED!
echo   [.!] !REMAINING{s} remaining...

REM Check key ports
set SERVICES_OK=true

netstat -ano | findstr ":5432" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 set SERVICES_OK=false

netstat -ano | findstr ":19530" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 set SERVICES_OK=false

netstat -ano | findstr ":6379" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 set SERVICES_OK=false

if "!SERVICES_OK!"=="true" (
    echo [OK] Core services (PostgreSQL, Milvus, Redis) are reachable.
    goto :wait_done
)

timeout /t !INTERVAL! /nobreak >nul
set /a ELAPSED=!ELAPSED!+!INTERVAL!
goto wait_loop

:wait_done
echo.
goto :eof
