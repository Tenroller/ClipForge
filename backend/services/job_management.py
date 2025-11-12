"""
Job management service layer.
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class JobManagementService:
    """Service for handling job management operations."""
    
    def __init__(self):
        from ..database import get_job_store
        from ..job_queue_unified import get_job_queue
        self.job_store = get_job_store()
        self.job_queue = get_job_queue()
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        return self.job_store.get_job(job_id)
    
    def list_jobs(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List jobs with optional filtering."""
        return self.job_store.list_jobs(limit=min(limit, 100), status=status)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        if not self.job_queue.cancel_job(job_id):
            return False
        self._update_job(job_id, status="cancelled")
        return True
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job from the database."""
        try:
            # First try to cancel if it's still running
            if self.job_queue.cancel_job(job_id):
                time.sleep(0.1)  # Brief pause to let cancellation complete
            
            # Delete from database
            return self.job_store.delete_job(job_id)
        except Exception as e:
            from ..logging_config import get_logger
            logger = get_logger("job_management")
            logger.error(f"Failed to delete job {job_id}: {e}")
            return False

    def purge_job(self, job_id: str, reason: str = "Purged by user") -> bool:
        """Purge a job and record a tombstone so subsequent GET returns 410."""
        try:
            return self.job_store.purge_job(job_id, reason)
        except Exception as e:
            from ..logging_config import get_logger
            logger = get_logger("job_management")
            logger.error(f"Failed to purge job {job_id}: {e}")
            return False
    
    def cleanup_jobs(self, older_than_days: int = 7, statuses: Optional[List[str]] = None) -> Dict[str, Any]:
        """Cleanup old jobs based on age and status."""
        if statuses is None:
            statuses = ["done", "error", "cancelled"]
        
        try:
            from datetime import datetime, timezone, timedelta
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            all_jobs = self.job_store.list_jobs(limit=1000)  # Get a large batch
            
            jobs_to_delete = []
            for job in all_jobs:
                if job.get('status') in statuses:
                    # Check if job is older than cutoff
                    job_date = job.get('created_at')
                    if job_date:
                        if isinstance(job_date, str):
                            try:
                                job_date = datetime.fromisoformat(job_date.replace('Z', '+00:00'))
                            except ValueError:
                                continue
                        elif isinstance(job_date, datetime):
                            if job_date.tzinfo is None:
                                job_date = job_date.replace(tzinfo=timezone.utc)
                        
                        if job_date < cutoff_date:
                            jobs_to_delete.append(job['id'])
            
            # Delete the jobs
            deleted_count = 0
            details = []
            for job_id in jobs_to_delete:
                if self.delete_job(job_id):
                    deleted_count += 1
                    details.append(f"Deleted job {job_id}")
                else:
                    details.append(f"Failed to delete job {job_id}")
            
            return {
                "cleaned_count": deleted_count,
                "total_candidates": len(jobs_to_delete),
                "details": details
            }
            
        except Exception as e:
            from ..utils.error_handling import handle_error
            error_info = handle_error(e, {'operation': 'cleanup_jobs'})
            return {
                "cleaned_count": 0,
                "total_candidates": 0,
                "details": [f"Error during cleanup: {error_info['error']['message']}"]
            }

    def get_resumable_jobs(self) -> Dict[str, Any]:
        """Get jobs that can be resumed (failed or cancelled jobs)."""
        try:
            from ..database import get_job_store
            job_store = get_job_store()
            
            # Get jobs that are in resumable states
            resumable_statuses = ['error', 'cancelled']
            all_resumable = []
            
            for status in resumable_statuses:
                jobs = job_store.list_jobs(limit=50, status=status)
                all_resumable.extend(jobs)
            
            # Filter jobs that have partial progress and can actually be resumed
            resumable_jobs = []
            for job in all_resumable:
                # Check if job has enough info to resume
                if (job.get('workflow') and 
                    job.get('request_data') and 
                    job.get('step')):  # Has made some progress
                    
                    # Add next step information
                    next_step = self._get_next_step_for_workflow(job['workflow'], job.get('step', ''))
                    job['next_step'] = next_step
                    # Ensure resume attempt is present for UI / decisions
                    if 'resume_attempt' not in job:
                        job['resume_attempt'] = 1
                    resumable_jobs.append(job)
            
            return {
                'resumable_jobs': resumable_jobs,
                'total_count': len(resumable_jobs)
            }
        except Exception as e:
            from ..utils.error_handling import handle_error
            error_info = handle_error(e, {'operation': 'get_resumable_jobs'})
            return {
                'error': error_info['error']['message'],
                'resumable_jobs': [],
                'total_count': 0
            }
    
    def _update_job(self, job_id: str, **fields: Any) -> None:
        """Update job in unified queue (which handles database persistence)."""
        # Handle special fields that need queue-specific processing
        if 'step' in fields:
            self.job_queue.update_job_progress(job_id, fields['step'])
            fields.pop('step')  # Remove from database update

        # Update database directly for remaining fields
        if fields:
            self.job_store.update_job(job_id, **fields)

        self._enqueue_job_update(job_id)
    
    def _enqueue_job_update(self, job_id: str) -> None:
        """No-op: WebSocket broadcasting has been removed, using REST API polling instead."""
        pass
    
    def _get_next_step_for_workflow(self, workflow: str, last_step: str) -> str:
        """Determine the next step for a workflow based on the last completed step."""
        if workflow == "moneyprinter":
            steps = ["validate_env", "fetch_music", "script_generation", "search_terms", "stock_download", "tts", "subtitles", "compose_video"]
            try:
                current_index = steps.index(last_step)
                if current_index < len(steps) - 1:
                    return steps[current_index + 1]
                return "completed"
            except ValueError:
                return steps[0]  # Start from beginning if step not found
        elif workflow == "brainrot":
            steps = ["process_video", "generate_compilations"]
            try:
                current_index = steps.index(last_step)
                if current_index < len(steps) - 1:
                    return steps[current_index + 1]
                return "completed"
            except ValueError:
                return steps[0]
        else:
            return "unknown"
