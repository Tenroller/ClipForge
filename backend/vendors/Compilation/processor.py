"""
Cat Video Processor

This script processes YouTube cat videos by:
1. Reading video IDs from video_ids_to_process.txt
2. Randomly downloading videos from YouTube using yt-dlp
3. Detecting if videos are compilations and splitting them into scenes
4. Processing videos without database tracking
"""

import os
import random
import subprocess
import sys
from pathlib import Path
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
# Add moviepy scene detection import

from moviepy import VideoFileClip
from moviepy.video.tools.cuts import detect_scenes
import cv2
import numpy as np
import matplotlib.pyplot as plt
import re
import time
import yt_dlp
import shutil


class SimpleScene:
    """Simple scene class to make moviepy output compatible with scenedetect format"""
    def __init__(self, start_time, end_time):
        self.start_time = start_time
        self.end_time = end_time
    
    def get_seconds(self):
        """Return start time for compatibility with scenedetect format"""
        return self.start_time


def clean_text_for_filename(text):
    """
    Cleans text to make it suitable for filenames by removing emojis and special characters.
    """
    # Remove emojis and special characters, keep only alphanumeric and spaces
    cleaned = re.sub(r'[^\w\s-]', '', text)
    # Replace spaces with underscores and limit length
    cleaned = re.sub(r'\s+', '_', cleaned.strip())
    # Limit length to 50 characters
    return cleaned[:50]


