import os
import sys
import uuid
import json
import shutil
import contextlib
import signal
import atexit
from contextlib import asynccontextmanager
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

# Windows console encoding setup for Unicode support
if sys.platform == "win32":
    try:
        # Try to set console to UTF-8 mode
        import subprocess
        subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
        # Also try to set environment variable
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    except Exception:
        pass

import asyncio
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Depends, Header, Request, Cookie
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from collections import deque
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .validation import (
    validate_youtube_url, validate_subject, validate_custom_prompt,
    validate_zip_url, validate_color, validate_subtitle_position,
    validate_ai_model, validate_voice
)
from .logging_config import (
    get_logger, log_request, log_job_event, log_error, log_security_event,
    log_generation_step, log_api_call, log_file_operation, log_performance_metric
)
from .metrics import get_metrics, record_request_metrics, init_metrics_system, track_job_metrics
from .utils.error_handling import handle_error, create_error_response, ProcessingError, ResourceError



# Use centralized configuration and path management
from .core.config import AppConfig
from .utils.paths import get_project_root, get_output_path, get_backend_path

ROOT = get_project_root()
# Ensure a unified output directory for all generators
DEFAULT_OUTPUT_DIR = get_output_path()
os.environ.setdefault("VIDEOHELPER_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))
# Vendored copies live under backend/vendors/
# Use the current file's directory to locate the vendors folder reliably.
VENDOR_ROOT = get_backend_path("vendors")
MONEYPRINTER_BACKEND = VENDOR_ROOT / "moneyprinter"
BRAINROT_ROOT = VENDOR_ROOT / "brainrot"

# Load environment variables early so running uvicorn directly works consistently
try:
    from dotenv import load_dotenv  # type: ignore
    # Canonical: repository root .env
    load_dotenv((ROOT / ".env"))
    # Legacy monorepo layout support: attempt parent-of-root if it contains a .env next to old layout
    try:
        legacy_env = (ROOT.parents[1] / ".env")
        if legacy_env.exists():
            load_dotenv(legacy_env)
    except Exception:
        pass
    # Also support backend-local .env and vendor override for MoneyPrinter
    load_dotenv((Path(__file__).resolve().parent / ".env"))
    load_dotenv((MONEYPRINTER_BACKEND / ".env"))
except Exception:
    # python-dotenv is optional; env vars can be provided by shell or process manager
    pass

# Early logger for module-level initialization (will be replaced in lifespan)
import logging
early_logger = logging.getLogger("video_generator")
early_logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
early_logger.addHandler(handler)

logger = early_logger  # Use early logger until proper initialization

# Global flags to track shutdown and cleanup state
_SHUTDOWN_IN_PROGRESS = False
_CLEANUP_COMPLETED = False


# Setup espeak-ng environment for Kokoro TTS
# Clear potentially problematic espeakng_loader environment variables
for key in ['ESPEAK_DATA_PATH', 'ESPEAKNG_DATA_PATH', 'PHONEMIZER_ESPEAK_DATA_PATH', 'PHONEMIZER_ESPEAK_LIBRARY']:
    if key in os.environ:
        del os.environ[key]

# Use system espeak-ng if available (recommended for macOS with Homebrew, Linux, and Windows)
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

    logger.info(f"✅ Configured system espeak-ng for Kokoro TTS:")
    logger.info(f"   ESPEAK_PATH: {system_espeak}")
    logger.info(f"   DATA_PATH: {system_data}")
else:
    # Fallback to espeakng_loader if system installation not found
    try:
        import espeakng_loader
        espeak_data_path = espeakng_loader.get_data_path()
        espeak_lib_path = espeakng_loader.get_library_path()
        if espeak_data_path and os.path.exists(espeak_data_path):
            os.environ['ESPEAK_DATA_PATH'] = espeak_data_path
            os.environ['PHONEMIZER_ESPEAK_DATA_PATH'] = espeak_data_path
        if espeak_lib_path and os.path.exists(espeak_lib_path):
            os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = espeak_lib_path
        logger.warning(f"⚠️  Using espeakng_loader (may have issues):")
        logger.warning(f"   DATA_PATH: {espeak_data_path}")
        logger.warning(f"   LIB_PATH: {espeak_lib_path}")
    except ImportError:
        logger.error("❌ Neither system espeak-ng nor espeakng_loader found - Kokoro TTS may not work")
        logger.error("   Install espeak-ng: brew install espeak-ng (macOS) or apt install espeak-ng (Ubuntu)")
    except Exception as e:
        logger.error(f"⚠️  Error setting up espeak-ng environment: {e}")


def _is_interpreter_shutting_down():
    """Check if the Python interpreter is shutting down."""
    import sys
    try:
        # Check if the interpreter is shutting down
        return sys.is_finalizing()
    except AttributeError:
        # sys.is_finalizing() is Python 3.7+, fallback to checking thread count
        import threading
        return len(threading.enumerate()) <= 2  # Only main thread + daemon threads


def _signal_handler(signum, frame):
    """Signal handler for graceful shutdown."""
    global _SHUTDOWN_IN_PROGRESS
    _SHUTDOWN_IN_PROGRESS = True

    logger.info(f"Received signal {signum}, initiating graceful shutdown...")

    # Set a timeout for cleanup to prevent hanging
    import threading
    import time

    def cleanup_with_timeout():
        try:
            _cleanup_resources()
            logger.info("Cleanup completed successfully")
        except Exception as e:
            # Don't log "can't register atexit after shutdown" errors during import
            if "can't register atexit after shutdown" not in str(e):
                logger.error(f"Error during cleanup: {e}")

    # Run cleanup in a separate thread with timeout
    cleanup_thread = threading.Thread(target=cleanup_with_timeout, daemon=True)
    cleanup_thread.start()
    cleanup_thread.join(timeout=10)  # 10 second timeout

    if cleanup_thread.is_alive():
        logger.warning("Cleanup timeout reached, forcing exit")

    # Force exit after cleanup attempt
    logger.info("Shutdown complete, exiting")
    os._exit(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context to manage background broadcaster task."""
    global MAIN_LOOP, logger
    MAIN_LOOP = asyncio.get_running_loop()

    # Initialize logging system (only once per process)
    from .logging_config import initialize_logging
    logger = initialize_logging()

    # Initialize enhanced systems
    try:
        init_metrics_system()

        # Initialize utility systems
        from .utils.file_management import init_temp_manager, cleanup_temp_files_on_startup
       
        from .utils.streaming_processor import init_streaming_processor
        from .utils.fonts import init_font_manager
        from .utils.paths import init_path_manager
        from .utils.gpu_manager import init_gpu_manager

        init_temp_manager()
        cleanup_temp_files_on_startup()
        init_streaming_processor()
        init_font_manager()
        init_path_manager()
        init_gpu_manager()

        logger.info("✅ All systems initialized")
    except Exception as e:
        logger.error(f"Failed to initialize enhanced systems: {e}")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    async def _broadcast_loop():
        while True:
            try:
                job_id, payload = await ASYNC_QUEUE.get()
            except asyncio.CancelledError:
                # Exit cleanly on shutdown
                break

    broadcaster_task = asyncio.create_task(_broadcast_loop())
    try:
        yield
    finally:
        broadcaster_task.cancel()
        # In Python 3.12+ asyncio.CancelledError may not inherit from Exception
        try:
            await asyncio.wait_for(broadcaster_task, timeout=3.0)  # 3 second timeout
        except asyncio.TimeoutError:
            logger.warning("Broadcaster task cleanup timeout reached")
        except Exception:
            pass  # Other exceptions are fine to ignore during shutdown
        
        # Cleanup multiprocessing resources to prevent semaphore leaks
        if not _is_interpreter_shutting_down():
            try:
                # Use the simplified cleanup function with timeout
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: _cleanup_multiprocessing_resources())
                    try:
                        future.result(timeout=5)  # 5 second timeout
                        logger.debug("Multiprocessing resources cleaned up")
                    except concurrent.futures.TimeoutError:
                        logger.warning("Multiprocessing cleanup timeout reached")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup multiprocessing resources: {e}")
            except Exception as e:
                logger.warning(f"Failed to cleanup multiprocessing resources: {e}")
        else:
            logger.debug("Interpreter shutting down, skipping multiprocessing cleanup")

        # Cleanup threading resources
        if not _is_interpreter_shutting_down():
            try:
                # Release the job semaphore with timeout
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: JOB_SEMAPHORE.release())
                    try:
                        future.result(timeout=2)  # 2 second timeout
                        logger.debug("Threading resources cleaned up")
                    except concurrent.futures.TimeoutError:
                        logger.warning("Threading cleanup timeout reached")
                    except ValueError:
                        # Semaphore is already at maximum value, which is fine
                        logger.debug("Threading resources already cleaned up")
                    except Exception:
                        pass  # Other exceptions are fine to ignore during shutdown
            except Exception:
                pass  # Semaphore might already be released
        else:
            logger.debug("Interpreter shutting down, skipping threading cleanup")

        # Cleanup any remaining WebSocket connections
        try:
            active_connections = sum(len(subscribers) for subscribers in WS_SUBSCRIBERS.values())
            if active_connections > 0:
                logger.info(f"Cleaning up {active_connections} WebSocket connections...")

                # Close all WebSocket connections
                for subscribers in WS_SUBSCRIBERS.values(): 
                    for websocket in subscribers:
                        await websocket.close()
            else:
                logger.debug("No active WebSocket connections found")
        except Exception as e:
            logger.warning(f"Failed to cleanup WebSocket connections: {e}")

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging and monitoring."""

    async def dispatch(self, request: Request, call_next):
        import uuid
        start_time = time.time()
        request_id = str(uuid.uuid4())[:8]  # Short request ID for tracking

        # Extract request details
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = str(request.url.path)
        query_params = str(request.url.query)
        user_agent = request.headers.get("User-Agent", "")
        content_length = request.headers.get("Content-Length", "0")

        # Log request start with detailed info
        logger.debug(
            f"REQUEST START: {request_id} | {method} {path} | IP: {client_ip} | UA: {user_agent[:50]}...",
            extra={
                "request_id": request_id,
                "http_request": True,
                "request_start": True
            }
        )

        response = None
        status_code = 500
        response_size = 0

        try:
            response = await call_next(request)
            status_code = response.status_code
            # Try to get response size if available
            if hasattr(response, 'headers') and 'Content-Length' in response.headers:
                response_size = int(response.headers.get('Content-Length', 0))
        except Exception as e:
            # Use standardized error handling
            error_info = handle_error(e, {
                "path": path,
                "method": method,
                "client_ip": client_ip,
                "endpoint": "middleware",
                "request_id": request_id
            })
            raise
        finally:
            # Log request completion with comprehensive details
            duration = time.time() - start_time
            request_size = int(content_length) if content_length.isdigit() else 0

            log_request(
                logger, method, path, status_code, duration, client_ip,
                request_size=request_size, response_size=response_size,
                user_agent=user_agent, request_id=request_id
            )

            # Record metrics
            record_request_metrics(method, path, status_code, duration)

            # Log slow requests with performance details
            if duration > 5.0:
                log_performance_metric(
                    logger, "slow_request_duration", duration, "seconds",
                    method=method, path=path, status_code=status_code,
                    request_id=request_id
                )

            # Enhanced security event logging
            if status_code == 401:
                log_security_event(
                    logger, "unauthorized_access", client_ip,
                    f"{method} {path} | Request-ID: {request_id} | UA: {user_agent[:50]}..."
                )
            elif status_code == 429:
                log_security_event(
                    logger, "rate_limit_exceeded", client_ip,
                    f"{method} {path} | Request-ID: {request_id} | Rate limited"
                )
            elif status_code >= 500:
                logger.error(
                    f"Server error: {method} {path} -> {status_code} ({duration:.3f}s)",
                    extra={
                        "request_id": request_id,
                        "server_error": True,
                        "error_status": status_code
                    }
                )

        return response


app = FastAPI(
    title="AI Video Generator API",
    description="""
    A comprehensive API for generating videos using AI-powered workflows.
    
    ## Features
    
    * **MoneyPrinter Workflow**: Generate videos from text prompts using AI script generation, stock footage, and TTS
    * **Brainrot Workflow**: Create TikTok-style compilations from YouTube videos
    * **Real-time Progress**: WebSocket support for live job updates
    * **Job Management**: Persistent job storage with SQLite/PostgreSQL support
    * **Security**: Rate limiting
    * **Monitoring**: Comprehensive logging and error tracking
    
    ## Rate Limiting
    
    If enabled via `RATE_LIMIT_PER_MINUTE`, endpoints are rate-limited per IP address.
    
    ## WebSocket Support
    
    Connect to `/ws/jobs/{job_id}` for real-time job progress updates.
    """,
    version="1.0.0",
    contact={
        "name": "AI Video Generator",
        "url": "https://github.com/your-repo",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan
)


# Add security middleware
trusted_hosts = os.getenv("TRUSTED_HOSTS", "*").split(",")
if trusted_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Sentry (optional) — enable if SENTRY_DSN is set
try:
    import sentry_sdk  # type: ignore
    from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
    _sentry_dsn = os.getenv("SENTRY_DSN")
    if _sentry_dsn:
        sentry_sdk.init(
            dsn=_sentry_dsn,
            integrations=[FastApiIntegration()],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0")),
        )
except Exception:
    # Sentry is optional; ignore any initialization/import failure
    pass

# Configurable CORS
_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
if _cors_origins_env.strip() == "*":
    # Default dev-friendly origins so we can enable credentials for cookies
    _allow_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:9000",
        "http://127.0.0.1:9000",
    ]
    _allow_credentials = True
else:
    _allow_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MoneyPrinterRequest(BaseModel):
    videoSubject: str
    aiModel: str = "gemini-2.0-flash"
    paragraphNumber: int = Field(default=1, ge=1, le=10)
    threads: Optional[int] = Field(default=None, ge=1, le=16)
    subtitlesPosition: str = "center,bottom"
    color: str = "#FFFF00"
    useMusic: bool = False
    zipUrl: Optional[str] = None
    automateYoutubeUpload: bool = False
    useGPU: bool = True
    voice: str = "af_bella"
    customPrompt: Optional[str] = None
    
    # Enhanced subtitle options
    useTikTokSubtitles: bool = False
    useWhisperEnhanced: bool = False  # Use Whisper for precise word timing
    whisperModel: str = "base"  # Whisper model size: tiny, base, small, medium, large
    subtitleFont: str = "Arial-Bold"
    subtitleFontSize: int = Field(default=48, ge=20, le=100)
    subtitleDefaultColor: str = "#FFFFFF"
    subtitleHighlightColor: str = "#FFFFFF"  # Changed to white for new style
    subtitleStrokeColor: str = "#000000"
    subtitleBackgroundColor: str = "#000000"
    subtitleStrokeWidth: int = Field(default=0, ge=0, le=10)  # Disabled for new style
    subtitleBackgroundOpacity: float = Field(default=0.0, ge=0.0, le=1.0)  # Disabled for new style
    subtitlePaddingX: int = Field(default=20, ge=0, le=50)  # Increased padding
    subtitlePaddingY: int = Field(default=16, ge=0, le=50)
    
    # 3D Blue Shadow Layers for Enhanced Subtitles
    shadowLayersCount: int = Field(default=4, ge=2, le=4)  # Number of shadow layers (2, 3, or 4)
    shadowLayer1Color: str = "#4A90E2"  # Light blue (closest to text)
    shadowLayer2Color: str = "#357ABD"  # Medium blue
    shadowLayer3Color: str = "#2E5F8A"  # Dark blue
    shadowLayer4Color: str = "#1E3F5A"  # Darkest blue (furthest from text)
    
    # Shared content fields for benchmarking (optional)
    shared_content: Optional[bool] = Field(default=False)
    shared_content_dir: Optional[str] = Field(default=None)
    shared_script: Optional[str] = Field(default=None)
    shared_search_terms: Optional[List[str]] = Field(default=None)
    shared_sentences: Optional[List[str]] = Field(default=None)
    shared_voice: Optional[str] = Field(default=None)
    shared_stock_videos: Optional[List[str]] = Field(default=None)
    shared_tts_path: Optional[str] = Field(default=None)
    shared_subtitles_path: Optional[str] = Field(default=None)
    shared_manifest: Optional[Dict[str, Any]] = Field(default=None)

    @field_validator('videoSubject')
    @classmethod
    def validate_subject_field(cls, v):
        return validate_subject(v)

    @field_validator('aiModel')
    @classmethod
    def validate_ai_model_field(cls, v):
        return validate_ai_model(v)

    @field_validator('voice')
    @classmethod
    def validate_voice_field(cls, v):
        return validate_voice(v)

    @field_validator('color')
    @classmethod
    def validate_color_field(cls, v):
        return validate_color(v)

    @field_validator('subtitlesPosition')
    @classmethod
    def validate_subtitle_position_field(cls, v):
        return validate_subtitle_position(v)

    @field_validator('zipUrl')
    @classmethod
    def validate_zip_url_field(cls, v):
        return validate_zip_url(v)

    @field_validator('customPrompt')
    @classmethod
    def validate_custom_prompt_field(cls, v):
        return validate_custom_prompt(v)
    
    @field_validator('subtitleFont')
    @classmethod
    def validate_subtitle_font_field(cls, v):
        from validation import validate_subtitle_font
        return validate_subtitle_font(v)
    
    @field_validator('subtitleDefaultColor', 'subtitleHighlightColor', 'subtitleStrokeColor', 'subtitleBackgroundColor', 'shadowLayer1Color', 'shadowLayer2Color', 'shadowLayer3Color', 'shadowLayer4Color')
    @classmethod
    def validate_subtitle_color_fields(cls, v):
        return validate_color(v)
    
    @field_validator('subtitleBackgroundOpacity')
    @classmethod
    def validate_subtitle_opacity_field(cls, v):
        from validation import validate_subtitle_opacity
        return validate_subtitle_opacity(v)


class BrainrotRequest(BaseModel):
    youtubeUrl: Optional[str] = Field(default=None, description="YouTube URL to download and process")
    uploadedVideoPath: Optional[str] = Field(default=None, description="Path to uploaded video file (alternative to YouTube URL)")
    numCompilations: int = Field(default=1, ge=1)
    minDuration: int = Field(default=60, ge=10, le=3600)
    maxDuration: int = Field(default=110, ge=10, le=3600)
    maxReuse: int = Field(default=3, ge=1)
    unlimited: bool = Field(default=False)

    @field_validator('youtubeUrl')
    @classmethod
    def validate_youtube_url_field(cls, v):
        if v is not None:
            return validate_youtube_url(v)
        return v
        
    @field_validator('uploadedVideoPath')
    @classmethod
    def validate_uploaded_video_path(cls, v):
        if v is not None:
            from .validation import validate_video_file_path
            return validate_video_file_path(v)
        return v
        
    def model_post_init(self, __context) -> None:
        """Ensure exactly one of youtubeUrl or uploadedVideoPath is provided"""
        if not self.youtubeUrl and not self.uploadedVideoPath:
            raise ValueError("Either youtubeUrl or uploadedVideoPath must be provided")
        if self.youtubeUrl and self.uploadedVideoPath:
            raise ValueError("Cannot provide both youtubeUrl and uploadedVideoPath - choose one input method")




from .database import get_job_store, migrate_from_json
from .job_queue_unified import get_job_queue, update_job_progress

# Legacy file-based storage for migration
JOBS_FILE = DEFAULT_OUTPUT_DIR / "jobs.json"

# Initialize database and migrate existing data
job_store = get_job_store()
if JOBS_FILE.exists():
    migrated = migrate_from_json(JOBS_FILE, job_store)
    if migrated > 0:
        logger.info(f"✅ Migrated {migrated} jobs from JSON to database")
        # Keep the JSON file as backup
        backup_file = JOBS_FILE.with_suffix(".json.backup")
        JOBS_FILE.rename(backup_file)
        logger.info(f"   Backed up original file to {backup_file}")

# Initialize unified job queue
job_queue = get_job_queue()

# System initialization moved to lifespan startup to avoid duplicates

# Remove old job loading/saving functions as they're now handled by database

# WebSocket pub-sub for job updates
WS_SUBSCRIBERS: Dict[str, set] = defaultdict(set)
ASYNC_QUEUE: "asyncio.Queue[tuple[str, Dict[str, Any]]]" = asyncio.Queue()
MAIN_LOOP: "asyncio.AbstractEventLoop | None" = None
# Use centralized configuration
config = AppConfig.from_env()
max_concurrent_jobs = config.max_concurrent_jobs
JOB_SEMAPHORE = threading.Semaphore(max(1, max_concurrent_jobs))
# Backwards-compat in tests that patch `app.JOBS`
JOBS: Dict[str, Dict[str, Any]] = {}

# Simple optional in-memory rate limiter (per minute)
RATE_LIMIT_PER_MIN = getattr(config, 'rate_limit_per_minute', 0)
RATE_LIMIT_BUCKETS: Dict[str, deque] = defaultdict(deque)  # key: f"{bucket}:{ip}"
RATE_LIMIT_LOCK = threading.Lock()

def _enqueue_job_update(job_id: str) -> None:
    """Thread-safe enqueue of a job update for websocket broadcast."""
    global MAIN_LOOP
    try:
        # Get job data from unified queue (which includes database data)
        payload = job_queue.get_job_status(job_id)
        if payload and MAIN_LOOP is not None:
            MAIN_LOOP.call_soon_threadsafe(ASYNC_QUEUE.put_nowait, (job_id, payload))
    except Exception:
        # Best-effort only
        pass



def _update_job(job_id: str, **fields: Any) -> None:
    """Update job in unified queue (which handles database persistence)."""
    # Handle special fields that need queue-specific processing
    if 'logs' in fields and fields['logs']:
        # Add log message to queue
        job_queue.update_job_progress(job_id, fields.get('step', ''), fields['logs'][-1])
        fields.pop('logs')  # Remove from database update

    if 'step' in fields:
        job_queue.update_job_progress(job_id, fields['step'])
        fields.pop('step')  # Remove from database update

    # Update database directly for remaining fields
    if fields:
        job_store.update_job(job_id, **fields)

    _enqueue_job_update(job_id)


def _check_cancel(job_id: str) -> None:
    """Check if job has been cancelled."""
    # The unified queue handles cancellation internally
    status = job_queue.get_job_status(job_id)
    if status and status.get('status') == 'cancelled':
        raise RuntimeError("cancelled")


# Database handles persistence automatically


@contextlib.contextmanager
def pushd(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def ensure_on_path(path: Path):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)




@app.get("/api/health", tags=["System"], summary="Health Check")
def health():
    return {
        "status": "ok",
        "cwd": str(Path.cwd()),
        "root": str(ROOT),
        "moneyprinter_present": MONEYPRINTER_BACKEND.exists(),
        "brainrot_present": BRAINROT_ROOT.exists(),
    }




@app.post(
    "/api/moneyprinter/generate",
    tags=["Video Generation"],
    summary="Generate AI Video",
    description="""
    Create a video using AI-powered script generation, stock footage, and text-to-speech.

    This endpoint starts a video generation job and returns immediately with a job ID.
    Use the job ID to track progress via WebSocket or polling.

    **Process Overview:**
    1. Generate script from subject using AI model
    2. Extract search terms for stock footage
    3. Download relevant stock videos
    4. Generate text-to-speech audio
    5. Create subtitles
    6. Compose final video with audio and subtitles

    **Required Environment Variables:**
    - `PEXELS_API_KEY`: For stock video search
    - `GEMINI_API_KEY`: For AI script generation

    """
)
def moneyprinter_generate(
    req: MoneyPrinterRequest,
):

    job_id = str(uuid.uuid4())

    # Log request parameters with enhanced details
    logger.debug(f"MoneyPrinter request parameters: useTikTokSubtitles={req.useTikTokSubtitles}, subtitleFont={req.subtitleFont}, voice={req.voice}, aiModel={req.aiModel}")

    log_job_event(logger, job_id, "moneyprinter", "created",
                subject=req.videoSubject[:100], voice=req.voice, ai_model=req.aiModel)
    
    # Create progress tracker and initial logs immediately
    from utils.progress_tracker import get_progress_tracker
    tracker = get_progress_tracker(job_id)
    tracker.add_log("MoneyPrinter job created and queued for processing", "info", "moneyprinter")
    tracker.add_log(f"Configuration: {req.aiModel} model, {req.voice} voice, {req.paragraphNumber} paragraphs", "info", "config")
    
    # Use unified queue for job management
    job_queue.add_job(
        _run_moneyprinter_job,
        job_id,
        req,
        workflow="moneyprinter"
    )
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            job = job_store.get_job(job_id)
            if job:
                log_job_event(logger, job_id, "moneyprinter", "persisted_to_db", attempt=attempt)
                break
            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff
        except Exception as db_e:
            logger.warning(f"Database persistence check failed for job {job_id}, attempt {attempt + 1}: {db_e}",
                          extra={"job_id": job_id, "attempt": attempt, "db_error": str(db_e)})
            if attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))

    return {"status": "queued", "jobId": job_id}

