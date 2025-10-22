import os
from pathlib import Path

def get_temp_dir() -> Path:
    # Navigate up from the current file's location (video-processor/utils) to the project root
    project_root = Path(__file__).parent.parent.parent
    temp_dir = project_root / "temp"
    
    # Create the directory if it doesn't exist
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    return temp_dir

def get_temp_file_path(filename: str) -> str:
    """Returns the full path for a file in the temp directory."""
    return str(get_temp_dir() / filename)
