#!/usr/bin/env python3
"""
Standalone Video Processor Testing Tool

This script allows you to test the video-processor service directly
without needing to start the frontend or backend services.

Usage:
    # Start the video processor first (in another terminal):
    python -m video-processor.main

    # Then run this script to submit test jobs:
    python test_processor.py moneyprinter "AI advancements in 2024"
    python test_processor.py brainrot "https://www.youtube.com/watch?v=VIDEO_ID"
    python test_processor.py podcastclips "https://www.youtube.com/watch?v=VIDEO_ID"

    # Or use interactive mode:
    python test_processor.py
"""

import sys
import time
import json
import uuid
import argparse
import requests
from typing import Dict, Any, Optional
from pathlib import Path


class VideoProcessorTester:
    """Test harness for the video processor service."""

    def __init__(self, base_url: str = "http://localhost:8090"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"

    def check_health(self) -> bool:
        """Check if the video processor is running."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Video processor is healthy (ID: {data.get('processor_id')})")
                print(f"   Queue size: {data.get('queue_size')}, Active jobs: {data.get('active_jobs')}")
                return True
            else:
                print(f"⚠️  Video processor returned status {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print(f"❌ Could not connect to video processor at {self.base_url}")
            print("   Make sure the service is running:")
            print(f"   cd video-processor && python main.py")
            return False
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False

    def get_processor_status(self) -> Optional[Dict[str, Any]]:
        """Get detailed processor status."""
        try:
            response = requests.get(f"{self.api_url}/status", timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Failed to get status: {e}")
            return None

    def submit_job(self, workflow: str, request_data: Dict[str, Any],
                   priority: str = "normal") -> Optional[str]:
        """Submit a job to the video processor."""
        job_id = str(uuid.uuid4())

        payload = {
            "job_id": job_id,
            "workflow": workflow,
            "priority": priority,
            "request_data": request_data,
            "callback_url": None  # No callback needed for testing
        }

        try:
            response = requests.post(
                f"{self.api_url}/jobs",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Job created successfully!")
                print(f"   Job ID: {job_id}")
                print(f"   Status: {result.get('status')}")
                return job_id
            else:
                print(f"❌ Failed to create job: {response.status_code}")
                print(f"   {response.text}")
                return None

        except Exception as e:
            print(f"❌ Failed to submit job: {e}")
            return None

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a job."""
        try:
            response = requests.get(f"{self.api_url}/jobs/{job_id}", timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Failed to get job status: {e}")
            return None

    def monitor_job(self, job_id: str, poll_interval: int = 3) -> bool:
        """Monitor a job until completion."""
        print(f"\n📊 Monitoring job {job_id}...")
        print("   Press Ctrl+C to stop monitoring\n")

        last_status = None
        last_step = None

        try:
            while True:
                status = self.get_job_status(job_id)

                if not status:
                    print("⚠️  Could not retrieve job status")
                    time.sleep(poll_interval)
                    continue

                current_status = status.get('status')
                current_step = status.get('current_step')
                progress = status.get('progress')

                # Print updates only when something changes
                if current_status != last_status or current_step != last_step:
                    timestamp = time.strftime("%H:%M:%S")
                    status_emoji = {
                        'queued': '⏳',
                        'running': '▶️',
                        'completed': '✅',
                        'failed': '❌',
                        'cancelled': '🚫'
                    }.get(current_status, '❓')

                    print(f"[{timestamp}] {status_emoji} Status: {current_status.upper()}", end='')
                    if current_step:
                        print(f" | Step: {current_step}", end='')
                    if progress:
                        print(f" | Progress: {progress}", end='')
                    print()

                    last_status = current_status
                    last_step = current_step

                # Check if job is finished
                if current_status in ['completed', 'failed', 'cancelled']:
                    print(f"\n{'='*60}")

                    if current_status == 'completed':
                        print("✅ JOB COMPLETED SUCCESSFULLY!")
                        result_data = status.get('result_data', {})

                        if result_data:
                            print("\n📁 Output files:")
                            if 'video_file' in result_data:
                                print(f"   Video: {result_data['video_file']}")
                            if 'audio_file' in result_data:
                                print(f"   Audio: {result_data['audio_file']}")
                            if 'output_files' in result_data:
                                for i, file in enumerate(result_data['output_files'], 1):
                                    print(f"   {i}. {file}")
                            if 'output_dir' in result_data:
                                print(f"   Directory: {result_data['output_dir']}")

                        duration = status.get('duration_seconds')
                        if duration:
                            print(f"\n⏱️  Duration: {duration}s ({duration // 60}m {duration % 60}s)")

                    elif current_status == 'failed':
                        print("❌ JOB FAILED")
                        error_msg = status.get('error_message')
                        if error_msg:
                            print(f"\n🔥 Error: {error_msg}")

                    elif current_status == 'cancelled':
                        print("🚫 JOB CANCELLED")

                    # Print logs if available
                    logs = status.get('logs', [])
                    if logs:
                        print(f"\n📝 Logs (last {len(logs)} entries):")
                        for log in logs[-10:]:
                            print(f"   {log}")

                    print(f"{'='*60}\n")
                    return current_status == 'completed'

                time.sleep(poll_interval)

        except KeyboardInterrupt:
            print("\n\n⏸️  Monitoring stopped (job is still running)")
            print(f"   Check status: curl {self.api_url}/jobs/{job_id}")
            return False

    def list_jobs(self, status: Optional[str] = None, limit: int = 10):
        """List recent jobs."""
        try:
            params = {"limit": limit}
            if status:
                params["status"] = status

            response = requests.get(f"{self.api_url}/jobs", params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                jobs = data.get('jobs', [])

                if not jobs:
                    print("No jobs found")
                    return

                print(f"\n📋 Recent jobs (showing {len(jobs)}):\n")
                for job in jobs:
                    status_emoji = {
                        'queued': '⏳',
                        'running': '▶️',
                        'completed': '✅',
                        'failed': '❌',
                        'cancelled': '🚫'
                    }.get(job['status'], '❓')

                    print(f"{status_emoji} {job['job_id'][:8]}... | {job['workflow']} | {job['status']}")
                    if job.get('current_step'):
                        print(f"   └─ {job['current_step']}")

                print()
            else:
                print(f"Failed to list jobs: {response.status_code}")
        except Exception as e:
            print(f"Failed to list jobs: {e}")


def create_moneyprinter_job(subject: str, **kwargs) -> Dict[str, Any]:
    """Create a MoneyPrinter job configuration."""
    return {
        "videoSubject": subject,
        "paragraphNumber": kwargs.get("paragraphs", 3),
        "voice": kwargs.get("voice", "af_bella"),
        "aiModel": kwargs.get("model", "gemini-2.0-flash"),
        "useMusic": kwargs.get("use_music", False),
        "zipUrl": kwargs.get("music_url"),
        "useTikTokSubtitles": kwargs.get("subtitles", True),
        "subtitleFont": kwargs.get("font", "Arial"),
        "customPrompt": kwargs.get("prompt")
    }


def create_brainrot_job(youtube_url: str, **kwargs) -> Dict[str, Any]:
    """Create a Brainrot job configuration."""
    return {
        "youtubeUrl": youtube_url,
        "numCompilations": kwargs.get("num_compilations", 1),
        "minDuration": kwargs.get("min_duration", 30),
        "maxDuration": kwargs.get("max_duration", 60),
        "maxReuse": kwargs.get("max_reuse", 3),
        "unlimited": kwargs.get("unlimited", False),
        "generateNoBackground": kwargs.get("no_background", True),
        "blurredPillarboxThreshold": kwargs.get("threshold", 0.1)
    }


def create_podcastclips_job(youtube_url: str, **kwargs) -> Dict[str, Any]:
    """Create a PodcastClips job configuration."""
    return {
        "youtubeUrl": youtube_url,
        "aiModel": kwargs.get("model", "gemini-2.5-pro"),
        "whisperModel": kwargs.get("whisper_model", "base"),
        "targetClipCount": kwargs.get("clip_count", 7),
        "minDuration": kwargs.get("min_duration", 20),
        "maxDuration": kwargs.get("max_duration", 70),
        "useGPU": kwargs.get("use_gpu", True),
        "subtitleFontSize": kwargs.get("font_size", 40),
        "subtitleColor": kwargs.get("text_color", "#FFFFFF"),
        "subtitleStrokeColor": kwargs.get("stroke_color", "#000000"),
        "subtitleStrokeWidth": kwargs.get("stroke_width", 2),
        "viralFocusKeywords": kwargs.get("viral_keywords", []),
        "Debug": kwargs.get("debug", True)
    }


def interactive_mode(tester: VideoProcessorTester):
    """Run in interactive mode."""
    print("\n" + "="*60)
    print("🎬 Video Processor Testing Tool - Interactive Mode")
    print("="*60)

    # Check health
    if not tester.check_health():
        print("\nPlease start the video processor first:")
        print("  cd video-processor")
        print("  python main.py")
        return

    print("\nAvailable workflows:")
    print("  1. MoneyPrinter - AI script generation + stock footage")
    print("  2. Brainrot - YouTube compilation videos")
    print("  3. PodcastClips - Extract viral moments from podcasts")
    print("  4. List recent jobs")
    print("  5. Check processor status")
    print("  0. Exit")

    while True:
        try:
            choice = input("\nSelect workflow (0-5): ").strip()

            if choice == "0":
                print("Goodbye! 👋")
                break

            elif choice == "1":
                subject = input("Enter video subject: ").strip()
                if subject:
                    request_data = create_moneyprinter_job(subject)
                    job_id = tester.submit_job("moneyprinter", request_data)
                    if job_id:
                        monitor = input("Monitor job progress? (y/n): ").strip().lower()
                        if monitor == 'y':
                            tester.monitor_job(job_id)

            elif choice == "2":
                url = input("Enter YouTube URL: ").strip()
                if url:
                    request_data = create_brainrot_job(url)
                    job_id = tester.submit_job("brainrot", request_data)
                    if job_id:
                        monitor = input("Monitor job progress? (y/n): ").strip().lower()
                        if monitor == 'y':
                            tester.monitor_job(job_id)

            elif choice == "3":
                url = input("Enter YouTube podcast URL: ").strip()
                if url:
                    request_data = create_podcastclips_job(url)
                    job_id = tester.submit_job("podcastclips", request_data)
                    if job_id:
                        monitor = input("Monitor job progress? (y/n): ").strip().lower()
                        if monitor == 'y':
                            tester.monitor_job(job_id)

            elif choice == "4":
                tester.list_jobs()

            elif choice == "5":
                status = tester.get_processor_status()
                if status:
                    print("\n📊 Processor Status:")
                    print(f"   ID: {status.get('processor_id')}")
                    print(f"   Status: {status.get('status')}")
                    print(f"   Active jobs: {status.get('current_jobs')}/{status.get('max_concurrent_jobs')}")
                    print(f"   Total processed: {status.get('total_processed')}")
                    print(f"   Uptime: {status.get('uptime_seconds')}s")
                    print(f"   Workflows: {', '.join(status.get('available_workflows', []))}")

            else:
                print("Invalid choice. Please select 0-5.")

        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test the video processor service directly",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python test_processor.py

  # MoneyPrinter workflow
  python test_processor.py moneyprinter "Amazing AI discoveries in 2024"

  # Brainrot workflow
  python test_processor.py brainrot "https://www.youtube.com/watch?v=VIDEO_ID"

  # PodcastClips workflow
  python test_processor.py podcastclips "https://www.youtube.com/watch?v=VIDEO_ID"

  # List recent jobs
  python test_processor.py list

  # Check processor status
  python test_processor.py status
        """
    )

    parser.add_argument(
        "workflow",
        nargs="?",
        choices=["moneyprinter", "brainrot", "podcastclips", "list", "status"],
        help="Workflow type or command"
    )

    parser.add_argument(
        "input",
        nargs="?",
        help="Input for the workflow (subject for moneyprinter, URL for brainrot/podcastclips)"
    )

    parser.add_argument(
        "--url",
        default="http://localhost:8090",
        help="Video processor base URL (default: http://localhost:8090)"
    )

    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="Don't monitor job progress after submission"
    )

    args = parser.parse_args()

    tester = VideoProcessorTester(base_url=args.url)

    # If no workflow specified, run interactive mode
    if not args.workflow:
        interactive_mode(tester)
        return

    # Check health first
    if not tester.check_health():
        print("\nPlease start the video processor first:")
        print("  cd video-processor")
        print("  python main.py")
        sys.exit(1)

    # Handle commands
    if args.workflow == "list":
        tester.list_jobs()
        return

    elif args.workflow == "status":
        status = tester.get_processor_status()
        if status:
            print(json.dumps(status, indent=2, default=str))
        return

    # Handle workflow submissions
    if not args.input:
        print(f"Error: Input required for {args.workflow} workflow")
        print(f"Usage: python test_processor.py {args.workflow} <input>")
        sys.exit(1)

    # Create job based on workflow
    if args.workflow == "moneyprinter":
        request_data = create_moneyprinter_job(args.input)
    elif args.workflow == "brainrot":
        request_data = create_brainrot_job(args.input)
    elif args.workflow == "podcastclips":
        request_data = create_podcastclips_job(args.input)
    else:
        print(f"Unknown workflow: {args.workflow}")
        sys.exit(1)

    # Submit job
    job_id = tester.submit_job(args.workflow, request_data)

    if job_id and not args.no_monitor:
        tester.monitor_job(job_id)


if __name__ == "__main__":
    main()
