"""
Face tracking module using MediaPipe for intelligent person-focused cropping.
"""

import cv2
import mediapipe as mp
import numpy as np
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FaceBox:
    """Face bounding box information."""
    x: int  # Left coordinate
    y: int  # Top coordinate
    width: int
    height: int
    confidence: float

    @property
    def center(self) -> Tuple[int, int]:
        """Get center point of face box."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def area(self) -> int:
        """Get area of face box."""
        return self.width * self.height


@dataclass
class CropBox:
    """Crop box for 9:16 format video."""
    x: int  # Left coordinate
    y: int  # Top coordinate (always 0 for horizontal videos)
    width: int
    height: int

    def to_moviepy_crop(self) -> Tuple[int, int, int, int]:
        """Convert to MoviePy crop format (x1, y1, x2, y2)."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)


class FaceTracker:
    """
    Face tracking using MediaPipe Face Detection.

    Analyzes video frames to detect faces and provides optimal crop boxes
    for converting horizontal podcast videos to 9:16 vertical format while
    keeping the speaker centered.
    """

    def __init__(self, use_gpu: bool = True):
        """
        Initialize face tracker with MediaPipe.

        Args:
            use_gpu: Whether to use GPU acceleration (if available)
        """
        self.use_gpu = use_gpu

        # Initialize MediaPipe Face Detection
        mp_face_detection = mp.solutions.face_detection
        self.face_detection = mp_face_detection.FaceDetection(
            model_selection=1,  # 1 = full range model (better for podcasts), 0 = short range
            min_detection_confidence=0.5
        )

        # Storage for detected face positions over time
        self.face_positions: Dict[float, FaceBox] = {}
        self.video_width = 0
        self.video_height = 0
        self.target_aspect = 9 / 16  # Vertical format

    def analyze_video(
        self,
        video_path: str,
        sample_rate: int = 2,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[float, FaceBox]:
        """
        Analyze video and detect face positions at sampled frames.

        Args:
            video_path: Path to video file
            sample_rate: Sample every Nth frame (default 2 = 15fps sampling at 30fps video)
            start_time: Optional start time in seconds (for analyzing specific segments)
            end_time: Optional end time in seconds
            progress_callback: Optional callback function(progress_pct, message) for progress updates

        Returns:
            Dictionary mapping timestamps to face boxes
        """
        logger.info(f"Analyzing video for face detection: {video_path}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        # Get video properties
        self.video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video properties: {self.video_width}x{self.video_height} @ {fps} fps, {total_frames} frames")

        # Determine frame range
        start_frame = int(start_time * fps) if start_time else 0
        end_frame = int(end_time * fps) if end_time else total_frames

        # Calculate total frames to process (with sampling)
        total_frames_to_process = (end_frame - start_frame) // sample_rate
        logger.info(f"Will analyze {total_frames_to_process} frames (sampling every {sample_rate} frames)")

        face_positions = {}
        frames_processed = 0
        faces_detected = 0
        last_progress_pct = 0

        try:
            for frame_num in range(start_frame, end_frame, sample_rate):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()

                if not ret:
                    break

                # Convert BGR to RGB for MediaPipe
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Detect faces
                results = self.face_detection.process(frame_rgb)

                timestamp = frame_num / fps

                if results.detections:
                    # Use the first (most confident) detection
                    detection = results.detections[0]

                    # Get bounding box (normalized coordinates)
                    bbox = detection.location_data.relative_bounding_box

                    # Convert to pixel coordinates
                    x = int(bbox.xmin * self.video_width)
                    y = int(bbox.ymin * self.video_height)
                    w = int(bbox.width * self.video_width)
                    h = int(bbox.height * self.video_height)

                    # Ensure coordinates are within frame bounds
                    x = max(0, x)
                    y = max(0, y)
                    w = min(w, self.video_width - x)
                    h = min(h, self.video_height - y)

                    face_box = FaceBox(
                        x=x,
                        y=y,
                        width=w,
                        height=h,
                        confidence=detection.score[0]
                    )

                    face_positions[timestamp] = face_box
                    faces_detected += 1

                frames_processed += 1

                # Log progress every 10% or every 50 frames (whichever comes first)
                progress_pct = int((frames_processed / total_frames_to_process) * 100)
                if progress_pct >= last_progress_pct + 10 or frames_processed % 50 == 0:
                    detection_rate = (faces_detected / frames_processed * 100) if frames_processed > 0 else 0
                    message = f"Face detection: {progress_pct}% ({frames_processed}/{total_frames_to_process} frames) - {faces_detected} faces found ({detection_rate:.1f}% detection rate)"
                    logger.info(message)

                    # Call progress callback if provided
                    if progress_callback:
                        try:
                            progress_callback(progress_pct, message)
                        except Exception as e:
                            logger.warning(f"Progress callback failed: {e}")

                    last_progress_pct = progress_pct

        finally:
            cap.release()

        self.face_positions = face_positions

        detection_rate = (faces_detected / frames_processed * 100) if frames_processed > 0 else 0
        logger.info(f"Face detection complete: {faces_detected}/{frames_processed} frames ({detection_rate:.1f}%)")

        return face_positions

    def get_optimal_crop_box(
        self,
        start_time: float,
        end_time: float,
        padding_factor: float = 1.5
    ) -> CropBox:
        """
        Calculate optimal crop box for a video segment (9:16 format).

        Uses face positions to determine where to crop the video horizontally,
        ensuring the speaker stays centered throughout the clip.

        Args:
            start_time: Clip start time in seconds
            end_time: Clip end time in seconds
            padding_factor: How much padding around face (1.0 = tight, 2.0 = loose)

        Returns:
            CropBox defining the optimal crop region
        """
        # Get face positions within the time range
        relevant_faces = [
            face for timestamp, face in self.face_positions.items()
            if start_time <= timestamp <= end_time
        ]

        if not relevant_faces:
            logger.warning(f"No faces detected in clip {start_time:.1f}s-{end_time:.1f}s, using center crop")
            return self._get_center_crop_box()

        # Calculate average face center position (for stable crop)
        avg_face_center_x = int(np.mean([face.center[0] for face in relevant_faces]))
        avg_face_center_y = int(np.mean([face.center[1] for face in relevant_faces]))

        # Calculate target width for 9:16 aspect ratio
        target_width = int(self.video_height * self.target_aspect)

        # If video is already narrower than target, use full width
        if self.video_width <= target_width:
            logger.info("Video already narrow enough for 9:16, no horizontal crop needed")
            return CropBox(x=0, y=0, width=self.video_width, height=self.video_height)

        # Calculate crop box centered on average face position
        crop_x = avg_face_center_x - target_width // 2

        # Ensure crop box stays within video bounds
        crop_x = max(0, min(crop_x, self.video_width - target_width))

        logger.info(f"Crop box for {start_time:.1f}s-{end_time:.1f}s: x={crop_x}, width={target_width}, centered on face at ({avg_face_center_x}, {avg_face_center_y})")

        return CropBox(
            x=crop_x,
            y=0,
            width=target_width,
            height=self.video_height
        )

    def _get_center_crop_box(self) -> CropBox:
        """
        Get center crop box when no faces detected (fallback).

        Returns:
            CropBox for center-cropped 9:16 video
        """
        target_width = int(self.video_height * self.target_aspect)

        if self.video_width <= target_width:
            return CropBox(x=0, y=0, width=self.video_width, height=self.video_height)

        crop_x = (self.video_width - target_width) // 2

        return CropBox(
            x=crop_x,
            y=0,
            width=target_width,
            height=self.video_height
        )

    def get_face_position_at_time(self, timestamp: float) -> Optional[FaceBox]:
        """
        Get interpolated face position at a specific timestamp.

        Uses linear interpolation between detected face positions for smooth tracking.

        Args:
            timestamp: Time in seconds

        Returns:
            Interpolated FaceBox, or None if no nearby face positions found
        """
        if not self.face_positions:
            return None

        # Get sorted timestamps
        timestamps = sorted(self.face_positions.keys())

        # Find exact match
        if timestamp in self.face_positions:
            return self.face_positions[timestamp]

        # Find bounding timestamps for interpolation
        before_ts = None
        after_ts = None

        for ts in timestamps:
            if ts <= timestamp:
                before_ts = ts
            elif ts > timestamp and after_ts is None:
                after_ts = ts
                break

        # If timestamp is before all detections
        if before_ts is None and after_ts is not None:
            return self.face_positions[after_ts]

        # If timestamp is after all detections
        if after_ts is None and before_ts is not None:
            return self.face_positions[before_ts]

        # If we have no face positions at all
        if before_ts is None and after_ts is None:
            return None

        # Interpolate between before and after
        face_before = self.face_positions[before_ts]
        face_after = self.face_positions[after_ts]

        # Calculate interpolation factor
        time_diff = after_ts - before_ts
        if time_diff == 0:
            return face_before

        t = (timestamp - before_ts) / time_diff

        # Linear interpolation of face box properties
        interpolated_x = int(face_before.x + t * (face_after.x - face_before.x))
        interpolated_y = int(face_before.y + t * (face_after.y - face_before.y))
        interpolated_w = int(face_before.width + t * (face_after.width - face_before.width))
        interpolated_h = int(face_before.height + t * (face_after.height - face_before.height))
        interpolated_conf = face_before.confidence + t * (face_after.confidence - face_before.confidence)

        return FaceBox(
            x=interpolated_x,
            y=interpolated_y,
            width=interpolated_w,
            height=interpolated_h,
            confidence=interpolated_conf
        )

    def get_dynamic_crop_box_at_time(
        self,
        timestamp: float,
        padding_factor: float = 1.5,
        smoothing_window: float = 1.5
    ) -> CropBox:
        """
        Get crop box for a specific timestamp with smoothing for stable tracking.

        Args:
            timestamp: Time in seconds
            padding_factor: How much padding around face (1.0 = tight, 2.0 = loose)
            smoothing_window: Window in seconds to average face positions (reduces jitter)

        Returns:
            CropBox for the specified timestamp
        """
        # Get face positions within smoothing window
        relevant_faces = [
            face for ts, face in self.face_positions.items()
            if timestamp - smoothing_window / 2 <= ts <= timestamp + smoothing_window / 2
        ]

        if not relevant_faces:
            # Fallback to interpolated position
            face = self.get_face_position_at_time(timestamp)
            if face:
                relevant_faces = [face]
            else:
                return self._get_center_crop_box()

        # Calculate smoothed face center position
        avg_face_center_x = int(np.mean([face.center[0] for face in relevant_faces]))

        # Calculate target width for 9:16 aspect ratio
        target_width = int(self.video_height * self.target_aspect)

        # If video is already narrower than target, use full width
        if self.video_width <= target_width:
            return CropBox(x=0, y=0, width=self.video_width, height=self.video_height)

        # Calculate crop box centered on smoothed face position
        crop_x = avg_face_center_x - target_width // 2

        # Ensure crop box stays within video bounds
        crop_x = max(0, min(crop_x, self.video_width - target_width))

        return CropBox(
            x=crop_x,
            y=0,
            width=target_width,
            height=self.video_height
        )

    def get_face_coverage_percentage(self, start_time: float, end_time: float) -> float:
        """
        Calculate what percentage of the time range has face detections.

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            Percentage (0-100) of time with face detections
        """
        if not self.face_positions:
            return 0.0

        timestamps_in_range = [
            ts for ts in self.face_positions.keys()
            if start_time <= ts <= end_time
        ]

        if not timestamps_in_range:
            return 0.0

        # Estimate coverage based on sampled points
        duration = end_time - start_time
        time_between_samples = 2.0 / 30.0  # Assuming sample_rate=2, ~15 samples per second at 30fps
        expected_samples = duration / time_between_samples

        coverage = (len(timestamps_in_range) / expected_samples) * 100 if expected_samples > 0 else 0
        return min(100.0, coverage)

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'face_detection'):
            self.face_detection.close()
        self.face_positions.clear()
