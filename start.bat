@echo off
REM ClipForge - Start all services (Backend, Frontend, Video Processor)

setlocal enabledelayedexpansion

echo ========================================
echo    ClipForge - Starting Services
echo ========================================
echo.

REM Check if directories exist
if not exist "backend" (
    echo Error: backend directory not found
    exit /b 1
)

if not exist "frontend" (
    echo Error: frontend directory not found
    exit /b 1
)

if not exist "video-processor" (
    echo Error: video-processor directory not found
    exit /b 1
)

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

echo [Backend] Starting on port 9000...
start "ClipForge - Backend (Port 9000)" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate && python run_backend.py"

timeout /t 2 /nobreak >nul

echo [Video-Processor] Starting on port 8090...
start "ClipForge - Video-Processor (Port 8090)" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate && cd video-processor && python main.py"

timeout /t 2 /nobreak >nul

echo [Frontend] Starting on port 3000...
start "ClipForge - Frontend (Port 3000)" cmd /k "cd /d %~dp0\frontend && npm run dev"

echo.
echo ========================================
echo    All services started successfully!
echo ========================================
echo.
echo Services:
echo   Backend:         http://localhost:9000
echo   Frontend:        http://localhost:3000
echo   Video-Processor: http://localhost:8090
echo.
echo Close this window or press Ctrl+C to stop services
echo.

pause
