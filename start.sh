#!/bin/bash

# AI Video Generator - Development Start Script
# 
# This script starts all three services:
# - Frontend (React/Vite) on port 5173
# - Backend (FastAPI) on port 9000  
# - Video Processor (FastAPI) on port 8090
#
# Prerequisites:
# 1. Create .venv: python3 -m venv .venv && source .venv/bin/activate
# 2. Install backend deps: pip install -r requirements.txt
# 3. Install video-processor deps: cd video-processor && pip install -r requirements.txt
# 4. Install frontend deps: cd frontend && npm install
# 5. Configure environment: cp env-example.txt .env and edit API keys
#
# Note: The script will run with dummy API keys if .env is not configured

# Function to kill all background processes when the script exits
cleanup() {
    echo "Shutting down all services..."
    kill $(jobs -p)
    exit
}

# Trap the EXIT signal to run the cleanup function
trap cleanup EXIT

# --- Frontend ---
echo "Starting frontend development server..."
cd frontend
if [ ! -d "node_modules" ]; then
  echo "Node modules not found. Running npm install..."
  npm install
fi
npm run dev &
cd ..

# --- Backend ---
echo "Starting backend server..."

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Python virtual environment not found. Please run:"
    echo "python3 -m venv .venv"
    echo "source .venv/bin/activate"
    echo "pip install -r requirements.txt"
    exit 1
fi

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    echo "Loading environment variables for backend from .env file..."
    set -a  # Mark all new/modified variables for export
    source .env
    set +a  # Stop auto-exporting
else
    echo "No .env file found in project root. Using default backend configuration."
fi

# Activate virtual environment and start the server
source .venv/bin/activate

# Set PYTHONPATH to include the project root so backend module can be imported
export PYTHONPATH="${PWD}:${PYTHONPATH}"

cd backend

python main.py &
cd ..

# --- Video Processor ---
echo "Starting video processor service..."

# Check if video-processor directory exists
if [ ! -d "video-processor" ]; then
    echo "Video processor directory not found!"
    exit 1
fi

cd video-processor

# Check if requirements are installed (optional check)
python -c "import fastapi, uvicorn" 2>/dev/null || {
    echo "Video processor dependencies not found. Please install requirements:"
    echo "pip install -r requirements.txt"
    echo "or"
    echo "pip install -r requirements.simple.txt"
}

# Load environment variables from project root .env if it exists
if [ -f "../.env" ]; then
    echo "Loading environment variables from .env file..."
    set -a  # Mark all new/modified variables for export
    source ../.env
    set +a  # Stop auto-exporting
else
    echo "No .env file found. Using default configuration."
    echo "To configure API keys, copy env-example.txt to .env in the project root."
fi

# Set default environment variables for video processor if not already set
export PROCESSOR_ID=${PROCESSOR_ID:-processor-1}
export PROCESSOR_HOST=${PROCESSOR_HOST:-0.0.0.0}
export PROCESSOR_PORT=${PROCESSOR_PORT:-8090}
export BACKEND_API_URL=${BACKEND_API_URL:-http://localhost:9000}
export REDIS_URL=${REDIS_URL:-redis://localhost:6379}
export REDIS_DB=${REDIS_DB:-1}
export OUTPUT_DIR=${OUTPUT_DIR:-../output}
export TEMP_DIR=${TEMP_DIR:-./temp}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

# Set dummy API keys if not provided (for development only)
export PEXELS_API_KEY=${PEXELS_API_KEY:-dummy_pexels_key_for_dev}
export GEMINI_API_KEY=${GEMINI_API_KEY:-dummy_gemini_key_for_dev}

# Start the video processor
python main.py &
cd ..

# Wait for all background processes to complete
wait
