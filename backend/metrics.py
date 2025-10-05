"""
Prometheus metrics collection for the AI Video Generator.
"""

import time
import threading
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

try:
    from prometheus_client import Counter, Histogram, Gauge, Summary, Info, start_http_server, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    # Mock prometheus_client classes for when it's not available
    class MockMetric:
        def __init__(self, *args, **kwargs):
            pass
        def inc(self, *args, **kwargs):
            pass
        def observe(self, *args, **kwargs):
            pass
        def set(self, *args, **kwargs):
            pass
        def info(self, *args, **kwargs):
            pass
        def labels(self, *args, **kwargs):
            return self
    
    Counter = Histogram = Gauge = Summary = Info = MockMetric
    start_http_server = lambda *args, **kwargs: None
    generate_latest = lambda: b""
    CONTENT_TYPE_LATEST = "text/plain"
    PROMETHEUS_AVAILABLE = False

try:
    from .logging_config import get_logger
except ImportError:
    # Fallback for when running from backend directory
    from logging_config import get_logger

logger = get_logger("metrics")


class MetricsCollector:
    """Collect and expose Prometheus metrics for the video generator."""
    
    def __init__(self, enable_prometheus: bool = None):
        self.enabled = enable_prometheus if enable_prometheus is not None else PROMETHEUS_AVAILABLE
        self.metrics_server_port = int(os.getenv("METRICS_PORT", "9090"))
        self.metrics_server_started = False
        
        # In-memory metrics for fallback
        self.fallback_metrics = defaultdict(lambda: defaultdict(int))
        self.fallback_histograms = defaultdict(list)
        self.fallback_gauges = defaultdict(float)
        
        if self.enabled:
            self._init_prometheus_metrics()
            logger.info("✅ Prometheus metrics initialized")
        else:
            logger.warning("⚠️ Prometheus not available, using in-memory metrics")
    
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics."""
        # Request metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code']
        )
        
        self.http_request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
        )
        
        # Job metrics
        self.jobs_total = Counter(
            'video_generation_jobs_total',
            'Total video generation jobs',
            ['workflow', 'status']
        )
        
        self.job_duration = Histogram(
            'video_generation_duration_seconds',
            'Video generation job duration',
            ['workflow'],
            buckets=[10, 30, 60, 120, 300, 600, 1200, 1800, 3600]
        )
        
        self.active_jobs = Gauge(
            'video_generation_active_jobs',
            'Currently active video generation jobs',
            ['workflow']
        )
        
        self.job_queue_size = Gauge(
            'video_generation_queue_size',
            'Video generation job queue size',
            ['priority']
        )
        
        # System metrics
        self.system_info = Info(
            'video_generator_info',
            'Video generator system information'
        )
        
        self.memory_usage = Gauge(
            'video_generator_memory_bytes',
            'Memory usage in bytes',
            ['type']
        )
        
        self.disk_usage = Gauge(
            'video_generator_disk_bytes',
            'Disk usage in bytes',
            ['type']
        )
        
        # Cache metrics
        self.cache_operations = Counter(
            'cache_operations_total',
            'Total cache operations',
            ['operation', 'level', 'result']
        )
        
        self.cache_hit_ratio = Gauge(
            'cache_hit_ratio',
            'Cache hit ratio',
            ['level']
        )
        
        # API key usage metrics
        self.api_key_usage = Counter(
            'api_key_usage_total',
            'API key usage',
            ['key_id', 'endpoint']
        )
        
        # Rate limiting metrics
        self.rate_limit_hits = Counter(
            'rate_limit_hits_total',
            'Rate limit hits',
            ['endpoint', 'limit_type']
        )
        
        # Video processing metrics
        self.video_processing_steps = Counter(
            'video_processing_steps_total',
            'Video processing steps',
            ['workflow', 'step', 'status']
        )
        
        self.video_file_sizes = Histogram(
            'video_file_size_bytes',
            'Generated video file sizes',
            ['workflow'],
            buckets=[1e6, 5e6, 10e6, 25e6, 50e6, 100e6, 250e6, 500e6, 1e9]
        )
        
        self.tts_generation_time = Histogram(
            'tts_generation_duration_seconds',
            'Text-to-speech generation time',
            ['voice'],
            buckets=[1, 2, 5, 10, 20, 30, 60]
        )
        
        # Error metrics
        self.errors_total = Counter(
            'errors_total',
            'Total errors',
            ['type', 'component']
        )
        
        # Set system info
        self.system_info.info({
            'version': '1.0.0',
            'python_version': os.sys.version.split()[0],
            'prometheus_enabled': str(self.enabled)
        })
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics."""
        if self.enabled:
            self.http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            self.http_request_duration.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
        else:
            # Fallback to in-memory
            self.fallback_metrics['http_requests'][f"{method}_{endpoint}_{status_code}"] += 1
            self.fallback_histograms[f"http_duration_{method}_{endpoint}"].append(duration)
    
    def record_job_start(self, workflow: str):
        """Record job start."""
        if self.enabled:
            self.active_jobs.labels(workflow=workflow).inc()
        else:
            self.fallback_gauges[f"active_jobs_{workflow}"] += 1
    
    def record_job_completion(self, workflow: str, status: str, duration: float):
        """Record job completion."""
        if self.enabled:
            self.jobs_total.labels(workflow=workflow, status=status).inc()
            self.job_duration.labels(workflow=workflow).observe(duration)
            self.active_jobs.labels(workflow=workflow).dec()
        else:
            self.fallback_metrics['jobs'][f"{workflow}_{status}"] += 1
            self.fallback_histograms[f"job_duration_{workflow}"].append(duration)
            self.fallback_gauges[f"active_jobs_{workflow}"] -= 1
    
    def record_processing_step(self, workflow: str, step: str, status: str):
        """Record video processing step."""
        if self.enabled:
            self.video_processing_steps.labels(
                workflow=workflow,
                step=step,
                status=status
            ).inc()
        else:
            self.fallback_metrics['processing_steps'][f"{workflow}_{step}_{status}"] += 1
    
    def record_cache_operation(self, operation: str, level: str, result: str):
        """Record cache operation."""
        if self.enabled:
            self.cache_operations.labels(
                operation=operation,
                level=level,
                result=result
            ).inc()
        else:
            self.fallback_metrics['cache'][f"{operation}_{level}_{result}"] += 1
    
    def set_cache_hit_ratio(self, level: str, ratio: float):
        """Set cache hit ratio."""
        if self.enabled:
            self.cache_hit_ratio.labels(level=level).set(ratio)
        else:
            self.fallback_gauges[f"cache_hit_ratio_{level}"] = ratio
    
    def record_error(self, error_type: str, component: str):
        """Record error occurrence."""
        if self.enabled:
            self.errors_total.labels(type=error_type, component=component).inc()
        else:
            self.fallback_metrics['errors'][f"{error_type}_{component}"] += 1
    
    def record_file_size(self, workflow: str, size_bytes: int):
        """Record generated file size."""
        if self.enabled:
            self.video_file_sizes.labels(workflow=workflow).observe(size_bytes)
        else:
            self.fallback_histograms[f"file_size_{workflow}"].append(size_bytes)
    
    def record_tts_generation(self, voice: str, duration: float):
        """Record TTS generation time."""
        if self.enabled:
            self.tts_generation_time.labels(voice=voice).observe(duration)
        else:
            self.fallback_histograms[f"tts_duration_{voice}"].append(duration)
    
    def update_queue_size(self, priority: str, size: int):
        """Update job queue size."""
        if self.enabled:
            self.job_queue_size.labels(priority=priority).set(size)
        else:
            self.fallback_gauges[f"queue_size_{priority}"] = size
    
    def record_api_key_usage(self, key_id: str, endpoint: str):
        """Record API key usage."""
        if self.enabled:
            self.api_key_usage.labels(key_id=key_id, endpoint=endpoint).inc()
        else:
            self.fallback_metrics['api_usage'][f"{key_id}_{endpoint}"] += 1
    
    def record_rate_limit_hit(self, endpoint: str, limit_type: str):
        """Record rate limit hit."""
        if self.enabled:
            self.rate_limit_hits.labels(endpoint=endpoint, limit_type=limit_type).inc()
        else:
            self.fallback_metrics['rate_limits'][f"{endpoint}_{limit_type}"] += 1
    
    def update_memory_usage(self, memory_type: str, bytes_used: int):
        """Update memory usage metrics."""
        if self.enabled:
            self.memory_usage.labels(type=memory_type).set(bytes_used)
        else:
            self.fallback_gauges[f"memory_{memory_type}"] = bytes_used
    
    def update_disk_usage(self, disk_type: str, bytes_used: int):
        """Update disk usage metrics."""
        if self.enabled:
            self.disk_usage.labels(type=disk_type).set(bytes_used)
        else:
            self.fallback_gauges[f"disk_{disk_type}"] = bytes_used
    
    def start_metrics_server(self):
        """Start Prometheus metrics HTTP server."""
        if not self.enabled or self.metrics_server_started:
            return
        
        try:
            start_http_server(self.metrics_server_port)
            self.metrics_server_started = True
            logger.info(f"✅ Metrics server started on port {self.metrics_server_port}")
        except OSError as e:
            if "Address already in use" in str(e):
                logger.warning(f"⚠️ Metrics server port {self.metrics_server_port} already in use (likely due to uvicorn reload). Skipping metrics server startup.")
            else:
                logger.error(f"Failed to start metrics server: {e}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
    
    def get_metrics_text(self) -> str:
        """Get metrics in Prometheus text format."""
        if self.enabled:
            return generate_latest().decode('utf-8')
        else:
            # Return simple text format for fallback metrics
            lines = ["# Fallback metrics (Prometheus not available)"]
            
            for category, metrics in self.fallback_metrics.items():
                for name, value in metrics.items():
                    lines.append(f"{category}_{name} {value}")
            
            for name, value in self.fallback_gauges.items():
                lines.append(f"{name} {value}")
            
            return "\n".join(lines)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get metrics statistics."""
        stats = {
            "prometheus_enabled": self.enabled,
            "metrics_server_port": self.metrics_server_port,
            "metrics_server_started": self.metrics_server_started
        }
        
        if not self.enabled:
            stats["fallback_metrics"] = {
                "counters": dict(self.fallback_metrics),
                "gauges": dict(self.fallback_gauges),
                "histogram_counts": {k: len(v) for k, v in self.fallback_histograms.items()}
            }
        
        return stats


def timed_metric(metric_name: str, labels: Dict[str, str] = None):
    """Decorator to automatically time function execution and record metrics."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            error_occurred = False
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_occurred = True
                get_metrics().record_error(
                    error_type=type(e).__name__,
                    component=func.__name__
                )
                raise
            finally:
                duration = time.time() - start_time
                
                # You could record this as a custom histogram if needed
                # For now, just log timing info
                if error_occurred:
                    logger.error(f"Function {func.__name__} failed after {duration:.3f}s")
                else:
                    logger.debug(f"Function {func.__name__} completed in {duration:.3f}s")
        
        return wrapper
    return decorator


def track_job_metrics(workflow: str):
    """Decorator to track job execution metrics."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            metrics = get_metrics()
            start_time = time.time()
            
            metrics.record_job_start(workflow)
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                metrics.record_job_completion(workflow, "completed", duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                metrics.record_job_completion(workflow, "failed", duration)
                metrics.record_error(type(e).__name__, workflow)
                raise
        
        return wrapper
    return decorator


class SystemMonitor:
    """Monitor system resources and update metrics."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self, interval: int = 30):
        """Start system monitoring in background thread."""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        self.monitor_thread.start()
        logger.info(f"✅ System monitoring started (interval: {interval}s)")
    
    def stop_monitoring(self):
        """Stop system monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def _monitor_loop(self, interval: int):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                self._collect_system_metrics()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"System monitoring error: {e}")
                time.sleep(interval)
    
    def _collect_system_metrics(self):
        """Collect system metrics."""
        try:
            import psutil
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics.update_memory_usage("used", memory.used)
            self.metrics.update_memory_usage("available", memory.available)
            
            # Disk usage for output directory
            output_dir = os.getenv("VIDEOHELPER_OUTPUT_DIR", "./output")
            if os.path.exists(output_dir):
                disk = psutil.disk_usage(output_dir)
                self.metrics.update_disk_usage("used", disk.used)
                self.metrics.update_disk_usage("free", disk.free)
            
        except ImportError:
            # psutil not available, skip system metrics
            pass
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")


# Global metrics instance
_metrics: Optional[MetricsCollector] = None
_system_monitor: Optional[SystemMonitor] = None


def get_metrics() -> MetricsCollector:
    """Get or create the global metrics collector instance."""
    global _metrics
    if _metrics is None:
        enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() == "true"
        _metrics = MetricsCollector(enable_prometheus=enable_metrics)
    return _metrics


def get_system_monitor() -> SystemMonitor:
    """Get or create the global system monitor instance."""
    global _system_monitor
    if _system_monitor is None:
        _system_monitor = SystemMonitor(get_metrics())
    return _system_monitor


def init_metrics_system():
    """Initialize the complete metrics system."""
    metrics = get_metrics()
    monitor = get_system_monitor()
    
    # Start metrics server if Prometheus is enabled
    if metrics.enabled:
        metrics.start_metrics_server()
    
    # Start system monitoring
    monitor.start_monitoring()
    
    logger.info("✅ Metrics system initialized")


def record_request_metrics(method: str, path: str, status_code: int, duration: float):
    """Helper function to record HTTP request metrics."""
    # Sanitize endpoint path for metrics
    endpoint = path
    if endpoint.startswith("/api/"):
        endpoint = endpoint[4:]  # Remove /api/ prefix
    
    # Replace dynamic parts with placeholders
    import re
    endpoint = re.sub(r'/[0-9a-f-]{36}', '/{job_id}', endpoint)  # UUID patterns
    endpoint = re.sub(r'/\d+', '/{id}', endpoint)  # Numeric IDs
    
    get_metrics().record_http_request(method, endpoint, status_code, duration)
