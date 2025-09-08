"""
Parallel processing utilities for optimized video processing.

This module provides intelligent parallel processing capabilities
for video generation tasks, including task distribution, load balancing,
and resource optimization.
"""

import os
import time
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass
from logging_config import get_logger

logger = get_logger("parallel_processor")


@dataclass
class TaskConfig:
    """Configuration for a parallel processing task."""
    name: str
    func: Callable
    args: tuple = ()
    kwargs: Dict[str, Any] = None
    priority: int = 1
    estimated_time: float = 1.0  # seconds
    memory_mb: int = 100  # MB
    cpu_cores: int = 1
    gpu_memory_mb: int = 0

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


class ParallelProcessor:
    """
    Intelligent parallel processor for video generation tasks.

    Features:
    - Automatic task distribution across CPU/GPU resources
    - Load balancing based on system resources
    - Memory and CPU usage monitoring
    - Priority-based task scheduling
    - Fallback to sequential processing when needed
    """

    def __init__(self, max_workers: Optional[int] = None, use_processes: bool = False):
        self.system_info = self._get_system_info()
        self.max_workers = max_workers or self._calculate_optimal_workers()
        self.use_processes = use_processes
        self.executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
        self.executor: Optional[Union[ThreadPoolExecutor, ProcessPoolExecutor]] = None
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_history: List[Dict[str, Any]] = []

        logger.info(f"Parallel processor initialized: {self.max_workers} workers, "
                   f"{'processes' if use_processes else 'threads'}")

    def _get_system_info(self) -> Dict[str, Any]:
        """Get system resource information."""
        cpu_count = psutil.cpu_count(logical=True)
        cpu_physical = psutil.cpu_count(logical=False)
        memory = psutil.virtual_memory()

        # GPU detection
        gpu_available = False
        gpu_memory_gb = 0

        try:
            import torch
            if torch.cuda.is_available():
                gpu_available = True
                gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        except ImportError:
            pass

        return {
            'cpu_count': cpu_count,
            'cpu_physical': cpu_physical,
            'memory_total_gb': memory.total / (1024**3),
            'memory_available_gb': memory.available / (1024**3),
            'gpu_available': gpu_available,
            'gpu_memory_gb': gpu_memory_gb
        }

    def _calculate_optimal_workers(self) -> int:
        """Calculate optimal number of workers based on system resources."""
        cpu_count = self.system_info['cpu_count']

        # For CPU-bound tasks, use physical cores
        if self.use_processes:
            optimal = max(1, self.system_info['cpu_physical'] - 1)  # Leave 1 core for system
        else:
            # For I/O bound tasks, can use more threads
            optimal = min(cpu_count * 2, 8)  # Cap at 8 for most systems

        # Consider memory constraints
        memory_per_worker = 200  # MB per worker
        max_by_memory = int(self.system_info['memory_available_gb'] * 1024 / memory_per_worker)
        optimal = min(optimal, max_by_memory, 4)  # Cap at 4 for conservative approach

        return max(1, optimal)

    def start(self):
        """Start the parallel processor."""
        if self.executor is None:
            self.executor = self.executor_class(max_workers=self.max_workers)
            logger.info(f"Started parallel processor with {self.max_workers} workers")

    def stop(self):
        """Stop the parallel processor."""
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None
            logger.info("Stopped parallel processor")

    def submit_task(self, task_config: TaskConfig) -> str:
        """
        Submit a task for parallel processing.

        Args:
            task_config: Task configuration

        Returns:
            Task ID for tracking
        """
        if self.executor is None:
            self.start()

        task_id = f"{task_config.name}_{int(time.time())}_{hash(str(task_config.args))}"

        # Check resource availability
        if not self._can_run_task(task_config):
            logger.warning(f"Cannot run task {task_config.name}: insufficient resources")
            return None

        # Submit task
        future = self.executor.submit(self._execute_task, task_config)

        # Track task
        self.active_tasks[task_id] = {
            'config': task_config,
            'future': future,
            'submitted_at': time.time(),
            'status': 'running'
        }

        logger.info(f"Submitted task {task_id} ({task_config.name})")
        return task_id

    def submit_batch(self, tasks: List[TaskConfig], max_concurrent: Optional[int] = None) -> List[str]:
        """
        Submit multiple tasks with resource management.

        Args:
            tasks: List of task configurations
            max_concurrent: Maximum concurrent tasks (default: auto-calculated)

        Returns:
            List of task IDs
        """
        if max_concurrent is None:
            max_concurrent = self._calculate_concurrent_capacity()

        # Sort tasks by priority (higher priority first)
        sorted_tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)

        task_ids = []
        active_count = 0

        for task in sorted_tasks:
            # Wait if we've reached the concurrent limit
            while active_count >= max_concurrent:
                time.sleep(0.1)  # Small delay
                self._cleanup_completed_tasks()
                active_count = len([t for t in self.active_tasks.values() if t['status'] == 'running'])

            task_id = self.submit_task(task)
            if task_id:
                task_ids.append(task_id)
                active_count += 1

        return task_ids

    def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Wait for a specific task to complete.

        Args:
            task_id: Task ID to wait for
            timeout: Maximum time to wait (seconds)

        Returns:
            Task result dictionary
        """
        if task_id not in self.active_tasks:
            return {'status': 'not_found', 'task_id': task_id}

        task_info = self.active_tasks[task_id]
        future = task_info['future']

        try:
            if timeout:
                result = future.result(timeout=timeout)
            else:
                result = future.result()

            task_info['status'] = 'completed'
            task_info['result'] = result
            task_info['completed_at'] = time.time()

            # Add to history
            self.task_history.append({
                'task_id': task_id,
                'config': task_info['config'],
                'result': result,
                'duration': task_info['completed_at'] - task_info['submitted_at'],
                'status': 'completed'
            })

            return {
                'status': 'completed',
                'task_id': task_id,
                'result': result,
                'duration': task_info['completed_at'] - task_info['submitted_at']
            }

        except Exception as e:
            task_info['status'] = 'failed'
            task_info['error'] = str(e)
            task_info['completed_at'] = time.time()

            # Add to history
            self.task_history.append({
                'task_id': task_id,
                'config': task_info['config'],
                'error': str(e),
                'duration': task_info['completed_at'] - task_info['submitted_at'],
                'status': 'failed'
            })

            logger.error(f"Task {task_id} failed: {e}")
            return {
                'status': 'failed',
                'task_id': task_id,
                'error': str(e),
                'duration': task_info['completed_at'] - task_info['submitted_at']
            }

    def wait_for_all(self, task_ids: List[str], timeout: Optional[float] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Wait for multiple tasks to complete.

        Args:
            task_ids: List of task IDs to wait for
            timeout: Maximum time to wait for all tasks

        Returns:
            Results dictionary with completed and failed tasks
        """
        start_time = time.time()
        results = {'completed': [], 'failed': [], 'pending': []}

        for task_id in task_ids:
            if timeout and (time.time() - start_time) > timeout:
                results['pending'].append(task_id)
                continue

            task_timeout = None
            if timeout:
                remaining_time = timeout - (time.time() - start_time)
                task_timeout = max(0.1, remaining_time / len(task_ids))

            result = self.wait_for_task(task_id, task_timeout)

            if result['status'] == 'completed':
                results['completed'].append(result)
            elif result['status'] == 'failed':
                results['failed'].append(result)
            else:
                results['pending'].append(task_id)

        return results

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a specific task."""
        if task_id not in self.active_tasks:
            return {'status': 'not_found', 'task_id': task_id}

        task_info = self.active_tasks[task_id]
        future = task_info['future']

        if future.done():
            try:
                result = future.result(timeout=0.1)
                task_info['status'] = 'completed'
                task_info['result'] = result
                return {
                    'status': 'completed',
                    'task_id': task_id,
                    'result': result,
                    'duration': time.time() - task_info['submitted_at']
                }
            except Exception as e:
                task_info['status'] = 'failed'
                task_info['error'] = str(e)
                return {
                    'status': 'failed',
                    'task_id': task_id,
                    'error': str(e),
                    'duration': time.time() - task_info['submitted_at']
                }
        else:
            return {
                'status': 'running',
                'task_id': task_id,
                'duration': time.time() - task_info['submitted_at']
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        self._cleanup_completed_tasks()

        active_count = len([t for t in self.active_tasks.values() if t['status'] == 'running'])
        completed_count = len([t for t in self.active_tasks.values() if t['status'] == 'completed'])
        failed_count = len([t for t in self.active_tasks.values() if t['status'] == 'failed'])

        # Calculate average task duration
        completed_tasks = [t for t in self.task_history if t['status'] == 'completed']
        avg_duration = 0
        if completed_tasks:
            avg_duration = sum(t['duration'] for t in completed_tasks) / len(completed_tasks)

        return {
            'system_info': self.system_info,
            'max_workers': self.max_workers,
            'active_tasks': active_count,
            'completed_tasks': completed_count,
            'failed_tasks': failed_count,
            'total_tasks_processed': len(self.task_history),
            'average_task_duration': avg_duration,
            'executor_type': 'process' if self.use_processes else 'thread'
        }

    def _can_run_task(self, task_config: TaskConfig) -> bool:
        """Check if system can handle the task."""
        # Check CPU cores
        if task_config.cpu_cores > self.system_info['cpu_count']:
            return False

        # Check memory
        required_memory_gb = task_config.memory_mb / 1024
        if required_memory_gb > self.system_info['memory_available_gb'] * 0.8:  # Leave 20% buffer
            return False

        # Check GPU memory if required
        if task_config.gpu_memory_mb > 0:
            if not self.system_info['gpu_available']:
                return False

            gpu_memory_mb = self.system_info['gpu_memory_gb'] * 1024
            if task_config.gpu_memory_mb > gpu_memory_mb * 0.8:  # Leave 20% buffer
                return False

        return True

    def _calculate_concurrent_capacity(self) -> int:
        """Calculate how many tasks can run concurrently."""
        # Base on available memory and CPU cores
        memory_based = int(self.system_info['memory_available_gb'] * 1024 / 200)  # 200MB per task
        cpu_based = self.system_info['cpu_count'] // 2  # Conservative CPU usage

        capacity = min(memory_based, cpu_based, self.max_workers)
        return max(1, capacity)

    def _execute_task(self, task_config: TaskConfig) -> Any:
        """Execute a task with proper error handling."""
        try:
            logger.debug(f"Executing task: {task_config.name}")
            start_time = time.time()

            result = task_config.func(*task_config.args, **task_config.kwargs)

            duration = time.time() - start_time
            logger.debug(f"Task {task_config.name} completed in {duration:.2f}s")

            return result

        except Exception as e:
            logger.error(f"Task {task_config.name} failed: {e}")
            raise

    def _cleanup_completed_tasks(self):
        """Clean up completed tasks from active tasks dict."""
        to_remove = []
        for task_id, task_info in self.active_tasks.items():
            if task_info['status'] in ['completed', 'failed']:
                to_remove.append(task_id)

        for task_id in to_remove:
            del self.active_tasks[task_id]


# Global instance
_parallel_processor: Optional[ParallelProcessor] = None


def get_parallel_processor() -> ParallelProcessor:
    """Get or create the global parallel processor instance."""
    global _parallel_processor
    if _parallel_processor is None:
        # Use threads by default for better compatibility
        _parallel_processor = ParallelProcessor(use_processes=False)
    return _parallel_processor


def init_parallel_processor():
    """Initialize the parallel processor."""
    processor = get_parallel_processor()
    processor.start()
    logger.info("Parallel processor initialized")


def create_video_task(name: str, func: Callable, *args, priority: int = 1,
                     estimated_memory_mb: int = 500, **kwargs) -> TaskConfig:
    """
    Create a video processing task configuration.

    Args:
        name: Task name
        func: Function to execute
        *args: Function arguments
        priority: Task priority (higher = more important)
        estimated_memory_mb: Estimated memory usage in MB
        **kwargs: Function keyword arguments

    Returns:
        TaskConfig for the video task
    """
    return TaskConfig(
        name=name,
        func=func,
        args=args,
        kwargs=kwargs,
        priority=priority,
        memory_mb=estimated_memory_mb,
        cpu_cores=1,
        gpu_memory_mb=1000 if kwargs.get('use_gpu', False) else 0  # 1GB GPU memory if GPU enabled
    )


# Initialize parallel processor when module is imported
try:
    init_parallel_processor()
except Exception as e:
    logger.error(f"Failed to initialize parallel processor: {e}")
