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
from loguru import logger

# FFmpeg pool for centralized process management
try:
    from utils.ffmpeg_pool import run_ffmpeg_command, get_pool_stats
    HAS_FFMPEG_POOL = True
except ImportError:
    HAS_FFMPEG_POOL = False
    # Fallback to direct subprocess if pool not available
    def run_ffmpeg_command(cmd, description="FFmpeg", **kwargs):
        import subprocess
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

# Initialize logger for this module
logger = logger.bind(name="Compilation.processor")

# Define placeholder logging functions that were imported but may not exist
def log_generation_step(logger, *args, **kwargs):
    logger.info(f"Generation step: {args}, {kwargs}")

def log_file_operation(logger, operation, path, **kwargs):
    logger.info(f"File {operation}: {path}, {kwargs}")

def log_api_call(logger, *args, **kwargs):
    logger.info(f"API call: {args}, {kwargs}")


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
    def __init__(self, output_dir="final_videos", ffmpeg_path=None,
                 crop_verbose: bool | None = None,
                 crop_debug_frames: bool | None = None,
                 enable_yolo: bool | None = None):
        # FFmpeg 7+ compatibility fixes - cross-platform
        import sys
        import os
        
        # Add the backend directory to the Python path
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
        from utils.ffmpeg_utils import setup_ffmpeg_environment
        
        setup_ffmpeg_environment()
        
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

        # Runtime behavior flags (env overrides -> args -> defaults)
        # Set to 1 to enable detailed crop detection logs
        if crop_verbose is None:
            crop_verbose = os.getenv("CROP_VERBOSE", "0") == "1"
        if crop_debug_frames is None:
            crop_debug_frames = os.getenv("CROP_DEBUG_FRAMES", "0") == "1"
        if enable_yolo is None:
            enable_yolo = os.getenv("CROP_ENABLE_YOLO", "1") != "0"

        self.crop_verbose = crop_verbose
        self.crop_debug_frames = crop_debug_frames
        self.enable_yolo = enable_yolo

        # Cached YOLO model (lazy loaded) so we don't reload per video
        self._yolo_model = None
        self._yolo_device = None

    # ---------------- internal logging helpers -----------------
    def _crop_log(self, msg: str, always: bool = False):
        """Log crop detection messages respecting verbosity flag."""
        if always or self.crop_verbose:
            print(msg)
    
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
    
    def download_video(self, video_id, max_retries=5):
        """Download a video using the unified youtube utility (simplified).

        Returns: (video_path, title) or (None, None) on failure to preserve legacy interface.
        Increased max_retries to 5 for better handling of problematic videos.
        """
        logger.info(f"Starting YouTube video download for: {video_id} (unified)")
        try: 
            from utils.youtube import download_video as unified_download
            output_dir = os.path.join(self.output_dir, video_id)
            url = f"https://www.youtube.com/watch?v={video_id}"
            result = unified_download(url, output_dir, max_retries=max_retries)
            # Basic quality/log context
            if result.resolution:
                w, h = result.resolution
                print(f"✅ Downloaded {video_id}: {w}x{h}, duration={result.duration or 'unknown'}s")
            return result.video_path, result.title
        except Exception as e:
            # Handle both YouTubeDownloadError and other exceptions
            if "YouTubeDownloadError" in str(type(e)):
                print(f"Download failed for {video_id}: {e}")
            else:
                print(f"Unexpected download error for {video_id}: {e}")
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
                'ffprobe', '-v', 'fatal', '-show_entries', 'format=duration',  # Changed from 'quiet' to 'fatal'
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
                ffprobe_path, '-v', 'fatal', video_path  # Changed from 'error' to 'fatal' to suppress warnings
            ], capture_output=True, text=True, timeout=5)

            if simple_result.returncode != 0:
                print(f"❌ ffprobe basic check failed: {simple_result.stderr}")
                return None

            result = subprocess.run([
                ffprobe_path, '-v', 'fatal', '-show_entries',  # Changed from 'quiet' to 'fatal' for consistency
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
            # Use higher threshold to avoid false positives from scene content
            edge_threshold = np.max(vertical_edges) * 0.3  # Increased from 0.1 to 0.3
            
            # Find left boundary - look for sustained edge activity
            left_boundary = 0
            for x in range(width // 4):  # Look in outer 25% instead of 33%
                # Check if there's sustained edge activity in a small window
                window_start = max(0, x - 5)
                window_end = min(width, x + 5)
                window_activity = np.mean(vertical_edges[window_start:window_end])
                if window_activity > edge_threshold:
                    left_boundary = x
                    break
            
            # Find right boundary - look for sustained edge activity
            right_boundary = width - 1
            for x in range(width - 1, width * 3 // 4, -1):  # Look in outer 25% instead of 33%
                # Check if there's sustained edge activity in a small window
                window_start = max(0, x - 5)
                window_end = min(width, x + 5)
                window_activity = np.mean(vertical_edges[window_start:window_end])
                if window_activity > edge_threshold:
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
        if not self.enable_yolo:
            # YOLO disabled explicitly
            return 0, 0
        self._crop_log(f"[YOLOv8 Detection] Starting YOLOv8 object-based pillarbox detection")
        try:
            # Lazy import to avoid cost when not used
            from ultralytics import YOLO  # type: ignore
            import torch  # type: ignore
        except ImportError:
            self._crop_log("[YOLOv8 Detection] ultralytics not installed, falling back to vision methods")
            return self.detect_pillarboxes_transition_based(video_path, sample_frames)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._crop_log(f"[YOLOv8 Detection] Video: {width}x{height}, {total_frames} frames")

        # Load YOLOv8 model once and reuse
        if self._yolo_model is None:
            model_name = os.getenv("CROP_YOLO_MODEL", "yolov8n.pt")
            try:
                self._yolo_model = YOLO(model_name)
                self._yolo_device = 'cuda' if torch.cuda.is_available() else 'cpu'
                self._yolo_model.to(self._yolo_device)
                self._crop_log(f"[YOLOv8 Detection] Loaded model {model_name} on {self._yolo_device}")
            except Exception as e:
                self._crop_log(f"[YOLOv8 Detection] Failed to load model ({e}), fallback to vision methods")
                return self.detect_pillarboxes_transition_based(video_path, sample_frames)
        model = self._yolo_model

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
            self._crop_log("[YOLOv8 Detection] No objects detected, falling back to vision methods.")
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
        self._crop_log(f"[YOLOv8 Detection] Cropping to: left={left_crop}, right={right_crop}")
        return left_crop, right_crop

    def crop_video_if_vertical_with_blur(self, video_path):
        """
        Detects if a video is a vertical video with added blur bars on the sides,
        and if so, crops it to its original vertical aspect ratio.
        Uses edge detection as the primary method, with fallback to YOLOv8 and then transition-based methods.
        Returns the path to the cropped video, or the original path if no cropping was needed.
        """
        # Minimal log always
        self._crop_log(f"Detecting and removing pillarboxes from {video_path}", always=self.crop_verbose)

        # Debug: Check if file exists and is accessible
        if not os.path.exists(video_path):
            print(f"❌ File does not exist: {video_path}")
            return video_path

        try:
            file_size = os.path.getsize(video_path)
            self._crop_log(f"✅ File exists: {video_path} ({file_size} bytes)")
        except Exception as e:
            print(f"❌ Cannot access file: {video_path} - {e}")
            return video_path

        debug_dir = "debug_frames"
        if self.crop_debug_frames:
            Path(debug_dir).mkdir(exist_ok=True)
        video_id = Path(video_path).stem
        video_info = self.get_video_info(video_path)
        if not video_info:
            print("Error: Could not get video info")
            return video_path
        width = video_info.get('width', 0)
        height = video_info.get('height', 0)
        self._crop_log(f"[Crop Detection] Video dimensions: {width}x{height}")
        if height >= width:
            print("Video is already vertical or square. No cropping needed.")
            return video_path
        # Save a preview frame for debugging
        if self.crop_debug_frames:
            try:
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
                    ret, frame = cap.read()
                    if ret:
                        preview_path = os.path.join(debug_dir, f"{video_id}_original.png")
                        cv2.imwrite(preview_path, frame)
                        self._crop_log(f"[Crop Detection] Saved preview frame: {preview_path}")
                    cap.release()
            except Exception as e:
                self._crop_log(f"[Crop Detection] Could not save preview frame: {e}")
        # Use edge detection as primary, fallback to YOLOv8, then transition-based
        try:
            left_crop, right_crop = self.detect_pillarboxes_edge_detection(video_path)
            self._crop_log(f"[Crop Detection] [Edge] Detected pillarboxes: left={left_crop}px, right={right_crop}px")
            if left_crop == 0 and right_crop == 0:
                self._crop_log("[Crop Detection] [Edge] No crop detected, falling back to YOLOv8.")
                left_crop, right_crop = self.detect_pillarboxes_yolov8(video_path)
                self._crop_log(f"[Crop Detection] [YOLOv8] Detected pillarboxes: left={left_crop}px, right={right_crop}px")
                if left_crop == 0 and right_crop == 0:
                    self._crop_log("[Crop Detection] [YOLOv8] No crop detected, falling back to transition-based.")
                    left_crop, right_crop = self.detect_pillarboxes_transition_based(video_path)
                    self._crop_log(f"[Crop Detection] [Transition] Detected pillarboxes: left={left_crop}px, right={right_crop}px")
            crop_width = width - left_crop - right_crop
            if crop_width <= 0:
                print("[Crop Detection] Invalid crop width, no cropping needed")
                return video_path
            if left_crop >= width or right_crop >= width:
                print(f"[Crop Detection] Crop values too large: left={left_crop}, right={right_crop}, width={width}")
                return video_path
            if left_crop + right_crop >= width * 0.5:  # Reduced from 0.8 to 0.5
                print(f"[Crop Detection] Would crop too much content ({left_crop + right_crop}px of {width}px)")
                return video_path
            min_crop_threshold = max(width * 0.05, 30)  # Increased from 0.02/20 to 0.05/30
            total_crop = left_crop + right_crop
            self._crop_log(f"[Crop Detection] Total crop: {total_crop}px, threshold: {min_crop_threshold*2:.1f}px")
            if total_crop < min_crop_threshold * 2:
                print(f"[Crop Detection] Not enough cropping detected ({total_crop}px < {min_crop_threshold*2:.1f}px)")
                return video_path
            new_aspect_ratio = crop_width / height
            original_aspect_ratio = width / height
            self._crop_log(f"[Crop Detection] Aspect ratios: original={original_aspect_ratio:.2f}, new={new_aspect_ratio:.2f}")
            if new_aspect_ratio >= original_aspect_ratio * 0.8:  # Increased from 0.9 to 0.8 - require more significant improvement
                print(f"[Crop Detection] Not enough improvement in aspect ratio")
                return video_path
            if new_aspect_ratio > 1.5:  # Reduced from 1.8 to 1.5 - be more strict about wide videos
                print(f"[Crop Detection] Still too wide after cropping (ratio: {new_aspect_ratio:.2f})")
                return video_path
            self._crop_log(f"[Crop Detection] ✓ Cropping approved: {width}x{height} -> {crop_width}x{height}", always=True)
            self._crop_log(f"[Crop Detection] ✓ Aspect ratio: {original_aspect_ratio:.2f} -> {new_aspect_ratio:.2f}")
            try:
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
                    ret, frame = cap.read()
                    if ret:
                        crop_region = frame[:, left_crop:left_crop+crop_width]
                        region_variance = np.var(cv2.cvtColor(crop_region, cv2.COLOR_BGR2GRAY).astype(np.float64))
                        self._crop_log(f"[Crop Detection] Crop region variance: {region_variance:.2f}")
                        if region_variance < 10:
                            print(f"[Crop Detection] Crop region appears empty (variance={region_variance:.2f})")
                            cap.release()
                            return video_path
                        if self.crop_debug_frames:
                            preview_crop_path = os.path.join(debug_dir, f"{video_id}_crop_preview.png")
                            cv2.imwrite(preview_crop_path, crop_region)
                            self._crop_log(f"[Crop Detection] Saved crop preview: {preview_crop_path}")
                            debug_frame = frame.copy()
                            cv2.line(debug_frame, (left_crop, 0), (left_crop, height-1), (0, 255, 0), 2)
                            cv2.line(debug_frame, (left_crop + crop_width, 0), (left_crop + crop_width, height-1), (0, 0, 255), 2)
                            debug_path = os.path.join(debug_dir, f"{video_id}_crop_lines.png")
                            cv2.imwrite(debug_path, debug_frame)
                            self._crop_log(f"[Crop Detection] Saved debug frame with crop lines: {debug_path}")
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
                    self._crop_log("[Crop Detection] 🎮 GPU acceleration available - using NVENC encoding")
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
                    self._crop_log("[Crop Detection] 💻 Using CPU encoding (GPU not available)")
                    cmd = [
                        self.ffmpeg_path, '-y', '-i', video_path,
                        '-filter:v', f'crop={crop_width}:{height}:{left_crop}:0',
                        '-c:v', 'libx264',    # CPU H.264 encoding
                        '-preset', 'fast',     # Fast preset
                        '-c:a', 'copy',
                        '-avoid_negative_ts', 'make_zero',
                        output_path
                    ]

                self._crop_log(f"[Crop Detection] Running FFmpeg: crop={crop_width}:{height}:{left_crop}:0")
                self._crop_log(f"[Crop Detection] Using {'GPU (NVENC)' if has_gpu else 'CPU (libx264)'} encoding")
                result = run_ffmpeg_command(cmd, description=f"Crop video: {os.path.basename(video_path)}")
                if result.returncode == 0:
                    self._crop_log(f"[Crop Detection] ✓ Successfully cropped video and saved to {output_path}", always=True)
                    output_info = self.get_video_info(output_path)
                    if output_info and output_info.get('duration', 0) > 0:
                        self._crop_log(f"[Crop Detection] ✓ Output validation: {output_info['width']}x{output_info['height']}, {output_info['duration']:.1f}s")
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
        """Split a video segment with fast keyframe copy + optional accurate re-encode.

        Env toggles:
          SPLIT_ACCURATE_SEEK=1 -> force accurate re-encode
          SPLIT_ENCODE_PRESET (default fast)
          SPLIT_ENCODE_CRF (default 23)
        """
        try:
            print(f"🎬 Splitting scene: {start_time:.1f}s to {end_time:.1f}s -> {os.path.basename(output_path)}")
            if not os.path.exists(self.ffmpeg_path):
                print(f"❌ FFmpeg not found at: {self.ffmpeg_path}")
                return False
            if not os.path.exists(video_path):
                # Allow idempotent reuse if output already present
                if os.path.exists(output_path):
                    print(f"✅ Output already exists (source missing): {os.path.basename(output_path)}")
                    return True
                print(f"❌ Input video not found: {video_path}")
                return False
            cmd_copy = [
                self.ffmpeg_path, '-y', '-loglevel', 'error',
                '-ss', str(start_time), '-i', video_path,
                '-t', str(end_time - start_time),
                '-c:v', 'copy', '-c:a', 'copy',
                '-avoid_negative_ts', 'make_zero', '-fflags', '+genpts',
                '-start_at_zero', '-err_detect', 'ignore_err',
                output_path
            ]
            print(f"   📋 FFmpeg command: {' '.join(cmd_copy)}")
            result = run_ffmpeg_command(cmd_copy, description=f"Split video (copy): {os.path.basename(output_path)}", check=False)
            if result.returncode != 0:
                print(f"   ❌ Stream copy failed: {result.stderr}")
            if os.path.exists(output_path):
                print(f"   ✅ File created: {os.path.getsize(output_path)} bytes")
            else:
                print("   ❌ File not created")
            accurate_seek_requested = os.getenv("SPLIT_ACCURATE_SEEK", "0") == "1"
            if accurate_seek_requested:
                print("   ℹ️ SPLIT_ACCURATE_SEEK=1 -> enforcing accurate seek")
            need_reencode = (accurate_seek_requested or result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) < 1024)
            if need_reencode:
                if os.path.exists(output_path):
                    try: os.remove(output_path)
                    except OSError: pass
                cmd_encode = [
                    self.ffmpeg_path, '-y', '-loglevel', 'error',
                    '-i', video_path,
                    '-ss', str(start_time), '-t', str(end_time - start_time),
                    '-c:v', 'libx264', '-c:a', 'aac',
                    '-preset', os.getenv('SPLIT_ENCODE_PRESET', 'fast'),
                    '-crf', os.getenv('SPLIT_ENCODE_CRF', '23'),
                    '-pix_fmt', 'yuv420p', '-movflags', 'faststart',
                    '-avoid_negative_ts', 'make_zero', '-fflags', '+genpts',
                    '-start_at_zero', '-err_detect', 'ignore_err',
                    output_path
                ]
                print(f"   🔄 Re-encoding with: {' '.join(cmd_encode)}")
                result = run_ffmpeg_command(cmd_encode, description=f"Split video (encode): {os.path.basename(output_path)}", check=False)
                if result.returncode != 0:
                    print(f"   ❌ Re-encoding failed: {result.stderr}")
                elif os.path.exists(output_path):
                    print(f"   ✅ Re-encoded file: {os.path.getsize(output_path)} bytes")
                else:
                    print("   ❌ Re-encoded file not created")
            if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
                return True
            print(f"Error splitting video with ffmpeg: {result.stderr}")
            return False
        except Exception as e:
            print(f"Error splitting video with ffmpeg: {e}")
            return False

    def analyze_video_scenes(self, video_path, threshold: float = 17.0, method: str = 'scenedetect'):
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
            moviepy_threshold = int(threshold) if threshold != 17.0 else 10
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

    def analyze_video_scenes_audio(self, video_path, visual_threshold: float = 17.0,
                                    silence_threshold_db: float = -40.0,
                                    min_silence_duration: float = 0.3,
                                    energy_spike_threshold: float = 2.0):
        """
        Hybrid scene detection using visual + audio analysis.
        
        Combines:
        - Visual: scenedetect ContentDetector for visual cuts
        - Audio: librosa-based silence detection and energy spike detection
        
        Args:
            video_path: Path to video file
            visual_threshold: Threshold for visual scene detection (default 17.0)
            silence_threshold_db: dB threshold below which is considered silence (default -40)
            min_silence_duration: Minimum silence duration to consider as scene break (default 0.3s)
            energy_spike_threshold: Factor above mean energy to detect spikes (default 2.0)
            
        Returns:
            dict with merged scenes, is_compilation, and metadata
        """
        print(f"🎵 Analyzing video with audio-enhanced scene detection: {video_path}")
        
        # First, get visual scenes
        visual_analysis = self.analyze_video_scenes(video_path, threshold=visual_threshold, method='scenedetect')
        visual_scenes = visual_analysis.get('scenes', [])
        duration = visual_analysis.get('duration', 0)
        
        print(f"   Visual detection found {len(visual_scenes)} scenes")
        
        # Try audio-based scene detection
        audio_boundaries = []
        try:
            import librosa
            import numpy as np
            
            # Load audio from video
            print(f"   Loading audio for analysis...")
            y, sr = librosa.load(video_path, sr=22050, mono=True)
            
            if len(y) == 0:
                print(f"   ⚠️ No audio found, using visual-only detection")
                return visual_analysis
            
            audio_duration = len(y) / sr
            print(f"   Audio loaded: {audio_duration:.1f}s at {sr}Hz")
            
            # 1. Silence detection
            print(f"   Detecting silence gaps (threshold: {silence_threshold_db}dB)...")
            
            # Calculate RMS energy in windows
            frame_length = int(sr * 0.025)  # 25ms frames
            hop_length = int(sr * 0.010)    # 10ms hop
            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
            
            # Convert to dB
            rms_db = 20 * np.log10(rms + 1e-10)
            
            # Find silent regions
            is_silent = rms_db < silence_threshold_db
            
            # Find silence boundaries (transitions from loud to silent or vice versa)
            silence_changes = np.diff(is_silent.astype(int))
            silence_start_frames = np.where(silence_changes == 1)[0]
            silence_end_frames = np.where(silence_changes == -1)[0]
            
            # Convert frame indices to time
            frame_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
            
            # Find silences that are long enough to be scene breaks
            for start_idx in silence_start_frames:
                # Find matching end
                matching_ends = silence_end_frames[silence_end_frames > start_idx]
                if len(matching_ends) > 0:
                    end_idx = matching_ends[0]
                    silence_duration = frame_times[end_idx] - frame_times[start_idx]
                    
                    if silence_duration >= min_silence_duration:
                        # Use the middle of the silence as the scene boundary
                        boundary_time = (frame_times[start_idx] + frame_times[end_idx]) / 2
                        audio_boundaries.append(('silence', boundary_time))
            
            print(f"   Found {len(audio_boundaries)} silence-based boundaries")
            
            # 2. Energy spike detection (sudden loud moments often indicate scene changes)
            print(f"   Detecting energy spikes...")
            
            # Smooth RMS for spike detection
            rms_smooth = np.convolve(rms, np.ones(10)/10, mode='same')
            mean_energy = np.mean(rms_smooth)
            
            # Find spikes above threshold
            spikes = rms_smooth > (mean_energy * energy_spike_threshold)
            spike_frames = np.where(np.diff(spikes.astype(int)) == 1)[0]
            
            for frame_idx in spike_frames:
                boundary_time = frame_times[frame_idx]
                # Only add if not too close to existing boundaries
                too_close = any(abs(boundary_time - b[1]) < 0.5 for b in audio_boundaries)
                if not too_close:
                    audio_boundaries.append(('spike', boundary_time))
            
            print(f"   Found {len([b for b in audio_boundaries if b[0] == 'spike'])} energy spike boundaries")
            print(f"   Total audio boundaries: {len(audio_boundaries)}")
            
        except ImportError:
            print(f"   ⚠️ librosa not available, using visual-only detection")
            return visual_analysis
        except Exception as e:
            print(f"   ⚠️ Audio analysis failed ({e}), using visual-only detection")
            return visual_analysis
        
        # 3. Merge visual and audio boundaries
        print(f"   Merging visual and audio boundaries...")
        
        all_boundaries = set()
        
        # Add visual scene boundaries
        for scene_start, scene_end in visual_scenes:
            try:
                start_time = scene_start.get_seconds()
                all_boundaries.add(start_time)
            except:
                pass
        
        # Add audio boundaries (with deduplication)
        merge_threshold = 0.5  # Boundaries within 0.5s are considered the same
        for _, boundary_time in audio_boundaries:
            # Check if this boundary is close to an existing one
            is_duplicate = any(abs(boundary_time - b) < merge_threshold for b in all_boundaries)
            if not is_duplicate and 0 < boundary_time < duration:
                all_boundaries.add(boundary_time)
        
        # Sort boundaries and create scene list
        sorted_boundaries = sorted(all_boundaries)
        
        # Build scene list (pairs of start/end)
        merged_scenes = []
        if sorted_boundaries:
            # Add scene from 0 to first boundary
            if sorted_boundaries[0] > 0.5:
                merged_scenes.append((SimpleScene(0, sorted_boundaries[0]), 
                                     SimpleScene(sorted_boundaries[0], sorted_boundaries[0])))
            
            # Add scenes between boundaries
            for i in range(len(sorted_boundaries) - 1):
                start = sorted_boundaries[i]
                end = sorted_boundaries[i + 1]
                if end - start >= 0.5:  # Minimum scene duration
                    merged_scenes.append((SimpleScene(start, start), SimpleScene(end, end)))
            
            # Add scene from last boundary to end
            if duration - sorted_boundaries[-1] > 0.5:
                merged_scenes.append((SimpleScene(sorted_boundaries[-1], sorted_boundaries[-1]),
                                     SimpleScene(duration, duration)))
        
        print(f"   Merged result: {len(merged_scenes)} scenes (visual: {len(visual_scenes)}, audio-only: {len(audio_boundaries)})")
        
        # Calculate scenes per minute
        scenes_per_minute = len(merged_scenes) / (duration / 60) if duration > 0 else 0
        is_compilation = len(merged_scenes) > 5 and scenes_per_minute > 3
        
        return {
            'scenes': merged_scenes,
            'is_compilation': is_compilation,
            'duration': duration,
            'scenes_per_minute': scenes_per_minute,
            'scene_count': len(merged_scenes),
            'method': 'audio_enhanced',
            'visual_scene_count': len(visual_scenes),
            'audio_boundary_count': len(audio_boundaries),
            'audio_boundaries': [(b[0], b[1]) for b in audio_boundaries]
        }

    def split_video_from_scenes(self, video_path, source_video_id, scene_list):
        """Split video into scene clips (optional concurrency) then crop pillarboxes.

        Improvements vs older version:
          - Creates a protected working copy to avoid source deletion mid-process
          - Adds start_time / end_time to each returned clip dict (prevents KeyError downstream)
          - Collects basic failure stats

        Env:
          SCENE_SPLIT_CONCURRENCY -> int workers (default 1, cap 6)
        """
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        temp_dir = backend_dir / "temp_vertical"
        os.makedirs(temp_dir, exist_ok=True)

        if not os.path.exists(video_path):
            print(f"❌ Source video not found at start of splitting: {video_path}")
            return str(temp_dir), []

        # Record initial file size for sanity
        try:
            initial_size = os.path.getsize(video_path)
            print(f"🎬 Starting scene splitting: {len(scene_list)} scenes from {video_path} ({initial_size} bytes)")
        except Exception as e:
            print(f"❌ Cannot access source video file: {e}")
            return str(temp_dir), []

        # Create protected working copy (prevents cleanup race conditions)
        protected_video_path = None
        try:
            import uuid, shutil
            working_filename = f"working_{source_video_id}_{uuid.uuid4().hex[:8]}.mp4"
            protected_video_path = os.path.join(str(temp_dir), working_filename)
            print(f"🔒 Creating protected working copy: {protected_video_path}")
            shutil.copy2(video_path, protected_video_path)
            protected_size = os.path.getsize(protected_video_path)
            if protected_size != initial_size:
                print(f"❌ Working copy size mismatch: {initial_size} vs {protected_size}")
                return str(temp_dir), []
            print(f"✅ Protected working copy created successfully ({protected_size} bytes)")
            working_video_path = protected_video_path
        except Exception as e:
            print(f"⚠️  Could not create protected working copy: {e}")
            print(f"🔄 Falling back to original source file (risk of cleanup interference)")
            working_video_path = video_path

        # Preprocess & filter extremely short scenes (<0.5s)
        prepared = []
        for idx, (start, end) in enumerate(scene_list):
            try:
                s = start.get_seconds(); e = end.get_seconds()
                if e - s < 0.5:
                    continue
                prepared.append((idx, s, e))
            except Exception:
                continue

        # Determine concurrency
        try:
            concurrency = int(os.getenv("SCENE_SPLIT_CONCURRENCY", "1"))
        except ValueError:
            concurrency = 1
        concurrency = max(1, min(concurrency, 6))
        if concurrency > 1 and len(prepared) > 2:
            print(f"⚙️  Parallel scene splitting enabled (workers={concurrency})")
        else:
            concurrency = 1

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _do_split(idx, s, e):
            scene_no = idx + 1
            out_path = os.path.join(str(temp_dir), f"{source_video_id}-Scene-{scene_no:03d}.mp4")
            # Reuse existing if already valid
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                return scene_no, out_path, True, s, e
            ok = self.split_video_with_ffmpeg(working_video_path, s, e, out_path)
            return scene_no, out_path, ok, s, e

        split_results = []
        failed_scenes = []
        if concurrency > 1:
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                future_map = {pool.submit(_do_split, idx, s, e): (idx, s, e) for idx, s, e in prepared}
                for fut in as_completed(future_map):
                    idx, s, e = future_map[fut]
                    try:
                        split_results.append(fut.result())
                    except Exception as exc:
                        scene_no = idx + 1
                        msg = f"Exception splitting scene {scene_no} ({s:.1f}-{e:.1f}s): {exc}"
                        print(f"❌ {msg}")
                        failed_scenes.append((scene_no, msg))
        else:
            for idx, s, e in prepared:
                split_results.append(_do_split(idx, s, e))

        # Deterministic order
        split_results.sort(key=lambda r: r[0])

        # Collect metadata
        valid_segments = []
        for scene_no, out_path, ok, s, e in split_results:
            if not ok or not os.path.exists(out_path):
                msg = f"Failed to split scene {scene_no} from {s:.1f}s to {e:.1f}s"
                print(f"❌ {msg}")
                failed_scenes.append((scene_no, msg))
                continue
            try:
                size = os.path.getsize(out_path)
                print(f"✅ Scene {scene_no} created: {os.path.basename(out_path)} ({size} bytes)")
            except OSError as fs_err:
                msg = f"File access error scene {scene_no}: {fs_err}"
                print(f"❌ {msg}")
                failed_scenes.append((scene_no, msg))
                continue
            time.sleep(0.05)
            clip_info = self.get_video_info(out_path)
            if not (clip_info and clip_info.get('duration') and clip_info['duration'] >= 3.0):
                continue
            valid_segments.append((scene_no, out_path, clip_info, s, e))

        # Cropping phase
        video_clips = []
        for scene_no, out_path, clip_info, s, e in valid_segments:
            print(f"🔍 Detecting pillarboxes on scene {scene_no}...")
            cropped_path = self.crop_video_if_vertical_with_blur(out_path)
            if cropped_path != out_path:
                print(f"✅ Scene {scene_no} cropped: {os.path.basename(out_path)} -> {os.path.basename(cropped_path)}")
                out_path = cropped_path
            else:
                print(f"ℹ️  No pillarboxes detected on scene {scene_no}")
            video_clips.append({
                "path": out_path,
                "duration": clip_info["duration"],
                "orientation": self.get_video_orientation(clip_info),
                "scene_number": scene_no,
                "start_time": s,
                "end_time": e,
            })

        # Summary
        print("📊 Scene splitting summary:")
        print(f"   Total scenes: {len(scene_list)}")
        print(f"   Successfully processed: {len(video_clips)}")
        print(f"   Failed: {len(failed_scenes)}")
        if failed_scenes:
            print("⚠️  Failed scenes details:")
            for scene_num, error in failed_scenes:
                print(f"   Scene {scene_num}: {error}")

        # Deferred cleanup: keep protected copy until explicit frontend cleanup command
        if protected_video_path and os.path.exists(protected_video_path):
            print(f"� Deferred cleanup: protected working copy retained at {protected_video_path}")

        print(f"✅ Generated {len(video_clips)} valid clips from {source_video_id}")
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
                # Note: Be cautious with cleanup to avoid race conditions
                # Defer removal of original file; will be handled by explicit cleanup action
                if video_clips and os.path.exists(video_path):
                    print(f"🕒 Deferred cleanup: original video file retained ({video_path})")

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

