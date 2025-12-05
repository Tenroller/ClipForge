#!/usr/bin/env python3
"""
Debug Face Tracking Visualization Script

This script visualizes face tracking and speaker detection for debugging purposes.
It draws colored bounding boxes on detected faces to show which face would be zoomed:
- Green: Face that will be zoomed (active speaker)
- Red: Other detected faces (not selected for zoom)
- Blue dashed: The 9:16 crop region

Usage:
    python debug_face_tracking.py --video /path/to/video.mp4 --output /path/to/output.mp4
    python debug_face_tracking.py --video /path/to/video.mp4  # Output to same directory
"""

import argparse
import cv2
import numpy as np
import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from tqdm import tqdm
from loguru import logger

# Add parent paths for imports
current_dir = Path(__file__).parent
video_processor_dir = current_dir.parent.parent
backend_dir = video_processor_dir.parent / 'backend'
project_root = video_processor_dir.parent

# Load .env file from project root
try:
    from dotenv import load_dotenv
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment from: {env_path}")
    else:
        # Try video-processor directory
        env_path = video_processor_dir / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded environment from: {env_path}")
except ImportError:
    logger.warning("python-dotenv not installed. Environment variables must be set manually.")

# Add paths for imports - order matters!
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(video_processor_dir))
sys.path.insert(0, str(current_dir))

# Set up package structure for relative imports to work
# Create a fake package to allow relative imports in the modules
import types

# Create the package hierarchy
vendors_package = types.ModuleType('vendors')
vendors_package.__path__ = [str(current_dir.parent)]
sys.modules['vendors'] = vendors_package

podcast_clips_package = types.ModuleType('vendors.PodcastClips')
podcast_clips_package.__path__ = [str(current_dir)]
podcast_clips_package.__package__ = 'vendors.PodcastClips'
sys.modules['vendors.PodcastClips'] = podcast_clips_package

# Now import using the proper package structure
try:
    # Import speaker_detector
    from vendors.PodcastClips.speaker_detector import SpeakerDetector

    # Import face_tracker components
    from vendors.PodcastClips.face_tracker import FaceTracker, FaceBox, CropBox

    # Import content mode detector for format detection
    from vendors.PodcastClips.content_detector import ContentModeDetector, ContentMode, ContentSegment

    logger.info("Successfully loaded face tracking modules")

except Exception as e:
    logger.error(f"Failed to import modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


def extract_audio_from_video(video_path: str, output_path: Optional[str] = None) -> str:
    """
    Extract audio from video file using ffmpeg.

    Args:
        video_path: Path to input video
        output_path: Optional output path for audio file

    Returns:
        Path to extracted audio file
    """
    if output_path is None:
        # Create temporary file
        output_path = tempfile.mktemp(suffix='.wav')

    import subprocess

    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '16000', '-ac', '1',
        output_path
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"Extracted audio to: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract audio: {e.stderr.decode()}")
        raise


def draw_dashed_rectangle(
    frame: np.ndarray,
    pt1: tuple,
    pt2: tuple,
    color: tuple,
    thickness: int = 2,
    dash_length: int = 10
):
    """Draw a dashed rectangle on the frame."""
    x1, y1 = pt1
    x2, y2 = pt2

    # Top edge
    for i in range(x1, x2, dash_length * 2):
        end = min(i + dash_length, x2)
        cv2.line(frame, (i, y1), (end, y1), color, thickness)

    # Bottom edge
    for i in range(x1, x2, dash_length * 2):
        end = min(i + dash_length, x2)
        cv2.line(frame, (i, y2), (end, y2), color, thickness)

    # Left edge
    for i in range(y1, y2, dash_length * 2):
        end = min(i + dash_length, y2)
        cv2.line(frame, (x1, i), (x1, end), color, thickness)

    # Right edge
    for i in range(y1, y2, dash_length * 2):
        end = min(i + dash_length, y2)
        cv2.line(frame, (x2, i), (x2, end), color, thickness)


