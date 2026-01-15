#!/usr/bin/env python3
"""
Face Detection Testing Framework - Batch Test Runner

Runs face tracking debug analysis on all test videos in the videos/ folder.
Generates debug visualization videos and JSON metrics for each.

Usage:
    python run_all_tests.py
    python run_all_tests.py --video single_speaker.mp4  # Run single test
"""

import argparse
import cv2
import json
import os
import sys
import time
import tempfile
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add parent paths for imports
current_dir = Path(__file__).parent
podcast_clips_dir = current_dir.parent
video_processor_dir = podcast_clips_dir.parent.parent
backend_dir = video_processor_dir.parent / 'backend'
project_root = video_processor_dir.parent

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Add paths for imports
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(video_processor_dir))
sys.path.insert(0, str(podcast_clips_dir))

# Create package structure for imports
import types
vendors_package = types.ModuleType('vendors')
vendors_package.__path__ = [str(podcast_clips_dir.parent)]
sys.modules['vendors'] = vendors_package

podcast_clips_package = types.ModuleType('vendors.PodcastClips')
podcast_clips_package.__path__ = [str(podcast_clips_dir)]
podcast_clips_package.__package__ = 'vendors.PodcastClips'
sys.modules['vendors.PodcastClips'] = podcast_clips_package

from loguru import logger
import numpy as np
from tqdm import tqdm

# Import face tracking modules
try:
    from vendors.PodcastClips.face_tracker import FaceTracker, FaceBox, CropBox
    from vendors.PodcastClips.content_detector import ContentModeDetector, ContentMode, ContentSegment
    logger.info("Successfully loaded face tracking modules")
