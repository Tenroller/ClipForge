#!/usr/bin/env python3
"""
TikYou Video Generator

Takes a YouTube URL, downloads the video, splits it into individual clips,
processes them based on orientation, and creates 3 random vertical compilations.

Usage:
    python -m tikyou_video_generator.generator <youtube_url>

Example:
    python -m tikyou_video_generator.generator "https://www.youtube.com/watch?v=ef9iFTB-3cs"
"""

import sys
import os
import re
import random
import argparse
import shutil
import gc
import psutil
import logging
from pathlib import Path
import multiprocessing
from tqdm import tqdm
import torch
import time
import uuid
import concurrent.futures
import hashlib
import subprocess

# Initialize logger for this module
logger = logging.getLogger("video_generator.compilation")

# Define placeholder logging functions if they don't exist in logging_config
def log_generation_step(logger, *args, **kwargs):
    logger.info(f"Generation step: {args}, {kwargs}")

def log_file_operation(logger, operation, path, **kwargs):
    logger.info(f"File {operation}: {path}, {kwargs}")


from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    ColorClip,
    ImageClip,
    TextClip,
    concatenate_videoclips,
    vfx
)

from .processor import CatVideoProcessor
try:
    from backend.utils.youtube import extract_video_id as unified_extract_video_id
except Exception:
    unified_extract_video_id = None  # fallback if utility unavailable during standalone execution
from .tiktok import TikTokVideoCreator

from .title_generator import TitleGenerator

# Font path setup for cross-platform compatibility
try:
    from backend.font_detection import get_font_fallback_list
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    backend_dir = Path(__file__).resolve().parent.parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from font_detection import get_font_fallback_list

# Get the centralized font fallback list
FONT_CHOICES = get_font_fallback_list()
FONT_PATH_STR = FONT_CHOICES[0] if FONT_CHOICES and FONT_CHOICES[0] else None

if FONT_PATH_STR:
    print(f"✅ Using default font: {FONT_PATH_STR}")
else:
    print(f"⚠️ Warning: Default font not found, will fall back to system fonts")


def convert_clip_worker(args):
    """Worker function for parallel video conversion"""
    clip_info, converted_paths, temp_files = args
    try:
        if clip_info['orientation'] in ['horizontal', 'square']:
            if clip_info['path'] not in converted_paths:
                generator = TikYouGenerator()
                vertical_path = generator.create_vertical_clip_from_horizontal(clip_info['path'])
                if vertical_path:
                    return (clip_info['path'], vertical_path)
    except Exception as e:
        print(f"Error converting clip {clip_info['path']}: {e}")
    return None

