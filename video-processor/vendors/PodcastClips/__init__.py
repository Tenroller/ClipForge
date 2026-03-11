"""
PodcastClips workflow - Generate viral short-form videos from podcasts.

This workflow:
1. Downloads YouTube podcast videos
2. Transcribes with word-level timestamps using Whisper
3. Uses AI to detect viral moments
4. Tracks speaker faces for intelligent cropping
5. Generates 5-10 short-form (9:16) videos with subtitles

Enhanced Features:
- Parallel clip generation (3x-5x speedup)
- Mixed-mode content detection (face-tracking + horizontal content)
- Automatic detection of screen recordings, articles, and visual content
- Smooth transitions between face-tracked and horizontal modes
- Thumbnail generation for social media
- Audio normalization and enhancement
- Clip quality scoring and ranking
- Smart hook optimization
"""

# =============================================================================
# FFmpeg DLL Configuration for torio/torchaudio (MUST be FIRST before imports)
# This enables pyannote.audio speaker diarization on Windows
# =============================================================================
import os
import platform
if platform.system() == "Windows":
    FFMPEG_SHARED_BIN = r"C:\ffmpeg-shared\ffmpeg-6.1.1-full_build-shared\bin"
    if os.path.exists(FFMPEG_SHARED_BIN):
        # CRITICAL: For Python 3.8+ on Windows, we must use os.add_dll_directory()
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(FFMPEG_SHARED_BIN)
            except Exception:
                pass  # Already added or other issues
        # Also add to PATH for subprocess calls
        current_path = os.environ.get("PATH", "")
        if FFMPEG_SHARED_BIN not in current_path:
            os.environ["PATH"] = FFMPEG_SHARED_BIN + os.pathsep + current_path

from .processor import PodcastClipsProcessor
from .face_tracker import FaceTracker
from .clip_generator import ClipGenerator, ViralMoment, GeneratedClip
from .content_detector import ContentModeDetector, ContentSegment, ContentMode
from .thumbnail_generator import ThumbnailGenerator
from .audio_enhancer import AudioEnhancer
from .clip_scorer import ClipScorer
from .hook_optimizer import HookOptimizer

__all__ = [
    'PodcastClipsProcessor',
    'FaceTracker',
    'ClipGenerator',
    'ViralMoment',
    'GeneratedClip',
    'ContentModeDetector',
    'ContentSegment',
    'ContentMode',
    'ThumbnailGenerator',
    'AudioEnhancer',
    'ClipScorer',
    'HookOptimizer'
]
