"""
Fallback implementations for backend modules that may not be available in containers
"""

import logging
logger = logging.getLogger(__name__)

def check_env_vars():
    """Fallback implementation for environment variable checking."""
    import os
    
    required_vars = ["PEXELS_API_KEY", "GEMINI_API_KEY"]
    missing = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info("Environment variables validation passed")

def generate_script_fallback(video_subject, paragraph_number, ai_model, voice, custom_prompt=""):
    """Fallback implementation for script generation."""
    logger.warning("Using fallback script generation - backend not available")
    
    # Simple fallback script
    fallback_script = f"""
Welcome to this video about {video_subject}.

In this video, we'll explore the fascinating topic of {video_subject}. 
This subject has captured the attention of many people around the world.

{custom_prompt if custom_prompt else 'Let me tell you more about this interesting topic.'}

There are many aspects to consider when discussing {video_subject}.
Each element brings its own unique perspective and insights.

Thank you for watching this video about {video_subject}.
Don't forget to like and subscribe for more content!
""".strip()
    
    return fallback_script

def tts_fallback(script, voice, output_file):
    """Fallback implementation for text-to-speech."""
    logger.warning("Using fallback TTS - backend not available")
    
    # Try to use system TTS or espeak as fallback
    import subprocess
    import os
    
    try:
        # Try espeak-ng first
        cmd = ["espeak-ng", "-w", output_file, "-s", "150", script]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_file):
            logger.info(f"Generated audio using espeak-ng: {output_file}")
            return
            
    except FileNotFoundError:
        pass
    
    # If espeak-ng fails, create a silent audio file as fallback
    try:
        # Create 30-second silent audio file
        duration = max(len(script) / 10, 10)  # Rough estimate: 10 chars per second
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", 
            "-i", f"anullsrc=r=22050:cl=mono", 
            "-t", str(duration), "-acodec", "pcm_s16le", 
            output_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.warning(f"Created silent audio file as fallback: {output_file}")
            return
            
    except Exception as e:
        logger.error(f"Failed to create fallback audio: {e}")
    
    raise RuntimeError("Could not generate audio - no TTS system available")

def search_for_stock_videos_fallback(query, api_key, it=5, min_dur=10):
    """Fallback implementation for stock video search."""
    logger.warning("Using fallback video search - backend not available")
    
    # Simple implementation using Pexels API directly
    import requests
    
    try:
        headers = {
            'Authorization': api_key
        }
        
        params = {
            'query': query,
            'per_page': it,
            'orientation': 'portrait'  # For vertical videos
        }
        
        response = requests.get(
            'https://api.pexels.com/videos/search',
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            videos = []
            
            for video in data.get('videos', []):
                # Get the highest quality vertical video file
                video_files = video.get('video_files', [])
                
                # Prefer vertical videos (height > width)
                vertical_files = [f for f in video_files if f.get('height', 0) > f.get('width', 0)]
                if not vertical_files:
                    vertical_files = video_files
                
                if vertical_files:
                    # Sort by quality and get the best one
                    best_file = max(vertical_files, key=lambda x: x.get('height', 0) * x.get('width', 0))
                    videos.append(best_file.get('link'))
            
            logger.info(f"Found {len(videos)} stock videos using fallback search")
            return videos
            
    except Exception as e:
        logger.error(f"Fallback video search failed: {e}")
    
    return []  # Return empty list if search fails