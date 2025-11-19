#!/bin/bash
# VideoHelper - Start all services (Backend, Frontend, Video Processor)

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Trap Ctrl+C and cleanup
trap cleanup INT TERM

cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"

    # Kill all background jobs
    jobs -p | xargs -r kill 2>/dev/null || true

    echo -e "${GREEN}All services stopped${NC}"
    exit 0
}

# Check if directories exist
if [ ! -d "backend" ]; then
    echo -e "${RED}Error: backend directory not found${NC}"
    exit 1
fi

if [ ! -d "frontend" ]; then
    echo -e "${RED}Error: frontend-next directory not found${NC}"
    exit 1
fi

if [ ! -d "video-processor" ]; then
    echo -e "${RED}Error: video-processor directory not found${NC}"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}   VideoHelper - Starting Services${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Start Backend (Port 9000)
echo -e "${BLUE}[Backend]${NC} Starting on port 9000..."
(
    python run_backend.py 2>&1 | while IFS= read -r line; do
        echo -e "${BLUE}[Backend]${NC} $line"
    done
) &
BACKEND_PID=$!
echo -e "${GREEN}[Backend]${NC} Started (PID: $BACKEND_PID)"

# Wait a moment for backend to initialize
sleep 10

# Start Video Processor (Port 8090)
echo -e "${MAGENTA}[Video-Processor]${NC} Starting on port 8090..."
(
    cd video-processor
    python main.py 2>&1 | while IFS= read -r line; do
        echo -e "${MAGENTA}[Video-Processor]${NC} $line"
    done
) &
VIDEO_PROCESSOR_PID=$!
echo -e "${GREEN}[Video-Processor]${NC} Started (PID: $VIDEO_PROCESSOR_PID)"

# Wait a moment for video processor to initialize
sleep 2

# Start Frontend (Port 3000)
echo -e "${CYAN}[Frontend]${NC} Starting on port 3000..."
(
    cd frontend
    npm run dev 2>&1 | while IFS= read -r line; do
        echo -e "${CYAN}[Frontend]${NC} $line"
    done
) &
FRONTEND_PID=$!
echo -e "${GREEN}[Frontend]${NC} Started (PID: $FRONTEND_PID)"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   All services started successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}Services:${NC}"
echo -e "  ${BLUE}Backend:${NC}         http://localhost:9000"
echo -e "  ${CYAN}Frontend:${NC}        http://localhost:3000"
echo -e "  ${MAGENTA}Video-Processor:${NC} http://localhost:8090"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for all background processes
wait
