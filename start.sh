#!/bin/bash

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

# # Check if venv exists
# if [ ! -d "venv" ]; then
#     echo "Python virtual environment not found. Please run:"
#     echo "python3 -m venv venv"
#     echo "source venv/bin/activate"
#     echo "pip install -r ../requirements.txt"
#     exit 1
# fi

# Activate virtual environment and start the server
source venv/bin/activate
cd backend

python main.py &

# Wait for all background processes to complete
wait