except Exception as e:
    logger.error(f"Failed to import modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# Expected modes based on video filename patterns
# More specific patterns should come first
EXPECTED_MODES = {
    'front_speakers': ContentMode.SPLIT_SCREEN,  # 2 speakers in front + audience
    'interview': ContentMode.SPLIT_SCREEN,
    '2_people': ContentMode.SPLIT_SCREEN,
    'split': ContentMode.SPLIT_SCREEN,
    'single': ContentMode.FACE,
    'speaker': ContentMode.FACE,
    'face': ContentMode.FACE,
    'audience': ContentMode.HORIZONTAL,
    'wide': ContentMode.HORIZONTAL,
    'content': ContentMode.HORIZONTAL,
    'screen': ContentMode.HORIZONTAL,
}


@dataclass
class FaceMetrics:
    """Metrics for a single face track."""
    face_id: int
    avg_size_ratio: float = 0.0
    min_size_ratio: float = 0.0
    max_size_ratio: float = 0.0
    confidence_avg: float = 0.0
    confidence_min: float = 0.0
    speech_correlation: float = 0.0
    detection_count: int = 0
    position_variance_x: float = 0.0
    position_variance_y: float = 0.0


@dataclass
class VideoTestResult:
    """Results from testing a single video."""
    video_name: str
    video_path: str
    duration: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    total_frames: int = 0
    
    # Expected vs actual
    expected_mode: Optional[str] = None
    detected_mode: str = "UNKNOWN"
    mode_match: bool = False
    
    # Face detection metrics
    face_track_count: int = 0
    frames_with_faces: int = 0
    frame_coverage_pct: float = 0.0
    avg_simultaneous_faces: float = 0.0
    max_simultaneous_faces: int = 0
    
    # Per-face metrics
    face_metrics: List[Dict] = field(default_factory=list)
    
    # Content mode segments
    mode_segments: List[Dict] = field(default_factory=list)
    
    # Issues detected
    issues: List[str] = field(default_factory=list)
    
    # Timing
    processing_time_seconds: float = 0.0
    
    # Output paths
    debug_video_path: Optional[str] = None
    json_data_path: Optional[str] = None


def get_expected_mode(video_name: str) -> Optional[ContentMode]:
    """Determine expected mode from video filename."""
    name_lower = video_name.lower()
    for pattern, mode in EXPECTED_MODES.items():
        if pattern in name_lower:
            return mode
    return None


def extract_audio(video_path: str, output_path: Optional[str] = None) -> str:
    """Extract audio from video using ffmpeg."""
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.wav')
    
    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '16000', '-ac', '1',
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    except subprocess.CalledProcessError as e:
        logger.warning(f"Audio extraction failed: {e}")
        return None


def draw_dashed_rectangle(frame, pt1, pt2, color, thickness=2, dash_length=10):
    """Draw a dashed rectangle on the frame."""
    x1, y1 = pt1
    x2, y2 = pt2
    
    for i in range(x1, x2, dash_length * 2):
        end = min(i + dash_length, x2)
        cv2.line(frame, (i, y1), (end, y1), color, thickness)
        cv2.line(frame, (i, y2), (end, y2), color, thickness)
    
    for i in range(y1, y2, dash_length * 2):
        end = min(i + dash_length, y2)
        cv2.line(frame, (x1, i), (x1, end), color, thickness)
        cv2.line(frame, (x2, i), (x2, end), color, thickness)


def run_test(video_path: str, output_dir: str, sample_rate: int = 2) -> VideoTestResult:
    """
    Run face detection test on a single video.
    
    Returns VideoTestResult with all metrics.
    """
    video_name = os.path.basename(video_path)
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {video_name}")
    logger.info(f"{'='*60}")
    
    start_time = time.time()
    
    result = VideoTestResult(
        video_name=video_name,
        video_path=video_path,
        expected_mode=get_expected_mode(video_name).value if get_expected_mode(video_name) else None
    )
    
    # Initialize face tracker
    face_tracker = FaceTracker(
        detection_height=0,  # Adaptive
        batch_size=4,
        min_face_size_ratio=0.002,
        max_tracked_faces=6,
        enable_speaker_detection=True,
        enable_lip_detection=False
    )
    
    # Get video properties
    cap = cv2.VideoCapture(video_path)
    result.fps = cap.get(cv2.CAP_PROP_FPS)
    result.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    result.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    result.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    result.duration = result.total_frames / result.fps if result.fps > 0 else 0
    cap.release()
    
    logger.info(f"Video: {result.width}x{result.height} @ {result.fps:.1f}fps, {result.duration:.1f}s")
    
    # Analyze video for faces
    logger.info("Step 1/4: Analyzing faces...")
    face_positions = face_tracker.analyze_video(video_path, sample_rate=sample_rate)
    
    result.face_track_count = len(face_tracker.face_tracks)
    logger.info(f"Detected {len(face_positions)} face positions, {result.face_track_count} tracks")
    
    # Extract and analyze audio
    logger.info("Step 2/4: Analyzing audio...")
    audio_path = extract_audio(video_path)
    if audio_path:
        try:
            face_tracker.analyze_audio_for_speech(audio_path)
            face_tracker.correlate_faces_with_speech()
        except Exception as e:
            logger.warning(f"Audio analysis failed: {e}")
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)
    
    # Collect face metrics
    for track in face_tracker.face_tracks:
        positions = list(track.positions.values())
        if not positions:
            continue
        
        sizes = [f.width * f.height / (result.width * result.height) for f in positions]
        confidences = [f.confidence for f in positions]
        x_positions = [f.center[0] / result.width for f in positions]
        y_positions = [f.center[1] / result.height for f in positions]
        
        metrics = FaceMetrics(
            face_id=track.face_id,
            avg_size_ratio=np.mean(sizes) if sizes else 0,
            min_size_ratio=np.min(sizes) if sizes else 0,
            max_size_ratio=np.max(sizes) if sizes else 0,
            confidence_avg=np.mean(confidences) if confidences else 0,
            confidence_min=np.min(confidences) if confidences else 0,
            speech_correlation=track.speech_correlation,
            detection_count=len(positions),
            position_variance_x=np.var(x_positions) if len(x_positions) > 1 else 0,
            position_variance_y=np.var(y_positions) if len(y_positions) > 1 else 0
        )
        result.face_metrics.append(asdict(metrics))
    
    # Content mode detection
    logger.info("Step 3/4: Detecting content modes...")
    content_detector = ContentModeDetector(
        face_loss_threshold=1.0,
        min_segment_duration=0.5,
        use_ocr=False,
        face_tracker=face_tracker
    )
    
    content_segments = content_detector.analyze_video_segments(
        video_path=video_path,
        face_positions=face_positions,
        fps=result.fps,
        start_time=0.0,
        end_time=result.duration
    )
    
    # Determine dominant mode
    mode_durations = {}
    for seg in content_segments:
        mode = seg.mode.value
        mode_durations[mode] = mode_durations.get(mode, 0) + seg.duration()
        result.mode_segments.append({
            'start': seg.start_time,
            'end': seg.end_time,
            'mode': mode,
            'confidence': seg.confidence
        })
    
    if mode_durations:
        result.detected_mode = max(mode_durations, key=mode_durations.get)
    
    result.mode_match = (result.expected_mode == result.detected_mode) if result.expected_mode else True
    
    logger.info(f"Mode segments: {len(content_segments)}")
    for seg in content_segments:
        logger.info(f"  {seg.start_time:.2f}s - {seg.end_time:.2f}s: {seg.mode.value}")
    
    # Calculate frame coverage
    frames_with_faces = set()
    simultaneous_counts = []
    
    for ts, face in face_positions.items():
        frame_idx = int(ts * result.fps)
        frames_with_faces.add(frame_idx)
    
    # Count simultaneous faces per timestamp
    timestamps = sorted(set(face_positions.keys()))
    for ts in timestamps:
        count = sum(1 for track in face_tracker.face_tracks 
                   if any(abs(t - ts) < 0.5 for t in track.positions.keys()))
        simultaneous_counts.append(count)
    
    result.frames_with_faces = len(frames_with_faces)
    result.frame_coverage_pct = (result.frames_with_faces / result.total_frames * 100) if result.total_frames > 0 else 0
    result.avg_simultaneous_faces = np.mean(simultaneous_counts) if simultaneous_counts else 0
    result.max_simultaneous_faces = max(simultaneous_counts) if simultaneous_counts else 0
    
    # Detect issues
    if result.frame_coverage_pct < 30:
        result.issues.append(f"LOW_COVERAGE: Only {result.frame_coverage_pct:.1f}% frames have faces")
    
    if result.face_track_count < 2 and result.expected_mode == 'split_screen':
        result.issues.append(f"INSUFFICIENT_FACES: Need 2+ faces for split screen, found {result.face_track_count}")
    
    for fm in result.face_metrics:
        if fm['avg_size_ratio'] < 0.002:
            result.issues.append(f"SMALL_FACE: Face {fm['face_id']} avg size {fm['avg_size_ratio']*100:.3f}% (< 0.2%)")
        if fm['confidence_avg'] < 0.5:
            result.issues.append(f"LOW_CONFIDENCE: Face {fm['face_id']} avg confidence {fm['confidence_avg']:.2f}")
    
    # Generate debug visualization video
    logger.info("Step 4/4: Generating debug video...")
    output_video = os.path.join(output_dir, f"{Path(video_name).stem}_debug.mp4")
    output_json = os.path.join(output_dir, f"{Path(video_name).stem}_data.json")
    
    _generate_debug_video(
        video_path=video_path,
        output_path=output_video,
        face_tracker=face_tracker,
        face_positions=face_positions,
        content_segments=content_segments,
        result=result
    )
    
    result.debug_video_path = output_video
    result.json_data_path = output_json
    result.processing_time_seconds = time.time() - start_time
    
    # Save JSON data
    with open(output_json, 'w') as f:
        json.dump(asdict(result), f, indent=2)
    
    logger.info(f"Completed in {result.processing_time_seconds:.1f}s")
    logger.info(f"Expected: {result.expected_mode}, Detected: {result.detected_mode} {'✓' if result.mode_match else '✗'}")
    
    face_tracker.cleanup()
    return result


