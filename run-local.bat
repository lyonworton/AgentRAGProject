@echo off
REM Start local GPU services for AgentRAG (Windows batch)
REM Prerequisites: Docker infra running via `docker compose up -d`
REM Usage: run-local.bat

echo ============================================
echo AgentRAG Local GPU Services
echo ============================================

REM Check if Docker infra is running
echo [1/3] Checking Docker infrastructure...
docker ps --format "{{.Names}}" | findstr /C:postgres >nul
if %errorlevel% neq 0 (
    echo ERROR: Docker infrastructure not running!
    echo Run: docker compose up -d
    pause
    exit /b 1
)
echo OK: Docker services detected

REM Check if backend port is available
echo [2/3] Checking port 8081...
netstat -ano | findstr ":8081" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo WARNING: Port 8081 is already in use.
    echo Another process may be running.
)

echo [3/3] Starting FastAPI (GPU enabled)...
start "AgentRAG Backend" cmd /k "cd /d %~dp0 && call conda activate myenv && uvicorn app.main:app --host 0.0.0.0 --port 8081"

echo Starting ARQ Worker (GPU enabled)...
start "AgentRAG Worker" cmd /k "cd /d %~dp0 && call conda activate myenv && python -m arq app.workers.main.WorkerSettings"

echo.
echo ============================================
echo Backend:  http://localhost:8081
echo Worker:   running in background
echo Frontend: http://localhost:3000 (Docker)
echo ============================================
echo.
echo Two new windows opened. Close them to stop services.
pause