def _run_moneyprinter_job(job_id: str, req: MoneyPrinterRequest):
    """Execute MoneyPrinter video generation job."""
    generation_logger = get_logger("video_generator.generation")
    start_time = time.time()

    try:
        log_job_event(generation_logger, job_id, "moneyprinter", "started_processing")
        _update_job(job_id, started_at=datetime.now(timezone.utc).isoformat())

        # Log job parameters for debugging
        log_job_event(generation_logger, job_id, "moneyprinter", "job_parameters",
                     subject=req.videoSubject[:100], voice=req.voice, ai_model=req.aiModel,
                     use_music=req.useMusic, use_subtitles=req.useTikTokSubtitles,
                     paragraphs=req.paragraphNumber)

        log_generation_step(generation_logger, job_id, "moneyprinter", "setup_environment", "started")

        from vendors.AIvideos.utils import fetch_songs, check_env_vars
        from vendors.AIvideos.gpt import generate_script, get_search_terms
        from vendors.AIvideos.search import search_for_stock_videos
        from vendors.AIvideos.tiktokvoice import tts
        from vendors.AIvideos.video import generate_subtitles, combine_videos, generate_video
        from vendors.AIvideos.video import save_video as mp_save_video
        from moviepy import AudioFileClip, CompositeAudioClip, VideoFileClip, concatenate_audioclips  # type: ignore
        from pathlib import Path
        import shutil

        log_generation_step(generation_logger, job_id, "moneyprinter", "validate_env", "started")
        _update_job(job_id, step="validate_env")
        update_job_progress(job_id, "validate_env", "validate_env: checking AIvideos environment variables")

        try:
            check_env_vars()
            log_generation_step(generation_logger, job_id, "moneyprinter", "validate_env", "completed")
        except SystemExit:
            log_generation_step(generation_logger, job_id, "moneyprinter", "validate_env", "failed",
                              error="Missing required AIvideos environment variables")
            raise RuntimeError("Missing required AIvideos environment variables")

        _check_cancel(job_id)
        print(f"DEBUG: Job {job_id} - About to check music settings")
        if req.useMusic and req.zipUrl:
            log_generation_step(generation_logger, job_id, "moneyprinter", "fetch_music", "started",
                              zip_url=req.zipUrl)
            _update_job(job_id, step="fetch_music")
            update_job_progress(job_id, "fetch_music", f"fetch_music: downloading songs from zipUrl={req.zipUrl}")

            music_start = time.time()
            fetch_songs(req.zipUrl)
            music_duration = time.time() - music_start

            log_generation_step(generation_logger, job_id, "moneyprinter", "fetch_music", "completed",
                              duration=music_duration)
        else:
            print(f"DEBUG: Job {job_id} - Skipping music (useMusic={req.useMusic}, zipUrl={req.zipUrl})")
                    
        print(f"DEBUG: Job {job_id} - About to check shared content")

        # Check if this is a shared content benchmark request
        use_shared_content = hasattr(req, '_shared_content') and getattr(req, '_shared_content', False)
        print(f"DEBUG: Job {job_id} - Shared content check: use_shared_content={use_shared_content}")
        if use_shared_content:
                logger.info(f"[AIvideos_generate] Job {job_id}: Step benchmark - using shared content for identical testing")
                update_job_progress(job_id, "benchmark", "benchmark: using shared content for identical testing")
                
                # Extract shared content from request
                shared_script = getattr(req, '_shared_script', None)
                shared_terms = getattr(req, '_shared_search_terms', [])
                shared_sentences = getattr(req, '_shared_sentences', [])
                shared_video_paths = getattr(req, '_shared_stock_videos', [])
                shared_tts_path = getattr(req, '_shared_tts_path', None)
                
                if not shared_script or not shared_video_paths or not shared_tts_path:
                    raise RuntimeError("Incomplete shared content provided")
                
                logger.info(f"[AIvideos_generate] Job {job_id}: Step benchmark - shared content loaded - {len(shared_video_paths)} videos, script length: {len(shared_script)}")
                update_job_progress(job_id, "benchmark", f"benchmark: shared content loaded - {len(shared_video_paths)} videos, script length: {len(shared_script)}")
                
                # Skip content generation steps and use shared content
                script = shared_script
                terms = shared_terms
                sentences = shared_sentences
                video_paths = shared_video_paths
                tts_path = shared_tts_path
                
                # Copy shared audio to temp for processing  
                temp_dir = Path("../temp")
                temp_dir.mkdir(exist_ok=True)
                temp_tts_path = temp_dir / f"{uuid.uuid4()}.mp3"
                shutil.copy2(shared_tts_path, temp_tts_path)
                tts_path = str(temp_tts_path)
                temp_audio_files = [tts_path]
                
                # Create audio clips for subtitles
                audio_clips = [AudioFileClip(tts_path)]
                
                logger.info(f"[AIvideos_generate] Job {job_id}: Step benchmark - skipped content generation, proceeding to video assembly")
                update_job_progress(job_id, "benchmark", "benchmark: skipped content generation, proceeding to video assembly")
                
                
                
        else:
            # Normal content generation path
            _check_cancel(job_id)
            logger.info(f"[AIvideos_generate] Job {job_id}: Step script_generation - model={req.aiModel} voice={req.voice} paragraphs={req.paragraphNumber}")
            _update_job(job_id, step="script_generation")
            update_job_progress(job_id, "script_generation", f"script_generation: model={req.aiModel} voice={req.voice} paragraphs={req.paragraphNumber}")
            script = generate_script(req.videoSubject, req.paragraphNumber, req.aiModel, req.voice, req.customPrompt or "")
            if not script:
                raise RuntimeError("Script generation failed")
                
                

                _check_cancel(job_id)
                logger.info(f"[AIvideos_generate] Job {job_id}: Step search_terms - extracting search terms from script")
                _update_job(job_id, step="search_terms")
                terms = get_search_terms(req.videoSubject, 10, script, req.aiModel)
                update_job_progress(job_id, "search_terms", f"search_terms: {len(terms)} terms -> {terms[:5]}{'...' if len(terms) > 5 else ''}")
                
                

                _check_cancel(job_id)
                logger.info(f"[AIvideos_generate] Job {job_id}: Step stock_download - downloading stock videos for terms")
                _update_job(job_id, step="stock_download")

                # Download several videos per term locally, filter by duration >= 4
                video_paths: list[str] = []
                # Create temp directory in the project root
                temp_dir = ROOT / "temp"
                temp_dir.mkdir(exist_ok=True)
                
                for term in terms:
                    urls = search_for_stock_videos(term, os.getenv("PEXELS_API_KEY", ""), 5, 4)
                    for url in urls[:2]:
                        _check_cancel(job_id)
                        try:
                            local_path = mp_save_video(url, directory=str(temp_dir))
                            video_paths.append(local_path)
                        except Exception:
                            logger.warning(f"[AIvideos_generate] Job {job_id}: Failed to download video for url {url}")
                            continue
                if not video_paths:
                    logger.error(f"[AIvideos_generate] Job {job_id}: No stock videos downloaded")
                    raise RuntimeError("No stock videos downloaded")
                else:
                    logger.info(f"[AIvideos_generate] Job {job_id}: Downloaded {len(video_paths)} stock video clips")
                    update_job_progress(job_id, "stock_download", f"stock_download: downloaded {len(video_paths)} clips")
                    
                
                _check_cancel(job_id)
                logger.info(f"[AIvideos_generate] Job {job_id}: Step tts - generating audio segments using voice={req.voice}")
                _update_job(job_id, step="tts")
                update_job_progress(job_id, "tts", f"tts: generating {len([s for s in script.split('. ') if s])} audio segments using voice={req.voice}")
                sentences = [s for s in script.split(". ") if s]
                audio_clips = []
                temp_dir = ROOT / "temp"
                temp_dir.mkdir(exist_ok=True)
                    
                temp_audio_files = []
                for s in sentences:
                    _check_cancel(job_id)
                    current_tts_path = temp_dir / f"{uuid.uuid4()}.mp3"
                    tts(s, req.voice, filename=str(current_tts_path))
                    audio_clips.append(AudioFileClip(str(current_tts_path)))
                    temp_audio_files.append(str(current_tts_path))

                if not audio_clips:
                    logger.error(f"[AIvideos_generate] Job {job_id}: No audio clips generated")
                    raise RuntimeError("No audio clips generated")

                tts_path = str(temp_dir / f"{uuid.uuid4()}.mp3")
                concatenate_audioclips(audio_clips).write_audiofile(tts_path)
                temp_audio_files.append(tts_path)
                logger.info(f"[AIvideos_generate] Job {job_id}: TTS concatenated audio -> {tts_path}")
                update_job_progress(job_id, "tts", f"tts: concatenated audio -> {tts_path}")
                    
                    

                _check_cancel(job_id)
                logger.info(f"[AIvideos_generate] Job {job_id}: Step subtitles - generating subtitles")
                _update_job(job_id, step="subtitles")
                
                # Choose subtitle generation method based on request

                # uuid is already imported at the top
                subtitles_path = None
                try:
                    if req.useTikTokSubtitles:
                        if req.useWhisperEnhanced:
                            from vendors.AIvideos.whisper_enhanced_subtitles import generate_enhanced_subtitles_with_optional_whisper
                            subtitle_config = {
                                'font_family': req.subtitleFont,
                                'font_size': req.subtitleFontSize,
                                'default_color': req.subtitleDefaultColor,
                                'highlight_color': req.subtitleHighlightColor,
                                'stroke_color': req.subtitleStrokeColor,
                                'background_color': req.subtitleBackgroundColor,
                                'stroke_width': req.subtitleStrokeWidth,
                                'background_opacity': req.subtitleBackgroundOpacity,
                                'padding_x': req.subtitlePaddingX,
                                'padding_y': req.subtitlePaddingY,
                                'position': req.subtitlesPosition,
                                'shadow_layers_count': req.shadowLayersCount,
                                'shadow_layer_1_color': req.shadowLayer1Color,
                                'shadow_layer_2_color': req.shadowLayer2Color,
                                'shadow_layer_3_color': req.shadowLayer3Color,
                                'shadow_layer_4_color': req.shadowLayer4Color,
                                # Add job_id to output filename for traceability
                                'output_path': f"subtitles/{job_id}_whisper_enhanced.json"
                            }
                            subtitles_path = generate_enhanced_subtitles_with_optional_whisper(
                                sentences=sentences,
                                audio_clips=audio_clips,
                                audio_path=str(tts_path) if tts_path else None,
                                use_whisper=True,
                                whisper_model=req.whisperModel,
                                config=subtitle_config,
                                video_size=(1080, 1920)
                            )
                            logger.info(f"[AIvideos_generate] Job {job_id}: Subtitles - using Whisper-enhanced TikTok-style subtitles -> {subtitles_path}")
                            update_job_progress(job_id, "subtitles", f"subtitles: using Whisper-enhanced TikTok-style subtitles -> {subtitles_path}")
                        else:
                            from vendors.AIvideos.enhanced_subtitles import generate_enhanced_subtitles, SubtitleConfig
                            subtitle_config_dict = {
                                'font_family': req.subtitleFont,
                                'font_size': req.subtitleFontSize,
                                'default_color': req.subtitleDefaultColor,
                                'highlight_color': req.subtitleHighlightColor,
                                'stroke_color': req.subtitleStrokeColor,
                                'background_color': req.subtitleBackgroundColor,
                                'stroke_width': req.subtitleStrokeWidth,
                                'background_opacity': req.subtitleBackgroundOpacity,
                                'padding_x': req.subtitlePaddingX,
                                'padding_y': req.subtitlePaddingY,
                                'position': req.subtitlesPosition,
                                'shadow_layers_count': req.shadowLayersCount,
                                'shadow_layer_1_color': req.shadowLayer1Color,
                                'shadow_layer_2_color': req.shadowLayer2Color,
                                'shadow_layer_3_color': req.shadowLayer3Color,
                                'shadow_layer_4_color': req.shadowLayer4Color
                            }
                            subtitle_config = SubtitleConfig(**subtitle_config_dict)
                            output_path = f"subtitles/{job_id}_enhanced.json"
                            subtitles_path = generate_enhanced_subtitles(
                                sentences=sentences,
                                audio_clips=audio_clips,
                                config=subtitle_config,
                                video_size=(1080, 1920),
                                output_path=output_path
                            )
                            logger.info(f"[AIvideos_generate] Job {job_id}: Subtitles - using TikTok-style enhanced subtitles -> {subtitles_path}")
                            update_job_progress(job_id, "subtitles", f"subtitles: using TikTok-style enhanced subtitles -> {subtitles_path}")
                    else:
                        if not tts_path:
                            raise RuntimeError("TTS path is required for subtitle generation")
                        subtitles_path = generate_subtitles(audio_path=str(tts_path), sentences=sentences, audio_clips=audio_clips, voice=req.voice)
                        logger.info(f"[AIvideos_generate] Job {job_id}: Subtitles - using traditional subtitles -> {subtitles_path}")
                        update_job_progress(job_id, "subtitles", f"subtitles: using traditional subtitles -> {subtitles_path}")

                    
                    # Strict subtitle file validation
                    if not subtitles_path:
                        logger.error(f"[AIvideos_generate] Job {job_id}: Subtitles ERROR - subtitle file not created: {subtitles_path}")
                        update_job_progress(job_id, "subtitles", f"subtitles: ERROR - subtitle file not created: {subtitles_path}")
                        raise RuntimeError(f"Subtitle generation failed: file not created: {subtitles_path}")
                    sp = Path(subtitles_path)
                    if not sp.exists() or sp.stat().st_size < 10:
                        logger.error(f"[AIvideos_generate] Job {job_id}: Subtitles ERROR - subtitle file not created or empty: {subtitles_path}")
                        update_job_progress(job_id, "subtitles", f"subtitles: ERROR - subtitle file not created or empty: {subtitles_path}")
                        raise RuntimeError(f"Subtitle generation failed: file not created or empty: {subtitles_path}")

                    # Enhanced subtitle: must be valid JSON with required fields
                    if subtitles_path.endswith('.json'):
                        import json
                        try:
                            with sp.open("r", encoding="utf-8", errors="ignore") as fh:
                                data = json.load(fh)
                            if not (isinstance(data, dict) and 'sentences' in data and 'word_timings' in data):
                                raise ValueError("Enhanced subtitle JSON missing required fields")
                        except Exception as e:
                            logger.error(f"[AIvideos_generate] Job {job_id}: Subtitles ERROR - invalid enhanced subtitle JSON: {e}")
                            update_job_progress(job_id, "subtitles", f"subtitles: ERROR - invalid enhanced subtitle JSON: {e}")
                            raise RuntimeError(f"Subtitle generation failed: invalid enhanced subtitle JSON: {e}")
                    # SRT: must not be JSON and must have SRT structure
                    elif subtitles_path.endswith('.srt'):
                        with sp.open("r", encoding="utf-8", errors="ignore") as fh:
                            head = fh.read(512)
                        if head.strip().startswith('{'):
                            logger.error(f"[AIvideos_generate] Job {job_id}: Subtitles ERROR - SRT file is actually JSON: {subtitles_path}")
                            update_job_progress(job_id, "subtitles", f"subtitles: ERROR - SRT file is actually JSON: {subtitles_path}")
                            raise RuntimeError(f"Subtitle generation failed: SRT file is actually JSON: {subtitles_path}")
                        if not any('-->' in line for line in head.splitlines()):
                            logger.error(f"[AIvideos_generate] Job {job_id}: Subtitles ERROR - SRT file missing timing lines: {subtitles_path}")
                            update_job_progress(job_id, "subtitles", f"subtitles: ERROR - SRT file missing timing lines: {subtitles_path}")
                            raise RuntimeError(f"Subtitle generation failed: SRT file missing timing lines: {subtitles_path}")
                    else:
                        logger.error(f"[AIvideos_generate] Job {job_id}: Subtitles ERROR - unknown subtitle file extension: {subtitles_path}")
                        update_job_progress(job_id, "subtitles", f"subtitles: ERROR - unknown subtitle file extension: {subtitles_path}")
                        raise RuntimeError(f"Subtitle generation failed: unknown subtitle file extension: {subtitles_path}")
                except Exception as e:
                    logger.error(f"[AIvideos_generate] Job {job_id}: Subtitles failed to generate or inspect file: {e}")
                    update_job_progress(job_id, "subtitles", f"subtitles: failed to generate or inspect file: {e}")
                    raise

                _check_cancel(job_id)
                logger.info(f"[AIvideos_generate] Job {job_id}: Step compose_video - threads={req.threads or 2} useGPU={req.useGPU} color={req.color or '#FFFF00'} position={req.subtitlesPosition}")
                _update_job(job_id, step="compose_video")
                update_job_progress(job_id, "compose_video",
                    f"compose_video: threads={req.threads or 2} useGPU={req.useGPU} color={req.color or '#FFFF00'} position={req.subtitlesPosition}"
                )
                temp_audio = AudioFileClip(tts_path)
                
                # Use intelligent GPU decision making
                from utils.gpu_manager import should_use_gpu
                gpu_decision = should_use_gpu(estimated_memory_gb=2.0)  # Estimate 2GB for video processing
                use_gpu = req.useGPU and gpu_decision['use_gpu']

                if not gpu_decision['use_gpu'] and req.useGPU:
                    logger.info(f"GPU requested but not recommended: {gpu_decision['reason']}")

                # Use local video processing with optional streaming for memory efficiency
                use_streaming = os.getenv("VIDEOHELPER_USE_STREAMING", "false").lower() == "true"
                combined_video_path = combine_videos(video_paths, int(temp_audio.duration), 5, req.threads or 2, use_gpu, use_streaming)
                logger.info(f"[AIvideos_generate] Job {job_id}: Combined video -> {combined_video_path}")
                update_job_progress(job_id, "compose_video", f"compose_video: combined video -> {combined_video_path}")

                # Log environment versions helpful for font/TextClip issues
                try:
                    import platform  # type: ignore
                    import moviepy  # type: ignore
                    from PIL import Image, ImageFont, __version__ as PIL_VERSION  # type: ignore
                    logger.info(f"[AIvideos_generate] Job {job_id}: env: python={platform.python_version()} moviepy={getattr(moviepy, '__version__', 'unknown')} pillow={PIL_VERSION}")
                    update_job_progress(job_id, "compose_video",
                        f"env: python={platform.python_version()} moviepy={getattr(moviepy, '__version__', 'unknown')} pillow={PIL_VERSION}"
                    )
                    logger.info(f"[AIvideos_generate] Job {job_id}: PIL ImageFont module file={getattr(ImageFont, '__file__', 'unknown')}")
                    update_job_progress(job_id, "compose_video", f"PIL ImageFont module file={getattr(ImageFont, '__file__', 'unknown')}")
                except Exception as e:
                    logger.warning(f"[AIvideos_generate] Job {job_id}: env: failed to get version info ({e})")
                    update_job_progress(job_id, "compose_video", f"env: failed to get version info ({e})")

                try:
                    # Debug: Check subtitle file type before video generation
                    from vendors.AIvideos.enhanced_subtitles import is_enhanced_subtitle_file
                    
                    if subtitles_path:
                        is_enhanced = is_enhanced_subtitle_file(subtitles_path)
                        logger.info(f"[AIvideos_generate] Job {job_id}: compose_video: subtitle_type={'enhanced' if is_enhanced else 'traditional'} path={subtitles_path}")
                        update_job_progress(job_id, "compose_video", f"compose_video: subtitle_type={'enhanced' if is_enhanced else 'traditional'} path={subtitles_path}")
                    else:
                        logger.warning(f"[AIvideos_generate] Job {job_id}: compose_video: no_subtitles_path")
                        update_job_progress(job_id, "compose_video", f"compose_video: no_subtitles_path")
                    
                    # Use local video generation
                    final_video_path = generate_video(
                        combined_video_path,
                        tts_path,
                        subtitles_path or "",
                        req.threads or 2,
                        req.subtitlesPosition,
                        req.color or "#FFFF00",
                        req.useGPU
                    )
                except Exception as ge:
                    import traceback
                    tb = traceback.format_exc()
                    logger.error(f"[AIvideos_generate] Job {job_id}: compose_video: generate_video failed: {ge}")
                    logger.error(f"[AIvideos_generate] Job {job_id}: traceback: {tb}")
                    update_job_progress(job_id, "compose_video", f"compose_video: generate_video failed: {ge}")
                    update_job_progress(job_id, "compose_video", f"traceback: {tb}")
                    raise

                # Optional background music
                if req.useMusic:
                    _check_cancel(job_id)
                    from vendors.AIvideos.utils import choose_random_song
                    song_path = choose_random_song()
                    codec_settings = {"codec": "h264_nvenc" if req.useGPU else "libx264", "audio_codec": "aac"}
                    video_clip_path = Path(str(final_video_path))
                    if not video_clip_path.is_absolute():
                        video_clip_path = Path("..") / str(final_video_path)
                    video_clip = VideoFileClip(str(video_clip_path))
                    original_duration = video_clip.duration
                    original_audio = video_clip.audio
                    song_clip = AudioFileClip(song_path).with_fps(44100).with_volume_scaled(0.1)
                    comp_audio = CompositeAudioClip([original_audio, song_clip])
                    video_clip = (
                        video_clip
                        .with_audio(comp_audio)
                        .with_fps(30)
                        .with_duration(original_duration)
                    )
                    video_clip.write_videofile(str(video_clip_path), threads=req.threads or 1, **codec_settings)

                _check_cancel(job_id)
                # Create job-specific output folder named with job UUID
                job_output_dir = DEFAULT_OUTPUT_DIR / job_id
                job_output_dir.mkdir(parents=True, exist_ok=True)

                # Move video to job-specific folder
                final_output_path = job_output_dir / "AIvideos.mp4"

                # Move the video from temporary location to final output location
                try:
                    if Path(final_video_path).exists():
                        shutil.move(str(final_video_path), str(final_output_path))
                        final_video_path = str(final_output_path.resolve())
                        logger.info(f"[AIvideos_generate] Job {job_id}: moved video to final location: {final_video_path}")
                        update_job_progress(job_id, "done", f"moved video to final location: {final_video_path}")
                    else:
                        logger.warning(f"[AIvideos_generate] Job {job_id}: warning: video file not found at {final_video_path}")
                        update_job_progress(job_id, "done", f"warning: video file not found at {final_video_path}")
                except Exception as move_error:
                    logger.warning(f"[AIvideos_generate] Job {job_id}: warning: could not move video to final location: {move_error}")
                    update_job_progress(job_id, "done", f"warning: could not move video to final location: {move_error}")
                    # Continue with original path if move fails

                # Move subtitles file to job-specific folder if it exists
                final_subtitles_path = None
                if subtitles_path and Path(subtitles_path).exists():
                    try:
                        subtitles_filename = Path(subtitles_path).name
                        final_subtitles_path = job_output_dir / subtitles_filename
                        shutil.move(str(subtitles_path), str(final_subtitles_path))
                        final_subtitles_path = str(final_subtitles_path.resolve())
                        logger.info(f"[AIvideos_generate] Job {job_id}: moved subtitles to final location: {final_subtitles_path}")
                        update_job_progress(job_id, "done", f"moved subtitles to final location: {final_subtitles_path}")
                    except Exception as move_error:
                        logger.warning(f"[AIvideos_generate] Job {job_id}: warning: could not move subtitles to final location: {move_error}")
                        update_job_progress(job_id, "done", f"warning: could not move subtitles to final location: {move_error}")
                        final_subtitles_path = subtitles_path  # Use original path if move fails
                else:
                    final_subtitles_path = subtitles_path

                duration_seconds = int(time.time() - start_time)
                logger.info(f"[AIvideos_generate] Job {job_id}: done: final video -> {final_video_path} (took {duration_seconds}s)")
                update_job_progress(job_id, "done", f"done: final video -> {final_video_path} (took {duration_seconds}s)")
                _update_job(job_id, status="done", result={"output": str(final_video_path), "subtitles": final_subtitles_path}, duration_seconds=duration_seconds)

    except Exception as e:
        duration_seconds = int(time.time() - start_time)
        if str(e) == "cancelled":
            logger.info(f"[AIvideos_generate] Job {job_id}: Job cancelled")
            _update_job(job_id, status="cancelled", error="cancelled", duration_seconds=duration_seconds)
        else:
            # Use standardized error handling
            error_info = handle_error(e, {
                "job_id": job_id,
                "step": "video_generation",
                "duration_seconds": duration_seconds
            })

            # Add specific hints for common issues
            error_msg = error_info['error']['message']
            if any(k in error_msg.lower() for k in ["font", "pillow", "textclip"]):
                error_msg += " (possible font/Pillow/TextClip configuration issue)"

            update_job_progress(job_id, "error", f"error: {error_msg}")
            _update_job(job_id, status="error", error=error_msg, duration_seconds=duration_seconds)