class CatVideoProcessor:
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
        self.video_ids_file = "video_ids_to_process.txt"
        
        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(exist_ok=True)
        
        if ffmpeg_path:
            self.ffmpeg_path = ffmpeg_path
        else:
            self.ffmpeg_path = os.getenv('FFMPEG_PATH') or shutil.which('ffmpeg') or r'C:\ffmpeg\bin\ffmpeg.exe'

        self.check_dependencies()
    
    def check_dependencies(self):
        """Check if required dependencies are installed"""
        # Check ffmpeg
        try:
            result = subprocess.run([self.ffmpeg_path, '-version'], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print(f"Error: Could not run ffmpeg at: {self.ffmpeg_path}")
                print("Please install ffmpeg and ensure it is in your system's PATH or provide the path.")
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print(f"Error: ffmpeg not found at: {self.ffmpeg_path}")
            print("Please install ffmpeg and ensure it is in your system's PATH or provide the path.")
            return False
        
        # Check yt-dlp
        try:
            result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, timeout=10)
            if not result.stdout:
                print("Error: Missing required dependency: yt-dlp")
                print("You can install yt-dlp with: pip install yt-dlp")
                return False
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            print("Error: Missing required dependency: yt-dlp")
            print("You can install yt-dlp with: pip install yt-dlp")
            return False
        
        # Check yt-dlp Python library
        try:
            import yt_dlp
        except ImportError:
            print("Error: Missing required dependency: yt-dlp Python library")
            print("You can install yt-dlp with: pip install yt-dlp")
            return False
        
        return True
    
    def download_video(self, video_id, max_retries=3):
        """Download a video from YouTube using yt-dlp with improved error handling and YouTube compatibility"""
        print(f"Downloading video: {video_id}")
        
        # Create specific directory for this video
        video_output_dir = os.path.join(self.output_dir, video_id)
        os.makedirs(video_output_dir, exist_ok=True)
        
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        output_template = os.path.join(video_output_dir, f"{video_id}.%(ext)s")
        
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1} of {max_retries}")
                
                # Enhanced yt-dlp options to handle YouTube's recent changes
                ydl_opts = {
                    # Explicitly prioritize high quality formats
                    'format': (
                        'bestvideo[height>=1080][ext=mp4]+bestaudio[ext=m4a]/'  # 1080p+ MP4 video with M4A audio
                        'bestvideo[height>=1080]+bestaudio/'   # 1080p+ video with any audio
                        'bestvideo[height>=720][ext=mp4]+bestaudio[ext=m4a]/'   # 720p+ MP4 video with M4A audio
                        'bestvideo[height>=720]+bestaudio/'    # 720p+ video with any audio
                        'best[height>=1080]/'                  # Combined file 1080p+
                        'best[height>=720]/'                   # Combined file 720p+
                        'best[ext=mp4]/'                       # Best MP4 format
                        'best'                                 # Final fallback
                    ),
                    'outtmpl': output_template,
                    'noplaylist': True,
                    'extractaudio': False,
                    'quiet': False,
                    'no_warnings': False,
                    'writeinfojson': True,  # Write info to debug quality selection
                    'listformats': True,    # List all available formats before downloading
                    'overwrites': True,     # Force overwrite existing files to get higher quality
                    'writesubtitles': False,
                    'writeautomaticsub': False,
                    'ratelimit': 2000 * 1024,  # Higher rate limit for better quality downloads
                    'sleep_interval': 0.5,     # Reduced sleep interval for faster downloads
                    'retries': 5,
                    'fragment_retries': 10,
                    'retry_sleep': 'linear=1:5',
                    
                    # Quality-focused options
                    'prefer_free_formats': False,  # Don't prefer free formats over better quality
                    'prefer_insecure': False,
                    'merge_output_format': 'mp4',  # Ensure final output is MP4
                    'postprocessor_args': {
                        'ffmpeg': [
                            '-c:v', 'copy',    # Copy video codec when possible (no re-encoding)
                            '-c:a', 'copy',    # Copy audio codec when possible
                            '-avoid_negative_ts', 'make_zero'  # Fix timing issues
                        ]
                    },
                    
                    # Enhanced headers and user agent
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                    },
                    
                    # Use default YouTube extractor settings for better compatibility
                    
                    # Additional options for stability
                    'ignoreerrors': False,
                    'no_color': False,
                    'extract_flat': False,
                    'writethumbnail': False,
                    'simulate': False,
                    'listformats': False,
                    'prefer_ffmpeg': True,
                    'keepvideo': False,
                    'socket_timeout': 30,
                    'source_address': None,
                    'force_ipv4': False,
                    'force_ipv6': False,
                    'cn_verification_proxy': None,
                    'geo_verification_proxy': None,
                    'geo_bypass': True,
                    'geo_bypass_country': None,
                    'geo_bypass_ip_block': None,
                    'file_access_retries': 3,
                    'skip_unavailable_fragments': True,
                    'concurrent_fragment_downloads': 1,
                    'buffersize': 1024,
                    'noresizebuffer': False,
                    'http_chunk_size': None,
                    'external_downloader': None,
                    'hls_use_mpegts': None,
                    'hls_prefer_native': None,
                    'hls_prefer_ffmpeg': None,
                    'hls_split_discontinuity': False,
                    'playlist_items': None,
                    'playlistreverse': False,
                    'playlistrandom': False,
                    'matchtitle': None,
                    'rejecttitle': None,
                    'max_downloads': None,
                    'min_filesize': None,
                    'max_filesize': None,
                    'date': None,
                    'datebefore': None,
                    'dateafter': None,
                    'min_views': None,
                    'max_views': None,
                    'match_filter': None,
                    'age_limit': None,
                    'download_archive': None,
                    'break_on_existing': False,
                    'break_on_reject': False,
                    'cookiefile': None,
                    'cookiesfrombrowser': None,
                    'nocheckcertificate': False,
                    'prefer_insecure': False,
                    'proxy': None,
                    'cachedir': None,
                    'verbose': False,
                    'dump_single_json': False,
                    'dump_json': False,
                    'force_json': False,
                    'print_json': False,
                    'force_write_download_archive': False,
                    'simulate': False,
                    'skip_download': False,
                    'geturl': False,
                    'gettitle': False,
                    'getid': False,
                    'getthumbnail': False,
                    'getdescription': False,
                    'getduration': False,
                    'getfilename': False,
                    'getformat': False,
                    'dumpjson': False,
                    'dumpsingle': False,
                    'print_traffic': False,
                    'call_home': False,
                    'ffmpeg_location': self.ffmpeg_path,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Get video info first to check if video is accessible
                    try:
                        info = ydl.extract_info(video_url, download=False)
                        
                        if not info:
                            print(f"Warning: No info found for this video ({video_id})")
                            return None, None
                        
                        # Check video properties
                        video_title = info.get('title', 'Unknown')
                        duration = info.get('duration', 0)
                      
                        is_live = info.get('is_live', False)
                        availability = info.get('availability', 'unknown')
                        
                        print(f"Video title: {video_title}")
                        print(f"Duration: {duration} seconds ({duration/60:.1f} minutes)")
                        print(f"Availability: {availability}")
                        
                        # Check for problematic videos
                        if availability in ['private', 'premium_only', 'subscriber_only', 'needs_auth']:
                            print(f"Video is not publicly available: {availability}")
                            return None, None
                    
                        if is_live:
                            print(f"Skipping live video: {video_title}")
                            return None, None
                        
                        if availability != 'public':
                            print(f"Skipping private/unavailable video: {video_title} ({availability})")
                            return None, None
                        
                      
                      
                        
                        # Check if formats are available and log quality info
                        formats = info.get('formats', [])
                        if not formats:
                            print("Warning: No formats found for this video")
                            return None, None
                        
                        # Log available quality information
                        if formats:
                            # Filter out None heights and get the max
                            valid_heights = [f.get('height', 0) for f in formats if f.get('height') is not None and isinstance(f.get('height'), (int, float))]
                            best_height = max(valid_heights) if valid_heights else 0
                            print(f"📺 Best available quality: {best_height}p")
                            
                            # Count quality tiers
                            quality_counts = {}
                            for f in formats:
                                height = f.get('height', 0)
                                # Ensure height is a number before comparison
                                if height is not None and isinstance(height, (int, float)):
                                    if height >= 2160:
                                        quality_counts['4K'] = quality_counts.get('4K', 0) + 1
                                    elif height >= 1440:
                                        quality_counts['1440p'] = quality_counts.get('1440p', 0) + 1
                                    elif height >= 1080:
                                        quality_counts['1080p'] = quality_counts.get('1080p', 0) + 1
                                    elif height >= 720:
                                        quality_counts['720p'] = quality_counts.get('720p', 0) + 1
                            
                            if quality_counts:
                                quality_summary = ', '.join([f"{k}: {v} formats" for k, v in quality_counts.items()])
                                print(f"📊 Quality tiers available: {quality_summary}")
                        
                        # Proceed with download
                        print("🔥 Downloading highest quality available...")
                        ydl.download([video_url])
                        
                        # Find the downloaded file
                        downloaded_files = []
                        for file in os.listdir(video_output_dir):
                            if file.startswith(video_id) and file.endswith(('.mp4', '.mkv', '.webm', '.avi')):
                                downloaded_files.append(os.path.join(video_output_dir, file))
                        
                        if not downloaded_files:
                            print(f"No video file found after download in {video_output_dir}")
                            continue
                        
                        # Use the first downloaded video file
                        video_path = downloaded_files[0]
                        print(f"Downloaded: {video_path}")
                        
                        # Debug: Show actual video quality information
                        video_info_actual = self.get_video_info(video_path)
                        if video_info_actual:
                            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
                            bitrate_mbps = (file_size_mb * 8) / (duration / 60) if duration > 0 else 0
                            print(f"📊 Downloaded video quality:")
                            print(f"   - Resolution: {video_info_actual.get('width', 'unknown')}x{video_info_actual.get('height', 'unknown')}")
                            print(f"   - Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
                            print(f"   - File size: {file_size_mb:.1f} MB")
                            print(f"   - Estimated bitrate: {bitrate_mbps:.2f} Mbps")
                            
                            # Warn if quality seems low
                            video_height = video_info_actual.get('height', 0)
                            if video_height is not None and isinstance(video_height, (int, float)):
                                if video_height < 480:
                                    print(f"⚠️  WARNING: Video resolution is below 480p - very low quality!")
                                elif bitrate_mbps < 1.0:
                                    print(f"⚠️  WARNING: Video bitrate is below 1 Mbps - low quality for this duration!")
                        
                        # Check if info.json was created for format debugging
                        info_json_path = os.path.join(video_output_dir, f"{video_id}.info.json")
                        if os.path.exists(info_json_path):
                            try:
                                import json
                                with open(info_json_path, 'r', encoding='utf-8') as f:
                                    info_data = json.load(f)
                                format_id = info_data.get('format_id', 'unknown')
                                format_note = info_data.get('format_note', 'unknown')
                                vcodec = info_data.get('vcodec', 'unknown')
                                acodec = info_data.get('acodec', 'unknown')
                                print(f"📋 Format details: {format_id} ({format_note}) - Video: {vcodec}, Audio: {acodec}")
                                
                                # Clean up info file
                                os.remove(info_json_path)
                            except Exception as e:
                                print(f"Could not read format info: {e}")
                        
                        return video_path, video_title
                        
                    except yt_dlp.utils.DownloadError as e:
                        print(f"Download error for {video_id}: {e}")
                        if "Private video" in str(e) or "Video unavailable" in str(e):
                            return None, None
                        # Fall through to retry for other errors
                    
            except Exception as e:
                print(f"An error occurred during download attempt {attempt + 1}: {e}")
            
            # Wait before retrying
            sleep_time = 2 ** attempt
            print(f"Waiting {sleep_time} seconds before retrying...")
            time.sleep(sleep_time)
            
        print(f"Failed to download video {video_id} after {max_retries} retries.")
        return None, None
    
    def is_compilation_video(self, video_path, method: str = 'scenedetect'):
        """
        Determine if a video is a compilation by analyzing scene changes
        A compilation typically has many rapid scene changes
        
        Args:
            video_path: Path to the video file
            method: Detection method - 'scenedetect' or 'moviepy'
        """
        # Use the unified analyze_video_scenes method
        analysis = self.analyze_video_scenes(video_path, method=method)
        return analysis.get('is_compilation', False)
    
    def get_video_duration(self, video_path):
        """Get video duration using ffprobe directly (FFmpeg 7+ compatible)"""
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                '-of', 'csv=p=0', video_path
            ], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            print(f"Error getting video duration: {e}")
        return 0
    
    def get_video_info(self, video_path):
        """Get comprehensive video information using ffprobe directly (FFmpeg 7+ compatible)"""
        try:
            print(f"🔍 Getting video info for: {video_path}")

            # First, try a simple ffprobe command to check if the file is accessible
            ffprobe_path = os.environ.get('FFPROBE_BINARY', r'C:\ffmpeg\bin\ffprobe.exe')
            simple_result = subprocess.run([
                ffprobe_path, '-v', 'error', video_path
            ], capture_output=True, text=True, timeout=5)

            if simple_result.returncode != 0:
                print(f"❌ ffprobe basic check failed: {simple_result.stderr}")
                return None

            result = subprocess.run([
                ffprobe_path, '-v', 'quiet', '-show_entries',
                'stream=width,height,duration,r_frame_rate,codec_name,codec_type',
                '-of', 'json', video_path
            ], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                # Robustly check for streams key and type
                if 'streams' in data and isinstance(data['streams'], list):
                    video_stream = next((stream for stream in data['streams'] if stream.get('codec_type') == 'video'), None)
                    if video_stream:
                        # Safely convert values to appropriate types
                        duration = video_stream.get('duration', 0)
                        width = video_stream.get('width', 0)
                        height = video_stream.get('height', 0)
                        fps_str = video_stream.get('r_frame_rate', '30/1')
                        
                        # Convert to appropriate types with error handling
                        try:
                            duration = float(duration) if duration is not None else 0.0
                        except (ValueError, TypeError):
                            duration = 0.0
                            
                        try:
                            width = int(width) if width is not None else 0
                        except (ValueError, TypeError):
                            width = 0
                            
                        try:
                            height = int(height) if height is not None else 0
                        except (ValueError, TypeError):
                            height = 0
                            
                        try:
                            fps = eval(fps_str) if fps_str and fps_str != 'N/A' else 30.0
                        except (ValueError, TypeError, ZeroDivisionError):
                            fps = 30.0
                        
                        return {
                            'duration': duration,
                            'width': width,
                            'height': height,
                            'fps': fps,
                            'codec': video_stream.get('codec_name', 'unknown')
                        }
                    else:
                        print(f"No video stream found in ffprobe output for {video_path}. Full output: {data}")
                else:
                    print(f"No 'streams' key or not a list in ffprobe output for {video_path}. Full output: {data}")
        except Exception as e:
            print(f"Error getting video info for {video_path}: {e}")

            # Fallback: Try to get basic info using OpenCV
            try:
                print(f"🔄 Trying OpenCV fallback for {video_path}")
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    duration = total_frames / fps if fps > 0 else 0
                    cap.release()

                    print(f"✅ OpenCV fallback successful: {width}x{height}, {duration:.1f}s, {fps}fps")
                    return {
                        'duration': duration,
                        'width': width,
                        'height': height,
                        'fps': fps,
                        'codec': 'unknown'
                    }
                else:
                    print(f"❌ OpenCV fallback failed: could not open video")
            except Exception as cv_e:
                print(f"❌ OpenCV fallback failed: {cv_e}")

        return None
    
    def detect_pillarboxes_opencv(self, video_path, sample_frames=10, threshold=20):
        """
        Detect pillarboxes by analyzing the brightness of left and right edges
        across multiple frames.
        
        Args:
            video_path: Path to the video file
            sample_frames: Number of frames to sample for detection
            threshold: Brightness threshold to consider as black bar
        
        Returns:
            tuple: (left_crop, right_crop) - pixels to crop from each side
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Sample frames evenly throughout the video
        frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
        
        left_crops = []
        right_crops = []
        
        for frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
                
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect left pillarbox
            left_crop = 0
            for x in range(width // 3):  # Check up to 1/3 of width
                column = gray[:, x]
                if np.mean(column.astype(np.float64)) > threshold:
                    left_crop = x
                    break
            
            # Detect right pillarbox
            right_crop = 0
            for x in range(width - 1, width * 2 // 3, -1):  # Check from right
                column = gray[:, x]
                if np.mean(column.astype(np.float64)) > threshold:
                    right_crop = width - x - 1
                    break
            
            left_crops.append(left_crop)
            right_crops.append(right_crop)
        
        cap.release()
        
        # Use the most common crop values
        left_crop = max(set(left_crops), key=left_crops.count)
        right_crop = max(set(right_crops), key=right_crops.count)
        
        return left_crop, right_crop

    def detect_blurred_pillarboxes(self, video_path, sample_frames=10, variance_threshold=50):
        """
        Detect blurred pillarboxes by analyzing texture variance and color consistency.
        Works better for blurred/gradual transitions than sharp black bars.
        
        Args:
            video_path: Path to the video file
            sample_frames: Number of frames to sample for detection
            variance_threshold: Texture variance threshold (lower = more uniform)
        
        Returns:
            tuple: (left_crop, right_crop) - pixels to crop from each side
        """
        print(f"[Blurred Detection] Starting with variance_threshold={variance_threshold}")
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"[Blurred Detection] Video: {width}x{height}, {total_frames} frames")
        
        frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
        
        left_boundaries = []
        right_boundaries = []
        
        for i, frame_idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate texture variance for each column
            variances = []
            for x in range(width):
                column = gray[:, x]
                # Use local variance to detect texture
                variance = np.var(column.astype(np.float64))
                variances.append(variance)
            
            variances = np.array(variances)
            
            # Smooth the variance curve to reduce noise
            try:
                from scipy.ndimage import gaussian_filter1d
                smoothed_variances = gaussian_filter1d(variances, sigma=8)  # More smoothing
            except ImportError:
                # Fallback: larger moving average if scipy not available
                smoothed_variances = np.convolve(variances, np.ones(15)/15, mode='same')
            
            # More sophisticated boundary detection
            # Find peaks in variance that indicate content boundaries
            max_var = np.max(smoothed_variances)
            mean_var = np.mean(smoothed_variances)
            
            # More conservative dynamic threshold
            dynamic_threshold = max(variance_threshold * 0.7, float(mean_var * 0.6))
            
            # Look for the main content region by finding the largest high-variance region
            # This helps avoid detecting noise as content boundaries
            
            # Find all regions above threshold
            high_var_regions = smoothed_variances > dynamic_threshold
            
            # Find start and end of the largest continuous region
            if np.any(high_var_regions):
                # Find all continuous regions
                diff = np.diff(np.concatenate(([False], high_var_regions, [False])).astype(int))
                starts = np.where(diff == 1)[0]
                ends = np.where(diff == -1)[0]
                
                if len(starts) > 0 and len(ends) > 0:
                    # Find the largest region
                    region_sizes = ends - starts
                    largest_region_idx = np.argmax(region_sizes)
                    
                    left_boundary = starts[largest_region_idx]
                    right_boundary = ends[largest_region_idx] - 1
                    
                    # Add some padding to avoid cutting into content
                    padding = max(5, width // 100)
                    left_boundary = max(0, left_boundary - padding)
                    right_boundary = min(width - 1, right_boundary + padding)
                else:
                    left_boundary = 0
                    right_boundary = width - 1
            else:
                left_boundary = 0
                right_boundary = width - 1
            
            left_boundaries.append(left_boundary)
            right_boundaries.append(width - right_boundary - 1)
            
            if i == 0:  # Debug info for first frame
                print(f"[Blurred Detection] Frame {frame_idx}: max_var={max_var:.2f}, mean_var={mean_var:.2f}, threshold={dynamic_threshold:.2f}")
                print(f"[Blurred Detection] Frame {frame_idx}: left_boundary={left_boundary}, right_boundary={right_boundary}")
        
        cap.release()
        
        # Filter outliers before taking median
        left_boundaries = np.array(left_boundaries)
        right_boundaries = np.array(right_boundaries)
        
        # Remove extreme outliers (beyond 2 standard deviations)
        if len(left_boundaries) > 3:  # Only filter if we have enough samples
            left_mean = np.mean(left_boundaries)
            left_std = np.std(left_boundaries)
            left_mask = np.abs(left_boundaries - left_mean) <= 2 * left_std
            left_boundaries = left_boundaries[left_mask]
            
            right_mean = np.mean(right_boundaries)
            right_std = np.std(right_boundaries)
            right_mask = np.abs(right_boundaries - right_mean) <= 2 * right_std
            right_boundaries = right_boundaries[right_mask]
        
        # Use median values for robustness
        left_crop = int(np.median(left_boundaries)) if len(left_boundaries) > 0 else 0
        right_crop = int(np.median(right_boundaries)) if len(right_boundaries) > 0 else 0
        
        # Additional validation: ensure we're not cropping too much
        if left_crop + right_crop > width * 0.7:
            print(f"[Blurred Detection] WARNING: Would crop {left_crop + right_crop}px of {width}px, reducing...")
            # Scale down proportionally
            scale_factor = (width * 0.6) / (left_crop + right_crop)
            left_crop = int(left_crop * scale_factor)
            right_crop = int(right_crop * scale_factor)
        
        print(f"[Blurred Detection] All boundaries: left={list(left_boundaries)}, right={list(right_boundaries)}")
        print(f"[Blurred Detection] Final result: left_crop={left_crop}, right_crop={right_crop}")
        
        return left_crop, right_crop

    def detect_pillarboxes_edge_detection(self, video_path, sample_frames=10):
        """
        Detect pillarboxes using edge detection to find the content boundaries.
        
        Args:
            video_path: Path to the video file
            sample_frames: Number of frames to sample
        
        Returns:
            tuple: (left_crop, right_crop) - pixels to crop from each side
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
        
        left_boundaries = []
        right_boundaries = []
        
        for frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            # Convert to grayscale and apply edge detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            # Sum edges vertically to find content boundaries
            vertical_edges = np.sum(edges, axis=0)
            
            # Find first and last significant edge positions
            edge_threshold = np.max(vertical_edges) * 0.1
            
            # Find left boundary
            left_boundary = 0
            for x in range(width // 3):
                if vertical_edges[x] > edge_threshold:
                    left_boundary = x
                    break
            
            # Find right boundary
            right_boundary = width - 1
            for x in range(width - 1, width * 2 // 3, -1):
                if vertical_edges[x] > edge_threshold:
                    right_boundary = x
                    break
            
            left_boundaries.append(left_boundary)
            right_boundaries.append(width - right_boundary - 1)
        
        cap.release()
        
        # Use median values for more robustness
        left_crop = int(np.median(left_boundaries))
        right_crop = int(np.median(right_boundaries))
        
        return left_crop, right_crop

    def detect_symmetric_pillarboxes(self, video_path, sample_frames=10):
        """
        Detect pillarboxes assuming the content is centered with symmetric bars.
        This is the most common case for pillarboxed videos.
        
        Args:
            video_path: Path to the video file
            sample_frames: Number of frames to sample for detection
        
        Returns:
            tuple: (left_crop, right_crop) - pixels to crop from each side (should be equal)
        """
        print(f"[Symmetric Detection] Starting symmetric pillarbox detection")
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"[Symmetric Detection] Video: {width}x{height}, {total_frames} frames")
        
        frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
        
        center = width // 2
        left_boundaries = []
        right_boundaries = []
        
        for i, frame_idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate variance for each column
            variances = []
            for x in range(width):
                column = gray[:, x]
                variance = np.var(column.astype(np.float64))
                variances.append(variance)
            
            variances = np.array(variances)
            
            # Smooth the variance curve
            try:
                from scipy.ndimage import gaussian_filter1d
                smoothed_variances = gaussian_filter1d(variances, sigma=8)
            except ImportError:
                smoothed_variances = np.convolve(variances, np.ones(15)/15, mode='same')
            
            # Use a more conservative threshold - look for significant content
            max_var = np.max(smoothed_variances)
            mean_var = np.mean(smoothed_variances)
            
            # Use a lower threshold to better detect content boundaries
            threshold = mean_var + (max_var - mean_var) * 0.3  # 30% above mean toward max
            
            # Find content boundaries by looking from edges inward
            # Look for where variance significantly increases (entering content)
            
            # Find left boundary - start from left edge and go right
            left_boundary = 0
            for x in range(width // 2):  # Only search left half
                if smoothed_variances[x] > threshold:
                    # Found potential content start, verify with window
                    window_end = min(width, x + 30)
                    window_mean = np.mean(smoothed_variances[x:window_end])
                    if window_mean > threshold * 0.8:  # Sustained high variance
                        left_boundary = max(0, x - 5)  # Small padding
                        break
            
            # Find right boundary - start from right edge and go left  
            right_boundary = width - 1
            for x in range(width - 1, width // 2, -1):  # Only search right half
                if smoothed_variances[x] > threshold:
                    # Found potential content end, verify with window
                    window_start = max(0, x - 30)
                    window_mean = np.mean(smoothed_variances[window_start:x+1])
                    if window_mean > threshold * 0.8:  # Sustained high variance
                        right_boundary = min(width - 1, x + 5)  # Small padding
                        break
            
            left_boundaries.append(left_boundary)
            right_boundaries.append(width - 1 - right_boundary)  # Convert to crop amount
            
            if i == 0:  # Debug info for first frame
                content_width = right_boundary - left_boundary
                print(f"[Symmetric Detection] Frame {frame_idx}: max_var={max_var:.2f}, mean_var={mean_var:.2f}, threshold={threshold:.2f}")
                print(f"[Symmetric Detection] Frame {frame_idx}: left_boundary={left_boundary}, right_boundary={right_boundary}, content_width={content_width}")
        
        cap.release()
        
        # Filter out unreasonable boundaries
        left_boundaries = np.array(left_boundaries)
        right_boundaries = np.array(right_boundaries)
        
        # Remove outliers
        if len(left_boundaries) > 3:
            left_q75, left_q25 = np.percentile(left_boundaries, [75, 25])
            left_iqr = left_q75 - left_q25
            left_lower = left_q25 - 1.5 * left_iqr
            left_upper = left_q75 + 1.5 * left_iqr
            left_mask = (left_boundaries >= left_lower) & (left_boundaries <= left_upper)
            left_boundaries = left_boundaries[left_mask]
            
            right_q75, right_q25 = np.percentile(right_boundaries, [75, 25])
            right_iqr = right_q75 - right_q25
            right_lower = right_q25 - 1.5 * right_iqr
            right_upper = right_q75 + 1.5 * right_iqr
            right_mask = (right_boundaries >= right_lower) & (right_boundaries <= right_upper)
            right_boundaries = right_boundaries[right_mask]
        
        # Calculate symmetric crop
        if len(left_boundaries) > 0 and len(right_boundaries) > 0:
            left_crop = int(np.median(left_boundaries))
            right_crop = int(np.median(right_boundaries))
            
            # Force symmetry by using the average
            symmetric_crop = (left_crop + right_crop) // 2
            
            # Validate result - reject if too extreme
            if symmetric_crop > width * 0.4:  # Don't crop more than 40% per side
                print(f"[Symmetric Detection] Rejecting extreme crop: {symmetric_crop} > {width * 0.4:.0f}")
                return 0, 0
                
            if symmetric_crop < 5:  # Too small to be meaningful
                print(f"[Symmetric Detection] Rejecting tiny crop: {symmetric_crop}")
                return 0, 0
            
            print(f"[Symmetric Detection] Raw boundaries: left={list(left_boundaries)}, right={list(right_boundaries)}")
            print(f"[Symmetric Detection] Median crops: left={left_crop}, right={right_crop}")
            print(f"[Symmetric Detection] Final symmetric crop per side: {symmetric_crop}")
            
            return symmetric_crop, symmetric_crop
        else:
            print(f"[Symmetric Detection] No valid boundaries found")
            return 0, 0

    def detect_pillarboxes_advanced(self, video_path, sample_frames=10, method='edge'):
        """
        Advanced pillarbox detection that combines multiple methods for better accuracy.
        Handles both sharp and blurred pillarboxes.
        
        Args:
            video_path: Path to the video file
            sample_frames: Number of frames to sample
            method: 'auto', 'sharp', 'blurred', 'edge', 'symmetric', or 'combined'
        
        Returns:
            tuple: (left_crop, right_crop) - pixels to crop from each side
        """
        print(f"[Advanced Detection] Using method: {method}")
        
        # Get video dimensions for validation
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
        else:
            width, height = 640, 360  # fallback
        
        try:
            if method == 'sharp':
                return self.detect_pillarboxes_opencv(video_path, sample_frames)
            elif method == 'blurred':
                return self.detect_blurred_pillarboxes(video_path, sample_frames)
            elif method == 'edge':
                return self.detect_pillarboxes_edge_detection(video_path, sample_frames)
            elif method == 'symmetric':
                return self.detect_symmetric_pillarboxes(video_path, sample_frames)
            elif method == 'combined':
                # Try multiple methods and use consensus
                results = []
                try:
                    results.append(('symmetric', self.detect_symmetric_pillarboxes(video_path, sample_frames)))
                except Exception as e:
                    print(f"[Combined] Symmetric detection failed: {e}")
                
                try:
                    results.append(('blurred', self.detect_blurred_pillarboxes(video_path, sample_frames)))
                except Exception as e:
                    print(f"[Combined] Blurred detection failed: {e}")
                
                try:
                    results.append(('edge', self.detect_pillarboxes_edge_detection(video_path, sample_frames)))
                except Exception as e:
                    print(f"[Combined] Edge detection failed: {e}")
                
                if not results:
                    print("[Combined] All methods failed")
                    return 0, 0
                
                # Prefer symmetric results if available and reasonable
                symmetric_results = [r for r in results if r[0] == 'symmetric']
                if symmetric_results:
                    sym_left, sym_right = symmetric_results[0][1]
                    # Use symmetric if it's reasonable (not too extreme)
                    if sym_left == sym_right and sym_left > 0 and sym_left < width * 0.4:
                        print(f"[Combined] Using symmetric result: {sym_left}, {sym_right}")
                        return sym_left, sym_right
                
                # Otherwise use consensus from all methods
                left_crops = [result[1][0] for result in results]
                right_crops = [result[1][1] for result in results]
                
                # Force symmetry in consensus by averaging the crops
                avg_crop = (np.median(left_crops) + np.median(right_crops)) / 2
                symmetric_crop = int(avg_crop / 2)  # Divide by 2 since it's total crop
                
                print(f"[Combined] Individual results: {results}")
                print(f"[Combined] Forced symmetric consensus: left={symmetric_crop}, right={symmetric_crop}")
                
                return symmetric_crop, symmetric_crop
            
            elif method == 'auto':
                # Auto-detect the best method based on video characteristics
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    return 0, 0
                
                # Sample a few frames to determine the best method
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                # Get a middle frame for analysis
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
                ret, frame = cap.read()
                cap.release()
                
                if not ret:
                    return 0, 0
                
                # Analyze the frame to determine pillarbox type
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Check left and right edges for uniformity
                edge_width = max(width//15, 50)  # Use wider edge for better analysis
                left_edge = gray[:, :edge_width]
                right_edge = gray[:, -edge_width:]
                
                left_var = np.var(left_edge.astype(np.float64))
                right_var = np.var(right_edge.astype(np.float64))
                avg_var = (left_var + right_var) / 2
                
                print(f"[Auto] Frame analysis: width={width}, height={height}")
                print(f"[Auto] Edge analysis: left_var={left_var:.2f}, right_var={right_var:.2f}, avg_var={avg_var:.2f}")
                
                # More sophisticated analysis for blurred pillarboxes
                # Check if the edges look like stretched/blurred content
                left_mean = np.mean(left_edge.astype(np.float64))
                right_mean = np.mean(right_edge.astype(np.float64))
                center_width = width // 3
                center_region = gray[:, center_width:width-center_width]
                center_var = np.var(center_region.astype(np.float64))
                
                print(f"[Auto] Content analysis: center_var={center_var:.2f}, left_mean={left_mean:.2f}, right_mean={right_mean:.2f}")
                
                # For most pillarboxed videos, try symmetric first
                print("[Auto] Trying symmetric detection first (most common case)")
                return self.detect_symmetric_pillarboxes(video_path, sample_frames)
            
            else:
                print(f"[Advanced] Unknown method: {method}, using auto")
                return self.detect_pillarboxes_advanced(video_path, sample_frames, 'auto')
                
        except Exception as e:
            print(f"[Advanced Detection] Error: {e}")
            return 0, 0

    def detect_pillarboxes_transition_based(self, video_path, sample_frames=10):
        """
        Detect pillarboxes by finding the transition zones between blurred/stretched content 
        and actual video content. This method is more conservative and focuses on identifying
        the boundaries where pillarboxes end and real content begins.
        
        Args:
            video_path: Path to the video file
            sample_frames: Number of frames to sample for detection
        
        Returns:
            tuple: (left_crop, right_crop) - pixels to crop from each side
        """
        print(f"[Transition Detection] Starting transition-based pillarbox detection")
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"[Transition Detection] Video: {width}x{height}, {total_frames} frames")
        
        frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
        
        left_boundaries = []
        right_boundaries = []
        
        for i, frame_idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate multiple features for each column
            texture_scores = []
            brightness_scores = []
            gradient_scores = []
            
            for x in range(width):
                column = gray[:, x]
                
                # 1. Texture analysis - local variation
                texture_score = np.std(column.astype(np.float64))
                texture_scores.append(texture_score)
                
                # 2. Brightness analysis - pillarboxes often have different brightness
                brightness_score = np.mean(column.astype(np.float64))
                brightness_scores.append(brightness_score)
                
                # 3. Gradient analysis - transitions between regions
                if x > 0:
                    prev_column = gray[:, x-1]
                    gradient = np.mean(np.abs(column.astype(float) - prev_column.astype(float)))
                    gradient_scores.append(gradient)
                else:
                    gradient_scores.append(0)
            
            # Convert to numpy arrays
            texture_scores = np.array(texture_scores)
            brightness_scores = np.array(brightness_scores)
            gradient_scores = np.array(gradient_scores)
            
            # Smooth all curves
            try:
                from scipy.ndimage import gaussian_filter1d
                smooth_texture = gaussian_filter1d(texture_scores, sigma=6)
                smooth_brightness = gaussian_filter1d(brightness_scores, sigma=6)
                smooth_gradient = gaussian_filter1d(gradient_scores, sigma=4)
            except ImportError:
                smooth_texture = np.convolve(texture_scores, np.ones(12)/12, mode='same')
                smooth_brightness = np.convolve(brightness_scores, np.ones(12)/12, mode='same')
                smooth_gradient = np.convolve(gradient_scores, np.ones(8)/8, mode='same')
            
            # Strategy: Look for transitions from low to high complexity
            # Pillarboxes typically have lower, more uniform complexity
            
            # Find the main content region by looking for sustained high texture
            texture_threshold = np.mean(smooth_texture) + 0.3 * (np.max(smooth_texture) - np.mean(smooth_texture))
            
            # Look for transition points where texture significantly increases
            # This indicates moving from pillarbox to content
            
            # Left boundary: scan from left, find where texture starts increasing significantly
            left_boundary = 0
            baseline_texture = np.mean(smooth_texture[:width//6])  # Sample from leftmost region
            
            for x in range(width//6, width//2):  # Don't scan too far right
                current_texture = smooth_texture[x]
                
                # Look for significant increase from baseline
                if current_texture > baseline_texture * 1.4:  # 40% increase
                    # Verify this is sustained increase by checking nearby region
                    window_start = max(0, x - 15)
                    window_end = min(width, x + 15)
                    window_avg = np.mean(smooth_texture[window_start:window_end])
                    
                    if window_avg > baseline_texture * 1.3:  # Sustained increase
                        left_boundary = max(0, x - 10)  # Conservative padding
                        break
            
            # Right boundary: scan from right, find where texture starts increasing significantly
            right_boundary = width - 1
            baseline_texture_right = np.mean(smooth_texture[-width//6:])  # Sample from rightmost region
            
            for x in range(width - width//6, width//2, -1):  # Don't scan too far left
                current_texture = smooth_texture[x]
                
                # Look for significant increase from baseline
                if current_texture > baseline_texture_right * 1.4:  # 40% increase
                    # Verify this is sustained increase by checking nearby region
                    window_start = max(0, x - 15)
                    window_end = min(width, x + 15)
                    window_avg = np.mean(smooth_texture[window_start:window_end])
                    
                    if window_avg > baseline_texture_right * 1.3:  # Sustained increase
                        right_boundary = min(width - 1, x + 10)  # Conservative padding
                        break
            
            # Additional validation using brightness and gradient information
            # Pillarboxes often have different brightness characteristics
            
            # Check if the detected boundaries make sense
            left_region_brightness = np.mean(smooth_brightness[:left_boundary]) if left_boundary > 0 else 0
            right_region_brightness = np.mean(smooth_brightness[right_boundary:]) if right_boundary < width - 1 else 0
            center_brightness = np.mean(smooth_brightness[left_boundary:right_boundary])
            
            # If detected regions have very different brightness, it might be correct
            brightness_diff_left = abs(left_region_brightness - center_brightness)
            brightness_diff_right = abs(right_region_brightness - center_brightness)
            
            left_crop = left_boundary
            right_crop = width - 1 - right_boundary
            
            left_boundaries.append(left_crop)
            right_boundaries.append(right_crop)
            
            if i == 0:  # Debug info for first frame
                content_width = right_boundary - left_boundary
                print(f"[Transition Detection] Frame {frame_idx}: texture_threshold={texture_threshold:.2f}")
                print(f"[Transition Detection] Frame {frame_idx}: baseline_left={baseline_texture:.2f}, baseline_right={baseline_texture_right:.2f}")
                print(f"[Transition Detection] Frame {frame_idx}: left_boundary={left_boundary}, right_boundary={right_boundary}, content_width={content_width}")
                print(f"[Transition Detection] Frame {frame_idx}: brightness_diff_left={brightness_diff_left:.2f}, brightness_diff_right={brightness_diff_right:.2f}")
                print(f"[Transition Detection] Frame {frame_idx}: left_crop={left_crop}, right_crop={right_crop}")
        
        cap.release()
        
        # Process results
        left_boundaries = np.array(left_boundaries)
        right_boundaries = np.array(right_boundaries)
        
        if len(left_boundaries) > 0 and len(right_boundaries) > 0:
            # Filter out extreme outliers (values that are too large)
            left_boundaries = left_boundaries[left_boundaries < width * 0.3]
            right_boundaries = right_boundaries[right_boundaries < width * 0.3]
            
            if len(left_boundaries) > 0 and len(right_boundaries) > 0:
                # Use median for robustness
                left_crop = int(np.median(left_boundaries))
                right_crop = int(np.median(right_boundaries))
                
                # Force symmetry (pillarboxes should be symmetric)
                symmetric_crop = (left_crop + right_crop) // 2
                
                # Conservative validation - don't crop too much
                if symmetric_crop >= 5 and symmetric_crop <= width * 0.25:  # Max 25% per side
                    print(f"[Transition Detection] Raw boundaries: left={list(left_boundaries)}, right={list(right_boundaries)}")
                    print(f"[Transition Detection] Median crops: left={left_crop}, right={right_crop}")
                    print(f"[Transition Detection] Final symmetric crop per side: {symmetric_crop}")
                    
                    return symmetric_crop, symmetric_crop
                else:
                    print(f"[Transition Detection] Crop too extreme or too small: {symmetric_crop}")
            else:
                print(f"[Transition Detection] No valid boundaries after filtering")
        
        print(f"[Transition Detection] No valid boundaries found")
        return 0, 0

    def detect_pillarboxes_yolov8(self, video_path, sample_frames=10, padding_ratio=0.05):
        """
        Detect pillarboxes using YOLOv8 object detection. Crops to the bounding box containing all detected objects.
        Args:
            video_path: Path to the video file
            sample_frames: Number of frames to sample for detection
            padding_ratio: Fraction of width to pad on each side
        Returns:
            tuple: (left_crop, right_crop) - pixels to crop from each side
        """
        print(f"[YOLOv8 Detection] Starting YOLOv8 object-based pillarbox detection")
        try:
            from ultralytics import YOLO  # type: ignore
            import torch  # type: ignore
        except ImportError:
            print("[YOLOv8 Detection] ultralytics not installed, falling back to vision methods")
            return self.detect_pillarboxes_transition_based(video_path, sample_frames)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[YOLOv8 Detection] Video: {width}x{height}, {total_frames} frames")

        # Load YOLOv8 model (nano for speed, or use 'yolov8m.pt' for more accuracy)
        model = YOLO('yolov8n.pt')
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model.to(device)

        frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
        all_boxes = []
        for frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue
            # YOLO expects RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = model(rgb, verbose=False)
            boxes = results[0].boxes.xyxy.cpu().numpy() if len(results) > 0 and hasattr(results[0], 'boxes') else []
            for box in boxes:
                x1, y1, x2, y2 = box[:4]
                all_boxes.append((x1, x2))
        cap.release()

        if not all_boxes:
            print("[YOLOv8 Detection] No objects detected, falling back to vision methods.")
            return self.detect_pillarboxes_transition_based(video_path, sample_frames)

        # Find the min/max x coordinates across all boxes
        min_x = min(x1 for x1, x2 in all_boxes)
        max_x = max(x2 for x1, x2 in all_boxes)
        # Add padding
        pad = int(width * padding_ratio)
        left = max(0, int(min_x) - pad)
        right = min(width, int(max_x) + pad)
        left_crop = left
        right_crop = width - right
        # Force symmetry if the difference is small
        if abs(left_crop - right_crop) < width * 0.05:
            avg_crop = (left_crop + right_crop) // 2
            left_crop = right_crop = avg_crop
        print(f"[YOLOv8 Detection] Cropping to: left={left_crop}, right={right_crop}")
        return left_crop, right_crop

    def crop_video_if_vertical_with_blur(self, video_path):
        """
        Detects if a video is a vertical video with added blur bars on the sides,
        and if so, crops it to its original vertical aspect ratio.
        Uses edge detection as the primary method, with fallback to YOLOv8 and then transition-based methods.
        Returns the path to the cropped video, or the original path if no cropping was needed.
        """
        print(f"Detecting and removing pillarboxes from {video_path}")

        # Debug: Check if file exists and is accessible
        if not os.path.exists(video_path):
            print(f"❌ File does not exist: {video_path}")
            return video_path

        try:
            file_size = os.path.getsize(video_path)
            print(f"✅ File exists: {video_path} ({file_size} bytes)")
        except Exception as e:
            print(f"❌ Cannot access file: {video_path} - {e}")
            return video_path

        debug_dir = "debug_frames"
        Path(debug_dir).mkdir(exist_ok=True)
        video_id = Path(video_path).stem
        video_info = self.get_video_info(video_path)
        if not video_info:
            print("Error: Could not get video info")
            return video_path
        width = video_info.get('width', 0)
        height = video_info.get('height', 0)
        print(f"[Crop Detection] Video dimensions: {width}x{height}")
        if height >= width:
            print("Video is already vertical or square. No cropping needed.")
            return video_path
        # Save a preview frame for debugging
        try:
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
                ret, frame = cap.read()
                if ret:
                    preview_path = os.path.join(debug_dir, f"{video_id}_original.png")
                    cv2.imwrite(preview_path, frame)
                    print(f"[Crop Detection] Saved preview frame: {preview_path}")
                cap.release()
        except Exception as e:
            print(f"[Crop Detection] Could not save preview frame: {e}")
        # Use edge detection as primary, fallback to YOLOv8, then transition-based
        try:
            left_crop, right_crop = self.detect_pillarboxes_edge_detection(video_path)
            print(f"[Crop Detection] [Edge] Detected pillarboxes: left={left_crop}px, right={right_crop}px")
            if left_crop == 0 and right_crop == 0:
                print("[Crop Detection] [Edge] No crop detected, falling back to YOLOv8.")
                left_crop, right_crop = self.detect_pillarboxes_yolov8(video_path)
                print(f"[Crop Detection] [YOLOv8] Detected pillarboxes: left={left_crop}px, right={right_crop}px")
                if left_crop == 0 and right_crop == 0:
                    print("[Crop Detection] [YOLOv8] No crop detected, falling back to transition-based.")
                    left_crop, right_crop = self.detect_pillarboxes_transition_based(video_path)
                    print(f"[Crop Detection] [Transition] Detected pillarboxes: left={left_crop}px, right={right_crop}px")
            crop_width = width - left_crop - right_crop
            if crop_width <= 0:
                print("[Crop Detection] Invalid crop width, no cropping needed")
                return video_path
            if left_crop >= width or right_crop >= width:
                print(f"[Crop Detection] Crop values too large: left={left_crop}, right={right_crop}, width={width}")
                return video_path
            if left_crop + right_crop >= width * 0.8:
                print(f"[Crop Detection] Would crop too much content ({left_crop + right_crop}px of {width}px)")
                return video_path
            min_crop_threshold = max(width * 0.02, 20)
            total_crop = left_crop + right_crop
            print(f"[Crop Detection] Total crop: {total_crop}px, threshold: {min_crop_threshold*2:.1f}px")
            if total_crop < min_crop_threshold * 2:
                print(f"[Crop Detection] Not enough cropping detected ({total_crop}px < {min_crop_threshold*2:.1f}px)")
                return video_path
            new_aspect_ratio = crop_width / height
            original_aspect_ratio = width / height
            print(f"[Crop Detection] Aspect ratios: original={original_aspect_ratio:.2f}, new={new_aspect_ratio:.2f}")
            if new_aspect_ratio >= original_aspect_ratio * 0.9:
                print(f"[Crop Detection] Not enough improvement in aspect ratio")
                return video_path
            if new_aspect_ratio > 1.8:
                print(f"[Crop Detection] Still too wide after cropping (ratio: {new_aspect_ratio:.2f})")
                return video_path
            print(f"[Crop Detection] ✓ Cropping approved: {width}x{height} -> {crop_width}x{height}")
            print(f"[Crop Detection] ✓ Aspect ratio: {original_aspect_ratio:.2f} -> {new_aspect_ratio:.2f}")
            try:
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
                    ret, frame = cap.read()
                    if ret:
                        crop_region = frame[:, left_crop:left_crop+crop_width]
                        region_variance = np.var(cv2.cvtColor(crop_region, cv2.COLOR_BGR2GRAY).astype(np.float64))
                        print(f"[Crop Detection] Crop region variance: {region_variance:.2f}")
                        if region_variance < 10:
                            print(f"[Crop Detection] Crop region appears empty (variance={region_variance:.2f})")
                            cap.release()
                            return video_path
                        preview_crop_path = os.path.join(debug_dir, f"{video_id}_crop_preview.png")
                        cv2.imwrite(preview_crop_path, crop_region)
                        print(f"[Crop Detection] Saved crop preview: {preview_crop_path}")
                        debug_frame = frame.copy()
                        cv2.line(debug_frame, (left_crop, 0), (left_crop, height-1), (0, 255, 0), 2)
                        cv2.line(debug_frame, (left_crop + crop_width, 0), (left_crop + crop_width, height-1), (0, 0, 255), 2)
                        debug_path = os.path.join(debug_dir, f"{video_id}_crop_lines.png")
                        cv2.imwrite(debug_path, debug_frame)
                        print(f"[Crop Detection] Saved debug frame with crop lines: {debug_path}")
                    cap.release()
            except Exception as e:
                print(f"[Crop Detection] Could not validate crop region: {e}")
            output_path = video_path.replace('.mp4', '_cropped.mp4')
            try:
                # Check for GPU availability and use hardware acceleration if available
                has_gpu = False
                try:
                    import torch
                    has_gpu = torch.cuda.is_available()
                except ImportError:
                    pass

                if has_gpu:
                    print("[Crop Detection] 🎮 GPU acceleration available - using NVENC encoding")
                    cmd = [
                        self.ffmpeg_path, '-y', '-i', video_path,
                        '-filter:v', f'crop={crop_width}:{height}:{left_crop}:0',
                        '-c:v', 'h264_nvenc',  # GPU-accelerated H.264 encoding
                        '-preset', 'fast',     # Fast preset for good performance
                        '-c:a', 'copy',
                        '-avoid_negative_ts', 'make_zero',
                        output_path
                    ]
                else:
                    print("[Crop Detection] 💻 Using CPU encoding (GPU not available)")
                    cmd = [
                        self.ffmpeg_path, '-y', '-i', video_path,
                        '-filter:v', f'crop={crop_width}:{height}:{left_crop}:0',
                        '-c:v', 'libx264',    # CPU H.264 encoding
                        '-preset', 'fast',     # Fast preset
                        '-c:a', 'copy',
                        '-avoid_negative_ts', 'make_zero',
                        output_path
                    ]

                print(f"[Crop Detection] Running FFmpeg: crop={crop_width}:{height}:{left_crop}:0")
                print(f"[Crop Detection] Using {'GPU (NVENC)' if has_gpu else 'CPU (libx264)'} encoding")
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"[Crop Detection] ✓ Successfully cropped video and saved to {output_path}")
                    output_info = self.get_video_info(output_path)
                    if output_info and output_info.get('duration', 0) > 0:
                        print(f"[Crop Detection] ✓ Output validation: {output_info['width']}x{output_info['height']}, {output_info['duration']:.1f}s")
                        return output_path
                    else:
                        print(f"[Crop Detection] ✗ Output file appears invalid")
                        return video_path
                else:
                    print(f"[Crop Detection] ✗ FFmpeg error: {result.stderr}", file=sys.stderr)
                    return video_path
            except Exception as e:
                print(f"[Crop Detection] ✗ Error cropping video: {e}", file=sys.stderr)
                return video_path
        except Exception as e:
            print(f"[Crop Detection] ✗ Error in detection pipeline: {e}")
            return video_path

    def split_video_with_ffmpeg(self, video_path, start_time, end_time, output_path):
        """Split a video segment using ffmpeg via subprocess with improved compatibility"""
        try:
            print(f"🎬 Splitting scene: {start_time:.1f}s to {end_time:.1f}s -> {os.path.basename(output_path)}")

            # Check if ffmpeg is available
            if not os.path.exists(self.ffmpeg_path):
                print(f"❌ FFmpeg not found at: {self.ffmpeg_path}")
                return False

            # Check if input video exists
            if not os.path.exists(video_path):
                print(f"❌ Input video not found: {video_path}")
                return False

            # First, try with stream copy for speed - FIXED: Put -ss BEFORE -i for accurate seeking
            cmd_copy = [
                self.ffmpeg_path, '-y',
                '-ss', str(start_time),  # Put seek BEFORE input for accurate timing
                '-i', video_path,
                '-t', str(end_time - start_time),
                '-c:v', 'copy', '-c:a', 'copy',
                '-avoid_negative_ts', 'make_zero',  # Fix timing issues
                '-fflags', '+genpts',  # Generate presentation timestamps
                '-start_at_zero',  # Ensure output starts at zero
                output_path
            ]

            print(f"   📋 FFmpeg command: {' '.join(cmd_copy)}")
            result = subprocess.run(cmd_copy, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"   ❌ Stream copy failed: {result.stderr}")

            # Check if file was created
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"   ✅ File created: {file_size} bytes")
            else:
                print(f"   ❌ File not created")
            
            # If stream copy fails or produces invalid output, re-encode
            if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
                print(f"Stream copy failed for {os.path.basename(output_path)}, re-encoding...")
                
                # Remove failed output file if it exists
                if os.path.exists(output_path):
                    os.remove(output_path)
                
                # Re-encode with compatibility settings - FIXED: Put -ss BEFORE -i
                cmd_encode = [
                    self.ffmpeg_path, '-y',
                    '-ss', str(start_time),  # Put seek BEFORE input for accurate timing
                    '-i', video_path,
                    '-t', str(end_time - start_time),
                    '-c:v', 'libx264',  # Ensure H.264 video codec
                    '-c:a', 'aac',      # Ensure AAC audio codec
                    '-preset', 'fast',   # Balance speed and quality
                    '-crf', '23',        # Good quality setting
                    '-pix_fmt', 'yuv420p',  # Ensure compatibility
                    '-movflags', 'faststart',  # Web optimization
                    '-avoid_negative_ts', 'make_zero',
                    '-fflags', '+genpts',
                    '-start_at_zero',  # Ensure output starts at zero
                    output_path
                ]

                print(f"   🔄 Re-encoding with: {' '.join(cmd_encode)}")
                result = subprocess.run(cmd_encode, capture_output=True, text=True)

                if result.returncode != 0:
                    print(f"   ❌ Re-encoding failed: {result.stderr}")

                # Check if file was created after re-encoding
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"   ✅ Re-encoded file: {file_size} bytes")
                else:
                    print(f"   ❌ Re-encoded file not created")
                
            if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                return True
            else:
                print(f"Error splitting video with ffmpeg: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error splitting video with ffmpeg: {e}")
            return False

    def analyze_video_scenes(self, video_path, threshold: float = 27, method: str = 'scenedetect'):
        """
        Analyze video for scenes and classification in a single pass
        Returns dict with scenes, is_compilation, and other metadata
        
        Args:
            video_path: Path to the video file
            threshold: Detection threshold (30.0 for scenedetect, 10 for moviepy)
            method: Detection method - 'scenedetect' or 'moviepy'
        """
        if method.lower() == 'moviepy':
            # Use moviepy detection with appropriate threshold conversion
            moviepy_threshold = int(threshold) if threshold != 30.0 else 10
            return self.analyze_video_scenes_moviepy(video_path, moviepy_threshold)
        
        # Default to scenedetect method
        try:
            video = open_video(video_path)
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=threshold))
            
            print(f"Analyzing video scenes with scenedetect (threshold {threshold}): {video_path}")
            scene_manager.detect_scenes(video, show_progress=True)
            scene_list = scene_manager.get_scene_list()
            
            # Get video duration using ffmpeg-python
            duration_seconds = self.get_video_duration(video_path)
            
            # Calculate scenes per minute and determine if it's a compilation
            is_compilation = False
            scenes_per_minute = 0
            
            if duration_seconds > 0:
                scenes_per_minute = len(scene_list) / (duration_seconds / 60)
                print(f"Found {len(scene_list)} scenes in {duration_seconds:.1f} seconds")
                print(f"Scenes per minute: {scenes_per_minute:.2f}")
                
                # If more than 3 scenes per minute, consider it a compilation
                is_compilation = len(scene_list) > 5 and scenes_per_minute > 3
            else:
                is_compilation = len(scene_list) > 5
            
            return {
                'scenes': scene_list,
                'is_compilation': is_compilation,
                'duration': duration_seconds,
                'scenes_per_minute': scenes_per_minute,
                'scene_count': len(scene_list),
                'method': 'scenedetect'
            }
            
        except Exception as e:
            print(f"Error analyzing video scenes with scenedetect: {e}")
            return {
                'scenes': [],
                'is_compilation': False,
                'duration': 0,
                'scenes_per_minute': 0,
                'scene_count': 0,
                'method': 'scenedetect',
                'error': str(e)
            }

    def analyze_video_scenes_moviepy(self, video_path, luminosity_threshold: int = 10):
        """
        Analyze video for scenes using moviepy's scene detection
        Returns dict with scenes, is_compilation, and other metadata
        """
        try:
            print(f"Analyzing video scenes with moviepy (threshold {luminosity_threshold}): {video_path}")
            
            # Load video with moviepy
            with VideoFileClip(video_path) as clip:
                # Detect scenes using moviepy
                cuts, luminosities = detect_scenes(
                    clip=clip,
                    luminosity_threshold=luminosity_threshold,
                    logger='bar'  # Use progress bar
                )
                
                # Convert cuts to scene list compatible with existing code
                scene_list = []
                for i, (start_time, end_time) in enumerate(cuts):
                    # Create tuple of (start_scene, end_scene) for compatibility
                    start_scene = SimpleScene(start_time, start_time)
                    end_scene = SimpleScene(end_time, end_time)
                    scene_list.append((start_scene, end_scene))
                
                # Get video duration
                duration_seconds = clip.duration
                
                # Calculate scenes per minute and determine if it's a compilation
                is_compilation = False
                scenes_per_minute = 0
                
                if duration_seconds > 0:
                    scenes_per_minute = len(scene_list) / (duration_seconds / 60)
                    print(f"Found {len(scene_list)} scenes in {duration_seconds:.1f} seconds")
                    print(f"Scenes per minute: {scenes_per_minute:.2f}")
                    
                    # If more than 3 scenes per minute, consider it a compilation
                    is_compilation = len(scene_list) > 5 and scenes_per_minute > 3
                else:
                    is_compilation = len(scene_list) > 5
                
                return {
                    'scenes': scene_list,
                    'is_compilation': is_compilation,
                    'duration': duration_seconds,
                    'scenes_per_minute': scenes_per_minute,
                    'scene_count': len(scene_list),
                    'method': 'moviepy',
                    'luminosities': luminosities  # Additional data from moviepy
                }
                
        except Exception as e:
            print(f"Error analyzing video scenes with moviepy: {e}")
            return {
                'scenes': [],
                'is_compilation': False,
                'duration': 0,
                'scenes_per_minute': 0,
                'scene_count': 0,
                'method': 'moviepy',
                'error': str(e)
            }

    def split_video_from_scenes(self, video_path, source_video_id, scene_list):
        """
        Splits a video into multiple clips based on a list of scenes using ffmpeg.
        Saves clips to the 'temp_vertical' directory.
        Returns the temporary directory and a list of dictionaries with clip info.
        """
        # Clips are saved in a flat structure in 'temp_vertical'
        # Use absolute path to avoid working directory issues
        # Get the backend directory (parent of vendors)
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        temp_dir = backend_dir / "temp_vertical"
        os.makedirs(temp_dir, exist_ok=True)
        
        video_clips = []
        print(f"Splitting video into {len(scene_list)} scenes...")
        
        for i, (start, end) in enumerate(scene_list):
            output_filename = os.path.join(str(temp_dir), f"{source_video_id}-Scene-{i+1:03d}.mp4")
            
            # Use ffmpeg for splitting
            success = self.split_video_with_ffmpeg(video_path, start.get_seconds(), end.get_seconds(), output_filename)

            if not success:
                print(f"❌ Failed to split scene {i+1} from {start.get_seconds():.1f}s to {end.get_seconds():.1f}s")
                continue

            # Verify file was created
            if not os.path.exists(output_filename):
                print(f"❌ Scene file not found after splitting: {output_filename}")
                continue

            try:
                file_size = os.path.getsize(output_filename)
                print(f"✅ Scene {i+1} created: {os.path.basename(output_filename)} ({file_size} bytes)")
            except Exception as e:
                print(f"❌ Cannot access scene file {i+1}: {e}")
                continue

            # Add a small delay to ensure file is fully written (Windows file locking issue)
            import time
            time.sleep(0.5)

            # Get video info
            clip_info = self.get_video_info(output_filename)
            
            # Append clip information to the list
            if clip_info and clip_info.get('duration') and clip_info['duration'] > 0.5:  # Filter out very short clips
                # ✅ Detect and crop pillarboxes on each clip
                print(f"🔍 Detecting pillarboxes on scene {i+1}...")
                cropped_clip_path = self.crop_video_if_vertical_with_blur(output_filename)
                if cropped_clip_path != output_filename:
                    print(f"✅ Scene {i+1} pillarboxes cropped: {os.path.basename(output_filename)} -> {os.path.basename(cropped_clip_path)}")
                    output_filename = cropped_clip_path
                else:
                    print(f"ℹ️  No pillarboxes detected on scene {i+1}")
                
                video_clips.append({
                    "path": output_filename,
                    "duration": clip_info["duration"],
                    "orientation": self.get_video_orientation(clip_info),
                    "scene_number": i + 1,
                })
        
        print(f"Generated {len(video_clips)} valid clips.")
        return str(temp_dir), video_clips

    def get_video_orientation(self, video_info):
        """Determine video orientation from its info"""
        if not video_info or 'width' not in video_info or 'height' not in video_info:
            return 'unknown'
        
        width = video_info['width']
        height = video_info['height']

        if width == 0 or height == 0:
            return 'unknown'
        
        aspect_ratio = width / height
        
        if aspect_ratio > 1.2: # Horizontal
            return 'horizontal'
        elif aspect_ratio < 0.8: # Vertical
            return 'vertical'
        else: # Square-ish
            return 'square'
        
    def download_and_split(self, video_id: str, sensitivity: float = 30.0, method: str = 'scenedetect'):
        """
        Process a single video by its ID: download, analyze scenes, split, and then process each clip.
        Pillarbox detection is performed on each individual clip after splitting.
        
        Args:
            video_id: YouTube video ID
            sensitivity: Detection threshold
            method: Detection method - 'scenedetect' or 'moviepy'
        """
        # 1. Download the video
        download_result = self.download_video(video_id)
        
        if not download_result or download_result[0] is None:
            print(f"Error: Could not download video {video_id}")
            return []
        
        video_path, video_title = download_result
        print(f"Video downloaded to: {video_path}")
        
        try:
            # 2. Always analyze for scenes first
            analysis = self.analyze_video_scenes(video_path, threshold=sensitivity, method=method)
            scenes = analysis.get('scenes', [])

            # 3. If scenes are found, split the video. If not, treat as a single clip.
            if not scenes:
                print("No scenes detected. Treating video as a single clip.")
                
                # Pillarbox detection on the single clip
                print(f"🔍 Detecting pillarboxes on single clip...")
                cropped_video_path = self.crop_video_if_vertical_with_blur(video_path)
                
                if cropped_video_path != video_path:
                    print(f"✅ Single clip pillarboxes cropped: {os.path.basename(video_path)} -> {os.path.basename(cropped_video_path)}")
                    video_path = cropped_video_path
                else:
                    print(f"ℹ️  No pillarboxes detected on single clip")

                video_info = self.get_video_info(video_path)
                duration = video_info.get('duration', 0) if video_info else 0
                
                video_clips = [{
                    "path": video_path,
                    "duration": duration,
                    "orientation": self.get_video_orientation(video_info),
                    "scene_number": 1,
                    "title": video_title
                }]
            else:
                print(f"Found {len(scenes)} scenes. Splitting video now...")
                # split_video_from_scenes will handle pillarbox detection for each scene
                temp_dir, video_clips = self.split_video_from_scenes(video_path, video_id, scenes)
                
                print(f"✅ Pillarbox detection completed on {len(video_clips)} individual clips")
                
                # Clean up original downloaded file if splitting was successful
                if video_clips:
                    os.remove(video_path)

        except Exception as e:
            print(f"An error occurred during video processing for {video_id}: {e}")
            # As a fallback, treat the whole video as a single clip
            try:
                # Pillarbox detection on the fallback single clip
                print(f"🔍 Detecting pillarboxes on fallback single clip...")
                cropped_video_path = self.crop_video_if_vertical_with_blur(video_path)
                if cropped_video_path != video_path:
                    print(f"✅ Fallback single clip pillarboxes cropped: {os.path.basename(video_path)} -> {os.path.basename(cropped_video_path)}")
                    video_path = cropped_video_path
                else:
                    print(f"ℹ️  No pillarboxes detected on fallback single clip")
                
                video_info = self.get_video_info(video_path)
                duration = video_info.get('duration', 0) if video_info else 0
                video_clips = [{
                    "path": video_path,
                    "duration": duration,
                    "orientation": self.get_video_orientation(video_info),
                    "scene_number": 1,
                    "title": video_title
                }]
            except Exception as fallback_e:
                print(f"Fallback failed for {video_id}: {fallback_e}")
                return []

        # 4. Final cleanup and return
        if not video_clips:
            print(f"No clips were generated for {video_id}")
            return []

        print(f"Successfully generated {len(video_clips)} clips for {video_id}")
        return video_clips

