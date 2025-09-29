#!/usr/bin/env python3
"""
TikYou Video Generator

Takes a YouTube URL, downloads the video, splits it into individual clips,
processes them based on orientation, and creates 3 random vertical compilations.
"""

import sys
import os
import re
import random
import argparse
import shutil
import gc
import psutil
import time
import uuid
from pathlib import Path
from tqdm import tqdm
import torch
from typing import List, Dict, Any, Optional, Tuple

from moviepy import (
    VideoFileClip,
    CompositeVideoClip,
    ColorClip,
    TextClip,
    concatenate_videoclips,
    vfx,
    VideoClip
)

# Import centralized font utility
try:
    from font_detection import get_font_fallback_list
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from font_detection import get_font_fallback_list

from .processor import CatVideoProcessor
from .tiktok import TikTokVideoCreator
from .title_generator import TitleGenerator

# Import our new modules
from .config import TikYouConfig
from .logging_config import get_logger, get_performance_logger
from .validation import InputValidator, validate_youtube_url, ensure_valid_or_raise
try:  # Attempt normal import when running inside backend package
    import importlib
    _youtube_mod = importlib.import_module('backend.utils.youtube')  # type: ignore
    util_extract_video_id = getattr(_youtube_mod, 'extract_video_id')
    util_download_video = getattr(_youtube_mod, 'download_video')
    _YouTubeDownloadError = getattr(_youtube_mod, 'YouTubeDownloadError')
except Exception:  # pragma: no cover
    # Fallback path adjustments for direct script execution
    import sys as _sys
    from pathlib import Path as _Path
    backend_dir = _Path(__file__).resolve().parent.parent.parent.parent
    if str(backend_dir) not in _sys.path:
        _sys.path.insert(0, str(backend_dir))
    try:
        _youtube_mod = importlib.import_module('backend.utils.youtube')  # type: ignore
        util_extract_video_id = getattr(_youtube_mod, 'extract_video_id')
        util_download_video = getattr(_youtube_mod, 'download_video')
        _YouTubeDownloadError = getattr(_youtube_mod, 'YouTubeDownloadError')
    except Exception:
        def util_extract_video_id(url: str) -> str:  # type: ignore
            import re as _re
            m = _re.search(r'(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([^&\n?#]+)', url)
            if not m:
                raise ValueError(f"Could not extract video id from: {url}")
            return m.group(1)
        def util_download_video(url: str, output_dir: str):  # type: ignore
            raise RuntimeError("youtube utility unavailable; cannot download video in standalone mode")
        class _YouTubeDownloadError(RuntimeError):  # type: ignore
            pass

YouTubeDownloadError = _YouTubeDownloadError  # unify name locally

# Provide a lightweight alias with relaxed typing to silence strict type expectations
util_download_video_alias: Any = util_download_video  # type: ignore
from .caching import get_video_analysis_cache
from .data_models import (
    ClipInfo, VideoOrientation, SceneType, ProcessingStatus, CompilationType,
    CompilationRequest, CompilationResult, PerformanceStats,
    SystemResources, ProcessingParams, create_system_resources, create_performance_stats
)
from .exceptions import (
    CompilationError,
    ValidationError, EncodingError
)

logger = get_logger()
performance_logger = get_performance_logger()


