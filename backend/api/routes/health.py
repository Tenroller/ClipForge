"""
Health check and basic system status endpoints.
"""

from pathlib import Path
from fastapi import APIRouter

from ...utils.paths import get_project_root, get_backend_path

router = APIRouter()

ROOT = get_project_root()
VENDOR_ROOT = get_backend_path("vendors")
MONEYPRINTER_BACKEND = VENDOR_ROOT / "moneyprinter"
BRAINROT_ROOT = VENDOR_ROOT / "brainrot"


@router.get("/api/health", summary="Health Check")
def health():
    """Basic health check endpoint."""
    return {
        "status": "ok",
        "cwd": str(Path.cwd()),
        "root": str(ROOT),
        "moneyprinter_present": MONEYPRINTER_BACKEND.exists(),
        "brainrot_present": BRAINROT_ROOT.exists(),
    }
