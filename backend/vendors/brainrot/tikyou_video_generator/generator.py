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
from pathlib import Path
import multiprocessing
from tqdm import tqdm
import torch
import time
import uuid

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
from .tiktok import TikTokVideoCreator

from .title_generator import TitleGenerator


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
    def __init__(self, output_dir="final_videos", ffmpeg_path=None):
        # FFMPEG 7+ compatibility fix for moviepy
        if "FFPROBE_BINARY" not in os.environ:
            os.environ["FFPROBE_BINARY"] = "ffprobe"
        
        # Additional FFmpeg 7+ compatibility fixes
        if "FFMPEG_BINARY" not in os.environ:
            os.environ["FFMPEG_BINARY"] = "ffmpeg"
        
        # Set FFmpeg 7+ compatibility flags
        os.environ["FFMPEG_7_COMPAT"] = "1"
        
        # Disable deprecated options that cause issues in FFmpeg 7+
        os.environ["FFMPEG_DISABLE_SHOW_FORMAT"] = "1"
        
        self.output_dir = output_dir
        self.processor = CatVideoProcessor(output_dir=output_dir, ffmpeg_path=ffmpeg_path)
        self.creator = TikTokVideoCreator(output_dir=output_dir, ffmpeg_path=ffmpeg_path)
        self.max_workers = min(multiprocessing.cpu_count(), 4)  # Limit to 4 workers max
        
        # Initialize TTS generator for enhanced video variations
        try:
            # Import TTSGenerator here to handle import errors gracefully
            from .tts_generator import TTSGenerator
            self.tts_generator = TTSGenerator()
            self.tts_enabled = True
            print("🎙️ TTS Generator initialized successfully")
        except Exception as e:
            print(f"⚠️ TTS Generator initialization failed: {e}")
            print("   This is likely due to dependency version incompatibilities")
            print("   TTS variations will be skipped")
            self.tts_generator = None
            self.tts_enabled = False
        
        # Initialize Title generator for video titles
        try:
            self.title_generator = TitleGenerator()
            self.title_enabled = True
            print("🎬 Title Generator initialized successfully")
        except Exception as e:
            print(f"⚠️ Title Generator initialization failed: {e}")
            print("   Title overlays will be skipped")
            self.title_generator = None
            self.title_enabled = False
        
        # Memory monitoring
        self.memory_threshold = 0.85  # 85% memory usage threshold
        self.initial_memory = psutil.virtual_memory().percent
        print(f"💾 Initial memory usage: {self.initial_memory:.1f}%")
        
        # Check for GPU availability
        self.has_gpu = torch.cuda.is_available()
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
            print(f"   - GPU Encoding: h264_nvenc codec will be used")
        else:
            print("💻 Using CPU processing")
            print(f"   - CPU Encoding: libx264 codec will be used")
            print(f"   - CPU Workers: {self.max_workers}")
        
        # Create output directory
        Path(self.output_dir).mkdir(exist_ok=True)
    
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
        """Extract video ID from YouTube URL"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
            r'youtube\.com.*[?&]v=([^&\n?#]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        
        raise ValueError(f"Could not extract video ID from URL: {youtube_url}")
    
    def _process_clip_for_compilation(self, clip_path, target_resolution=(1080, 1920)):
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
                    clip = clip.with_effects([vfx.Resize(ratio)])
                else:
                    print(f"        📏 No resize needed, clip fits within bounds")
                
                # 3. Position original clip in the center
                print(f"        📍 Positioning clip at center...")
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
                        clip = clip.with_effects([vfx.Crop(x_center=clip.w / 2, y_center=clip.h / 2, width=target_w, height=target_h)])  # type: ignore[attr-defined]
                    else: # Taller than target
                        print(f"        📏 Clip is taller than target, resizing and cropping...")
                        clip = clip.with_effects([vfx.Resize(width=target_w)])
                        clip = clip.with_effects([vfx.Crop(x_center=clip.w / 2, y_center=clip.h / 2, width=target_w, height=target_h)])  # type: ignore[attr-defined]
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

    def process_single_video(self, youtube_url, sensitivity: float = 30.0, method: str = 'scenedetect'):
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
        print(f"🎬 Processing YouTube URL: {youtube_url}")
        
        # Extract video ID
        try:
            video_id = self.extract_video_id(youtube_url)
            print(f"📝 Extracted video ID: {video_id}")
        except ValueError as e:
            print(f"❌ Error: {e}")
            return []
        
        # Download the video
        print(f"📥 Downloading video...")
        download_result = self.processor.download_video(video_id)
        
        if not download_result or download_result[0] is None:
            print(f"❌ Failed to download video {video_id}")
            return []
        
        video_path, video_title = download_result
        print(f"✅ Downloaded: {video_path}")
        
        # 2. ✅ Detect and crop pillarboxes on the main video
        print(f"🔍 Detecting and cropping pillarboxes from main video...")
        cropped_video_path = self.processor.crop_video_if_vertical_with_blur(video_path)
        if cropped_video_path != video_path:
            print(f"✅ Pillarboxes cropped: {video_path} -> {cropped_video_path}")
            video_path = cropped_video_path
        else:
            print(f"ℹ️  No pillarboxes detected or cropping not needed")
        
        # Analyze the video for scenes
        print(f"🔍 Analyzing video for scenes...")
        analysis = self.processor.analyze_video_scenes(video_path, threshold=sensitivity, method=method)
        
        is_compilation = analysis['is_compilation']
        scenes = analysis['scenes']
        
        print(f"📊 Analysis Results:")
        print(f"   - Compilation: {'Yes' if is_compilation else 'No'}")
        print(f"   - Scenes found: {len(scenes)}")
        print(f"   - Duration: {analysis['duration']:.1f}s")
        
        video_clips = []
        
        if is_compilation and len(scenes) > 1:
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
        else:
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
        try:
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join("temp_vertical", f"{video_name}_vertical.mp4")
            
            # If vertical version already exists, return its path
            if os.path.exists(output_path):
                return output_path

            os.makedirs("temp_vertical", exist_ok=True)
            
            # Create a simplified vertical video without text
            W, H = 1080, 1920
            BACKGROUND_COLOR = (255, 255, 255)

            video_clip = VideoFileClip(video_path, audio=True)
            original_duration = video_clip.duration
            
            # IMPROVED: Higher bitrates for better quality
            if video_clip.w * video_clip.h > 1920 * 1080:  # High resolution source
                bitrate = '6000k'  # Increased from 3000k
                audio_bitrate = '256k'  # Increased from 192k
            elif original_duration > 60:  # Long video
                bitrate = '5000k'  # Increased from 2500k
                audio_bitrate = '192k'  # Increased from 160k
            else:  # Standard quality
                bitrate = '4000k'  # Increased from 2000k
                audio_bitrate = '192k'  # Increased from 128k
            
            video_clip = video_clip.with_effects([vfx.Resize(width=W)])
            background = ColorClip(size=(W, H), color=BACKGROUND_COLOR, duration=video_clip.duration)
            
            # Position video in the middle area of the frame
            video_y_position = 650
            video_clip = video_clip.with_position(('center', video_y_position))  # type: ignore[attr-defined]

            final_clip = CompositeVideoClip([background, video_clip], size=(W, H))
            final_clip.duration = video_clip.duration
            final_clip.audio = video_clip.audio

            # Enhanced encoding settings with GPU support and adaptive quality
            encoding_params = {
                'codec': 'h264_nvenc' if self.has_gpu else 'libx264',
                'audio_codec': 'aac',
                'preset': 'p3' if self.has_gpu else 'slow',  # IMPROVED: Better quality presets
                'threads': self.max_workers,
                'fps': 30,
                'bitrate': bitrate,
                'audio_bitrate': audio_bitrate,
                'write_logfile': False,
                'logger': None,
                'ffmpeg_params': [
                    '-movflags', 'faststart',
                    '-pix_fmt', 'yuv420p',  # Ensure compatibility
                    '-profile:v', 'high',   # H.264 high profile for better compression
                    '-level', '4.1'         # H.264 level for mobile compatibility
                ]
            }

            # Log encoding mode
            codec_name = 'h264_nvenc (GPU)' if self.has_gpu else 'libx264 (CPU)'
            preset_name = 'p3 (GPU)' if self.has_gpu else 'slow (CPU)'
            print(f"🎬 Converting {video_name}: {codec_name}, preset={preset_name}, bitrate={bitrate}")

            if self.has_gpu:
                # GPU encoding parameters are handled automatically by h264_nvenc
                print(f"   - GPU Options: Using NVENC hardware acceleration")
            else:
                # CPU-specific optimizations with IMPROVED quality settings
                encoding_params['ffmpeg_params'].extend([
                    '-crf', '20',  # IMPROVED: Lower CRF for better quality (was 23)
                    '-maxrate', bitrate,
                    '-bufsize', str(int(bitrate.replace('k', '')) * 2) + 'k'
                ])
                print(f"   - CPU Options: crf=20, maxrate={bitrate}, bufsize={str(int(bitrate.replace('k', '')) * 2)}k")

            final_clip.write_videofile(output_path, **encoding_params)
            
            video_clip.close()
            final_clip.close()

            # Verify output file was created successfully
            if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:  # Less than 1KB
                print(f"⚠️  Warning: Output file seems invalid for {video_name}")
                return None

            return output_path
        except Exception as e:
            print(f"❌ Error converting horizontal video: {e}")
            # Clean up partial file
            if 'output_path' in locals() and os.path.exists(output_path):
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
        
        # Concatenate clips
        try:
            print(f"     📹 Starting clip concatenation...")
            final_compilation = concatenate_videoclips(final_clips, method="compose")
            print(f"     ✅ Concatenation completed successfully")
            print(f"     📊 Final compilation duration: {final_compilation.duration:.1f}s")
            
            # Add title overlay if available
            if title and self.title_enabled:
                try:
                    print(f"     🎬 Adding title overlay: '{title}'")
                    # Use a simple text overlay approach instead of Playwright to avoid async issues
                    
                    # Create title clip directly with MoviePy TextClip
                    print(f"        📝 Creating text clip...")
                    title_clip = TextClip(
                        text=title, 
                        font_size=48, 
                        color='#00010a',
                        stroke_color='black',
                        stroke_width=1
                    ).with_duration(final_compilation.duration)
                    
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
            codec = 'h264_nvenc' if self.has_gpu else 'libx264'
            ffmpeg_params = [
                '-movflags', 'faststart',
                '-pix_fmt', 'yuv420p',
                '-profile:v', 'high',
                '-level', '4.1',
            ]
            
            # Log final compilation encoding mode
            codec_name = 'h264_nvenc (GPU)' if self.has_gpu else 'libx264 (CPU)'
            print(f"      🎬 Encoding configuration:")
            print(f"         - Codec: {codec_name}")
            print(f"         - Preset: {adaptive_params['quality_preset']}")
            print(f"         - Bitrate: {adaptive_params['bitrate']}")
            print(f"         - Workers: {self.max_workers}")
            
            # Add CPU-specific quality flags if not using GPU
            if not self.has_gpu:
                ffmpeg_params.extend([
                    '-crf', '20',  # IMPROVED: Lower CRF for better quality (was 22)
                    '-maxrate', adaptive_params['bitrate'],
                    '-bufsize', str(int(adaptive_params['bitrate'].replace('k', '')) * 2) + 'k'
                ])
                print(f"         - CPU Options: crf=20, maxrate={adaptive_params['bitrate']}, bufsize={str(int(adaptive_params['bitrate'].replace('k', '')) * 2)}k")
            else:
                print(f"         - GPU Options: Using NVENC hardware acceleration")

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
    
    def create_all_compilation_variations(self, selected_clips, base_output_path, video_id, compilation_num):
        """
        Create all 3 variations of a compilation:
        1. Normal compilation
        2. TTS intro compilation  
        3. Heavily edited compilation
        
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
        print(f"\n   📹 Variation 1/2: Normal Compilation")
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
            print(f"\n   🎙️ Variation 2/2: TTS Intro Compilation")
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
            print(f"\n   ⏭️ Variation 2/2: TTS Intro Compilation (SKIPPED - not available)")
        
        # 3. Heavily Edited Compilation (REMOVED)
        print(f"\n   ⏭️ Variation 3/3: Heavily Edited Compilation (REMOVED - no longer generated)")
        
        print(f"\n   📊 Compilation {compilation_num} Summary:")
        print(f"      ✅ Successful variations: {results['successful_count']}/{results['total_count']}")
        
        # Final system resource check
        final_memory = psutil.virtual_memory().percent
        final_disk = psutil.disk_usage(os.path.dirname(base_output_path)).free / (1024**3)  # GB
        print(f"   💻 Final system resources:")
        print(f"      - Memory usage: {final_memory:.1f}% (was {current_memory:.1f}%)")
        print(f"      - Available disk space: {final_disk:.1f}GB (was {available_disk:.1f}GB)")
        
        return results
    
    def generate_tikyou_videos(self, youtube_url, num_compilations=None, min_duration=60, max_duration=110, max_reuse=3):
        """
        Generate a number of vertical "brainrot" videos from a single YouTube URL.
        
        Args:
            youtube_url (str): The URL of the YouTube video.
            num_compilations (int, optional): The number of compilations to create. 
                                              If None, generates as many as possible. Defaults to None.
            min_duration (int): The minimum duration of each compilation in seconds.
            max_duration (int): The maximum duration of each compilation in seconds.
            max_reuse (int): The maximum number of times a single clip can be reused.
        """
        start_time = time.time()
        
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
        
        # 1. Process the video and get clips
        print(f"\n{'='*50}")
        print(f"PHASE 1: Video Processing")
        print(f"{'='*50}")
        
        phase_start = time.time()
        video_clips = self.process_single_video(youtube_url)
        performance_stats['download_time'] = time.time() - phase_start
        
        if not video_clips:
            print("❌ No video clips were processed. Exiting.")
            return performance_stats

        # 2. Categorize clips and prepare for generation
        print(f"\n{'='*50}")
        print(f"PHASE 2: Clip Analysis & Categorization")
        print(f"{'='*50}")
        
        phase_start = time.time()
        categorized_clips = self.categorize_clips(video_clips)
        all_clips = [clip for clips in categorized_clips.values() for clip in clips if clip['duration'] >= 1.0]
        performance_stats['total_clips_processed'] = len(all_clips)
        performance_stats['processing_time'] = time.time() - phase_start
        
        if not all_clips:
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
            print(f"🎯 Generating {num_compilations} compilation sets (3 variations each)...")
            
            for i in range(num_compilations):
                compilation_start = time.time()
                print(f"\n{'='*80}")
                print(f"COMPILATION SET {i+1}/{num_compilations}")
                print(f"{'='*80}")
                
                # Update peak memory usage
                current_memory = psutil.virtual_memory().percent
                performance_stats['peak_memory_usage'] = max(performance_stats['peak_memory_usage'], current_memory)
                
                selected_clips = self._select_clips_with_constraints(all_clips, clip_usage, max_reuse, min_duration, max_duration)
                
                if not selected_clips:
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
                    
                    performance_stats['total_variations'] += variations_result['successful_count']
                    
                    # Track output file sizes
                    total_set_size = 0
                    for variation_name, path in [('normal', variations_result['normal']), 
                                               ('tts', variations_result['tts'])]:
                        if path and os.path.exists(path):
                            file_size = os.path.getsize(path) / (1024 * 1024)  # MB
                            total_set_size += file_size
                            print(f"   📦 {variation_name.capitalize()} variation: {file_size:.1f}MB")
                    
                    performance_stats['total_output_size'] += total_set_size
                    print(f"   📦 Total set size: {total_set_size:.1f}MB")
                else:
                    performance_stats['failed_compilations'] += 1
                
                compilation_time = time.time() - compilation_start
                print(f"   ⏱️  Total set creation time: {compilation_time:.1f}s")

        else:
            print("🎯 Generating as many compilation sets as possible...")
            compilation_num = 1
            while True:
                compilation_start = time.time()
                print(f"\n{'='*80}")
                print(f"COMPILATION SET {compilation_num} (Unlimited Mode)")
                print(f"{'='*80}")
                
                # Update peak memory usage
                current_memory = psutil.virtual_memory().percent
                performance_stats['peak_memory_usage'] = max(performance_stats['peak_memory_usage'], current_memory)
                
                selected_clips = self._select_clips_with_constraints(all_clips, clip_usage, max_reuse, min_duration, max_duration)
                
                if not selected_clips:
                    print("✅ No more valid compilations can be created with the remaining clips.")
                    break
                
                # Update usage
                for clip in selected_clips:
                    clip_usage[clip['path']] += 1
                
                # Create all variations
                base_output_path = os.path.join(self.output_dir, f"{video_id}_compilation_{compilation_num}")
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
                    
                    performance_stats['total_variations'] += variations_result['successful_count']
                    
                    # Track output file sizes
                    total_set_size = 0
                    for variation_name, path in [('normal', variations_result['normal']), 
                                               ('tts', variations_result['tts'])]:
                        if path and os.path.exists(path):
                            file_size = os.path.getsize(path) / (1024 * 1024)  # MB
                            total_set_size += file_size
                            print(f"   📦 {variation_name.capitalize()} variation: {file_size:.1f}MB")
                    
                    performance_stats['total_output_size'] += total_set_size
                    print(f"   📦 Total set size: {total_set_size:.1f}MB")
                else:
                    performance_stats['failed_compilations'] += 1
                
                compilation_time = time.time() - compilation_start
                print(f"   ⏱️  Total set creation time: {compilation_time:.1f}s")
                compilation_num += 1

        performance_stats['generation_time'] = time.time() - generation_start
        total_time = time.time() - start_time

        # Cleanup temp directory
        if os.path.isdir("temp_vertical"):
            print("\n🧹 Cleaning up temporary files...")
            shutil.rmtree("temp_vertical")

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
        print(f"\n⏱️  TIMING BREAKDOWN:")
        print(f"   📥 Download & Processing: {performance_stats['download_time']:.1f}s")
        print(f"   🔍 Analysis & Categorization: {performance_stats['processing_time']:.1f}s")
        print(f"   🎬 Video Generation: {performance_stats['generation_time']:.1f}s")
        print(f"   🏁 Total Time: {total_time:.1f}s")
        
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

    def generate_compilations_from_clips(self, video_id: str, clips: list, num_compilations: int, min_duration: int, max_duration: int, max_reuse: int):
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
                performance_stats['total_variations'] += variations_result['successful_count']
                
                total_set_size = 0
                for variation_name, path in [('normal', variations_result['normal']), ('tts', variations_result['tts'])]:
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
    parser.add_argument("--min_duration", type=int, default=60, 
                        help="Minimum duration of each compilation in seconds.")
    parser.add_argument("--max_duration", type=int, default=100,
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