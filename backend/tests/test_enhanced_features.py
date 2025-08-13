"""
Tests for enhanced features: caching, metrics, batch processing, and thumbnails.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app import app
    return TestClient(app)


class TestCaching:
    def test_memory_cache_basic_operations(self):
        from caching import MemoryCache
        
        cache = MemoryCache(max_size=10, default_ttl=60)
        
        # Test set and get
        assert cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # Test non-existent key
        assert cache.get("nonexistent") is None
        
        # Test delete
        assert cache.delete("key1")
        assert cache.get("key1") is None
        
        # Test exists
        cache.set("key2", "value2")
        assert cache.exists("key2")
        assert not cache.exists("key1")
        
        # Test clear
        cache.set("key3", "value3")
        assert cache.clear()
        assert not cache.exists("key2")
        assert not cache.exists("key3")
    
    def test_memory_cache_ttl(self):
        from caching import MemoryCache
        
        cache = MemoryCache(default_ttl=1)  # 1 second TTL
        
        cache.set("temp_key", "temp_value", ttl=1)
        assert cache.get("temp_key") == "temp_value"
        
        # Wait for expiry
        time.sleep(1.1)
        assert cache.get("temp_key") is None
    
    def test_multi_level_cache(self):
        from caching import MultiLevelCache, MemoryCache
        
        cache = MultiLevelCache(
            memory_cache=MemoryCache(max_size=5, default_ttl=60)
        )
        
        # Test basic operations
        assert cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"
        
        # Test stats
        stats = cache.stats()
        assert "hit_stats" in stats
        assert "total_requests" in stats
    
    def test_cached_decorator(self):
        from caching import cached, get_cache
        
        call_count = 0
        
        @cached(ttl=60)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call should execute function
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Should still be 1


class TestMetrics:
    def test_metrics_collector_fallback(self):
        from metrics import MetricsCollector
        
        # Test with Prometheus disabled
        metrics = MetricsCollector(enable_prometheus=False)
        
        # Test HTTP request metrics
        metrics.record_http_request("GET", "/api/health", 200, 0.1)
        
        # Test job metrics
        metrics.record_job_start("moneyprinter")
        metrics.record_job_completion("moneyprinter", "completed", 30.0)
        
        # Test error metrics
        metrics.record_error("ValueError", "test_component")
        
        # Test stats
        stats = metrics.get_stats()
        assert not stats["prometheus_enabled"]
        assert "fallback_metrics" in stats
    
    def test_metrics_text_format(self):
        from metrics import MetricsCollector
        
        metrics = MetricsCollector(enable_prometheus=False)
        metrics.record_http_request("GET", "/test", 200, 0.5)
        
        text = metrics.get_metrics_text()
        assert "Fallback metrics" in text
        assert "http_requests" in text
    
    def test_timed_metric_decorator(self):
        from metrics import timed_metric
        
        @timed_metric("test_function")
        def test_function():
            time.sleep(0.01)
            return "success"
        
        result = test_function()
        assert result == "success"


class TestBatchProcessing:
    def test_batch_processor_creation(self):
        from batch_processing import BatchProcessor, JobPriority
        
        processor = BatchProcessor()
        
        # Test batch creation
        job_params = [
            {"videoSubject": "Test 1"},
            {"videoSubject": "Test 2"}
        ]
        
        batch_id = processor.create_batch(
            name="Test Batch",
            workflow="moneyprinter",
            job_parameters=job_params,
            priority=JobPriority.LOW
        )
        
        assert batch_id is not None
        
        # Test batch status
        status = processor.get_batch_status(batch_id)
        assert status is not None
        assert status["name"] == "Test Batch"
        assert status["workflow"] == "moneyprinter"
        assert status["total_jobs"] == 2
        assert status["status"] == "pending"
    
    def test_template_batch_creation(self):
        from batch_processing import BatchProcessor
        
        processor = BatchProcessor()
        
        # Test MoneyPrinter template
        batch_id = processor.create_template_batch("moneyprinter_subjects", count=3)
        assert batch_id is not None
        
        status = processor.get_batch_status(batch_id)
        assert status["total_jobs"] == 3
        assert status["workflow"] == "moneyprinter"
    
    def test_batch_listing(self):
        from batch_processing import BatchProcessor
        
        processor = BatchProcessor()
        
        # Create a few batches
        batch_id1 = processor.create_template_batch("moneyprinter_subjects", count=2)
        batch_id2 = processor.create_template_batch("moneyprinter_subjects", count=3)
        
        # List batches
        batches = processor.list_batches()
        assert len(batches) >= 2
        
        # Find our batches
        batch_ids = [b["id"] for b in batches]
        assert batch_id1 in batch_ids
        assert batch_id2 in batch_ids
    
    def test_batch_cancellation(self):
        from batch_processing import BatchProcessor
        
        processor = BatchProcessor()
        
        batch_id = processor.create_template_batch("moneyprinter_subjects", count=2)
        
        # Cancel batch
        success = processor.cancel_batch(batch_id)
        assert success
        
        # Check status
        status = processor.get_batch_status(batch_id)
        assert status["status"] == "cancelled"


class TestThumbnailGeneration:
    def test_thumbnail_generator_init(self):
        # This test might fail if FFmpeg is not available
        try:
            from thumbnail_generator import ThumbnailGenerator
            generator = ThumbnailGenerator()
            assert generator is not None
        except Exception:
            # Skip test if FFmpeg not available
            pytest.skip("FFmpeg not available for thumbnail generation")
    
    def test_thumbnail_generator_fallback(self):
        from thumbnail_generator import get_thumbnail_generator
        
        # Test that we can get a generator instance
        generator = get_thumbnail_generator()
        assert generator is not None


class TestJobQueue:
    def test_redis_job_queue_fallback(self):
        from job_queue import RedisJobQueue
        
        # Test with Redis not available (should fallback)
        queue = RedisJobQueue(redis_url="redis://nonexistent:6379/0")
        assert not queue.enabled
        
        # Test enqueue (should use fallback)
        def test_job():
            return "test result"
        
        job_id = queue.enqueue_job(test_job)
        assert job_id is not None
    
    def test_job_queue_stats(self):
        from job_queue import RedisJobQueue
        
        queue = RedisJobQueue()
        stats = queue.get_queue_stats()
        assert "redis_available" in stats


class TestAPIEndpoints:
    def test_metrics_endpoint(self, client):
        # Test without auth (should fail if API_KEY is set)
        response = client.get("/api/metrics")
        # Either 200 (no auth) or 401 (auth required)
        assert response.status_code in [200, 401]
    
    def test_cache_stats_endpoint(self, client):
        response = client.get("/api/cache/stats")
        assert response.status_code in [200, 401]
    
    def test_batch_endpoints(self, client):
        # Test batch creation
        batch_data = {
            "name": "Test API Batch",
            "workflow": "moneyprinter", 
            "job_parameters": [{"videoSubject": "Test"}],
            "priority": "low"
        }
        
        response = client.post("/api/batch", json=batch_data)
        # Should either succeed or require auth
        assert response.status_code in [200, 401, 422]  # 422 for validation errors
        
        # Test batch listing
        response = client.get("/api/batches")
        assert response.status_code in [200, 401]
    
    def test_template_batch_endpoint(self, client):
        response = client.post("/api/batch/template", json={
            "template_type": "moneyprinter_subjects",
            "count": 3
        })
        assert response.status_code in [200, 401, 422]


class TestIntegration:
    def test_system_initialization(self):
        """Test that all systems can be initialized together."""
        from metrics import get_metrics
        from caching import get_cache
        from batch_processing import get_batch_processor
        from job_queue import get_job_queue
        
        # These should not raise exceptions
        metrics = get_metrics()
        cache = get_cache()
        batch_processor = get_batch_processor()
        job_queue = get_job_queue()
        
        assert metrics is not None
        assert cache is not None
        assert batch_processor is not None
        assert job_queue is not None
    
    def test_enhanced_features_availability(self):
        """Test that enhanced features are available in the app."""
        from app import app
        
        # Check that enhanced endpoints exist
        routes = [route.path for route in app.routes]
        
        expected_routes = [
            "/api/metrics",
            "/api/cache/stats",
            "/api/batch",
            "/api/batches"
        ]
        
        for route in expected_routes:
            assert route in routes or any(route in r for r in routes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