class ClipProcessor:
    """Handles individual clip processing operations"""
    
    def __init__(self, config: TikYouConfig):
        self.config = config
        self.logger = logger
    
    def process_clip_for_compilation(self, clip_path: str, target_resolution: Tuple[int, int]) -> Optional[VideoClip]:
        """
        Load, resize, and process a single clip for compilation.
        Refactored from the original large method.
        """
        try:
            self.logger.video_processing(f"Loading clip: {os.path.basename(clip_path)}")
            
            # Load clip with validation
            clip = self._load_and_validate_clip(clip_path)
            if not clip:
                return None
            
            # Process based on resolution
            if self._is_low_resolution_clip(clip, target_resolution):
                processed_clip = self._process_low_resolution_clip(clip, target_resolution)
            else:
                processed_clip = self._process_high_resolution_clip(clip, target_resolution)
            
            # Ensure audio exists
            final_clip = self._ensure_audio_track(processed_clip)
            
            self.logger.video_processing("Clip processing completed successfully")
            return final_clip
            
        except Exception as e:
            self.logger.error(f"Error processing clip {os.path.basename(clip_path)}: {e}")
            return None
    
    def _load_and_validate_clip(self, clip_path: str) -> Optional[VideoFileClip]:
        """Load and validate a video clip"""
        try:
            clip = VideoFileClip(clip_path, audio=True)
            
            # Validate clip properties
            if clip.duration is None or clip.duration <= 0:
                self.logger.error(f"Invalid clip duration: {clip_path}")
                return None
            
            w, h = clip.size
            self.logger.video_processing(f"Original dimensions: {w}x{h}")
            self.logger.video_processing(f"Original duration: {clip.duration:.1f}s")
            
            return clip
            
        except Exception as e:
            self.logger.error(f"Failed to load clip {clip_path}: {e}")
            return None
    
    def _is_low_resolution_clip(self, clip: VideoFileClip, target_resolution: Tuple[int, int]) -> bool:
        """Check if clip is low resolution and needs special handling"""
        w, h = clip.size
        target_w, target_h = target_resolution
        
        is_low_res = (w < target_w * self.config.processing.low_res_scale_factor or 
                     h < target_h * self.config.processing.low_res_scale_factor)
        
        if is_low_res:
            self.logger.video_processing(f"Low-res clip detected ({w}x{h}), using solid background approach")
        else:
            self.logger.video_processing(f"High-res clip detected, using standard processing")
        
        return is_low_res
    
    def _process_low_resolution_clip(self, clip: VideoFileClip, target_resolution: Tuple[int, int]) -> VideoClip:
        """Process low resolution clip with solid background"""
        target_w, target_h = target_resolution
        
        # Create solid background
        self.logger.video_processing("Creating solid background...")
        background = ColorClip(
            size=(target_w, target_h), 
            color=self.config.ui.background_color, 
            duration=clip.duration
        )
        
        # Resize clip to fit within bounds
        resized_clip = self._resize_clip_to_fit(clip, target_resolution)

        # Position clip at center and composite
        self.logger.video_processing("Positioning clip at center and compositing...")
        centered_clip = resized_clip.with_position("center")
        final_clip = CompositeVideoClip([background, centered_clip], size=(target_w, target_h))

        # Preserve audio
        if final_clip.audio is None and clip.audio is not None:
            self.logger.video_processing("Preserving original audio...")
            try:
                from moviepy import CompositeAudioClip
                final_clip.audio = CompositeAudioClip([clip.audio])
            except Exception:
                self.logger.debug("Failed to attach original audio to composite clip")

        return final_clip
    
    def _resize_clip_to_fit(self, clip: VideoClip, target_resolution: Tuple[int, int]) -> VideoClip:
        """Resize clip to fit within target bounds while preserving aspect ratio"""
        target_w, target_h = target_resolution
        w, h = clip.size
        
        clip_max_w = target_w * self.config.processing.low_res_fit_factor
        clip_max_h = target_h * self.config.processing.low_res_fit_factor
        
        if w > clip_max_w or h > clip_max_h:
            ratio = min(clip_max_w/w, clip_max_h/h)
            self.logger.video_processing(f"Resizing clip by ratio: {ratio:.3f}")
            try:
                return clip.with_effects([vfx.Resize(ratio)])  # type: ignore
            except Exception:
                return clip
        else:
            self.logger.video_processing("No resize needed, clip fits within bounds")
            return clip
    
    def _process_high_resolution_clip(self, clip: VideoClip, target_resolution: Tuple[int, int]) -> VideoClip:
        """Process high resolution clip with standard approach"""
        w, h = clip.size
        target_w, target_h = target_resolution
        
        aspect_ratio = w / h
        target_aspect_ratio = target_w / target_h
        
        self.logger.video_processing(f"Aspect ratios - Original: {aspect_ratio:.3f}, Target: {target_aspect_ratio:.3f}")
        
        if abs(aspect_ratio - target_aspect_ratio) > 0.01:
            if aspect_ratio > target_aspect_ratio:  # Wider than target
                return self._resize_and_crop_wide_clip(clip, target_resolution)
            else:  # Taller than target
                return self._resize_and_crop_tall_clip(clip, target_resolution)
        else:
            self.logger.video_processing("Aspect ratios match, simple resize...")
            try:
                return clip.with_effects([vfx.Resize(width=target_w, height=target_h)])  # type: ignore
            except Exception:
                return clip
    
    def _resize_and_crop_wide_clip(self, clip: VideoClip, target_resolution: Tuple[int, int]) -> VideoClip:
        """Resize and crop a wide clip"""
        target_w, target_h = target_resolution
        self.logger.video_processing("Clip is wider than target, resizing and cropping...")

        try:
            resized_clip = clip.with_effects([vfx.Resize(height=target_h)])  # type: ignore
        except Exception:
            resized_clip = clip

        # Get dimensions after resize
        resized_w, resized_h = resized_clip.size  # type: ignore
        x1 = int((resized_w - target_w) // 2)
        y1 = int((resized_h - target_h) // 2)
        x2 = x1 + target_w
        y2 = y1 + target_h
        try:
            return resized_clip.with_effects([vfx.Crop(x1, y1, x2, y2)])  # type: ignore
        except Exception:
            try:
                crop_fn = getattr(resized_clip, 'crop', None)
                if callable(crop_fn):
                    return crop_fn(x1=x1, y1=y1, x2=x2, y2=y2)  # type: ignore
                return resized_clip  # type: ignore
            except Exception:
                return resized_clip  # type: ignore
    
    def _resize_and_crop_tall_clip(self, clip: VideoClip, target_resolution: Tuple[int, int]) -> VideoClip:
        """Resize and crop a tall clip"""
        target_w, target_h = target_resolution
        self.logger.video_processing("Clip is taller than target, resizing and cropping...")

        try:
            resized_clip = clip.with_effects([vfx.Resize(width=target_w)])  # type: ignore
        except Exception:
            resized_clip = clip

        # Get dimensions after resize
        resized_w, resized_h = resized_clip.size  # type: ignore
        x1 = int((resized_w - target_w) // 2)
        y1 = int((resized_h - target_h) // 2)
        x2 = x1 + target_w
        y2 = y1 + target_h
        try:
            return resized_clip.with_effects([vfx.Crop(x1, y1, x2, y2)])  # type: ignore
        except Exception:
            try:
                crop_fn = getattr(resized_clip, 'crop', None)
                if callable(crop_fn):
                    return crop_fn(x1=x1, y1=y1, x2=x2, y2=y2)  # type: ignore
                return resized_clip  # type: ignore
            except Exception:
                return resized_clip  # type: ignore
    
    def _ensure_audio_track(self, clip: VideoClip) -> VideoClip:
        """Ensure clip has an audio track, add silent one if missing"""
        if clip.audio is None:
            self.logger.video_processing("Clip has no audio, adding silent track")
            try:
                from moviepy import AudioClip
                silent_audio = AudioClip(lambda t: 0, duration=clip.duration, fps=44100)
                return clip.with_audio(silent_audio)
            except Exception:
                return clip
        else:
            self.logger.video_processing("Audio track found and preserved")
            return clip


class VideoProcessor:
    """Handles video processing and analysis operations"""
    
    
    
    def __init__(self, config: TikYouConfig):
        self.config = config
        self.validator = InputValidator()
        self.cache = get_video_analysis_cache()
        self.processor = CatVideoProcessor(output_dir=config.paths.output_dir)
        self.creator = TikTokVideoCreator(output_dir=config.paths.output_dir)
        self.logger = logger
    
    def process_single_video(self, youtube_url: str, sensitivity: float = 30.0) -> List[ClipInfo]:
        """
        Process a single YouTube video into clips.
        Refactored from the original large method.
        """
        self.logger.video_processing(f"Processing YouTube URL: {youtube_url}")
        
        # Validate URL
        url_validation = validate_youtube_url(youtube_url)
        ensure_valid_or_raise(url_validation, ValidationError)
            
        # Extract video ID
        video_id = self._extract_video_id(youtube_url)
        
        # Download video
        video_path = self._download_video(video_id)
        if not video_path:
            return []
        
        # Crop pillarboxes
        processed_video_path = self._crop_pillarboxes(video_path)
        
        # Analyze video
        analysis = self._analyze_video(processed_video_path, sensitivity)
        
        # Create clips
        clips = self._create_clips_from_analysis(analysis, video_id, processed_video_path)
        
        self.logger.video_processing(f"Processing complete: {len(clips)} clips ready")
        return clips
    
    def process_uploaded_video(self, video_path: str, sensitivity: float = 30.0) -> List[ClipInfo]:
        """
        Process an uploaded video file into clips.
        Skips the YouTube download step and processes the file directly.
        
        Args:
            video_path: Path to the uploaded video file
            sensitivity: Detection threshold
        """
        self.logger.video_processing(f"Processing uploaded video: {video_path}")
        
        # Validate video file
        from .validation import validate_video_file
        validation = validate_video_file(video_path)
        ensure_valid_or_raise(validation, ValidationError)
        
        # Generate a unique ID for this uploaded video (use filename without extension)
        import os
        from pathlib import Path
        video_id = Path(video_path).stem
        
        self.logger.video_processing(f"Using video ID from filename: {video_id}")
        
        # Crop pillarboxes
        processed_video_path = self._crop_pillarboxes(video_path)
        
        # Analyze video
        analysis = self._analyze_video(processed_video_path, sensitivity)
        
        # Create clips
        clips = self._create_clips_from_analysis(analysis, video_id, processed_video_path)
        
        self.logger.video_processing(f"Uploaded video processing complete: {len(clips)} clips ready")
        return clips
    
    def process_video_source(self, youtube_url: Optional[str] = None, uploaded_video_path: Optional[str] = None, sensitivity: float = 30.0) -> List[ClipInfo]:
        """
        Process a video from either YouTube URL or uploaded file.
        
        Args:
            youtube_url: YouTube URL to download and process (optional)
            uploaded_video_path: Path to uploaded video file (optional)
            sensitivity: Detection threshold
            
        Returns:
            List of ClipInfo objects
            
        Raises:
            ValidationError: If neither or both sources are provided, or if validation fails
        """
        if not youtube_url and not uploaded_video_path:
            raise ValidationError(
                field_name="video_source",
                field_value="None",
                constraint="Either youtube_url or uploaded_video_path must be provided"
            )
        
        if youtube_url and uploaded_video_path:
            raise ValidationError(
                field_name="video_source", 
                field_value="Both provided",
                constraint="Cannot provide both youtube_url and uploaded_video_path"
            )
        
        if youtube_url:
            self.logger.video_processing("Processing YouTube URL")
            return self.process_single_video(youtube_url, sensitivity)
        elif uploaded_video_path:
            self.logger.video_processing("Processing uploaded video file")
            return self.process_uploaded_video(uploaded_video_path, sensitivity)
        else:
            # This should never happen due to earlier validation, but added for type safety
            raise ValidationError(
                field_name="video_source",
                field_value="None",
                constraint="No valid video source provided"
            )
    
    def _extract_video_id(self, youtube_url: str) -> str:
        """Delegate video ID extraction to unified youtube utility."""
        try:
            video_id = util_extract_video_id(youtube_url)
            self.logger.video_processing(f"Extracted video ID (utility): {video_id}")
            return video_id
        except Exception:
            raise ValidationError(
                field_name="youtube_url",
                field_value=youtube_url,
                constraint="Must be a valid YouTube URL"
            )
    
    def _download_video(self, video_id: str) -> Optional[str]:
        """Download video and return path using unified youtube utility.

        We receive a video_id, reconstruct a watch URL for stability.
        """
        self.logger.video_processing("Downloading video (utility)...")
        url = f"https://www.youtube.com/watch?v={video_id}"
        output_dir = str(Path(self.config.paths.output_dir) / video_id)
        try:
            result = util_download_video(url, output_dir)
            self.logger.video_processing(f"Downloaded: {result.video_path}")
            return result.video_path
        except YouTubeDownloadError as e:
            self.logger.error(f"YouTube download failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected download error: {e}")
            return None
    
    def _crop_pillarboxes(self, video_path: str) -> str:
        """Detect and crop pillarboxes from video"""
        self.logger.video_processing("Detecting and cropping pillarboxes...")
        
        try:
            cropped_path = self.processor.crop_video_if_vertical_with_blur(video_path)
            
            if cropped_path != video_path:
                self.logger.video_processing(f"Pillarboxes cropped: {os.path.basename(cropped_path)}")
            else:
                self.logger.video_processing("No pillarboxes detected or cropping not needed")
            
            return cropped_path
            
        except Exception as e:
            self.logger.error(f"Pillarbox cropping failed: {e}")
            return video_path  # Return original if cropping fails
    
    def _analyze_video(self, video_path: str, sensitivity: float, method: str = 'scenedetect') -> Dict[str, Any]:
        """Analyze video for scenes with caching"""
        self.logger.video_processing("Analyzing video for scenes...")
        
        # Try to get from cache first
        cached_analysis = self.cache.get_analysis(video_path, sensitivity)
        if cached_analysis:
            self.logger.video_processing("Using cached video analysis")
            return cached_analysis.__dict__
        
        # Perform analysis
        analysis = self.processor.analyze_video_scenes(video_path, threshold=sensitivity, method=method)
        
        # Cache results
        # TODO: Convert to VideoAnalysis dataclass and cache
        
        self.logger.video_processing("Video analysis completed")
        self.logger.video_processing(f"Compilation: {'Yes' if analysis['is_compilation'] else 'No'}")
        self.logger.video_processing(f"Scenes found: {len(analysis['scenes'])}")
        self.logger.video_processing(f"Duration: {analysis['duration']:.1f}s")
        
        return analysis
    
    def _create_clips_from_analysis(self, analysis: Dict[str, Any], video_id: str, video_path: str) -> List[ClipInfo]:
        """Create ClipInfo objects from analysis results"""
        clips = []
        
        if analysis['is_compilation'] and len(analysis['scenes']) > 1:
            clips = self._create_clips_from_scenes(analysis, video_id, video_path)
        else:
            clips = self._create_single_clip(analysis, video_id, video_path)
        
        return clips
    
    def _create_clips_from_scenes(self, analysis: Dict[str, Any], video_id: str, video_path: str) -> List[ClipInfo]:
        """Create clips from scene analysis"""
        self.logger.video_processing(f"Splitting compilation into {len(analysis['scenes'])} scenes...")
        
        clips = []
        temp_dir, split_videos = self.processor.split_video_from_scenes(
            video_path, video_id, analysis['scenes']
        )
        
        for split_info in split_videos:
            if os.path.exists(split_info['path']):
                # Crop pillarboxes on individual clip
                cropped_clip_path = self._crop_pillarboxes(split_info['path'])
                split_info['path'] = cropped_clip_path
                
                # Create ClipInfo
                clip_info = ClipInfo(
                    id=split_info.get('id', f"{video_id}-scene-{split_info.get('scene_number', 'unknown')}"),
                    path=split_info['path'],
                    duration=split_info['duration'],
                    orientation=VideoOrientation(self.creator.get_video_orientation(split_info['path'])),
                    source_id=video_id,
                    type=SceneType.SPLIT,
                    scene_number=split_info.get('scene_number')
                )
                clips.append(clip_info)
        
        return clips
    
    def _create_single_clip(self, analysis: Dict[str, Any], video_id: str, video_path: str) -> List[ClipInfo]:
        """Create a single clip from the whole video"""
        self.logger.video_processing("Single video, not splitting")
        
        clip_info = ClipInfo(
            id=video_id,
            path=video_path,
            duration=analysis['duration'],
            orientation=VideoOrientation(self.creator.get_video_orientation(video_path)),
            source_id=video_id,
            type=SceneType.SINGLE
        )
        
        return [clip_info]


class CompilationBuilder:
    """Handles compilation creation and management"""
    
    def __init__(self, config: TikYouConfig):
        self.config = config
        self.logger = logger
        self.clip_processor = ClipProcessor(config)
        self.validator = InputValidator()
        
        # Initialize generators
        self.tts_generator = self._initialize_tts_generator()
        self.title_generator = self._initialize_title_generator()
    
    def _initialize_tts_generator(self):
        """Initialize TTS generator if available"""
        try:
            from .tts_generator import TTSGenerator
            tts_gen = TTSGenerator()
            self.logger.system_info("TTS Generator initialized successfully")
            return tts_gen
        except Exception as e:
            self.logger.warning(f"TTS Generator initialization failed: {e}")
            return None
    
    def _initialize_title_generator(self) -> Optional[TitleGenerator]:
        """Initialize title generator if available"""
        try:
            title_gen = TitleGenerator()
            self.logger.system_info("Title Generator initialized successfully")
            return title_gen
        except Exception as e:
            self.logger.warning(f"Title Generator initialization failed: {e}")
            return None
    
    def create_compilation(self, request: CompilationRequest) -> CompilationResult:
        """Create a single compilation from a request"""
        self.logger.info(f"Creating compilation #{request.compilation_num}")
        
        # Validate request
        validation_result = self.validator.validate_compilation_request(request)
        ensure_valid_or_raise(validation_result, ValidationError)
        
        start_time = time.time()
        result = CompilationResult(
            compilation_request=request,
            status=ProcessingStatus.IN_PROGRESS
        )
        
        compilation_clip = None  # predefine for finally block
        final_clips = []  # predefine for finally block
        try:
            # Process clips
            final_clips = self._process_clips_for_compilation(request.clips, request.target_resolution)
            if not final_clips:
                raise CompilationError(
                    compilation_id=str(request.compilation_num),
                    clips_count=len(request.clips),
                    total_duration=request.total_clips_duration,
                    reason="No valid clips found after processing"
                )
            
            # Create compilation
            compilation_clip = self._create_compilation_from_clips(final_clips)
            
            # Add title if available
            if request.title and self.title_generator:
                compilation_clip = self._add_title_overlay(compilation_clip, request.title)
            
            # Write to file
            self._write_compilation_to_file(compilation_clip, request.output_path)
            
            # Update result
            result.status = ProcessingStatus.COMPLETED
            result.output_path = request.output_path
            result.processing_time = time.time() - start_time
            result.output_size_mb = os.path.getsize(request.output_path) / (1024 * 1024)
            result.actual_duration = compilation_clip.duration
            
            self.logger.info(f"Compilation #{request.compilation_num} completed successfully")
            
        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.error_message = str(e)
            result.processing_time = time.time() - start_time
            
            self.logger.error(f"Compilation #{request.compilation_num} failed: {e}")
            
        finally:
            # Cleanup
            try:
                if compilation_clip is not None:
                    compilation_clip.close()
            except Exception:
                pass
            for clip in final_clips:
                try:
                    clip.close()
                except Exception:
                    pass
            gc.collect()
        
        return result
    
    def _process_clips_for_compilation(self, clips: List[ClipInfo], target_resolution: Tuple[int, int]) -> List[VideoClip]:
        """Process clips for compilation"""
        self.logger.processing_step(f"Processing {len(clips)} clips for compilation...")
        
        final_clips = []
        
        with tqdm(total=len(clips), desc="Processing clips") as pbar:
            for i, clip_info in enumerate(clips):
                # ClipInfo may not have `filename` attribute; use basename of path
                self.logger.video_processing(f"Processing clip {i+1}/{len(clips)}: {os.path.basename(clip_info.path)}")
                
                processed_clip = self.clip_processor.process_clip_for_compilation(
                    clip_info.path, target_resolution
                )
                
                if processed_clip:
                    final_clips.append(processed_clip)
                    self.logger.video_processing("Clip processed successfully")
                else:
                    self.logger.error("Failed to process clip")
                
                pbar.update(1)
        
        self.logger.processing_step(f"Successfully processed {len(final_clips)} clips")
        return final_clips
    
    def _create_compilation_from_clips(self, clips: List[VideoClip]) -> VideoClip:
        """Create compilation by concatenating clips"""
        self.logger.processing_step("Concatenating clips into final compilation...")
        
        try:
            compilation = concatenate_videoclips(clips, method="compose")
            self.logger.processing_step(f"Concatenation completed successfully")
            self.logger.processing_step(f"Final compilation duration: {compilation.duration:.1f}s")
            return compilation
            
        except Exception as e:
            raise CompilationError(
                compilation_id="unknown",
                clips_count=len(clips),
                total_duration=sum(clip.duration for clip in clips),
                reason=f"Concatenation failed: {str(e)}"
            )
    
    def _add_title_overlay(self, compilation: VideoClip, title: str) -> VideoClip:
        """Add title overlay to compilation"""
        self.logger.processing_step(f"Adding title overlay: '{title}'")
        
        try:
            # Font fallback mechanism - try multiple fonts until one works
            # Use centralized font fallback list
            font_choices = get_font_fallback_list()
            title_clip = None

            for font_choice in font_choices:
                try:
                    title_clip = TextClip(
                        text=title,
                        font_size=self.config.ui.title_font_size,
                        font=font_choice,  # Try different fonts
                        color=self.config.ui.title_color,
                        stroke_color=self.config.ui.title_stroke_color,
                        stroke_width=self.config.ui.title_stroke_width
                    ).with_duration(compilation.duration)
                    self.logger.processing_step(f"Title clip created successfully with font: {font_choice or 'default'}")
                    break  # Success - exit the loop
                except Exception as font_error:
                    self.logger.debug(f"Failed to create title clip with font '{font_choice or 'default'}': {font_error}")
                    continue  # Try next font

            # If all fonts failed, raise an error
            if title_clip is None:
                raise Exception("Failed to create title clip with any available font")
            
            title_clip = title_clip.with_position(('center', self.config.ui.title_y_position))
            
            final_compilation = CompositeVideoClip([compilation, title_clip])
            self.logger.processing_step("Title overlay added successfully")
            return final_compilation
            
        except Exception as e:
            self.logger.warning(f"Failed to add title overlay: {e}")
            return compilation
    
    def _write_compilation_to_file(self, compilation: VideoClip, output_path: str):
        """Write compilation to file with optimized encoding"""
        self.logger.processing_step(f"Writing compilation to file: {output_path}")
        
        # Get system resources for adaptive encoding
        resources = create_system_resources()
        
        # Get encoding parameters
        encoding_params = self.config.get_encoding_params(
            use_gpu=resources.gpu_available,
            duration=compilation.duration,
            resolution=(compilation.w, compilation.h)
        )
        
        self.logger.encoding_info(f"Encoding with {encoding_params['codec']}")
        self.logger.log_encoding_params(encoding_params)
        
        try:
            # Create unique temp audio file
            temp_audio_file = self.config.paths.temp_audio_pattern.format(uuid=uuid.uuid4().hex)
            
            compilation.write_videofile(
                str(output_path),
                codec=encoding_params['codec'],
                audio_codec=encoding_params['audio_codec'],
                temp_audiofile=temp_audio_file,
                remove_temp=True,
                fps=encoding_params['fps'],
                preset=encoding_params['preset'],
                threads=self.config.processing.max_workers,
                logger="bar",
                bitrate=encoding_params['bitrate'],
                ffmpeg_params=encoding_params['ffmpeg_params'],
            )
            
            self.logger.processing_step("Video file written successfully")
            
        except Exception as e:
            raise EncodingError(
                input_path="compilation",
                output_path=output_path,
                codec=str(encoding_params['codec']),
                reason=str(e)
            )


class ResourceManager:
    """Handles system resource monitoring and management"""
    
    def __init__(self, config: TikYouConfig):
        self.config = config
        self.logger = logger
        self.validator = InputValidator()
        self.initial_resources = create_system_resources()
        
        self.logger.log_system_resources(
            self.initial_resources.cpu_percent,
            self.initial_resources.memory_percent,
            self.initial_resources.available_memory_gb,
            self.initial_resources.disk_space_gb
        )
    
    def check_system_resources(self) -> SystemResources:
        """Check current system resources"""
        resources = create_system_resources()
        
        # Validate resources
        validation_result = self.validator.validate_system_resources(resources)
        if not validation_result.is_valid:
            self.logger.warning("System resources validation failed:")
            for error in validation_result.errors:
                self.logger.warning(f"  - {error}")
        
        return resources
    
    def get_adaptive_processing_params(self, clips_count: int, total_duration: float) -> ProcessingParams:
        """Get adaptive processing parameters based on current system state"""
        resources = self.check_system_resources()
        
        params_dict = self.config.get_adaptive_processing_params(
            clips_count=clips_count,
            total_duration=total_duration,
            cpu_percent=resources.cpu_percent,
            memory_percent=resources.memory_percent,
            available_memory_gb=resources.available_memory_gb,
            use_gpu=resources.gpu_available
        )
        
        # Convert to ProcessingParams dataclass
        processing_params = ProcessingParams(
            max_workers=params_dict['max_workers'],
            chunk_size=params_dict['chunk_size'],
            quality_preset=params_dict['preset'],
            bitrate=params_dict['bitrate'],
            memory_conservative=params_dict['memory_conservative'],
            processing_strategy=params_dict['processing_strategy'],
            codec=params_dict['codec'],
            audio_codec=params_dict['audio_codec'],
            fps=params_dict['fps'],
            ffmpeg_params=params_dict['ffmpeg_params']
        )
        
        self.logger.processing_step(f"Adaptive parameters: {processing_params.to_dict()}")
        return processing_params
    
    def cleanup_resources(self):
        """Cleanup system resources"""
        self.logger.processing_step("Cleaning up resources...")
        
        gc.collect()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # Clean up temporary files
        temp_dir = Path(self.config.paths.temp_vertical_dir)
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                temp_dir.mkdir(parents=True, exist_ok=True)
                self.logger.processing_step("Temporary files cleaned up")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup temporary files: {e}")


class TikYouGeneratorRefactored:
    """
    Refactored version of the TikYou Video Generator with improved architecture
    """
    
    def __init__(self, config: Optional[TikYouConfig] = None):
        self.config = config or TikYouConfig()
        self.logger = logger
        self.performance_logger = performance_logger
        
        # Initialize components
        self.video_processor = VideoProcessor(self.config)
        self.compilation_builder = CompilationBuilder(self.config)
        self.resource_manager = ResourceManager(self.config)
        self.validator = InputValidator()
        
        # Setup environment
        self.config.setup_environment()
        self.config.create_directories()
        
        # Log initialization
        self.logger.info("TikYou Video Generator (Refactored) initialized")
        self.logger.info(f"GPU available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            self.logger.info(f"GPU: {gpu_name} ({gpu_memory:.1f}GB)")
    
    def generate_videos(self, youtube_url: str, num_compilations: Optional[int] = None,
                       min_duration: int = 20, max_duration: int = 40,
                       max_reuse: int = 3) -> PerformanceStats:
        """
        Generate videos from YouTube URL with improved error handling and logging
        """
        self.logger.log_phase_start("Video Generation", f"URL: {youtube_url}")
        
        # Initialize performance tracking
        stats = create_performance_stats()
        
        try:
            # Phase 1: Video Processing
            clips = self._process_video_phase(youtube_url, stats)
            if not clips:
                return stats
            
            # Phase 2: Compilation Generation
            self._generate_compilations_phase(clips, num_compilations, min_duration, 
                                           max_duration, max_reuse, stats)
            
            # Finalize statistics
            stats.end_time = time.time()
            
            self.logger.log_final_summary(
                stats.total_time,
                stats.successful_compilations,
                stats.failed_compilations,
                stats.total_variations,
                stats.total_output_size_mb
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Critical error in video generation: {e}")
            stats.end_time = time.time()
            return stats
        
        finally:
            # Cleanup
            self.resource_manager.cleanup_resources()
    
    def _process_video_phase(self, youtube_url: str, stats: PerformanceStats) -> List[ClipInfo]:
        """Process video phase with error handling"""
        phase_start = time.time()
        
        try:
            clips = self.video_processor.process_single_video(youtube_url)
            stats.download_time = time.time() - phase_start
            stats.total_clips_processed = len(clips)
            
            self.logger.log_phase_end("Video Processing", stats.download_time, success=True)
            return clips
            
        except Exception as e:
            stats.download_time = time.time() - phase_start
            self.logger.log_phase_end("Video Processing", stats.download_time, success=False)
            raise
    
    def _generate_compilations_phase(self, clips: List[ClipInfo], num_compilations: Optional[int],
                                   min_duration: int, max_duration: int, max_reuse: int,
                                   stats: PerformanceStats):
        """Generate compilations phase"""
        phase_start = time.time()
        
        try:
            # Create compilation requests
            requests = self._create_compilation_requests(clips, num_compilations, 
                                                       min_duration, max_duration, max_reuse)
            
            # Process each compilation
            for request in requests:
                result = self.compilation_builder.create_compilation(request)
                
                if result.success:
                    stats.successful_compilations += 1
                    stats.total_output_size_mb += result.output_size_mb
                    
                    # Update variation counts
                    if request.compilation_type == CompilationType.NORMAL:
                        stats.normal_variations += 1
                    elif request.compilation_type == CompilationType.TTS:
                        stats.tts_variations += 1
                    
                    stats.total_variations += 1
                else:
                    stats.failed_compilations += 1
                    self.logger.error(f"Compilation failed: {result.error_message}")
            
            stats.generation_time = time.time() - phase_start
            
        except Exception as e:
            stats.generation_time = time.time() - phase_start
            self.logger.error(f"Compilation generation phase failed: {e}")
            raise
    
    def _create_compilation_requests(self, clips: List[ClipInfo], num_compilations: Optional[int],
                                   min_duration: int, max_duration: int, max_reuse: int) -> List[CompilationRequest]:
        """Create compilation requests from clips"""
        requests = []
        clip_usage = {clip.path: 0 for clip in clips}
        
        target_count = num_compilations or self._calculate_max_compilations(clips, min_duration, max_duration, max_reuse)
        
        for i in range(target_count):
            # Select clips for this compilation
            selected_clips = self._select_clips_for_compilation(clips, clip_usage, max_reuse, min_duration, max_duration)
            
            if not selected_clips:
                self.logger.warning(f"Could not create compilation {i+1}, stopping")
                break
            
            # Update usage counts
            for clip in selected_clips:
                clip_usage[clip.path] += 1
            
            # Create requests for normal and TTS variations
            video_id = selected_clips[0].source_id
            
            # Normal compilation
            normal_request = CompilationRequest(
                clips=selected_clips,
                output_path=self.config.get_output_path(video_id, i+1, "normal"),
                compilation_type=CompilationType.NORMAL,
                compilation_num=i+1,
                min_duration=min_duration,
                max_duration=max_duration,
                target_resolution=self.config.video.size
            )
            requests.append(normal_request)
            
            # TTS compilation if available
            if self.compilation_builder.tts_generator:
                tts_request = CompilationRequest(
                    clips=selected_clips,
                    output_path=self.config.get_output_path(video_id, i+1, "tts"),
                    compilation_type=CompilationType.TTS,
                    compilation_num=i+1,
                    min_duration=min_duration,
                    max_duration=max_duration,
                    target_resolution=self.config.video.size
                )
                requests.append(tts_request)
        
        return requests
    
    def _calculate_max_compilations(self, clips: List[ClipInfo], min_duration: int, max_duration: int, max_reuse: int) -> int:
        """Calculate maximum possible compilations"""
        total_available_duration = sum(clip.duration * max_reuse for clip in clips)
        avg_compilation_duration = (min_duration + max_duration) / 2
        return max(1, int(total_available_duration / avg_compilation_duration))
    
    def _select_clips_for_compilation(self, clips: List[ClipInfo], clip_usage: Dict[str, int], 
                                    max_reuse: int, min_duration: int, max_duration: int) -> List[ClipInfo]:
        """Select clips for a compilation with constraints"""
        # Filter available clips
        available_clips = [clip for clip in clips if clip_usage.get(clip.path, 0) < max_reuse]
        
        if not available_clips:
            return []
        
        # Sort by priority: vertical first, then horizontal
        available_clips.sort(key=lambda c: (
            0 if c.orientation == VideoOrientation.VERTICAL else 1,
            random.random()  # Add randomness within each category
        ))
        
        # Select clips within duration constraints
        selected = []
        total_duration = 0
        
        for clip in available_clips:
            if total_duration + clip.duration <= max_duration:
                selected.append(clip)
                total_duration += clip.duration
                
                if total_duration >= min_duration:
                    break
        
        return selected if total_duration >= min_duration else []


def main():
    """Main function for CLI execution"""
    parser = argparse.ArgumentParser(description="TikYou Video Generator (Refactored)")
    
    parser.add_argument("youtube_url", help="The YouTube URL to process")
    parser.add_argument("-n", "--num_compilations", type=int,
                        help="The number of compilations to create")
    parser.add_argument("--min_duration", type=int, default=20,
                        help="Minimum duration of each compilation in seconds")
    parser.add_argument("--max_duration", type=int, default=40,
                        help="Maximum duration of each compilation in seconds")
    parser.add_argument("--max_reuse", type=int, default=3,
                        help="Maximum number of times a single clip can be reused")
    parser.add_argument("--config", type=str,
                        help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Load configuration
    config_obj = TikYouConfig(args.config) if args.config else TikYouConfig()
    
    # Initialize generator
    generator = TikYouGeneratorRefactored(config_obj)
    
    # Generate videos
    stats = generator.generate_videos(
        args.youtube_url,
        num_compilations=args.num_compilations,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        max_reuse=args.max_reuse
    )
    
    # Log final performance statistics
    performance_logger.log_performance_stats(stats.to_dict())


if __name__ == "__main__":
    main() 