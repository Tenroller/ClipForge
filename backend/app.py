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
from datetime import datetime, timezone

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
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header, Request, Cookie
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from collections import deque
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from validation import (
    validate_youtube_url, validate_subject, validate_custom_prompt,
    validate_zip_url, validate_color, validate_subtitle_position,
    validate_ai_model, validate_voice
)
from logging_config import get_logger, log_request, log_job_event, log_error, log_security_event
from metrics import get_metrics, record_request_metrics, init_metrics_system, track_job_metrics



ROOT = Path(__file__).resolve().parents[1]
# Ensure a unified output directory for all generators
DEFAULT_OUTPUT_DIR = (ROOT / "output").resolve()
os.environ.setdefault("VIDEOHELPER_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# Vendored copies live under backend/vendors/
# Use the current file's directory to locate the vendors folder reliably.
VENDOR_ROOT = Path(__file__).resolve().parent / "vendors"
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

# Initialize logger
logger = get_logger("video_generator")

# Setup espeak-ng environment for Kokoro TTS
# Clear potentially problematic espeakng_loader environment variables
for key in ['ESPEAK_DATA_PATH', 'ESPEAKNG_DATA_PATH', 'PHONEMIZER_ESPEAK_DATA_PATH', 'PHONEMIZER_ESPEAK_LIBRARY']:
    if key in os.environ:
        del os.environ[key]

# Use system espeak-ng if available (recommended for macOS with Homebrew)
system_espeak_paths = [
    '/opt/homebrew/bin/espeak-ng',  # Homebrew ARM64
    '/usr/local/bin/espeak-ng',    # Homebrew x86_64
    '/usr/bin/espeak-ng'           # System package
]

system_espeak_data_paths = [
    '/opt/homebrew/share/espeak-ng-data',  # Homebrew ARM64
    '/usr/local/share/espeak-ng-data',    # Homebrew x86_64
    '/usr/share/espeak-ng-data'           # System package
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


def _signal_handler(signum, frame):
    """Signal handler for graceful shutdown."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    
    # Set a timeout for cleanup to prevent hanging
    import threading
    import time
    
    def cleanup_with_timeout():
        try:
            _cleanup_resources()
            logger.info("Cleanup completed successfully")
        except Exception as e:
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
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    
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
            subscribers = list(WS_SUBSCRIBERS.get(job_id, set()))
            if not subscribers:
                continue
            dead = []
            for ws in subscribers:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead.append(ws)
            # Cleanup dead sockets
            for ws in dead:
                try:
                    WS_SUBSCRIBERS[job_id].discard(ws)
                except Exception:
                    pass

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
        try:
            # Use the simplified cleanup function with timeout
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
        except Exception as e:
            logger.warning(f"Failed to cleanup multiprocessing resources: {e}")
        
        # Cleanup threading resources
        try:
            # Release the job semaphore with timeout
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

        # Cleanup any remaining WebSocket connections
        try:
            active_connections = sum(len(subscribers) for subscribers in WS_SUBSCRIBERS.values())
            if active_connections > 0:
                logger.info(f"Cleaning up {active_connections} WebSocket connections...")
                
                # Close all WebSocket connections
                try:
                    await _cleanup_websockets()
                    logger.info("WebSocket connections cleaned up")
                except Exception as e:
                    logger.warning(f"Failed to cleanup WebSocket connections: {e}")
            else:
                logger.info("No active WebSocket connections found")
        except Exception as e:
            logger.warning(f"Failed to cleanup WebSocket connections: {e}")


async def _cleanup_websockets():
    """Helper function to cleanup WebSocket connections."""
    for job_id in list(WS_SUBSCRIBERS.keys()):
        for websocket in list(WS_SUBSCRIBERS[job_id]):
            try:
                # Try to close the websocket gracefully
                if hasattr(websocket, 'close'):
                    await websocket.close()
            except Exception:
                pass
        WS_SUBSCRIBERS[job_id].clear()
    WS_SUBSCRIBERS.clear()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging and monitoring."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        
        # Log request start
        method = request.method
        path = str(request.url.path)
        
        response = None
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            log_error(logger, e, {"path": path, "method": method, "client_ip": client_ip})
            raise
        finally:
            # Log request completion
            duration = time.time() - start_time
            log_request(logger, method, path, status_code, duration, client_ip)
            
            # Record metrics
            record_request_metrics(method, path, status_code, duration)
            
            # Log slow requests
            if duration > 5.0:
                logger.warning(f"Slow request: {method} {path} took {duration:.2f}s")
            
            # Log security events
            if status_code == 401:
                log_security_event(logger, "unauthorized_access", client_ip, f"{method} {path}")
            elif status_code == 429:
                log_security_event(logger, "rate_limit_exceeded", client_ip, f"{method} {path}")
        
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
    * **Security**: Optional API key authentication and rate limiting
    * **Monitoring**: Comprehensive logging and error tracking
    
    ## Authentication
    
    If `API_KEY` environment variable is set, protected endpoints require the `X-API-Key` header:
    
    ```
    X-API-Key: your-secret-api-key
    ```
    
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
        "http://localhost:8080",
        "http://127.0.0.1:8080",
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
    youtubeUrl: str
    numCompilations: int = Field(default=1, ge=1, le=10)
    minDuration: int = Field(default=60, ge=10, le=3600)
    maxDuration: int = Field(default=110, ge=10, le=3600)
    maxReuse: int = Field(default=3, ge=1, le=10)

    @field_validator('youtubeUrl')
    @classmethod
    def validate_youtube_url_field(cls, v):
        return validate_youtube_url(v)


from database import get_job_store, migrate_from_json

# Legacy file-based storage for migration
JOBS_FILE = DEFAULT_OUTPUT_DIR / "jobs.json"
JOB_CONTROLS: Dict[str, Dict[str, Any]] = {}

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

# Initialize enhanced systems
try:
    init_metrics_system()
    
    logger.info("✅ All systems initialized")
except Exception as e:
    logger.error(f"Failed to initialize enhanced systems: {e}")

# Remove old job loading/saving functions as they're now handled by database

# WebSocket pub-sub for job updates
WS_SUBSCRIBERS: Dict[str, set] = defaultdict(set)
ASYNC_QUEUE: "asyncio.Queue[tuple[str, Dict[str, Any]]]" = asyncio.Queue()
MAIN_LOOP: "asyncio.AbstractEventLoop | None" = None
JOB_SEMAPHORE = threading.Semaphore(max(1, int(os.getenv("MAX_CONCURRENT_JOBS", "2") or "2")))
# Backwards-compat in tests that patch `app.JOBS`
JOBS: Dict[str, Dict[str, Any]] = {}

# Simple optional in-memory rate limiter (per minute)
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MINUTE", "0") or "0")
RATE_LIMIT_BUCKETS: Dict[str, deque] = defaultdict(deque)  # key: f"{bucket}:{ip}"
RATE_LIMIT_LOCK = threading.Lock()

def _enqueue_job_update(job_id: str) -> None:
    """Thread-safe enqueue of a job update for websocket broadcast."""
    global MAIN_LOOP
    try:
        payload = job_store.get_job(job_id)
        if payload and MAIN_LOOP is not None:
            MAIN_LOOP.call_soon_threadsafe(ASYNC_QUEUE.put_nowait, (job_id, payload))
    except Exception:
        # Best-effort only
        pass


def _update_job(job_id: str, **fields: Any) -> None:
    job_store.update_job(job_id, **fields)
    _enqueue_job_update(job_id)


def _check_cancel(job_id: str) -> None:
    ctrl = JOB_CONTROLS.get(job_id)
    if ctrl and ctrl.get("cancel") and ctrl["cancel"].is_set():
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


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Optional API key protection.

    If environment variable API_KEY is set, require header X-API-Key to match it.
    If not set, allow all requests.
    """
    expected = os.getenv("API_KEY")
    if expected and (x_api_key or "") != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


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
    - `GOOGLE_API_KEY` or `GEMINI_API_KEY`: For AI script generation
    """
)
def moneyprinter_generate(
    req: MoneyPrinterRequest,
    _: None = Depends(require_api_key),

    
):
    job_id = str(uuid.uuid4())
    
    # Debug: Log the request parameters
    logger.debug(f"Request useTikTokSubtitles: {req.useTikTokSubtitles} (type: {type(req.useTikTokSubtitles)})")
    logger.debug(f"Request subtitleFont: {req.subtitleFont}")
    
    logger.info(f"[moneyprinter_generate] Creating job {job_id}")
    job_store.create_job(job_id, "moneyprinter", req.model_dump())
    JOB_CONTROLS[job_id] = {"cancel": threading.Event()}
    _enqueue_job_update(job_id)

    def _log_job(message: str) -> None:
        try:
            job = job_store.get_job(job_id)
            
            if job:
                logs = job.get("logs", [])
                if not isinstance(logs, list):
                    logs = []
                logs.append(message)
                _update_job(job_id, logs=logs)
        except Exception:
            # Best-effort logging
            pass

    def _run_job():
        logger.info(f"[moneyprinter_generate] Started processing job {job_id}")
        start_time = time.time()
        
        try:
            # Record when job actually started processing
            logger.info(f"[moneyprinter_generate] Job {job_id}: Marking as started")
            _update_job(job_id, started_at=datetime.now(timezone.utc).isoformat())
            
            # Ensure output directory environment variable is set for the job thread
            logger.info(f"[moneyprinter_generate] Job {job_id}: Setting VIDEOHELPER_OUTPUT_DIR to {DEFAULT_OUTPUT_DIR}")
            os.environ["VIDEOHELPER_OUTPUT_DIR"] = str(DEFAULT_OUTPUT_DIR)
            
            logger.info(f"[moneyprinter_generate] Job {job_id}: Ensuring MONEYPRINTER_BACKEND on path and entering directory")
            ensure_on_path(MONEYPRINTER_BACKEND)
            with pushd(MONEYPRINTER_BACKEND):
                # Lazy imports from vendored MoneyPrinter project
                from vendors.moneyprinter.utils import fetch_songs, check_env_vars
                from vendors.moneyprinter.gpt import generate_script, get_search_terms
                from vendors.moneyprinter.search import search_for_stock_videos
                from vendors.moneyprinter.tiktokvoice import tts
                from vendors.moneyprinter.video import generate_subtitles, combine_videos, generate_video
                from vendors.moneyprinter.video import save_video as mp_save_video
                from moviepy import AudioFileClip, CompositeAudioClip, VideoFileClip, concatenate_audioclips  # type: ignore
                from pathlib import Path
                import shutil

                logger.info(f"[moneyprinter_generate] Job {job_id}: Step validate_env - checking MoneyPrinter environment variables")
                _update_job(job_id, step="validate_env")
                _log_job("validate_env: checking MoneyPrinter environment variables")
                try:
                    check_env_vars()
                except SystemExit:
                    raise RuntimeError("Missing required MoneyPrinter environment variables")

                _check_cancel(job_id)
                if req.useMusic and req.zipUrl:
                    logger.info(f"[moneyprinter_generate] Job {job_id}: Step fetch_music - downloading songs from zipUrl={req.zipUrl}")
                    _update_job(job_id, step="fetch_music")
                    _log_job(f"fetch_music: downloading songs from zipUrl={req.zipUrl}")
                    fetch_songs(req.zipUrl)
                   
                    

                # Check if this is a shared content benchmark request
                use_shared_content = hasattr(req, '_shared_content') and getattr(req, '_shared_content', False)
                if use_shared_content:
                    logger.info(f"[moneyprinter_generate] Job {job_id}: Step benchmark - using shared content for identical testing")
                    _log_job("benchmark: using shared content for identical testing")
                    
                    # Extract shared content from request
                    shared_script = getattr(req, '_shared_script', None)
                    shared_terms = getattr(req, '_shared_search_terms', [])
                    shared_sentences = getattr(req, '_shared_sentences', [])
                    shared_video_paths = getattr(req, '_shared_stock_videos', [])
                    shared_tts_path = getattr(req, '_shared_tts_path', None)
                    shared_subtitles_path = getattr(req, '_shared_subtitles_path', None)
                    
                    if not shared_script or not shared_video_paths or not shared_tts_path:
                        raise RuntimeError("Incomplete shared content provided")
                    
                    logger.info(f"[moneyprinter_generate] Job {job_id}: Step benchmark - shared content loaded - {len(shared_video_paths)} videos, script length: {len(shared_script)}")
                    _log_job(f"benchmark: shared content loaded - {len(shared_video_paths)} videos, script length: {len(shared_script)}")
                    
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
                    
                    logger.info(f"[moneyprinter_generate] Job {job_id}: Step benchmark - skipped content generation, proceeding to video assembly")
                    _log_job("benchmark: skipped content generation, proceeding to video assembly")
                    
                  
                    
                else:
                    # Normal content generation path
                    _check_cancel(job_id)
                    logger.info(f"[moneyprinter_generate] Job {job_id}: Step script_generation - model={req.aiModel} voice={req.voice} paragraphs={req.paragraphNumber}")
                    _update_job(job_id, step="script_generation")
                    _log_job(f"script_generation: model={req.aiModel} voice={req.voice} paragraphs={req.paragraphNumber}")
                    script = generate_script(req.videoSubject, req.paragraphNumber, req.aiModel, req.voice, req.customPrompt or "")
                    if not script:
                        raise RuntimeError("Script generation failed")
                    
                   

                    _check_cancel(job_id)
                    logger.info(f"[moneyprinter_generate] Job {job_id}: Step search_terms - extracting search terms from script")
                    _update_job(job_id, step="search_terms")
                    terms = get_search_terms(req.videoSubject, 10, script, req.aiModel)
                    _log_job(f"search_terms: {len(terms)} terms -> {terms[:5]}{'...' if len(terms) > 5 else ''}")
                    
                   

                    _check_cancel(job_id)
                    logger.info(f"[moneyprinter_generate] Job {job_id}: Step stock_download - downloading stock videos for terms")
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
                                logger.warning(f"[moneyprinter_generate] Job {job_id}: Failed to download video for url {url}")
                                continue
                    if not video_paths:
                        logger.error(f"[moneyprinter_generate] Job {job_id}: No stock videos downloaded")
                        raise RuntimeError("No stock videos downloaded")
                    else:
                        logger.info(f"[moneyprinter_generate] Job {job_id}: Downloaded {len(video_paths)} stock video clips")
                        _log_job(f"stock_download: downloaded {len(video_paths)} clips")
                        
                 
                    _check_cancel(job_id)
                    logger.info(f"[moneyprinter_generate] Job {job_id}: Step tts - generating audio segments using voice={req.voice}")
                    _update_job(job_id, step="tts")
                    _log_job(f"tts: generating {len([s for s in script.split('. ') if s])} audio segments using voice={req.voice}")
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
                        logger.error(f"[moneyprinter_generate] Job {job_id}: No audio clips generated")
                        raise RuntimeError("No audio clips generated")

                    tts_path = str(temp_dir / f"{uuid.uuid4()}.mp3")
                    concatenate_audioclips(audio_clips).write_audiofile(tts_path)
                    temp_audio_files.append(tts_path)
                    logger.info(f"[moneyprinter_generate] Job {job_id}: TTS concatenated audio -> {tts_path}")
                    _log_job(f"tts: concatenated audio -> {tts_path}")
                    
                    

                _check_cancel(job_id)
                logger.info(f"[moneyprinter_generate] Job {job_id}: Step subtitles - generating subtitles")
                _update_job(job_id, step="subtitles")
                
                # Choose subtitle generation method based on request

                # uuid is already imported at the top
                subtitles_path = None
                try:
                    if req.useTikTokSubtitles:
                        if req.useWhisperEnhanced:
                            from vendors.moneyprinter.whisper_enhanced_subtitles import generate_enhanced_subtitles_with_optional_whisper
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
                            logger.info(f"[moneyprinter_generate] Job {job_id}: Subtitles - using Whisper-enhanced TikTok-style subtitles -> {subtitles_path}")
                            _log_job(f"subtitles: using Whisper-enhanced TikTok-style subtitles -> {subtitles_path}")
                        else:
                            from vendors.moneyprinter.enhanced_subtitles import generate_enhanced_subtitles, SubtitleConfig
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
                            logger.info(f"[moneyprinter_generate] Job {job_id}: Subtitles - using TikTok-style enhanced subtitles -> {subtitles_path}")
                            _log_job(f"subtitles: using TikTok-style enhanced subtitles -> {subtitles_path}")
                    else:
                        if not tts_path:
                            raise RuntimeError("TTS path is required for subtitle generation")
                        subtitles_path = generate_subtitles(audio_path=str(tts_path), sentences=sentences, audio_clips=audio_clips, voice=req.voice)
                        logger.info(f"[moneyprinter_generate] Job {job_id}: Subtitles - using traditional subtitles -> {subtitles_path}")
                        _log_job(f"subtitles: using traditional subtitles -> {subtitles_path}")

                   
                    # Strict subtitle file validation
                    if not subtitles_path:
                        logger.error(f"[moneyprinter_generate] Job {job_id}: Subtitles ERROR - subtitle file not created: {subtitles_path}")
                        _log_job(f"subtitles: ERROR - subtitle file not created: {subtitles_path}")
                        raise RuntimeError(f"Subtitle generation failed: file not created: {subtitles_path}")
                    sp = Path(subtitles_path)
                    if not sp.exists() or sp.stat().st_size < 10:
                        logger.error(f"[moneyprinter_generate] Job {job_id}: Subtitles ERROR - subtitle file not created or empty: {subtitles_path}")
                        _log_job(f"subtitles: ERROR - subtitle file not created or empty: {subtitles_path}")
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
                            logger.error(f"[moneyprinter_generate] Job {job_id}: Subtitles ERROR - invalid enhanced subtitle JSON: {e}")
                            _log_job(f"subtitles: ERROR - invalid enhanced subtitle JSON: {e}")
                            raise RuntimeError(f"Subtitle generation failed: invalid enhanced subtitle JSON: {e}")
                    # SRT: must not be JSON and must have SRT structure
                    elif subtitles_path.endswith('.srt'):
                        with sp.open("r", encoding="utf-8", errors="ignore") as fh:
                            head = fh.read(512)
                        if head.strip().startswith('{'):
                            logger.error(f"[moneyprinter_generate] Job {job_id}: Subtitles ERROR - SRT file is actually JSON: {subtitles_path}")
                            _log_job(f"subtitles: ERROR - SRT file is actually JSON: {subtitles_path}")
                            raise RuntimeError(f"Subtitle generation failed: SRT file is actually JSON: {subtitles_path}")
                        if not any('-->' in line for line in head.splitlines()):
                            logger.error(f"[moneyprinter_generate] Job {job_id}: Subtitles ERROR - SRT file missing timing lines: {subtitles_path}")
                            _log_job(f"subtitles: ERROR - SRT file missing timing lines: {subtitles_path}")
                            raise RuntimeError(f"Subtitle generation failed: SRT file missing timing lines: {subtitles_path}")
                    else:
                        logger.error(f"[moneyprinter_generate] Job {job_id}: Subtitles ERROR - unknown subtitle file extension: {subtitles_path}")
                        _log_job(f"subtitles: ERROR - unknown subtitle file extension: {subtitles_path}")
                        raise RuntimeError(f"Subtitle generation failed: unknown subtitle file extension: {subtitles_path}")
                except Exception as e:
                    logger.error(f"[moneyprinter_generate] Job {job_id}: Subtitles failed to generate or inspect file: {e}")
                    _log_job(f"subtitles: failed to generate or inspect file: {e}")
                    raise

                _check_cancel(job_id)
                logger.info(f"[moneyprinter_generate] Job {job_id}: Step compose_video - threads={req.threads or 2} useGPU={req.useGPU} color={req.color or '#FFFF00'} position={req.subtitlesPosition}")
                _update_job(job_id, step="compose_video")
                _log_job(
                    f"compose_video: threads={req.threads or 2} useGPU={req.useGPU} color={req.color or '#FFFF00'} position={req.subtitlesPosition}"
                )
                temp_audio = AudioFileClip(tts_path)
                
                # Use local video processing
                combined_video_path = combine_videos(video_paths, int(temp_audio.duration), 5, req.threads or 2, req.useGPU)
                logger.info(f"[moneyprinter_generate] Job {job_id}: Combined video -> {combined_video_path}")
                _log_job(f"compose_video: combined video -> {combined_video_path}")

                # Log environment versions helpful for font/TextClip issues
                try:
                    import platform  # type: ignore
                    import moviepy  # type: ignore
                    from PIL import Image, ImageFont, __version__ as PIL_VERSION  # type: ignore
                    logger.info(f"[moneyprinter_generate] Job {job_id}: env: python={platform.python_version()} moviepy={getattr(moviepy, '__version__', 'unknown')} pillow={PIL_VERSION}")
                    _log_job(
                        f"env: python={platform.python_version()} moviepy={getattr(moviepy, '__version__', 'unknown')} pillow={PIL_VERSION}"
                    )
                    logger.info(f"[moneyprinter_generate] Job {job_id}: PIL ImageFont module file={getattr(ImageFont, '__file__', 'unknown')}")
                    _log_job(f"PIL ImageFont module file={getattr(ImageFont, '__file__', 'unknown')}")
                except Exception as e:
                    logger.warning(f"[moneyprinter_generate] Job {job_id}: env: failed to get version info ({e})")
                    _log_job(f"env: failed to get version info ({e})")

                try:
                    # Debug: Check subtitle file type before video generation
                    from vendors.moneyprinter.enhanced_subtitles import is_enhanced_subtitle_file
                    
                    if subtitles_path:
                        is_enhanced = is_enhanced_subtitle_file(subtitles_path)
                        logger.info(f"[moneyprinter_generate] Job {job_id}: compose_video: subtitle_type={'enhanced' if is_enhanced else 'traditional'} path={subtitles_path}")
                        _log_job(f"compose_video: subtitle_type={'enhanced' if is_enhanced else 'traditional'} path={subtitles_path}")
                    else:
                        logger.warning(f"[moneyprinter_generate] Job {job_id}: compose_video: no_subtitles_path")
                        _log_job(f"compose_video: no_subtitles_path")
                    
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
                    logger.error(f"[moneyprinter_generate] Job {job_id}: compose_video: generate_video failed: {ge}")
                    logger.error(f"[moneyprinter_generate] Job {job_id}: traceback: {tb}")
                    _log_job(f"compose_video: generate_video failed: {ge}")
                    _log_job(f"traceback: {tb}")
                    raise

                # Optional background music
                if req.useMusic:
                    _check_cancel(job_id)
                    from vendors.moneyprinter.utils import choose_random_song
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

                if not JOB_CONTROLS[job_id]["cancel"].is_set():
                    # Move video to final output location with job ID as filename
                    # Use the default output directory (root output folder)
                    output_dir = DEFAULT_OUTPUT_DIR
                    output_dir.mkdir(exist_ok=True)
                    final_output_path = output_dir / f"moneyprinter_{job_id}.mp4"
                    
                    # Move the video from temporary location to final output location
                    try:
                        if Path(final_video_path).exists():
                            shutil.move(str(final_video_path), str(final_output_path))
                            final_video_path = str(final_output_path.resolve())
                            logger.info(f"[moneyprinter_generate] Job {job_id}: moved video to final location: {final_video_path}")
                            _log_job(f"moved video to final location: {final_video_path}")
                        else:
                            logger.warning(f"[moneyprinter_generate] Job {job_id}: warning: video file not found at {final_video_path}")
                            _log_job(f"warning: video file not found at {final_video_path}")
                    except Exception as move_error:
                        logger.warning(f"[moneyprinter_generate] Job {job_id}: warning: could not move video to final location: {move_error}")
                        _log_job(f"warning: could not move video to final location: {move_error}")
                        # Continue with original path if move fails
                    
                    duration_seconds = int(time.time() - start_time)
                    logger.info(f"[moneyprinter_generate] Job {job_id}: done: final video -> {final_video_path} (took {duration_seconds}s)")
                    _log_job(f"done: final video -> {final_video_path} (took {duration_seconds}s)")
                    _update_job(job_id, status="done", result={"output": str(final_video_path), "subtitles": subtitles_path}, duration_seconds=duration_seconds)

        except Exception as e:
            duration_seconds = int(time.time() - start_time)
            if str(e) == "cancelled":
                logger.info(f"[moneyprinter_generate] Job {job_id}: Job cancelled")
                _update_job(job_id, status="cancelled", error="cancelled", duration_seconds=duration_seconds)
            else:
                # Preserve the last known step in the error and include a hint if it's a font/TextClip issue
                hint = ""
                msg = str(e)
                if any(k in msg.lower() for k in ["font", "pillow", "textclip"]):
                    hint = " (possible font/Pillow/TextClip configuration issue)"
                logger.error(f"[moneyprinter_generate] Job {job_id}: error: {msg}{hint}")
                _log_job(f"error: {msg}{hint}")
                _update_job(job_id, status="error", error=msg, duration_seconds=duration_seconds)

    # Run the long-running job in a detached daemon thread rather than Starlette BackgroundTasks.
    # This avoids noisy asyncio.CancelledError tracebacks on server shutdown (Ctrl+C)
    # when Starlette awaits background tasks during request teardown.
    # Enforce global concurrency limit
    def _runner_with_limit():
        with JOB_SEMAPHORE:
            _run_job()
    threading.Thread(target=_runner_with_limit, name=f"moneyprinter-job-{job_id}", daemon=True).start()
    return {"status": "queued", "jobId": job_id}


class SuggestSubjectRequest(BaseModel):
    aiModel: str | None = None
    examples: list[str] | None = None
    topicHint: str | None = None


@app.post("/api/moneyprinter/suggest-subject")
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
        if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
            logger.warning("suggest-subject: Gemini API key not set (GOOGLE_API_KEY/GEMINI_API_KEY)")
    except Exception:
        pass

    ensure_on_path(MONEYPRINTER_BACKEND)
    with pushd(MONEYPRINTER_BACKEND):
        try:
            from vendors.moneyprinter.gpt import generate_response  # type: ignore
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

@app.get("/api/models", tags=["Configuration"], summary="List AI Models")
def list_models() -> Dict[str, List[str]]:
    """List available Gemini models (static list; can be swapped to dynamic)."""
    # Use a curated list compatible with current SDK; replace with API discovery if desired
    models = [
        "gemini-2.0-flash",
        "gemini-2.0-pro-exp",
        "gemini-2.0-pro",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-2.0-flash-lite",
    ]
    return {"models": models}


@app.get("/api/gpu-info")
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
    ensure_on_path(MONEYPRINTER_BACKEND)
    start_ts = time.time()
    try:
        with pushd(MONEYPRINTER_BACKEND):
            # Avoid importing heavy Kokoro runtime just to list voices.
            # Use the static VOICES constant from the vendor module so this
            # endpoint works even when Kokoro/torch are not installed.
            from vendors.moneyprinter.tiktokvoice import VOICES as KOKORO_VOICES  # type: ignore
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
            from vendors.moneyprinter.tiktokvoice import tts, list_voices as kokoro_voices  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load TTS backend: {e}")

    # Safely attempt to load available voices using static constant to
    # avoid forcing Kokoro runtime at import time.
    try:
        from vendors.moneyprinter.tiktokvoice import VOICES as KOKORO_VOICES  # type: ignore
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


@app.post("/api/brainrot/generate")
def brainrot_generate(
    req: BrainrotRequest,
    _: None = Depends(require_api_key),
  
):
    job_id = str(uuid.uuid4())
    job_store.create_job(job_id, "brainrot", req.dict())
    JOB_CONTROLS[job_id] = {"cancel": threading.Event()}
    _enqueue_job_update(job_id)

    def _run_job():
        start_time = time.time()
        
        try:
            # Record when job actually started processing
            _update_job(job_id, started_at=datetime.now(timezone.utc).isoformat())
            
            ensure_on_path(BRAINROT_ROOT)
            with pushd(BRAINROT_ROOT):
                from tikyou_video_generator.generator import TikYouGenerator  # type: ignore

            _check_cancel(job_id)
            _update_job(job_id, step="process_video")
            
            # Always use the main output directory for consistency
            output_dir = str(DEFAULT_OUTPUT_DIR.resolve())
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            generator = TikYouGenerator(output_dir=output_dir)
            video_clips = generator.process_single_video(req.youtubeUrl)
            if not video_clips:
                raise RuntimeError("No clips generated from source video")

            _check_cancel(job_id)
            _update_job(job_id, step="generate_compilations")
            generator.generate_tikyou_videos(
                req.youtubeUrl,
                num_compilations=req.numCompilations,
                min_duration=req.minDuration,
                max_duration=req.maxDuration,
                video_clips=video_clips  # Pass the already-processed clips
            )

            if not JOB_CONTROLS[job_id]["cancel"].is_set():
                # Find generated video files with more detailed information
                generated_videos = []
                output_path = Path(output_dir)
                if output_path.exists():
                    # Look for video files (common formats)
                    for pattern in ["*.mp4", "*.mov", "*.avi", "*.mkv"]:
                        for video_file in output_path.glob(pattern):
                            if video_file.is_file():
                                try:
                                    stat = video_file.stat()
                                    # Get file size in MB
                                    size_mb = round(stat.st_size / (1024 * 1024), 2)
                                    
                                    # Extract compilation info from filename
                                    filename = video_file.name
                                    is_tts = "_tts" in filename
                                    is_normal = "_normal" in filename
                                    compilation_type = "TTS" if is_tts else "Normal" if is_normal else "Unknown"
                                    
                                    generated_videos.append({
                                        "filename": filename,
                                        "path": str(video_file.resolve()),
                                        "size_mb": size_mb,
                                        "size_bytes": stat.st_size,
                                        "mtime": stat.st_mtime,
                                        "compilation_type": compilation_type,
                                        "download_url": f"/api/download?path={video_file.resolve()}"
                                    })
                                except Exception as e:
                                    logger.warning(f"Failed to get file info for {video_file}: {e}")
                                    continue
                
                # Sort videos by modification time (newest first)
                generated_videos.sort(key=lambda x: x["mtime"], reverse=True)
                
                duration_seconds = int(time.time() - start_time)
                result_data = {
                    "output_dir": output_dir,
                    "generated_videos": generated_videos,
                    "video_count": len(generated_videos),
                    "total_size_mb": sum(v["size_mb"] for v in generated_videos),
                    "compilation_types": {
                        "normal": len([v for v in generated_videos if v["compilation_type"] == "Normal"]),
                        "tts": len([v for v in generated_videos if v["compilation_type"] == "TTS"]),
                        "total": len(generated_videos)
                    }
                }
                _update_job(job_id, status="done", result=result_data, duration_seconds=duration_seconds)
        except Exception as e:
            duration_seconds = int(time.time() - start_time)
            if str(e) == "cancelled":
                _update_job(job_id, status="cancelled", error="cancelled", duration_seconds=duration_seconds)
            else:
                _update_job(job_id, status="error", error=str(e), duration_seconds=duration_seconds)

    # Run the job in a detached daemon thread to avoid shutdown cancellation noise
    def _runner_with_limit():
        with JOB_SEMAPHORE:
            _run_job()
    threading.Thread(target=_runner_with_limit, name=f"brainrot-job-{job_id}", daemon=True).start()
    return {"status": "queued", "jobId": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs", tags=["Job Management"], summary="List Jobs")
def list_jobs(
    limit: int = 50, 
    status: Optional[str] = None,
    _: None = Depends(require_api_key)
) -> Dict[str, Any]:
    """List jobs with optional filtering."""
    jobs = job_store.list_jobs(limit=min(limit, 100), status=status)
    return {"jobs": jobs, "total": len(jobs)}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, _: None = Depends(require_api_key)):
    ctrl = JOB_CONTROLS.get(job_id)
    if not ctrl:
        raise HTTPException(status_code=404, detail="Job not found")
    ctrl["cancel"].set()
    _update_job(job_id, status="cancelled")
    return {"status": "cancelled", "jobId": job_id}


# Enhanced features endpoints

@app.get("/api/metrics", tags=["Monitoring"], summary="Get Metrics")
def get_prometheus_metrics(_: None = Depends(require_api_key)):
    """Get Prometheus metrics in text format."""
    metrics = get_metrics()
    return Response(
        content=metrics.get_metrics_text(),
        media_type="text/plain"
    )


@app.get("/api/metrics/stats", tags=["Monitoring"], summary="Get Metrics Stats")
def get_metrics_stats(_: None = Depends(require_api_key)) -> Dict[str, Any]:
    """Get metrics statistics."""
    return get_metrics().get_stats()

class PlaylistBatchRequest(BaseModel):
    playlistUrl: str
    name: Optional[str] = None
    limit: Optional[int] = None
    sample: Optional[int] = None
    shuffle: bool = False
    priority: str = "normal"
    maxConcurrent: int = 3
    stopOnError: bool = False
    # Brainrot common params
    numCompilations: int = Field(default=1, ge=1, le=10)
    minDuration: int = Field(default=60, ge=10, le=3600)
    maxDuration: int = Field(default=110, ge=10, le=3600)


@app.websocket("/ws/jobs/{job_id}")
async def websocket_job_updates(websocket: WebSocket, job_id: str):
    await websocket.accept()
    # Add to subscribers
    WS_SUBSCRIBERS[job_id].add(websocket)
    # Send the current job state immediately if exists
    try:
        initial = JOBS.get(job_id)
        if initial is not None:
            await websocket.send_json(initial)
    except Exception:
        pass
    try:
        # Keep the connection open; simple ping-pong to detect disconnect
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                # Ignore malformed frames; continue until disconnect
                await asyncio.sleep(0.5)
    finally:
        try:
            WS_SUBSCRIBERS[job_id].discard(websocket)
        except Exception:
            pass

 
def _is_allowed_path(p: Path) -> bool:
    p_resolved = p.resolve()
    allowed_roots = [
        DEFAULT_OUTPUT_DIR.resolve(), 
        (ROOT / "brainrot_output").resolve(),
        (ROOT / "temp").resolve(),  # Allow access to temp directory
        # Include old moneyprinter temp directory for backwards compatibility
        (VENDOR_ROOT / "moneyprinter" / "cat-video-creator" / "output").resolve()
    ]
    for root in allowed_roots:
        try:
            if p_resolved.is_relative_to(root):
                return True
        except Exception:
            # Fallback for older Python versions or edge cases
            if str(p_resolved).startswith(str(root) + os.sep):
                return True
    return False


@app.get("/api/download")
def download_file(path: str):
    file_path = Path(path)
    
    # If the path doesn't exist as-is, try to resolve it relative to allowed directories
    if not file_path.exists() or not file_path.is_file():
        # Try to find the file in allowed directories
        allowed_roots = [DEFAULT_OUTPUT_DIR.resolve(), (ROOT / "brainrot_output").resolve(), (ROOT / "temp").resolve()]
        
        # Also check the old moneyprinter temp directory for backwards compatibility
        moneyprinter_temp = VENDOR_ROOT / "moneyprinter" / "cat-video-creator" / "output"
        if moneyprinter_temp.exists():
            allowed_roots.append(moneyprinter_temp.resolve())
        
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
            
            # Handle paths like "cat-video-creator/output/file.mp4"
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
    
    if not _is_allowed_path(file_path):
        raise HTTPException(status_code=403, detail="Access denied")
    
    media_type = "application/octet-stream"
    if file_path.suffix.lower() == ".mp4":
        media_type = "video/mp4"
    return FileResponse(str(file_path), filename=file_path.name, media_type=media_type)


@app.get("/api/list-videos")
def list_videos(dir: str):
    """List mp4 videos inside a directory under the allowed output roots.

    Returns a JSON object: { "files": [{"path": str, "name": str, "size": int, "mtime": float}] }
    """
    directory = Path(dir)
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")
    if not _is_allowed_path(directory):
        raise HTTPException(status_code=403, detail="Access denied")

    files = []
    try:
        for p in sorted(directory.glob("*.mp4")):
            try:
                stat = p.stat()
                files.append({
                    "path": str(p.resolve()),
                    "name": p.name,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })
            except Exception:
                continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {e}")

    return {"files": files}


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
            logger.info("No active multiprocessing processes found")
        
        logger.info("Multiprocessing resources cleaned up")
    except Exception as e:
        logger.warning(f"Failed to cleanup multiprocessing resources: {e}")


def _cleanup_resources():
    """Comprehensive cleanup function for all resources."""
    logger.info("Cleaning up resources...")
    
    # Set overall timeout for cleanup
    import threading
    import time
    
    def cleanup_worker():
        try:
            # Cleanup multiprocessing resources
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
            
            # Cleanup any remaining WebSocket connections
            try:
                active_connections = sum(len(subscribers) for subscribers in WS_SUBSCRIBERS.values())
                if active_connections > 0:
                    logger.info(f"Cleaning up {active_connections} WebSocket connections...")
                    
                    # Close all WebSocket connections
                    try:
                        # Since this is in a non-async context, we'll just clear the subscribers
                        # The actual cleanup will happen in the async context
                        for job_id in list(WS_SUBSCRIBERS.keys()):
                            WS_SUBSCRIBERS[job_id].clear()
                        WS_SUBSCRIBERS.clear()
                        logger.info("WebSocket connections cleaned up")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup WebSocket connections: {e}")
                else:
                    logger.info("No active WebSocket connections found")
            except Exception as e:
                logger.warning(f"Failed to cleanup WebSocket connections: {e}")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    # Run cleanup with timeout
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    cleanup_thread.join(timeout=15)  # 15 second overall timeout
    
    if cleanup_thread.is_alive():
        logger.warning("Cleanup timeout reached, some resources may not be fully cleaned up")
    else:
        logger.info("Cleanup completed successfully")


# Register cleanup function to run on exit with timeout
def _atexit_cleanup_with_timeout():
    """Atexit cleanup wrapper with timeout to prevent hanging."""
    import threading
    import time
    
    def cleanup_worker():
        try:
            _cleanup_resources()
        except Exception as e:
            logger.error(f"Error during atexit cleanup: {e}")
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    cleanup_thread.join(timeout=10)  # 10 second timeout
    
    if cleanup_thread.is_alive():
        logger.warning("Atexit cleanup timeout reached")

atexit.register(_atexit_cleanup_with_timeout)

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
    finally:
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


