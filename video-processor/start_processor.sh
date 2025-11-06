#!/bin/bash
# Start the video processor service standalone
# This script starts only the video-processor without frontend or backend

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🎬 Starting Video Processor Service..."
echo "========================================"

# Check if .env file exists
if [ ! -f ".env" ] && [ ! -f "../.env" ]; then
    echo "⚠️  Warning: No .env file found"
    echo "   The processor will use default settings"
    echo ""
fi

# Check for required Python packages
echo "📦 Checking Python environment..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "❌ FastAPI not found. Installing requirements..."
    pip install -r requirements.txt
fi

# Check for required API keys
if [ -z "$GEMINI_API_KEY" ] && [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠️  Warning: GEMINI_API_KEY not set"
    echo "   MoneyPrinter workflow may not work without API key"
fi

if [ -z "$PEXELS_API_KEY" ]; then
    echo "⚠️  Warning: PEXELS_API_KEY not set"
    echo "   Stock video downloads may not work without API key"
fi

echo ""
echo "✅ Environment ready"
echo ""
echo "📊 Service Configuration:"
echo "   Port: ${PROCESSOR_PORT:-8090}"
echo "   Max Concurrent Jobs: ${PROCESSOR_MAX_CONCURRENT_JOBS:-2}"
echo "   Output Directory: ${OUTPUT_DIR:-./output}"
echo ""
echo "🌐 API will be available at:"
echo "   http://localhost:${PROCESSOR_PORT:-8090}"
echo "   Health: http://localhost:${PROCESSOR_PORT:-8090}/health"
echo "   API Docs: http://localhost:${PROCESSOR_PORT:-8090}/docs"
echo ""
echo "🧪 To test the processor, run in another terminal:"
echo "   python test_processor.py"
echo ""
echo "========================================"
echo ""

# Start the processor
python3 main.py
