"""
Core application configuration and setup.
"""

from .app_factory import create_app
from .config import AppConfig
from .lifespan import lifespan

__all__ = [
    "create_app",
    "AppConfig", 
    "lifespan",
]
