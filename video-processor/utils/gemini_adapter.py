"""
Adapter to access backend Gemini utilities from video-processor.

This module handles the import path resolution to access backend Gemini client
from the video-processor context.
"""

import sys
from pathlib import Path
from typing import List, Optional

# Add project root to Python path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def get_available_gemini_models() -> List[str]:
    """
    Fetch available Gemini models from the API using google-genai SDK.
    
    Returns:
        List[str]: List of available model names (e.g., ['gemini-2.0-flash', 'gemini-1.5-pro', ...])
                   Falls back to hardcoded list if API call fails.
    """
    try:
        from backend.utils.gemini_client import get_available_gemini_models
        return get_available_gemini_models()
    except Exception:
        # Fallback to default models if import fails
        return [
            "gemini-2.0-flash",
            "gemini-2.0-pro", 
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]


def get_model_info(model_name: str) -> Optional[dict]:
    """
    Get detailed information about a specific Gemini model.
    
    Args:
        model_name: Name of the model (e.g., 'gemini-2.0-flash')
    
    Returns:
        Optional[dict]: Model information including input/output token limits, etc.
                       None if model not found or API call fails.
    """
    try:
        from backend.utils.gemini_client import get_model_info
        return get_model_info(model_name)
    except Exception:
        return None