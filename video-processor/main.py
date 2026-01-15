"""
Video Processor Service Main Entry Point
"""

import os
import sys
import platform

# =============================================================================
# FFmpeg DLL Configuration for torio/torchaudio (MUST be FIRST before any imports)
# This enables pyannote.audio speaker diarization on Windows
# =============================================================================
if platform.system() == "Windows":
    FFMPEG_SHARED_BIN = r"C:\ffmpeg-shared\ffmpeg-6.1.1-full_build-shared\bin"
    if os.path.exists(FFMPEG_SHARED_BIN):
        # CRITICAL: For Python 3.8+ on Windows, we must use os.add_dll_directory()
        # to allow torio/torchaudio to find FFmpeg DLLs
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(FFMPEG_SHARED_BIN)
                print(f"[FFmpeg] Added DLL directory: {FFMPEG_SHARED_BIN}")
            except Exception as e:
                print(f"[FFmpeg] Warning: Failed to add DLL directory: {e}")
        # Also add to PATH for subprocess calls
        current_path = os.environ.get("PATH", "")
        if FFMPEG_SHARED_BIN not in current_path:
            os.environ["PATH"] = FFMPEG_SHARED_BIN + os.pathsep + current_path
        os.environ["FFMPEG_BINARY"] = os.path.join(FFMPEG_SHARED_BIN, "ffmpeg.exe")
        os.environ["FFPROBE_BINARY"] = os.path.join(FFMPEG_SHARED_BIN, "ffprobe.exe")

# Now import the app (this triggers all other imports)
from src.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)