def _run_brainrot_job(job_id: str, req_dict: dict):
    """Execute Brainrot video generation job."""
    logger.info(f"[brainrot_generate] Started processing job {job_id}")
    start_time = time.time()

    try:
        # Convert dict back to BrainrotRequest
        req = BrainrotRequest(**req_dict)

        # Record when job actually started processing
        _update_job(job_id, started_at=datetime.now(timezone.utc).isoformat())

        from vendors.Compilation.generator import TikYouGenerator

        _check_cancel(job_id)
        _update_job(job_id, step="process_video")

        # Create job-specific output folder named with job UUID
        job_output_dir = DEFAULT_OUTPUT_DIR / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)
        output_dir = str(job_output_dir.resolve())

        generator = TikYouGenerator(output_dir=output_dir)
        
        # Process video from either YouTube URL or uploaded file
        if req.youtubeUrl:
            video_clips = generator.process_single_video(req.youtubeUrl)
        elif req.uploadedVideoPath:
            video_clips = generator._process_uploaded_video(req.uploadedVideoPath)
        else:
            raise RuntimeError("No video source provided")
            
        if not video_clips:
            raise RuntimeError("No clips generated from source video")

        _check_cancel(job_id)
        _update_job(job_id, step="generate_compilations")

        # Initialize partial results tracking
        partial_results = {
            "output_dir": output_dir,
            "generated_videos": [],
            "video_count": 0,
            "total_size_mb": 0,
            "compilation_types": {"normal": 0, "tts": 0, "total": 0},
            "expected_videos": None if req.unlimited else req.numCompilations * 2  # Normal + TTS per compilation, None for unlimited
        }

        # Track individual video progress
        completed_videos = []

        # Override the create_all_compilation_variations method to send real-time updates
        original_create_all_compilation_variations = generator.create_all_compilation_variations

        def create_all_compilation_variations_with_progress(selected_clips, base_output_path, video_id, compilation_num):
            results = original_create_all_compilation_variations(selected_clips, base_output_path, video_id, compilation_num)

            # Send update for each completed video
            for variation_name, path in [('normal', results.get('normal')), ('tts', results.get('tts'))]:
                if path and os.path.exists(path):
                    try:
                        stat = Path(path).stat()
                        size_mb = round(stat.st_size / (1024 * 1024), 2)

                        filename = os.path.basename(path)
                        is_tts = "_tts" in filename
                        is_normal = "_normal" in filename
                        compilation_type = "TTS" if is_tts else "Normal" if is_normal else "Unknown"

                        video_info = {
                            "filename": filename,
                            "path": str(Path(path).resolve()),
                            "size_mb": size_mb,
                            "size_bytes": stat.st_size,
                            "mtime": stat.st_mtime,
                            "compilation_type": compilation_type,
                            "download_url": f"/api/download?path={Path(path).resolve()}",
                            "compilation_num": compilation_num,
                            "variation": variation_name
                        }

                        completed_videos.append(video_info)

                        # Update partial results
                        partial_results["generated_videos"] = completed_videos
                        partial_results["video_count"] = len(completed_videos)
                        partial_results["total_size_mb"] = sum(v["size_mb"] for v in completed_videos)
                        partial_results["compilation_types"]["normal"] = len([v for v in completed_videos if v["compilation_type"] == "Normal"])
                        partial_results["compilation_types"]["tts"] = len([v for v in completed_videos if v["compilation_type"] == "TTS"])
                        partial_results["compilation_types"]["total"] = len(completed_videos)

                        # Send WebSocket update with partial results
                        _update_job(job_id, result=partial_results)

                    except Exception as e:
                        logger.warning(f"Failed to process completed video {path}: {e}")

            return results

        # Monkey patch the method for real-time updates
        generator.create_all_compilation_variations = create_all_compilation_variations_with_progress

        # Generate videos with progress tracking
        generator.generate_tikyou_videos(
            youtube_url=req.youtubeUrl,
            uploaded_video_path=req.uploadedVideoPath,
            num_compilations=None if req.unlimited else req.numCompilations,
            min_duration=req.minDuration,
            max_duration=req.maxDuration,
            video_clips=video_clips  # Pass the already-processed clips
        )

        _check_cancel(job_id)
        # Final update with all videos
        duration_seconds = int(time.time() - start_time)
        partial_results["generated_videos"].sort(key=lambda x: x["mtime"], reverse=True)
        _update_job(job_id, status="done", result=partial_results, duration_seconds=duration_seconds)

    except Exception as e:
        duration_seconds = int(time.time() - start_time)
        if str(e) == "cancelled":
            _update_job(job_id, status="cancelled", error="cancelled", duration_seconds=duration_seconds)
        else:
            _update_job(job_id, status="error", error=str(e), duration_seconds=duration_seconds)


