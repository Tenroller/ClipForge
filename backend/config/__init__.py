"""
Centralized configuration management for VideoHelper.

This module provides a unified configuration system that replaces
scattered environment variable usage throughout the application.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
from ..logging_config import get_logger

logger = get_logger("config")


class Config:
    """Centralized configuration manager."""

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}
        self._load_defaults()
        self._load_from_env()

    def _load_defaults(self):
        """Load default configuration values."""
        # Path configurations
        from ..utils.paths import get_project_root, get_output_path, get_temp_path, get_backend_path
        project_root = get_project_root()

        self._defaults = {
            # Core paths
            'project_root': project_root,
            'output_dir': get_output_path(),
            'temp_dir': get_temp_path(),
            'backend_dir': get_backend_path(),
            'logs_dir': project_root / 'logs',

            # Video processing
            'videohelper_use_streaming': False,
            'videohelper_max_concurrent_jobs': 2,
            'videohelper_output_dir': str(get_output_path()),

            # Memory management
            'videohelper_temp_cleanup_interval': 30,  # minutes
            'videohelper_temp_max_age_hours': 24,
            'videohelper_streaming_cleanup_hours': 1,

            # Database (PostgreSQL only)
            'database_url': 'postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper',
            'videohelper_db_pool_size': 10,
            'videohelper_db_pool_timeout': 60,

            # WebSocket
            'videohelper_ws_max_age_hours': 1,
            'videohelper_ws_heartbeat': 30,

            # API
            'api_key': '',
            'cors_allow_origins': '*',
            'rate_limit_per_minute': 0,
            'trusted_hosts': '*',

            # AI/ML
            'pexels_api_key': '',
            'google_api_key': '',
            'gemini_api_key': '',


            # Authentication
            'jwt_secret_key': 'your-secret-key-change-this-in-production',
            'jwt_access_token_expire_minutes': 30,

            # External services
            'sentry_dsn': '',
            'sentry_traces_sample_rate': 0.0,
            'sentry_profiles_sample_rate': 0.0,

            # Development
            'debug_mode': False,
            'log_level': 'INFO',
        }

    def _load_from_env(self):
        """Load configuration from environment variables."""
        # Try to load .env file first
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

        # Map environment variables to config keys
        env_mappings = {
            'VIDEOHELPER_USE_STREAMING': 'videohelper_use_streaming',
            'VIDEOHELPER_MAX_CONCURRENT_JOBS': 'videohelper_max_concurrent_jobs',
            'VIDEOHELPER_OUTPUT_DIR': 'videohelper_output_dir',
            'VIDEOHELPER_TEMP_CLEANUP_INTERVAL': 'videohelper_temp_cleanup_interval',
            'VIDEOHELPER_TEMP_MAX_AGE_HOURS': 'videohelper_temp_max_age_hours',
            'VIDEOHELPER_STREAMING_CLEANUP_HOURS': 'videohelper_streaming_cleanup_hours',
            'DATABASE_URL': 'database_url',
            'VIDEOHELPER_DB_POOL_SIZE': 'videohelper_db_pool_size',
            'VIDEOHELPER_DB_POOL_TIMEOUT': 'videohelper_db_pool_timeout',
            'VIDEOHELPER_WS_MAX_AGE_HOURS': 'videohelper_ws_max_age_hours',
            'VIDEOHELPER_WS_HEARTBEAT': 'videohelper_ws_heartbeat',
            'API_KEY': 'api_key',
            'CORS_ALLOW_ORIGINS': 'cors_allow_origins',
            'RATE_LIMIT_PER_MINUTE': 'rate_limit_per_minute',
            'TRUSTED_HOSTS': 'trusted_hosts',
            'PEXELS_API_KEY': 'pexels_api_key',
            'GOOGLE_API_KEY': 'google_api_key',
            'GEMINI_API_KEY': 'gemini_api_key',
            'OPENAI_API_KEY': 'openai_api_key',
            'JWT_SECRET_KEY': 'jwt_secret_key',
            'JWT_ACCESS_TOKEN_EXPIRE_MINUTES': 'jwt_access_token_expire_minutes',
            'SENTRY_DSN': 'sentry_dsn',
            'SENTRY_TRACES_SAMPLE_RATE': 'sentry_traces_sample_rate',
            'SENTRY_PROFILES_SAMPLE_RATE': 'sentry_profiles_sample_rate',
        }

        # Load from environment
        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string values to appropriate types
                if config_key in ['videohelper_use_streaming', 'debug_mode']:
                    self._config[config_key] = value.lower() in ('true', '1', 'yes', 'on')
                elif config_key in ['videohelper_max_concurrent_jobs', 'videohelper_temp_cleanup_interval',
                                  'videohelper_temp_max_age_hours', 'videohelper_streaming_cleanup_hours',
                                  'videohelper_db_pool_size', 'videohelper_db_pool_timeout',
                                  'videohelper_ws_max_age_hours', 'videohelper_ws_heartbeat',
                                  'rate_limit_per_minute', 'jwt_access_token_expire_minutes']:
                    try:
                        self._config[config_key] = int(value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {env_var}: {value}")
                elif config_key in ['sentry_traces_sample_rate', 'sentry_profiles_sample_rate']:
                    try:
                        self._config[config_key] = float(value)
                    except ValueError:
                        logger.warning(f"Invalid float value for {env_var}: {value}")
                else:
                    self._config[config_key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, self._defaults.get(key, default))

    def set(self, key: str, value: Any):
        """Set configuration value."""
        self._config[key] = value

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value."""
        value = self.get(key, default)
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value."""
        value = self.get(key, default)
        if isinstance(value, float):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_path(self, key: str, default: Union[str, Path] = "") -> Path:
        """Get path configuration value."""
        value = self.get(key, default)
        return Path(value)

    def get_list(self, key: str, default: Optional[list] = None, separator: str = ',') -> list:
        """Get list configuration value."""
        if default is None:
            default = []

        value = self.get(key)
        if value is None:
            return default

        if isinstance(value, list):
            return value

        if isinstance(value, str):
            return [item.strip() for item in value.split(separator) if item.strip()]

        return default

    def to_dict(self) -> Dict[str, Any]:
        """Get all configuration as dictionary."""
        result = self._defaults.copy()
        result.update(self._config)
        return result

    def validate(self) -> Dict[str, Any]:
        """Validate configuration and return validation results."""
        issues = []

        # Check required paths exist
        required_paths = ['output_dir', 'temp_dir', 'backend_dir']
        for path_key in required_paths:
            path = self.get_path(path_key)
            if not path.exists():
                issues.append(f"Required path does not exist: {path_key}={path}")

        # Check API keys are set for required services
        if not self.get('pexels_api_key'):
            issues.append("PEXELS_API_KEY is not set (required for video search)")

        ai_keys = [self.get('google_api_key'), self.get('gemini_api_key'), self.get('openai_api_key')]
        if not any(ai_keys):
            issues.append("No AI API key set (GOOGLE_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY required)")

        # Check PostgreSQL database configuration
        db_url = self.get('database_url')
        if not db_url or not db_url.startswith('postgresql://'):
            issues.append("DATABASE_URL must be set to a valid PostgreSQL connection string (postgresql://user:password@host:port/database)")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'config_summary': {
                'paths_configured': all(self.get_path(p).exists() for p in required_paths),
                'api_keys_configured': bool(self.get('pexels_api_key')),
                'ai_keys_configured': any(ai_keys),
                'database_configured': bool(self.get('database_url') or self.get('database_path')),
                'streaming_enabled': self.get_bool('videohelper_use_streaming'),
            }
        }


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config():
    """Initialize the configuration system."""
    config = get_config()
    validation = config.validate()

    if validation['valid']:
        logger.info("Configuration validation passed")
    else:
        logger.warning(f"Configuration issues found: {validation['issues']}")

    # Log configuration summary
    summary = validation['config_summary']
    logger.info(f"Config summary: paths={summary['paths_configured']}, "
               f"api_keys={summary['api_keys_configured']}, "
               f"ai_keys={summary['ai_keys_configured']}, "
               f"streaming={summary['streaming_enabled']}")

    return config


# Convenience functions for common configuration access
def get_output_dir() -> Path:
    """Get output directory."""
    return get_config().get_path('output_dir')


def get_temp_dir() -> Path:
    """Get temp directory."""
    return get_config().get_path('temp_dir')


def is_streaming_enabled() -> bool:
    """Check if streaming is enabled."""
    return get_config().get_bool('videohelper_use_streaming')


def get_max_concurrent_jobs() -> int:
    """Get maximum concurrent jobs."""
    return get_config().get_int('videohelper_max_concurrent_jobs', 2)


def get_api_key() -> str:
    """Get API key."""
    return get_config().get('api_key', '')


def get_cors_origins() -> list:
    """Get CORS allowed origins."""
    return get_config().get_list('cors_allow_origins', ['*'])


# Initialize configuration when module is imported
try:
    init_config()
except Exception as e:
    logger.error(f"Failed to initialize configuration system: {e}")
