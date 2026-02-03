#!/usr/bin/env python3
"""
Backend startup script that properly sets up the Python path.
"""

import sys
import os
from pathlib import Path
import warnings
import logging

# =============================================================================
# FFmpeg Configuration for torio/torchaudio (used by pyannote.audio)
# =============================================================================
# Using FFmpeg 7.1 shared build with DLLs for proper torio integration
# The shared build provides avcodec-61.dll, avformat-61.dll, etc.

# Path to FFmpeg shared libraries (with DLLs)
FFMPEG_SHARED_BIN = r"C:\ffmpeg-shared\ffmpeg-6.1.1-full_build-shared\bin"
# Fallback to static FFmpeg for subprocess calls if shared not available
FFMPEG_STATIC_BIN = r"C:\ffmpeg\bin"

# Determine which FFmpeg to use
import platform
import shutil

# Check system PATH first (works for macOS/Linux and properly configured Windows)
system_ffmpeg = shutil.which("ffmpeg")

if system_ffmpeg:
    print(f"[FFmpeg] Found on system PATH: {system_ffmpeg}")
    # We don't set FFMPEG_BINARY here necessarily, allowing backend/utils/ffmpeg_utils.py to detect it too
    # But setting it ensures consistency if we want
    if "FFMPEG_BINARY" not in os.environ:
        os.environ["FFMPEG_BINARY"] = system_ffmpeg

# Windows-specific DLL handling for torio/pyannote
elif os.path.exists(FFMPEG_SHARED_BIN) and platform.system() == "Windows":
    ffmpeg_bin_path = FFMPEG_SHARED_BIN
    
    # CRITICAL: For Python 3.8+ on Windows, we must use os.add_dll_directory()
    # to allow torio/torchaudio to find FFmpeg DLLs
    # This must be done BEFORE importing torchaudio or pyannote
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(FFMPEG_SHARED_BIN)
        print(f"[FFmpeg] Added DLL directory: {FFMPEG_SHARED_BIN}")
    
    # Also add to PATH for subprocess calls
    current_path = os.environ.get("PATH", "")
    if FFMPEG_SHARED_BIN not in current_path:
        os.environ["PATH"] = FFMPEG_SHARED_BIN + os.pathsep + current_path
    
    os.environ["FFMPEG_BINARY"] = os.path.join(FFMPEG_SHARED_BIN, "ffmpeg.exe")
    print(f"[FFmpeg] Using shared build: {FFMPEG_SHARED_BIN}")
    
elif os.path.exists(FFMPEG_STATIC_BIN) and platform.system() == "Windows":
    ffmpeg_bin_path = FFMPEG_STATIC_BIN
    
    # Suppress torio warnings for static FFmpeg (no DLLs available)
    warnings.filterwarnings("ignore", message=".*FFmpeg.*extension.*")
    logging.getLogger("torio._extension.utils").setLevel(logging.ERROR)
    
    current_path = os.environ.get("PATH", "")
    if FFMPEG_STATIC_BIN not in current_path:
        os.environ["PATH"] = FFMPEG_STATIC_BIN + os.pathsep + current_path
    
    os.environ["FFMPEG_BINARY"] = os.path.join(FFMPEG_STATIC_BIN, "ffmpeg.exe")
    print(f"[FFmpeg] Using static build (torio may show warnings): {FFMPEG_STATIC_BIN}")
else:
    print("[FFmpeg] WARNING: No FFmpeg installation found! (Please install FFmpeg and add it to PATH)")

def main():
    # Get the project root directory
    project_root = Path(__file__).parent.resolve()
    backend_dir = project_root / "backend"
    
    # Add project root to Python path so 'backend' module can be imported
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Add backend directory to path for direct imports (when in backend dir)
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "9000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    print(f"Starting ClipForge API on {host}:{port}")
    print(f"Project root: {project_root}")
    print(f"Python path includes: backend={str(backend_dir) in sys.path}")
    
    # Import uvicorn
    import uvicorn
    
    # Run the app using the backend module path
    uvicorn.run(
        "backend.app:app",  # Use backend.app:app since we're running from project root
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
