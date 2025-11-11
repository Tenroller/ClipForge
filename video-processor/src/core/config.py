"""
Video Processing API Configuration
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ProcessorConfig:
    """Configuration for the video processing service."""
    
    # Service identity
    processor_id: str = "processor-1"
    host: str = "0.0.0.0"
    port: int = 8090
    
    # Processing limits
    max_concurrent_jobs: int = 2
    job_timeout_seconds: int = 3600  # 1 hour
    
    # Backend API communication
    backend_api_url: str = "http://localhost:9000"
    backend_api_key: str = ""
    
    # Job queue persistence (PostgreSQL takes priority over Redis)
    database_url: str = ""  # PostgreSQL URL for job persistence
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 1
    enable_job_persistence: bool = True  # Enable persistent job storage

    # Directories
    output_dir: Path = Path("./output")  # Docker will mount shared volume here
    temp_dir: Path = Path("./temp")
    
    # AI API keys
    pexels_api_key: str = ""
    gemini_api_key: str = ""
    
    # Logging
    log_level: str = "INFO"
    
    # Health check
    health_check_interval: int = 30
    
    @classmethod
    def from_env(cls) -> "ProcessorConfig":
        """Create configuration from environment variables."""
        # Load .env file if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        
        def get_int(key: str, default: int) -> int:
            try:
                return int(os.getenv(key, str(default)))
            except ValueError:
                return default
        
        def get_bool(key: str, default: bool) -> bool:
            value = os.getenv(key, str(default)).lower()
            return value in ('true', '1', 'yes', 'on')

        return cls(
            processor_id=os.getenv("PROCESSOR_ID", "processor-1"),
            host=os.getenv("PROCESSOR_HOST", "0.0.0.0"),
            port=get_int("PROCESSOR_PORT", 8090),
            max_concurrent_jobs=get_int("PROCESSOR_MAX_CONCURRENT_JOBS", 2),
            job_timeout_seconds=get_int("PROCESSOR_JOB_TIMEOUT_SECONDS", 3600),
            backend_api_url=os.getenv("BACKEND_API_URL", "http://localhost:9000"),
            backend_api_key=os.getenv("BACKEND_API_KEY", ""),
            database_url=os.getenv("DATABASE_URL", ""),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            redis_db=get_int("REDIS_DB", 1),
            enable_job_persistence=get_bool("PROCESSOR_ENABLE_PERSISTENCE", True),
            output_dir=Path(os.getenv("OUTPUT_DIR", "./output")),
            temp_dir=Path(os.getenv("TEMP_DIR", "./temp")),
            pexels_api_key=os.getenv("PEXELS_API_KEY", ""),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            health_check_interval=get_int("HEALTH_CHECK_INTERVAL", 30),
        )
    
    def setup_directories(self):
        """Create necessary directories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def validate(self) -> dict:
        """Validate configuration."""
        issues = []
        warnings = []
        
        # Check required API keys
        if not self.pexels_api_key:
            issues.append("PEXELS_API_KEY is required for stock video search")
        
        if not self.gemini_api_key:
            issues.append("GEMINI_API_KEY is required for AI text generation")
        
        if not self.backend_api_key:
            warnings.append("BACKEND_API_KEY not set - communication may be insecure")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }