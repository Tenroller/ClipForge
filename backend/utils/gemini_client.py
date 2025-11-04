"""
Gemini API client utilities.
"""

import os
import logging
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger("gemini_client")


def get_available_gemini_models() -> List[str]:
    """
    Fetch available Gemini models from the API using google-genai SDK.

    Returns:
        List[str]: List of available model names (e.g., ['gemini-2.0-flash', 'gemini-1.5-pro', ...])
                   Falls back to hardcoded list if API call fails.
    """
    try:
        logger.info("Attempting to fetch models from Gemini API...")
        from google import genai
        logger.info("Successfully imported google.genai")

        # Get API key from environment
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.warning("GEMINI_API_KEY not set, returning default models")
            return _get_default_models()

        logger.info(f"GEMINI_API_KEY found (length: {len(api_key)})")

        # Create client
        client = genai.Client(api_key=api_key)
        logger.info("Created Gemini client")

        # List all models using the SDK
        logger.info("Calling client.models.list()...")
        models_pager = client.models.list()
        logger.info(f"Received models response from API")

        # Extract model names (Pager is directly iterable)
        model_names = []
        for model in models_pager:
            # Check if model supports generateContent
            if hasattr(model, 'supported_actions') and 'generateContent' in model.supported_actions:
                # Extract the model name (e.g., "models/gemini-2.0-flash" -> "gemini-2.0-flash")
                model_name = model.name
                if model_name.startswith('models/'):
                    model_name = model_name.replace('models/', '')
                model_names.append(model_name)
                logger.debug(f"Found model: {model_name}")

        if not model_names:
            logger.warning("No models found from API after filtering, returning default models")
            return _get_default_models()

        logger.info(f"Successfully fetched {len(model_names)} models with generateContent support from Gemini API")
        return sorted(model_names, reverse=True)  # Sort with newest first

    except ImportError as e:
        logger.error(f"google-genai package not installed: {e}", exc_info=True)
        return _get_default_models()
    except Exception as e:
        logger.error(f"Failed to fetch models from Gemini API: {e}", exc_info=True)
        return _get_default_models()


def _get_default_models() -> List[str]:
    """
    Return a hardcoded list of default Gemini models as fallback.

    Returns:
        List[str]: Default model names
    """
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
        from google import genai

        # Get API key from environment
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.warning("GEMINI_API_KEY not set")
            return None

        # Create client
        client = genai.Client(api_key=api_key)

        # Fetch model info
        model = client.models.get(model=f"models/{model_name}")

        return {
            "name": model.name.replace('models/', ''),
            "display_name": model.display_name if hasattr(model, 'display_name') else model_name,
            "description": model.description if hasattr(model, 'description') else "",
            "input_token_limit": model.input_token_limit if hasattr(model, 'input_token_limit') else None,
            "output_token_limit": model.output_token_limit if hasattr(model, 'output_token_limit') else None,
            "supported_actions": model.supported_actions if hasattr(model, 'supported_actions') else [],
        }

    except ImportError:
        logger.error("google-genai package not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch model info for {model_name}: {e}")
        return None