class SuggestSubjectRequest(BaseModel):
    aiModel: str | None = None
    examples: list[str] | None = None
    topicHint: str | None = None


@app.post("/api/AIvideos/suggest-subject")
def suggest_subject(req: SuggestSubjectRequest) -> Dict[str, str]:
    """Suggest a short content subject using Gemini.

    Returns a JSON object: {"subject": "..."}
    """
    # Log start and config hints
    try:
        logger.info(
            "suggest-subject: start",
            extra={
                "endpoint": "suggest_subject",
                "ai_model": (req.aiModel or "gemini-2.0-flash"),
                "examples_count": len(req.examples or []),
                "has_hint": bool((req.topicHint or "").strip()),
            },
        )
        if not os.getenv("GEMINI_API_KEY"):
            logger.warning("suggest-subject: Gemini API key not set (GEMINI_API_KEY)")
    except Exception:
        pass

    # Import the generate_response function
    try:
        from vendors.AIvideos.gpt import generate_response  # type: ignore
    except Exception as e:
        log_error(logger, e, {"endpoint": "suggest_subject", "stage": "import_vendor"})
        raise HTTPException(status_code=500, detail=f"Failed to initialize Gemini backend: {e}")

    examples = req.examples or [
        "Good foods for cats",
        "How to calm your dog",
        "How to fix a broken pipe",
    ]
    hint = (req.topicHint or "").strip()

    prompt_lines = [
        "Suggest one short, catchy subject for a short-form video.",
        "- 3 to 6 words.",
        "- No quotes, no emojis, minimal punctuation.",
        "- Return ONLY the subject text.",
        "",
        "Examples:",
    ]
    prompt_lines += [f"- {e}" for e in examples if e]
    if hint:
        prompt_lines += ["", f"Topic hint: {hint}"]
    prompt = "\n".join(prompt_lines)

    try:
        model = req.aiModel or "gemini-2.0-flash"
        logger.info("suggest-subject: calling Gemini", extra={"endpoint": "suggest_subject", "stage": "call_gemini", "ai_model": model, "prompt_len": len(prompt)})
        raw = generate_response(prompt, model)

    except Exception as e:
        log_error(logger, e, {"endpoint": "suggest_subject", "stage": "call_gemini"})
        raise HTTPException(status_code=500, detail=f"Gemini request failed: {e}")

    text = (raw or "").strip().splitlines()[0] if raw else ""
    # light cleanup: drop surrounding quotes and trailing punctuation
    text = text.strip().strip('"\'').strip()
    if text.endswith(('.', '!', '?')):
        text = text[:-1].strip()
    if not text:
        try:
            logger.warning("suggest-subject: empty response from model", extra={"endpoint": "suggest_subject", "stage": "empty_result"})
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Empty subject from model")
    try:
        logger.info("suggest-subject: success", extra={"endpoint": "suggest_subject", "stage": "done", "subject_len": len(text)})
    except Exception:
        pass
    return {"subject": text}


