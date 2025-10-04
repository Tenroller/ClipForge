@echo off
setlocal enabledelayedexpansion

REM AI Video Generator - Development Start Script (Windows)
REM 
REM This script starts all three services:
REM - Frontend (React/Vite) on port 5173
REM - Backend (FastAPI) on port 8080  
REM - Video Processor (FastAPI) on port 8090
REM
REM Prerequisites:
REM 1. Create .venv: python -m venv .venv && .venv\Scripts\activate
REM 2. Install backend deps: pip install -r requirements.txt
REM 3. Install video-processor deps: cd video-processor && pip install -r requirements.txt
REM 4. Install frontend deps: cd frontend && npm install
REM 5. Configure environment: copy env-example.txt to .env and edit API keys
REM
REM Note: The script will run with dummy API keys if .env is not configured

REM Function to kill all background processes when the script exits
:cleanup
echo Shutting down all services...
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
exit /b

REM Set up cleanup on script exit
set "CLEANUP_SCRIPT=%~f0"
set "CLEANUP_FUNCTION=:cleanup"

REM --- Frontend ---
echo Starting frontend development server...
cd frontend
if not exist "node_modules" (
    echo Node modules not found. Running npm install...
    npm install
)
start "Frontend" cmd /c "npm run dev"
cd ..

REM --- Backend ---
echo Starting backend server...

REM Check if .venv exists
if not exist ".venv" (
    echo Python virtual environment not found. Please run:
    echo python -m venv .venv
    echo .venv\Scripts\activate
    echo pip install -r requirements.txt
    pause
    exit /b 1
)

REM Load environment variables from .env if it exists
if exist ".env" (
    echo Loading environment variables for backend from .env file...
    for /f "usebackq delims=" %%i in (".env") do (
        set "line=%%i"
        if not "!line:~0,1!"=="#" (
            if not "!line!"=="" (
                set "!line!"
            )
        )
    )
) else (
    echo No .env file found in project root. Using default backend configuration.
)

REM Activate virtual environment and start the server
call .venv\Scripts\activate.bat

REM Set PYTHONPATH to include the project root so backend module can be imported
set "PYTHONPATH=%CD%;%PYTHONPATH%"

cd backend

start "Backend" cmd /c "python main.py"

cd ..

REM --- Video Processor ---
echo Starting video processor service...

REM Check if video-processor directory exists
if not exist "video-processor" (
    echo Video processor directory not found!
    pause
    exit /b 1
)

cd video-processor

REM Check if requirements are installed (optional check)
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo Video processor dependencies not found. Please install requirements:
    echo pip install -r requirements.txt
    echo or
    echo pip install -r requirements.simple.txt
)

REM Load environment variables from project root .env if it exists
if exist "../.env" (
    echo Loading environment variables from .env file...
    for /f "usebackq delims=" %%i in ("../.env") do (
        set "line=%%i"
        if not "!line:~0,1!"=="#" (
            if not "!line!"=="" (
                set "!line!"
            )
        )
    )
) else (
    echo No .env file found. Using default configuration.
    echo To configure API keys, copy env-example.txt to .env in the project root.
)

REM Set default environment variables for video processor if not already set
if not defined PROCESSOR_ID set "PROCESSOR_ID=processor-1"
if not defined PROCESSOR_HOST set "PROCESSOR_HOST=0.0.0.0"
if not defined PROCESSOR_PORT set "PROCESSOR_PORT=8090"
if not defined BACKEND_API_URL set "BACKEND_API_URL=http://localhost:8080"
if not defined REDIS_URL set "REDIS_URL=redis://localhost:6379"
if not defined REDIS_DB set "REDIS_DB=1"
if not defined OUTPUT_DIR set "OUTPUT_DIR=../output"
if not defined TEMP_DIR set "TEMP_DIR=./temp"
if not defined LOG_LEVEL set "LOG_LEVEL=INFO"

REM Set dummy API keys if not provided (for development only)
if not defined PEXELS_API_KEY set "PEXELS_API_KEY=dummy_pexels_key_for_dev"
if not defined GEMINI_API_KEY set "GEMINI_API_KEY=dummy_gemini_key_for_dev"

REM Start the video processor
start "VideoProcessor" cmd /c "python main.py"
cd ..

REM Wait for user input to keep the script running
echo All services started. Press any key to stop all services...
pause >nul

REM Cleanup when user presses a key
call :cleanup
