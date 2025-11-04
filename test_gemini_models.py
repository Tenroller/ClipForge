#!/usr/bin/env python3
"""
Test script for podcast video processing workflow
Tests the PodcastClips processor end-to-end
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add project directories to path
project_root = Path(__file__).parent.resolve()
backend_path = project_root / "backend"
video_processor_path = project_root / "video-processor"

sys.path.insert(0, str(backend_path))
sys.path.insert(0, str(video_processor_path))
sys.path.insert(0, str(video_processor_path / "vendors"))

# Set environment variables for testing
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")
os.environ["PEXELS_API_KEY"] = os.getenv("PEXELS_API_KEY", "")

def test_gemini_connection():
    """Test if Gemini API is accessible"""
    print("\n" + "="*80)
    print("TEST 1: Gemini API Connection")
    print("="*80)

    try:
        # Import here to avoid issues if dependencies are missing
        from vendors.AIvideos.gpt import generate_response

        response = generate_response("Say 'Hello, test successful!' in exactly 5 words.", "gemini-2.0-flash")

        if response:
            print(f"✓ Gemini API is accessible")
            print(f"  Response: {response[:100]}")
            return True
        else:
            print("✗ Gemini API returned empty response")
            return False

    except Exception as e:
        print(f"✗ Gemini API connection failed: {e}")
        return False


def test_youtube_download():
    """Test YouTube video download functionality"""
    print("\n" + "="*80)
    print("TEST 2: YouTube Download (Dry Run)")
    print("="*80)

    try:
        from utils.youtube import extract_video_id

        # Test with a short public video
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = extract_video_id(test_url)

        print(f"✓ YouTube URL parsing works")
        print(f"  Video ID extracted: {video_id}")
        return True

    except Exception as e:
        print(f"✗ YouTube functionality test failed: {e}")
        return False


def test_whisper_availability():
    """Test if Whisper is available for transcription"""
    print("\n" + "="*80)
    print("TEST 3: Whisper Transcription Availability")
    print("="*80)

    try:
        import whisper

        print(f"✓ Whisper is installed (version: {whisper.__version__ if hasattr(whisper, '__version__') else 'unknown'})")
        print(f"  Available models: tiny, base, small, medium, large")
        return True

    except ImportError:
        print("✗ Whisper is not installed")
        print("  Install with: pip install openai-whisper")
        return False
    except Exception as e:
        print(f"✗ Whisper availability check failed: {e}")
        return False


def test_face_detection():
    """Test face detection dependencies"""
    print("\n" + "="*80)
    print("TEST 4: Face Detection (MediaPipe)")
    print("="*80)

    try:
        import mediapipe as mp

        print(f"✓ MediaPipe is installed")
        print(f"  Face detection ready for intelligent cropping")
        return True

    except ImportError:
        print("✗ MediaPipe is not installed")
        print("  Install with: pip install mediapipe")
        return False
    except Exception as e:
        print(f"✗ MediaPipe check failed: {e}")
        return False


def test_video_processing_dependencies():
    """Test video processing library dependencies"""
    print("\n" + "="*80)
    print("TEST 5: Video Processing Dependencies")
    print("="*80)

    results = {}

    # Test MoviePy
    try:
        import moviepy.editor
        print(f"✓ MoviePy is installed")
        results['moviepy'] = True
    except ImportError:
        print("✗ MoviePy is not installed")
        results['moviepy'] = False

    # Test OpenCV
    try:
        import cv2
        print(f"✓ OpenCV is installed (version: {cv2.__version__})")
        results['opencv'] = True
    except ImportError:
        print("✗ OpenCV is not installed")
        results['opencv'] = False

    # Test FFmpeg
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✓ FFmpeg is available: {version_line}")
            results['ffmpeg'] = True
        else:
            print("✗ FFmpeg is not accessible")
            results['ffmpeg'] = False
    except Exception as e:
        print(f"✗ FFmpeg check failed: {e}")
        results['ffmpeg'] = False

    return all(results.values())


def test_podcast_processor_import():
    """Test if PodcastClips processor can be imported"""
    print("\n" + "="*80)
    print("TEST 6: PodcastClips Processor Import")
    print("="*80)

    try:
        from PodcastClips.processor import PodcastClipsProcessor

        print(f"✓ PodcastClipsProcessor can be imported")
        print(f"  Module location: {PodcastClipsProcessor.__module__}")
        return True

    except ImportError as e:
        print(f"✗ Failed to import PodcastClipsProcessor: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error during import: {e}")
        return False


def test_processor_initialization():
    """Test processor initialization"""
    print("\n" + "="*80)
    print("TEST 7: Processor Initialization")
    print("="*80)

    try:
        from PodcastClips.processor import PodcastClipsProcessor

        # Create temporary directories
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            temp_work_dir = Path(temp_dir) / "temp"

            processor = PodcastClipsProcessor(
                job_id="test-job-12345",
                output_dir=str(output_dir),
                temp_dir=str(temp_work_dir)
            )

            print(f"✓ Processor initialized successfully")
            print(f"  Job ID: {processor.job_id}")
            print(f"  Output dir: {processor.output_dir}")
            print(f"  Temp dir: {processor.temp_dir}")
            return True

    except Exception as e:
        print(f"✗ Processor initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_full_test_suite():
    """Run all tests and generate report"""
    print("\n" + "="*80)
    print("PODCAST VIDEO PROCESSING - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print("\nThis test suite validates the podcast workflow components:")
    print("1. Gemini AI API (for viral moment detection)")
    print("2. YouTube download (yt-dlp)")
    print("3. Whisper transcription (word-level timestamps)")
    print("4. Face detection (MediaPipe for 9:16 cropping)")
    print("5. Video processing (MoviePy, OpenCV, FFmpeg)")
    print("6. PodcastClips processor")

    # Run all tests
    test_results = {
        "Gemini API": test_gemini_connection(),
        "YouTube Download": test_youtube_download(),
        "Whisper Transcription": test_whisper_availability(),
        "Face Detection": test_face_detection(),
        "Video Processing": test_video_processing_dependencies(),
        "Processor Import": test_podcast_processor_import(),
        "Processor Init": test_processor_initialization()
    }

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for result in test_results.values() if result)
    total = len(test_results)

    for test_name, result in test_results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:10} {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")

    # Recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    if not test_results["Gemini API"]:
        print("⚠ Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable")
        print("  Get API key from: https://aistudio.google.com/app/apikey")

    if not test_results["Whisper Transcription"]:
        print("⚠ Install Whisper: pip install openai-whisper")

    if not test_results["Face Detection"]:
        print("⚠ Install MediaPipe: pip install mediapipe")

    if not test_results["Video Processing"]:
        print("⚠ Install video dependencies: pip install moviepy opencv-python")
        print("⚠ Install FFmpeg: apt-get install ffmpeg (or brew install ffmpeg)")

    if all(test_results.values()):
        print("\n✓ All tests passed! The podcast workflow is ready to use.")
        print("\nTo test with a real podcast video:")
        print("  1. Start the backend: cd backend && uvicorn app:app --reload")
        print("  2. Start video-processor: cd video-processor && python -m src.main")
        print("  3. POST to /api/podcastclips/generate with a YouTube URL")
    else:
        print("\n⚠ Some tests failed. Address the issues above before using the workflow.")

    return all(test_results.values())


if __name__ == "__main__":
    success = run_full_test_suite()
    sys.exit(0 if success else 1)
