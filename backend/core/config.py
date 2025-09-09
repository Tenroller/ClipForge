"""
Application configuration management.
"""

import os
from typing import List, Optional
from dataclasses import dataclass

from ..config import get_config


@dataclass
class AppConfig:
    """Application configuration settings."""
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    reload: bool = False
    
    # Security settings
    trusted_hosts: Optional[List[str]] = None
    cors_origins: Optional[List[str]] = None
    cors_allow_credentials: bool = True
    
    # Rate limiting
    rate_limit_per_minute: int = 0
    
    # Job processing
    max_concurrent_jobs: int = 2
    
    # Sentry monitoring
    sentry_dsn: Optional[str] = None
    sentry_traces_sample_rate: float = 0.0
    sentry_profiles_sample_rate: float = 0.0
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables."""
        config = get_config()
        
        # Parse CORS origins
        cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
        if cors_origins_env.strip() == "*":
            cors_origins = [
                "http://localhost:5173",
                "http://127.0.0.1:5173", 
                "http://localhost:8080",
                "http://127.0.0.1:8080",
            ]
        else:
            cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
        
        # Parse trusted hosts
        trusted_hosts = os.getenv("TRUSTED_HOSTS", "*").split(",")
        if trusted_hosts == ["*"]:
            trusted_hosts = None
            
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8080")),
            reload=os.getenv("RELOAD", "false").lower() == "true",
            trusted_hosts=trusted_hosts,
            cors_origins=cors_origins,
            cors_allow_credentials=True,
            rate_limit_per_minute=config.get_int('rate_limit_per_minute', 0),
            max_concurrent_jobs=config.get_int('videohelper_max_concurrent_jobs', 2),
            sentry_dsn=os.getenv("SENTRY_DSN"),
            sentry_traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
            sentry_profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0")),
        )
