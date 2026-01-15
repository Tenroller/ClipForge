import re
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Optional, Any, Dict

from termcolor import colored
from loguru import logger
from dotenv import load_dotenv
from google import genai  # type: ignore
from pydantic import BaseModel, Field

# Load environment variables
# Try loading local .env if present (vendored path)
try:
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    load_dotenv("../.env")

# Configure Gemini - get API key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Debug configuration
DEBUG_PROMPTS = os.getenv('DEBUG_PROMPTS', 'false').lower() == 'true'
DEBUG_DIR = Path(__file__).resolve().parent / "debug_prompts"

# Bind logger with context for this module
logger = logger.bind(name="AIvideos.gpt")

# Initialize client lazily
_client = None

def _get_client():
    """Get or create the Gemini client."""
    global _client
    if _client is None and GEMINI_API_KEY:
        try:
            _client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            logger.error(f"Failed to create Gemini client: {e}")
    return _client


def _save_debug_prompt(prompt: str, function_name: str, extra_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Save prompt to debug file if DEBUG_PROMPTS is enabled.
    
    Args:
        prompt: The prompt text to save
        function_name: Name of the function making the request
        extra_data: Additional context data to save
        
    Returns:
        Path to saved file if saved, None if debug disabled
    """
    if not DEBUG_PROMPTS:
        return None
        
    try:
        # Create debug directory if it doesn't exist
        DEBUG_DIR.mkdir(exist_ok=True)
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # milliseconds
        filename = f"{function_name}_{timestamp}.json"
        filepath = DEBUG_DIR / filename
        
        # Prepare debug data
        debug_data = {
            "timestamp": datetime.now().isoformat(),
            "function": function_name,
            "prompt": prompt,
            "prompt_length": len(prompt),
            "extra_data": extra_data or {}
        }
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(debug_data, f, indent=2, ensure_ascii=False)
            
        logger.debug(f"Debug prompt saved: {filepath}")
        return str(filepath)
        
    except Exception as e:
        logger.warning(f"Failed to save debug prompt: {e}")
        return None


# Pydantic models for structured output (Viral Moments Detection)
class ViralMomentSchema(BaseModel):
    """Schema for a single viral moment detected by AI."""
    start_time: float = Field(description="Start time in seconds (>=0), 2 decimal precision")
    end_time: float = Field(description="End time in seconds (> start_time), 2 decimal precision")
    duration: float = Field(description="Duration in seconds (end_time - start_time)")
    title: str = Field(description="Catchy title for the clip, max 60 chars")
    reason: str = Field(description="1-2 sentences explaining why this will go viral")
    hook: str = Field(description="Attention-grabbing first sentence (max 120 chars)")
    viral_score: int = Field(description="Viral potential score from 0-100 (higher is better)")
    hook_strength: int = Field(description="Hook strength score 0-100 for first 3-5 seconds only (minimum 70 required)")
    confidence: float = Field(description="Model confidence in selection (0.0-1.0)")
    caption: str = Field(description="Share caption/subtitle for social media (<= 150 chars)")
    tags: List[str] = Field(description="Up to 6 tags/hashtags (without # symbol)")
    thumbnail_text: str = Field(description="Short text for thumbnail (<=25 chars)")
    recommended_crop: str = Field(description="Crop recommendation: close-up, mid, wide, or focus-on-person-X")
    cut_padding_before: float = Field(description="Suggested extra seconds before start (0.0-2.0)")
    cut_padding_after: float = Field(description="Suggested extra seconds after end (0.0-2.0)")
    subtitles: str = Field(description="Exact transcript excerpt for this clip (max 300 chars)")
    notes: str = Field(description="Optional notes: speaker changes, warnings, or fallback suggestions")


class ViralMomentsResponse(BaseModel):
    """Schema for the complete viral moments response."""
    moments: List[ViralMomentSchema] = Field(description="List of detected viral moments, ordered by viral potential (best first)")


def generate_response(prompt: str, ai_model: str) -> str:
    """
    Generate a script for a video, depending on the subject of the video.

    Args:
        video_subject (str): The subject of the video.
        ai_model (str): The AI model to use for generation.


    Returns:

        str: The response from the AI model.

    """

    # Force Gemini-only; allow ai_model to be a concrete Gemini model name
    model_name = ai_model or 'gemini-2.0-flash'
    
    # Save debug prompt if enabled
    debug_file = _save_debug_prompt(prompt, "generate_response", {
        "ai_model": model_name
    })
    
    try:
        logger.info("gemini.generate_response: start", extra={
            "ai_model": model_name, 
            "prompt_len": len(prompt),
            "debug_file": debug_file
        })

        # Get the client
        client = _get_client()
        if not client:
            raise RuntimeError("Gemini client not initialized. Check GEMINI_API_KEY.")

        # Use new API: client.models.generate_content
        response_model = client.models.generate_content(
            model=model_name,
            contents=prompt
        )

        # Extract text from response
        response = getattr(response_model, 'text', None)
        if not response:
            # Try alternative attribute paths
            try:
                response = response_model.candidates[0].content.parts[0].text  # type: ignore[attr-defined]
            except Exception:
                response = ""
    except Exception as e:
        try:
            logger.error("gemini.generate_response: error", exc_info=True, extra={"ai_model": model_name})
        except Exception:
            pass
        print(colored(f"[-] Gemini Error: {e}", "red"))
        return ""

    try:
        logger.info("gemini.generate_response: success", extra={"ai_model": model_name, "got_text": bool(response)})
    except Exception:
        pass
    return response or ""


def generate_structured_response(
    prompt: str,
    ai_model: str,
    response_schema: type[BaseModel],
    system_instruction: str = None # type: ignore
) -> Dict[str, Any]:
    """
    Generate a structured response using Gemini with JSON schema validation.

    This function uses Gemini's Structured Outputs feature to guarantee that
    the AI returns valid JSON matching the provided Pydantic schema.

    Includes automatic retry with exponential backoff and model fallback for
    rate limiting (429) errors.

    Args:
        prompt: The prompt to send to the AI
        ai_model: The AI model to use (e.g., 'gemini-2.5-pro')
        response_schema: Pydantic BaseModel class defining the expected JSON structure
        system_instruction: Optional system instruction to guide the AI's behavior

    Returns:
        Dictionary containing the validated response data

    Raises:
        RuntimeError: If client initialization fails or API call fails after all retries
        ValidationError: If response doesn't match schema (unlikely with structured outputs)
    """
    import time
    
    # Model fallback order for rate limiting
    FALLBACK_MODELS = [
        ai_model or 'gemini-2.5-flash',
        'gemini-2.0-pro',
        'gemini-2.0-flash',
        'gemini-2.0-flash-exp',
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
                logger.info("gemini.generate_structured_response: start", extra={
                    "ai_model": model_name,
                    "prompt_len": len(prompt),
                    "schema": response_schema.__name__,
                    "attempt": attempt + 1
                })

                # Get the client
                client = _get_client()
                if not client:
                    raise RuntimeError("Gemini client not initialized. Check GEMINI_API_KEY.")

                # Build config dictionary
                config = {
                    "response_mime_type": "application/json",
                    "response_json_schema": response_schema.model_json_schema(),
                }

                # Add system instruction if provided
                if system_instruction:
                    config["system_instruction"] = system_instruction

                # Generate content with structured output
                response_model = client.models.generate_content(
                    model='gemini-3-flash-preview',
                    contents=prompt,
                    config=config
                )

                # Extract text from response
                response_text = getattr(response_model, 'text', None)
                if not response_text:
                    # Try alternative attribute paths
                    try:
                        response_text = response_model.candidates[0].content.parts[0].text
                    except Exception:
                        response_text = ""

                if not response_text:
                    raise RuntimeError("Empty response from Gemini API")

                # Parse and validate JSON against schema
                response_data = response_schema.model_validate_json(response_text)

                logger.info("gemini.generate_structured_response: success", extra={
                    "ai_model": model_name,
                    "schema": response_schema.__name__,
                    "attempt": attempt + 1
                })

                # Return as dictionary
                return response_data.model_dump()

            except Exception as e:
                last_error = e
                error_str = str(e)
                
                # Check if this is a rate limit error (429)
                is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower()
                
                if is_rate_limit:
                    # Extract retry delay from error if available
                    retry_delay = BASE_DELAY * (2 ** attempt)  # Exponential backoff
                    
                    # Try to parse retry delay from error message
                    import re
                    retry_match = re.search(r'retry in (\d+(?:\.\d+)?)', error_str.lower())
                    if retry_match:
                        suggested_delay = float(retry_match.group(1))
                        retry_delay = max(retry_delay, suggested_delay + 1)
                    
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"Rate limit hit for {model_name}, attempt {attempt + 1}/{MAX_RETRIES}. "
                                     f"Retrying in {retry_delay:.1f}s...", extra={
                            "ai_model": model_name,
                            "attempt": attempt + 1,
                            "retry_delay": retry_delay
                        })
                        print(colored(f"[!] Rate limit hit. Retrying in {retry_delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})...", "yellow"))
                        time.sleep(retry_delay)
                        continue
                    else:
                        # Max retries exceeded for this model, try next model
                        logger.warning(f"Max retries exceeded for {model_name}, trying fallback model...", extra={
                            "ai_model": model_name
                        })
                        print(colored(f"[!] Max retries exceeded for {model_name}. Trying next model...", "yellow"))
                        break  # Break inner loop to try next model
                else:
                    # Non-rate-limit error, log and re-raise
                    logger.error("gemini.generate_structured_response: error", exc_info=True, extra={
                        "ai_model": model_name,
                        "schema": response_schema.__name__ if response_schema else "None",
                        "attempt": attempt + 1
                    })
                    print(colored(f"[-] Gemini Structured Output Error: {e}", "red"))
                    raise
    
    # All models and retries exhausted
    logger.error("All Gemini models exhausted due to rate limiting", extra={
        "models_tried": fallback_models
    })
    print(colored(f"[-] All Gemini models rate limited. Please wait and try again.", "red"))
    raise last_error or RuntimeError("All Gemini models exhausted due to rate limiting")

def generate_script(video_subject: str, paragraph_number: int, ai_model: str, voice: str, customPrompt: str) -> Optional[str]:

    """
    Generate a script for a video, depending on the subject of the video, the number of paragraphs, and the AI model.



    Args:

        video_subject (str): The subject of the video.

        paragraph_number (int): The number of paragraphs to generate.

        ai_model (str): The AI model to use for generation.



    Returns:

        str: The script for the video.

    """

    # Build prompt
    
    if customPrompt:
        # Ensure English output even with custom prompts
        prompt = f"""
        {customPrompt}
        
        IMPORTANT: You must write the script in English only, regardless of any language mentioned in the above prompt or subject.
        Generate exactly {paragraph_number} paragraphs for the subject: {video_subject}
        """
    else:
        prompt = """
            Generate a script for a video, depending on the subject of the video.

            The script is to be returned as a string with the specified number of paragraphs.

            Here is an example of a string:
            "This is an example string."

            Do not under any circumstance reference this prompt in your response.

            Get straight to the point, don't start with unnecessary things like, "welcome to this video".

            Obviously, the script should be related to the subject of the video.

            YOU MUST NOT INCLUDE ANY TYPE OF MARKDOWN OR FORMATTING IN THE SCRIPT, NEVER USE A TITLE.
            YOU MUST ALWAYS WRITE THE SCRIPT IN ENGLISH, NO EXCEPTIONS.
            ONLY RETURN THE RAW CONTENT OF THE SCRIPT. DO NOT INCLUDE "VOICEOVER", "NARRATOR" OR SIMILAR INDICATORS OF WHAT SHOULD BE SPOKEN AT THE BEGINNING OF EACH PARAGRAPH OR LINE. YOU MUST NOT MENTION THE PROMPT, OR ANYTHING ABOUT THE SCRIPT ITSELF. ALSO, NEVER TALK ABOUT THE AMOUNT OF PARAGRAPHS OR LINES. JUST WRITE THE SCRIPT.

        """

    prompt += f"""
    
    Subject: {video_subject}
    Number of paragraphs: {paragraph_number}
    Language: English

    """

    # Save debug prompt if enabled
    _save_debug_prompt(prompt, "generate_script", {
        "video_subject": video_subject,
        "paragraph_number": paragraph_number,
        "ai_model": ai_model,
        "voice": voice,
        "has_custom_prompt": bool(customPrompt)
    })

    # Generate script
    response = generate_response(prompt, ai_model)

    print(colored(response, "cyan"))

    # Return the generated script
    if response:
        # Clean the script
        # Remove asterisks, hashes
        response = response.replace("*", "")
        response = response.replace("#", "")

        # Remove markdown syntax
        response = re.sub(r"\[.*\]", "", response)
        response = re.sub(r"\(.*\)", "", response)

        # Split the script into paragraphs
        paragraphs = response.split("\n\n")

        # Select the specified number of paragraphs
        selected_paragraphs = paragraphs[:paragraph_number]

        # Join the selected paragraphs into a single string
        final_script = "\n\n".join(selected_paragraphs)

        # Print to console the number of paragraphs used
        print(colored(f"Number of paragraphs used: {len(selected_paragraphs)}", "green"))

        return final_script
    else:
        print(colored("[-] GPT returned an empty response.", "red"))
        return None


def get_search_terms(video_subject: str, amount: int, script: str, ai_model: str) -> List[str]:
    """
    Generate a JSON-Array of search terms for stock videos,
    depending on the subject of a video.

    Args:
        video_subject (str): The subject of the video.
        amount (int): The amount of search terms to generate.
        script (str): The script of the video.
        ai_model (str): The AI model to use for generation.

    Returns:
        List[str]: The search terms for the video subject.
    """

    # Build prompt
    prompt = f"""
    Generate {amount} search terms for stock videos,
    depending on the subject of a video.
    Subject: {video_subject}

    The search terms are to be returned as
    a JSON-Array of strings.

    Each search term should consist of 1-3 words,
    always add the main subject of the video.
    
    YOU MUST ONLY RETURN THE JSON-ARRAY OF STRINGS.
    YOU MUST NOT RETURN ANYTHING ELSE. 
    YOU MUST NOT RETURN THE SCRIPT.
    
    The search terms must be related to the subject of the video.
    Here is an example of a JSON-Array of strings:
    ["search term 1", "search term 2", "search term 3"]

    For context, here is the full text:
    {script}
    """

    # Save debug prompt if enabled
    _save_debug_prompt(prompt, "get_search_terms", {
        "video_subject": video_subject,
        "amount": amount,
        "ai_model": ai_model,
        "script_length": len(script)
    })

    # Generate search terms
    response = generate_response(prompt, ai_model)
    print(response)

    # Parse response into a list of search terms
    search_terms = []
    
    try:
        # First try to parse the response directly as JSON
        search_terms = json.loads(response)
        if not isinstance(search_terms, list) or not all(isinstance(term, str) for term in search_terms):
            raise ValueError("Response is not a list of strings.")

    except (json.JSONDecodeError, ValueError):
        print(colored("[*] GPT returned an unformatted response. Attempting to clean...", "yellow"))

        # Try to find JSON array in the response
        # Look for content between square brackets
        start_bracket = response.find("[")
        end_bracket = response.rfind("]")
        
        if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
            json_str = response[start_bracket:end_bracket + 1]
            
            try:
                search_terms = json.loads(json_str)
                if not isinstance(search_terms, list) or not all(isinstance(term, str) for term in search_terms):
                    raise ValueError("Extracted content is not a list of strings.")
            except (json.JSONDecodeError, ValueError):
                # If that fails, try regex approach
                match = re.search(r'\[[\s\S]*?\]', response)
                if match:
                    try:
                        search_terms = json.loads(match.group())
                        if not isinstance(search_terms, list) or not all(isinstance(term, str) for term in search_terms):
                            raise ValueError("Regex extracted content is not a list of strings.")
                    except (json.JSONDecodeError, ValueError):
                        print(colored("[-] Could not parse response as JSON.", "red"))
                        # Fallback: try to extract quoted strings
                        quoted_strings = re.findall(r'"([^"]*)"', response)
                        if quoted_strings:
                            search_terms = quoted_strings[:amount]
                            print(colored(f"[*] Extracted {len(search_terms)} terms using fallback method.", "yellow"))
                        else:
                            print(colored("[-] Could not extract any search terms.", "red"))
                            return []
                else:
                    print(colored("[-] No JSON array found in response.", "red"))
                    return []
        else:
            print(colored("[-] No square brackets found in response.", "red"))
            return []

    # Let user know
    print(colored(f"\nGenerated {len(search_terms)} search terms: {', '.join(search_terms)}", "cyan"))

    # Return search terms
    return search_terms


def generate_metadata(video_subject: str, script: str, ai_model: str) -> Tuple[str, str, List[str]]:
    """
    Generate metadata for a YouTube video, including the title, description, and keywords.

    Args:
        video_subject (str): The subject of the video.
        script (str): The script of the video.
        ai_model (str): The AI model to use for generation.

    Returns:
        Tuple[str, str, List[str]]: The title, description, and keywords for the video.
    """

    # Build prompt for title
    title_prompt = f"""
    Generate a catchy and SEO-friendly title for a YouTube shorts video about {video_subject}.
    """

    # Save debug prompts if enabled
    _save_debug_prompt(title_prompt, "generate_metadata_title", {
        "video_subject": video_subject,
        "ai_model": ai_model
    })

    # Generate title
    title = generate_response(title_prompt, ai_model).strip()

    # Build prompt for description
    description_prompt = f"""
    Write a brief and engaging description for a YouTube shorts video about {video_subject}.
    The video is based on the following script:
    {script}
    """

    # Save debug prompt for description
    _save_debug_prompt(description_prompt, "generate_metadata_description", {
        "video_subject": video_subject,
        "ai_model": ai_model,
        "script_length": len(script)
    })

    # Generate description
    description = generate_response(description_prompt, ai_model).strip()

    # Generate keywords
    keywords = get_search_terms(video_subject, 6, script, ai_model)

    return title, description, keywords


# Pydantic model for frame selection response
class ThumbnailFrameSelection(BaseModel):
    """Schema for AI-selected best thumbnail frame."""
    selected_frame_index: int = Field(description="Index of the best frame for thumbnail (0-based)")
    reasoning: str = Field(description="Brief explanation of why this frame was selected")
    engagement_score: int = Field(description="Estimated engagement potential (0-100)")


def select_best_thumbnail_frame(
    frame_images: List[str],
    viral_context: Dict[str, Any],
    ai_model: str = "gemini-2.0-flash-exp"
) -> Dict[str, Any]:
    """
    Use Gemini Vision API to select the best frame for a viral thumbnail.

    Analyzes multiple candidate frames and selects the one with highest viral potential.
    Considers facial expressions, composition, clarity, and engagement factors.

    Args:
        frame_images: List of base64-encoded image data URIs (e.g., "data:image/jpeg;base64,...")
        viral_context: Context about the clip (title, hook, tags, etc.)
        ai_model: Gemini model to use (must support vision)

    Returns:
        Dictionary with selected_frame_index, reasoning, and engagement_score

    Raises:
        RuntimeError: If API call fails
    """
    try:
        logger.info("gemini.select_best_thumbnail_frame: start", extra={
            "ai_model": ai_model,
            "frame_count": len(frame_images)
        })

        # Get the client
        client = _get_client()
        if not client:
            raise RuntimeError("Gemini client not initialized. Check GEMINI_API_KEY.")

        # Build prompt with viral context
        title = viral_context.get('title', 'Viral Moment')
        hook = viral_context.get('hook', '')
        thumbnail_text = viral_context.get('thumbnail_text', '')

        prompt = f"""You are an expert at viral social media content optimization.

Analyze these {len(frame_images)} thumbnail candidate frames and select the ONE with the highest viral potential for a short-form video clip.

**Clip Context:**
- Title: {title}
- Hook: {hook}
- Thumbnail Text: {thumbnail_text}

**Selection Criteria (in priority order):**
1. **Facial Expression** - Look for expressive faces showing emotion (surprise, excitement, focus, intensity)
2. **Visual Clarity** - Sharp, well-lit, high-contrast frames
3. **Composition** - Centered subject, clear focal point, engaging framing
4. **Authenticity** - Natural moment that looks genuine (not mid-blink or awkward)
5. **Stop-Scroll Factor** - Would this make someone stop scrolling?

**Instructions:**
- Analyze all {len(frame_images)} frames carefully
- Consider which frame pairs best with the thumbnail text overlay
- Prefer frames with dynamic facial expressions or gestures
- Avoid frames where the person is mid-word (open mouth, weird expression)
- Select the frame with maximum viral/engagement potential

Return your selection as JSON."""

        # Save debug prompt if enabled (without base64 image data for readability)
        _save_debug_prompt(prompt, "select_best_thumbnail_frame", {
            "ai_model": ai_model,
            "frame_count": len(frame_images),
            "viral_context": viral_context,
            "note": "Image data excluded from debug save for readability"
        })

        # Create content with images
        # Gemini expects a single content object with parts array
        from typing import Any, Dict, List, Union
        content_parts: List[Dict[str, Any]] = [{"text": prompt}]

        for i, frame_data in enumerate(frame_images):
            # Extract base64 data from data URI
            if frame_data.startswith("data:"):
                # Format: "data:image/jpeg;base64,<base64_data>"
                mime_type, base64_data = frame_data.split(";base64,")
                mime_type = mime_type.replace("data:", "")

                # Create inline data part
                inline_data_part: Dict[str, Any] = {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64_data
                    }
                }
                content_parts.append(inline_data_part)
                content_parts.append({"text": f"Frame {i}"})

        # Generate structured response with proper content structure
        response_model = client.models.generate_content(
            model=ai_model,
            contents=[{"parts": content_parts}],
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ThumbnailFrameSelection.model_json_schema(),
            }
        )

        # Extract text from response
        response_text = getattr(response_model, 'text', None)
        if not response_text:
            try:
                response_text = response_model.candidates[0].content.parts[0].text
            except Exception:
                response_text = ""

        if not response_text:
            raise RuntimeError("Empty response from Gemini Vision API")

        # Parse and validate
        selection_data = ThumbnailFrameSelection.model_validate_json(response_text)

        logger.info("gemini.select_best_thumbnail_frame: success", extra={
            "ai_model": ai_model,
            "selected_index": selection_data.selected_frame_index,
            "engagement_score": selection_data.engagement_score
        })

        return selection_data.model_dump()

    except Exception as e:
        logger.error("gemini.select_best_thumbnail_frame: error", exc_info=True, extra={
            "ai_model": ai_model
        })
        print(colored(f"[-] Gemini Vision Error: {e}", "red"))
        # Fallback: return first frame
        return {
            "selected_frame_index": 0,
            "reasoning": "Fallback to first frame due to API error",
            "engagement_score": 50
        }
