"""
Configuration validation utilities.

This module provides validation functions for configuration values
to ensure they meet requirements and constraints.
"""

import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse


def validate_api_key(api_key: str) -> Tuple[bool, str]:
    """
    Validate API key format.

    Args:
        api_key: API key string

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key:
        return True, ""  # Empty API key is allowed (no auth)

    if len(api_key) < 8:
        return False, "API key must be at least 8 characters long"

    if len(api_key) > 128:
        return False, "API key must be no more than 128 characters long"

    # Check for basic security requirements
    if not re.match(r'^[a-zA-Z0-9\-_\.]+$', api_key):
        return False, "API key contains invalid characters (only alphanumeric, dash, underscore, dot allowed)"

    return True, ""


def validate_database_url(db_url: str) -> Tuple[bool, str]:
    """
    Validate database URL format.

    Args:
        db_url: Database URL string

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not db_url:
        return True, ""  # Empty URL is allowed (use SQLite file)

    try:
        parsed = urlparse(db_url)

        # Check scheme
        if parsed.scheme not in ['sqlite', 'postgresql', 'mysql', 'oracle']:
            return False, f"Unsupported database scheme: {parsed.scheme}"

        # Check for required components
        if not parsed.path and parsed.scheme != 'sqlite':
            return False, "Database path is required"

        return True, ""

    except Exception as e:
        return False, f"Invalid database URL format: {e}"


def validate_path(path_str: str, must_exist: bool = True, must_be_dir: bool = False) -> Tuple[bool, str]:
    """
    Validate file system path.

    Args:
        path_str: Path string
        must_exist: Whether path must exist
        must_be_dir: Whether path must be a directory

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path_str:
        return False, "Path cannot be empty"

    try:
        path = Path(path_str).resolve()

        if must_exist and not path.exists():
            return False, f"Path does not exist: {path}"

        if must_be_dir and path.exists() and not path.is_dir():
            return False, f"Path is not a directory: {path}"

        # Check if path is accessible
        if path.exists():
            try:
                path.stat()
            except PermissionError:
                return False, f"Permission denied accessing path: {path}"

        return True, ""

    except Exception as e:
        return False, f"Invalid path: {e}"


def validate_cors_origins(origins_str: str) -> Tuple[bool, str]:
    """
    Validate CORS allowed origins.

    Args:
        origins_str: Comma-separated origins string

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not origins_str or origins_str.strip() == "*":
        return True, ""  # Allow all origins

    origins = [o.strip() for o in origins_str.split(",") if o.strip()]

    for origin in origins:
        if not origin.startswith(('http://', 'https://')) and origin != "*":
            return False, f"Invalid CORS origin format: {origin} (must start with http:// or https://)"

        # Basic URL validation
        if origin != "*":
            try:
                parsed = urlparse(origin)
                if not parsed.netloc:
                    return False, f"Invalid URL format: {origin}"
            except Exception:
                return False, f"Invalid URL: {origin}"

    return True, ""


def validate_rate_limit(rate_limit: int) -> Tuple[bool, str]:
    """
    Validate rate limit value.

    Args:
        rate_limit: Rate limit per minute

    Returns:
        Tuple of (is_valid, error_message)
    """
    if rate_limit < 0:
        return False, "Rate limit cannot be negative"

    if rate_limit > 10000:
        return False, "Rate limit cannot exceed 10000 requests per minute"

    return True, ""


def validate_concurrent_jobs(max_jobs: int) -> Tuple[bool, str]:
    """
    Validate maximum concurrent jobs.

    Args:
        max_jobs: Maximum number of concurrent jobs

    Returns:
        Tuple of (is_valid, error_message)
    """
    if max_jobs < 1:
        return False, "Maximum concurrent jobs must be at least 1"

    if max_jobs > 20:
        return False, "Maximum concurrent jobs cannot exceed 20"

    return True, ""


def validate_timeout_seconds(timeout: int) -> Tuple[bool, str]:
    """
    Validate timeout value in seconds.

    Args:
        timeout: Timeout in seconds

    Returns:
        Tuple of (is_valid, error_message)
    """
    if timeout < 1:
        return False, "Timeout must be at least 1 second"

    if timeout > 3600:
        return False, "Timeout cannot exceed 3600 seconds (1 hour)"

    return True, ""


