"""
OpenRouter API client utilities.
Replaces the Gemini client with OpenRouter SDK for unified AI model access.
"""

import os
import time
import re
from typing import List, Optional, Dict, Any
from pathlib import Path

try:
    from ..logging_config import get_logger
except ImportError:
    from logging_config import get_logger

logger = get_logger("openrouter_client")

# Client singleton
_client = None


def get_client():
    """Get or create the OpenRouter client."""
    global _client
    if _client is None:
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set. Get your key at https://openrouter.ai/settings/keys")
        
        try:
            from openrouter import OpenRouter
            _client = OpenRouter(api_key=api_key)
            logger.info("OpenRouter client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to create OpenRouter client: {e}")
            raise
    return _client


def generate_content(
    prompt: str,
    model: str = "openrouter/auto",
    system_instruction: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Generate text content using OpenRouter.

    Args:
        prompt: The prompt to send to the AI
        model: The model to use (OpenRouter format, e.g., 'google/gemini-2.5-flash')
        system_instruction: Optional system instruction to guide behavior
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum output tokens

    Returns:
        str: The generated text response
    """
    try:
        logger.info("openrouter.generate_content: start", extra={
            "model": model,
            "prompt_len": len(prompt),
        })

        client = get_client()
        messages = []

        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = client.chat.send(**kwargs)
        
        result = response.choices[0].message.content if response.choices else ""
        
        logger.info("openrouter.generate_content: success", extra={
            "model": model,
            "got_text": bool(result)
        })
        
        return result or ""

    except Exception as e:
        logger.error(f"openrouter.generate_content: error - {e}", exc_info=True)
        return ""


def generate_structured_response(
    prompt: str,
    response_schema,  # Pydantic BaseModel class
    model: str = "openrouter/auto",
    system_instruction: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate structured JSON response using OpenRouter.

    Uses OpenRouter's structured outputs feature to guarantee valid JSON
    matching the provided Pydantic schema.

    Includes automatic retry with exponential backoff and model fallback
    for rate limiting (429) errors.

    Args:
        prompt: The prompt to send to the AI
        response_schema: Pydantic BaseModel class defining expected JSON structure
        model: The model to use (must support structured outputs)
        system_instruction: Optional system instruction

    Returns:
        Dict containing the validated response data

    Raises:
        RuntimeError: If API call fails after all retries
    """
    # Model fallback order for rate limiting
    FALLBACK_MODELS = [
        model,
        "google/gemini-2.5-flash",
        "google/gemini-2.0-flash",
        "anthropic/claude-sonnet-4",
    ]
    seen = set()
    fallback_models = []
    for m in FALLBACK_MODELS:
        if m not in seen:
            fallback_models.append(m)
            seen.add(m)

    # Retry configuration
    MAX_RETRIES = 3
    BASE_DELAY = 5  # seconds

    last_error = None

    for model_name in fallback_models:
        for attempt in range(MAX_RETRIES):
            try:
                logger.info("openrouter.generate_structured_response: start", extra={
                    "model": model_name,
                    "prompt_len": len(prompt),
                    "schema": response_schema.__name__,
                    "attempt": attempt + 1
                })

                client = get_client()
                messages = []

                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})

                response = client.chat.send(
                    model=model_name,
                    messages=messages,
                    stream=False,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": response_schema.__name__,
                            "schema": response_schema.model_json_schema(),
                            "strict": True,
                        }
                    },
                )

                response_text = response.choices[0].message.content if response.choices else ""

                if not response_text:
                    raise RuntimeError("Empty response from OpenRouter API")

                # Parse and validate JSON against schema
                response_data = response_schema.model_validate_json(response_text)

                logger.info("openrouter.generate_structured_response: success", extra={
                    "model": model_name,
                    "schema": response_schema.__name__,
                    "attempt": attempt + 1
                })

                return response_data.model_dump()

            except Exception as e:
                last_error = e
                error_str = str(e)

                # Check if this is a rate limit error (429)
                is_rate_limit = "429" in error_str or "rate" in error_str.lower() or "quota" in error_str.lower()

                if is_rate_limit:
                    retry_delay = BASE_DELAY * (2 ** attempt)  # Exponential backoff

                    # Try to parse retry delay from error message
                    retry_match = re.search(r'retry in (\d+(?:\.\d+)?)', error_str.lower())
                    if retry_match:
                        suggested_delay = float(retry_match.group(1))
                        retry_delay = max(retry_delay, suggested_delay + 1)

                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"Rate limit hit for {model_name}, attempt {attempt + 1}/{MAX_RETRIES}. "
                                     f"Retrying in {retry_delay:.1f}s...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        logger.warning(f"Max retries exceeded for {model_name}, trying fallback model...")
                        break
                else:
                    logger.error(f"openrouter.generate_structured_response: error - {e}", exc_info=True)
                    raise

    # All models and retries exhausted
    logger.error("All OpenRouter models exhausted due to rate limiting", extra={
        "models_tried": fallback_models
    })
    raise last_error or RuntimeError("All OpenRouter models exhausted due to rate limiting")


