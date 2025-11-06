@echo off
REM Start the video processor service standalone
REM This script starts only the video-processor without frontend or backend

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ========================================
echo  Starting Video Processor Service...
echo ========================================
echo.

REM Check if .env file exists
if not exist ".env" if not exist "..\\.env" (
    echo WARNING: No .env file found
    echo    The processor will use default settings
    echo.
)

REM Check for required Python packages
echo Checking Python environment...
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo FastAPI not found. Installing requirements...
    pip install -r requirements.txt
)

REM Check for required API keys
if "%GEMINI_API_KEY%"=="" if "%GOOGLE_API_KEY%"=="" (
    echo WARNING: GEMINI_API_KEY not set
    echo    MoneyPrinter workflow may not work without API key
)

if "%PEXELS_API_KEY%"=="" (
    echo WARNING: PEXELS_API_KEY not set
    echo    Stock video downloads may not work without API key
)

echo.
echo Environment ready
echo.
echo Service Configuration:
echo    Port: %PROCESSOR_PORT%
if "%PROCESSOR_PORT%"=="" echo    Port: 8090 (default)
echo    Max Concurrent Jobs: %PROCESSOR_MAX_CONCURRENT_JOBS%
if "%PROCESSOR_MAX_CONCURRENT_JOBS%"=="" echo    Max Concurrent Jobs: 2 (default)
echo    Output Directory: %OUTPUT_DIR%
if "%OUTPUT_DIR%"=="" echo    Output Directory: ./output (default)
echo.
echo API will be available at:
if "%PROCESSOR_PORT%"=="" (
    echo    http://localhost:8090
    echo    Health: http://localhost:8090/health
    echo    API Docs: http://localhost:8090/docs
) else (
    echo    http://localhost:%PROCESSOR_PORT%
    echo    Health: http://localhost:%PROCESSOR_PORT%/health
    echo    API Docs: http://localhost:%PROCESSOR_PORT%/docs
)
echo.
echo To test the processor, run in another terminal:
echo    python test_processor.py
echo.
echo ========================================
echo.

REM Start the processor
python main.py

pause