def validate_pool_size(pool_size: int) -> Tuple[bool, str]:
    """
    Validate connection pool size.

    Args:
        pool_size: Pool size

    Returns:
        Tuple of (is_valid, error_message)
    """
    if pool_size < 1:
        return False, "Pool size must be at least 1"

    if pool_size > 50:
        return False, "Pool size cannot exceed 50"

    return True, ""


def validate_memory_limit(limit_mb: int) -> Tuple[bool, str]:
    """
    Validate memory limit in MB.

    Args:
        limit_mb: Memory limit in megabytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    if limit_mb < 10:
        return False, "Memory limit must be at least 10 MB"

    if limit_mb > 10000:
        return False, "Memory limit cannot exceed 10000 MB"

    return True, ""


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate complete configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Validation results dictionary
    """
    issues = []
    warnings = []

    # Validate API key
    if 'api_key' in config:
        valid, error = validate_api_key(config['api_key'])
        if not valid:
            issues.append(f"API Key: {error}")

    # Validate database URL
    if 'database_url' in config:
        valid, error = validate_database_url(config['database_url'])
        if not valid:
            issues.append(f"Database URL: {error}")

    # Validate paths
    path_configs = {
        'output_dir': ('Output directory', True, True),
        'temp_dir': ('Temp directory', True, True),
        'backend_dir': ('Backend directory', True, True),
    }

    for key, (description, must_exist, must_be_dir) in path_configs.items():
        if key in config:
            valid, error = validate_path(str(config[key]), must_exist, must_be_dir)
            if not valid:
                issues.append(f"{description}: {error}")

    # Validate CORS origins
    if 'cors_allow_origins' in config:
        origins_str = ','.join(config['cors_allow_origins']) if isinstance(config['cors_allow_origins'], list) else config['cors_allow_origins']
        valid, error = validate_cors_origins(origins_str)
        if not valid:
            issues.append(f"CORS Origins: {error}")

    # Validate numeric configurations
    numeric_configs = {
        'rate_limit_per_minute': ('Rate limit', validate_rate_limit),
        'videohelper_max_concurrent_jobs': ('Max concurrent jobs', validate_concurrent_jobs),
        'videohelper_db_pool_timeout': ('Database pool timeout', validate_timeout_seconds),
        'videohelper_db_pool_size': ('Database pool size', validate_pool_size),
    }

    for key, (description, validator) in numeric_configs.items():
        if key in config:
            valid, error = validator(config[key])
            if not valid:
                issues.append(f"{description}: {error}")

    # Check for potential issues
    if config.get('videohelper_use_streaming', False) and not config.get('debug_mode', False):
        warnings.append("Streaming mode enabled - monitor memory usage closely")

    if config.get('rate_limit_per_minute', 0) == 0 and config.get('api_key'):
        warnings.append("Rate limiting disabled but API key authentication enabled")

    if not any([config.get('google_api_key'), config.get('gemini_api_key'), config.get('openai_api_key')]):
        issues.append("No AI API key configured (required for video generation)")

    if not config.get('pexels_api_key'):
        issues.append("PEXELS_API_KEY not configured (required for stock video search)")

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'severity': 'error' if issues else ('warning' if warnings else 'ok')
    }


def get_config_defaults() -> Dict[str, Any]:
    """
    Get default configuration values with validation.

    Returns:
        Dictionary of validated default values
    """
    from config import Config
    temp_config = Config()
    return temp_config._defaults


def validate_environment() -> Dict[str, Any]:
    """
    Validate current environment configuration.

    Returns:
        Environment validation results
    """
    import os
    from config import get_config

    config = get_config()
    env_issues = []
    env_warnings = []

    # Check required environment variables
    required_env = [
        ('PEXELS_API_KEY', 'Required for stock video search'),
    ]

    ai_keys = ['GOOGLE_API_KEY', 'GEMINI_API_KEY', 'OPENAI_API_KEY']
    has_ai_key = any(os.getenv(key) for key in ai_keys)

    if not has_ai_key:
        env_issues.append(f"One of {', '.join(ai_keys)} is required for AI text generation")

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
        'config_valid': config.validate()['valid']
    }
