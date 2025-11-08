@echo off
REM VideoHelper - Start all services (Backend, Frontend, Video Processor)

setlocal enabledelayedexpansion

echo ========================================
echo    VideoHelper - Starting Services
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
start "Backend" cmd /c "python run_backend.py 2>&1 | python -c \"import sys; [print('^[Backend^]', line.rstrip()) for line in sys.stdin]\""

timeout /t 2 /nobreak >nul

echo [Video-Processor] Starting on port 8090...
start "Video-Processor" cmd /c "cd video-processor && python main.py 2>&1 | python -c \"import sys; [print('^[Video-Processor^]', line.rstrip()) for line in sys.stdin]\""

timeout /t 2 /nobreak >nul

echo [Frontend] Starting on port 3000...
start "Frontend" cmd /c "cd frontend && npm run dev 2>&1 | python -c \"import sys; [print('^[Frontend^]', line.rstrip()) for line in sys.stdin]\""

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
