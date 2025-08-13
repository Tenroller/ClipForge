import os
import sys
import uuid
import json
import shutil
import contextlib
from contextlib import asynccontextmanager
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

import asyncio
from collections import defaultdict
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from collections import deque
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from validation import (
    validate_youtube_url, validate_subject, validate_custom_prompt,
    validate_zip_url, validate_color, validate_subtitle_position,
    validate_ai_model, validate_voice
)
from logging_config import get_logger, log_request, log_job_event, log_error, log_security_event
from metrics import get_metrics, record_request_metrics, init_metrics_system, track_job_metrics
from caching import get_cache, cached
from thumbnail_generator import get_thumbnail_generator, create_video_preview_package
from batch_processing import get_batch_processor
from batch_processing import create_brainrot_batch_from_playlist


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
    print(f"✅ Configured system espeak-ng for Kokoro TTS:")
    print(f"   ESPEAK_PATH: {system_espeak}")
    print(f"   DATA_PATH: {system_data}")
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
            
        print(f"⚠️  Using espeakng_loader (may have issues):")
        print(f"   DATA_PATH: {espeak_data_path}")
        print(f"   LIB_PATH: {espeak_lib_path}")
    except ImportError:
        print("❌ Neither system espeak-ng nor espeakng_loader found - Kokoro TTS may not work")
        print("   Install espeak-ng: brew install espeak-ng (macOS) or apt install espeak-ng (Ubuntu)")
    except Exception as e:
        print(f"⚠️  Error setting up espeak-ng environment: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context to manage background broadcaster task."""
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()

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
        with contextlib.suppress(Exception, asyncio.CancelledError):
            await broadcaster_task


# Initialize logger
logger = get_logger("video_generator")


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
    _allow_origins = ["*"]
    _allow_credentials = False
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
    useCloudGPU: bool = False
    voice: str = "af_bella"
    customPrompt: Optional[str] = None

    @validator('videoSubject')
    def validate_subject_field(cls, v):
        return validate_subject(v)

    @validator('aiModel')
    def validate_ai_model_field(cls, v):
        return validate_ai_model(v)

    @validator('voice')
    def validate_voice_field(cls, v):
        return validate_voice(v)

    @validator('color')
    def validate_color_field(cls, v):
        return validate_color(v)

    @validator('subtitlesPosition')
    def validate_subtitle_position_field(cls, v):
        return validate_subtitle_position(v)

    @validator('zipUrl')
    def validate_zip_url_field(cls, v):
        return validate_zip_url(v)

    @validator('customPrompt')
    def validate_custom_prompt_field(cls, v):
        return validate_custom_prompt(v)


class BrainrotRequest(BaseModel):
    youtubeUrl: str
    numCompilations: int = Field(default=1, ge=1, le=10)
    minDuration: int = Field(default=60, ge=10, le=3600)
    maxDuration: int = Field(default=110, ge=10, le=3600)
    maxReuse: int = Field(default=3, ge=1, le=10)

    @validator('youtubeUrl')
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
        print(f"✅ Migrated {migrated} jobs from JSON to database")
        # Keep the JSON file as backup
        backup_file = JOBS_FILE.with_suffix(".json.backup")
        JOBS_FILE.rename(backup_file)
        print(f"   Backed up original file to {backup_file}")

# Initialize enhanced systems
try:
    init_metrics_system()
    get_cache()  # Initialize cache
    get_batch_processor()  # Initialize batch processor
    logger.info("✅ All enhanced systems initialized")
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


def make_rate_limiter(bucket: str):
    def _dep(request: Request) -> None:
        # Read the current limit from environment at request time to respect test overrides
        current_limit_env = os.getenv("RATE_LIMIT_PER_MINUTE", "0") or "0"
        try:
            current_limit = int(current_limit_env)
        except Exception:
            current_limit = 0
        if current_limit <= 0:
            return
        client_ip = (request.client.host if request.client else "unknown") or "unknown"
        key = f"{bucket}:{client_ip}"
        now = time.time()
        window_start = now - 60.0
        with RATE_LIMIT_LOCK:
            dq = RATE_LIMIT_BUCKETS[key]
            while dq and dq[0] < window_start:
                dq.popleft()
            if len(dq) >= current_limit:
                raise HTTPException(status_code=429, detail="Too Many Requests")
            dq.append(now)
    return _dep


@app.get("/api/health", tags=["System"], summary="Health Check")
def health():
    return {
        "status": "ok",
        "cwd": str(Path.cwd()),
        "root": str(ROOT),
        "moneyprinter_present": MONEYPRINTER_BACKEND.exists(),
        "brainrot_present": BRAINROT_ROOT.exists(),
    }


@app.get(
    "/api/ping", 
    tags=["System"], 
    summary="Authentication Test",
    description="Test endpoint to verify API key authentication is working"
)
def ping(_: None = Depends(require_api_key)) -> Dict[str, Any]:
    return {"ok": True}


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
    __: None = Depends(make_rate_limiter("moneyprinter")),
):
    job_id = str(uuid.uuid4())
    job_store.create_job(job_id, "moneyprinter", req.dict())
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
        try:
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

                _update_job(job_id, step="validate_env")
                _log_job("validate_env: checking MoneyPrinter environment variables")
                try:
                    check_env_vars()
                except SystemExit:
                    raise RuntimeError("Missing required MoneyPrinter environment variables")

                _check_cancel(job_id)
                if req.useMusic and req.zipUrl:
                    _update_job(job_id, step="fetch_music")
                    _log_job(f"fetch_music: downloading songs from zipUrl={req.zipUrl}")
                    fetch_songs(req.zipUrl)

                _check_cancel(job_id)
                _update_job(job_id, step="script_generation")
                _log_job(f"script_generation: model={req.aiModel} voice={req.voice} paragraphs={req.paragraphNumber}")
                script = generate_script(req.videoSubject, req.paragraphNumber, req.aiModel, req.voice, req.customPrompt or "")
                if not script:
                    raise RuntimeError("Script generation failed")

                _check_cancel(job_id)
                _update_job(job_id, step="search_terms")
                terms = get_search_terms(req.videoSubject, 10, script, req.aiModel)
                _log_job(f"search_terms: {len(terms)} terms -> {terms[:5]}{'...' if len(terms) > 5 else ''}")

                _check_cancel(job_id)
                _update_job(job_id, step="stock_download")
                voice_prefix = req.voice

                # Download several videos per term locally, filter by duration >= 4
                video_paths: list[str] = []
                for term in terms:
                    urls = search_for_stock_videos(term, os.getenv("PEXELS_API_KEY", ""), 5, 4)
                    for url in urls[:2]:
                        _check_cancel(job_id)
                        try:
                            local_path = mp_save_video(url, directory="../temp")
                            video_paths.append(local_path)
                        except Exception:
                            continue
                if not video_paths:
                    raise RuntimeError("No stock videos downloaded")
                else:
                    _log_job(f"stock_download: downloaded {len(video_paths)} clips")

                _check_cancel(job_id)
                _update_job(job_id, step="tts")
                _log_job(f"tts: generating {len([s for s in script.split('. ') if s])} audio segments using voice={voice_prefix}")
                sentences = [s for s in script.split(". ") if s]
                audio_clips = []
                temp_dir = Path("../temp")
                temp_dir.mkdir(exist_ok=True)
                for s in sentences:
                    _check_cancel(job_id)
                    current_tts_path = temp_dir / f"{uuid.uuid4()}.mp3"
                    tts(s, req.voice, filename=str(current_tts_path))
                    audio_clips.append(AudioFileClip(str(current_tts_path)))

                if not audio_clips:
                    raise RuntimeError("No audio clips generated")

                tts_path = str(temp_dir / f"{uuid.uuid4()}.mp3")
                concatenate_audioclips(audio_clips).write_audiofile(tts_path)
                _log_job(f"tts: concatenated audio -> {tts_path}")

                _check_cancel(job_id)
                _update_job(job_id, step="subtitles")
                subtitles_path = generate_subtitles(audio_path=tts_path, sentences=sentences, audio_clips=audio_clips, voice=voice_prefix)
                try:
                    sp = Path(subtitles_path)
                    head = ""
                    if sp.exists():
                        with sp.open("r", encoding="utf-8", errors="ignore") as fh:
                            # Read first ~3 lines to help debug format
                            for _ in range(3):
                                line = fh.readline()
                                if not line:
                                    break
                                head += line.strip() + " | "
                    _log_job(f"subtitles: path={subtitles_path} exists={sp.exists()} size={sp.stat().st_size if sp.exists() else 'n/a'} head={head[:200]}")
                except Exception as e:
                    _log_job(f"subtitles: failed to inspect file ({e})")

                _check_cancel(job_id)
                _update_job(job_id, step="compose_video")
                _log_job(
                    f"compose_video: threads={req.threads or 2} useGPU={req.useGPU} color={req.color or '#FFFF00'} position={req.subtitlesPosition}"
                )
                temp_audio = AudioFileClip(tts_path)
                combined_video_path = combine_videos(video_paths, int(temp_audio.duration), 5, req.threads or 2, req.useGPU)
                _log_job(f"compose_video: combined video -> {combined_video_path}")

                # Log environment versions helpful for font/TextClip issues
                try:
                    import platform  # type: ignore
                    import moviepy  # type: ignore
                    from PIL import Image, ImageFont, __version__ as PIL_VERSION  # type: ignore
                    _log_job(
                        f"env: python={platform.python_version()} moviepy={getattr(moviepy, '__version__', 'unknown')} pillow={PIL_VERSION}"
                    )
                    _log_job(f"PIL ImageFont module file={getattr(ImageFont, '__file__', 'unknown')}")
                except Exception as e:
                    _log_job(f"env: failed to get version info ({e})")

                try:
                    final_video_path = generate_video(
                        combined_video_path,
                        tts_path,
                        subtitles_path or "",
                        req.threads or 2,
                        req.subtitlesPosition,
                        req.color or "#FFFF00",
                        req.useGPU,
                    )
                except Exception as ge:
                    import traceback
                    tb = traceback.format_exc()
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
                    _log_job(f"done: final video -> {final_video_path}")
                    _update_job(job_id, status="done", result={"output": str(final_video_path), "subtitles": subtitles_path})
        except Exception as e:
            if str(e) == "cancelled":
                _update_job(job_id, status="cancelled", error="cancelled")
            else:
                # Preserve the last known step in the error and include a hint if it's a font/TextClip issue
                hint = ""
                msg = str(e)
                if any(k in msg.lower() for k in ["font", "pillow", "textclip"]):
                    hint = " (possible font/Pillow/TextClip configuration issue)"
                _log_job(f"error: {msg}{hint}")
                _update_job(job_id, status="error", error=msg)

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
    ensure_on_path(MONEYPRINTER_BACKEND)
    with pushd(MONEYPRINTER_BACKEND):
        try:
            from vendors.moneyprinter.gpt import generate_response  # type: ignore
        except Exception as e:
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
        raw = generate_response(prompt, model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini request failed: {e}")

    text = (raw or "").strip().splitlines()[0] if raw else ""
    # light cleanup: drop surrounding quotes and trailing punctuation
    text = text.strip().strip('"\'').strip()
    if text.endswith(('.', '!', '?')):
        text = text[:-1].strip()
    if not text:
        raise HTTPException(status_code=502, detail="Empty subject from model")
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
            from vendors.moneyprinter.tiktokvoice import list_voices as kokoro_voices  # type: ignore
            voices = kokoro_voices()
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

    voices = set(kokoro_voices())
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
    __: None = Depends(make_rate_limiter("brainrot")),
):
    job_id = str(uuid.uuid4())
    job_store.create_job(job_id, "brainrot", req.dict())
    JOB_CONTROLS[job_id] = {"cancel": threading.Event()}
    _enqueue_job_update(job_id)

    def _run_job():
        try:
            ensure_on_path(BRAINROT_ROOT)
            with pushd(BRAINROT_ROOT):
                from tikyou_video_generator.generator import TikYouGenerator  # type: ignore

                _check_cancel(job_id)
                _update_job(job_id, step="process_video")
                unified_output_dir = os.getenv("VIDEOHELPER_OUTPUT_DIR")
                if unified_output_dir:
                    output_dir = str(Path(unified_output_dir).resolve())
                else:
                    output_dir = str((ROOT / "brainrot_output").resolve())
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
                )

                if not JOB_CONTROLS[job_id]["cancel"].is_set():
                    _update_job(job_id, status="done", result={"output_dir": output_dir})
        except Exception as e:
            if str(e) == "cancelled":
                _update_job(job_id, status="cancelled", error="cancelled")
            else:
                _update_job(job_id, status="error", error=str(e))

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


