import re
import os
import json
from pathlib import Path
from typing import Tuple, List, Optional, Any, Dict

from termcolor import colored
import logging
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

logger = logging.getLogger("video_generator")

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
    try:
        logger.info("gemini.generate_response: start", extra={"ai_model": model_name, "prompt_len": len(prompt)})

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


def generate_structured_response(prompt: str, ai_model: str, response_schema: type[BaseModel]) -> Dict[str, Any]:
    """
    Generate a structured response using Gemini with JSON schema validation.

    This function uses Gemini's Structured Outputs feature to guarantee that
    the AI returns valid JSON matching the provided Pydantic schema.

    Args:
        prompt: The prompt to send to the AI
        ai_model: The AI model to use (e.g., 'gemini-2.5-flash')
        response_schema: Pydantic BaseModel class defining the expected JSON structure

    Returns:
        Dictionary containing the validated response data

    Raises:
        RuntimeError: If client initialization fails or API call fails
        ValidationError: If response doesn't match schema (unlikely with structured outputs)
    """
    model_name = ai_model or 'gemini-2.5-flash'

    try:
        logger.info("gemini.generate_structured_response: start", extra={
            "ai_model": model_name,
            "prompt_len": len(prompt),
            "schema": response_schema.__name__
        })

        # Get the client
        client = _get_client()
        if not client:
            raise RuntimeError("Gemini client not initialized. Check GEMINI_API_KEY.")

        # Generate content with structured output
        response_model = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": response_schema.model_json_schema(),
            }
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
            "schema": response_schema.__name__
        })

        # Return as dictionary
        return response_data.model_dump()

    except Exception as e:
        logger.error("gemini.generate_structured_response: error", exc_info=True, extra={
            "ai_model": model_name,
            "schema": response_schema.__name__ if response_schema else "None"
        })
        print(colored(f"[-] Gemini Structured Output Error: {e}", "red"))
        raise

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
  
    # Generate title  
    title = generate_response(title_prompt, ai_model).strip()  
    
    # Build prompt for description  
    description_prompt = f"""  
    Write a brief and engaging description for a YouTube shorts video about {video_subject}.  
    The video is based on the following script:  
    {script}  
    """  
  
    # Generate description  
    description = generate_response(description_prompt, ai_model).strip()  
  
    # Generate keywords  
    keywords = get_search_terms(video_subject, 6, script, ai_model)  

    return title, description, keywords
