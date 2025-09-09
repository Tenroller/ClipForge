"""
Video thumbnail generation service.
"""

import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
import time

from ..logging_config import get_logger
from ..utils.paths import get_project_root

logger = get_logger("thumbnail_service")

class ThumbnailService:
    """Service for generating and managing video thumbnails."""
    
    def __init__(self):
        self.cache_dir = get_project_root() / "backend" / "cache" / "thumbnails"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_cache_key(self, video_path: str) -> str:
        """Generate a cache key for a video file."""
        # Use video path and file modification time for cache key
        try:
            file_path = Path(video_path)
            if not file_path.exists():
                return hashlib.md5(video_path.encode()).hexdigest()
                
            # Include file size and modification time in cache key
            stat = file_path.stat()
            cache_data = f"{video_path}_{stat.st_size}_{stat.st_mtime}"
            return hashlib.md5(cache_data.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to generate cache key for {video_path}: {e}")
            return hashlib.md5(video_path.encode()).hexdigest()
    
    def _get_thumbnail_path(self, cache_key: str) -> Path:
        """Get the path where thumbnail should be stored."""
        return self.cache_dir / f"{cache_key}.jpg"
    
    def generate_thumbnail(self, video_path: str, timestamp: float = 5.0) -> Optional[str]:
        """
        Generate a thumbnail for a video file.
        
        Args:
            video_path: Path to the video file
            timestamp: Time in seconds to extract thumbnail from (default: 5.0)
            
        Returns:
            Path to generated thumbnail file, or None if generation failed
        """
        try:
            video_file = Path(video_path)
            if not video_file.exists() or not video_file.is_file():
                logger.warning(f"Video file not found: {video_path}")
                return None
            
            # Check cache first
            cache_key = self._get_cache_key(video_path)
            thumbnail_path = self._get_thumbnail_path(cache_key)
            
            if thumbnail_path.exists():
                logger.debug(f"Using cached thumbnail for {video_path}")
                return str(thumbnail_path)
            
            # Try to import moviepy
            try:
                from moviepy import VideoFileClip
            except ImportError:
                logger.error("moviepy not available for thumbnail generation")
                return None
            
            # Generate thumbnail using moviepy
            logger.info(f"Generating thumbnail for {video_path} at {timestamp}s")
            
            with VideoFileClip(video_path) as clip:
                # Use timestamp or 10% of video duration, whichever is smaller
                thumbnail_time = min(timestamp, clip.duration * 0.1) if clip.duration else timestamp
                
                # Extract frame
                frame = clip.get_frame(thumbnail_time)
                
                # Save as JPEG using PIL/Pillow
                try:
                    from PIL import Image
                    import numpy as np
                    
                    # Convert frame to PIL Image
                    if frame.dtype != np.uint8:
                        frame = (frame * 255).astype(np.uint8)
                    
                    image = Image.fromarray(frame)
                    
                    # Resize to reasonable thumbnail size (320x180 for 16:9)
                    image.thumbnail((320, 180), Image.Resampling.LANCZOS)
                    
                    # Save as JPEG
                    image.save(str(thumbnail_path), "JPEG", quality=85, optimize=True)
                    
                    logger.info(f"Generated thumbnail: {thumbnail_path}")
                    return str(thumbnail_path)
                    
                except ImportError:
                    logger.error("PIL/Pillow not available for thumbnail generation")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to generate thumbnail for {video_path}: {e}")
            return None
    
    def get_thumbnail_url(self, video_path: str, base_url: str = "/api") -> Optional[str]:
        """
        Get the URL for a video's thumbnail, generating it if necessary.
        
        Args:
            video_path: Path to the video file
            base_url: Base URL for the API
            
        Returns:
            URL to thumbnail, or None if generation failed
        """
        thumbnail_path = self.generate_thumbnail(video_path)
        if not thumbnail_path:
            return None
            
        # Convert to relative path for URL
        try:
            cache_key = self._get_cache_key(video_path)
            return f"{base_url}/thumbnail/{cache_key}.jpg"
        except Exception as e:
            logger.error(f"Failed to generate thumbnail URL for {video_path}: {e}")
            return None
    
    def cleanup_old_thumbnails(self, max_age_days: int = 30) -> int:
        """
        Remove thumbnail files older than specified days.
        
        Args:
            max_age_days: Maximum age in days for thumbnail files
            
        Returns:
            Number of files removed
        """
        try:
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            removed_count = 0
            
            for thumbnail_file in self.cache_dir.glob("*.jpg"):
                try:
                    if current_time - thumbnail_file.stat().st_mtime > max_age_seconds:
                        thumbnail_file.unlink()
                        removed_count += 1
                        logger.debug(f"Removed old thumbnail: {thumbnail_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove old thumbnail {thumbnail_file}: {e}")
            
            logger.info(f"Cleaned up {removed_count} old thumbnails")
            return removed_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old thumbnails: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the thumbnail cache."""
        try:
            total_files = 0
            total_size = 0
            
            for thumbnail_file in self.cache_dir.glob("*.jpg"):
                try:
                    stat = thumbnail_file.stat()
                    total_files += 1
                    total_size += stat.st_size
                except Exception:
                    continue
            
            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_dir": str(self.cache_dir)
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "cache_dir": str(self.cache_dir)
            }


# Global instance
_thumbnail_service = None

def get_thumbnail_service() -> ThumbnailService:
    """Get the global thumbnail service instance."""
    global _thumbnail_service
    if _thumbnail_service is None:
        _thumbnail_service = ThumbnailService()
    return _thumbnail_service
