"""
Face detection caching system for performance optimization.

Caches face detection results to disk to avoid re-processing the same video.
Uses video hash as cache key for integrity.
"""

import os
import pickle
import hashlib
import json
from typing import Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.face_cache")


@dataclass
class CachedFaceData:
    """Cached face detection data."""
    video_hash: str
    video_path: str
    video_duration: float
    video_width: int
    video_height: int
    face_positions: Dict  # timestamp -> FaceBox dict
    face_tracks: list     # List of FaceTrack dicts
    detection_params: Dict  # Parameters used for detection
    cache_version: str = "1.0"


class FaceDetectionCache:
    """
    Cache manager for face detection results.

    Caches face positions and tracks to disk, keyed by video file hash.
    Automatically invalidates cache if video changes or detection parameters change.
    """

    def __init__(
        self,
        cache_dir: str = ".face_detection_cache",
        enable_cache: bool = True,
        hash_method: str = "quick"  # "quick" or "full"
    ):
        """
        Initialize face detection cache.

        Args:
            cache_dir: Directory to store cache files
            enable_cache: Whether caching is enabled
            hash_method: Method for computing video hash
                        - "quick": Hash first/last 1MB (fast, might miss changes)
                        - "full": Hash entire file (slow, guaranteed detection)
        """
        self.cache_dir = Path(cache_dir)
        self.enable_cache = enable_cache
        self.hash_method = hash_method

        if self.enable_cache:
            # Create cache directory if needed
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Face detection cache enabled: {self.cache_dir}")

    def compute_video_hash(self, video_path: str) -> str:
        """
        Compute hash of video file for cache key.

        Args:
            video_path: Path to video file

        Returns:
            SHA256 hash string
        """
        hasher = hashlib.sha256()

        try:
            file_size = os.path.getsize(video_path)

            if self.hash_method == "quick" and file_size > 2 * 1024 * 1024:
                # Quick hash: first and last 1MB
                with open(video_path, 'rb') as f:
                    # First 1MB
                    chunk = f.read(1024 * 1024)
                    hasher.update(chunk)

                    # Last 1MB
                    f.seek(-1024 * 1024, os.SEEK_END)
                    chunk = f.read(1024 * 1024)
                    hasher.update(chunk)

                # Also include file size in hash
                hasher.update(str(file_size).encode())

            else:
                # Full hash: entire file
                with open(video_path, 'rb') as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        hasher.update(chunk)

            video_hash = hasher.hexdigest()

            logger.debug(
                f"Computed {'quick' if self.hash_method == 'quick' else 'full'} "
                f"hash for {video_path}: {video_hash[:12]}..."
            )

            return video_hash

        except Exception as e:
            logger.error(f"Failed to compute video hash: {e}")
            # Return a timestamp-based fallback
            import time
            return hashlib.sha256(f"{video_path}{time.time()}".encode()).hexdigest()

    def get_cache_path(self, video_hash: str) -> Path:
        """
        Get cache file path for a video hash.

        Args:
            video_hash: Video SHA256 hash

        Returns:
            Path to cache file
        """
        return self.cache_dir / f"{video_hash}.pkl"

    def get_metadata_path(self, video_hash: str) -> Path:
        """
        Get metadata file path for a video hash.

        Args:
            video_hash: Video SHA256 hash

        Returns:
            Path to metadata JSON file
        """
        return self.cache_dir / f"{video_hash}_meta.json"

    def load_from_cache(
        self,
        video_path: str,
        detection_params: Optional[Dict] = None
    ) -> Optional[CachedFaceData]:
        """
        Load face detection data from cache.

        Args:
            video_path: Path to video file
            detection_params: Detection parameters to verify cache validity

        Returns:
            CachedFaceData if valid cache exists, None otherwise
        """
        if not self.enable_cache:
            return None

        try:
            # Compute video hash
            video_hash = self.compute_video_hash(video_path)
            cache_path = self.get_cache_path(video_hash)

            if not cache_path.exists():
                logger.debug(f"No cache found for {video_path}")
                return None

            # Load cached data
            with open(cache_path, 'rb') as f:
                cached_data = pickle.load(f)

            # Validate cache
            if not isinstance(cached_data, CachedFaceData):
                logger.warning(f"Invalid cache format for {video_path}")
                return None

            # Check if detection parameters match (if provided)
            if detection_params is not None:
                cached_params = cached_data.detection_params

                # Check critical parameters
                critical_params = [
                    'detection_height',
                    'min_face_size_ratio',
                    'max_tracked_faces',
                    'enable_speaker_detection',
                    'enable_lip_detection'
                ]

                for param in critical_params:
                    if param in detection_params and param in cached_params:
                        if detection_params[param] != cached_params[param]:
                            logger.info(
                                f"Cache invalid: parameter '{param}' changed "
                                f"({cached_params[param]} -> {detection_params[param]})"
                            )
                            return None

            logger.info(
                f"✓ Loaded face detections from cache for {video_path} "
                f"({len(cached_data.face_positions)} positions, "
                f"{len(cached_data.face_tracks)} tracks)"
            )

            return cached_data

        except Exception as e:
            logger.error(f"Failed to load cache for {video_path}: {e}")
            return None

    def save_to_cache(
        self,
        video_path: str,
        video_duration: float,
        video_width: int,
        video_height: int,
        face_positions: Dict,
        face_tracks: list,
        detection_params: Dict
    ) -> bool:
        """
        Save face detection data to cache.

        Args:
            video_path: Path to video file
            video_duration: Video duration in seconds
            video_width: Video width
            video_height: Video height
            face_positions: Dict of timestamp -> FaceBox
            face_tracks: List of FaceTrack objects
            detection_params: Detection parameters used

        Returns:
            True if saved successfully, False otherwise
        """
        if not self.enable_cache:
            return False

        try:
            # Compute video hash
            video_hash = self.compute_video_hash(video_path)
            cache_path = self.get_cache_path(video_hash)
            metadata_path = self.get_metadata_path(video_hash)

            # Convert face_positions to serializable format
            # FaceBox objects need to be converted to dicts
            serializable_positions = {}
            for timestamp, face_box in face_positions.items():
                if hasattr(face_box, '__dict__'):
                    serializable_positions[timestamp] = asdict(face_box)
                else:
                    serializable_positions[timestamp] = face_box

            # Convert face_tracks to serializable format
            serializable_tracks = []
            for track in face_tracks:
                if hasattr(track, '__dict__'):
                    track_dict = asdict(track)
                    # Convert positions dict
                    track_dict['positions'] = {
                        ts: asdict(fb) if hasattr(fb, '__dict__') else fb
                        for ts, fb in track.positions.items()
                    }
                    serializable_tracks.append(track_dict)
                else:
                    serializable_tracks.append(track)

            # Create cached data object
            cached_data = CachedFaceData(
                video_hash=video_hash,
                video_path=video_path,
                video_duration=video_duration,
                video_width=video_width,
                video_height=video_height,
                face_positions=serializable_positions,
                face_tracks=serializable_tracks,
                detection_params=detection_params
            )

            # Save to pickle file
            with open(cache_path, 'wb') as f:
                pickle.dump(cached_data, f, protocol=pickle.HIGHEST_PROTOCOL)

            # Save metadata as JSON for human inspection
            metadata = {
                "video_path": video_path,
                "video_hash": video_hash,
                "video_duration": video_duration,
                "video_width": video_width,
                "video_height": video_height,
                "num_face_positions": len(face_positions),
                "num_face_tracks": len(face_tracks),
                "detection_params": detection_params,
                "cache_version": cached_data.cache_version
            }

            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(
                f"✓ Saved face detections to cache for {video_path} "
                f"({len(face_positions)} positions, {len(face_tracks)} tracks)"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to save cache for {video_path}: {e}")
            return False

    def invalidate_cache(self, video_path: str) -> bool:
        """
        Invalidate (delete) cache for a specific video.

        Args:
            video_path: Path to video file

        Returns:
            True if cache was deleted, False otherwise
        """
        if not self.enable_cache:
            return False

        try:
            video_hash = self.compute_video_hash(video_path)
            cache_path = self.get_cache_path(video_hash)
            metadata_path = self.get_metadata_path(video_hash)

            deleted = False

            if cache_path.exists():
                cache_path.unlink()
                deleted = True

            if metadata_path.exists():
                metadata_path.unlink()

            if deleted:
                logger.info(f"Invalidated cache for {video_path}")

            return deleted

        except Exception as e:
            logger.error(f"Failed to invalidate cache for {video_path}: {e}")
            return False

    def clear_all_cache(self) -> int:
        """
        Clear all cached face detection data.

        Returns:
            Number of cache files deleted
        """
        if not self.enable_cache:
            return 0

        try:
            count = 0

            # Delete all .pkl and .json files in cache directory
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
                count += 1

            for meta_file in self.cache_dir.glob("*.json"):
                meta_file.unlink()

            logger.info(f"Cleared all cache files ({count} files deleted)")

            return count

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.

        Returns:
            Dictionary with cache statistics
        """
        if not self.enable_cache or not self.cache_dir.exists():
            return {
                "enabled": False,
                "num_cached_videos": 0,
                "total_size_mb": 0.0
            }

        try:
            cache_files = list(self.cache_dir.glob("*.pkl"))
            total_size = sum(f.stat().st_size for f in cache_files)

            return {
                "enabled": True,
                "cache_dir": str(self.cache_dir),
                "num_cached_videos": len(cache_files),
                "total_size_mb": total_size / (1024 * 1024),
                "hash_method": self.hash_method
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"enabled": True, "error": str(e)}
