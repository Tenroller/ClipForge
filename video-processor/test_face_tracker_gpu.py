"""
Test script to verify GPU detection in FaceTracker.
"""

import sys
import os

# Fix Windows console encoding issues
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from vendors.PodcastClips.face_tracker import FaceTracker
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_gpu_modes():
    """Test different GPU modes."""

    print("\n" + "="*60)
    print("Testing FaceTracker GPU Detection")
    print("="*60)

    # Test 1: Request GPU (will use GPU manager to decide)
    print("\n[Test 1] Initializing with use_gpu=True (prefer GPU)...")
    try:
        tracker_gpu = FaceTracker(use_gpu=True)
        print(f"✓ Initialized successfully")
        print(f"  - GPU requested: {tracker_gpu.use_gpu_requested}")
        print(f"  - GPU actual: {tracker_gpu.use_gpu_actual}")
        tracker_gpu.cleanup()
    except Exception as e:
        print(f"✗ Failed: {e}")

    # Test 2: Request CPU
    print("\n[Test 2] Initializing with use_gpu=False (CPU only)...")
    try:
        tracker_cpu = FaceTracker(use_gpu=False)
        print(f"✓ Initialized successfully")
        print(f"  - GPU requested: {tracker_cpu.use_gpu_requested}")
        print(f"  - GPU actual: {tracker_cpu.use_gpu_actual}")
        tracker_cpu.cleanup()
    except Exception as e:
        print(f"✗ Failed: {e}")

    # Test 3: Check GPU availability
    print("\n[Test 3] Checking GPU availability...")
    try:
        from vendors.PodcastClips.face_tracker import GPU_MANAGER_AVAILABLE
        print(f"  - GPU Manager available: {GPU_MANAGER_AVAILABLE}")

        if GPU_MANAGER_AVAILABLE:
            from utils.gpu_manager import get_gpu_stats, should_use_gpu

            stats = get_gpu_stats()
            print(f"  - GPU available: {stats.get('gpu_available', False)}")

            if stats.get('gpu_available'):
                devices = stats.get('devices', [])
                if devices:
                    device = devices[0]
                    print(f"  - GPU name: {device.get('name', 'Unknown')}")
                    print(f"  - Total memory: {device.get('total_memory_gb', 0):.2f} GB")
                    print(f"  - Free memory: {device.get('free_memory_gb', 0):.2f} GB")
                    print(f"  - Usage: {device.get('usage_percentage', 0):.1f}%")

            # Check if GPU should be used for face detection
            decision = should_use_gpu(estimated_memory_gb=1.5)
            print(f"\n  GPU decision for face detection (1.5GB estimate):")
            print(f"  - Use GPU: {decision.get('use_gpu', False)}")
            print(f"  - Reason: {decision.get('reason', 'Unknown')}")
            print(f"  - Confidence: {decision.get('confidence', 'Unknown')}")
    except Exception as e:
        print(f"✗ Failed: {e}")

    print("\n" + "="*60)
    print("Test completed")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_gpu_modes()
