"""
API route registration.
"""

from fastapi import FastAPI

from .health import router as health_router
from .video_generation import router as video_generation_router
from .job_management import router as job_management_router
from .job_callbacks import router as job_callbacks_router
from .system import router as system_router
from .videos import router as videos_router
from .video_management import router as video_management_router


def register_routes(app: FastAPI) -> None:
    """Register all API routes with the FastAPI application."""
    
    # Health and system status
    app.include_router(health_router, tags=["System"])
    
    # Video generation workflows
    app.include_router(video_generation_router, prefix="/api", tags=["Video Generation"])
    
    # Job management and monitoring
    app.include_router(job_management_router, prefix="/api", tags=["Job Management"])
    
    # Job callbacks from video processor
    app.include_router(job_callbacks_router, prefix="/api", tags=["Job Callbacks"])
    
    # Video management and listing (legacy)
    app.include_router(videos_router, prefix="/api", tags=["Video Management"])
    
    # Video management (new tracking system)
    app.include_router(video_management_router, prefix="/api", tags=["Video Tracking"])
    
    # System management and maintenance
    app.include_router(system_router, prefix="/api", tags=["System"])
