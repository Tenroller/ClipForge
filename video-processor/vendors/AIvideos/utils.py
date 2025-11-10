import os
import sys
import json
import random
import zipfile
import requests
from typing import Tuple, Dict, Any, Optional

from termcolor import colored
from loguru import logger

# Bind logger with context for this module
logger = logger.bind(name="AIvideos.utils")


def clean_dir(path: str) -> None:
    """
    Removes every file in a directory.

    Args:
        path (str): Path to directory.

    Returns:
        None
    """
    try:
        if not os.path.exists(path):
            os.mkdir(path)
            logger.info(f"Created directory: {path}")

        for file in os.listdir(path):
            file_path = os.path.join(path, file)
            os.remove(file_path)
            logger.info(f"Removed file: {file_path}")

        logger.info(colored(f"Cleaned {path} directory", "green"))
    except Exception as e:
        logger.error(f"Error occurred while cleaning directory {path}: {str(e)}")

def fetch_songs(zip_url: str) -> None:
    """
    Downloads songs into songs/ directory to use with geneated videos.

    Args:
        zip_url (str): The URL to the zip file containing the songs.

    Returns:
        None
    """
    try:
        logger.info(colored(f" => Fetching songs...", "magenta"))

        files_dir = "../../../Songs"
        if not os.path.exists(files_dir):
            os.mkdir(files_dir)
            logger.info(colored(f"Created directory: {files_dir}", "green"))
        else:
            # Skip if songs are already downloaded
            return

        # Download songs
        response = requests.get(zip_url)

        # Save the zip file
        with open("../../../Songs/songs.zip", "wb") as file:
            file.write(response.content)

        # Unzip the file
        with zipfile.ZipFile("../../../Songs/songs.zip", "r") as file:
            file.extractall("../../../Songs")

        # Remove the zip file
        os.remove("../../../Songs/songs.zip")

        logger.info(colored(" => Downloaded Songs to ../../../Songs.", "green"))

    except Exception as e:
        logger.error(colored(f"Error occurred while fetching songs: {str(e)}", "red"))

def choose_random_song() -> str:
    """
    Chooses a random song from the songs/ directory.

    Returns:
        str: The path to the chosen song.
    """
    try:
        songs = os.listdir("../../../Songs")
        songs = [s for s in songs if s.lower().endswith((".mp3", ".wav", ".m4a"))]
        if not songs:
            raise RuntimeError("No songs available in ../../../Songs")
        song = random.choice(songs)
        logger.info(colored(f"Chose song: {song}", "green"))
        return f"../../../Songs/{song}"
    except Exception as e:
        logger.error(colored(f"Error occurred while choosing random song: {str(e)}", "red"))
        raise

def check_env_vars() -> None:
    """
    Checks if the necessary environment variables are set.

    Returns:
        None

    Raises:
        SystemExit: If any required environment variables are missing.
    """
    try:
        # Required for stock video search
        required_always = ["PEXELS_API_KEY"]
        # At least one of these must be present for script generation
        one_of = ["GEMINI_API_KEY"]

        missing: list[str] = []
        for var in required_always:
            val = os.getenv(var)
            if not val:
                missing.append(var)

        # Validate the one-of group
        if not any(os.getenv(v) for v in one_of):
            missing.extend([f"one of: {', '.join(one_of)}"])

        if missing:
            missing_vars_str = ", ".join(missing)
            logger.error(colored(f"Missing required environment variables: {missing_vars_str}", "red"))
            logger.error(colored("Please consult 'EnvironmentVariables.md' for instructions on how to set them.", "yellow"))
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error occurred while checking environment variables: {str(e)}")
        sys.exit(1)


def get_video_info(video_path: str) -> Optional[Dict[str, Any]]:
    """
    Get video information using ffprobe.
    
    Args:
        video_path (str): Path to the video file
        
    Returns:
        Dict with video info or None if failed
    """
    try:
        import subprocess
        
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', 
            '-show_format', video_path
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            info = json.loads(result.stdout)
            
            # Find video stream
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    return {
                        'width': stream.get('width', 0),
                        'height': stream.get('height', 0),
                        'duration': float(stream.get('duration', 0)),
                        'fps': eval(stream.get('r_frame_rate', '0/1')),
                        'codec': stream.get('codec_name', ''),
                        'bitrate': int(info.get('format', {}).get('bit_rate', 0))
                    }
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting video info for {video_path}: {e}")
        return None


def determine_optimal_resolution(input_video_path: str) -> Tuple[int, int]:
    """
    Determine optimal output resolution based on input video aspect ratio.
    
    Args:
        input_video_path (str): Path to the input video
        
    Returns:
        Tuple of (width, height) for optimal output resolution
    """
    try:
        video_info = get_video_info(input_video_path)
        
        if not video_info:
            logger.warning(f"Could not get video info for {input_video_path}, defaulting to 1920x1080")
            return (1920, 1080)  # Default to horizontal
        
        width = video_info.get('width', 1920)
        height = video_info.get('height', 1080)
        
        if width == 0 or height == 0:
            logger.warning(f"Invalid dimensions {width}x{height}, defaulting to 1920x1080")
            return (1920, 1080)
        
        aspect_ratio = width / height
        
        logger.info(f"Input video: {width}x{height}, aspect ratio: {aspect_ratio:.3f}")
        
        # Determine optimal output resolution based on aspect ratio
        if aspect_ratio > 1.5:  # Horizontal (16:9, 21:9, etc.)
            optimal_resolution = (1920, 1080)  # HD horizontal
            logger.info("Detected horizontal video -> 1920x1080 output")
        elif aspect_ratio < 0.7:  # Vertical (9:16, 9:21, etc.)
            optimal_resolution = (1080, 1920)  # HD vertical
            logger.info("Detected vertical video -> 1080x1920 output")
        else:  # Square-ish (1:1, 4:3, 3:4, etc.)
            optimal_resolution = (1080, 1080)  # Square
            logger.info("Detected square/square-ish video -> 1080x1080 output")
        
        return optimal_resolution
        
    except Exception as e:
        logger.error(f"Error determining optimal resolution for {input_video_path}: {e}")
        return (1920, 1080)  # Default fallback


def get_target_aspect_ratio(target_resolution: Tuple[int, int]) -> float:
    """
    Get target aspect ratio from resolution tuple.
    
    Args:
        target_resolution: Tuple of (width, height)
        
    Returns:
        Aspect ratio as float
    """
    width, height = target_resolution
    return width / height if height > 0 else 16/9

