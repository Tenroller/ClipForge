#!/usr/bin/env python3
"""
Test Script for No-Background Clip Creation
Tests the no-background clip creation process in isolation
"""

import os
import sys
import time
import psutil
import signal
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

def test_no_background_creation():
    """Test no-background clip creation with a sample clip"""
    
    print("🧪 Testing No-Background Clip Creation")
    print("="*50)
    
    # Look for existing clips to test with
    temp_dirs = [
        "temp_vertical",
        "output",
        "../backend/temp_vertical"
    ]
    
    test_clip = None
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.mov', '.avi')) and 'cropped' in file:
                    test_clip = os.path.join(temp_dir, file)
                    break
            if test_clip:
                break
    
    if not test_clip:
        print("❌ No test clips found. Please ensure you have processed clips available.")
        print("   Look for files in temp_vertical/ or output/ directories")
        return False
    
    print(f"✅ Found test clip: {test_clip}")
    print(f"   File size: {os.path.getsize(test_clip) / (1024*1024):.1f} MB")
    
    # Import the generator
    try:
        from vendors.Compilation.generator import TikYouGenerator
    except ImportError as e:
        print(f"❌ Error importing TikYouGenerator: {e}")
        return False
    
    # Create generator instance
    generator = TikYouGenerator()
    
    # Set up timeout handling
    def timeout_handler(signum, frame):
        print(f"\n⏰ Test timed out after 5 minutes")
        print(f"🛑 This suggests the no-background creation is hanging")
        raise TimeoutError("No-background creation test timed out")
    
    # Test the no-background creation
    print(f"\n🎬 Testing no-background creation...")
    print(f"   This should complete within 2-3 minutes for a typical clip")
    print(f"   If it takes longer than 5 minutes, there's likely a hang")
    
    start_time = time.time()
    
    # Set 5 minute timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(300)  # 5 minutes
    
    try:
        result = generator.create_no_background_clip(test_clip)
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result:
            print(f"✅ No-background clip created successfully!")
            print(f"   Output: {result}")
            print(f"   Duration: {duration:.1f} seconds")
            print(f"   Output size: {os.path.getsize(result) / (1024*1024):.1f} MB")
            
            # Test loading the result
            try:
                from moviepy.editor import VideoFileClip
                test_clip_obj = VideoFileClip(result)
                print(f"   ✅ Output clip is valid: {test_clip_obj.w}x{test_clip_obj.h}, {test_clip_obj.duration:.1f}s")
                test_clip_obj.close()
            except Exception as e:
                print(f"   ⚠️  Warning: Output clip validation failed: {e}")
                
            return True
        else:
            print(f"❌ No-background clip creation failed")
            print(f"   Duration before failure: {duration:.1f} seconds")
            return False
            
    except TimeoutError:
        print(f"❌ Test confirmed: no-background creation is hanging")
        print(f"\n🔧 Troubleshooting suggestions:")
        print(f"   1. Check system resources (RAM, disk space)")
        print(f"   2. Try with a smaller/shorter clip")
        print(f"   3. Check if GPU encoding is causing issues")
        print(f"   4. Review the updated create_no_background_clip method")
        return False
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"❌ Error during test: {e}")
        print(f"   Duration before error: {duration:.1f} seconds")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        signal.alarm(0)  # Cancel the alarm
        signal.signal(signal.SIGALRM, old_handler)

def monitor_system_during_test():
    """Monitor system resources during the test"""
    print(f"\n💻 System Status:")
    
    # Memory
    memory = psutil.virtual_memory()
    print(f"   Memory: {memory.percent:.1f}% used, {memory.available/1024/1024/1024:.1f} GB available")
    
    # Disk
    disk = psutil.disk_usage('.')
    print(f"   Disk: {disk.percent:.1f}% used, {disk.free/1024/1024/1024:.1f} GB free")
    
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"   CPU: {cpu_percent:.1f}% usage")

if __name__ == "__main__":
    print("🚀 Starting No-Background Creation Test")
    
    # Check system status first
    monitor_system_during_test()
    
    # Run the test
    success = test_no_background_creation()
    
    if success:
        print(f"\n✅ Test PASSED: No-background creation is working correctly")
        print(f"   The hang issue may be resolved with the recent fixes")
    else:
        print(f"\n❌ Test FAILED: No-background creation is still having issues")
        print(f"   Additional debugging may be needed")
    
    print(f"\n📝 Next Steps:")
    print(f"   1. If test passed: Try running your full compilation again")
    print(f"   2. If test failed: Use the monitor_compilation.py script during compilation")
    print(f"   3. Consider running with smaller batch sizes to isolate issues")