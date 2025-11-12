"""
Health check and basic system status endpoints.
"""

from pathlib import Path
from fastapi import APIRouter

try:
    from ...utils.paths import get_project_root
except ImportError:
    # Fallback for when running from backend directory
    from utils.paths import get_project_root

router = APIRouter()

ROOT = get_project_root()


@router.get("/api/health", summary="Health Check")
def health():
    """Basic health check endpoint."""
    return {
        "status": "ok",
        "cwd": str(Path.cwd()),
        "root": str(ROOT),
    }
