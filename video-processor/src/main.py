"""
Video Processing API Main Application
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Setup logging with Unicode support for Windows
import os
if sys.platform == "win32":
    # Set environment variable for UTF-8 encoding
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # Try to set console code page to UTF-8
    try:
        import subprocess
        subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
    except Exception:
        pass
    
    # ==========================================================================
    # FFmpeg Configuration for torio/torchaudio (used by pyannote.audio)
    # This MUST be done before any import of torchaudio or pyannote
    # ==========================================================================
    FFMPEG_SHARED_BIN = r"C:\ffmpeg-shared\ffmpeg-6.1.1-full_build-shared\bin"
    FFMPEG_STATIC_BIN = r"C:\ffmpeg\bin"
    
    if os.path.exists(FFMPEG_SHARED_BIN):
        # CRITICAL: For Python 3.8+ on Windows, we must use os.add_dll_directory()
        # to allow torio/torchaudio to find FFmpeg DLLs
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(FFMPEG_SHARED_BIN)
        # Add to PATH for subprocess calls
        current_path = os.environ.get("PATH", "")
        if FFMPEG_SHARED_BIN not in current_path:
            os.environ["PATH"] = FFMPEG_SHARED_BIN + os.pathsep + current_path
        os.environ["FFMPEG_BINARY"] = os.path.join(FFMPEG_SHARED_BIN, "ffmpeg.exe")
    elif os.path.exists(FFMPEG_STATIC_BIN):
        # Fallback to static FFmpeg - suppress torio warnings
        import warnings
        import logging as std_logging
        warnings.filterwarnings("ignore", message=".*FFmpeg.*extension.*")
        std_logging.getLogger("torio._extension.utils").setLevel(std_logging.ERROR)
        current_path = os.environ.get("PATH", "")
        if FFMPEG_STATIC_BIN not in current_path:
            os.environ["PATH"] = FFMPEG_STATIC_BIN + os.pathsep + current_path
        os.environ["FFMPEG_BINARY"] = os.path.join(FFMPEG_STATIC_BIN, "ffmpeg.exe")

# Import the proper logging configuration
sys.path.append(str(Path(__file__).parent.parent))
from logging_config import setup_logging
from loguru import logger as loguru_logger

# Setup logging with Unicode support
setup_logging()
logger = loguru_logger

# Import our modules
from .core.config import ProcessorConfig
from .core.simple_queue import ProcessorJobQueue
from .services.video_processing import VideoProcessingService
from .api.routes import router, set_dependencies
from .models import WorkflowType

# Global instances
config: ProcessorConfig
job_queue: ProcessorJobQueue
video_service: VideoProcessingService


def _auto_update_yt_dlp(check_interval_days: int = 1):
    """Auto-update yt-dlp on startup if needed.

    Args:
        check_interval_days: Only update if last check was more than N days ago
    """
    from datetime import datetime, timedelta

    # Import from parent utils directory
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.youtube import update_yt_dlp, check_yt_dlp_version

    last_check_file = Path(__file__).parent.parent / ".yt_dlp_last_check"

    try:
        # Check if we updated recently
        if last_check_file.exists():
            last_check = datetime.fromtimestamp(last_check_file.stat().st_mtime)
            if datetime.now() - last_check < timedelta(days=check_interval_days):
                logger.debug(f"yt-dlp update check skipped (last check: {last_check.strftime('%Y-%m-%d')})")
                return

        current_version = check_yt_dlp_version()
        logger.info(f"Current yt-dlp version: {current_version}")
        logger.info("Checking for yt-dlp updates...")

        success = update_yt_dlp()

        if success:
            # Touch the file to record last check time
            last_check_file.touch()
            new_version = check_yt_dlp_version()
            if new_version and new_version != current_version:
                logger.info(f"yt-dlp updated: {current_version} -> {new_version}")
            else:
                logger.info("yt-dlp is already up to date")
        else:
            logger.warning("yt-dlp update check failed, continuing with current version")

    except Exception as e:
        logger.error(f"Error during yt-dlp auto-update: {e}")
        # Don't fail startup if update fails


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global config, job_queue, video_service

    # Startup
    logger.info("Starting Video Processing API...")

    # Setup FFmpeg environment before any video processing
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from utils.ffmpeg_utils import setup_ffmpeg_environment, verify_ffmpeg_installation

    logger.info("Setting up FFmpeg environment...")
    ffmpeg_path, ffprobe_path = setup_ffmpeg_environment()

    # Verify FFmpeg installation
    ffmpeg_status = verify_ffmpeg_installation()
    if not ffmpeg_status["ffmpeg_available"]:
        logger.error(f"FFmpeg not found! Error: {ffmpeg_status.get('error', 'Unknown error')}")
        logger.error("Please install FFmpeg: https://ffmpeg.org/download.html")
        raise RuntimeError("FFmpeg is required but not found")

    logger.info(f"FFmpeg setup complete: ffmpeg={ffmpeg_status['ffmpeg_path']}, ffprobe={ffmpeg_status['ffprobe_path']}")

    # Auto-update yt-dlp on startup
    _auto_update_yt_dlp(check_interval_days=1)

    try:
        # Load configuration
        config = ProcessorConfig.from_env()
        logger.info(f"Loaded configuration for processor: {config.processor_id}")
        
        # Validate configuration
        validation = config.validate()
        if not validation['valid']:
            for issue in validation['issues']:
                logger.error(f"Configuration issue: {issue}")
            raise RuntimeError("Invalid configuration")
        
        for warning in validation.get('warnings', []):
            logger.warning(f"Configuration warning: {warning}")
        
        # Setup directories
        config.setup_directories()
        logger.info(f"Setup directories: output={config.output_dir}, temp={config.temp_dir}")
        
        # Initialize job queue
        job_queue = ProcessorJobQueue(config)
        await job_queue.connect()

        # Initialize video processing service
        video_service = VideoProcessingService(config, job_queue=job_queue)
        
        # Register workflow handlers
        job_queue.register_handler(WorkflowType.MONEYPRINTER, video_service.process_moneyprinter_job)
        job_queue.register_handler(WorkflowType.BRAINROT, video_service.process_brainrot_job)
        job_queue.register_handler(WorkflowType.PODCASTCLIPS, video_service.process_podcastclips_job)
        
        # Set dependencies for routes
        set_dependencies(job_queue, video_service, config.processor_id)
        
        # Start processing
        asyncio.create_task(job_queue.start_processing())

        # Initialize temp file manager with protected files from active jobs
        from utils.file_management import init_temp_manager, get_temp_manager
        init_temp_manager()
        get_temp_manager().set_protected_files_fn(job_queue.get_active_job_files)

        logger.info(f"Video Processing API started successfully on {config.host}:{config.port}")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start Video Processing API: {e}")
        raise
    
    # Shutdown
    logger.info("Shutting down Video Processing API...")
    
    try:
        if job_queue:
            await job_queue.stop_processing()
            await job_queue.disconnect()
        
        logger.info("Video Processing API shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Video Processing API",
        description="Microservice for processing video generation workflows",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify exact origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routes
    app.include_router(router, prefix="/api/v1")
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "service": "Video Processing API",
            "version": "1.0.0",
            "status": "running",
            "processor_id": config.processor_id if 'config' in globals() else "unknown"
        }
    
    # Health endpoint
    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "service": "Video Processing API",
            "processor_id": config.processor_id if 'config' in globals() else "unknown",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # Load config to get port
    temp_config = ProcessorConfig.from_env()

    # Configure uvicorn to use loguru (disable default logging)
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO"},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO"},
            "uvicorn.access": {"handlers": ["default"], "level": "INFO"},
        },
    }

    uvicorn.run(
        "src.main:app",
        host=temp_config.host,
        port=temp_config.port,
        reload=False,  # Don't use reload in production
        log_level=temp_config.log_level.lower(),
        log_config=log_config
    )