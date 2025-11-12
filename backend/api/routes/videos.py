"""
Video management and listing endpoints.
"""

from typing import Dict, Any, Optional, List
from pathlib import Path
import time
import requests

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...database import get_job_store
from ...logging_config import get_logger
from ...utils.paths import get_output_path, get_project_root
from ...services.thumbnail_service import get_thumbnail_service
from ...services.video_service import get_video_service
from ...core.config import AppConfig
from ...utils.paths import get_output_path, get_project_root

router = APIRouter()
logger = get_logger("videos")

# Get database instance
job_store = get_job_store()

# Get thumbnail service
thumbnail_service = get_thumbnail_service()

# Get video service
video_service = get_video_service()

class PostVideoRequest(BaseModel):
    """Request model for posting a video to webhook"""
    video_id: str
    job_id: str


def _is_allowed_path(file_path: Path) -> bool:
    """Check if a file path is within allowed directories."""
    try:
        # Define allowed root directories
        project_root = get_project_root()
        allowed_roots = [
            get_output_path().resolve(),
            (project_root / "AIvideos_output").resolve(),
            (project_root / "temp").resolve(),
            (project_root / "backend" / "temp").resolve(),
            (project_root / "backend" / "final_videos").resolve(),
            (project_root / "video-processor" / "output").resolve(),
        ]

        file_resolved = file_path.resolve()
        
        for root in allowed_roots:
            try:
                # Check if file is under this root
                file_resolved.relative_to(root)
                return True
            except ValueError:
                continue
        
        return False
        
    except Exception as e:
        logger.warning(f"Error checking allowed path {file_path}: {e}")
        return False


def scan_orphaned_videos() -> List[Dict[str, Any]]:
    """
    Scan the output directory for videos that aren't tracked in the job system.
    
    Returns list of video information for orphaned videos.
    """
    orphaned_videos = []
    output_dir = get_output_path()
    
    if not output_dir.exists():
        return orphaned_videos
    
    try:
        # Get all job IDs from database for tracking
        all_jobs = job_store.list_jobs(limit=10000)  # Get all jobs
        if all_jobs is None:
            all_jobs = []
        tracked_job_ids = {job["id"] for job in all_jobs}
        
        # Recursively find all .mp4 files in output directory
        for video_file in output_dir.rglob("*.mp4"):
            if not video_file.is_file():
                continue
                
            try:
                # Determine job ID from file path
                # Typical structure: output/job_id/file.mp4 or output/job_id/subfolder/file.mp4
                path_parts = video_file.relative_to(output_dir).parts
                
                if len(path_parts) == 0:
                    continue
                    
                # First part should be job ID
                potential_job_id = path_parts[0]
                
                # Skip if this video is already tracked by an existing job
                if potential_job_id in tracked_job_ids:
                    # Check if this specific video is actually in the job result
                    job = next((j for j in all_jobs if j["id"] == potential_job_id), None)
                    if job and job.get("result"):
                        job_result = job["result"]
                        
                        # Check if video is tracked in moneyprinter workflow
                        if job.get("workflow") == "moneyprinter":
                            if "output" in job_result:
                                tracked_path = Path(job_result["output"])
                                if tracked_path.exists() and tracked_path.samefile(video_file):
                                    continue  # This video is properly tracked
                        
                        # Check if video is tracked in brainrot workflow
                        elif job.get("workflow") == "brainrot":
                            if "generated_videos" in job_result and job_result["generated_videos"] is not None:
                                generated_videos = job_result["generated_videos"]
                                tracked_paths = []
                                for v in generated_videos:
                                    if v and v.get("path"):  # Check if video data and path exist
                                        try:
                                            tracked_paths.append(Path(v["path"]))
                                        except (TypeError, ValueError):
                                            continue  # Skip invalid paths
                                if any(p.exists() and p.samefile(video_file) for p in tracked_paths):
                                    continue  # This video is properly tracked

                        # Check if video is tracked in podcastclips workflow
                        elif job.get("workflow") == "podcastclips":
                            if "generated_videos" in job_result and job_result["generated_videos"] is not None:
                                generated_videos = job_result["generated_videos"]
                                tracked_paths = []
                                for v in generated_videos:
                                    if v and v.get("path"):  # Check if video data and path exist
                                        try:
                                            tracked_paths.append(Path(v["path"]))
                                        except (TypeError, ValueError):
                                            continue  # Skip invalid paths
                                if any(p.exists() and p.samefile(video_file) for p in tracked_paths):
                                    continue  # This video is properly tracked
                
                # This video appears to be orphaned
                stat = video_file.stat()

                # Try to determine video type from path structure
                video_type = "unknown"
                compilation_type = None
                compilation_num = None

                if "compilation" in video_file.name.lower():
                    video_type = "compilation"
                    # Try to extract compilation info from filename
                    filename_lower = video_file.name.lower()
                    if "_compilation_" in filename_lower:
                        parts = filename_lower.split("_compilation_")
                        if len(parts) > 1:
                            num_part = parts[1].split("_")[0]
                            try:
                                compilation_num = int(num_part)
                            except ValueError:
                                pass

                    if "_normal" in filename_lower:
                        compilation_type = "normal"
                    elif "_tts" in filename_lower:
                        compilation_type = "tts"
                else:
                    video_type = "ai_generated"

                # Determine workflow from job record if available, otherwise guess from video type
                workflow = "moneyprinter"  # default
                if job and job.get("workflow"):
                    workflow = job["workflow"]
                elif video_type == "compilation":
                    # Default to brainrot for compilation videos if no job record
                    workflow = "brainrot"

                # Adjust video_type based on workflow
                if workflow == "podcastclips":
                    video_type = "podcast_clip"

                # Use file modification time as created_at
                created_at = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(stat.st_mtime))
                
                video_info = {
                    "id": f"orphaned_{potential_job_id}_{video_file.stem}",
                    "job_id": potential_job_id,
                    "workflow": workflow,
                    "filename": video_file.name,
                    "path": str(video_file),
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": created_at,
                    "duration_seconds": None,  # Could be calculated with moviepy if needed
                    "download_url": f"/api/download?path={video_file.resolve()}",
                    "thumbnail_url": thumbnail_service.get_thumbnail_url(str(video_file)),
                    "video_type": video_type,
                    "compilation_type": compilation_type,
                    "compilation_num": compilation_num,
                    "is_orphaned": True,  # Flag to indicate this is an orphaned video
                    "posted": False  # Orphaned videos are never posted
                }
                
                orphaned_videos.append(video_info)
                
            except Exception as e:
                logger.warning(f"Failed to process orphaned video {video_file}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Failed to scan for orphaned videos: {e}")
    
    return orphaned_videos


@router.get("/list-videos", summary="Legacy: list videos (compat)")
def legacy_list_videos(dir: Optional[str] = None) -> Dict[str, Any]:
    """Legacy compatibility endpoint used by older clients/tests.

    Returns a simple JSON with files and dir keys similar to older API.
    """
    try:
        output_dir = get_output_path()
        # If dir query param provided, attempt to resolve but keep safe
        target_dir = Path(dir) if dir else output_dir

        # Only allow listing within allowed roots
        if not _is_allowed_path(target_dir):
            # Match existing behavior: 403 or 404 is acceptable; use 404 here
            raise HTTPException(status_code=404, detail="Directory not allowed")

        files = []
        if target_dir.exists() and target_dir.is_dir():
            for p in target_dir.iterdir():
                files.append({
                    "name": p.name,
                    "is_dir": p.is_dir(),
                    "path": str(p)
                })

        return {"files": files, "dir": str(target_dir)}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Legacy list-videos failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


## Removed legacy /videos/all endpoint. Use /api/videos/managed for database-tracked videos.


@router.get("/videos/stats", summary="Get Video Statistics")
def get_video_stats() -> Dict[str, Any]:
    """Get statistics about all generated videos, including orphaned ones."""
    try:
        # Get stats from tracked jobs
        logger.info("Getting job stats - starting")
        try:
            jobs = job_store.list_jobs(limit=1000, status="done")
            logger.info(f"Got jobs list: {type(jobs)}, length: {len(jobs) if jobs else 'None'}")
            if jobs is None:
                logger.warning("Jobs list is None, setting to empty list")
                jobs = []
        except Exception as db_err:
            logger.error(f"Error fetching jobs from job_store: {db_err}")
            # Fall back to empty jobs list; continue gathering orphaned video stats
            jobs = []
        
        stats = {
            "total_videos": 0,
            "total_size_mb": 0,
            "workflows": {
                "moneyprinter": {"count": 0, "size_mb": 0},
                "brainrot": {"count": 0, "size_mb": 0},
                "podcastclips": {"count": 0, "size_mb": 0}
            },
            "video_types": {
                "ai_generated": {"count": 0, "size_mb": 0},
                "compilation": {"count": 0, "size_mb": 0},
                "podcast_clip": {"count": 0, "size_mb": 0}
            }
        }
        
        for job in jobs:
            job_result = job.get("result", {})
            job_workflow = job.get("workflow", "unknown")
            
            if job_workflow == "moneyprinter" and "output" in job_result:
                video_path = job_result["output"]
                if video_path and Path(video_path).exists():
                    try:
                        size_mb = Path(video_path).stat().st_size / (1024 * 1024)
                        stats["total_videos"] += 1
                        stats["total_size_mb"] += size_mb
                        stats["workflows"]["moneyprinter"]["count"] += 1
                        stats["workflows"]["moneyprinter"]["size_mb"] += size_mb
                        stats["video_types"]["ai_generated"]["count"] += 1
                        stats["video_types"]["ai_generated"]["size_mb"] += size_mb
                    except Exception:
                        continue
                        
            elif job_workflow == "brainrot" and "generated_videos" in job_result:
                generated_videos = job_result.get("generated_videos", [])
                # Handle case where generated_videos could be None
                if generated_videos is None:
                    generated_videos = []
                for video_data in generated_videos:
                    if video_data is None:  # Skip None video entries
                        continue
                    video_path = video_data.get("path")
                    if video_path and Path(video_path).exists():
                        try:
                            size_mb = video_data.get("size_mb", 0)
                            stats["total_videos"] += 1
                            stats["total_size_mb"] += size_mb
                            stats["workflows"]["brainrot"]["count"] += 1
                            stats["workflows"]["brainrot"]["size_mb"] += size_mb
                            stats["video_types"]["compilation"]["count"] += 1
                            stats["video_types"]["compilation"]["size_mb"] += size_mb
                        except Exception:
                            continue

            elif job_workflow == "podcastclips" and "generated_videos" in job_result:
                generated_videos = job_result.get("generated_videos", [])
                # Handle case where generated_videos could be None
                if generated_videos is None:
                    generated_videos = []
                for video_data in generated_videos:
                    if video_data is None:  # Skip None video entries
                        continue
                    video_path = video_data.get("path")
                    if video_path and Path(video_path).exists():
                        try:
                            size_mb = video_data.get("size_mb", 0)
                            stats["total_videos"] += 1
                            stats["total_size_mb"] += size_mb
                            stats["workflows"]["podcastclips"]["count"] += 1
                            stats["workflows"]["podcastclips"]["size_mb"] += size_mb
                            stats["video_types"]["podcast_clip"]["count"] += 1
                            stats["video_types"]["podcast_clip"]["size_mb"] += size_mb
                        except Exception:
                            continue
        
        # Add orphaned videos to stats
        logger.info("Getting orphaned videos")
        try:
            orphaned_videos = scan_orphaned_videos() or []
            logger.info(f"Got orphaned videos: {type(orphaned_videos)}, length: {len(orphaned_videos)}")
        except Exception as e:
            logger.error(f"Failed to scan orphaned videos: {e}")
            orphaned_videos = []
            
        for video in orphaned_videos:
            try:
                size_mb = video.get("size_mb", 0)
                stats["total_videos"] += 1
                stats["total_size_mb"] += size_mb
                
                workflow = video.get("workflow", "unknown")
                video_type = video.get("video_type", "unknown")
                
                if workflow in stats["workflows"]:
                    stats["workflows"][workflow]["count"] += 1
                    stats["workflows"][workflow]["size_mb"] += size_mb
                
                if video_type in stats["video_types"]:
                    stats["video_types"][video_type]["count"] += 1
                    stats["video_types"][video_type]["size_mb"] += size_mb
                    
            except Exception:
                continue
        
        # Round sizes
        stats["total_size_mb"] = round(stats["total_size_mb"], 2)
        for workflow_stats in stats["workflows"].values():
            workflow_stats["size_mb"] = round(workflow_stats["size_mb"], 2)
        for type_stats in stats["video_types"].values():
            type_stats["size_mb"] = round(type_stats["size_mb"], 2)
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get video stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get video stats: {e}")


