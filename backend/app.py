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
VENDOR_ROOT = get_backend_path("vendors")

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
    # Also support backend-local .env and vendor override
    backend_env = Path(__file__).resolve().parent / ".env"
    if backend_env.exists():
        load_dotenv(backend_env, override=True)
        print(f"[ENV] Loaded {backend_env}")
    vendor_env = VENDOR_ROOT / "moneyprinter" / ".env"
    if vendor_env.exists():
        load_dotenv(vendor_env, override=True)
        print(f"[ENV] Loaded {vendor_env}")

    # Verify critical keys are loaded
    gemini_key = os.getenv('GEMINI_API_KEY')
    if gemini_key:
        print(f"[ENV] GEMINI_API_KEY loaded (length: {len(gemini_key)})")
    else:
        print("[ENV] WARNING: GEMINI_API_KEY not found in environment!")
except Exception as e:
    print(f"[ENV] Error loading .env files: {e}")
    pass

# Early logger setup
import logging
early_logger = logging.getLogger("video_generator")
early_logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
early_logger.addHandler(handler)

# Global cleanup state
_SHUTDOWN_IN_PROGRESS = False
_CLEANUP_COMPLETED = False

# Setup espeak-ng environment for Kokoro TTS
def setup_espeak_environment():
    """Setup espeak-ng environment for Kokoro TTS."""
    # Clear potentially problematic espeakng_loader environment variables
    for key in ['ESPEAK_DATA_PATH', 'ESPEAKNG_DATA_PATH', 'PHONEMIZER_ESPEAK_DATA_PATH', 'PHONEMIZER_ESPEAK_LIBRARY']:
        if key in os.environ:
            del os.environ[key]

    # Use system espeak-ng if available
    system_espeak_paths = [
        '/opt/homebrew/bin/espeak-ng',  # Homebrew ARM64
        '/usr/local/bin/espeak-ng',    # Homebrew x86_64
        '/usr/bin/espeak-ng',          # System package (Linux)
        'C:\\Program Files\\eSpeak NG\\espeak-ng.exe',  # Windows winget installation
        'C:\\Program Files (x86)\\eSpeak NG\\espeak-ng.exe'  # Windows 32-bit
    ]

    system_espeak_data_paths = [
        '/opt/homebrew/share/espeak-ng-data',  # Homebrew ARM64
        '/usr/local/share/espeak-ng-data',    # Homebrew x86_64
        '/usr/share/espeak-ng-data',          # System package (Linux)
        'C:\\Program Files\\eSpeak NG\\espeak-ng-data',  # Windows winget installation
        'C:\\Program Files (x86)\\eSpeak NG\\espeak-ng-data'  # Windows 32-bit
    ]

    system_espeak = None
    system_data = None

    for espeak_path in system_espeak_paths:
        if os.path.exists(espeak_path):
            system_espeak = espeak_path
            break

    for data_path in system_espeak_data_paths:
        if os.path.exists(data_path):
            system_data = data_path
            break

    if system_espeak and system_data:
        os.environ['PHONEMIZER_ESPEAK_PATH'] = system_espeak
        os.environ['ESPEAK_DATA_PATH'] = system_data

        # For Windows, also add to PATH if it's not already there
        if system_espeak.startswith('C:\\Program Files'):
            espeak_dir = os.path.dirname(system_espeak)
            current_path = os.environ.get('PATH', '')
            if espeak_dir not in current_path:
                os.environ['PATH'] = espeak_dir + os.pathsep + current_path

        early_logger.info(f"✅ Configured system espeak-ng for Kokoro TTS:")
        early_logger.info(f"   ESPEAK_PATH: {system_espeak}")
        early_logger.info(f"   DATA_PATH: {system_data}")
    else:
        # Fallback to espeakng_loader if system installation not found
        try:
            import espeakng_loader  # type: ignore
            espeak_data_path = espeakng_loader.get_data_path()
            espeak_lib_path = espeakng_loader.get_library_path()
            if espeak_data_path and os.path.exists(espeak_data_path):
                os.environ['ESPEAK_DATA_PATH'] = espeak_data_path
                os.environ['PHONEMIZER_ESPEAK_DATA_PATH'] = espeak_data_path
            if espeak_lib_path and os.path.exists(espeak_lib_path):
                os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = espeak_lib_path
            early_logger.warning(f"⚠️  Using espeakng_loader (may have issues):")
            early_logger.warning(f"   DATA_PATH: {espeak_data_path}")
            early_logger.warning(f"   LIB_PATH: {espeak_lib_path}")
        except ImportError:
            early_logger.error("❌ Neither system espeak-ng nor espeakng_loader found - Kokoro TTS may not work")
            early_logger.error("   Install espeak-ng: brew install espeak-ng (macOS) or apt install espeak-ng (Ubuntu)")
        except Exception as e:
            early_logger.error(f"⚠️  Error setting up espeak-ng environment: {e}")

# Setup espeak environment
setup_espeak_environment()

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