def _generate_debug_video(
    video_path: str,
    output_path: str,
    face_tracker: 'FaceTracker',
    face_positions: Dict[float, 'FaceBox'],
    content_segments: List['ContentSegment'],
    result: VideoTestResult
):
    """Generate debug visualization video with all overlays."""
    cap = cv2.VideoCapture(video_path)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, result.fps, (result.width, result.height))
    
    # Build mode lookup
    def get_mode_at_time(ts: float) -> ContentMode:
        for seg in content_segments:
            if seg.start_time <= ts < seg.end_time:
                return seg.mode
        return ContentMode.FACE
    
    FACE_PERSISTENCE_WINDOW = 2.0
    
    for frame_idx in tqdm(range(result.total_frames), desc="Rendering debug"):
        ret, frame = cap.read()
        if not ret:
            break
        
        timestamp = frame_idx / result.fps
        current_mode = get_mode_at_time(timestamp)
        
        # Get active faces at this timestamp
        active_faces = []
        for track in face_tracker.face_tracks:
            nearby = [ts for ts in track.positions.keys() if abs(ts - timestamp) < FACE_PERSISTENCE_WINDOW]
            if nearby:
                closest = min(nearby, key=lambda t: abs(t - timestamp))
                face = track.positions[closest]
                active_faces.append({'face': face, 'track': track, 'interpolated': abs(closest - timestamp) > 0.2})
        
        # Get active speaker
        active_speaker = face_tracker.get_active_speaker_at_time(timestamp)
        
        # Draw mode indicator at top
        mode_colors = {
            ContentMode.FACE: (255, 150, 0),       # Blue
            ContentMode.HORIZONTAL: (0, 165, 255),  # Orange
            ContentMode.SPLIT_SCREEN: (255, 0, 255) # Magenta
        }
        mode_color = mode_colors.get(current_mode, (255, 255, 255))
        cv2.rectangle(frame, (0, 0), (result.width, 50), (0, 0, 0), -1)
        cv2.putText(frame, f"MODE: {current_mode.value.upper()}", (10, 35),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, mode_color, 2)
        
        # Draw expected mode
        if result.expected_mode:
            match_text = "MATCH" if result.detected_mode == result.expected_mode else "MISMATCH"
            match_color = (0, 255, 0) if result.detected_mode == result.expected_mode else (0, 0, 255)
            cv2.putText(frame, f"Expected: {result.expected_mode} [{match_text}]", 
                       (result.width - 400, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, match_color, 2)
        
        # Draw faces
        for face_data in active_faces:
            face = face_data['face']
            track = face_data['track']
            is_active = active_speaker and face.face_id == active_speaker.face_id
            
            # Color: green for active, red for others
            color = (0, 255, 0) if is_active else (0, 0, 255)
            thickness = 4 if is_active else 2
            
            # Draw bounding box
            cv2.rectangle(frame, (face.x, face.y), 
                         (face.x + face.width, face.y + face.height), color, thickness)
            
            # Calculate face size ratio
            size_ratio = (face.width * face.height) / (result.width * result.height) * 100
            
            # Draw label
            label = f"ID:{face.face_id} Conf:{face.confidence:.2f} Size:{size_ratio:.2f}%"
            label_y = face.y - 10 if face.y > 30 else face.y + face.height + 20
            
            cv2.rectangle(frame, (face.x, label_y - 18), 
                         (face.x + len(label) * 9, label_y + 4), color, -1)
            cv2.putText(frame, label, (face.x + 3, label_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        
        # Draw crop region based on mode
        if current_mode == ContentMode.FACE:
            crop_box = face_tracker.get_dynamic_crop_box_at_time(timestamp)
            if crop_box:
                draw_dashed_rectangle(frame, (crop_box.x, crop_box.y),
                                     (crop_box.x + crop_box.width, crop_box.y + crop_box.height),
                                     (255, 150, 0), 3, 15)
        
        elif current_mode == ContentMode.SPLIT_SCREEN:
            # Get the 2 separated faces for split-screen layout
            separated_faces = face_tracker.get_separated_faces_at_time(timestamp)
            if separated_faces and len(separated_faces) >= 2:
                # Calculate crop boxes matching clip_generator._create_face_crop_clip logic
                # Target: each panel is 1080x960 (half of 1080x1920)
                target_panel_width = 1080
                target_panel_height = 960  # Half of 1920
                target_aspect = target_panel_width / target_panel_height  # 1.125
                
                for i, face in enumerate(separated_faces[:2]):
                    # Match _create_face_crop_clip: 1.8x padding around face
                    face_center_x, face_center_y = face.center
                    padding_factor = 1.8
                    
                    crop_width = int(face.width * padding_factor)
                    crop_height = int(face.height * padding_factor)
                    
                    # Adjust crop to maintain target aspect ratio (1080/960 = 1.125)
                    crop_aspect = crop_width / crop_height if crop_height > 0 else 1.0
                    
                    if crop_aspect > target_aspect:
                        # Crop is too wide, increase height
                        crop_height = int(crop_width / target_aspect)
                    else:
                        # Crop is too tall, increase width
                        crop_width = int(crop_height * target_aspect)
                    
                    # Center crop on face
                    crop_x = face_center_x - crop_width // 2
                    crop_y = face_center_y - crop_height // 2
                    
                    # Ensure crop stays within bounds
                    crop_x = max(0, min(crop_x, result.width - crop_width))
                    crop_y = max(0, min(crop_y, result.height - crop_height))
                    
                    # Ensure positive dimensions
                    crop_width = max(1, min(crop_width, result.width - crop_x))
                    crop_height = max(1, min(crop_height, result.height - crop_y))
                    
                    # Draw dashed rectangle for this face's crop region
                    color = (255, 0, 255)  # Magenta for split-screen
                    draw_dashed_rectangle(frame, (crop_x, crop_y),
                                         (crop_x + crop_width, crop_y + crop_height),
                                         color, 3, 15)
                    
                    # Label indicating top/bottom position in output
                    position_label = "TOP" if i == 0 else "BOTTOM"
                    label_x = crop_x + 5
                    label_y = crop_y + 25
                    cv2.rectangle(frame, (label_x, label_y - 18), (label_x + 80, label_y + 4), color, -1)
                    cv2.putText(frame, position_label, (label_x + 5, label_y),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Draw timeline bar at bottom
        timeline_height = 20
        timeline_y = result.height - timeline_height - 10
        cv2.rectangle(frame, (10, timeline_y), (result.width - 10, timeline_y + timeline_height), (50, 50, 50), -1)
        
        # Mark current position
        progress = frame_idx / result.total_frames
        marker_x = int(10 + progress * (result.width - 20))
        cv2.rectangle(frame, (marker_x - 2, timeline_y), (marker_x + 2, timeline_y + timeline_height), (255, 255, 255), -1)
        
        # Draw mode segments on timeline
        for seg in content_segments:
            seg_start = int(10 + (seg.start_time / result.duration) * (result.width - 20))
            seg_end = int(10 + (seg.end_time / result.duration) * (result.width - 20))
            seg_color = mode_colors.get(seg.mode, (128, 128, 128))
            cv2.rectangle(frame, (seg_start, timeline_y + 2), (seg_end, timeline_y + timeline_height - 2), seg_color, -1)
        
        # Draw metrics panel
        panel_y = 60
        metrics = [
            f"Faces: {len(active_faces)} | Tracks: {result.face_track_count}",
            f"Frame: {frame_idx}/{result.total_frames} | Time: {timestamp:.2f}s",
            f"Coverage: {result.frame_coverage_pct:.1f}%"
        ]
        for line in metrics:
            cv2.rectangle(frame, (5, panel_y - 15), (300, panel_y + 5), (0, 0, 0), -1)
            cv2.putText(frame, line, (10, panel_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            panel_y += 22
        
        out.write(frame)
    
    cap.release()
    out.release()
    logger.info(f"Debug video saved: {output_path}")


def print_summary(results: List[VideoTestResult]):
    """Print summary table of all test results."""
    print("\n" + "="*80)
    print("FACE DETECTION TEST RESULTS SUMMARY")
    print("="*80)
    
    print(f"\n{'Video':<35} {'Expected':<12} {'Detected':<12} {'Match':<6} {'Faces':<6} {'Coverage':<10}")
    print("-"*80)
    
    for r in results:
        match_str = "✓" if r.mode_match else "✗"
        expected = r.expected_mode or "N/A"
        print(f"{r.video_name:<35} {expected:<12} {r.detected_mode:<12} {match_str:<6} {r.face_track_count:<6} {r.frame_coverage_pct:.1f}%")
    
    print("-"*80)
    
    # Print issues
    all_issues = []
    for r in results:
        for issue in r.issues:
            all_issues.append(f"[{r.video_name}] {issue}")
    
    if all_issues:
        print("\nISSUES DETECTED:")
        for issue in all_issues:
            print(f"  ⚠ {issue}")
    else:
        print("\n✓ No issues detected")
    
    print()


def main():
    parser = argparse.ArgumentParser(description="Run face detection tests on all videos")
    parser.add_argument('--video', '-v', help='Test specific video file')
    parser.add_argument('--sample-rate', type=int, default=2, help='Face detection sample rate (default: 2)')
    args = parser.parse_args()
    
    videos_dir = current_dir / 'videos'
    outputs_dir = current_dir / 'outputs'
    
    # Ensure directories exist
    videos_dir.mkdir(exist_ok=True)
    outputs_dir.mkdir(exist_ok=True)
    
    # Find test videos
    if args.video:
        video_path = videos_dir / args.video
        if not video_path.exists():
            video_path = Path(args.video)
        if not video_path.exists():
            logger.error(f"Video not found: {args.video}")
            sys.exit(1)
        video_files = [video_path]
    else:
        video_files = list(videos_dir.glob('*.mp4'))
    
    if not video_files:
        logger.warning(f"No .mp4 files found in {videos_dir}")
        logger.info("Add test videos to the videos/ folder and run again.")
        logger.info("See videos/README.md for naming conventions.")
        sys.exit(0)
    
    logger.info(f"Found {len(video_files)} test video(s)")
    
    # Run tests
    results = []
    for video_path in video_files:
        try:
            result = run_test(str(video_path), str(outputs_dir), sample_rate=args.sample_rate)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to test {video_path}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print summary
    if results:
        print_summary(results)
        
        # Save combined results
        combined_path = outputs_dir / 'all_results.json'
        with open(combined_path, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2)
        logger.info(f"Combined results saved: {combined_path}")


if __name__ == "__main__":
    main()