@router.get("/download", summary="Download Video File")
def download_file(path: str):
    """
    Download a video file by path.
    
    Supports downloading files from allowed directories with security checks.
    """
    try:
        file_path = Path(path)
        
        # If the path doesn't exist as-is, try to resolve it relative to allowed directories
        if not file_path.exists() or not file_path.is_file():
            # Define allowed root directories
            project_root = get_project_root()
            allowed_roots = [
                get_output_path().resolve(),
                (project_root / "AIvideos_output").resolve(),
                (project_root / "temp").resolve(),
                (project_root / "backend" / "temp").resolve(),
                (project_root / "backend" / "final_videos").resolve(),
                (project_root / "video-processor" / "output").resolve(),
            ]

            found_path = None
            for root in allowed_roots:
                # Try absolute path from root
                candidate = root / Path(path).name
                if candidate.exists() and candidate.is_file():
                    found_path = candidate
                    break
                
                # Try relative path from root
                try:
                    candidate = root / path
                    if candidate.exists() and candidate.is_file():
                        found_path = candidate
                        break
                except Exception:
                    continue
                
                # Handle paths like "output/job_id/file.mp4"
                if "output" in path:
                    filename = Path(path).name
                    candidate = root / filename
                    if candidate.exists() and candidate.is_file():
                        found_path = candidate
                        break
            
            if found_path:
                file_path = found_path
            else:
                raise HTTPException(status_code=404, detail="File not found")
        
        # Security check: ensure file is in allowed directory
        if not _is_allowed_path(file_path):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Determine media type
        media_type = "application/octet-stream"
        if file_path.suffix.lower() == ".mp4":
            media_type = "video/mp4"
        elif file_path.suffix.lower() in [".mov", ".avi", ".mkv"]:
            media_type = "video/mp4"  # Serve as mp4 for compatibility
        elif file_path.suffix.lower() in [".mp3", ".wav", ".m4a"]:
            media_type = "audio/mpeg"
        
        return FileResponse(
            str(file_path), 
            filename=file_path.name, 
            media_type=media_type
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to download file {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {e}")


@router.get("/thumbnail/{cache_key}", summary="Get Video Thumbnail")
def get_thumbnail(cache_key: str):
    """
    Serve a video thumbnail by cache key.
    
    Cache keys are generated automatically when thumbnails are created.
    """
    try:
        # Validate cache key format (should be hex)
        if not cache_key.endswith('.jpg'):
            cache_key = f"{cache_key}.jpg"
        
        # Security: ensure cache key only contains safe characters
        safe_cache_key = ''.join(c for c in cache_key if c.isalnum() or c in '.-_')
        if safe_cache_key != cache_key:
            raise HTTPException(status_code=400, detail="Invalid cache key format")
        
        # Get thumbnail path
        thumbnail_path = thumbnail_service.cache_dir / safe_cache_key
        
        if not thumbnail_path.exists() or not thumbnail_path.is_file():
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        
        return FileResponse(
            str(thumbnail_path),
            media_type="image/jpeg",
            filename=f"thumbnail_{safe_cache_key}"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to serve thumbnail {cache_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to serve thumbnail: {e}")


@router.post("/thumbnails/generate/{job_id}", summary="Generate Thumbnails for Job")
def generate_thumbnails_for_job(job_id: str):
    """
    Generate thumbnails for all videos in a specific job.
    
    This can be used to pre-generate thumbnails for better performance.
    """
    try:
        job = job_store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_result = job.get("result", {})
        if not job_result:
            raise HTTPException(status_code=400, detail="Job has no results")
        
        generated_count = 0
        job_workflow = job.get("workflow", "unknown")
        
        # Handle MoneyPrinter workflow
        if job_workflow == "moneyprinter" and "output" in job_result:
            video_path = job_result["output"]
            if video_path and Path(video_path).exists():
                if thumbnail_service.generate_thumbnail(video_path):
                    generated_count += 1
        
        # Handle Brainrot workflow
        elif job_workflow == "brainrot" and "generated_videos" in job_result:
            generated_videos = job_result.get("generated_videos", [])
            for video_data in generated_videos:
                video_path = video_data.get("path")
                if video_path and Path(video_path).exists():
                    if thumbnail_service.generate_thumbnail(video_path):
                        generated_count += 1
        
        return {
            "job_id": job_id,
            "generated_thumbnails": generated_count,
            "message": f"Generated {generated_count} thumbnails for job {job_id}"
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to generate thumbnails for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate thumbnails: {e}")


@router.get("/thumbnails/stats", summary="Get Thumbnail Cache Statistics")
def get_thumbnail_stats():
    """Get statistics about the thumbnail cache."""
    try:
        stats = thumbnail_service.get_cache_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get thumbnail stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get thumbnail stats: {e}")


@router.delete("/thumbnails/cleanup", summary="Cleanup Old Thumbnails")
def cleanup_thumbnails(max_age_days: int = 30):
    """
    Remove thumbnail files older than specified days.
    
    Args:
        max_age_days: Maximum age in days for thumbnail files (default: 30)
    """
    try:
        removed_count = thumbnail_service.cleanup_old_thumbnails(max_age_days)
        return {
            "removed_count": removed_count,
            "max_age_days": max_age_days,
            "message": f"Removed {removed_count} old thumbnails"
        }
    except Exception as e:
        logger.error(f"Failed to cleanup thumbnails: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup thumbnails: {e}")


@router.post("/videos/post", summary="Post Video to Webhook")
def post_video_to_webhook(request: PostVideoRequest):
    """
    Post a video to the specified webhook and mark it as posted.
    
    Args:
        request: Contains video_id and job_id to identify the video to post
    """
    try:
        # Get the job (if it exists)
        job = job_store.get_job(request.job_id)
        job_result = job.get("result", {}) if job else {}
        job_workflow = job.get("workflow", "unknown") if job else "unknown"
        video_path = None
        video_data = None
        is_orphaned_video = request.video_id.startswith("orphaned_")
        
        # If no job exists, treat as orphaned video and continue with file-based approach
        if not job:
            logger.info(f"Job {request.job_id} not found in database, treating video {request.video_id} as orphaned")
        
        # Handle orphaned videos or videos without job results
        if is_orphaned_video or not job_result or not job:
            logger.info(f"Handling orphaned/missing job video: {request.video_id}")
            
            # For orphaned videos, try to find the file directly in the output directory
            output_dir = get_output_path()
            
            # Parse orphaned video ID format: "orphaned_{job_id}_{video_file_stem}"
            if is_orphaned_video:
                # Extract the original filename from the orphaned video ID
                id_parts = request.video_id.split("_", 2)  # Split into max 3 parts
                if len(id_parts) >= 3:
                    file_stem = id_parts[2]  # Everything after "orphaned_{job_id}_"
                    
                    # Search for the video file in the job's output directory
                    job_output_dir = output_dir / request.job_id
                    if job_output_dir.exists():
                        # Look for .mp4 files that match the stem
                        for video_file in job_output_dir.rglob("*.mp4"):
                            if video_file.stem == file_stem:
                                video_path = str(video_file)
                                break
            
            # If still no video path found, try to search based on job_id directory
            if not video_path:
                job_output_dir = output_dir / request.job_id
                if job_output_dir.exists():
                    # For videos without results, try to find any video in the job directory
                    video_files = list(job_output_dir.rglob("*.mp4"))
                    if video_files:
                        video_path = str(video_files[0])  # Use the first video found
                        logger.info(f"Found video file for job without results: {video_path}")
                        
                        # Try to detect workflow from file path
                        if not job:
                            path_str = str(video_files[0]).lower()
                            if "brainrot" in path_str or "compilation" in path_str:
                                job_workflow = "brainrot"
                            elif "moneyprinter" in path_str or "ai_generated" in path_str:
                                job_workflow = "moneyprinter"
                            else:
                                # Check parent directory names for clues
                                parent_dirs = [p.name.lower() for p in video_files[0].parents]
                                if any("brainrot" in p or "compilation" in p for p in parent_dirs):
                                    job_workflow = "brainrot"
                                elif any("moneyprinter" in p or "ai" in p for p in parent_dirs):
                                    job_workflow = "moneyprinter"
            
            if not video_path or not Path(video_path).exists():
                raise HTTPException(status_code=404, detail="Video file not found")
                
        else:
            # Handle tracked videos with job results (original logic)
            # Find the video in the job result
            if job_workflow == "moneyprinter" and "output" in job_result:
                # For moneyprinter, there's only one video
                if request.video_id == f"{request.job_id}_main":
                    video_path = job_result["output"]
                    if not video_path or not Path(video_path).exists():
                        raise HTTPException(status_code=404, detail="Video file not found")
            
            elif job_workflow == "brainrot" and "generated_videos" in job_result:
                # For brainrot, search through generated videos
                generated_videos = job_result.get("generated_videos", [])
                for video in generated_videos:
                    video_id = f"{request.job_id}_{video.get('compilation_num', 'unknown')}_{video.get('variation', 'unknown')}"
                    if video_id == request.video_id:
                        video_path = video.get("path")
                        video_data = video
                        break
                
                if not video_path or not Path(video_path).exists():
                    raise HTTPException(status_code=404, detail="Video file not found")
            
            else:
                raise HTTPException(status_code=400, detail="Invalid workflow or no videos found")
        
        # Ensure video_path is not None
        if not video_path:
            raise HTTPException(status_code=404, detail="Video file not found")
        
        video_file_path = Path(video_path)
        
        # Note: Videos can be re-posted to webhook multiple times
        # We still track the posted status but don't prevent re-posting
        
        # Post video to webhook
        config = AppConfig.from_env()
        webhook_url = config.webhook_url or "https://n8n.dight.app/webhook/29ad5d4d-0fd0-4eb7-a8e1-8f782c38b3d4"
        webhook_success = False
        webhook_error = None
        
        # Skip webhook if no URL is configured
        if not webhook_url:
            logger.info(f"No webhook URL configured, skipping webhook posting for video {request.video_id}")
            webhook_success = True  # Consider it successful if no webhook is configured
        else:
            try:
                with open(video_file_path, 'rb') as video_file:
                    files = {
                        'video': (video_file_path.name, video_file, 'video/mp4')
                    }
                    
                    # Add metadata as form data
                    data = {
                        'video_id': request.video_id,
                        'job_id': request.job_id,
                        'filename': video_file_path.name,
                        'workflow': job_workflow
                    }
                    
                    response = requests.post(webhook_url, files=files, data=data, timeout=30)
                    
                    if response.status_code == 200:
                        webhook_success = True
                        logger.info(f"Successfully posted video {request.video_id} to webhook")
                    else:
                        webhook_error = f"Webhook returned status {response.status_code}: {response.text}"
                        logger.warning(f"Webhook failed for video {request.video_id}: {webhook_error}")
                    
            except requests.exceptions.RequestException as e:
                webhook_error = str(e)
                logger.error(f"Failed to post video to webhook: {e}")
            
            # Don't fail the entire request if webhook fails - just log it
            if not webhook_success:
                logger.warning(f"Video {request.video_id} processed but webhook posting failed: {webhook_error}")
        
        # Update the job result to mark video as posted (legacy system)
        if is_orphaned_video:
            # For orphaned videos, we can't update job results since they don't exist
            # The video will still be posted to the webhook successfully
            logger.info(f"Posted orphaned video {request.video_id} - cannot track posted status in job results")
        elif job_workflow == "moneyprinter":
            job_result["posted"] = True
            job_store.update_job(request.job_id, result=job_result)
        elif job_workflow == "brainrot" and video_data:
            video_data["posted"] = True
            job_store.update_job(request.job_id, result=job_result)
        
        # Also try to mark as posted in the new video tracking system
        try:
            # Try to find the video in the new tracking system by file path
            if video_path:
                managed_videos = video_service.list_videos(limit=1000)  # Get all videos to search
                for managed_video in managed_videos:
                    if managed_video["file_path"] == str(Path(video_path).resolve()):
                        success = video_service.mark_video_posted(managed_video["id"])
                        if success:
                            logger.info(f"Also marked video {managed_video['id']} as posted in new tracking system")
                        break
        except Exception as e:
            logger.debug(f"Could not update posted status in new video tracking system: {e}")
            # Don't fail the request if the new system has issues
        
        if webhook_success:
            logger.info(f"Successfully posted video {request.video_id} to webhook")
        else:
            logger.warning(f"Video {request.video_id} processed but webhook posting failed: {webhook_error}")
        
        return {
            "video_id": request.video_id,
            "job_id": request.job_id,
            "posted": webhook_success,
            "webhook_success": webhook_success,
            "webhook_error": webhook_error,
            "message": f"Video {request.video_id} processed successfully" + (f" and posted to webhook" if webhook_success else f" but webhook posting failed: {webhook_error}")
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to post video {request.video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to post video: {str(e)}")
