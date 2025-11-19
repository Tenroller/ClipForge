"""
PodcastClips Debug Visualizer

Helper functions for creating visualizations for the debug UI.
Handles video overlay generation, timeline plots, and data formatting.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import json
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.debug_visualizer")


def generate_face_tracking_overlay(
    video_path: str,
    face_boxes_data: Dict[str, Any],
    output_path: str,
    show_untracked: bool = True,
    show_speech_indicator: bool = True
) -> bool:
    """
    Generate a video with face tracking bounding boxes overlaid.

    Args:
        video_path: Path to the original video
        face_boxes_data: Dictionary containing frame-by-frame face box data
        output_path: Where to save the annotated video
        show_untracked: Whether to show red boxes for untracked faces
        show_speech_indicator: Whether to highlight speaking faces in blue

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Generating face tracking overlay for {video_path}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video: {video_path}")
            return False

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Setup video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        # Extract data
        face_tracks = face_boxes_data.get('face_tracks', [])
        frame_boxes = face_boxes_data.get('frames', {})
        speech_segments = face_boxes_data.get('speech_segments', [])

        logger.info(f"Processing {total_frames} frames with {len(face_tracks)} tracked faces")

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Get current time in seconds
            current_time = frame_idx / fps

            # Get boxes for this frame
            frame_data = frame_boxes.get(str(frame_idx), {})
            tracked_faces = frame_data.get('tracked', [])
            untracked_faces = frame_data.get('untracked', [])

            # Check if any tracked face is speaking
            active_speaker_id = None
            if show_speech_indicator:
                for segment in speech_segments:
                    if segment['start_time'] <= current_time <= segment['end_time']:
                        active_speaker_id = segment.get('face_id')
                        break

            # Draw tracked faces (green boxes, or blue if speaking)
            for face_box in tracked_faces:
                face_id = face_box.get('face_id', -1)
                x = int(face_box['x'])
                y = int(face_box['y'])
                w = int(face_box['width'])
                h = int(face_box['height'])
                confidence = face_box.get('confidence', 0)

                # Color: Blue if speaking, Green if tracked
                if face_id == active_speaker_id:
                    color = (255, 100, 0)  # Blue (BGR)
                    thickness = 4
                    label = f"Face {face_id} [SPEAKING]"
                else:
                    color = (0, 255, 0)  # Green (BGR)
                    thickness = 3
                    label = f"Face {face_id}"

                # Draw rectangle
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)

                # Draw label with background
                label_text = f"{label} ({confidence:.2f})"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                font_thickness = 2

                (text_width, text_height), _ = cv2.getTextSize(label_text, font, font_scale, font_thickness)

                # Background rectangle for text
                cv2.rectangle(
                    frame,
                    (x, y - text_height - 10),
                    (x + text_width + 10, y),
                    color,
                    -1  # Filled
                )

                # Text
                cv2.putText(
                    frame,
                    label_text,
                    (x + 5, y - 5),
                    font,
                    font_scale,
                    (255, 255, 255),  # White text
                    font_thickness
                )

            # Draw untracked faces (red boxes)
            if show_untracked:
                for face_box in untracked_faces:
                    x = int(face_box['x'])
                    y = int(face_box['y'])
                    w = int(face_box['width'])
                    h = int(face_box['height'])
                    reason = face_box.get('reason', 'untracked')

                    # Red dashed-looking box
                    color = (0, 0, 255)  # Red (BGR)
                    thickness = 2

                    # Draw dashed rectangle
                    dash_length = 10
                    for i in range(0, w, dash_length * 2):
                        cv2.line(frame, (x + i, y), (x + min(i + dash_length, w), y), color, thickness)
                        cv2.line(frame, (x + i, y + h), (x + min(i + dash_length, w), y + h), color, thickness)
                    for i in range(0, h, dash_length * 2):
                        cv2.line(frame, (x, y + i), (x, y + min(i + dash_length, h)), color, thickness)
                        cv2.line(frame, (x + w, y + i), (x + w, y + min(i + dash_length, h)), color, thickness)

                    # Small label
                    cv2.putText(
                        frame,
                        reason[:15],  # Truncate
                        (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        color,
                        1
                    )

            # Add timestamp and frame info overlay
            info_text = f"Frame: {frame_idx}/{total_frames} | Time: {current_time:.2f}s | Tracked: {len(tracked_faces)}"
            cv2.putText(
                frame,
                info_text,
                (10, height - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )

            # Add legend in top-right
            legend_y = 30
            legend_x = width - 250

            cv2.putText(frame, "Legend:", (legend_x, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            legend_y += 25

            cv2.rectangle(frame, (legend_x, legend_y - 15), (legend_x + 20, legend_y), (0, 255, 0), -1)
            cv2.putText(frame, "Tracked", (legend_x + 25, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            legend_y += 20

            cv2.rectangle(frame, (legend_x, legend_y - 15), (legend_x + 20, legend_y), (255, 100, 0), -1)
            cv2.putText(frame, "Speaking", (legend_x + 25, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            legend_y += 20

            if show_untracked:
                cv2.rectangle(frame, (legend_x, legend_y - 15), (legend_x + 20, legend_y), (0, 0, 255), 2)
                cv2.putText(frame, "Filtered", (legend_x + 25, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

            out.write(frame)
            frame_idx += 1

            # Progress logging every 100 frames
            if frame_idx % 100 == 0:
                logger.info(f"Processed {frame_idx}/{total_frames} frames ({frame_idx/total_frames*100:.1f}%)")

        cap.release()
        out.release()

        logger.info(f"Successfully generated face tracking overlay: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error generating face tracking overlay: {e}", exc_info=True)
        return False


def extract_face_boxes_from_processor_data(
    video_path: str,
    face_tracker,
    clip_start_time: float,
    clip_end_time: float
) -> Dict[str, Any]:
    """
    Extract frame-by-frame face box data from the face tracker.
    This is called during processing to save debug data.

    Args:
        video_path: Path to video
        face_tracker: FaceTracker instance
        clip_start_time: Start time of the clip
        clip_end_time: End time of the clip

    Returns:
        Dictionary with frame-by-frame face data
    """
    try:
        import mediapipe as mp

        logger.info(f"Extracting face boxes for debug visualization")

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Calculate frame range
        start_frame = int(clip_start_time * fps)
        end_frame = int(clip_end_time * fps)

        # Initialize MediaPipe
        mp_face_detection = mp.solutions.face_detection
        face_detection = mp_face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.5
        )

        frames_data = {}
        face_tracks = {}
        next_face_id = 0

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        for frame_idx in range(start_frame, end_frame):
            ret, frame = cap.read()
            if not ret:
                break

            # Convert to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect faces
            results = face_detection.process(rgb_frame)

            tracked = []
            untracked = []

            if results.detections:
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    x = int(bbox.xmin * width)
                    y = int(bbox.ymin * height)
                    w = int(bbox.width * width)
                    h = int(bbox.height * height)
                    confidence = detection.score[0]

                    # Calculate area ratio
                    area_ratio = (w * h) / (width * height)

                    # Simple tracking: assign face ID based on position similarity
                    face_id = -1
                    min_dist = float('inf')

                    for fid, track in face_tracks.items():
                        if track['last_frame'] == frame_idx - 1:
                            # Calculate distance
                            last_x, last_y = track['last_pos']
                            dist = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5

                            if dist < min_dist and dist < 100:  # Threshold
                                min_dist = dist
                                face_id = fid

                    if face_id == -1:
                        # New face
                        face_id = next_face_id
                        next_face_id += 1
                        face_tracks[face_id] = {
                            'last_frame': frame_idx,
                            'last_pos': (x, y),
                            'positions': {},
                            'face_id': face_id,
                            'area_ratios': []
                        }

                    # Update track
                    face_tracks[face_id]['last_frame'] = frame_idx
                    face_tracks[face_id]['last_pos'] = (x, y)
                    face_tracks[face_id]['positions'][str(frame_idx)] = {'x': x, 'y': y, 'width': w, 'height': h}
                    face_tracks[face_id]['area_ratios'].append(area_ratio)

                    # Determine if tracked or untracked
                    if area_ratio < 0.02:  # Too small
                        untracked.append({
                            'x': x, 'y': y, 'width': w, 'height': h,
                            'confidence': confidence,
                            'reason': 'too_small'
                        })
                    else:
                        tracked.append({
                            'x': x, 'y': y, 'width': w, 'height': h,
                            'confidence': confidence,
                            'face_id': face_id
                        })

            frames_data[str(frame_idx)] = {
                'tracked': tracked,
                'untracked': untracked
            }

        cap.release()
        face_detection.close()

        # Calculate summary for each track
        summary_tracks = []
        for face_id, track in face_tracks.items():
            avg_area = sum(track['area_ratios']) / len(track['area_ratios']) if track['area_ratios'] else 0
            summary_tracks.append({
                'face_id': face_id,
                'positions': track['positions'],
                'avg_area_ratio': avg_area,
                'speech_correlation': 0.0,  # Placeholder
                'frame_count': len(track['positions'])
            })

        return {
            'frames': frames_data,
            'face_tracks': summary_tracks,
            'speech_segments': [],  # Populated separately
            'video_info': {
                'width': width,
                'height': height,
                'fps': fps,
                'start_frame': start_frame,
                'end_frame': end_frame
            }
        }

    except Exception as e:
        logger.error(f"Error extracting face boxes: {e}", exc_info=True)
        return {}


def save_debug_artifact(output_dir: str, artifact_name: str, data: Any):
    """Save debug artifact to the debug directory"""
    debug_dir = Path(output_dir) / "artifacts" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    filepath = debug_dir / artifact_name

    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved debug artifact: {filepath}")
    except Exception as e:
        logger.error(f"Error saving debug artifact {artifact_name}: {e}")


def format_transcript_for_display(transcript_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Format transcript data for tabular display"""
    word_timings = transcript_data.get('word_timings', [])

    rows = []
    for word_info in word_timings:
        rows.append({
            'time': f"{word_info.get('start_time', 0):.2f}s",
            'speaker': word_info.get('speaker', 'N/A'),
            'word': word_info.get('word', ''),
            'confidence': f"{word_info.get('confidence', 0):.2%}"
        })

    return rows


def create_comparison_html(original: Dict, modified: Dict, diff_keys: List[str]) -> str:
    """Create HTML for side-by-side comparison of results"""
    html = "<div style='display: flex; gap: 20px;'>"

    # Original
    html += "<div style='flex: 1; border: 2px solid #ccc; padding: 15px; border-radius: 8px;'>"
    html += "<h3>Original</h3>"
    html += "<ul>"
    for key in diff_keys:
        value = original.get(key, 'N/A')
        html += f"<li><strong>{key}:</strong> {value}</li>"
    html += "</ul>"
    html += "</div>"

    # Modified
    html += "<div style='flex: 1; border: 2px solid #4CAF50; padding: 15px; border-radius: 8px;'>"
    html += "<h3>Modified</h3>"
    html += "<ul>"
    for key in diff_keys:
        value = modified.get(key, 'N/A')
        # Highlight if different
        if original.get(key) != value:
            html += f"<li><strong>{key}:</strong> <span style='background: yellow;'>{value}</span></li>"
        else:
            html += f"<li><strong>{key}:</strong> {value}</li>"
    html += "</ul>"
    html += "</div>"

    html += "</div>"
    return html