@app.post("/api/moneyprinter/suggest-subject", tags=["Video Generation"], summary="Suggest Subject (Alias)")
def suggest_subject_alias(req: SuggestSubjectRequest) -> Dict[str, str]:
    """Alias for /api/AIvideos/suggest-subject for frontend compatibility."""
    return suggest_subject(req)


@app.get("/api/AIvideos/models", tags=["Configuration"], summary="List AI Models")
def list_models() -> Dict[str, List[str]]:
    """List available Gemini models using API discovery."""
    try:
        from google import genai
        
        # Get API key from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("No Gemini API key found, returning fallback models")
            # Fallback to static list if no API key
            return {"models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]}

        genai.configure(api_key=api_key)  # type: ignore # Configure API key
        logger.info("Discovering Gemini models via API")
        # Discover available models
        available_models = []
        for model in genai.list_models(): # type: ignore
            if 'generateContent' in model.supported_generation_methods:
                # Extract model name (remove 'models/' prefix if present)
                model_name = model.name
                if model_name.startswith('models/'):
                    model_name = model_name[7:]
                available_models.append(model_name)
        
        # Sort models for consistent ordering
        available_models.sort()
        
        if not available_models:
            logger.warning("No models discovered, returning fallback models")
            return {"models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]}
        
        return {"models": available_models}
        
    except Exception as e:
        logger.error(f"Failed to discover Gemini models: {e}")
        # Return fallback models on error
        return {"models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]}


@app.get("/api/models", tags=["Configuration"], summary="List AI Models (Alias)")
def list_models_alias() -> Dict[str, List[str]]:
    """Alias for /api/AIvideos/models for frontend compatibility."""
    return list_models()


@app.get("/api/AIvideos/gpu-info")
def get_gpu_info() -> Dict[str, Any]:
    """Return information about locally available GPU acceleration.

    Combines CUDA (torch) detection with MoneyPrinter's ffmpeg encoder detection
    to provide a concise summary for the UI.
    """
    # Try CUDA/torch detection (optional dependency in some setups)
    cuda_available = False
    gpu_name: str | None = None
    gpu_memory_gb: float | None = None
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            cuda_available = True
            try:
                gpu_name = torch.cuda.get_device_name(0)
            except Exception:
                gpu_name = None
            try:
                props = torch.cuda.get_device_properties(0)
                gpu_memory_gb = float(getattr(props, "total_memory", 0) or 0) / (1024 ** 3)
            except Exception:
                gpu_memory_gb = None
    except Exception:
        # torch not installed or not functional; ignore
        pass

    # Use MoneyPrinter's codec detection if available
    preferred_codec: str | None = None
    ffmpeg_params: list[str] | None = None
    try:
        ensure_on_path(MONEYPRINTER_BACKEND)
        with pushd(MONEYPRINTER_BACKEND):
            from vendors.moneyprinter.video import detect_gpu_codec  # type: ignore
            try:
                cfg = detect_gpu_codec()
                if isinstance(cfg, dict):
                    preferred_codec = cfg.get("codec")  # type: ignore
                    fp = cfg.get("ffmpeg_params")  # type: ignore
                    if isinstance(fp, (list, tuple)):
                        ffmpeg_params = [str(x) for x in fp]
            except Exception:
                # If detection fails, just leave fields as None
                pass
    except Exception:
        # Vendors might not be available in some modes
        pass

    return {
        "local": {
            "cudaAvailable": cuda_available,
            "gpuName": gpu_name,
            "memoryGb": gpu_memory_gb,
            "preferredCodec": preferred_codec,
            "ffmpegParams": ffmpeg_params,
        }
    }

@app.get("/api/voices")
def list_voices() -> Dict[str, List[str]]:
    """Expose Kokoro voices used by the AI video workflow."""
    start_ts = time.time()
    try:
        # Import voices directly without changing directory since they're in AIvideos
        from vendors.AIvideos.tiktokvoice import VOICES as KOKORO_VOICES  # type: ignore
        voices = list(KOKORO_VOICES)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load voices: {e}")
    duration = time.time() - start_ts
    # Protect tests and API by failing fast if backend is abnormally slow
    try:
        max_secs = float(os.getenv("VOICES_ENDPOINT_MAX_SECS", "5"))
    except Exception:
        max_secs = 5.0
    if duration > max_secs:
        raise HTTPException(status_code=500, detail="Voice backend not responding quickly")
    return {"voices": voices}


@app.get("/api/voice-sample")
def voice_sample(voice: str, text: Optional[str] = None):
    """Generate and return a short MP3 sample for a given voice.

    Query params:
      - voice: Voice id from Kokoro voices
      - text: Optional custom sample text
    """
    ensure_on_path(MONEYPRINTER_BACKEND)
    # Load TTS functions within moneyprinter context
    with pushd(MONEYPRINTER_BACKEND):
        try:
            from vendors.AIvideos.tiktokvoice import tts, list_voices as kokoro_voices  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load TTS backend: {e}")

    # Safely attempt to load available voices using static constant to
    # avoid forcing Kokoro runtime at import time.
    try:
        from vendors.AIvideos.tiktokvoice import VOICES as KOKORO_VOICES  # type: ignore
        voices = set(KOKORO_VOICES)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load voices: {e}")
    if voice not in voices:
        raise HTTPException(status_code=400, detail="Invalid voice")

    # Use a stable absolute temp path under vendors/temp
    temp_dir = (VENDOR_ROOT / "temp").resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)
    target = (temp_dir / f"voice_sample_{voice}.mp3").resolve()
    sample_text = text or "This is a short sample of this voice."

    # If no custom text requested and a sample already exists, reuse it
    if text is None and target.exists() and target.is_file() and target.stat().st_size > 0:
        return FileResponse(str(target), filename=target.name, media_type="audio/mpeg")

    try:
        # Call TTS with absolute output path
        with pushd(MONEYPRINTER_BACKEND):
            tts(sample_text, voice, filename=str(target))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")

    return FileResponse(str(target), filename=target.name, media_type="audio/mpeg")


@app.post("/api/brainrot/generate", tags=["Video Generation"], summary="Generate Brainrot Compilation")
def brainrot_generate(
    req: BrainrotRequest,
):
    try:
        job_id = str(uuid.uuid4())

        # Create progress tracker and initial logs immediately
        from utils.progress_tracker import get_progress_tracker
        tracker = get_progress_tracker(job_id)
        tracker.add_log("Brainrot compilation job created and queued for processing", "info", "brainrot")
        if req.youtubeUrl:
            tracker.add_log(f"Source: YouTube URL - {req.youtubeUrl}", "info", "config")
        elif req.uploadedVideoPath:
            tracker.add_log(f"Source: Uploaded video - {req.uploadedVideoPath}", "info", "config")
        tracker.add_log(f"Compilations to generate: {req.numCompilations}, Duration: {req.minDuration}s-{req.maxDuration}s", "info", "config")

        # Use unified queue for job management
        job_queue.add_job(
            _run_brainrot_job,
            job_id,
            req.model_dump(),  # Convert Pydantic model to dict for serialization
            workflow="brainrot"
        )

        # Ensure job is persisted to database before returning
        # This prevents race conditions where frontend tries to fetch job immediately
        max_retries = 5
        for attempt in range(max_retries):
            try:
                job = job_store.get_job(job_id)
                if job:
                    logger.info(f"[brainrot_generate] Job {job_id} successfully persisted to database")
                    break
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
            except Exception as db_e:
                logger.warning(f"[brainrot_generate] Database check failed for job {job_id}, attempt {attempt + 1}: {db_e}")
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))

        return {"status": "success", "jobId": job_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate brainrot video: {e}")


@app.get("/api/jobs/resumable", tags=["Job Management"], summary="Get Resumable Jobs")
def get_resumable_jobs() -> Dict[str, Any]:
    """Get jobs that can be resumed (failed or cancelled jobs)."""
    try:
        # Get jobs that are in error or cancelled state
        error_jobs = job_store.list_jobs(limit=100, status="error")
        cancelled_jobs = job_store.list_jobs(limit=100, status="cancelled")
        
        resumable_jobs = []
        
        # Process error and cancelled jobs
        for job in error_jobs + cancelled_jobs:
            # Determine what step the job failed on and what could be resumed
            job_step = job.get('step', 'unknown')
            job_workflow = job.get('workflow', 'unknown')
            
            # For now, we'll consider most failed jobs as potentially resumable
            # In the future, this could be more sophisticated based on the specific failure
            resumable_job = {
                "id": job["id"],
                "workflow": job_workflow,
                "status": job["status"],
                "created_at": job["created_at"],
                "error": job.get("error"),
                "last_completed_step": job_step,
                "completed_steps": [],  # Could be enhanced to track individual steps
                "next_step": _get_next_step_for_workflow(job_workflow, job_step),
                "can_resume": True,
                "failure_reason": job.get("error", "Unknown error")
            }
            
            resumable_jobs.append(resumable_job)
        
        # Sort by creation time (newest first)
        resumable_jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return {
            "resumable_jobs": resumable_jobs,
            "total": len(resumable_jobs)
        }
        
    except Exception as e:
        logger.error(f"Failed to get resumable jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get resumable jobs: {e}")


def _get_next_step_for_workflow(workflow: str, last_step: str) -> str:
    """Determine the next step for a workflow based on the last completed step."""
    if workflow == "moneyprinter":
        steps = ["validate_env", "fetch_music", "script_generation", "search_terms", "stock_download", "tts", "subtitles", "compose_video"]
        try:
            current_index = steps.index(last_step)
            return steps[current_index + 1] if current_index + 1 < len(steps) else "compose_video"
        except ValueError:
            return "validate_env"  # Start from beginning if step not found
    elif workflow == "brainrot":
        steps = ["process_video", "generate_compilations"]
        try:
            current_index = steps.index(last_step)
            return steps[current_index + 1] if current_index + 1 < len(steps) else "generate_compilations"
        except ValueError:
            return "process_video"
    else:
        return "unknown"


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    # 410 handling for purged jobs
    purged_reason = job_store.is_purged(job_id)
    if purged_reason:
        raise HTTPException(status_code=410, detail=f"Job was removed: {purged_reason}")

    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Include logs in the job status response for efficiency
    try:
        logger.info(f"Legacy app: Fetching logs for job {job_id} in job_status endpoint")
        from services.job_management import JobManagementService
        job_service = JobManagementService()
        logs_data = job_service.get_job_logs(job_id)
        job['logs'] = logs_data.get('logs', [])
        job['total_logs'] = logs_data.get('total_logs', 0)
        logger.info(f"Legacy app: Successfully added {len(job['logs'])} logs to job status response")
    except Exception as e:
        logger.warning(f"Legacy app: Failed to fetch logs for job {job_id}: {e}")
        # Fallback to empty logs if logs fetch fails
        job['logs'] = []
        job['total_logs'] = 0
    
    return job


@app.get("/api/jobs/{job_id}/logs", tags=["Job Management"], summary="Get Job Logs")
def get_job_logs(job_id: str) -> Dict[str, Any]:
    """Get comprehensive logs for a specific job."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get logs from the job record
    job_logs = job.get('logs', [])
    
    # Try to get additional logs from progress tracker if job is active
    additional_logs = []
    try:
        from utils.progress_tracker import get_progress_tracker
        if job.get('status') in ['running', 'queued']:
            tracker = get_progress_tracker(job_id)
            progress_info = tracker.get_current_progress()
            if 'logs' in progress_info:
                additional_logs = progress_info['logs']
    except Exception as e:
        logger.warning(f"Failed to get progress tracker logs for job {job_id}: {e}")
    
    # Combine all logs and ensure they're timestamped
    all_logs = []
    
    # Add job logs
    for log_entry in job_logs:
        if isinstance(log_entry, str):
            all_logs.append({
                'timestamp': job.get('created_at', ''),
                'level': 'INFO',
                'source': 'job',
                'message': log_entry
            })
        elif isinstance(log_entry, dict):
            all_logs.append({
                'timestamp': log_entry.get('timestamp', job.get('created_at', '')),
                'level': log_entry.get('level', 'INFO'),
                'source': log_entry.get('source', 'job'),
                'message': log_entry.get('message', str(log_entry))
            })
    
    # Add progress tracker logs
    for log_entry in additional_logs:
        if isinstance(log_entry, dict):
            all_logs.append({
                'timestamp': log_entry.get('timestamp', ''),
                'level': log_entry.get('level', 'INFO'),
                'source': 'progress_tracker',
                'message': log_entry.get('message', str(log_entry))
            })
    
    # Sort logs by timestamp
    all_logs.sort(key=lambda x: x.get('timestamp', ''))
    
    return {
        'job_id': job_id,
        'logs': all_logs,
        'total_logs': len(all_logs)
    }


@app.get("/api/jobs", tags=["Job Management"], summary="List Jobs")
def list_jobs(
    limit: int = 50,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """List jobs with optional filtering."""

    jobs = job_store.list_jobs(limit=min(limit, 100), status=status)
    return {"jobs": jobs, "total": len(jobs)}


@app.post("/api/jobs/{job_id}/cancel", tags=["Job Management"], summary="Cancel Job")
def cancel_job(job_id: str):

    # Use unified queue for job cancellation
    if not job_queue.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found or cannot be cancelled")
    _update_job(job_id, status="cancelled")
    return {"status": "cancelled", "jobId": job_id}


@app.post("/api/jobs/{job_id}/purge", tags=["Job Management"], summary="Purge (delete) a job and create tombstone")
def purge_job(job_id: str):
    purged_reason = "Purged by request"
    if job_store.purge_job(job_id, purged_reason):
        return {"status": "purged", "jobId": job_id, "reason": purged_reason}
    raise HTTPException(status_code=404, detail="Job not found")


@app.post("/api/jobs/cleanup/manual", tags=["Job Management"], summary="Run manual stale job expiration")
def manual_cleanup():
    result = job_store.expire_stale_jobs()
    return {"status": "ok", "expired": result}

class PlaylistBatchRequest(BaseModel):
    playlistUrl: str
    name: Optional[str] = None
    limit: Optional[int] = None
    sample: Optional[int] = None
    shuffle: bool = False
    priority: str = "normal"
    maxConcurrent: int = 3
    stopOnError: bool = False
    # AIvideos common params
    numCompilations: int = Field(default=1, ge=1)
    minDuration: int = Field(default=60, ge=10, le=3600)
    maxDuration: int = Field(default=110, ge=10, le=3600)

@app.get("/api/download")
def download_file(path: str):
    """Download a file."""

    file_path = Path(path)
    
    # If the path doesn't exist as-is, try to resolve it relative to allowed directories
    if not file_path.exists() or not file_path.is_file():
        # Try to find the file in allowed directories
        allowed_roots = [DEFAULT_OUTPUT_DIR.resolve(), (ROOT / "AIvideos_output").resolve(), (ROOT / "temp").resolve()]
        
        # Also check the old moneyprinter temp directory for backwards compatibility
        AIvideos_temp = VENDOR_ROOT / "AIvideos" / "cat-video-creator" / "output"
        
        if AIvideos_temp.exists():
            allowed_roots.append(AIvideos_temp.resolve())
        
        found_path = None
        for root in allowed_roots:
            # Try absolute path from root
            candidate = root / Path(path).name
            if candidate.exists() and candidate.is_file():
                found_path = candidate
                break
            
            # Try relative path from root
            try:
                candidate = root / path
                if candidate.exists() and candidate.is_file():
                    found_path = candidate
                    break
            except Exception:
                continue
            
            # Handle paths like "AIvideos/output/file.mp4"
            if "output" in path:
                filename = Path(path).name
                candidate = root / filename
                if candidate.exists() and candidate.is_file():
                    found_path = candidate
                    break
        
        if found_path:
            file_path = found_path
        else:
            raise HTTPException(status_code=404, detail="File not found")
    
  
    
    media_type = "application/octet-stream"
    if file_path.suffix.lower() == ".mp4":
        media_type = "video/mp4"
    return FileResponse(str(file_path), filename=file_path.name, media_type=media_type)


## Removed deprecated /api/list-videos endpoint. Use /api/videos/managed instead.


## Removed deprecated /api/videos/all endpoint. Use /api/videos/managed or related managed endpoints instead.


@app.get("/api/videos/stats", tags=["Video Management"], summary="Get Video Statistics")
def get_video_stats() -> Dict[str, Any]:
    """Delegate video stats retrieval to the new videos route implementation."""
    try:
        from backend.api.routes import videos as videos_routes
        # videos_routes.get_video_stats is a sync function returning a dict
        return videos_routes.get_video_stats()
    except Exception:
        # Bubble up to allow FastAPI to produce a 500 and log details
        raise


@app.post("/api/cleanup/temp-files", tags=["Maintenance"], summary="Clean up temporary files")
async def cleanup_temp_files():
    """Delegate temporary files cleanup to the new system route implementation."""
    try:
        from backend.api.routes import system as system_routes
        return system_routes.cleanup_temp_files()
    except Exception:
        raise


@app.get("/api/cleanup/temp-files/stats", tags=["Maintenance"], summary="Get temporary files statistics")
async def get_temp_files_stats():
    """Delegate temp file stats retrieval to the new system route implementation."""
    try:
        from backend.api.routes import system as system_routes
        return system_routes.get_temp_files_stats()
    except Exception:
        raise

@app.get("/api/database/stats", tags=["Monitoring"], summary="Get database statistics")
async def get_database_stats():
    """Get statistics about database usage and connections.

    Returns job counts, database size, and connection pool status.
    """
    from database import get_job_store

    job_store = get_job_store()
    stats = job_store.get_stats()

    # Database size not available for PostgreSQL
    # Connection pool info from global engine configuration
    config = AppConfig.from_env()

    return {
        "database_stats": stats,
        "database_size_mb": 0,  # Not available for PostgreSQL
        "connection_pool": {
            "pool_size": getattr(config, 'videohelper_db_pool_size', 5),
            "active_connections": 0,  # Not tracked in JobStore
            "pool_timeout_seconds": getattr(config, 'videohelper_db_pool_timeout', 30)
        }
    }


@app.get("/api/streaming/stats", tags=["Monitoring"], summary="Get streaming processor statistics")
async def get_streaming_stats():
    """Get statistics about streaming video processing.

    Returns temp file counts, sizes, and processor status.
    """
    from utils.streaming_processor import get_streaming_processor

    processor = get_streaming_processor()
    stats = processor.get_stats()

    # Check if streaming is enabled
    streaming_enabled = os.getenv("VIDEOHELPER_USE_STREAMING", "false").lower() == "true"

    return {
        "streaming_processor": stats,
        "streaming_enabled": streaming_enabled
    }


@app.get("/api/gpu/stats", tags=["Monitoring"], summary="Get GPU memory statistics")
async def get_gpu_stats():
    """Get GPU memory usage and optimization recommendations.

    Returns GPU memory stats, usage history, and optimization suggestions.
    """
    from utils.gpu_manager import get_gpu_manager

    gpu_manager = get_gpu_manager()
    stats = gpu_manager.get_memory_stats()

    # Add usage history for the last 5 minutes
    usage_history = gpu_manager.get_usage_history(minutes=5)

    # Get optimization recommendations
    optimization = gpu_manager.optimize_for_task("general")

    return {
        "gpu_stats": stats,
        "usage_history": usage_history,
        "optimization_recommendations": optimization,
        "memory_thresholds": gpu_manager.memory_thresholds
    }


@app.post("/api/gpu/cleanup", tags=["Maintenance"], summary="Trigger GPU memory cleanup")
async def cleanup_gpu_memory():
    """Manually trigger GPU memory cleanup.

    Returns cleanup results and memory freed.
    """
    from utils.gpu_manager import cleanup_gpu_memory

    result = cleanup_gpu_memory(force=True)
    return result


@app.get("/api/memory/config", tags=["Configuration"], summary="Get memory optimization settings")
async def get_memory_config():
    """Get current memory optimization configuration.

    Returns settings for streaming, cleanup policies, and memory limits.
    """
    return {
        "streaming": {
            "enabled": os.getenv("VIDEOHELPER_USE_STREAMING", "false").lower() == "true",
            "temp_cleanup_hours": int(os.getenv("VIDEOHELPER_STREAMING_CLEANUP_HOURS", "1"))
        },
        "temp_files": {
            "cleanup_interval_minutes": int(os.getenv("VIDEOHELPER_TEMP_CLEANUP_INTERVAL", "30")),
            "max_age_hours": int(os.getenv("VIDEOHELPER_TEMP_MAX_AGE_HOURS", "24"))
        },
        "database": {
            "pool_size": int(os.getenv("VIDEOHELPER_DB_POOL_SIZE", "5")),
            "pool_timeout": int(os.getenv("VIDEOHELPER_DB_POOL_TIMEOUT", "30"))
        },
        "websocket": {
            "max_connection_age_hours": int(os.getenv("VIDEOHELPER_WS_MAX_AGE_HOURS", "1")),
            "heartbeat_interval_seconds": int(os.getenv("VIDEOHELPER_WS_HEARTBEAT", "30"))
        }
    }


@app.get("/api/progress/{job_id}", tags=["Monitoring"], summary="Get job progress")
async def get_job_progress(job_id: str):
    """Get detailed progress information for a specific job.

    Returns step-by-step progress, ETA, and performance metrics.
    """
    from utils.progress_tracker import get_progress_tracker

    tracker = get_progress_tracker(job_id)
    return tracker.get_current_progress()


@app.get("/api/progress", tags=["Monitoring"], summary="Get all job progress")
async def get_all_job_progress():
    """Get progress information for all active jobs.

    Returns progress data for all currently running jobs.
    """
    from utils.progress_tracker import get_all_progress

    return {"jobs": get_all_progress()}


@app.get("/api/cache/stats", tags=["Monitoring"], summary="Get cache statistics")
async def get_cache_stats():
    """Get cache performance and usage statistics.

    Returns cache hit rates, sizes, and optimization metrics.
    """
    from utils.cache_manager import get_cache_manager

    cache_manager = get_cache_manager()
    return {"cache_stats": cache_manager.get_stats()}


@app.post("/api/cache/clear", tags=["Maintenance"], summary="Clear cache")
async def clear_cache():
    """Clear all cache entries.

    Returns number of entries cleared.
    """
    from utils.cache_manager import get_cache_manager

    cache_manager = get_cache_manager()
    cleared_count = cache_manager.clear()
    return {"cleared_entries": cleared_count, "message": f"Cleared {cleared_count} cache entries"}


def _cleanup_multiprocessing_resources():
    """Cleanup multiprocessing resources to prevent leaks."""
    try:
        import multiprocessing

        # Clean up any remaining processes with timeout
        processes = multiprocessing.active_children()
        if processes:
            logger.info(f"Cleaning up {len(processes)} active processes...")

            for process in processes:
                try:
                    process.terminate()
                    process.join(timeout=2)  # 2 second timeout per process
                    if process.is_alive():
                        logger.warning(f"Force killing process {process.pid}")
                        process.kill()  # Force kill if still alive
                        process.join(timeout=1)  # Brief wait after kill
                except Exception as e:
                    logger.warning(f"Error cleaning up process {process.pid}: {e}")
        else:
            logger.debug("No active multiprocessing processes found")

        logger.debug("Multiprocessing resources cleaned up")
    except Exception as e:
        logger.warning(f"Failed to cleanup multiprocessing resources: {e}")


def _cleanup_resources():
    """Comprehensive cleanup function for all resources."""
    global _CLEANUP_COMPLETED

    # Prevent duplicate cleanup
    if _CLEANUP_COMPLETED:
        return

    # Skip cleanup if interpreter is shutting down
    if _is_interpreter_shutting_down():
        logger.info("Interpreter shutting down, skipping resource cleanup")
        _CLEANUP_COMPLETED = True
        return

    logger.info("Cleaning up resources...")

    # Set overall timeout for cleanup
    import threading
    import time

    def cleanup_worker():
        try:
            # Cleanup temp files first
            try:
                from utils.file_management import get_temp_manager
                temp_manager = get_temp_manager()
                temp_results = temp_manager.cleanup_all(force=True)
                temp_files = sum(r.get('files_removed', 0) for r in temp_results.values())
                temp_space = sum(r.get('space_freed_mb', 0) for r in temp_results.values())
                logger.info(f"Temp files cleaned up: {temp_files} files, {temp_space:.2f} MB freed")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp files: {e}")

            # Cleanup multiprocessing resources
            if not _is_interpreter_shutting_down():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: _cleanup_multiprocessing_resources())
                    try:
                        future.result(timeout=5)  # 5 second timeout
                        logger.info("Multiprocessing resources cleaned up")
                    except concurrent.futures.TimeoutError:
                        logger.warning("Multiprocessing cleanup timeout reached")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup multiprocessing resources: {e}")

            # Cleanup threading resources - only release if we have permits
            if not _is_interpreter_shutting_down():
                try:
                    # Try to release the semaphore with timeout
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(lambda: JOB_SEMAPHORE.release())
                        try:
                            future.result(timeout=2)  # 2 second timeout
                            logger.info("Threading resources cleaned up")
                        except concurrent.futures.TimeoutError:
                            logger.warning("Threading cleanup timeout reached")
                        except ValueError:
                            # Semaphore is already at maximum value, which is fine
                            logger.info("Threading resources already cleaned up")
                        except Exception:
                            pass  # Other exceptions are fine to ignore during shutdown
                except Exception:
                    pass  # Semaphore might already be released

            # Cleanup database connections
            try:
                from database import cleanup_job_store
                cleanup_job_store()
                logger.info("Database connections cleaned up")
            except Exception as e:
                logger.warning(f"Failed to cleanup database connections: {e}")

            # Cleanup streaming processor temp files
            try:
                from utils.streaming_processor import cleanup_streaming_temp_files
                cleanup_streaming_temp_files()
                logger.info("Streaming processor temp files cleaned up")
            except Exception as e:
                logger.warning(f"Failed to cleanup streaming temp files: {e}")

        except Exception as e:
            # Don't log "can't register atexit after shutdown" errors during import
            if "can't register atexit after shutdown" not in str(e):
                logger.error(f"Error during cleanup: {e}")

    # Run cleanup with timeout
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    cleanup_thread.join(timeout=15)  # 15 second overall timeout

    _CLEANUP_COMPLETED = True

    if cleanup_thread.is_alive():
        logger.warning("Cleanup timeout reached, some resources may not be fully cleaned up")
    else:
        logger.info("Cleanup completed successfully")


# Register cleanup function to run on exit with timeout
def _atexit_cleanup_with_timeout():
    """Atexit cleanup wrapper with timeout to prevent hanging."""
    global _SHUTDOWN_IN_PROGRESS

    if _SHUTDOWN_IN_PROGRESS or _is_interpreter_shutting_down():
        return  # Already handled by signal handler or interpreter is shutting down

    _SHUTDOWN_IN_PROGRESS = True

    import threading
    import time

    def cleanup_worker():
        try:
            _cleanup_resources()
        except Exception as e:
            # Don't log "can't register atexit after shutdown" errors during import
            if "can't register atexit after shutdown" not in str(e):
                logger.error(f"Error during atexit cleanup: {e}")

    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    cleanup_thread.join(timeout=10)  # 10 second timeout

    if cleanup_thread.is_alive():
        logger.warning("Atexit cleanup timeout reached")

# Only register if not already shutting down
try:
    atexit.register(_atexit_cleanup_with_timeout)
except Exception:
    # atexit registration failed (interpreter shutting down)
    pass

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run("app:app", host="0.0.0.0", port=9000, reload=True)
    finally:
        if not _SHUTDOWN_IN_PROGRESS:
            _SHUTDOWN_IN_PROGRESS = True

            # Run cleanup with timeout
            import threading
            import time

            def cleanup_worker():
                try:
                    _cleanup_resources()
                except Exception as e:
                    logger.error(f"Error during main cleanup: {e}")

            cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
            cleanup_thread.start()
            cleanup_thread.join(timeout=10)  # 10 second timeout

            if cleanup_thread.is_alive():
                logger.warning("Main cleanup timeout reached, forcing exit")
                os._exit(1)


