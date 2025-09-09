"""
Video management and listing endpoints.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...database import get_job_store
from ...logging_config import get_logger

router = APIRouter()
logger = get_logger("videos")

# Get database instance
job_store = get_job_store()


@router.get("/videos/all", summary="List All Generated Videos")
def list_all_videos(
    limit: int = 100,
    offset: int = 0,
    workflow: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc"
) -> Dict[str, Any]:
    """
    List all generated videos across all jobs with metadata.
    
    Returns videos with job information, file details, and download URLs.
    """
    try:
        # Get jobs with completed videos
        valid_statuses = ["done"] if status is None else [status] if status == "done" else []
        jobs = job_store.list_jobs(limit=limit*2, status="done")  # Get more to account for filtering
        
        if workflow:
            jobs = [job for job in jobs if job.get("workflow") == workflow]
        
        videos = []
        processed_count = 0
        
        for job in jobs:
            if processed_count >= offset + limit:
                break
                
            job_result = job.get("result", {})
            if not job_result:
                continue
                
            job_id = job["id"]
            job_workflow = job.get("workflow", "unknown")
            created_at = job.get("created_at")
            duration_seconds = job.get("duration_seconds")
            
            # Handle MoneyPrinter workflow (single video)
            if job_workflow == "moneyprinter" and "output" in job_result:
                video_path = job_result["output"]
                if video_path and Path(video_path).exists():
                    try:
                        stat = Path(video_path).stat()
                        video_info = {
                            "id": f"{job_id}_main",
                            "job_id": job_id,
                            "workflow": job_workflow,
                            "filename": Path(video_path).name,
                            "path": video_path,
                            "size_bytes": stat.st_size,
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "created_at": created_at,
                            "duration_seconds": duration_seconds,
                            "download_url": f"/api/download?path={Path(video_path).resolve()}",
                            "thumbnail_url": None,  # Could be implemented later
                            "subtitles_path": job_result.get("subtitles"),
                            "video_type": "ai_generated"
                        }
                        
                        if processed_count >= offset:
                            videos.append(video_info)
                        processed_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Failed to process video {video_path}: {e}")
            
            # Handle Brainrot workflow (multiple videos)
            elif job_workflow == "brainrot" and "generated_videos" in job_result:
                generated_videos = job_result.get("generated_videos", [])
                for video_data in generated_videos:
                    if processed_count >= offset + limit:
                        break
                        
                    video_path = video_data.get("path")
                    if video_path and Path(video_path).exists():
                        try:
                            video_info = {
                                "id": f"{job_id}_{video_data.get('compilation_num', 'unknown')}_{video_data.get('variation', 'unknown')}",
                                "job_id": job_id,
                                "workflow": job_workflow,
                                "filename": video_data.get("filename", Path(video_path).name),
                                "path": video_path,
                                "size_bytes": video_data.get("size_bytes", 0),
                                "size_mb": video_data.get("size_mb", 0),
                                "created_at": created_at,
                                "duration_seconds": duration_seconds,
                                "download_url": video_data.get("download_url", f"/api/download?path={Path(video_path).resolve()}"),
                                "thumbnail_url": None,  # Could be implemented later
                                "compilation_type": video_data.get("compilation_type", "Unknown"),
                                "compilation_num": video_data.get("compilation_num"),
                                "video_type": "compilation"
                            }
                            
                            if processed_count >= offset:
                                videos.append(video_info)
                            processed_count += 1
                            
                        except Exception as e:
                            logger.warning(f"Failed to process video {video_path}: {e}")
        
        # Sort videos
        sort_key = sort_by if sort_by in ["created_at", "size_mb", "filename"] else "created_at"
        reverse_sort = sort_order.lower() == "desc"
        
        videos.sort(key=lambda x: x.get(sort_key, ""), reverse=reverse_sort)
        
        # Apply pagination
        paginated_videos = videos[offset:offset + limit] if offset < len(videos) else []
        
        return {
            "videos": paginated_videos,
            "total": len(videos),
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < len(videos)
        }
        
    except Exception as e:
        logger.error(f"Failed to list all videos: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {e}")


@router.get("/videos/stats", summary="Get Video Statistics")
def get_video_stats() -> Dict[str, Any]:
    """Get statistics about all generated videos."""
    try:
        jobs = job_store.list_jobs(limit=1000, status="done")
        
        stats = {
            "total_videos": 0,
            "total_size_mb": 0,
            "workflows": {
                "moneyprinter": {"count": 0, "size_mb": 0},
                "brainrot": {"count": 0, "size_mb": 0}
            },
            "video_types": {
                "ai_generated": {"count": 0, "size_mb": 0},
                "compilation": {"count": 0, "size_mb": 0}
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
                for video_data in generated_videos:
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