def generate_with_images(
    prompt: str,
    images: List[str],  # base64 data URIs or URLs
    model: str = "openrouter/auto",
    response_schema=None,  # Optional Pydantic BaseModel for structured output
) -> str:
    """
    Generate response with image inputs (vision).

    Args:
        prompt: Text prompt
        images: List of base64 data URIs (e.g., "data:image/jpeg;base64,...")
        model: Vision-capable model to use
        response_schema: Optional Pydantic model for structured JSON output

    Returns:
        str: Generated response (or JSON string if response_schema provided)
    """
    try:
        logger.info("openrouter.generate_with_images: start", extra={
            "model": model,
            "image_count": len(images),
        })

        client = get_client()

        # Build content with images in OpenAI-compatible format
        content = []
        for i, image_data in enumerate(images):
            if image_data.startswith("data:"):
                # Data URI format - OpenRouter accepts this directly
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image_data}
                })
            elif image_data.startswith("http"):
                # URL format
                content.append({
                    "type": "image_url",
                    "image_url": {"url": image_data}
                })
            content.append({"type": "text", "text": f"Frame {i}"})
        
        # Add the main prompt at the end
        content.append({"type": "text", "text": prompt})

        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        }

        # Add structured output if schema provided
        if response_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "schema": response_schema.model_json_schema(),
                    "strict": True,
                }
            }

        response = client.chat.send(**kwargs)
        result = response.choices[0].message.content if response.choices else ""

        logger.info("openrouter.generate_with_images: success", extra={
            "model": model,
            "got_text": bool(result)
        })

        return result or ""

    except Exception as e:
        logger.error(f"openrouter.generate_with_images: error - {e}", exc_info=True)
        return ""


def get_available_models() -> List[str]:
    """
    Get list of available OpenRouter models.

    Returns curated list of popular models suitable for video generation tasks.
    
    Returns:
        List[str]: Model identifiers in OpenRouter format
    """
    return [
        "google/gemini-2.5-flash",
        "google/gemini-2.5-pro", 
        "google/gemini-2.0-flash",
        "google/gemini-2.0-pro",
        "anthropic/claude-sonnet-4",
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "meta-llama/llama-3.3-70b-instruct",
    ]


def get_model_info(model_name: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a specific model.

    Note: OpenRouter doesn't expose detailed model info via SDK,
    so this returns basic info from our known model list.

    Args:
        model_name: Model identifier (e.g., 'google/gemini-2.5-flash')

    Returns:
        Dict with model info or None if unknown
    """
    known_models = {
        "google/gemini-2.5-flash": {
            "name": "google/gemini-2.5-flash",
            "display_name": "Gemini 2.5 Flash",
            "description": "Fast and efficient Gemini model",
            "supports_vision": True,
            "supports_structured_output": True,
        },
        "google/gemini-2.5-pro": {
            "name": "google/gemini-2.5-pro",
            "display_name": "Gemini 2.5 Pro",
            "description": "Advanced Gemini model with strong reasoning",
            "supports_vision": True,
            "supports_structured_output": True,
        },
        "anthropic/claude-sonnet-4": {
            "name": "anthropic/claude-sonnet-4",
            "display_name": "Claude Sonnet 4",
            "description": "Balanced Claude model for most tasks",
            "supports_vision": True,
            "supports_structured_output": True,
        },
        "openai/gpt-4o": {
            "name": "openai/gpt-4o",
            "display_name": "GPT-4o",
            "description": "OpenAI's multimodal flagship",
            "supports_vision": True,
            "supports_structured_output": True,
        },
    }
    
    return known_models.get(model_name)


# Backward compatibility aliases
get_available_gemini_models = get_available_models
