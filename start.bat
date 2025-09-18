@echo off
setlocal enabledelayedexpansion

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

REM Check if venv exists
if not exist "venv" (
    echo Python virtual environment not found. Please run:
    echo python -m venv venv
    echo venv\Scripts\activate
    echo pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment and start the server
call venv\Scripts\activate.bat
cd backend

start "Backend" cmd /c "python main.py"

cd ..

REM Wait for user input to keep the script running
echo Both services started. Press any key to stop all services...
pause >nul

REM Cleanup when user presses a key
call :cleanup
