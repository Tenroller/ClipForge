"""
OpenRouter client wrapper for video-processor AI text generation.

Provides get_client, generate_content, generate_structured_response, and
generate_with_images using the openrouter Python SDK (v0.7+).
"""

import os
import json
import time
from typing import Any, Dict, List, Optional, Type

from loguru import logger
from openrouter import OpenRouter, components
from pydantic import BaseModel

logger = logger.bind(name="openrouter_client")

_client: Optional[OpenRouter] = None

DEFAULT_MODEL = "openrouter/free"
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds


def get_client() -> OpenRouter:
    """Get or create the singleton OpenRouter client."""
    global _client
    if _client is None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY environment variable is not set")
        _client = OpenRouter(api_key=api_key)
        logger.info("OpenRouter client initialized")
    return _client


def generate_content(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """Generate text content from a prompt.

    Args:
        prompt: The text prompt.
        model: OpenRouter model identifier (e.g. 'google/gemini-2.0-flash-001').
        temperature: Sampling temperature (0-2).
        max_tokens: Maximum tokens in the response.

    Returns:
        The generated text as a string, or empty string on failure.
    """
    client = get_client()

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = float(max_tokens)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.send(**kwargs)
            content = response.choices[0].message.content
            return content or ""
        except Exception as e:
            last_error = e
            logger.warning(f"generate_content attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)

    logger.error(f"generate_content failed after {MAX_RETRIES} attempts: {last_error}")
    return ""


def generate_structured_response(
    prompt: str,
    response_schema: Type[BaseModel],
    model: str = DEFAULT_MODEL,
    system_instruction: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a structured JSON response matching a Pydantic schema.

    Args:
        prompt: The text prompt.
        response_schema: Pydantic model class defining the expected JSON structure.
        model: OpenRouter model identifier.
        system_instruction: Optional system message to guide behavior.

    Returns:
        Validated dictionary matching the schema.

    Raises:
        RuntimeError: If all retry attempts fail.
    """
    client = get_client()

    # Build JSON schema from Pydantic model
    json_schema = response_schema.model_json_schema()

    messages: List[Dict[str, str]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "response_format": components.ResponseFormatJSONSchema(
            type="json_schema",
            json_schema=components.JSONSchemaConfig(
                name=response_schema.__name__,
                schema=json_schema,
            ),
        ),
    }

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.send(**kwargs)
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("Empty response from OpenRouter")

            parsed = json.loads(content)
            # Validate against the Pydantic schema
            validated = response_schema.model_validate(parsed)
            return validated.model_dump()
        except Exception as e:
            last_error = e
            logger.warning(
                f"generate_structured_response attempt {attempt}/{MAX_RETRIES} failed: {e}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)

    raise RuntimeError(
        f"generate_structured_response failed after {MAX_RETRIES} attempts: {last_error}"
    )


def generate_with_images(
    prompt: str,
    images: List[str],
    model: str = DEFAULT_MODEL,
    response_schema: Optional[Type[BaseModel]] = None,
) -> str:
    """Generate a response from prompt and images (vision).

    Args:
        prompt: The text prompt describing the task.
        images: List of base64-encoded image data URIs
                (e.g. 'data:image/jpeg;base64,...').
        model: Vision-capable OpenRouter model identifier.
        response_schema: Optional Pydantic model for structured JSON output.

    Returns:
        The response text (JSON string if response_schema is provided).

    Raises:
        RuntimeError: If all retry attempts fail.
    """
    client = get_client()

    # Build multimodal content parts
    content_parts: List[Dict[str, Any]] = []
    for img in images:
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": img},
        })
    content_parts.append({"type": "text", "text": prompt})

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": content_parts}],
        "stream": False,
    }

    if response_schema:
        json_schema = response_schema.model_json_schema()
        kwargs["response_format"] = components.ResponseFormatJSONSchema(
            type="json_schema",
            json_schema=components.JSONSchemaConfig(
                name=response_schema.__name__,
                schema=json_schema,
            ),
        )

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.send(**kwargs)
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("Empty response from OpenRouter Vision API")
            return content
        except Exception as e:
            last_error = e
            logger.warning(
                f"generate_with_images attempt {attempt}/{MAX_RETRIES} failed: {e}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)

    raise RuntimeError(
        f"generate_with_images failed after {MAX_RETRIES} attempts: {last_error}"
    )