def visualize_face_tracking(
    video_path: str,
    output_path: str,
    enable_speaker_detection: bool = True,
    enable_diarization: bool = True,
    show_crop_region: bool = True,
    show_all_faces: bool = True,
    show_face_ids: bool = True,
    show_confidence: bool = True,
    show_speech_correlation: bool = True,
    export_data: bool = False,
    sample_rate: int = 2,
    max_tracked_faces: int = 4,
    enable_mixed_mode: bool = True,
    face_loss_threshold: float = 1.0,
    min_segment_duration: float = 0.5
) -> Dict[str, Any]:
    """
    Create a debug visualization video with face tracking overlays.

    Args:
        video_path: Path to input video
        output_path: Path for output annotated video
        enable_speaker_detection: Enable audio-based speaker detection
        enable_diarization: Enable speaker diarization for better speaker identification
        show_crop_region: Draw the crop region (9:16 or 16:9)
        show_all_faces: Show all detected faces (not just active speaker)
        show_face_ids: Display face IDs on boxes
        show_confidence: Display confidence scores
        show_speech_correlation: Display speech correlation scores
        export_data: Export frame-by-frame data to JSON
        sample_rate: Face detection sample rate (every Nth frame)
        max_tracked_faces: Maximum faces to track
        enable_mixed_mode: Enable format detection (9:16 vs 16:9)
        face_loss_threshold: Seconds without face to trigger horizontal mode
        min_segment_duration: Minimum segment duration to avoid flicker

    Returns:
        Dictionary with statistics about the processing
    """
    logger.info(f"Starting face tracking visualization for: {video_path}")

    # Initialize face tracker with improved defaults for wide shots
    face_tracker = FaceTracker(
        use_gpu=True,
        detection_height=0,  # Adaptive - use original resolution for best small face detection
        batch_size=4,
        min_face_size_ratio=0.002,  # Lowered to detect smaller faces in wide shots (allows ~65x65 px faces)
        max_tracked_faces=max_tracked_faces,
        enable_speaker_detection=enable_speaker_detection,
        enable_lip_detection=False
    )

    # Analyze video for faces
    logger.info("Step 1/4: Analyzing video for face detection...")
    face_positions = face_tracker.analyze_video(
        video_path,
        sample_rate=sample_rate
    )

    logger.info(f"Detected faces in {len(face_positions)} frames")
    logger.info(f"Built {len(face_tracker.face_tracks)} face tracks")

    # Extract and analyze audio if speaker detection enabled
    audio_path = None
    if enable_speaker_detection:
        logger.info("Step 2/4: Extracting and analyzing audio...")
        try:
            audio_path = extract_audio_from_video(video_path)
            speech_segments = face_tracker.analyze_audio_for_speech(audio_path)
            logger.info(f"Detected {len(speech_segments)} speech segments")

            # Correlate faces with speech
            logger.info("Step 3/4: Correlating faces with speech activity...")
            face_tracker.correlate_faces_with_speech()

            # Log speech correlation for each track
            for track in face_tracker.face_tracks:
                logger.info(
                    f"  Track {track.face_id}: speech_correlation={track.speech_correlation:.2f}, "
                    f"avg_size={track.avg_area_ratio:.3f}"
                )

            # Run speaker diarization for better speaker identification
            if enable_diarization:
                logger.info("Step 3.25/4: Running speaker diarization...")
                try:
                    face_tracker.run_speaker_diarization(audio_path)

                    # Build speaker-to-face mapping
                    if face_tracker.diarization_segments:
                        logger.info("Step 3.5/4: Building speaker-to-face mapping...")
                        face_tracker.build_speaker_face_mapping()

                        # Log the mapping
                        for speaker, face_id in face_tracker.speaker_to_face_map.items():
                            logger.info(f"  {speaker} -> Face Track {face_id}")
                except Exception as e:
                    logger.warning(f"Speaker diarization failed: {e}")
        except Exception as e:
            logger.warning(f"Audio analysis failed, continuing without speaker detection: {e}")
            enable_speaker_detection = False
    else:
        logger.info("Step 2/4: Skipping audio analysis (speaker detection disabled)")
        logger.info("Step 3/4: Skipping speech correlation")

    # Content mode detection for mixed mode (9:16 vs 16:9)
    content_segments = []
    if enable_mixed_mode:
        logger.info("Step 3.5/4: Detecting content modes (9:16 vs 16:9)...")
        try:
            # Get video properties for content detection
            cap_temp = cv2.VideoCapture(video_path)
            fps_temp = cap_temp.get(cv2.CAP_PROP_FPS)
            total_frames_temp = int(cap_temp.get(cv2.CAP_PROP_FRAME_COUNT))
            duration_temp = total_frames_temp / fps_temp
            cap_temp.release()

            # Initialize content mode detector
            content_detector = ContentModeDetector(
                face_loss_threshold=face_loss_threshold,
                min_segment_duration=min_segment_duration,
                use_ocr=False,
                face_tracker=face_tracker
            )

            # Analyze video for content modes
            content_segments = content_detector.analyze_video_segments(
                video_path=video_path,
                face_positions=face_positions,
                fps=fps_temp,
                start_time=0.0,
                end_time=duration_temp
            )

            logger.info(f"Detected {len(content_segments)} content mode segments")
            for seg in content_segments:
                logger.info(
                    f"  {seg.start_time:.2f}s - {seg.end_time:.2f}s: "
                    f"{seg.mode.value} (confidence: {seg.confidence:.2f})"
                )
        except Exception as e:
            logger.warning(f"Content mode detection failed, using face mode only: {e}")
            enable_mixed_mode = False
    else:
        logger.info("Step 3.5/4: Skipping content mode detection (mixed mode disabled)")

    # Helper function to get content mode at timestamp
    def get_mode_at_time(timestamp: float) -> ContentMode:
        """Get the content mode at a specific timestamp."""
        if not content_segments:
            return ContentMode.FACE
        for seg in content_segments:
            if seg.start_time <= timestamp < seg.end_time:
                return seg.mode
        return ContentMode.FACE

    # Open video for frame-by-frame processing
    logger.info("Step 4/4: Generating visualization video...")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    logger.info(f"Video: {width}x{height} @ {fps:.1f}fps, {total_frames} frames, {duration:.1f}s")

    # Setup video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # Statistics
    stats = {
        'total_frames': total_frames,
        'frames_with_faces': 0,
        'frames_with_active_speaker': 0,
        'face_tracks': len(face_tracker.face_tracks),
        'speech_segments': len(face_tracker.speech_segments) if enable_speaker_detection else 0,
        'content_segments': len(content_segments) if enable_mixed_mode else 0,
        'frames_in_horizontal_mode': 0
    }

    # Data for export
    frame_data = {} if export_data else None

    # Process each frame
    for frame_idx in tqdm(range(total_frames), desc="Processing frames"):
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_idx / fps

        # Get all active faces at this timestamp
        active_faces = []
        for track in face_tracker.face_tracks:
            # Find face position in this track near the timestamp
            nearby_timestamps = [
                ts for ts in track.positions.keys()
                if abs(ts - timestamp) < 0.5
            ]
            if nearby_timestamps:
                closest_ts = min(nearby_timestamps, key=lambda ts: abs(ts - timestamp))
                face = track.positions[closest_ts]
                active_faces.append({
                    'face': face,
                    'track': track,
                    'is_interpolated': abs(closest_ts - timestamp) > 0.1
                })

        # Get active speaker (the face that would be zoomed)
        active_speaker_face = None
        if enable_speaker_detection:
            active_speaker_face = face_tracker.get_active_speaker_at_time(timestamp)
        elif face_positions:
            # Fall back to largest face
            active_speaker_face = face_tracker.get_face_position_at_time(timestamp)

        # Get current content mode
        current_mode = get_mode_at_time(timestamp)

        # Get crop region - only for vertical mode
        crop_box = None
        if show_crop_region and current_mode != ContentMode.HORIZONTAL:
            crop_box = face_tracker.get_dynamic_crop_box_at_time(timestamp)

        # Draw crop region based on content mode
        if show_crop_region:
            if current_mode == ContentMode.HORIZONTAL:
                # For horizontal mode, show a 16:9 letterbox area
                # Calculate 16:9 region that would fit in the frame
                target_aspect = 16 / 9
                frame_aspect = width / height

                if frame_aspect > target_aspect:
                    # Frame is wider than 16:9, add horizontal letterbox
                    new_width = int(height * target_aspect)
                    horizontal_x = (width - new_width) // 2
                    horizontal_y = 0
                    horizontal_w = new_width
                    horizontal_h = height
                else:
                    # Frame is taller than 16:9, add vertical letterbox
                    new_height = int(width / target_aspect)
                    horizontal_x = 0
                    horizontal_y = (height - new_height) // 2
                    horizontal_w = width
                    horizontal_h = new_height

                # Draw yellow/orange dashed rectangle for horizontal mode
                draw_dashed_rectangle(
                    frame,
                    (horizontal_x, horizontal_y),
                    (horizontal_x + horizontal_w, horizontal_y + horizontal_h),
                    (0, 165, 255),  # Orange (BGR)
                    thickness=3,
                    dash_length=15
                )

                # Add "HORIZONTAL MODE" label
                cv2.putText(
                    frame,
                    "FORMAT: 16:9 HORIZONTAL",
                    (horizontal_x + 10, horizontal_y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 165, 255),
                    2
                )
            elif crop_box:
                # Draw blue dashed rectangle for face mode (9:16)
                draw_dashed_rectangle(
                    frame,
                    (crop_box.x, crop_box.y),
                    (crop_box.x + crop_box.width, crop_box.y + crop_box.height),
                    (255, 150, 0),  # Blue (BGR)
                    thickness=3,
                    dash_length=15
                )

                # Add "VERTICAL MODE" label
                cv2.putText(
                    frame,
                    "FORMAT: 9:16 VERTICAL",
                    (crop_box.x + 10, crop_box.y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 150, 0),
                    2
                )

        # Draw faces
        has_faces = False
        has_active_speaker = False

        if show_all_faces:
            for face_data in active_faces:
                face = face_data['face']
                track = face_data['track']

                # Determine if this is the active speaker
                is_active_speaker = (
                    active_speaker_face is not None and
                    face.face_id == active_speaker_face.face_id
                )

                if is_active_speaker:
                    # Green box for active speaker (face to be zoomed)
                    color = (0, 255, 0)  # Green (BGR)
                    thickness = 4
                    label_prefix = "ZOOM -> "
                    has_active_speaker = True
                else:
                    # Red box for other faces
                    color = (0, 0, 255)  # Red (BGR)
                    thickness = 2
                    label_prefix = ""

                has_faces = True

                # Draw bounding box
                cv2.rectangle(
                    frame,
                    (face.x, face.y),
                    (face.x + face.width, face.y + face.height),
                    color,
                    thickness
                )

                # Build label
                label_parts = []
                if show_face_ids:
                    label_parts.append(f"ID:{face.face_id}")
                if show_confidence:
                    label_parts.append(f"Conf:{face.confidence:.2f}")
                if show_speech_correlation and enable_speaker_detection:
                    label_parts.append(f"Speech:{track.speech_correlation:.2f}")

                label = label_prefix + " | ".join(label_parts)

                # Draw label background
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.5
                font_thickness = 1
                (text_width, text_height), _ = cv2.getTextSize(label, font, font_scale, font_thickness)

                label_y = face.y - 10
                if label_y < text_height + 5:
                    label_y = face.y + face.height + text_height + 5

                cv2.rectangle(
                    frame,
                    (face.x, label_y - text_height - 5),
                    (face.x + text_width + 10, label_y + 5),
                    color,
                    -1
                )

                # Draw label text
                cv2.putText(
                    frame,
                    label,
                    (face.x + 5, label_y),
                    font,
                    font_scale,
                    (255, 255, 255),
                    font_thickness
                )

        # Update stats
        if has_faces:
            stats['frames_with_faces'] += 1
        if has_active_speaker:
            stats['frames_with_active_speaker'] += 1
        if current_mode == ContentMode.HORIZONTAL:
            stats['frames_in_horizontal_mode'] += 1

        # Draw info overlay at bottom
        info_lines = [
            f"Frame: {frame_idx}/{total_frames} | Time: {timestamp:.2f}s",
            f"Faces detected: {len(active_faces)} | Active speaker: {'Yes' if has_active_speaker else 'No'}"
        ]

        # Add format mode info
        if enable_mixed_mode:
            mode_name = current_mode.value.upper()
            format_str = "9:16 VERTICAL" if current_mode == ContentMode.FACE else "16:9 HORIZONTAL"
            info_lines.append(f"Format: {format_str}")

        # Check speech activity
        if enable_speaker_detection:
            is_speech, energy = face_tracker.speaker_detector.is_speech_at_time(
                timestamp, face_tracker.speech_segments
            )
            speech_status = f"Speech: {'Yes' if is_speech else 'No'} (Energy: {energy:.1f})"
            info_lines.append(speech_status)

        # Show current speaker from diarization
        if face_tracker.diarization_segments and face_tracker.speaker_to_face_map:
            current_speaker = face_tracker.get_speaker_at_time(timestamp)
            if current_speaker:
                face_id = face_tracker.speaker_to_face_map.get(current_speaker, "?")
                info_lines.append(f"Diarization: {current_speaker} -> Face {face_id}")
            else:
                info_lines.append("Diarization: No speaker")

        y_offset = height - 20
        for line in reversed(info_lines):
            # Draw background
            (text_w, text_h), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (5, y_offset - text_h - 5), (text_w + 15, y_offset + 5), (0, 0, 0), -1)
            cv2.putText(
                frame,
                line,
                (10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
            y_offset -= 25

        # Draw legend in top-right corner
        legend_x = width - 300
        legend_y = 30

        cv2.putText(frame, "Legend:", (legend_x, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        legend_y += 30

        # Green = zoom target
        cv2.rectangle(frame, (legend_x, legend_y - 15), (legend_x + 25, legend_y), (0, 255, 0), -1)
        cv2.putText(frame, "Zoom Target (Active)", (legend_x + 35, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        legend_y += 25

        # Red = other faces
        cv2.rectangle(frame, (legend_x, legend_y - 15), (legend_x + 25, legend_y), (0, 0, 255), -1)
        cv2.putText(frame, "Other Faces", (legend_x + 35, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        legend_y += 25

        # Blue dashed = 9:16 vertical crop
        draw_dashed_rectangle(frame, (legend_x, legend_y - 15), (legend_x + 25, legend_y), (255, 150, 0), 2, 5)
        cv2.putText(frame, "9:16 Vertical Crop", (legend_x + 35, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        legend_y += 25

        # Orange dashed = 16:9 horizontal mode
        draw_dashed_rectangle(frame, (legend_x, legend_y - 15), (legend_x + 25, legend_y), (0, 165, 255), 2, 5)
        cv2.putText(frame, "16:9 Horizontal Mode", (legend_x + 35, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Export frame data if requested
        if export_data:
            frame_data[frame_idx] = {
                'timestamp': timestamp,
                'faces': [
                    {
                        'face_id': f['face'].face_id,
                        'x': f['face'].x,
                        'y': f['face'].y,
                        'width': f['face'].width,
                        'height': f['face'].height,
                        'confidence': f['face'].confidence,
                        'speech_correlation': f['track'].speech_correlation,
                        'is_active_speaker': (
                            active_speaker_face is not None and
                            f['face'].face_id == active_speaker_face.face_id
                        )
                    }
                    for f in active_faces
                ],
                'crop_region': {
                    'x': crop_box.x,
                    'y': crop_box.y,
                    'width': crop_box.width,
                    'height': crop_box.height
                } if crop_box else None
            }

        out.write(frame)

    # Cleanup
    cap.release()
    out.release()
    face_tracker.cleanup()

    if audio_path and os.path.exists(audio_path):
        os.remove(audio_path)

    # Export data if requested
    if export_data and frame_data:
        data_path = output_path.replace('.mp4', '_data.json')
        with open(data_path, 'w') as f:
            json.dump({
                'stats': stats,
                'face_tracks': [
                    {
                        'face_id': track.face_id,
                        'avg_area_ratio': track.avg_area_ratio,
                        'speech_correlation': track.speech_correlation,
                        'frame_count': len(track.positions)
                    }
                    for track in face_tracker.face_tracks
                ],
                'frames': frame_data
            }, f, indent=2)
        logger.info(f"Exported frame data to: {data_path}")

    logger.info(f"Visualization complete: {output_path}")
    logger.info(f"Statistics:")
    logger.info(f"  Total frames: {stats['total_frames']}")
    logger.info(f"  Frames with faces: {stats['frames_with_faces']} ({stats['frames_with_faces']/stats['total_frames']*100:.1f}%)")
    logger.info(f"  Frames with active speaker: {stats['frames_with_active_speaker']} ({stats['frames_with_active_speaker']/stats['total_frames']*100:.1f}%)")
    logger.info(f"  Face tracks: {stats['face_tracks']}")
    logger.info(f"  Speech segments: {stats['speech_segments']}")
    if enable_mixed_mode:
        logger.info(f"  Content segments: {stats['content_segments']}")
        logger.info(f"  Frames in horizontal mode: {stats['frames_in_horizontal_mode']} ({stats['frames_in_horizontal_mode']/stats['total_frames']*100:.1f}%)")
        logger.info(f"  Frames in vertical mode: {stats['total_frames'] - stats['frames_in_horizontal_mode']} ({(stats['total_frames'] - stats['frames_in_horizontal_mode'])/stats['total_frames']*100:.1f}%)")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Debug face tracking visualization for PodcastClips",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python debug_face_tracking.py --video podcast.mp4

  # Custom output path
  python debug_face_tracking.py --video podcast.mp4 --output debug_output.mp4

  # Disable speaker detection (faster, faces only)
  python debug_face_tracking.py --video podcast.mp4 --no-speaker-detection

  # Disable format detection (always use 9:16 vertical)
  python debug_face_tracking.py --video podcast.mp4 --no-mixed-mode

  # Tune format detection thresholds
  python debug_face_tracking.py --video podcast.mp4 --face-loss-threshold 2.0 --min-segment-duration 1.0

  # Export frame-by-frame data for analysis
  python debug_face_tracking.py --video podcast.mp4 --export-data

  # Process more faces
  python debug_face_tracking.py --video podcast.mp4 --max-faces 8
        """
    )

    parser.add_argument(
        '--video', '-v',
        required=True,
        help='Path to input video file'
    )

    parser.add_argument(
        '--output', '-o',
        help='Path for output video (default: <input>_debug.mp4)'
    )

    parser.add_argument(
        '--no-speaker-detection',
        action='store_true',
        help='Disable audio-based speaker detection'
    )

    parser.add_argument(
        '--no-diarization',
        action='store_true',
        help='Disable speaker diarization (faster but less accurate speaker identification)'
    )

    parser.add_argument(
        '--no-crop-region',
        action='store_true',
        help='Hide the 9:16 crop region overlay'
    )

    parser.add_argument(
        '--export-data',
        action='store_true',
        help='Export frame-by-frame data to JSON'
    )

    parser.add_argument(
        '--sample-rate',
        type=int,
        default=2,
        help='Face detection sample rate (default: 2, every 2nd frame)'
    )

    parser.add_argument(
        '--max-faces',
        type=int,
        default=4,
        help='Maximum number of faces to track (default: 4)'
    )

    parser.add_argument(
        '--hide-ids',
        action='store_true',
        help='Hide face IDs from labels'
    )

    parser.add_argument(
        '--hide-confidence',
        action='store_true',
        help='Hide confidence scores from labels'
    )

    parser.add_argument(
        '--hide-speech-correlation',
        action='store_true',
        help='Hide speech correlation from labels'
    )

    parser.add_argument(
        '--no-mixed-mode',
        action='store_true',
        help='Disable format detection (always use 9:16 vertical)'
    )

    parser.add_argument(
        '--face-loss-threshold',
        type=float,
        default=1.0,
        help='Seconds without face to trigger horizontal mode (default: 1.0)'
    )

    parser.add_argument(
        '--min-segment-duration',
        type=float,
        default=0.5,
        help='Minimum segment duration to avoid flicker (default: 0.5)'
    )

    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.video):
        logger.error(f"Video file not found: {args.video}")
        sys.exit(1)

    # Set output path
    if args.output:
        output_path = args.output
    else:
        video_dir = os.path.dirname(args.video)
        video_name = os.path.splitext(os.path.basename(args.video))[0]
        output_path = os.path.join(video_dir, f"{video_name}_debug.mp4")

    # Run visualization
    try:
        stats = visualize_face_tracking(
            video_path=args.video,
            output_path=output_path,
            enable_speaker_detection=not args.no_speaker_detection,
            enable_diarization=not args.no_diarization,
            show_crop_region=not args.no_crop_region,
            show_all_faces=True,
            show_face_ids=not args.hide_ids,
            show_confidence=not args.hide_confidence,
            show_speech_correlation=not args.hide_speech_correlation,
            export_data=args.export_data,
            sample_rate=args.sample_rate,
            max_tracked_faces=args.max_faces,
            enable_mixed_mode=not args.no_mixed_mode,
            face_loss_threshold=args.face_loss_threshold,
            min_segment_duration=args.min_segment_duration
        )

        print(f"\nVisualization saved to: {output_path}")

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during visualization: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
