"""
New reorganized FastAPI application.

This is a cleaner version of app.py that uses the reorganized backend structure.
"""

import os
import sys
import atexit
import threading
from pathlib import Path

# Early setup for environment and paths
try:
    from backend.utils.paths import get_project_root, get_output_path, get_backend_path
except ImportError:
    # Fallback for when running from backend directory
    from utils.paths import get_project_root, get_output_path, get_backend_path

ROOT = get_project_root()
DEFAULT_OUTPUT_DIR = get_output_path()
os.environ.setdefault("VIDEOHELPER_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))

# Load environment variables early
try:
    from dotenv import load_dotenv  # type: ignore
    # Canonical: repository root .env (override existing variables)
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
        print(f"[ENV] Loaded {env_path}")
    # Legacy monorepo layout support
    try:
        legacy_env = (ROOT.parents[1] / ".env")
        if legacy_env.exists():
            load_dotenv(legacy_env, override=True)
            print(f"[ENV] Loaded {legacy_env}")
    except Exception:
        pass
    # Also support backend-local .env
    backend_env = Path(__file__).resolve().parent / ".env"
    if backend_env.exists():
        load_dotenv(backend_env, override=True)
        print(f"[ENV] Loaded {backend_env}")

    # Verify critical keys are loaded
    gemini_key = os.getenv('GEMINI_API_KEY')
    if gemini_key:
        print(f"[ENV] GEMINI_API_KEY loaded (length: {len(gemini_key)})")
    else:
        print("[ENV] WARNING: GEMINI_API_KEY not found in environment!")
except Exception as e:
    print(f"[ENV] Error loading .env files: {e}")
    pass

# Early logger setup with Loguru
from loguru import logger as early_logger

# Configure early logging
early_logger.remove()
early_logger.add(
    sys.stderr, 
    format="{time:YYYY-MM-DD HH:mm:ss} - {name} - {level} - {message}",
    level="INFO"
)

# Global cleanup state
_SHUTDOWN_IN_PROGRESS = False
_CLEANUP_COMPLETED = False

# NOTE: espeak-ng setup removed - TTS is now handled by video-processor service

# Windows console encoding setup for Unicode support
if sys.platform == "win32":
    try:
        import subprocess
        # Try to set console to UTF-8 mode
        subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
        # Also try to set environment variable
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    except Exception:
        pass

# Create the FastAPI application using the new factory
try:
    from backend.core import create_app, AppConfig
except ImportError:
    # Fallback for when running from backend directory
    from core import create_app, AppConfig

# Create app with configuration
config = AppConfig.from_env()
app = create_app(config)

# Initialize database and migrate existing data
try:
    from backend.database import get_job_store, migrate_from_json
except ImportError:
    # Fallback for when running from backend directory
    from database import get_job_store, migrate_from_json

JOBS_FILE = DEFAULT_OUTPUT_DIR / "jobs.json"
job_store = get_job_store()

if JOBS_FILE.exists():
    migrated = migrate_from_json(JOBS_FILE, job_store)
    if migrated > 0:
        early_logger.info(f"✅ Migrated {migrated} jobs from JSON to database")
        # Keep the JSON file as backup
        backup_file = JOBS_FILE.with_suffix(".json.backup")
        JOBS_FILE.rename(backup_file)
        early_logger.info(f"   Backed up original file to {backup_file}")

# Initialize unified job queue
try:
    from backend.job_queue_unified import get_job_queue
except ImportError:
    # Fallback for when running from backend directory
    from job_queue_unified import get_job_queue
job_queue = get_job_queue()

# Legacy compatibility for tests that expect app.JOBS
JOBS = {}  # Kept for backwards compatibility

# Cleanup management
def _atexit_cleanup_with_timeout():
    """Atexit cleanup wrapper with timeout to prevent hanging."""
    global _SHUTDOWN_IN_PROGRESS

    if _SHUTDOWN_IN_PROGRESS:
        return

    _SHUTDOWN_IN_PROGRESS = True

    def cleanup_worker():
        try:
            try:
                from backend.core.lifespan import _cleanup_resources
            except ImportError:
                from core.lifespan import _cleanup_resources
            _cleanup_resources()
        except Exception as e:
            early_logger.error(f"Error during atexit cleanup: {e}")

    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    cleanup_thread.join(timeout=10)

    if cleanup_thread.is_alive():
        early_logger.warning("Atexit cleanup timeout reached")

# Only register if not already shutting down
try:
    atexit.register(_atexit_cleanup_with_timeout)
except Exception:
    # atexit registration failed (interpreter shutting down)
    pass

# Entry point for running the application
if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run("backend.app_new:app", host=config.host, port=config.port, reload=config.reload)
    finally:
        if not _SHUTDOWN_IN_PROGRESS:
            _atexit_cleanup_with_timeout()
