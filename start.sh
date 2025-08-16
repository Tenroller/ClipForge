#!/usr/bin/env bash
set -euo pipefail

# Simple dev runner to start backend (FastAPI/Uvicorn) and frontend (Vite)
# - Backend on BACKEND_PORT (default 8080)
# - Frontend on FRONTEND_PORT (default 5173)
# Logs written to ./logs/

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo "\nStopping services..."
  if [[ -n "$FRONTEND_PID" ]] && ps -p "$FRONTEND_PID" >/dev/null 2>&1; then
    echo "- Stopping frontend (PID $FRONTEND_PID)"
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$BACKEND_PID" ]] && ps -p "$BACKEND_PID" >/dev/null 2>&1; then
    echo "- Stopping backend (PID $BACKEND_PID)"
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

start_backend() {
  echo "Starting backend..."
  if [[ ! -d "$BACKEND_DIR" ]]; then
    echo "ERROR: Backend directory not found at $BACKEND_DIR" >&2
    exit 1
  fi

  # Use the root virtual environment
  VENV_DIR="$ROOT_DIR/.venv"
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "- Creating Python venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1090
  source "$VENV_DIR/bin/activate"

  # Load env vars if present
  if [[ -f "$ROOT_DIR/.env" ]]; then
    echo "- Loading env from $ROOT_DIR/.env"
    set -a; source "$ROOT_DIR/.env"; set +a
  fi
  if [[ -f "$BACKEND_DIR/vendors/moneyprinter/.env" ]]; then
    echo "- Loading env from $BACKEND_DIR/vendors/moneyprinter/.env"
    set -a; source "$BACKEND_DIR/vendors/moneyprinter/.env"; set +a
  fi

  # Ensure database is always created in the root directory
  export DATABASE_PATH="$ROOT_DIR/jobs.db"

  # Install Python deps if key packages are missing
  if ! python -c "import fastapi, moviepy" >/dev/null 2>&1; then
    echo "- Installing Python dependencies (one-time or when changed)"
    pip install --upgrade pip >/dev/null
    pip install -r "$ROOT_DIR/requirements.txt"
  fi

  # Ensure espeak-ng data/library paths are discoverable (fixes 'phontab' not found)
  # Some bundles of espeak-ng on macOS can report a wrong data path compiled from CI.
  # We explicitly point phonemizer/espeak to the packaged paths provided by espeakng_loader.
  ESPEAK_DATA_PATH="$(python -c 'import espeakng_loader; print(espeakng_loader.get_data_path())' 2>/dev/null || true)"
  if [[ -n "$ESPEAK_DATA_PATH" && -d "$ESPEAK_DATA_PATH" ]]; then
    export ESPEAK_DATA_PATH="$ESPEAK_DATA_PATH"
    export ESPEAKNG_DATA_PATH="$ESPEAK_DATA_PATH"
    export PHONEMIZER_ESPEAK_DATA_PATH="$ESPEAK_DATA_PATH"
    ESPEAK_LIB="$(python -c 'import espeakng_loader; print(espeakng_loader.get_library_path())' 2>/dev/null || true)"
    if [[ -n "$ESPEAK_LIB" && -f "$ESPEAK_LIB" ]]; then
      export PHONEMIZER_ESPEAK_LIBRARY="$ESPEAK_LIB"
      # macOS: ensure the dynamic loader can locate the dylib
      export DYLD_LIBRARY_PATH="$(dirname "$ESPEAK_LIB"):${DYLD_LIBRARY_PATH:-}"
    fi
  fi

  mkdir -p "$ROOT_DIR/output"

  pushd "$BACKEND_DIR" >/dev/null
  echo "- Uvicorn on http://localhost:$BACKEND_PORT (logs: $LOG_DIR/backend.log)"
  # Use reload for dev convenience
  # Use tee to output to both console and log file
  uvicorn app:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload 2>&1 | \
    tee -a "$LOG_DIR/backend.log" &
  BACKEND_PID=$!
  popd >/dev/null
}

start_frontend() {
  echo "Starting frontend..."
  if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "ERROR: Frontend directory not found at $FRONTEND_DIR" >&2
    exit 1
  fi

  pushd "$FRONTEND_DIR" >/dev/null
  if [[ ! -d node_modules ]]; then
    echo "- Installing npm dependencies (one-time)"
    npm install --no-audit --no-fund
  fi

  echo "- Vite dev server on http://localhost:$FRONTEND_PORT (logs: $LOG_DIR/frontend.log)"
  # Pass port through to vite
  # Use tee to output to both console and log file
  npm run dev -- --port "$FRONTEND_PORT" 2>&1 | \
    tee -a "$LOG_DIR/frontend.log" &
  FRONTEND_PID=$!
  popd >/dev/null
}

echo "Root: $ROOT_DIR"
echo "Logs: $LOG_DIR"

start_backend
start_frontend

echo "\nServices launched:"
echo "- Backend:  http://localhost:$BACKEND_PORT (PID $BACKEND_PID)"
echo "- Frontend: http://localhost:$FRONTEND_PORT (PID $FRONTEND_PID)"
echo "Press Ctrl+C to stop both."

# Keep script running while children run
wait "$BACKEND_PID" "$FRONTEND_PID" || true