@app.get("/api/jobs/stats")
def job_stats(_: None = Depends(require_api_key)) -> Dict[str, Any]:
    """Get job statistics."""
    return job_store.get_stats()


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


@app.get("/api/cache/stats", tags=["System"], summary="Get Cache Stats")
def get_cache_stats(_: None = Depends(require_api_key)) -> Dict[str, Any]:
    """Get cache statistics."""
    return get_cache().stats()


@app.post("/api/cache/clear", tags=["System"], summary="Clear Cache")
def clear_cache(levels: str = "all", _: None = Depends(require_api_key)) -> Dict[str, Any]:
    """Clear cache levels (l1, l2, l3, or all)."""
    success = get_cache().clear(levels)
    return {"success": success, "levels_cleared": levels}


@app.post("/api/videos/{job_id}/thumbnails", tags=["Video Processing"], summary="Generate Thumbnails")
def generate_thumbnails(job_id: str, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    """Generate thumbnails for a completed video job."""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    result = job.get("result", {})
    video_path = result.get("video_path")
    
    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    try:
        preview_package = create_video_preview_package(Path(video_path))
        return {"success": True, "preview_package": preview_package}
    except Exception as e:
        logger.error(f"Failed to generate thumbnails: {e}")
        raise HTTPException(status_code=500, detail=f"Thumbnail generation failed: {str(e)}")


# Batch processing endpoints

@app.post("/api/batch", tags=["Batch Processing"], summary="Create Batch")
def create_batch(
    name: str,
    workflow: str,
    job_parameters: List[Dict[str, Any]],
    priority: str = "normal",
    max_concurrent: int = 3,
    stop_on_error: bool = False,
    _: None = Depends(require_api_key)
) -> Dict[str, str]:
    """Create a new batch processing request."""
    from job_queue import JobPriority
    
    priority_map = {
        "low": JobPriority.LOW,
        "normal": JobPriority.NORMAL,
        "high": JobPriority.HIGH,
        "critical": JobPriority.CRITICAL
    }
    
    batch_priority = priority_map.get(priority.lower(), JobPriority.NORMAL)
    
    batch_processor = get_batch_processor()
    batch_id = batch_processor.create_batch(
        name=name,
        workflow=workflow,
        job_parameters=job_parameters,
        priority=batch_priority,
        max_concurrent=max_concurrent,
        stop_on_error=stop_on_error
    )
    
    return {"batch_id": batch_id}


@app.post("/api/batch/{batch_id}/start", tags=["Batch Processing"], summary="Start Batch")
def start_batch(batch_id: str, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    """Start processing a batch."""
    batch_processor = get_batch_processor()
    success = batch_processor.start_batch(batch_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to start batch")
    
    return {"success": True, "batch_id": batch_id}


@app.get("/api/batch/{batch_id}", tags=["Batch Processing"], summary="Get Batch Status")
def get_batch_status(batch_id: str, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    """Get batch status and progress."""
    batch_processor = get_batch_processor()
    status = batch_processor.get_batch_status(batch_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return status


@app.get("/api/batch/{batch_id}/results", tags=["Batch Processing"], summary="Get Batch Results")
def get_batch_results(batch_id: str, _: None = Depends(require_api_key)) -> List[Dict[str, Any]]:
    """Get detailed results for a batch."""
    batch_processor = get_batch_processor()
    results = batch_processor.get_batch_results(batch_id)
    
    if results is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return results


@app.post("/api/batch/{batch_id}/cancel", tags=["Batch Processing"], summary="Cancel Batch")
def cancel_batch(batch_id: str, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    """Cancel a batch and all its jobs."""
    batch_processor = get_batch_processor()
    success = batch_processor.cancel_batch(batch_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return {"success": True, "batch_id": batch_id}


@app.get("/api/batches", tags=["Batch Processing"], summary="List Batches")
def list_batches(limit: int = 50, _: None = Depends(require_api_key)) -> List[Dict[str, Any]]:
    """List all batches."""
    batch_processor = get_batch_processor()
    return batch_processor.list_batches(limit=limit)


@app.post("/api/batch/template", tags=["Batch Processing"], summary="Create Template Batch")
def create_template_batch(
    template_type: str,
    count: int = 10,
    _: None = Depends(require_api_key)
) -> Dict[str, str]:
    """Create a batch from a template."""
    batch_processor = get_batch_processor()
    
    try:
        batch_id = batch_processor.create_template_batch(template_type, count)
        return {"batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@app.post("/api/brainrot/playlist", tags=["Batch Processing"], summary="Create Brainrot batch from YouTube playlist")
def brainrot_playlist_batch(req: PlaylistBatchRequest, _: None = Depends(require_api_key)) -> Dict[str, Any]:
    """Expand a YouTube playlist/channel URL into videos and create a Brainrot batch.
    Returns batch_id and total_urls, then you can POST /api/batch/{batch_id}/start.
    """
    try:
        result = create_brainrot_batch_from_playlist(
            req.playlistUrl,
            name=req.name,
            limit=req.limit,
            sample=req.sample,
            shuffle=req.shuffle,
            priority=req.priority,
            max_concurrent=req.maxConcurrent,
            stop_on_error=req.stopOnError,
            numCompilations=req.numCompilations,
            minDuration=req.minDuration,
            maxDuration=req.maxDuration,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create playlist batch: {e}")


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
    allowed_roots = [DEFAULT_OUTPUT_DIR.resolve(), (ROOT / "brainrot_output").resolve()]
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
    if not file_path.exists() or not file_path.is_file():
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)