class TikYouGenerator:
    def __init__(self, output_dir="final_videos", ffmpeg_path=None, tracker=None, request=None):
        # FFMPEG 7+ compatibility fix for moviepy - cross-platform
        
        # Add the backend directory to the Python path
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
        from utils.ffmpeg_utils import setup_ffmpeg_environment
        
        setup_ffmpeg_environment()
        
        # Set FFmpeg 7+ compatibility flags
        os.environ["FFMPEG_7_COMPAT"] = "1"
        
        # Disable deprecated options that cause issues in FFmpeg 7+
        os.environ["FFMPEG_DISABLE_SHOW_FORMAT"] = "1"
        
        self.output_dir = output_dir
        self.processor = CatVideoProcessor(output_dir=output_dir, ffmpeg_path=ffmpeg_path)
        self.creator = TikTokVideoCreator(output_dir=output_dir, ffmpeg_path=ffmpeg_path)
        self.max_workers = min(multiprocessing.cpu_count(), 4)  # Limit to 4 workers max
        self.tracker = tracker  # Add tracker support
        self.request = request  # Store request for variation configuration
        
        # Performance optimization caches
        self.clip_cache = {}  # Cache for processed vertical clips
        self.encoding_cache = {}  # Cache for encoding parameters
        self.scene_analysis_cache = {}  # Cache for scene detection results
        self.video_metadata_cache = {}  # Cache for video metadata
        self.temp_dir = self._setup_temp_directory()
        self.cleanup_interval = 50  # Clean temp files every 50 compilations
        self.compilation_counter = 0
        
        # Initialize TTS generator for enhanced video variations
        try:
            # Import TTSGenerator here to handle import errors gracefully
            from .tts_generator import TTSGenerator
            self.tts_generator = TTSGenerator()
            self.tts_enabled = True
            logger.info("TTS Generator initialized successfully")
        except Exception as e:
            logger.warning(f"TTS Generator initialization failed: {e} - This is likely due to dependency version incompatibilities. TTS variations will be skipped")
            self.tts_generator = None
            self.tts_enabled = False
        
        # Initialize Title generator for video titles
        try:
            self.title_generator = TitleGenerator()
            self.title_enabled = True
            logger.info("Title Generator initialized successfully")
        except Exception as e:
            logger.warning(f"Title Generator initialization failed: {e} - Title overlays will be skipped")
            self.title_generator = None
            self.title_enabled = False
        
        # Memory monitoring
        self.memory_threshold = 0.85  # 85% memory usage threshold
        self.initial_memory = psutil.virtual_memory().percent
        print(f"💾 Initial memory usage: {self.initial_memory:.1f}%")
        
        # Check for GPU availability and optimize accordingly
        self.has_gpu = torch.cuda.is_available()
        self.encoding_params = self._get_optimized_encoding_params()
        
        if self.has_gpu:
            print("🎮 GPU acceleration available!")
            # Get GPU memory info
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3  # Convert to GB
            gpu_name = torch.cuda.get_device_name(0)
            print(f"   - GPU: {gpu_name}")
            print(f"   - GPU Memory: {gpu_mem:.1f}GB")
            # Adjust workers based on GPU memory
            self.max_workers = min(self.max_workers, max(1, int(gpu_mem / 2)))  # 2GB per worker
            print(f"   - Using {self.max_workers} workers based on GPU memory")
            print(f"   - GPU Encoding: {self.encoding_params['codec']} codec will be used")
        else:
            print("💻 Using CPU processing")
            print(f"   - CPU Encoding: {self.encoding_params['codec']} codec will be used")
            print(f"   - CPU Workers: {self.max_workers}")
        
        # Create output directory
        Path(self.output_dir).mkdir(exist_ok=True)
    
    def _log(self, message, level="info", component="tikyou"):
        """Helper method to log messages if tracker is available."""
        if self.tracker:
            self.tracker.add_log(message, level, component)
        else:
            # Fallback to print or logger if no tracker
            if level == "error":
                logger.error(f"{component}: {message}")
            elif level == "warning":
                logger.warning(f"{component}: {message}")
            else:
                logger.info(f"{component}: {message}")
    
    def _setup_temp_directory(self):
        """Set up optimized temporary directory for processing"""
        import tempfile
        
        # Try to use faster SSD temp directory if available
        temp_locations = ["/tmp", tempfile.gettempdir()]
        
        for temp_loc in temp_locations:
            if os.path.exists(temp_loc):
                try:
                    temp_dir = tempfile.mkdtemp(prefix="brainrot_", dir=temp_loc)
                    print(f"📁 Using temp directory: {temp_dir}")
                    return temp_dir
                except:
                    continue
        
        # Fallback to default
        temp_dir = tempfile.mkdtemp(prefix="brainrot_")
        print(f"📁 Using temp directory: {temp_dir}")
        return temp_dir
    
    def _get_optimized_encoding_params(self):
        """Get optimized encoding parameters based on available hardware"""
        params = {
            'codec': 'libx264',
            'ffmpeg_params': [
                '-preset', 'veryfast',
                '-crf', '23',
                '-movflags', '+faststart',
                '-tune', 'fastdecode'
            ]
        }
        
        # Check for hardware acceleration
        if self.has_gpu:
            # Check for NVIDIA GPU encoding support
            try:
                result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    params = {
                        'codec': 'h264_nvenc',
                        'ffmpeg_params': [
                            '-preset', 'p4',  # Fastest NVENC preset
                            '-tune', 'hq',
                            '-rc', 'vbr',
                            '-cq', '23',
                            '-b:v', '0',
                            '-maxrate', '10M',
                            '-bufsize', '20M'
                        ]
                    }
                    print("🎮 NVIDIA GPU encoding detected")
            except:
                pass
        
        return params
    
    def _cleanup_temp_files(self):
        """Periodic cleanup of temporary files"""
        try:
            current_time = time.time()
            cleanup_threshold = 3600  # 1 hour
            
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        if current_time - os.path.getmtime(file_path) > cleanup_threshold:
                            os.remove(file_path)
                    except:
                        pass  # Ignore errors for files in use
        except Exception as e:
            logger.warning(f"Temp cleanup failed: {e}")
    
    def _preprocess_clips_batch(self, video_clips, batch_size=None):
        """Pre-process clips in parallel batches for better performance"""
        if batch_size is None:
            batch_size = min(self.max_workers, 4)
        
        processed_clips = []
        clips_to_process = [clip for clip in video_clips if clip['duration'] >= 3.0]
        
        print(f"🔄 Pre-processing {len(clips_to_process)} clips in batches of {batch_size}")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            # Submit all conversion tasks
            future_to_clip = {}
            for clip in clips_to_process:
                if clip['orientation'] in ['horizontal', 'square']:
                    future = executor.submit(self._convert_clip_with_cache, clip['path'])
                    future_to_clip[future] = clip
                else:
                    # Vertical clips don't need conversion
                    processed_clips.append(clip)
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_clip):
                original_clip = future_to_clip[future]
                try:
                    vertical_path = future.result()
                    if vertical_path:
                        processed_clip = original_clip.copy()
                        processed_clip['vertical_path'] = vertical_path
                        processed_clips.append(processed_clip)
                    else:
                        # Keep original clip if conversion failed
                        processed_clips.append(original_clip)
                except Exception as e:
                    logger.warning(f"Failed to process clip {original_clip['path']}: {e}")
                    # Keep original clip even if conversion failed
                    processed_clips.append(original_clip)
        
        print(f"✅ Pre-processing completed: {len(processed_clips)} clips ready")
        return processed_clips
    
    def _get_video_cache_key(self, youtube_url):
        """Generate cache key for video based on URL and video metadata"""
        try:
            video_id = self.extract_video_id(youtube_url)
            # Include video ID and current date to handle video updates
            cache_key = f"{video_id}_{time.strftime('%Y%m%d')}"
            return hashlib.md5(cache_key.encode()).hexdigest()
        except:
            return None
    
    def _cache_scene_analysis(self, video_path, analysis_result):
        """Cache scene analysis results for faster re-processing"""
        try:
            # Use file size and modification time as cache key
            stat = os.stat(video_path)
            cache_key = f"{video_path}_{stat.st_size}_{stat.st_mtime}"
            cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
            self.scene_analysis_cache[cache_hash] = analysis_result
            return cache_hash
        except Exception as e:
            logger.warning(f"Failed to cache scene analysis: {e}")
            return None
    
    def _get_cached_scene_analysis(self, video_path):
        """Retrieve cached scene analysis if available"""
        try:
            stat = os.stat(video_path)
            cache_key = f"{video_path}_{stat.st_size}_{stat.st_mtime}"
            cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
            return self.scene_analysis_cache.get(cache_hash)
        except:
            return None
    
    def _convert_clip_with_cache(self, video_path):
        """Convert horizontal video to vertical format with caching"""
        # Generate cache key from file path and modification time
        try:
            cache_key = f"{video_path}_{os.path.getmtime(video_path)}"
            cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
            
            if cache_hash in self.clip_cache:
                cached_path = self.clip_cache[cache_hash]
                if os.path.exists(cached_path):
                    return cached_path
            
            # Convert the clip
            vertical_path = self.create_vertical_clip_from_horizontal(video_path)
            
            # Cache the result
            if vertical_path:
                self.clip_cache[cache_hash] = vertical_path
                
            return vertical_path
        except Exception as e:
            logger.warning(f"Clip conversion with cache failed for {video_path}: {e}")
            return None
        """Convert horizontal video to vertical format with caching"""
        # Generate cache key from file path and modification time
        try:
            cache_key = f"{video_path}_{os.path.getmtime(video_path)}"
            cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
            
            if cache_hash in self.clip_cache:
                cached_path = self.clip_cache[cache_hash]
                if os.path.exists(cached_path):
                    return cached_path
            
            # Convert the clip
            vertical_path = self.create_vertical_clip_from_horizontal(video_path)
            
            # Cache the result
            if vertical_path:
                self.clip_cache[cache_hash] = vertical_path
                
            return vertical_path
        except Exception as e:
            logger.warning(f"Clip conversion with cache failed for {video_path}: {e}")
            return None
    
    def _analyze_content_complexity(self, video_clips):
        """Analyze content complexity to optimize encoding parameters"""
        complexity_metrics = {
            'high_motion_clips': 0,
            'total_resolution': 0,
            'avg_duration': 0,
            'complexity_score': 'medium'
        }
        
        if not video_clips:
            return complexity_metrics
        
        total_duration = sum(clip['duration'] for clip in video_clips)
        complexity_metrics['avg_duration'] = total_duration / len(video_clips)
        
        # Simple heuristics for complexity
        for clip in video_clips:
            # High resolution indicates potentially complex content
            if hasattr(clip, 'resolution'):
                width, height = clip.get('resolution', (1920, 1080))
                complexity_metrics['total_resolution'] += width * height
            
            # Long clips might have more motion
            if clip['duration'] > 30:
                complexity_metrics['high_motion_clips'] += 1
        
        # Determine complexity score
        avg_resolution = complexity_metrics['total_resolution'] / len(video_clips) if video_clips else 0
        high_motion_ratio = complexity_metrics['high_motion_clips'] / len(video_clips)
        
        if avg_resolution > 1920 * 1080 or high_motion_ratio > 0.5:
            complexity_metrics['complexity_score'] = 'high'
        elif avg_resolution < 1280 * 720 and high_motion_ratio < 0.2:
            complexity_metrics['complexity_score'] = 'low'
        
        return complexity_metrics
    
    def _get_adaptive_encoding_params(self, complexity_metrics, base_params):
        """Get encoding parameters adapted to content complexity"""
        adaptive_params = base_params.copy()
        
        complexity = complexity_metrics['complexity_score']
        
        if complexity == 'high':
            # High complexity content needs more bitrate
            current_bitrate = int(adaptive_params['bitrate'].replace('k', ''))
            adaptive_params['bitrate'] = f"{int(current_bitrate * 1.3)}k"
            
            if self.encoding_params['codec'] == 'libx264':
                # Use slower preset for better quality on complex content
                adaptive_params['quality_preset'] = 'medium'
            
        elif complexity == 'low':
            # Low complexity can use lower bitrate and faster preset
            current_bitrate = int(adaptive_params['bitrate'].replace('k', ''))
            adaptive_params['bitrate'] = f"{int(current_bitrate * 0.8)}k"
            
            if self.encoding_params['codec'] == 'libx264':
                adaptive_params['quality_preset'] = 'fast'
        
        return adaptive_params
    
    def _create_compilation_worker(self, selected_clips, video_id, compilation_num, clip_usage):
        """Worker function for parallel compilation creation"""
        try:
            # Periodic cleanup
            if self.compilation_counter % self.cleanup_interval == 0:
                self._cleanup_temp_files()
            
            self.compilation_counter += 1
            
            # Create compilation
            base_output_path = os.path.join(self.output_dir, f"{video_id}_compilation_{compilation_num}")
            variations_result = self.create_all_compilation_variations(
                selected_clips, base_output_path, video_id, compilation_num
            )
            
            # Update clip usage (thread-safe)
            if variations_result['successful_count'] > 0:
                for clip in selected_clips:
                    clip_usage[clip['path']] += 1
            
            return {
                'success': variations_result['successful_count'] > 0,
                'variations_result': variations_result,
                'compilation_num': compilation_num
            }
            
        except Exception as e:
            logger.error(f"Compilation worker {compilation_num} failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'compilation_num': compilation_num
            }
        """Worker function for parallel compilation creation"""
        try:
            # Periodic cleanup
            if self.compilation_counter % self.cleanup_interval == 0:
                self._cleanup_temp_files()
            
            self.compilation_counter += 1
            
            # Create compilation
            base_output_path = os.path.join(self.output_dir, f"{video_id}_compilation_{compilation_num}")
            variations_result = self.create_all_compilation_variations(
                selected_clips, base_output_path, video_id, compilation_num
            )
            
            # Update clip usage (thread-safe)
            if variations_result['successful_count'] > 0:
                for clip in selected_clips:
                    clip_usage[clip['path']] += 1
            
            return {
                'success': variations_result['successful_count'] > 0,
                'variations_result': variations_result,
                'compilation_num': compilation_num
            }
            
        except Exception as e:
            logger.error(f"Compilation worker {compilation_num} failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'compilation_num': compilation_num
            }
    
    def _optimize_audio_processing(self, clip):
        """Optimize audio processing for better performance"""
        try:
            if clip.audio is None:
                return clip
            
            # Check if audio needs normalization or optimization
            audio = clip.audio
            
            # Simple audio optimization: ensure consistent sample rate
            if hasattr(audio, 'fps') and audio.fps != 44100:
                # Resample to standard 44.1kHz if needed
                audio = audio.with_fps(44100)
                clip = clip.with_audio(audio)
            
            return clip
        except Exception as e:
            logger.warning(f"Audio optimization failed: {e}")
            return clip
    
    def _get_optimal_worker_count(self):
        """Calculate optimal worker count based on system resources"""
        cpu_count = multiprocessing.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # Base worker count on CPU and memory
        optimal_workers = min(cpu_count, int(memory_gb / 2))  # 2GB per worker
        
        # Adjust for GPU
        if self.has_gpu:
            try:
                gpu_mem_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                gpu_workers = max(1, int(gpu_mem_gb / 4))  # 4GB per GPU worker
                optimal_workers = min(optimal_workers, gpu_workers)
            except:
                pass
        
        # Safety limits
        return max(1, min(optimal_workers, 6))  # Never exceed 6 workers
    
    def _check_memory_usage(self):
        """Check current memory usage and trigger cleanup if needed"""
        current_memory = psutil.virtual_memory().percent
        if current_memory > self.memory_threshold * 100:
            print(f"⚠️  High memory usage detected: {current_memory:.1f}%")
            print("   - Triggering garbage collection...")
            gc.collect()
            if self.has_gpu:
                torch.cuda.empty_cache()
            return True
        return False
        """Check current memory usage and trigger cleanup if needed"""
        current_memory = psutil.virtual_memory().percent
        if current_memory > self.memory_threshold * 100:
            print(f"⚠️  High memory usage detected: {current_memory:.1f}%")
            print("   - Triggering garbage collection...")
            gc.collect()
            if self.has_gpu:
                torch.cuda.empty_cache()
            return True
        return False
    
    def _adapt_processing_parameters(self, clips_count, total_duration):
        """Adapt processing parameters based on system resources and content complexity"""
        # Get current system resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        available_memory_gb = psutil.virtual_memory().available / (1024**3)
        
        # IMPROVED: Better base parameters - prioritize quality over speed
        params = {
            'max_workers': self.max_workers,
            'chunk_size': 5,
            'quality_preset': 'slow' if not self.has_gpu else 'p3',  # IMPROVED: Better quality presets
            'bitrate': '6000k',  # IMPROVED: Higher default bitrate
            'memory_conservative': False,
            'processing_strategy': 'parallel'
        }
        
        # IMPROVED: Better quality settings for both GPU and CPU
        if self.has_gpu:
            # Better preset for quality on GPU (p1=slowest/best, p7=fastest/worst)
            params['quality_preset'] = 'p2'  # IMPROVED: Higher quality preset
            params['bitrate'] = '8000k'      # IMPROVED: Higher bitrate for GPU encoding
        else:
            # Better preset for quality on CPU
            params['quality_preset'] = 'slow'  # Keep slow for best CPU quality
            params['bitrate'] = '6000k'        # IMPROVED: Higher bitrate for CPU

        # IMPROVED: Less aggressive quality reduction under system load
        if cpu_percent > 85:  # IMPROVED: Higher threshold (was 80)
            print(f"⚠️  High CPU usage ({cpu_percent:.1f}%), reducing parallelism slightly")
            params['max_workers'] = max(1, params['max_workers'] // 2)
            params['processing_strategy'] = 'sequential'
            # IMPROVED: Still maintain decent quality presets
            params['quality_preset'] = 'medium' if not self.has_gpu else 'p4'
            params['bitrate'] = '5000k'  # IMPROVED: Still maintain good bitrate

        if memory_percent > 80:  # IMPROVED: Higher threshold (was 75)
            print(f"⚠️  High memory usage ({memory_percent:.1f}%), enabling conservative mode")
            params['memory_conservative'] = True
            params['chunk_size'] = 2
            params['max_workers'] = max(1, params['max_workers'] // 2)
            # IMPROVED: Don't reduce quality as much
            params['bitrate'] = '4500k'  # IMPROVED: Better bitrate in conservative mode
        
        # IMPROVED: Only use minimal quality on very low memory
        if available_memory_gb < 1.5:  # IMPROVED: Lower threshold (was 2GB)
            print(f"⚠️  Very low available memory ({available_memory_gb:.1f}GB), using minimal resources")
            params['memory_conservative'] = True
            params['chunk_size'] = 1
            params['max_workers'] = 1
            params['processing_strategy'] = 'sequential'
            params['quality_preset'] = 'fast' if not self.has_gpu else 'p5'  # IMPROVED: Better than veryfast
            params['bitrate'] = '4000k'  # IMPROVED: Better bitrate even in minimal mode

        # IMPROVED: Less aggressive quality reduction for content complexity
        if clips_count > 25:  # IMPROVED: Higher threshold (was 20)
            print(f"📊 Large number of clips ({clips_count}), optimizing for batch processing")
            params['chunk_size'] = min(10, clips_count // 4)
        
        if total_duration > 360:  # IMPROVED: Higher threshold (was 300s/5min)
            print(f"📊 Long total duration ({total_duration:.1f}s), slightly optimizing for speed")
            params['quality_preset'] = 'medium' if not self.has_gpu else 'p4'  # IMPROVED: Better quality
            params['bitrate'] = '5500k'  # IMPROVED: Better bitrate for long videos
        
        print(f"🔧 Adaptive parameters: workers={params['max_workers']}, preset={params['quality_preset']}, bitrate={params['bitrate']}")
        return params
    
    def extract_video_id(self, youtube_url):
        """Extract video ID using unified utility if available (preferred)."""
        if unified_extract_video_id:
            try:
                return unified_extract_video_id(youtube_url)
            except Exception:
                pass  # fallback to legacy regex below
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
            r'youtube\.com.*[?&]v=([^&\n?#]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        raise ValueError(f"Could not extract video ID from URL: {youtube_url}")
    
    def _process_clip_for_compilation(self, clip_path, target_resolution=None):
        """
        Load, resize, and process a single clip for compilation.
        If the clip is low resolution, it will be placed on a blurred background
        instead of being upscaled to avoid pixelation.
        """
        try:
            print(f"        📂 Loading clip: {os.path.basename(clip_path)}")
            # Not passing target_resolution here to load with original resolution
            clip = VideoFileClip(clip_path, audio=True)
            print(f"        ✅ Clip loaded successfully")
            print(f"        📊 Original dimensions: {clip.size[0]}x{clip.size[1]}")
            print(f"        ⏱️ Original duration: {clip.duration:.1f}s")
            
            # Defensive check for clip duration
            if clip.duration is None or clip.duration <= 0:
                print(f"        ❌ Skipping clip with invalid duration: {clip_path}")
                return None

            w, h = clip.size
            
            # Use dynamic target resolution if not provided
            if target_resolution is None:
                from .config import TikYouConfig
                config = TikYouConfig()
                config.set_dynamic_resolution(clip_path)
                target_resolution = (config.video.width, config.video.height)
            
            target_w, target_h = target_resolution
            print(f"        🎯 Target resolution: {target_w}x{target_h}")

            # --- IMPROVED: Handle low-resolution clips to avoid pixelation ---
            # If clip is significantly smaller than target, add solid background
            # instead of upscaling. Threshold can be adjusted.
            if w < target_w * 0.9 or h < target_h * 0.9:
                print(f"        📱 Low-res clip detected ({w}x{h}), using solid background approach")
                
                # 1. Create solid background
                print(f"        🎨 Creating solid white background...")
                background = ColorClip(size=(target_w, target_h), color=(255, 255, 255), duration=clip.duration)

                # 2. Resize original clip to fit within 90% of target dimensions, preserving aspect ratio
                clip_max_w = target_w * 0.98
                clip_max_h = target_h * 0.98
                
                if w > clip_max_w or h > clip_max_h:
                    ratio = min(clip_max_w/w, clip_max_h/h)
                    print(f"        📏 Resizing clip by ratio: {ratio:.3f}")
                    clip = clip.resized(ratio)
                else:
                    print(f"        📏 No resize needed, clip fits within bounds")
                
                # 3. Position original clip in the center
                print(f"        📍 Positioning clip at center...")
                
                # Apply rounded corners to the video before positioning
                try:
                    from .video_effects import apply_rounded_corners_simple
                    corner_radius = 20  # Slightly smaller radius for smaller clips
                    clip = apply_rounded_corners_simple(clip, corner_radius)
                    print(f"        ✨ Applied rounded corners (radius: {corner_radius}px)")
                except Exception as e:
                    print(f"        ⚠️  Warning: Could not apply rounded corners: {e}")
                    # Continue without rounded corners if there's an error
                    pass
                
                clip = clip.with_position("center")  # type: ignore[attr-defined]

                # 4. Composite original clip over solid background
                print(f"        🔗 Compositing clip over background...")
                final_clip = CompositeVideoClip([background, clip], size=(target_w, target_h))
                
                # Ensure audio is preserved from original clip
                if final_clip.audio is None and clip.audio is not None:  # type: ignore[attr-defined]
                    print(f"        🔊 Preserving original audio...")
                    final_clip.audio = clip.audio  # type: ignore[attr-defined]
                
                clip = final_clip
                print(f"        ✅ Low-res clip processing completed")
            else:
                # --- Original high-resolution processing ---
                print(f"        📺 High-res clip detected, using standard processing")
                aspect_ratio = w / h
                target_aspect_ratio = target_w / target_h
                print(f"        📐 Aspect ratios - Original: {aspect_ratio:.3f}, Target: {target_aspect_ratio:.3f}")

                if abs(aspect_ratio - target_aspect_ratio) > 0.01:
                    if aspect_ratio > target_aspect_ratio: # Wider than target
                        print(f"        📏 Clip is wider than target, resizing and cropping...")
                        clip = clip.with_effects([vfx.Resize(height=target_h)])
                        # Calculate crop coordinates for center crop using clip.size (width, height)
                        current_w, current_h = clip.size  # type: ignore
                        x1 = int((current_w - target_w) // 2)
                        y1 = int((current_h - target_h) // 2)
                        x2 = x1 + target_w
                        y2 = y1 + target_h
                        clip = clip.with_effects([vfx.Crop(x1, y1, x2, y2)])
                    else: # Taller than target
                        print(f"        📏 Clip is taller than target, resizing and cropping...")
                        clip = clip.with_effects([vfx.Resize(width=target_w)])
                        # Calculate crop coordinates for center crop using clip.size (width, height)
                        current_w, current_h = clip.size  # type: ignore
                        x1 = int((current_w - target_w) // 2)
                        y1 = int((current_h - target_h) // 2)
                        x2 = x1 + target_w
                        y2 = y1 + target_h
                        clip = clip.with_effects([vfx.Crop(x1, y1, x2, y2)])
                else:
                    print(f"        📏 Aspect ratios match, simple resize...")
                    clip = clip.with_effects([vfx.Resize(width=target_w, height=target_h)])
                
                print(f"        ✅ High-res clip processing completed")

            # Ensure clip has audio; if not, add silent audio track
            if clip.audio is None:  # type: ignore[attr-defined]
                print(f"        🔇 Clip has no audio, adding silent track")
                # Generate a silent audio clip of the same duration
                from moviepy import AudioClip
                silent_audio = AudioClip(lambda t: [0, 0], duration=clip.duration, fps=44100)
                clip = clip.with_audio(silent_audio)  # type: ignore[attr-defined]
            else:
                print(f"        🔊 Audio track found and preserved")

            print(f"        ✅ Clip processing completed successfully")
            return clip
        except Exception as e:
            print(f"        ❌ Error processing clip {os.path.basename(clip_path)}: {e}")
            return None

    def process_single_video(self, youtube_url, sensitivity: float = 15, method: str = 'scenedetect'):
        """
        Process a single YouTube video:
        1. Download the video
        2. ✅ Detect and crop pillarboxes
        3. Split into individual scenes if it's a compilation
        4. ✅ Detect and crop pillarboxes on each clip
        5. Return list of video clips with metadata
        
        Args:
            youtube_url: YouTube video URL
            sensitivity: Detection threshold
            method: Scene detection method - 'scenedetect' or 'moviepy'
        """
        self._log(f"Starting video processing for URL: {youtube_url}", "info", "process_single_video")
        self._log(f"Using method: {method}, sensitivity: {sensitivity}", "info", "process_single_video")
        
        log_generation_step(logger, None, "compilation", "youtube_processing_started",
                           youtube_url=youtube_url)

        # Extract video ID
        try:
            video_id = self.extract_video_id(youtube_url)
            logger.info(f"YouTube video ID extracted: {video_id}")
            self._log(f"Extracted video ID: {video_id}", "info", "process_single_video")
        except ValueError as e:
            logger.error(f"Failed to extract YouTube video ID from URL {youtube_url}: {e}")
            self._log(f"Failed to extract video ID: {str(e)}", "error", "process_single_video")
            return []

        # Download the video
        self._log(f"Starting video download for ID: {video_id}", "info", "process_single_video")
        log_generation_step(logger, None, "compilation", "video_download_started",
                           video_id=video_id)
        download_start = time.time()
        download_result = self.processor.download_video(video_id)
        download_duration = time.time() - download_start

        if not download_result or download_result[0] is None:
            log_generation_step(logger, None, "compilation", "video_download_failed",
                               video_id=video_id, duration=download_duration)
            self._log(f"Video download failed for ID: {video_id}", "error", "process_single_video")
            return []

        log_generation_step(logger, None, "compilation", "video_download_completed",
                           video_id=video_id, duration=download_duration)
        self._log(f"Video download completed in {download_duration:.1f}s", "info", "process_single_video")
        
        video_path = download_result[0]
        if os.path.exists(video_path):
            file_size = os.path.getsize(video_path)
            log_file_operation(logger, "downloaded", video_path, file_size=file_size, duration=download_duration)

        # Add a small delay to ensure file is fully written (Windows file locking issue)
        print(f"⏳ Waiting 2 seconds for file to be fully written...")
        time.sleep(2)

        # 2. ✅ Detect and crop pillarboxes on the main video
        self._log("Detecting and cropping pillarboxes from main video", "info", "process_single_video")
        print(f"🔍 Detecting and cropping pillarboxes from main video...")
        cropped_video_path = self.processor.crop_video_if_vertical_with_blur(video_path)
        if cropped_video_path != video_path:
            print(f"✅ Pillarboxes cropped: {video_path} -> {cropped_video_path}")
            self._log("Pillarboxes detected and cropped", "info", "process_single_video")
            video_path = cropped_video_path
        else:
            print(f"ℹ️  No pillarboxes detected or cropping not needed")
            self._log("No pillarboxes detected or cropping not needed", "info", "process_single_video")
        
        # Analyze the video for scenes (with caching)
        self._log("Analyzing video for scenes", "info", "process_single_video")
        print(f"🔍 Analyzing video for scenes...")
        
        # Try to get cached analysis first
        cached_analysis = self._get_cached_scene_analysis(video_path)
        if cached_analysis:
            print(f"✅ Using cached scene analysis")
            self._log("Using cached scene analysis", "info", "process_single_video")
            analysis = cached_analysis
        else:
            print(f"🔄 Performing new scene analysis...")
            analysis = self.processor.analyze_video_scenes(video_path, threshold=sensitivity, method=method)
            # Cache the results
            self._cache_scene_analysis(video_path, analysis)
            self._log("Scene analysis completed and cached", "info", "process_single_video")
        
        is_compilation = analysis['is_compilation']
        scenes = analysis['scenes']
        
        print(f"📊 Analysis Results:")
        print(f"   - Compilation: {'Yes' if is_compilation else 'No'}")
        print(f"   - Scenes found: {len(scenes)}")
        print(f"   - Duration: {analysis['duration']:.1f}s")
        
        self._log(f"Scene analysis complete: {'compilation' if is_compilation else 'single video'} with {len(scenes)} scenes, duration {analysis['duration']:.1f}s", "info", "process_single_video")
        
        video_clips = []
        
        if is_compilation and len(scenes) > 1:
            self._log(f"Splitting compilation into {len(scenes)} scenes", "info", "process_single_video")
            print(f"✂️  Splitting compilation into {len(scenes)} scenes...")
            # Split the video into scenes
            temp_dir, split_videos = self.processor.split_video_from_scenes(video_path, video_id, scenes)
            
            for split_info in split_videos:
                if os.path.exists(split_info['path']):
                    # 5. ✅ Detect and crop pillarboxes on each clip
                    print(f"🔍 Detecting pillarboxes on clip: {os.path.basename(split_info['path'])}")
                    cropped_clip_path = self.processor.crop_video_if_vertical_with_blur(split_info['path'])
                    if cropped_clip_path != split_info['path']:
                        print(f"✅ Clip pillarboxes cropped: {os.path.basename(split_info['path'])} -> {os.path.basename(cropped_clip_path)}")
                        split_info['path'] = cropped_clip_path
                    else:
                        print(f"ℹ️  No pillarboxes detected on clip")
                    
                    orientation = self.creator.get_video_orientation(split_info['path'])
                    video_clips.append({
                        'id': split_info.get('id', f"{video_id}-scene-{split_info.get('scene_number', 'unknown')}"),
                        'path': split_info['path'],
                        'duration': split_info['duration'],
                        'orientation': orientation,
                        'type': 'split',
                        'source_id': video_id
                    })
            
            self._log(f"Successfully split video into {len(video_clips)} clips", "info", "process_single_video")
        else:
            self._log("Using single video without splitting", "info", "process_single_video")
            print(f"📹 Single video, not splitting")
            # Use the whole video as a single clip
            orientation = self.creator.get_video_orientation(video_path)
            video_clips.append({
                'id': video_id,
                'path': video_path,
                'duration': analysis['duration'],
                'orientation': orientation,
                'type': 'single',
                'source_id': video_id
            })
        
        print(f"✅ Processing complete: {len(video_clips)} clips ready")
        self._log(f"Video processing completed successfully: {len(video_clips)} clips ready", "info", "process_single_video")
        return video_clips
    
    def categorize_clips(self, video_clips):
        """Categorize clips by orientation"""
        categorized = {
            'horizontal': [],
            'vertical': [],
            'square': [],
            'unknown': []
        }
        
        for clip in video_clips:
            orientation = clip['orientation']
            categorized[orientation].append(clip)
        
        print(f"📊 Clip Categorization:")
        for orientation, clips in categorized.items():
            total_duration = sum(c['duration'] for c in clips)
            print(f"   - {orientation.capitalize()}: {len(clips)} clips ({total_duration:.1f}s)")
        
        return categorized
    
    def _select_clips_with_constraints(self, all_clips, clip_usage, max_reuse, min_duration, max_duration, max_retries=20):
        """
        Select a random set of clips that meets duration and reuse constraints.
        Prioritizes vertical videos at the start of compilations.
        
        This is a helper function for the main generation logic.
        """
        for _ in range(max_retries):
            # Filter clips that haven't reached max reuse
            available_clips = [c for c in all_clips if clip_usage.get(c['path'], 0) < max_reuse]
            
            # If no clips are available, stop trying
            if not available_clips:
                return None
            
            # Sort clips by orientation priority: vertical first, then horizontal/square
            def get_orientation_priority(clip):
                orientation = clip['orientation']
                if orientation == 'vertical':
                    return 0  # Highest priority
                elif orientation == 'horizontal':
                    return 1  # Lower priority
                elif orientation == 'square':
                    return 1  # Same as horizontal
                else:
                    return 2  # Lowest priority (unknown)
            
            # Sort by orientation priority, then shuffle within each group
            available_clips.sort(key=get_orientation_priority)
            
            # Shuffle within each orientation group to maintain randomness
            vertical_clips = [c for c in available_clips if c['orientation'] == 'vertical']
            horizontal_clips = [c for c in available_clips if c['orientation'] in ['horizontal', 'square']]
            other_clips = [c for c in available_clips if c['orientation'] not in ['vertical', 'horizontal', 'square']]
            
            random.shuffle(vertical_clips)
            random.shuffle(horizontal_clips)
            random.shuffle(other_clips)
            
            # Recombine with vertical clips first
            available_clips = vertical_clips + horizontal_clips + other_clips
            
            selected = []
            total_duration = 0
            
            for clip in available_clips:
                # Add clip if it doesn't exceed max_duration
                if total_duration + clip['duration'] <= max_duration:
                    selected.append(clip)
                    total_duration += clip['duration']

            # Check if the selection is valid
            if total_duration >= min_duration:
                # Log the selection order for transparency
                vertical_count = len([c for c in selected if c['orientation'] == 'vertical'])
                horizontal_count = len([c for c in selected if c['orientation'] in ['horizontal', 'square']])
                
                if len(selected) > 0:
                    first_clip_orientation = selected[0]['orientation']
                    print(f"📊 Clip selection prioritized: {vertical_count} vertical, {horizontal_count} horizontal clips")
                    print(f"🎯 First clip will be: {first_clip_orientation}")
                
                return selected
        
        return None

    def create_vertical_clip_from_horizontal(self, video_path):
        """Convert horizontal video to vertical format with optimized encoding"""
        output_path = None  # Initialize to avoid scope issues
        try:
            # Use the optimized temp directory
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(self.temp_dir, f"{video_name}_vertical.mp4")
            
            # If vertical version already exists, return its path
            if os.path.exists(output_path):
                return output_path
            
            # Create a simplified vertical video without text
            W, H = 1080, 1920
            BACKGROUND_COLOR = (255, 255, 255)

            video_clip = VideoFileClip(video_path, audio=True)
            original_duration = video_clip.duration
            
            # Enhanced bitrates for better quality based on source
            if video_clip.w * video_clip.h > 1920 * 1080:  # High resolution source
                bitrate = '8000k'  # Increased significantly
                audio_bitrate = '256k'
            elif original_duration > 60:  # Long video
                bitrate = '6000k'  # Increased
                audio_bitrate = '192k'
            else:  # Standard quality
                bitrate = '5000k'  # Increased
                audio_bitrate = '192k'
            
            video_clip = video_clip.with_effects([vfx.Resize(width=W)])
            background = ColorClip(size=(W, H), color=BACKGROUND_COLOR, duration=video_clip.duration)
            
            # Apply rounded corners to the video before positioning
            try:
                from .video_effects import apply_rounded_corners_simple
                corner_radius = 30  # Configurable corner radius
                video_clip = apply_rounded_corners_simple(video_clip, corner_radius)
                print(f"        ✨ Applied rounded corners (radius: {corner_radius}px)")
            except Exception as e:
                print(f"        ⚠️  Warning: Could not apply rounded corners: {e}")
                # Continue without rounded corners if there's an error
                pass
            
            # Position video in the middle area of the frame
            video_y_position = 650
            video_clip = video_clip.with_position(('center', video_y_position))  # type: ignore[attr-defined]

            final_clip = CompositeVideoClip([background, video_clip], size=(W, H))
            final_clip.duration = video_clip.duration
            final_clip.audio = video_clip.audio

            # Use optimized encoding parameters
            encoding_params = {
                'codec': self.encoding_params['codec'],
                'audio_codec': 'aac',
                'threads': self.max_workers,
                'fps': 30,
                'bitrate': bitrate,
                'audio_bitrate': audio_bitrate,
                'write_logfile': False,
                'logger': None,
                'ffmpeg_params': self.encoding_params['ffmpeg_params'] + [
                    '-avoid_negative_ts', 'make_zero',
                    '-fflags', '+genpts',
                    '-start_at_zero',
                    '-pix_fmt', 'yuv420p',
                    '-profile:v', 'high',
                    '-level', '4.1'
                ]
            }

            # Add quality settings based on codec
            if self.encoding_params['codec'] == 'h264_nvenc':
                print(f"🎬 Converting {video_name}: GPU NVENC, bitrate={bitrate}")
            else:
                encoding_params['ffmpeg_params'].extend([
                    '-crf', '20',  # Better quality
                    '-maxrate', bitrate,
                    '-bufsize', str(int(bitrate.replace('k', '')) * 2) + 'k'
                ])
                print(f"🎬 Converting {video_name}: CPU x264, crf=20, bitrate={bitrate}")

            final_clip.write_videofile(output_path, **encoding_params)
            
            video_clip.close()
            final_clip.close()

            # Verify output file was created successfully
            if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
                print(f"⚠️  Warning: Output file seems invalid for {video_name}")
                return None

            return output_path
        except Exception as e:
            print(f"❌ Error converting horizontal video: {e}")
            # Clean up partial file
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            return None
    
    def _fits_916_aspect_ratio(self, video_path, threshold=0.1):
        """Check if video fits 9:16 aspect ratio within threshold"""
        try:
            video = VideoFileClip(video_path)
            aspect_ratio = video.w / video.h
            target_ratio = 9 / 16  # 0.5625
            
            # Check if within threshold
            ratio_difference = abs(aspect_ratio - target_ratio)
            fits = ratio_difference <= threshold
            
            video.close()
            return fits, aspect_ratio
            
        except Exception as e:
            print(f"❌ Error checking aspect ratio for {video_path}: {e}")
            return False, 0
    
    def create_no_background_clip(self, video_path, target_resolution=(1080, 1920)):
        """Create a no-background version of the clip - just video or blurred pillarbox"""
        print(f"   🔧 Creating no-background clip from: {os.path.basename(video_path)}")
        output_path = None
        try:
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(self.temp_dir, f"{video_name}_no_bg.mp4")
            
            # If no-background version already exists, return its path
            if os.path.exists(output_path):
                return output_path
            
            target_w, target_h = target_resolution
            video_clip = VideoFileClip(video_path, audio=True)
            
            # Check if video fits 9:16 aspect ratio
            threshold = getattr(self.request, 'blurredPillarboxThreshold', 0.1) if self.request else 0.1
            fits_916, current_ratio = self._fits_916_aspect_ratio(video_path, threshold)
            
            if fits_916:
                # Video fits 9:16, just resize it to fill the frame
                print(f"   ✅ Video fits 9:16 aspect ratio, using full frame")
                final_clip = video_clip.resized((target_w, target_h))
            else:
                # Video doesn't fit, create blurred pillarbox
                print(f"   🔄 Video aspect ratio {current_ratio:.3f} doesn't fit 9:16, creating blurred pillarbox")
                
                # Scale video to fit height while maintaining aspect ratio
                # Ensure the main video takes up at least 85% of the frame height
                min_scale_factor = (target_h * 0.85) / video_clip.h
                height_scale_factor = target_h / video_clip.h
                scale_factor = max(min_scale_factor, height_scale_factor)
                
                scaled_w = int(video_clip.w * scale_factor)
                scaled_h = int(video_clip.h * scale_factor)
                scaled_clip = video_clip.resized((scaled_w, scaled_h))
                
                # Create blurred background version
                # Scale the original to fill the entire frame (will be cropped)
                bg_scale_factor = target_w / video_clip.w
                bg_clip = video_clip.resized((target_w, int(video_clip.h * bg_scale_factor)))
                
                # Apply blur to background using resize method (v2 compatible)
                # GaussianBlur is not available in MoviePy v2, so we use resize blur
                print(f"   🔄 Applying blur effect using resize method")
                blur_factor = 0.15  # Scale down to 15% then back up for better quality
                bg_w, bg_h = bg_clip.size  # type: ignore
                temp_w, temp_h = max(1, int(bg_w * blur_factor)), max(1, int(bg_h * blur_factor))
                bg_clip = bg_clip.with_effects([vfx.Resize(width=temp_w, height=temp_h)]).with_effects([vfx.Resize(width=target_w, height=target_h)])
                print(f"   ✅ Applied resize blur effect to background")
                
                # Center the background clip vertically
                bg_clip = bg_clip.with_position("center")  # type: ignore
                
                # Position the main video in center
                main_clip = scaled_clip.with_position("center")  # type: ignore
                
                # Composite: blurred background + main video
                final_clip = CompositeVideoClip([bg_clip, main_clip], size=(target_w, target_h))
            
            final_clip = final_clip.with_duration(video_clip.duration)
            if video_clip.audio is not None:
                final_clip = final_clip.with_audio(video_clip.audio)
            
            # Enhanced bitrates for better quality
            if video_clip.w * video_clip.h > 1920 * 1080:
                bitrate = '8000k'
                audio_bitrate = '256k'
            elif video_clip.duration > 60:
                bitrate = '6000k'
                audio_bitrate = '192k'
            else:
                bitrate = '5000k'
                audio_bitrate = '192k'
            
            # Use optimized encoding parameters
            codec = 'h264_nvenc' if (hasattr(self, 'has_gpu') and self.has_gpu) else 'libx264'
            ffmpeg_params = [
                '-movflags', 'faststart',
                '-pix_fmt', 'yuv420p',
                '-profile:v', 'high',
                '-level', '4.1',
            ]
            
            preset = 'p3' if (hasattr(self, 'has_gpu') and self.has_gpu) else 'slow'
            
            # Create unique temp audio file
            temp_audio_file = os.path.join(self.temp_dir, f"{uuid.uuid4().hex}_temp_audio.wav")
            
            final_clip.write_videofile(
                output_path,
                codec=codec,
                audio_codec='aac',
                bitrate=bitrate,
                audio_bitrate=audio_bitrate,
                temp_audiofile=temp_audio_file,
                remove_temp=True,
                fps=30,
                preset=preset,
                threads=self.max_workers,
                logger=None,
                ffmpeg_params=ffmpeg_params,
            )
            
            # Clean up
            video_clip.close()
            final_clip.close()
            
            # Cleanup temp audio file if it still exists
            if os.path.exists(temp_audio_file):
                try:
                    os.remove(temp_audio_file)
                except:
                    pass
            
            # Validate output
            if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
                print(f"⚠️  Warning: No-background output file seems invalid for {video_name}")
                return None
            
            return output_path
            
        except Exception as e:
            print(f"❌ Error creating no-background clip: {e}")
            # Clean up partial file
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            return None
    
    def create_single_compilation(self, selected_clips, output_path, compilation_num):
        """Create one compilation from a list of selected clips"""
        print(f"\n🎬 Creating compilation #{compilation_num}...")
        print(f"   📊 Input: {len(selected_clips)} clips selected")
        print(f"   🎯 Target resolution: 1080x1920")
        print(f"   📁 Output path: {output_path}")
        
        # Generate title for this compilation if title generator is available
        title = None
        if self.title_enabled and self.title_generator:
            try:
                print(f"   🎬 Generating title...")
                title = self.title_generator.generate_title_for_video(
                    video_context="cat videos", 
                    style=random.choice(["trending", "funny", "cute", "epic"])
                )
                print(f"   ✅ Generated title: '{title}'")
            except Exception as e:
                print(f"   ⚠️ Failed to generate title: {e}")
        else:
            print(f"   ⏭️ Title generation skipped (not available)")
        
        final_clips = []
        target_resolution = (1080, 1920)
        
        print(f"   🔄 Processing {len(selected_clips)} clips for compilation...")
        with tqdm(total=len(selected_clips), desc=f"     Processing clips") as pbar:
            for i, clip_info in enumerate(selected_clips):
                print(f"     📹 Processing clip {i+1}/{len(selected_clips)}: {os.path.basename(clip_info['path'])}")
                print(f"        - Duration: {clip_info['duration']:.1f}s")
                print(f"        - Orientation: {clip_info['orientation']}")
                
                processed_clip = self._process_clip_for_compilation(clip_info['path'], target_resolution)
                if processed_clip:
                    final_clips.append(processed_clip)
                    print(f"        ✅ Clip processed successfully")
                else:
                    print(f"        ❌ Failed to process clip")
                pbar.update(1)

        if not final_clips:
            print(f"   ❌ No valid clips found for compilation #{compilation_num}, skipping.")
            return None
        
        print(f"   ✅ Successfully processed {len(final_clips)} clips")
        print(f"   🔗 Concatenating clips into final compilation...")

        # Concatenate clips with timing fixes
        try:
            print(f"     📹 Starting clip concatenation...")

            # FIX: Ensure all clips start at time 0 to prevent timing offsets
            for i, clip in enumerate(final_clips):
                if hasattr(clip, 'start') and clip.start != 0:
                    print(f"        🔧 Fixing timing for clip {i+1}: start={clip.start} -> 0")
                    clip = clip.with_start(0)
                    final_clips[i] = clip

            final_compilation = concatenate_videoclips(final_clips, method="compose")

            # FIX: Ensure final compilation starts at zero
            if hasattr(final_compilation, 'start') and final_compilation.start != 0:
                print(f"        🔧 Fixing final compilation timing: start={final_compilation.start} -> 0")
                final_compilation = final_compilation.with_start(0)

            print(f"     ✅ Concatenation completed successfully")
            print(f"     📊 Final compilation duration: {final_compilation.duration:.1f}s")

            # Add title overlay if available
            if title and self.title_enabled:
                try:
                    print(f"     🎬 Adding title overlay: '{title}'")
                    # Use a simple text overlay approach instead of Playwright to avoid async issues
                    
                    # Create title clip directly with MoviePy TextClip
                    print(f"        📝 Creating text clip...")

                    # Font fallback mechanism - use centralized font choices
                    font_choices = FONT_CHOICES
                    title_clip = None

                    for font_choice in font_choices:
                        try:
                            title_clip = TextClip(
                                text=title,
                                font_size=48,
                                font=font_choice,  # Try different fonts
                                color='#00010a',
                                stroke_color='black',
                                stroke_width=1
                            ).with_duration(final_compilation.duration)
                            print(f"        ✅ Successfully created title clip with font: {font_choice or 'default'}")
                            break  # Success - exit the loop
                        except Exception as font_error:
                            print(f"        ⚠️ Failed to create title clip with font '{font_choice or 'default'}': {font_error}")
                            continue  # Try next font

                    # If all fonts failed, raise an error
                    if title_clip is None:
                        raise Exception("Failed to create title clip with any available font")
                    
                    # Position title at the top center
                    # 130 is the y-coordinate (in pixels) from the top of the video frame.
                    # It positions the title 130 pixels down from the top, centered horizontally.
                    print(f"        📍 Positioning title at center, y=130...")
                    title_clip = title_clip.with_position(('center', 130))
                    
                    # Composite title over final compilation
                    print(f"        🔗 Compositing title over compilation...")
                    final_compilation = CompositeVideoClip([final_compilation, title_clip])
                    
                    print(f"        ✅ Title overlay added successfully")
                    
                except Exception as e:
                    print(f"        ❌ Failed to add title overlay: {e}")
            else:
                print(f"     ⏭️ No title overlay (title not available or disabled)")
                    
        except Exception as e:
            print(f"   ❌ Error concatenating clips for compilation #{compilation_num}: {e}")
            # Cleanup memory
            for clip in final_clips:
                clip.close()
            gc.collect()
            return None

        # Write to file with progress bar and specific codecs
        print(f"   💾 Starting video file writing...")
        print(f"      📁 Output file: {output_path}")
        print(f"      📊 Compilation duration: {final_compilation.duration:.1f}s")
        
        # Check system resources before starting encoding
        current_memory = psutil.virtual_memory().percent
        available_disk = psutil.disk_usage(os.path.dirname(output_path)).free / (1024**3)  # GB
        print(f"      💻 System resources before encoding:")
        print(f"         - Memory usage: {current_memory:.1f}%")
        print(f"         - Available disk space: {available_disk:.1f}GB")
        
        if current_memory > 90:
            print(f"         ⚠️ High memory usage detected!")
        if available_disk < 1.0:
            print(f"         ⚠️ Low disk space detected!")
        
        try:
            # Use a unique temporary audio file name to avoid conflicts when multiple
            # compilations with the same `compilation_num` are created rapidly (e.g.,
            # a normal compilation followed by a TTS version). Re-using the same
            # temp file name can lead to race conditions where the file is still
            # locked or partially removed, causing MoviePy/FFmpeg to crash with
            # errors like "'NoneType' object has no attribute 'stdout'". A UUID
            # guarantees uniqueness for every call.
            unique_audio_temp = f"temp-audio-{uuid.uuid4().hex}.m4a"

            # Get adaptive parameters for encoding
            print(f"      🔧 Getting adaptive encoding parameters...")
            adaptive_params = self._adapt_processing_parameters(len(final_clips), final_compilation.duration)
            
            # Use GPU encoding if available, otherwise use CPU with quality flags
            codec = self.encoding_params['codec']
            ffmpeg_params = [
                '-movflags', 'faststart',
                '-pix_fmt', 'yuv420p',
                '-profile:v', 'high',
                '-level', '4.1',
                '-avoid_negative_ts', 'make_zero',  # FIX: Prevent negative timestamps
                '-fflags', '+genpts',  # FIX: Generate presentation timestamps
                '-start_at_zero',  # FIX: Ensure output starts at zero
            ] + self.encoding_params['ffmpeg_params']
            
            # Log final compilation encoding mode
            codec_name = self.encoding_params['codec']
            print(f"      🎬 Encoding configuration:")
            print(f"         - Codec: {codec_name}")
            print(f"         - Preset: {adaptive_params['quality_preset']}")
            print(f"         - Bitrate: {adaptive_params['bitrate']}")
            print(f"         - Workers: {self.max_workers}")
            
            # Add CPU-specific quality flags if not using GPU
            if codec == 'libx264':
                ffmpeg_params.extend([
                    '-crf', '20',  # Better quality
                    '-maxrate', adaptive_params['bitrate'],
                    '-bufsize', str(int(adaptive_params['bitrate'].replace('k', '')) * 2) + 'k'
                ])
                print(f"         - CPU Options: crf=20, maxrate={adaptive_params['bitrate']}")
            else:
                print(f"         - GPU Options: Using hardware acceleration")

            print(f"      🎬 Starting video encoding...")
            print(f"         - This may take several minutes depending on video length and system performance")
            print(f"         - Progress will be shown below:")
            
            # Add encoding start timestamp for progress tracking
            encoding_start_time = time.time()
            
            def encoding_progress_callback(current_frame, total_frames):
                if total_frames > 0:
                    progress = (current_frame / total_frames) * 100
                    elapsed_time = time.time() - encoding_start_time
                    if progress > 0:
                        estimated_total = elapsed_time / (progress / 100)
                        remaining_time = estimated_total - elapsed_time
                        print(f"         📊 Encoding progress: {progress:.1f}% ({current_frame}/{total_frames} frames) - ETA: {remaining_time:.0f}s")
            
            final_compilation.write_videofile(
                str(output_path),
                codec=codec,
                audio_codec='aac',
                temp_audiofile=unique_audio_temp,
                remove_temp=True,
                fps=30,
                preset=adaptive_params['quality_preset'],
                threads=self.max_workers,
                logger="bar",
                bitrate=adaptive_params['bitrate'],
                ffmpeg_params=ffmpeg_params,
            )
            
        except Exception as e:
            print(f"   ❌ Error writing video file for compilation #{compilation_num}: {e}")
            print(f"      💡 This could be due to:")
            print(f"         - Insufficient disk space")
            print(f"         - FFmpeg encoding issues")
            print(f"         - Memory constraints")
            print(f"         - File permission issues")
            return None
        finally:
            # Cleanup memory
            print(f"      🧹 Cleaning up memory...")
            final_compilation.close()
            for clip in final_clips:
                clip.close()
            gc.collect()
            if self.has_gpu:
                torch.cuda.empty_cache()
            print(f"      ✅ Memory cleanup completed")
        
        # Verify the output file was created successfully
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # Convert to MB
            print(f"   ✅ Successfully created compilation: {os.path.basename(output_path)}")
            print(f"      📦 File size: {file_size:.1f}MB")
            print(f"      📁 Full path: {output_path}")
        else:
            print(f"   ❌ Output file was not created: {output_path}")
            return None
            
        return output_path
    
    def create_no_background_compilation(self, selected_clips, output_path, compilation_num):
        """Create a compilation using no-background clips (no white background, no text overlay)"""
        print(f"\n🎬 Creating no-background compilation #{compilation_num}...")
        print(f"   📊 Input: {len(selected_clips)} clips selected")
        print(f"   🎯 Target resolution: 1080x1920")
        print(f"   📁 Output path: {output_path}")
        
        # Track processing start time
        start_time = time.time()
        final_clips = []
        final_compilation = None
        
        try:
            # Convert each clip to no-background format
            for i, clip_info in enumerate(selected_clips):
                clip_name = os.path.basename(clip_info['path'])
                
                print(f"   📽️  Processing clip {i+1}/{len(selected_clips)}: {clip_name}")
                
                # Convert to no-background format
                no_bg_path = self.create_no_background_clip(clip_info['path'])
                if not no_bg_path:
                    print(f"      ❌ Failed to create no-background version of {clip_name}")
                    continue
                
                print(f"      ✅ No-background clip created: {os.path.basename(no_bg_path)}")
                
                # Load the no-background clip
                try:
                    clip = VideoFileClip(no_bg_path, audio=True)
                    # Ensure correct duration
                    if hasattr(clip_info, 'duration'):
                        clip = clip.with_duration(clip_info['duration'])
                    final_clips.append(clip)
                except Exception as e:
                    print(f"      ❌ Error loading no-background clip: {e}")
                    continue
            
            if not final_clips:
                print(f"   ❌ No valid clips for compilation")
                return None
            
            print(f"   📋 Successfully processed {len(final_clips)}/{len(selected_clips)} clips")
            
            # Create the final compilation by concatenating clips
            print(f"   🔗 Concatenating clips...")
            final_compilation = concatenate_videoclips(final_clips, method="compose")
            
            # Log compilation info
            print(f"   ✅ Compilation created successfully!")
            print(f"      📁 Output file: {output_path}")
            print(f"      📊 Compilation duration: {final_compilation.duration:.1f}s")
            
            # Check system resources before encoding
            current_memory = psutil.virtual_memory().percent
            available_disk = psutil.disk_usage(os.path.dirname(output_path)).free / (1024**3)  # GB
            print(f"      💻 System resources before encoding:")
            print(f"         - Memory usage: {current_memory:.1f}%")
            print(f"         - Available disk space: {available_disk:.1f}GB")
            
            if current_memory > 90:
                print(f"         ⚠️ High memory usage detected!")
            if available_disk < 1.0:
                print(f"         ⚠️ Low disk space detected!")
            
            # Encoding parameters
            unique_audio_temp = f"temp-audio-{uuid.uuid4().hex}.m4a"
            adaptive_params = self._adapt_processing_parameters(len(final_clips), final_compilation.duration)
            
            # Use the same codec determination as normal compilation
            codec = self.encoding_params['codec']
            ffmpeg_params = [
                '-movflags', 'faststart',
                '-pix_fmt', 'yuv420p',
            ] + self.encoding_params['ffmpeg_params']
            
            # Add CPU-specific quality flags if not using GPU
            if codec == 'libx264':
                ffmpeg_params.extend([
                    '-crf', '20',  # Better quality
                    '-maxrate', adaptive_params['bitrate'],
                    '-bufsize', str(int(adaptive_params['bitrate'].replace('k', '')) * 2) + 'k'
                ])
            
            print(f"      🎬 Starting video encoding...")
            print(f"         - Codec: {codec}")
            print(f"         - Preset: {adaptive_params['quality_preset']}")
            print(f"         - Bitrate: {adaptive_params['bitrate']}")
            
            final_compilation.write_videofile(
                output_path,
                codec=codec,
                audio_codec='aac',
                bitrate=adaptive_params['bitrate'],
                audio_bitrate=adaptive_params.get('audio_bitrate', '192k'),
                temp_audiofile=unique_audio_temp,
                remove_temp=True,
                fps=30,
                preset=adaptive_params['quality_preset'],
                threads=self.max_workers,
                logger="bar",
                ffmpeg_params=ffmpeg_params,
            )
            
            processing_time = time.time() - start_time
            print(f"      ⏱️ Processing time: {processing_time:.1f}s")
            print(f"      ✅ No-background compilation encoding completed!")
            
        except Exception as e:
            print(f"   ❌ Error writing no-background compilation #{compilation_num}: {e}")
            print(f"      💡 This could be due to:")
            print(f"         - Insufficient disk space")
            print(f"         - FFmpeg encoding issues") 
            print(f"         - Memory constraints")
            print(f"         - File permission issues")
            return None
        finally:
            # Cleanup memory
            print(f"      🧹 Cleaning up memory...")
            if final_compilation is not None:
                final_compilation.close()
            for clip in final_clips:
                clip.close()
            gc.collect()
            if self.has_gpu:
                torch.cuda.empty_cache()
            print(f"      ✅ Memory cleanup completed")
        
        # Verify the output file was created successfully
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # Convert to MB
            print(f"   ✅ Successfully created no-background compilation: {os.path.basename(output_path)}")
            print(f"      📦 File size: {file_size:.1f}MB")
            print(f"      📁 Full path: {output_path}")
        else:
            print(f"   ❌ No-background output file was not created: {output_path}")
            return None
            
        return output_path
    
    def create_all_compilation_variations(self, selected_clips, base_output_path, video_id, compilation_num):
        """
        Create all variations of a compilation:
        1. Normal compilation (with white background)
        2. TTS intro compilation (with white background + TTS intro)
        3. No-background compilation (no white background, pure video/blurred pillarbox)
        
        Args:
            selected_clips (list): List of selected video clips
            base_output_path (str): Base output path (without extension)
            video_id (str): Video ID for naming
            compilation_num (int): Compilation number
            
        Returns:
            dict: Dictionary with results for each variation
        """
        results = {
            'normal': None,
            'tts': None,
            'no_background': None,
            'successful_count': 0,
            'total_count': 0
        }
        
        print(f"\n🎬 Creating all variations for compilation {compilation_num}")
        print(f"   📊 Selected clips: {len(selected_clips)}")
        print(f"   ⏱️ Total duration: {sum(c['duration'] for c in selected_clips):.1f}s")
        print(f"   📁 Base output path: {base_output_path}")
        
        # Check system resources at the start
        current_memory = psutil.virtual_memory().percent
        available_disk = psutil.disk_usage(os.path.dirname(base_output_path)).free / (1024**3)  # GB
        print(f"   💻 System resources:")
        print(f"      - Memory usage: {current_memory:.1f}%")
        print(f"      - Available disk space: {available_disk:.1f}GB")
        
        # 1. Create Normal Compilation
        print(f"\n   📹 Variation 1/3: Normal Compilation")
        normal_path = f"{base_output_path}_normal.mp4"
        results['total_count'] += 1
        
        try:
            print(f"   🎬 Starting normal compilation creation...")
            normal_result = self.create_single_compilation(selected_clips, normal_path, compilation_num)
            if normal_result:
                results['normal'] = normal_result
                results['successful_count'] += 1
                print(f"   ✅ Normal compilation created: {os.path.basename(normal_path)}")
            else:
                print(f"   ❌ Normal compilation failed")
        except Exception as e:
            print(f"   ❌ Normal compilation error: {e}")
            print(f"      💡 This could be due to:")
            print(f"         - Memory constraints")
            print(f"         - FFmpeg encoding issues")
            print(f"         - File system problems")
        
        # 2. Create TTS Intro Compilation (if enabled)
        if self.tts_enabled and self.tts_generator:
            print(f"\n   🎙️ Variation 2/3: TTS Intro Compilation")
            tts_path = f"{base_output_path}_tts.mp4"
            results['total_count'] += 1
            
            try:
                print(f"   🎬 Starting TTS compilation creation...")
                tts_result = self.tts_generator.create_tts_compilation(selected_clips, tts_path, compilation_num, generator=self)
                if tts_result:
                    results['tts'] = tts_result
                    results['successful_count'] += 1
                    print(f"   ✅ TTS compilation created: {os.path.basename(tts_path)}")
                else:
                    print(f"   ❌ TTS compilation failed")
            except Exception as e:
                print(f"   ❌ TTS compilation error: {e}")
                print(f"      💡 This could be due to:")
                print(f"         - TTS service issues")
                print(f"         - Memory constraints")
                print(f"         - FFmpeg encoding issues")
        else:
            print(f"\n   ⏭️ Variation 2/3: TTS Intro Compilation (SKIPPED - not available)")
        
        # 3. Create No-Background Compilation (if enabled)
        should_generate_no_bg = getattr(self.request, 'generateNoBackground', True) if self.request else True
        print(f"   🔍 Debug: request={self.request}, should_generate_no_bg={should_generate_no_bg}")
        if should_generate_no_bg:
            print(f"\n   🎯 Variation 3/3: No-Background Compilation")
            no_bg_path = f"{base_output_path}_no_bg.mp4"
            results['total_count'] += 1
            
            try:
                print(f"   🎬 Starting no-background compilation creation...")
                no_bg_result = self.create_no_background_compilation(selected_clips, no_bg_path, compilation_num)
                if no_bg_result:
                    results['no_background'] = no_bg_result
                    results['successful_count'] += 1
                    print(f"   ✅ No-background compilation created: {os.path.basename(no_bg_path)}")
                else:
                    print(f"   ❌ No-background compilation failed")
            except Exception as e:
                print(f"   ❌ No-background compilation error: {e}")
                print(f"      💡 This could be due to:")
                print(f"         - Aspect ratio detection issues")
                print(f"         - Video processing problems")
                print(f"         - Memory constraints")
                print(f"         - FFmpeg encoding issues")
        else:
            print(f"\n   ⏭️ Variation 3/3: No-Background Compilation (SKIPPED - disabled in request)")
        
        print(f"\n   📊 Compilation {compilation_num} Summary:")
        print(f"      ✅ Successful variations: {results['successful_count']}/{results['total_count']}")
        
        # Final system resource check
        final_memory = psutil.virtual_memory().percent
        final_disk = psutil.disk_usage(os.path.dirname(base_output_path)).free / (1024**3)  # GB
        print(f"   💻 Final system resources:")
        print(f"      - Memory usage: {final_memory:.1f}% (was {current_memory:.1f}%)")
        print(f"      - Available disk space: {final_disk:.1f}GB (was {available_disk:.1f}GB)")
        
        return results
    
    def generate_tikyou_videos(self, youtube_url, num_compilations=None, min_duration=20, max_duration=40, max_reuse=3, video_clips=None):
        """
        Generate a number of vertical "brainrot" videos from a single YouTube URL.
        
        Args:
            youtube_url (str): The URL of the YouTube video.
            num_compilations (int, optional): The number of compilations to create. 
                                              If None, generates as many as possible. Defaults to None.
            min_duration (int): The minimum duration of each compilation in seconds.
            max_duration (int): The maximum duration of each compilation in seconds.
            max_reuse (int): The maximum number of times a single clip can be reused.
            video_clips (list, optional): Pre-processed video clips. If provided, skips video download and processing.
        """
        start_time = time.time()
        
        self._log(f"Starting compilation generation: {num_compilations or 'unlimited'} videos, duration {min_duration}-{max_duration}s, max_reuse {max_reuse}", "info", "generate_tikyou_videos")
        
        # Performance tracking
        performance_stats = {
            'start_time': start_time,
            'download_time': 0,
            'processing_time': 0,
            'generation_time': 0,
            'total_clips_processed': 0,
            'successful_compilations': 0,
            'failed_compilations': 0,
            'peak_memory_usage': self.initial_memory,
            'total_output_size': 0,
            # New stats for variations
            'normal_variations': 0,
            'tts_variations': 0,
            'total_variations': 0
        }
        
        print(f"🧠 Starting Enhanced Brainrot Video Generation")
        print(f"   📊 Target: {num_compilations if num_compilations else 'Maximum possible'} compilations")
        print(f"   🎬 2 variations per compilation: Normal + TTS")
        print(f"   ⏱️  Duration range: {min_duration}-{max_duration}s")
        print(f"   🔄 Max reuse: {max_reuse}x per clip")
        
        # Show what generators are available
        available_variations = ["Normal"]
        if self.tts_enabled:
            available_variations.append("TTS Intro")
        print(f"   ✅ Available variations: {', '.join(available_variations)}")
        self._log(f"Available variations: {', '.join(available_variations)}", "info", "generate_tikyou_videos")
        
        # 1. Process the video and get clips (or use pre-processed clips)
        print(f"\n{'='*50}")
        print(f"PHASE 1: Video Processing")
        print(f"{'='*50}")
        
        phase_start = time.time()
        if video_clips is None:
            # Only download and process if clips weren't provided
            self._log("No pre-processed clips provided, downloading and processing video", "info", "generate_tikyou_videos")
            print(f"📥 No pre-processed clips provided, downloading and processing video...")
            video_clips = self.process_single_video(youtube_url)
            performance_stats['download_time'] = time.time() - phase_start
        else:
            self._log(f"Using {len(video_clips)} pre-processed video clips", "info", "generate_tikyou_videos")
            print(f"✅ Using {len(video_clips)} pre-processed video clips")
            performance_stats['download_time'] = 0  # No download time since clips were provided
        
        if not video_clips:
            self._log("No video clips were processed, exiting", "error", "generate_tikyou_videos")
            print("❌ No video clips were processed. Exiting.")
            return performance_stats

        # 2. Categorize clips and prepare for generation with pre-processing
        print(f"\n{'='*50}")
        print(f"PHASE 2: Clip Analysis, Categorization & Pre-processing")
        print(f"{'='*50}")
        
        phase_start = time.time()
        categorized_clips = self.categorize_clips(video_clips)
        
        # Analyze content complexity for adaptive encoding
        print(f"🧠 Analyzing content complexity for optimal encoding...")
        complexity_metrics = self._analyze_content_complexity(video_clips)
        print(f"   - Content complexity: {complexity_metrics['complexity_score']}")
        print(f"   - Average clip duration: {complexity_metrics['avg_duration']:.1f}s")
        print(f"   - High motion clips: {complexity_metrics['high_motion_clips']}")
        
        # Pre-process clips in parallel batches for better performance
        print(f"🚀 Starting parallel clip pre-processing...")
        all_clips_raw = [clip for clips in categorized_clips.values() for clip in clips if clip['duration'] >= 3.0]
        
        # Pre-process clips that need conversion
        all_clips = self._preprocess_clips_batch(all_clips_raw)
        
        performance_stats['total_clips_processed'] = len(all_clips)
        performance_stats['processing_time'] = time.time() - phase_start
        performance_stats['complexity_metrics'] = complexity_metrics
        
        self._log(f"Categorized and pre-processed {len(all_clips)} clips (>=3s duration)", "info", "generate_tikyou_videos")
        
        if not all_clips:
            self._log("No clips long enough to be used in compilations", "error", "generate_tikyou_videos")
            print("❌ No clips long enough to be used in compilations.")
            return performance_stats
            
        clip_usage = {clip['path']: 0 for clip in all_clips}
        video_id = self.extract_video_id(youtube_url)
        created_count = 0

        # 3. Generate videos with performance tracking
        print(f"\n{'='*50}")
        print(f"PHASE 3: Video Generation")
        print(f"{'='*50}")
        
        generation_start = time.time()

        if num_compilations:
            self._log(f"Generating {num_compilations} compilation sets", "info", "generate_tikyou_videos")
            print(f"🎯 Generating {num_compilations} compilation sets (3 variations each)...")
            
            for i in range(num_compilations):
                compilation_start = time.time()
                print(f"\n{'='*80}")
                print(f"COMPILATION SET {i+1}/{num_compilations}")
                print(f"{'='*80}")
                
                self._log(f"Starting compilation set {i+1}/{num_compilations}", "info", "generate_tikyou_videos")
                
                # Update peak memory usage
                current_memory = psutil.virtual_memory().percent
                performance_stats['peak_memory_usage'] = max(performance_stats['peak_memory_usage'], current_memory)
                
                selected_clips = self._select_clips_with_constraints(all_clips, clip_usage, max_reuse, min_duration, max_duration)
                
                if not selected_clips:
                    self._log("Could not create compilation with given constraints, stopping", "warning", "generate_tikyou_videos")
                    print("⚠️  Could not create a compilation with the given constraints. Stopping.")
                    performance_stats['failed_compilations'] += 1
                    break
                
                # Update usage
                for clip in selected_clips:
                    clip_usage[clip['path']] += 1
                
                # Create all variations
                base_output_path = os.path.join(self.output_dir, f"{video_id}_compilation_{i+1}")
                variations_result = self.create_all_compilation_variations(
                    selected_clips, base_output_path, video_id, i+1
                )
                
                # Update statistics
                if variations_result['successful_count'] > 0:
                    created_count += 1
                    performance_stats['successful_compilations'] += 1
                    
                    # Track individual variations
                    if variations_result['normal']:
                        performance_stats['normal_variations'] += 1
                    if variations_result['tts']:
                        performance_stats['tts_variations'] += 1
                    if variations_result.get('no_background'):
                        performance_stats['no_background_variations'] = performance_stats.get('no_background_variations', 0) + 1
                    
                    performance_stats['total_variations'] += variations_result['successful_count']
                    
                    # Track output file sizes
                    total_set_size = 0
                    for variation_name, path in [('normal', variations_result['normal']), 
                                               ('tts', variations_result['tts']),
                                               ('no_background', variations_result.get('no_background'))]:
                        if path and os.path.exists(path):
                            file_size = os.path.getsize(path) / (1024 * 1024)  # MB
                            total_set_size += file_size
                            print(f"   📦 {variation_name.replace('_', ' ').capitalize()} variation: {file_size:.1f}MB")
                    
                    performance_stats['total_output_size'] += total_set_size
                    print(f"   📦 Total set size: {total_set_size:.1f}MB")
                    self._log(f"Compilation set {i+1} completed: {variations_result['successful_count']} variations, {total_set_size:.1f}MB", "info", "generate_tikyou_videos")
                else:
                    performance_stats['failed_compilations'] += 1
                    self._log(f"Compilation set {i+1} failed", "error", "generate_tikyou_videos")
                
                compilation_time = time.time() - compilation_start
                print(f"   ⏱️  Total set creation time: {compilation_time:.1f}s")

        else:
            self._log("Generating as many compilation sets as possible with simplified parallel processing", "info", "generate_tikyou_videos")
            print("🎯 Generating as many compilation sets as possible...")
            
            # Simplified approach: Generate one at a time but with optimizations
            compilation_num = 1
            consecutive_failures = 0
            max_consecutive_failures = 3
            
            while consecutive_failures < max_consecutive_failures:
                compilation_start = time.time()
                print(f"\n{'='*80}")
                print(f"COMPILATION SET {compilation_num} (Unlimited Mode)")
                print(f"{'='*80}")
                
                self._log(f"Starting compilation set {compilation_num} (unlimited mode)", "info", "generate_tikyou_videos")
                
                # Update peak memory usage and check if we need to pause
                current_memory = psutil.virtual_memory().percent
                performance_stats['peak_memory_usage'] = max(performance_stats['peak_memory_usage'], current_memory)
                
                if self._check_memory_usage():
                    print("   - Pausing for memory cleanup...")
                    time.sleep(2)
                
                selected_clips = self._select_clips_with_constraints(all_clips, clip_usage, max_reuse, min_duration, max_duration)
                
                if not selected_clips:
                    consecutive_failures += 1
                    print(f"⚠️  Could not create compilation {compilation_num} with the given constraints. Failure {consecutive_failures}/{max_consecutive_failures}")
                    self._log(f"Failed to create compilation {compilation_num}, failure {consecutive_failures}/{max_consecutive_failures}", "warning", "generate_tikyou_videos")
                    
                    if consecutive_failures >= max_consecutive_failures:
                        print("✅ No more valid compilations can be created with the remaining clips.")
                        self._log("Maximum consecutive failures reached, stopping generation", "info", "generate_tikyou_videos")
                        break
                    else:
                        compilation_num += 1
                        continue
                
                # Reset consecutive failures since we found valid clips
                consecutive_failures = 0
                
                # Update usage
                for clip in selected_clips:
                    clip_usage[clip['path']] += 1
                
                # Create all variations
                base_output_path = os.path.join(self.output_dir, f"{video_id}_compilation_{compilation_num}")
                
                try:
                    variations_result = self.create_all_compilation_variations(
                        selected_clips, base_output_path, video_id, compilation_num
                    )
                    
                    # Update statistics
                    if variations_result['successful_count'] > 0:
                        created_count += 1
                        performance_stats['successful_compilations'] += 1
                        
                        # Track individual variations
                        if variations_result['normal']:
                            performance_stats['normal_variations'] += 1
                        if variations_result['tts']:
                            performance_stats['tts_variations'] += 1
                        if variations_result.get('no_background'):
                            performance_stats['no_background_variations'] = performance_stats.get('no_background_variations', 0) + 1
                        
                        performance_stats['total_variations'] += variations_result['successful_count']
                        
                        # Track output file sizes
                        total_set_size = 0
                        for variation_name, path in [('normal', variations_result['normal']), 
                                                   ('tts', variations_result['tts']),
                                                   ('no_background', variations_result.get('no_background'))]:
                            if path and os.path.exists(path):
                                file_size = os.path.getsize(path) / (1024 * 1024)  # MB
                                total_set_size += file_size
                                print(f"   📦 {variation_name.replace('_', ' ').capitalize()} variation: {file_size:.1f}MB")
                        
                        performance_stats['total_output_size'] += total_set_size
                        print(f"   📦 Total set size: {total_set_size:.1f}MB")
                        self._log(f"Compilation set {compilation_num} completed: {variations_result['successful_count']} variations, {total_set_size:.1f}MB", "info", "generate_tikyou_videos")
                    else:
                        performance_stats['failed_compilations'] += 1
                        consecutive_failures += 1
                        self._log(f"Compilation set {compilation_num} failed", "error", "generate_tikyou_videos")
                        
                except Exception as e:
                    performance_stats['failed_compilations'] += 1
                    consecutive_failures += 1
                    print(f"❌ Error creating compilation {compilation_num}: {e}")
                    self._log(f"Error creating compilation {compilation_num}: {e}", "error", "generate_tikyou_videos")
                
                compilation_time = time.time() - compilation_start
                print(f"   ⏱️  Total set creation time: {compilation_time:.1f}s")
                
                compilation_num += 1
                
                # Periodic cleanup every 10 compilations
                if compilation_num % 10 == 0:
                    print(f"🧹 Performing periodic cleanup...")
                    self._cleanup_temp_files()
                    gc.collect()
                    if self.has_gpu:
                        torch.cuda.empty_cache()

        performance_stats['generation_time'] = time.time() - generation_start
        total_time = time.time() - start_time

        # Cleanup temp directory
        print("\n🧹 Cleaning up temporary files...")
        try:
            if os.path.isdir(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                print("✅ Temporary files cleaned up successfully")
        except Exception as e:
            print(f"⚠️ Warning: Could not clean up temp directory: {e}")
        
        # Also cleanup the old temp_vertical directory if it exists
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        temp_vertical_dir = backend_dir / "temp_vertical"
        if os.path.isdir(temp_vertical_dir):
            try:
                shutil.rmtree(temp_vertical_dir)
                print("✅ Legacy temp directory cleaned up")
            except Exception as e:
                print(f"⚠️ Warning: Could not clean up legacy temp directory: {e}")

        # Performance Summary
        print(f"\n{'='*60}")
        print(f"🎉 ENHANCED BRAINROT GENERATION COMPLETE!")
        print(f"{'='*60}")
        print(f"📊 PERFORMANCE SUMMARY:")
        print(f"   ✅ Successful compilation sets: {performance_stats['successful_compilations']}")
        print(f"   ❌ Failed compilation sets: {performance_stats['failed_compilations']}")
        print(f"   📹 Total clips processed: {performance_stats['total_clips_processed']}")
        print(f"   🎬 Total video variations created: {performance_stats['total_variations']}")
        print(f"      - Normal compilations: {performance_stats['normal_variations']}")
        print(f"      - TTS intro compilations: {performance_stats['tts_variations']}")
        print(f"   📦 Total output size: {performance_stats['total_output_size']:.1f}MB")
        print(f"   💾 Peak memory usage: {performance_stats['peak_memory_usage']:.1f}%")
        print(f"   🚀 Optimization features used:")
        print(f"      - Sequential processing: ✅ Yes (reliable)")
        print(f"      - Hardware acceleration: {'✅ GPU' if self.has_gpu else '💻 CPU'}")
        print(f"      - Clip caching: ✅ Yes ({len(self.clip_cache)} cached)")
        print(f"      - Scene analysis caching: ✅ Yes ({len(self.scene_analysis_cache)} cached)")
        print(f"      - Optimized temp directory: ✅ Yes")
        print(f"      - Memory management: ✅ Yes")
        print(f"      - Content complexity analysis: ✅ Yes")
        print(f"\n⏱️  TIMING BREAKDOWN:")
        print(f"   📥 Download & Processing: {performance_stats['download_time']:.1f}s")
        print(f"   🔍 Analysis & Categorization: {performance_stats['processing_time']:.1f}s")
        print(f"   🎬 Video Generation: {performance_stats['generation_time']:.1f}s")
        print(f"   🏁 Total Time: {total_time:.1f}s")
        
        # Log final summary
        self._log(f"Generation completed: {performance_stats['successful_compilations']} sets, {performance_stats['total_variations']} variations, {total_time:.1f}s total", "info", "generate_tikyou_videos")
        
        if performance_stats['successful_compilations'] > 0:
            avg_time_per_set = performance_stats['generation_time'] / performance_stats['successful_compilations']
            avg_size_per_set = performance_stats['total_output_size'] / performance_stats['successful_compilations']
            print(f"\n📈 AVERAGES:")
            print(f"   ⏱️  Time per compilation set: {avg_time_per_set:.1f}s")
            print(f"   📦 Size per compilation set: {avg_size_per_set:.1f}MB")
            
            if performance_stats['total_variations'] > 0:
                avg_size_per_variation = performance_stats['total_output_size'] / performance_stats['total_variations']
                print(f"   📦 Size per video variation: {avg_size_per_variation:.1f}MB")
        
        success_rate = (performance_stats['successful_compilations'] / 
                       (performance_stats['successful_compilations'] + performance_stats['failed_compilations'])) * 100 if (performance_stats['successful_compilations'] + performance_stats['failed_compilations']) > 0 else 0
        print(f"   ✅ Success rate: {success_rate:.1f}%")
        
        return performance_stats

    def generate_compilations_from_clips(self, video_id: str, clips: list, num_compilations: int, min_duration: int = 20, max_duration: int = 40, max_reuse: int = 3):
        """
        Generate compilations from a pre-selected list of clips.
        """
        start_time = time.time()
        performance_stats = {
            'start_time': start_time,
            'generation_time': 0,
            'successful_compilations': 0,
            'failed_compilations': 0,
            'peak_memory_usage': self.initial_memory,
            'total_output_size': 0,
            'normal_variations': 0,
            'tts_variations': 0,
            'total_variations': 0
        }

        clip_usage = {clip['path']: 0 for clip in clips}
        created_count = 0

        print(f"🎯 Generating {num_compilations} compilation sets from {len(clips)} selected clips...")

        for i in range(num_compilations):
            compilation_start = time.time()
            print(f"\n{'='*80}")
            print(f"COMPILATION SET {i+1}/{num_compilations}")
            print(f"{'='*80}")
            
            selected_clips = self._select_clips_with_constraints(clips, clip_usage, max_reuse, min_duration, max_duration)
            
            if not selected_clips:
                print("⚠️  Could not create a compilation with the given constraints. Stopping.")
                performance_stats['failed_compilations'] += 1
                break
            
            for clip in selected_clips:
                clip_usage[clip['path']] += 1
            
            base_output_path = os.path.join(self.output_dir, f"{video_id}_compilation_{created_count + 1}")
            variations_result = self.create_all_compilation_variations(
                selected_clips, base_output_path, video_id, created_count + 1
            )
            
            if variations_result['successful_count'] > 0:
                created_count += 1
                performance_stats['successful_compilations'] += 1
                if variations_result['normal']:
                    performance_stats['normal_variations'] += 1
                if variations_result['tts']:
                    performance_stats['tts_variations'] += 1
                if variations_result.get('no_background'):
                    performance_stats['no_background_variations'] = performance_stats.get('no_background_variations', 0) + 1
                performance_stats['total_variations'] += variations_result['successful_count']
                
                total_set_size = 0
                for variation_name, path in [('normal', variations_result['normal']), ('tts', variations_result['tts']), ('no_background', variations_result.get('no_background'))]:
                    if path and os.path.exists(path):
                        file_size = os.path.getsize(path) / (1024 * 1024)
                        total_set_size += file_size
                performance_stats['total_output_size'] += total_set_size
            else:
                performance_stats['failed_compilations'] += 1

        performance_stats['generation_time'] = time.time() - start_time
        return performance_stats

    def download_and_split_video(self, youtube_url: str, sensitivity: float = 30.0):
        """
        New, streamlined function for API usage.
        Downloads, analyzes, and splits a video, returning clip data.
        """
        try:
            video_id = self.extract_video_id(youtube_url)
        except ValueError as e:
            print(f"Error: {e}")
            return []

        # This now returns a list of dictionaries with clip metadata
        clips = self.processor.download_and_split(video_id, sensitivity=sensitivity)
        
        return clips

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def validate_orientation(self, video_path: str) -> str:
        """Return the orientation classification for a given video file.

        This thin wrapper exists so that the API layer (`app/main.py`) can query
        orientation without needing to know about the underlying `TikTokVideoCreator`
        instance.  It simply delegates to `self.creator.get_video_orientation`,
        ensuring that we always use the single, enhanced implementation.
        """
        return self.creator.get_video_orientation(video_path)


def main():
    """Main function for CLI execution"""
    parser = argparse.ArgumentParser(description="TikYou Video Generator")
    
    parser.add_argument("youtube_url", help="The YouTube URL to process")
    parser.add_argument("-n", "--num_compilations", type=int,
                        help="The number of compilations to create. If not provided, creates as many as possible.")
    parser.add_argument("--min_duration", type=int, default=20,
                        help="Minimum duration of each compilation in seconds.")
    parser.add_argument("--max_duration", type=int, default=40,
                        help="Maximum duration of each compilation in seconds.")
    parser.add_argument("--max_reuse", type=int, default=3,
                        help="Maximum number of times a single clip can be reused.")

    args = parser.parse_args()

    # Initialize generator
    generator = TikYouGenerator()

    # Generate videos
    generator.generate_tikyou_videos(
        args.youtube_url,
        num_compilations=args.num_compilations,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        max_reuse=args.max_reuse
    )


if __name__ == "__main__":
    main() 