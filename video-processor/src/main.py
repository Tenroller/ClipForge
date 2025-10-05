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

# Import the proper logging configuration
sys.path.append(str(Path(__file__).parent.parent))
from logging_config import setup_logging

# Setup logging with Unicode support
logger = setup_logging()

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global config, job_queue, video_service
    
    # Startup
    logger.info("Starting Video Processing API...")
    
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
        video_service = VideoProcessingService(config)
        
        # Register workflow handlers
        job_queue.register_handler(WorkflowType.MONEYPRINTER, video_service.process_moneyprinter_job)
        job_queue.register_handler(WorkflowType.BRAINROT, video_service.process_brainrot_job)
        
        # Set dependencies for routes
        set_dependencies(job_queue, video_service, config.processor_id)
        
        # Start processing
        asyncio.create_task(job_queue.start_processing())
        
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
    
    uvicorn.run(
        "src.main:app",
        host=temp_config.host,
        port=temp_config.port,
        reload=False,  # Don't use reload in production
        log_level=temp_config.log_level.lower()
    )