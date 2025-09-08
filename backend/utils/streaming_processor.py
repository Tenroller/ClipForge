"""
Streaming video processor for memory-efficient video processing.
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from logging_config import get_logger

logger = get_logger("streaming_processor")


class StreamingVideoProcessor:
    """Processes videos using streaming techniques to reduce memory usage."""

    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path("temp") / "streaming"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def combine_videos_streaming(self, video_paths: List[str], target_duration: float,
                                min_clip_duration: float = 5.0, max_threads: int = 2,
                                use_gpu: bool = True) -> Optional[str]:
        """
        Combine videos using streaming concatenation to reduce memory usage.

        Args:
            video_paths: List of video file paths to combine
            target_duration: Target duration in seconds
            min_clip_duration: Minimum duration for each clip
            max_threads: Maximum number of threads to use
            use_gpu: Whether to use GPU acceleration

        Returns:
            Path to the combined video file or None if failed
        """
        if not video_paths:
            logger.warning("No video paths provided for streaming combination")
            return None

        logger.info(f"Starting streaming video combination of {len(video_paths)} videos")

        try:
            # Create a temporary concatenation file
            concat_file = self.temp_dir / f"concat_{os.getpid()}.txt"
            output_file = self.temp_dir / f"combined_streaming_{os.getpid()}.mp4"

            # Write concat file for FFmpeg
            with open(concat_file, 'w', encoding='utf-8') as f:
                for video_path in video_paths:
                    # Escape single quotes in paths for FFmpeg
                    escaped_path = video_path.replace("'", r"'\''")
                    f.write(f"file '{escaped_path}'\n")

            # Build FFmpeg command for streaming concatenation
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c:v', 'libx264',
                '-preset', 'medium' if not use_gpu else 'fast',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-avoid_negative_ts', 'make_zero',
                '-fflags', '+discardcorrupt',
                '-threads', str(max_threads),
                '-y',  # Overwrite output
                str(output_file)
            ]

            # Add GPU acceleration if requested
            if use_gpu:
                try:
                    # Try NVIDIA GPU first
                    cmd.insert(-1, '-c:v')
                    cmd.insert(-1, 'h264_nvenc')
                except:
                    # Fallback to CPU
                    pass

            logger.info(f"Running streaming FFmpeg command: {' '.join(cmd)}")

            # Run FFmpeg with streaming processing
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode == 0 and output_file.exists():
                logger.info(f"Streaming video combination successful: {output_file}")
                # Clean up concat file
                try:
                    concat_file.unlink()
                except:
                    pass
                return str(output_file)
            else:
                logger.error(f"FFmpeg streaming failed: {result.stderr}")
                # Clean up failed output
                try:
                    if output_file.exists():
                        output_file.unlink()
                    concat_file.unlink()
                except:
                    pass
                return None

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg streaming timed out")
            return None
        except Exception as e:
            logger.error(f"Error in streaming video combination: {e}")
            return None

    def extract_audio_streaming(self, video_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Extract audio from video using streaming to reduce memory usage.

        Args:
            video_path: Path to input video
            output_path: Optional output path for audio

        Returns:
            Path to extracted audio file or None if failed
        """
        if not os.path.exists(video_path):
            logger.error(f"Video file does not exist: {video_path}")
            return None

        if output_path is None:
            output_path = str(self.temp_dir / f"audio_stream_{os.getpid()}.wav")

        try:
            # Use FFmpeg to extract audio stream
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',
                '-ar', '44100',  # Sample rate
                '-ac', '2',  # Stereo
                '-f', 'wav',
                '-y',  # Overwrite
                output_path
            ]

            logger.info(f"Extracting audio stream from {video_path}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
                logger.info(f"Audio extracted successfully: {file_size:.2f} MB")
                return output_path
            else:
                logger.error(f"Audio extraction failed: {result.stderr}")
                # Clean up failed output
                try:
                    if os.path.exists(output_path):
                        os.unlink(output_path)
                except:
                    pass
                return None

        except subprocess.TimeoutExpired:
            logger.error("Audio extraction timed out")
            return None
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            return None

    def get_video_info_streaming(self, video_path: str) -> Optional[Dict[str, Any]]:
        """
        Get video information using FFprobe (streaming-friendly).

        Args:
            video_path: Path to video file

        Returns:
            Dictionary with video information or None if failed
        """
        if not os.path.exists(video_path):
            return None

        try:
            # Use ffprobe to get video information
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            if result.returncode == 0:
                import json
                info = json.loads(result.stdout)

                # Extract useful information
                video_info = {
                    'duration': float(info.get('format', {}).get('duration', 0)),
                    'size_bytes': int(info.get('format', {}).get('size', 0)),
                    'bitrate': int(info.get('format', {}).get('bit_rate', 0)),
                    'streams': []
                }

                for stream in info.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        video_info['video'] = {
                            'width': stream.get('width', 0),
                            'height': stream.get('height', 0),
                            'codec': stream.get('codec_name', ''),
                            'fps': eval(stream.get('r_frame_rate', '0/1')),
                            'duration': float(stream.get('duration', 0))
                        }
                    elif stream.get('codec_type') == 'audio':
                        video_info['audio'] = {
                            'codec': stream.get('codec_name', ''),
                            'channels': stream.get('channels', 0),
                            'sample_rate': int(stream.get('sample_rate', 0))
                        }

                return video_info
            else:
                logger.warning(f"FFprobe failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning("FFprobe timed out")
            return None
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None

    def cleanup_temp_files(self, older_than_seconds: int = 3600):
        """
        Clean up temporary streaming files older than specified time.

        Args:
            older_than_seconds: Files older than this will be deleted
        """
        import time

        try:
            current_time = time.time()
            cleaned_count = 0
            space_freed = 0

            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file():
                    try:
                        file_age = current_time - file_path.stat().st_mtime
                        if file_age > older_than_seconds:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            cleaned_count += 1
                            space_freed += file_size
                    except Exception as e:
                        logger.warning(f"Failed to clean temp file {file_path}: {e}")

            if cleaned_count > 0:
                logger.info(f"Cleaned {cleaned_count} streaming temp files, freed {space_freed / (1024*1024):.2f} MB")

        except Exception as e:
            logger.error(f"Error cleaning streaming temp files: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about streaming processor usage.

        Returns:
            Dictionary with temp directory statistics
        """
        try:
            files = list(self.temp_dir.glob("*"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())

            return {
                'temp_dir': str(self.temp_dir),
                'file_count': len([f for f in files if f.is_file()]),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'oldest_file_hours': self._get_oldest_file_age()
            }
        except Exception as e:
            return {
                'temp_dir': str(self.temp_dir),
                'error': str(e)
            }

    def _get_oldest_file_age(self) -> Optional[float]:
        """Get age of oldest file in hours."""
        try:
            import time
            files = list(self.temp_dir.glob("*"))
            if not files:
                return None

            oldest_time = min(f.stat().st_mtime for f in files if f.is_file())
            return (time.time() - oldest_time) / 3600
        except Exception:
            return None


# Global instance
_streaming_processor: Optional[StreamingVideoProcessor] = None


def get_streaming_processor() -> StreamingVideoProcessor:
    """Get or create the global streaming processor."""
    global _streaming_processor
    if _streaming_processor is None:
        _streaming_processor = StreamingVideoProcessor()
    return _streaming_processor


def init_streaming_processor():
    """Initialize the streaming processor."""
    processor = get_streaming_processor()
    logger.info("Streaming video processor initialized")


def cleanup_streaming_temp_files():
    """Clean up old streaming temp files."""
    try:
        processor = get_streaming_processor()
        processor.cleanup_temp_files()
    except Exception as e:
        logger.error(f"Failed to cleanup streaming temp files: {e}")
