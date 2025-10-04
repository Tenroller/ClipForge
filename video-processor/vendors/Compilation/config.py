#!/usr/bin/env python3
"""
Configuration Management for TikYou Video Generator

This module provides centralized configuration management for all settings
used throughout the video generation process.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path


@dataclass
class VideoResolution:
    """Video resolution configuration"""
    width: int
    height: int
    
    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height
    
    @property
    def size(self) -> Tuple[int, int]:
        return (self.width, self.height)


@dataclass
class EncodingConfig:
    """Video encoding configuration"""
    # GPU encoding settings
    gpu_codec: str = 'h264_nvenc'
    gpu_preset: str = 'p3'
    gpu_bitrate: str = '8000k'
    gpu_audio_bitrate: str = '256k'
    
    # CPU encoding settings
    cpu_codec: str = 'libx264'
    cpu_preset: str = 'slow'
    cpu_bitrate: str = '6000k'
    cpu_audio_bitrate: str = '192k'
    cpu_crf: str = '20'
    
    # Common settings
    audio_codec: str = 'aac'
    fps: int = 30
    max_bitrate_multiplier: int = 2
    
    # FFmpeg parameters
    ffmpeg_params: List[str] = field(default_factory=lambda: [
        '-movflags', 'faststart',
        '-pix_fmt', 'yuv420p',
        '-profile:v', 'high',
        '-level', '4.1'
    ])


@dataclass
class ProcessingConfig:
    """Processing configuration"""
    # Worker settings
    max_workers: int = 4
    chunk_size: int = 5
    
    # Memory settings
    memory_threshold: float = 0.85
    memory_conservative_threshold: float = 0.80
    low_memory_threshold_gb: float = 1.5
    
    # System resource thresholds
    high_cpu_threshold: float = 85.0
    high_memory_threshold: float = 80.0
    
    # Scene detection
    default_scene_sensitivity: float = 17.0
    min_scene_duration: float = 3
    
    # Clip constraints
    min_clip_duration: float = 1.0
    max_clip_reuse: int = 3
    
    # Compilation settings
    default_min_duration: int = 20
    default_max_duration: int = 40
    
    # Low resolution handling
    low_res_scale_factor: float = 0.5  # Only treat videos smaller than 50% as low-res
    low_res_fit_factor: float = 0.9   # Scale low-res videos to 90% of target size


@dataclass
class UIConfig:
    """User interface and visual configuration"""
    # Video positioning
    vertical_video_y_position: int = 650
    title_y_position: int = 130
    
    # Background colors
    background_color: Tuple[int, int, int] = (255, 255, 255)
    
    # Text settings
    title_font_size: int = 48
    title_font: str = 'EpundaSlab-VariableFont_wght.ttf'  # Use centralized font
    title_color: str = '#00010a'
    title_stroke_color: str = 'black'
    title_stroke_width: int = 1
    
    # Progress display
    show_detailed_progress: bool = True
    progress_update_interval: float = 1.0


@dataclass
class PathConfig:
    """Path configuration"""
    # Directory names
    # Prefer a unified output directory if provided via env; fallback to original
    output_dir: str = os.getenv("VIDEOHELPER_OUTPUT_DIR", "final_videos")
    temp_vertical_dir: str = "temp_vertical"
    debug_frames_dir: str = "debug_frames"
    
    # File naming patterns
    compilation_pattern: str = "{video_id}_compilation_{num}"
    normal_suffix: str = "_normal"
    tts_suffix: str = "_tts"
    vertical_suffix: str = "_vertical"
    
    # Temp file patterns
    temp_audio_pattern: str = "temp-audio-{uuid}.m4a"


@dataclass
class SystemConfig:
    """System-level configuration"""
    # FFmpeg environment variables
    ffmpeg_env_vars: Dict[str, str] = field(default_factory=lambda: {
        "FFPROBE_BINARY": "ffprobe",
        "FFMPEG_BINARY": "ffmpeg",
        "FFMPEG_7_COMPAT": "1",
        "FFMPEG_DISABLE_SHOW_FORMAT": "1"
    })
    
    # Retry settings
    max_retries: int = 20
    retry_delay: float = 1.0
    
    # Validation settings
    min_file_size_bytes: int = 1024  # 1KB minimum
    validate_outputs: bool = True


class TikYouConfig:
    """Main configuration class that combines all config sections"""
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration, optionally loading from file"""
        # Initialize all configuration sections with dynamic resolution support
        self.video = VideoResolution(width=1080, height=1920)  # Default, will be overridden dynamically
        self.encoding = EncodingConfig()
        self.processing = ProcessingConfig()
        self.ui = UIConfig()
        self.paths = PathConfig()
        self.system = SystemConfig()
        
        # Load from file if provided
        if config_file:
            self.load_from_file(config_file)
        
        # Apply environment variable overrides
        self._apply_env_overrides()
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to configuration"""
        # Video resolution
        width_str = os.getenv('TIKYOU_WIDTH')
        if width_str is not None:
            self.video.width = int(width_str)
        height_str = os.getenv('TIKYOU_HEIGHT')
        if height_str is not None:
            self.video.height = int(height_str)
            
        # Processing
        max_workers_str = os.getenv('TIKYOU_MAX_WORKERS')
        if max_workers_str is not None:
            self.processing.max_workers = int(max_workers_str)
        memory_threshold_str = os.getenv('TIKYOU_MEMORY_THRESHOLD')
        if memory_threshold_str is not None:
            self.processing.memory_threshold = float(memory_threshold_str)
            
        # Paths (prefer unified env var if present)
        unified_dir = os.getenv('VIDEOHELPER_OUTPUT_DIR')
        if unified_dir:
            self.paths.output_dir = unified_dir
        else:
            output_dir_override = os.getenv('TIKYOU_OUTPUT_DIR')
            if output_dir_override:
                self.paths.output_dir = output_dir_override
    
    def set_dynamic_resolution(self, input_video_path: str):
        """Set video resolution based on input video aspect ratio"""
        try:
            import subprocess
            import json
            
            # Get video info using ffprobe
            result = subprocess.run([
                'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', 
                '-show_format', input_video_path
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                
                # Find video stream
                for stream in info.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        width = stream.get('width', 1920)
                        height = stream.get('height', 1080)
                        
                        if width > 0 and height > 0:
                            aspect_ratio = width / height
                            
                            if aspect_ratio > 1.5:  # Horizontal
                                self.video.width = 1920
                                self.video.height = 1080
                                print(f"Detected horizontal video -> 1920x1080 output")
                            elif aspect_ratio < 0.7:  # Vertical
                                self.video.width = 1080
                                self.video.height = 1920
                                print(f"Detected vertical video -> 1080x1920 output")
                            else:  # Square-ish
                                self.video.width = 1080
                                self.video.height = 1080
                                print(f"Detected square video -> 1080x1080 output")
                            
                            return
            
            print("Could not detect video aspect ratio, using default 1920x1080")
            self.video.width = 1920
            self.video.height = 1080
            
        except Exception as e:
            print(f"Error detecting video aspect ratio: {e}, using default 1920x1080")
            self.video.width = 1920
            self.video.height = 1080

    def load_from_file(self, config_file: str):
        """Load configuration from a JSON or YAML file"""
        # TODO: Implement file loading
        pass
    
    def save_to_file(self, config_file: str):
        """Save current configuration to a file"""
        # TODO: Implement file saving
        pass
    
    def get_encoding_params(self, use_gpu: bool = False, duration: float = 0, 
                          resolution: Optional[Tuple[int, int]] = None) -> Dict[str, object]:
        """Get encoding parameters based on system capabilities and content"""
        config = self.encoding
        
        # Base parameters
        if use_gpu:
            params: Dict[str, object] = {
                'codec': config.gpu_codec,
                'preset': config.gpu_preset,
                'bitrate': config.gpu_bitrate,
                'audio_bitrate': config.gpu_audio_bitrate
            }
        else:
            params = {
                'codec': config.cpu_codec,
                'preset': config.cpu_preset,
                'bitrate': config.cpu_bitrate,
                'audio_bitrate': config.cpu_audio_bitrate
            }
        
        # Adjust bitrate based on resolution and duration
        if resolution and duration > 0:
            pixel_count = resolution[0] * resolution[1]
            if pixel_count > 1920 * 1080:  # High resolution
                bitrate_str = str(params['bitrate'])
                current_bitrate = int(bitrate_str.replace('k', ''))
                params['bitrate'] = f"{int(current_bitrate * 1.2)}k"
            elif duration > 300:  # Long duration
                bitrate_str = str(params['bitrate'])
                current_bitrate = int(bitrate_str.replace('k', ''))
                params['bitrate'] = f"{int(current_bitrate * 0.9)}k"
        
        # Add common parameters
        params.update({
            'audio_codec': config.audio_codec,
            'fps': config.fps,
            'ffmpeg_params': config.ffmpeg_params.copy()
        })
        
        # Add CPU-specific parameters
        if not use_gpu:
            ff_args = params.get('ffmpeg_params')
            if isinstance(ff_args, list):
                ff_args.extend([
                    '-crf', config.cpu_crf,
                    '-maxrate', params['bitrate'],
                    '-bufsize', f"{int(str(params['bitrate']).replace('k', '')) * config.max_bitrate_multiplier}k"
                ])
            else:
                params['ffmpeg_params'] = config.ffmpeg_params.copy() + [
                '-crf', config.cpu_crf,
                '-maxrate', params['bitrate'],
                '-bufsize', f"{int(str(params['bitrate']).replace('k', '')) * config.max_bitrate_multiplier}k"
            ]
        
        return params
    
    def get_adaptive_processing_params(self, clips_count: int, total_duration: float,
                                     cpu_percent: float, memory_percent: float,
                                     available_memory_gb: float, use_gpu: bool = False) -> Dict:
        """Get adaptive processing parameters based on system load and content"""
        proc_config = self.processing
        
        # Start with base parameters
        params = {
            'max_workers': min(proc_config.max_workers, max(1, clips_count // 4)),
            'chunk_size': proc_config.chunk_size,
            'memory_conservative': False,
            'processing_strategy': 'parallel'
        }
        
        # Get encoding parameters
        encoding_params = self.get_encoding_params(use_gpu, total_duration)
        params.update(encoding_params)
        
        # Adjust based on system load
        if cpu_percent > proc_config.high_cpu_threshold:
            params['max_workers'] = max(1, params['max_workers'] // 2)
            params['processing_strategy'] = 'sequential'
            if use_gpu:
                params['preset'] = 'p4'
            else:
                params['preset'] = 'medium'
        
        if memory_percent > proc_config.high_memory_threshold:
            params['memory_conservative'] = True
            params['chunk_size'] = 2
            params['max_workers'] = max(1, params['max_workers'] // 2)
        
        if available_memory_gb < proc_config.low_memory_threshold_gb:
            params['memory_conservative'] = True
            params['chunk_size'] = 1
            params['max_workers'] = 1
            params['processing_strategy'] = 'sequential'
            if use_gpu:
                params['preset'] = 'p5'
            else:
                params['preset'] = 'fast'
        
        # Adjust for content complexity
        if clips_count > 25:
            params['chunk_size'] = min(10, clips_count // 4)
        
        if total_duration > 360:  # 6 minutes
            if use_gpu:
                params['preset'] = 'p4'
            else:
                params['preset'] = 'medium'
        
        return params
    
    def setup_environment(self):
        """Set up environment variables for FFmpeg compatibility"""
        for key, value in self.system.ffmpeg_env_vars.items():
            if key not in os.environ:
                os.environ[key] = value
    
    def create_directories(self):
        """Create necessary directories"""
        directories = [
            self.paths.output_dir,
            self.paths.temp_vertical_dir,
            self.paths.debug_frames_dir
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_output_path(self, video_id: str, compilation_num: int, 
                       variation: str = "normal") -> str:
        """Generate output path for a video"""
        base_name = self.paths.compilation_pattern.format(
            video_id=video_id, 
            num=compilation_num
        )
        
        suffix = ""
        if variation == "normal":
            suffix = self.paths.normal_suffix
        elif variation == "tts":
            suffix = self.paths.tts_suffix
        
        return os.path.join(self.paths.output_dir, f"{base_name}{suffix}.mp4")
    
    def get_temp_vertical_path(self, video_name: str) -> str:
        """Generate temporary vertical video path"""
        return os.path.join(
            self.paths.temp_vertical_dir, 
            f"{video_name}{self.paths.vertical_suffix}.mp4"
        )


# Global configuration instance
config = TikYouConfig() 