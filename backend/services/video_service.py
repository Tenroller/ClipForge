"""
Video service for managing video records in the database.
"""

import hashlib
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..database import get_job_store
from ..logging_config import get_logger
from ..utils.paths import get_output_path


class VideoService:
    """Service for managing video records."""
    
    def __init__(self):
        self.logger = get_logger("video_service")
        self.job_store = get_job_store()
        self.output_dir = get_output_path()
    
    def generate_video_id(self, job_id: str, filename: str, compilation_num: int = None, 
                         compilation_type: str = None) -> str:
        """Generate a unique video ID based on job and file information."""
        # Create a unique identifier based on job_id, filename, and optional parameters
        base_string = f"{job_id}_{filename}"
        if compilation_num is not None:
            base_string += f"_comp{compilation_num}"
        if compilation_type:
            base_string += f"_{compilation_type}"
        
        # Create a shorter hash for the ID
        hash_object = hashlib.md5(base_string.encode())
        return f"vid_{hash_object.hexdigest()[:12]}"
    
    def register_video(self, job_id: str, file_path: str, workflow: str, 
                      video_type: str = None, compilation_type: str = None, 
                      compilation_num: int = None, metadata: Dict[str, Any] = None) -> str:
        """
        Register a new video in the database.
        
        Args:
            job_id: ID of the job that generated the video
            file_path: Full path to the video file
            workflow: Video generation workflow (moneyprinter, brainrot, etc.)
            video_type: Type of video (ai_generated, compilation, etc.)
            compilation_type: For brainrot videos (normal, tts, etc.)
            compilation_num: For brainrot videos, compilation number
            metadata: Additional metadata to store
            
        Returns:
            The generated video ID
        """
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                raise FileNotFoundError(f"Video file not found: {file_path}")
            
            # Generate unique video ID
            video_id = self.generate_video_id(
                job_id, file_path_obj.name, compilation_num, compilation_type
            )
            
            # Get file stats
            stat = file_path_obj.stat()
            size_bytes = stat.st_size
            
            # Try to get duration if moviepy is available
            duration_seconds = None
            try:
                from moviepy import VideoFileClip
                with VideoFileClip(str(file_path_obj)) as clip:
                    duration_seconds = clip.duration
            except Exception as e:
                self.logger.debug(f"Could not get video duration for {file_path}: {e}")
            
            # Create video record
            self.job_store.create_video(
                video_id=video_id,
                filename=file_path_obj.name,
                file_path=str(file_path_obj.resolve()),
                job_id=job_id,
                workflow=workflow,
                video_type=video_type,
                size_bytes=size_bytes,
                duration_seconds=duration_seconds,
                compilation_type=compilation_type,
                compilation_num=compilation_num,
                metadata=metadata or {}
            )
            
            self.logger.info(f"Registered video {video_id} for job {job_id}: {file_path_obj.name}")
            return video_id
            
        except Exception as e:
            self.logger.error(f"Failed to register video {file_path}: {e}")
            raise
    
    def mark_video_posted(self, video_id: str) -> bool:
        """Mark a video as posted."""
        try:
            success = self.job_store.update_video(video_id, posted=True)
            if success:
                self.logger.info(f"Marked video {video_id} as posted")
            else:
                self.logger.warning(f"Video {video_id} not found when marking as posted")
            return success
        except Exception as e:
            self.logger.error(f"Failed to mark video {video_id} as posted: {e}")
            return False
    
    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video information by ID."""
        try:
            return self.job_store.get_video(video_id)
        except Exception as e:
            self.logger.error(f"Failed to get video {video_id}: {e}")
            return None
    
    def list_videos(self, limit: int = 100, offset: int = 0, workflow: str = None, 
                   posted: bool = None, job_id: str = None) -> List[Dict[str, Any]]:
        """List videos with optional filtering."""
        try:
            return self.job_store.list_videos(
                limit=limit, offset=offset, workflow=workflow, posted=posted, job_id=job_id
            )
        except Exception as e:
            self.logger.error(f"Failed to list videos: {e}")
            return []
    
    def get_unposted_videos(self, workflow: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get videos that haven't been posted yet."""
        return self.list_videos(limit=limit, posted=False, workflow=workflow)
    
    def sync_videos_from_job_results(self) -> Dict[str, Any]:
        """
        Sync video records from existing job results.
        This is useful for migrating existing videos to the new tracking system.
        """
        try:
            # Get all completed jobs
            jobs = self.job_store.list_jobs(limit=10000, status="done")
            
            stats = {
                "processed_jobs": 0,
                "registered_videos": 0,
                "skipped_videos": 0,
                "errors": []
            }
            
            for job in jobs:
                try:
                    stats["processed_jobs"] += 1
                    job_result = job.get("result", {})
                    job_id = job["id"]
                    workflow = job.get("workflow", "unknown")
                    
                    # Handle MoneyPrinter workflow
                    if workflow == "moneyprinter" and "output" in job_result:
                        video_path = job_result["output"]
                        if video_path and Path(video_path).exists():
                            # Check if video already exists in database
                            existing_videos = self.list_videos(job_id=job_id, limit=1)
                            if not existing_videos:
                                try:
                                    video_id = self.register_video(
                                        job_id=job_id,
                                        file_path=video_path,
                                        workflow=workflow,
                                        video_type="ai_generated",
                                        metadata={
                                            "migrated_from_job_result": True,
                                            "original_posted_status": job_result.get("posted", False)
                                        }
                                    )
                                    
                                    # Preserve original posted status
                                    if job_result.get("posted", False):
                                        self.mark_video_posted(video_id)
                                    
                                    stats["registered_videos"] += 1
                                except Exception as e:
                                    stats["errors"].append(f"MoneyPrinter job {job_id}: {str(e)}")
                            else:
                                stats["skipped_videos"] += 1
                    
                    # Handle Brainrot workflow
                    elif workflow == "brainrot" and "generated_videos" in job_result:
                        generated_videos = job_result.get("generated_videos", [])
                        if generated_videos:
                            for video_data in generated_videos:
                                if not video_data:
                                    continue
                                    
                                video_path = video_data.get("path")
                                if video_path and Path(video_path).exists():
                                    try:
                                        video_id = self.register_video(
                                            job_id=job_id,
                                            file_path=video_path,
                                            workflow=workflow,
                                            video_type="compilation",
                                            compilation_type=video_data.get("compilation_type"),
                                            compilation_num=video_data.get("compilation_num"),
                                            metadata={
                                                "migrated_from_job_result": True,
                                                "original_posted_status": video_data.get("posted", False),
                                                "original_video_data": video_data
                                            }
                                        )
                                        
                                        # Preserve original posted status
                                        if video_data.get("posted", False):
                                            self.mark_video_posted(video_id)
                                        
                                        stats["registered_videos"] += 1
                                    except Exception as e:
                                        stats["errors"].append(f"Brainrot job {job_id}, video {video_path}: {str(e)}")
                                else:
                                    stats["skipped_videos"] += 1
                
                except Exception as e:
                    stats["errors"].append(f"Job {job.get('id', 'unknown')}: {str(e)}")
            
            self.logger.info(f"Video sync completed: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to sync videos from job results: {e}")
            return {"error": str(e)}
    
    def scan_and_register_orphaned_videos(self) -> Dict[str, Any]:
        """
        Scan the output directory for videos not tracked in the database and register them.
        """
        try:
            stats = {
                "scanned_files": 0,
                "registered_videos": 0,
                "skipped_videos": 0,
                "errors": []
            }
            
            if not self.output_dir.exists():
                return stats
            
            # Get all existing video IDs to avoid duplicates
            existing_videos = self.list_videos(limit=10000)
            existing_paths = {video["file_path"] for video in existing_videos}
            
            # Recursively find all .mp4 files
            for video_file in self.output_dir.rglob("*.mp4"):
                if not video_file.is_file():
                    continue
                
                stats["scanned_files"] += 1
                video_path_str = str(video_file.resolve())
                
                # Skip if already registered
                if video_path_str in existing_paths:
                    stats["skipped_videos"] += 1
                    continue
                
                try:
                    # Determine job ID from file path structure
                    path_parts = video_file.relative_to(self.output_dir).parts
                    if len(path_parts) == 0:
                        continue
                    
                    potential_job_id = path_parts[0]
                    
                    # Determine video type and workflow from filename
                    filename_lower = video_file.name.lower()
                    if "compilation" in filename_lower:
                        workflow = "brainrot"
                        video_type = "compilation"
                        
                        # Extract compilation info
                        compilation_type = None
                        compilation_num = None
                        
                        if "_normal" in filename_lower:
                            compilation_type = "normal"
                        elif "_tts" in filename_lower:
                            compilation_type = "tts"
                        
                        # Extract compilation number
                        if "_compilation_" in filename_lower:
                            parts = filename_lower.split("_compilation_")
                            if len(parts) > 1:
                                num_part = parts[1].split("_")[0]
                                try:
                                    compilation_num = int(num_part)
                                except ValueError:
                                    pass
                    else:
                        workflow = "moneyprinter"
                        video_type = "ai_generated"
                        compilation_type = None
                        compilation_num = None
                    
                    # Register the orphaned video
                    video_id = self.register_video(
                        job_id=potential_job_id,
                        file_path=video_path_str,
                        workflow=workflow,
                        video_type=video_type,
                        compilation_type=compilation_type,
                        compilation_num=compilation_num,
                        metadata={
                            "orphaned_video": True,
                            "discovered_at": time.time()
                        }
                    )
                    
                    stats["registered_videos"] += 1
                    
                except Exception as e:
                    stats["errors"].append(f"File {video_file}: {str(e)}")
            
            self.logger.info(f"Orphaned video scan completed: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to scan for orphaned videos: {e}")
            return {"error": str(e)}


# Global video service instance
_video_service: Optional[VideoService] = None


def get_video_service() -> VideoService:
    """Get or create the global video service instance."""
    global _video_service
    if _video_service is None:
        _video_service = VideoService()
    return _video_service
