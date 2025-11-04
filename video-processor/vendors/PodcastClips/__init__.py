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
- Thumbnail generation for social media
- Audio normalization and enhancement
- Clip quality scoring and ranking
- Smart hook optimization
"""

from .processor import PodcastClipsProcessor
from .face_tracker import FaceTracker
from .subtitle_generator import SubtitleGenerator
from .clip_generator import ClipGenerator, ViralMoment, GeneratedClip
from .thumbnail_generator import ThumbnailGenerator
from .audio_enhancer import AudioEnhancer
from .clip_scorer import ClipScorer
from .hook_optimizer import HookOptimizer

__all__ = [
    'PodcastClipsProcessor',
    'FaceTracker',
    'SubtitleGenerator',
    'ClipGenerator',
    'ViralMoment',
    'GeneratedClip',
    'ThumbnailGenerator',
    'AudioEnhancer',
    'ClipScorer',
    'HookOptimizer'
]
