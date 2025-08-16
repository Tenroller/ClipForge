"""
Resume Manager for Video Generation Jobs

Handles saving and resuming interrupted video generation processes.
Manages intermediate state, files, and progress tracking.
"""

import os
import json
import uuid
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib

from database import get_job_store
from logging_config import get_logger

logger = get_logger("resume_manager")


@dataclass
class ResumeStep:
    """Represents a completed step with its outputs"""
    step_name: str
    completed_at: datetime
    outputs: Dict[str, Any]
    files_created: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.files_created is None:
            self.files_created = []


@dataclass
class ResumeState:
    """Complete resume state for a job"""
    job_id: str
    workflow: str
    last_completed_step: str
    request_data: Dict[str, Any]
    completed_steps: List[ResumeStep]
    created_at: datetime
    updated_at: datetime
    temp_files: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.temp_files is None:
            self.temp_files = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        # Convert datetime objects to ISO strings
        result['created_at'] = self.created_at.isoformat()
        result['updated_at'] = self.updated_at.isoformat()
        for step in result['completed_steps']:
            step['completed_at'] = step['completed_at'] if isinstance(step['completed_at'], str) else step['completed_at'].isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResumeState':
        """Create from dictionary"""
        # Convert ISO strings back to datetime objects
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        completed_steps = []
        for step_data in data['completed_steps']:
            step_data['completed_at'] = datetime.fromisoformat(step_data['completed_at']) if isinstance(step_data['completed_at'], str) else step_data['completed_at']
            completed_steps.append(ResumeStep(**step_data))
        
        data['completed_steps'] = completed_steps
        return cls(**data)


