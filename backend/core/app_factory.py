"""
FastAPI application factory and configuration.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .config import AppConfig
from .lifespan import lifespan
from ..middleware.logging import LoggingMiddleware
from ..api.routes import register_routes


def setup_sentry(config: AppConfig) -> None:
    """Setup Sentry error tracking if configured."""
    if not config.sentry_dsn:
        return
        
    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        
        sentry_sdk.init(
            dsn=config.sentry_dsn,
            integrations=[FastApiIntegration()],
            traces_sample_rate=config.sentry_traces_sample_rate,
            profiles_sample_rate=config.sentry_profiles_sample_rate,
        )
    except ImportError:
        # Sentry is optional; ignore any initialization/import failure
        pass


def setup_middleware(app: FastAPI, config: AppConfig) -> None:
    """Setup application middleware."""
    
    # Add security middleware
    if config.trusted_hosts and config.trusted_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.trusted_hosts)

    # Add logging middleware
    app.add_middleware(LoggingMiddleware)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins or ["*"],
        allow_credentials=config.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    if config is None:
        config = AppConfig.from_env()
    
    # Setup Sentry monitoring
    setup_sentry(config)
    
    # Create FastAPI app
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
    
    # Setup middleware
    setup_middleware(app, config)
    
    # Register API routes
    register_routes(app)
    
    # Store config in app state for access by routes
    app.state.config = config
    
    return app
