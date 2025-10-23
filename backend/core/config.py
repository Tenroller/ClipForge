"""
Application configuration management.
"""

import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """Application configuration settings."""
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 9000
    reload: bool = False
    
    # Security settings
    trusted_hosts: Optional[List[str]] = None
    cors_origins: Optional[List[str]] = None
    cors_allow_credentials: bool = True
    
    # Rate limiting
    rate_limit_per_minute: int = 0
    
    # Job processing
    max_concurrent_jobs: int = 2
    max_resume_attempts: int = 5  # Maximum allowed attempts (original=1 + resumes)
    
    # Sentry monitoring
    sentry_dsn: Optional[str] = None
    sentry_traces_sample_rate: float = 0.0
    sentry_profiles_sample_rate: float = 0.0
    
    # Webhook settings
    webhook_url: Optional[str] = None
    
    # Core paths
    project_root: Optional[Path] = None
    output_dir: Optional[Path] = None
    temp_dir: Optional[Path] = None
    backend_dir: Optional[Path] = None
    logs_dir: Optional[Path] = None
    
    # Video processing
    videohelper_use_streaming: bool = False
    videohelper_output_dir: str = ""
    
    # Video processor orchestration
    video_processor_urls: List[str] = field(default_factory=lambda: ["http://localhost:8090"])
    video_processor_api_key: str = ""
    video_processor_timeout: int = 30
    video_processor_poll_interval: int = 5  # seconds
    video_processor_max_retries: int = 3
    backend_callback_url: str = "http://localhost:9000"  # Backend URL for processor callbacks
    
    # Memory management
    videohelper_temp_cleanup_interval: int = 30  # minutes
    videohelper_temp_max_age_hours: int = 24
    videohelper_streaming_cleanup_hours: int = 1
    
    # Database (PostgreSQL only)
    database_url: str = 'postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper'
    videohelper_db_pool_size: int = 10
    videohelper_db_pool_timeout: int = 60
    
    # API keys
    api_key: str = ""
    pexels_api_key: str = ""
    gemini_api_key: str = ""
    
    # Authentication
    jwt_secret_key: str = 'your-secret-key-change-this-in-production'
    jwt_access_token_expire_minutes: int = 30
    
    # Development
    debug_mode: bool = False
    log_level: str = 'INFO'
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables."""
        # Load .env file if available
        try:
            from dotenv import load_dotenv
            from ..utils.paths import get_project_root
            project_root = get_project_root()
            env_path = project_root / ".env"
            if env_path.exists():
                load_dotenv(env_path)
        except ImportError:
            # python-dotenv not available, continue with env vars only
            pass
        except Exception:
            # Any other error, continue with env vars only
            pass
        
        # Helper functions for type conversion
        def get_bool(key: str, default: bool = False) -> bool:
            return os.getenv(key, str(default)).lower() in ('true', '1', 'yes', 'on')
        
        def get_int(key: str, default: int = 0) -> int:
            try:
                return int(os.getenv(key, str(default)))
            except ValueError:
                return default
        
        def get_float(key: str, default: float = 0.0) -> float:
            try:
                return float(os.getenv(key, str(default)))
            except ValueError:
                return default
        
        # Initialize paths
        from ..utils.paths import get_project_root, get_output_path, get_temp_path, get_backend_path
        project_root = get_project_root()
        output_dir = get_output_path()
        temp_dir = get_temp_path()
        backend_dir = get_backend_path()
        logs_dir = project_root / 'logs'
        
        # Parse CORS origins
        cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
        if cors_origins_env.strip() == "*":
            cors_origins = [
                "http://localhost:3000",   # Frontend (production nginx)
                "http://127.0.0.1:3000",
                "http://localhost:5173",  # Vite dev server
                "http://127.0.0.1:5173", 
                "http://localhost:9000",  # Backend self
                "http://127.0.0.1:9000",
            ]
        else:
            cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
        
        # Parse trusted hosts
        trusted_hosts_env = os.getenv("TRUSTED_HOSTS", "*")
        if trusted_hosts_env.strip() == "*":
            trusted_hosts = None
        else:
            trusted_hosts = [h.strip() for h in trusted_hosts_env.split(",") if h.strip()]
            
        return cls(
            # Server settings
            host=os.getenv("HOST", "0.0.0.0"),
            port=get_int("PORT", 9000),
            reload=get_bool("RELOAD", False),
            
            # Security settings
            trusted_hosts=trusted_hosts,
            cors_origins=cors_origins,
            cors_allow_credentials=True,
            
            # Rate limiting
            rate_limit_per_minute=get_int("RATE_LIMIT_PER_MINUTE", 0),
            
            # Job processing
            max_concurrent_jobs=get_int("VIDEOHELPER_MAX_CONCURRENT_JOBS", 2),
            max_resume_attempts=get_int("VIDEOHELPER_MAX_RESUME_ATTEMPTS", 5),
            
            # Sentry monitoring
            sentry_dsn=os.getenv("SENTRY_DSN"),
            sentry_traces_sample_rate=get_float("SENTRY_TRACES_SAMPLE_RATE", 0.0),
            sentry_profiles_sample_rate=get_float("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
            
            # Webhook settings
            webhook_url=os.getenv("WEBHOOK_URL"),
            
            # Core paths
            project_root=project_root,
            output_dir=output_dir,
            temp_dir=temp_dir,
            backend_dir=backend_dir,
            logs_dir=logs_dir,
            
            # Video processing
            videohelper_use_streaming=get_bool("VIDEOHELPER_USE_STREAMING", False),
            videohelper_output_dir=os.getenv("VIDEOHELPER_OUTPUT_DIR", str(output_dir)),
            
            # Video processor orchestration
            video_processor_urls=os.getenv("VIDEO_PROCESSOR_URLS", "http://localhost:8090").split(","),
            video_processor_api_key=os.getenv("VIDEO_PROCESSOR_API_KEY", ""),
            video_processor_timeout=get_int("VIDEO_PROCESSOR_TIMEOUT", 30),
            video_processor_poll_interval=get_int("VIDEO_PROCESSOR_POLL_INTERVAL", 5),
            video_processor_max_retries=get_int("VIDEO_PROCESSOR_MAX_RETRIES", 3),
            backend_callback_url=os.getenv("BACKEND_CALLBACK_URL", "http://localhost:9000"),
            
            # Memory management
            videohelper_temp_cleanup_interval=get_int("VIDEOHELPER_TEMP_CLEANUP_INTERVAL", 30),
            videohelper_temp_max_age_hours=get_int("VIDEOHELPER_TEMP_MAX_AGE_HOURS", 24),
            videohelper_streaming_cleanup_hours=get_int("VIDEOHELPER_STREAMING_CLEANUP_HOURS", 1),
            
            # Database
            database_url=os.getenv("DATABASE_URL", "postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper"),
            videohelper_db_pool_size=get_int("VIDEOHELPER_DB_POOL_SIZE", 10),
            videohelper_db_pool_timeout=get_int("VIDEOHELPER_DB_POOL_TIMEOUT", 60),
            
            # API keys
            api_key=os.getenv("API_KEY", ""),
            pexels_api_key=os.getenv("PEXELS_API_KEY", ""),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            
            # Authentication
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production"),
            jwt_access_token_expire_minutes=get_int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30),
            
            # Development
            debug_mode=get_bool("DEBUG_MODE", False),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
    
    def validate_environment(self) -> dict:
        """Validate environment configuration."""
        import os
        
        env_issues = []
        env_warnings = []
        
        # Check required environment variables
        required_env = [
            ('PEXELS_API_KEY', 'Required for stock video search'),
        ]
        
        # Check for Gemini API key
        if not os.getenv('GEMINI_API_KEY'):
            env_issues.append("GEMINI_API_KEY is required for AI text generation")
        
        for env_var, description in required_env:
            if not os.getenv(env_var):
                env_issues.append(f"{env_var} not set: {description}")
        
        # Check for conflicting configurations
        if os.getenv('DATABASE_URL') and os.getenv('DATABASE_PATH'):
            env_warnings.append("Both DATABASE_URL and DATABASE_PATH set - DATABASE_URL takes precedence")
        
        return {
            'environment_valid': len(env_issues) == 0,
            'issues': env_issues,
            'warnings': env_warnings,
            'config_valid': True  # AppConfig is always valid by construction
        }