class ResumeManager:
    """Manages resume functionality for video generation jobs"""
    
    def __init__(self, resume_dir: Optional[Path] = None):
        self.resume_dir = resume_dir or Path("resume_states")
        self.resume_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.job_store = get_job_store()
        
        logger.info(f"Resume manager initialized with directory: {self.resume_dir}")
    
    def _get_resume_file(self, job_id: str) -> Path:
        """Get the resume state file path for a job"""
        return self.resume_dir / f"{job_id}.json"
    
    def save_step_completion(
        self, 
        job_id: str, 
        step_name: str, 
        outputs: Dict[str, Any],
        files_created: Optional[List[str]] = None
    ) -> None:
        """Save completion of a step"""
        with self.lock:
            # Get existing state or create new one
            state = self.get_resume_state(job_id)
            if not state:
                # Create initial state from job data
                job = self.job_store.get_job(job_id)
                if not job:
                    logger.error(f"Cannot save step for unknown job: {job_id}")
                    return
                
                state = ResumeState(
                    job_id=job_id,
                    workflow=job.get('workflow', 'unknown'),
                    last_completed_step=step_name,
                    request_data=job.get('request_data', {}),
                    completed_steps=[],
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
            
            # Add the completed step
            step = ResumeStep(
                step_name=step_name,
                completed_at=datetime.now(),
                outputs=outputs,
                files_created=files_created or []
            )
            
            # Remove any existing step with the same name (in case of retry)
            state.completed_steps = [s for s in state.completed_steps if s.step_name != step_name]
            state.completed_steps.append(step)
            
            state.last_completed_step = step_name
            state.updated_at = datetime.now()
            
            # Save to file
            self._save_state_to_file(state)
            
            logger.info(f"Saved step completion: {job_id} -> {step_name}")
    
    def get_resume_state(self, job_id: str) -> Optional[ResumeState]:
        """Get resume state for a job"""
        resume_file = self._get_resume_file(job_id)
        if not resume_file.exists():
            return None
        
        try:
            with open(resume_file, 'r') as f:
                data = json.load(f)
            return ResumeState.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load resume state for {job_id}: {e}")
            return None
    
    def _save_state_to_file(self, state: ResumeState) -> None:
        """Save state to file"""
        resume_file = self._get_resume_file(state.job_id)
        try:
            with open(resume_file, 'w') as f:
                json.dump(state.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save resume state for {state.job_id}: {e}")
    
    def can_resume_job(self, job_id: str) -> bool:
        """Check if a job can be resumed"""
        job = self.job_store.get_job(job_id)
        if not job:
            return False
        
        # Only allow resuming failed or cancelled jobs
        if job.get('status') not in ['error', 'cancelled', 'running']:
            return False
        
        state = self.get_resume_state(job_id)
        if not state or not state.completed_steps:
            return False
        
        # Check if the required files still exist
        return self._validate_resume_files(state)
    
    def _validate_resume_files(self, state: ResumeState) -> bool:
        """Validate that required files for resume still exist"""
        all_files = []
        for step in state.completed_steps:
            if step.files_created:
                all_files.extend(step.files_created)
        
        if state.temp_files:
            all_files.extend(state.temp_files)
        
        # Check if critical files exist
        for file_path in all_files:
            if not Path(file_path).exists():
                logger.warning(f"Resume file missing: {file_path}")
                return False
        
        return True
    
    def get_resumable_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs that can be resumed"""
        resumable = []
        
        # Scan resume directory for state files
        for resume_file in self.resume_dir.glob("*.json"):
            job_id = resume_file.stem
            
            if self.can_resume_job(job_id):
                state = self.get_resume_state(job_id)
                job = self.job_store.get_job(job_id)
                
                if state and job:
                    resumable.append({
                        'job_id': job_id,
                        'workflow': state.workflow,
                        'last_step': state.last_completed_step,
                        'completed_steps': len(state.completed_steps),
                        'created_at': state.created_at.isoformat(),
                        'updated_at': state.updated_at.isoformat(),
                        'status': job.get('status'),
                        'error': job.get('error')
                    })
        
        return sorted(resumable, key=lambda x: x['updated_at'], reverse=True)
    
    def get_next_step_to_execute(self, job_id: str) -> Optional[str]:
        """Get the next step that should be executed for resume"""
        state = self.get_resume_state(job_id)
        if not state:
            return None
        
        # Define step order for different workflows
        if state.workflow == 'moneyprinter':
            steps = [
                'validate_env',
                'fetch_music',  # Optional, only if useMusic and zipUrl
                'script_generation',
                'search_terms', 
                'stock_download',
                'tts',
                'subtitles',
                'compose_video'
            ]
        elif state.workflow == 'brainrot':
            steps = [
                'process_video',
                'generate_compilations'
            ]
        else:
            return None
        
        # Find next step after last completed
        completed_step_names = {step.step_name for step in state.completed_steps}
        
        for step in steps:
            if step not in completed_step_names:
                return step
        
        return None
    
    def get_step_outputs(self, job_id: str, step_name: str) -> Optional[Dict[str, Any]]:
        """Get outputs from a specific step"""
        state = self.get_resume_state(job_id)
        if not state:
            return None
        
        for step in state.completed_steps:
            if step.step_name == step_name:
                return step.outputs
        
        return None
    
    def cleanup_resume_state(self, job_id: str) -> None:
        """Clean up resume state for a completed job"""
        with self.lock:
            resume_file = self._get_resume_file(job_id)
            try:
                if resume_file.exists():
                    resume_file.unlink()
                    logger.info(f"Cleaned up resume state for job: {job_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup resume state for {job_id}: {e}")
    
    def cleanup_old_states(self, days: int = 7) -> int:
        """Clean up old resume states"""
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        cleaned = 0
        
        for resume_file in self.resume_dir.glob("*.json"):
            try:
                if resume_file.stat().st_mtime < cutoff:
                    resume_file.unlink()
                    cleaned += 1
            except Exception as e:
                logger.error(f"Failed to cleanup old resume state {resume_file}: {e}")
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old resume states")
        
        return cleaned
    
    def add_temp_file(self, job_id: str, file_path: str) -> None:
        """Track a temporary file for cleanup"""
        with self.lock:
            state = self.get_resume_state(job_id)
            if state:
                if not state.temp_files:
                    state.temp_files = []
                if file_path not in state.temp_files:
                    state.temp_files.append(file_path)
                    self._save_state_to_file(state)


# Global resume manager instance
_resume_manager: Optional[ResumeManager] = None


def get_resume_manager() -> ResumeManager:
    """Get or create the global resume manager instance"""
    global _resume_manager
    if _resume_manager is None:
        _resume_manager = ResumeManager()
    return _resume_manager


def save_step_completion(job_id: str, step_name: str, outputs: Dict[str, Any], files_created: Optional[List[str]] = None) -> None:
    """Convenience function to save step completion"""
    get_resume_manager().save_step_completion(job_id, step_name, outputs, files_created)


def can_resume_job(job_id: str) -> bool:
    """Convenience function to check if job can be resumed"""
    return get_resume_manager().can_resume_job(job_id)


def get_resume_state(job_id: str) -> Optional[ResumeState]:
    """Convenience function to get resume state"""
    return get_resume_manager().get_resume_state(job_id)


def cleanup_job_resume_state(job_id: str) -> None:
    """Convenience function to cleanup resume state"""
    get_resume_manager().cleanup_resume_state(job_id)
