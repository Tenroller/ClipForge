#!/usr/bin/env python3
"""
TikTok Video Creator

This script:
1. Processes videos using the cat video processor
2. Extracts and categorizes video parts by orientation (horizontal/vertical)
3. Combines random parts into a ~90-second vertical video for TikTok
4. Uses the template function for horizontal-to-vertical conversion
"""

import os
import random
import sys
from pathlib import Path
from moviepy import VideoFileClip, CompositeVideoClip, ColorClip, concatenate_videoclips
from PIL import Image
import numpy as np
from .processor import CatVideoProcessor
import torch


class TikTokVideoCreator:
    def __init__(self, output_dir="final_videos", ffmpeg_path=None):
        # FFmpeg 7+ compatibility fixes
        if "FFMPEG_BINARY" not in os.environ:
            os.environ["FFMPEG_BINARY"] = r'C:\ffmpeg\bin\ffmpeg.exe'
        if "FFPROBE_BINARY" not in os.environ:
            os.environ["FFPROBE_BINARY"] = r'C:\ffmpeg\bin\ffprobe.exe'
        
        # Set FFmpeg 7+ compatibility flags
        os.environ["FFMPEG_7_COMPAT"] = "1"
        os.environ["FFMPEG_DISABLE_SHOW_FORMAT"] = "1"
        
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.processor = CatVideoProcessor(output_dir=output_dir, ffmpeg_path=ffmpeg_path)
        
        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(exist_ok=True)
        
        # Add GPU detection
        self.has_gpu = torch.cuda.is_available()
    
    def validate_video_file(self, video_path):
        """Validate if a video file is readable and not corrupted"""
        video_info = self.processor.get_video_info(video_path)
        if not video_info:
            return False, "Failed to get video info"

        try:
            with VideoFileClip(video_path) as test_clip:
                if test_clip.duration > 0:
                    test_clip.get_frame(0)
                    return True, "Valid"
            return False, "MoviePy validation failed"
        except Exception as e:
            return False, f"MoviePy error: {str(e)}"
    
    def get_video_orientation(self, video_path):
        """Robustly determine if a video is horizontal, vertical, or pillar-boxed vertical.

        Strategy:
        1.  Quick exit for obvious cases (height >= width => vertical/square).
        2.  If the frame is wider than tall, run advanced pillar-box detection that analyses
            multiple frames using the new detect_pillarboxes_advanced method.
        3.  Default to horizontal when all heuristics fail.
        """

        video_info = self.processor.get_video_info(video_path)
        if not video_info:
            return 'unknown'

        width = video_info.get('width', 0)
        height = video_info.get('height', 0)

        # 1.  Fast path – clearly vertical or square
        if height > width:
            return 'vertical'
        if width == height:
            return 'square'

        # 2.  Potential pillar-boxed vertical – run advanced detection
        try:
            left_crop, right_crop = self.processor.detect_pillarboxes_advanced(video_path, method='edge')
            if left_crop > 0 or right_crop > 0:
                content_width = width - left_crop - right_crop
                # If the detected content is narrower than the frame height, treat as vertical
                if content_width < height:
                    return 'vertical'
        except Exception as pillar_err:
            print(f"[Orientation] Advanced pillar detection failed: {pillar_err}")

        # 3.  No heuristic indicated vertical → assume horizontal
        return 'horizontal'
    
    def categorize_videos_from_directory(self, video_directory):
        """Categorize videos from a directory by orientation"""
        categorized = {
            'horizontal': [],
            'vertical': [],
            'square': [],
            'unknown': []
        }
        
        if not os.path.exists(video_directory):
            print(f"Directory {video_directory} does not exist")
            return categorized
        
        # Find all video files in the directory
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        video_files = []
        
        for root, dirs, files in os.walk(video_directory):
            for file in files:
                if any(file.lower().endswith(ext) for ext in video_extensions):
                    video_files.append(os.path.join(root, file))
        
        print(f"Categorizing {len(video_files)} videos by orientation...")
        
        for video_path in video_files:
            if os.path.exists(video_path):
                # Get video duration using processor
                duration = self.processor.get_video_duration(video_path) or 0
                
                orientation = self.get_video_orientation(video_path)
                video_info = {
                    'id': os.path.basename(video_path),
                    'path': video_path,
                    'duration': duration,
                    'source_id': os.path.basename(video_path),
                    'orientation': orientation,
                    'type': 'file'
                }
                categorized[orientation].append(video_info)
                
                print(f"  {os.path.basename(video_path)}: {orientation} ({duration:.1f}s)")
            else:
                print(f"  {video_path}: File not found")
        
        # Print summary
        print(f"\n=== Orientation Summary ===")
        for orientation, videos in categorized.items():
            total_duration = sum(v['duration'] for v in videos)
            print(f"{orientation.capitalize()}: {len(videos)} videos ({total_duration:.1f}s total)")
        
        return categorized
    
    def select_videos_for_compilation(self, categorized_videos, target_duration=90):
        """Select random videos to reach approximately target duration"""
        all_videos = []
        
        # Combine all available videos, filtering out very short ones
        for orientation, videos in categorized_videos.items():
            if orientation != 'unknown':  # Skip unknown orientation videos
                # Filter out videos shorter than 5.0 seconds to prevent playback issues and avoid mid-scene cuts
                valid_videos = [v for v in videos if v['duration'] >= 5.0]
                all_videos.extend(valid_videos)
                
                if len(videos) != len(valid_videos):
                    print(f"Filtered out {len(videos) - len(valid_videos)} videos from {orientation} (too short < 5.0s)")
        
        if not all_videos:
            print("No videos available for compilation!")
            return []
        
        # Shuffle and select videos to reach target duration
        random.shuffle(all_videos)
        selected_videos = []
        total_duration = 0
        
        for video in all_videos:
            if total_duration >= target_duration:
                break
            
            # Validate video file before selecting it
            is_valid, validation_message = self.validate_video_file(video['path'])
            if not is_valid:
                print(f"⚠️  Skipping corrupted video {video['id']}: {validation_message}")
                continue
            
            selected_videos.append(video)
            total_duration += video['duration']
            
            video_type = video['type']
            orientation = video['orientation']
            template_note = " (will use template)" if orientation == 'horizontal' else " (direct use)" if orientation == 'vertical' else " (will use template)"
            
            print(f"Selected: {video['id']} ({orientation}, {video_type}, {video['duration']:.1f}s){template_note} - Total: {total_duration:.1f}s")
        
        print(f"\n=== Selection Complete ===")
        print(f"Selected {len(selected_videos)} videos for total duration: {total_duration:.1f}s")
        
        # Show breakdown
        horizontal_count = len([v for v in selected_videos if v['orientation'] == 'horizontal'])
        vertical_count = len([v for v in selected_videos if v['orientation'] == 'vertical'])
        square_count = len([v for v in selected_videos if v['orientation'] == 'square'])
        split_count = len([v for v in selected_videos if v['type'] == 'split'])
        single_count = len([v for v in selected_videos if v['type'] == 'single'])
        
        print(f"Breakdown:")
        print(f"  - Horizontal (with template): {horizontal_count}")
        print(f"  - Vertical (direct): {vertical_count}")
        print(f"  - Square (with template): {square_count}")
        print(f"  - Split scenes: {split_count}")
        print(f"  - Single videos: {single_count}")
        
        return selected_videos
    
    def scan_for_corrupted_videos_in_directory(self, video_directory):
        """Scan all videos in a directory and identify corrupted ones"""
        corrupted_videos = []
        
        print("🔍 Scanning for corrupted videos...")
        
        if not os.path.exists(video_directory):
            print(f"Directory {video_directory} does not exist")
            return corrupted_videos
        
        # Find all video files in the directory
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        video_files = []
        
        for root, dirs, files in os.walk(video_directory):
            for file in files:
                if any(file.lower().endswith(ext) for ext in video_extensions):
                    video_files.append(os.path.join(root, file))
        
        for video_path in video_files:
            if os.path.exists(video_path):
                is_valid, validation_message = self.validate_video_file(video_path)
                if not is_valid:
                    corrupted_videos.append({
                        'id': os.path.basename(video_path),
                        'path': video_path,
                        'type': 'file',
                        'source_id': os.path.basename(video_path),
                        'error': validation_message
                    })
                    print(f"❌ Corrupted video: {os.path.basename(video_path)} - {validation_message}")
        
        print(f"\n📊 Scan Results:")
        print(f"  - Total corrupted videos found: {len(corrupted_videos)}")
        
        if corrupted_videos:
            print(f"\n⚠️  Corrupted Videos:")
            for video in corrupted_videos:
                print(f"  - {video['id']} ({video['type']}): {video['error']}")
        
        return corrupted_videos
    
    def create_vertical_clip_from_horizontal(self, video_path):
        """Convert horizontal video to vertical format without title"""
        try:
            # Use absolute path to avoid working directory issues
            # Get the backend directory (parent of vendors)
            backend_dir = Path(__file__).resolve().parent.parent.parent.parent
            temp_vertical_dir = backend_dir / "temp_vertical"
            os.makedirs(temp_vertical_dir, exist_ok=True)
            
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(str(temp_vertical_dir), f"{video_name}_vertical.mp4")
            
            # If vertical version already exists, return its path
            if os.path.exists(output_path):
                return output_path
            
            # Create a simplified vertical video without text
            W, H = 1080, 1920
            BACKGROUND_COLOR = (255, 255, 255)

            video_clip = VideoFileClip(video_path, audio=True)
            video_clip = video_clip.resized(width=W)
            background = ColorClip(size=(W, H), color=BACKGROUND_COLOR, duration=video_clip.duration)
            
            # Position video in the middle area of the frame
            video_y_position = 650
            video_clip = video_clip.with_position(('center', video_y_position))  # type: ignore

            final_clip = CompositeVideoClip([background, video_clip], size=(W, H))
            final_clip.duration = video_clip.duration
            final_clip.audio = video_clip.audio

            # Use GPU encoding if available
            codec = 'h264_nvenc' if (hasattr(self, 'has_gpu') and self.has_gpu) else 'libx264'
            ffmpeg_params = [
                '-movflags', 'faststart',
                '-pix_fmt', 'yuv420p',
                '-profile:v', 'high',
                '-level', '4.1',
            ]
            
            # IMPROVED: Add quality settings
            preset = 'p3' if (hasattr(self, 'has_gpu') and self.has_gpu) else 'slow'
            bitrate = '5000k'  # IMPROVED: Add bitrate control
            
            # Log encoding mode
            use_gpu = hasattr(self, 'has_gpu') and self.has_gpu
            codec_name = 'h264_nvenc (GPU)' if use_gpu else 'libx264 (CPU)'
            preset_name = 'p3 (GPU)' if use_gpu else 'slow (CPU)'
            print(f"🎬 TikTok vertical conversion: {codec_name}, preset={preset_name}, bitrate={bitrate}")
            
            if not (hasattr(self, 'has_gpu') and self.has_gpu):
                # Add CRF for better quality on CPU encoding
                ffmpeg_params.extend([
                    '-crf', '20',
                    '-maxrate', bitrate,
                    '-bufsize', '10000k'
                ])
                print(f"   - CPU Options: crf=20, maxrate={bitrate}, bufsize=10000k")
            else:
                print(f"   - GPU Options: Using NVENC hardware acceleration")
            
            final_clip.write_videofile(
                output_path,
                codec=codec,
                audio_codec='aac',
                remove_temp=True,
                fps=30,
                preset=preset,  # IMPROVED: Use quality preset instead of veryfast
                threads=4,
                logger=None,
                bitrate=bitrate,  # IMPROVED: Add bitrate control
                ffmpeg_params=ffmpeg_params
            )
            
            video_clip.close()
            final_clip.close()

            return output_path
        except Exception as e:
            print(f"❌ Error converting horizontal video: {e}")
            return None
    
    def create_tiktok_compilation(self, selected_videos, output_path=None):
        """Create a TikTok-ready vertical video compilation"""
        if not selected_videos:
            print("No videos selected for compilation!")
            return None
        
        if output_path is None:
            output_path = os.path.join(self.output_dir, "tiktok_compilation.mp4")
        
        print(f"\n=== Creating TikTok Compilation ===")
        print(f"Output: {output_path}")
        
        clips = []
        temp_files = []  # Keep track of temporary files to clean up
        
        try:
            for i, video_info in enumerate(selected_videos):
                video_path = video_info['path']
                orientation = video_info['orientation']
                video_type = video_info['type']
                print(f"[COMPILATION] Using video for clip {i+1}: {video_path} (orientation: {orientation}, type: {video_type})")
                
                try:
                    if orientation == 'horizontal':
                        # Convert horizontal to vertical using template
                        vertical_path = self.create_vertical_clip_from_horizontal(video_path)
                        if vertical_path:
                            clip = VideoFileClip(vertical_path)
                            temp_files.append(vertical_path)
                        else:
                            print(f"Failed to convert horizontal video, skipping: {video_info['id']}")
                            continue
                    
                    elif orientation == 'vertical':
                        # Use vertical video as-is, just resize to TikTok dimensions
                        print(f"  Using vertical video directly (no template)")
                        clip = VideoFileClip(video_path)
                        # Ensure it's the right size for TikTok (1080x1920)
                        if clip.h != 1920 or clip.w != 1080:  # type: ignore
                            clip = clip.resized(height=1920)  # type: ignore
                            if clip.w > 1080:  # type: ignore
                                # If width is still too wide, center crop it
                                x1 = (clip.w - 1080) // 2  # type: ignore
                                clip = clip.cropped(x1=x1, width=1080)  # type: ignore
                            elif clip.w < 1080:  # type: ignore
                                # If width is too narrow, resize by width
                                clip = clip.resized(width=1080)  # type: ignore
                    
                    elif orientation == 'square':
                        # Convert square to vertical by adding padding or using template
                        vertical_path = self.create_vertical_clip_from_horizontal(video_path)
                        if vertical_path:
                            clip = VideoFileClip(vertical_path)
                            temp_files.append(vertical_path)
                        else:
                            print(f"Failed to convert square video, skipping: {video_info['id']}")
                            continue
                    
                    else:
                        print(f"Unknown orientation, skipping: {video_info['id']}")
                        continue
                        
                except Exception as e:
                    print(f"⚠️  Error processing video {video_info['id']} ({video_path}): {e}")
                    print(f"   Skipping corrupted/problematic video and continuing...")
                    # Clean up any partially created clip
                    try:
                        if 'clip' in locals():
                            clip.close()
                    except:
                        pass
                    continue
                
                clips.append(clip)
            
            if not clips:
                print("No clips available for compilation!")
                return None
            
            print(f"Concatenating {len(clips)} clips...")
            
            # Concatenate all clips
            final_video = concatenate_videoclips(clips, method="compose")
            
            # Ensure final video is exactly 1080x1920
            final_video = final_video.resized(width=1080, height=1920)
            
            # Write the final video
            print(f"Writing final compilation to: {output_path}")
            
            # IMPROVED: Better quality settings for final compilation
            codec = 'h264_nvenc' if (hasattr(self, 'has_gpu') and self.has_gpu) else 'libx264'
            preset = 'p3' if (hasattr(self, 'has_gpu') and self.has_gpu) else 'slow'
            bitrate = '6000k'  # IMPROVED: Add bitrate control
            
            # Enhanced ffmpeg parameters for better quality
            ffmpeg_params = [
                '-movflags', 'faststart',
                '-pix_fmt', 'yuv420p',
                '-profile:v', 'high',
                '-level', '4.1',
            ]
            
            # Log final compilation encoding mode
            use_gpu = hasattr(self, 'has_gpu') and self.has_gpu
            codec_name = 'h264_nvenc (GPU)' if use_gpu else 'libx264 (CPU)'
            preset_name = 'p3 (GPU)' if use_gpu else 'slow (CPU)'
            print(f"🎬 TikTok final compilation: {codec_name}, preset={preset_name}, bitrate={bitrate}")
            
            if not (hasattr(self, 'has_gpu') and self.has_gpu):
                # Add CRF for better quality on CPU encoding
                ffmpeg_params.extend([
                    '-crf', '20',
                    '-maxrate', bitrate,
                    '-bufsize', '12000k'
                ])
                print(f"   - CPU Options: crf=20, maxrate={bitrate}, bufsize=12000k")
            else:
                print(f"   - GPU Options: Using NVENC hardware acceleration")
            
            final_video.write_videofile(  # type: ignore
                output_path,
                codec=codec,
                audio_codec='aac',
                preset=preset,  # IMPROVED: Use quality preset instead of ultrafast
                threads=8,
                logger=None,
                bitrate=bitrate,  # IMPROVED: Add bitrate control
                ffmpeg_params=ffmpeg_params
            )
            
            final_video.close()
            
            print(f"✅ Compilation created successfully!")
            return output_path
            
        except Exception as e:
            print(f"❌ Error creating compilation: {e}")
            return None
        finally:
            # Clean up
            for clip in clips:
                try:
                    clip.close()
                except:
                    pass
            
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
    
   