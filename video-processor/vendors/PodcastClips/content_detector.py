"""
Content mode detection module for identifying horizontal content segments.

Detects when video shows content (screen recordings, articles, images) instead of faces,
and determines when to switch between face-tracking vertical mode and horizontal content mode.
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    logging.warning("pytesseract not available - OCR-based content detection disabled")

from .face_tracker import FaceBox

logger = logging.getLogger(__name__)


class ContentMode(Enum):
    """Video content display mode."""
    FACE = "face"  # Face-tracked vertical crop
    HORIZONTAL = "horizontal"  # Full horizontal content display


@dataclass
class ContentSegment:
    """Represents a segment with a specific content mode."""
    start_time: float
    end_time: float
    mode: ContentMode
    confidence: float = 1.0  # Confidence in mode selection (0-1)

    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end_time - self.start_time

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "start": self.start_time,
            "end": self.end_time,
            "mode": self.mode.value,
            "confidence": self.confidence
        }


class ContentModeDetector:
    """
    Detects when video content switches between faces and horizontal content.

    Uses face detection data, OCR, and visual analysis to determine optimal
    display mode for each segment of a video.
    """

    def __init__(
        self,
        face_loss_threshold: float = 1.0,
        face_return_threshold: float = 0.5,
        min_segment_duration: float = 0.5,
        text_density_threshold: float = 0.02,
        use_ocr: bool = True
    ):
        """
        Initialize content mode detector.

        Args:
            face_loss_threshold: Seconds without face detection to trigger horizontal mode
            face_return_threshold: Seconds with face detection to return to face mode
            min_segment_duration: Minimum segment duration to avoid flicker (seconds)
            text_density_threshold: Minimum text density to confirm content (0-1)
            use_ocr: Whether to use OCR for text detection (requires pytesseract)
        """
        self.face_loss_threshold = face_loss_threshold
        self.face_return_threshold = face_return_threshold
        self.min_segment_duration = min_segment_duration
        self.text_density_threshold = text_density_threshold
        self.use_ocr = use_ocr and HAS_OCR

        if use_ocr and not HAS_OCR:
            logger.warning("OCR requested but pytesseract not available")

    def analyze_video_segments(
        self,
        video_path: str,
        face_positions: Dict[float, FaceBox],
        fps: float,
        start_time: float = 0.0,
        end_time: Optional[float] = None,
        progress_callback: Optional[callable] = None
    ) -> List[ContentSegment]:
        """
        Analyze video to determine content mode segments.

        Args:
            video_path: Path to video file
            face_positions: Dictionary of timestamp -> FaceBox from face tracker
            fps: Video frame rate
            start_time: Start time in seconds
            end_time: End time in seconds (None = video end)
            progress_callback: Optional callback(progress_pct, message)

        Returns:
            List of ContentSegment objects defining mode timeline
        """
        logger.info(f"Analyzing content modes for {video_path}")

        # Get video properties
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if end_time is None:
            end_time = total_frames / fps

        cap.release()

        # Step 1: Create initial timeline based on face detection
        face_timeline = self._create_face_detection_timeline(
            face_positions, fps, start_time, end_time
        )

        # Step 2: Analyze frames for content detection (optional OCR/visual analysis)
        if self.use_ocr:
            content_scores = self._analyze_content_frames(
                video_path, face_timeline, fps, progress_callback
            )
            # Refine timeline with content scores
            face_timeline = self._refine_timeline_with_content(
                face_timeline, content_scores
            )

        # Step 3: Apply smoothing to avoid rapid mode switching
        segments = self._smooth_segments(face_timeline, fps)

        # Step 4: Merge short segments below minimum duration
        segments = self._merge_short_segments(segments)

        logger.info(f"Content analysis complete: {len(segments)} segments detected")
        self._log_segment_summary(segments)

        return segments

    def _create_face_detection_timeline(
        self,
        face_positions: Dict[float, FaceBox],
        fps: float,
        start_time: float,
        end_time: float
    ) -> List[ContentSegment]:
        """
        Create initial timeline based on face detection gaps.

        Args:
            face_positions: Timestamp -> FaceBox mapping
            fps: Frame rate
            start_time: Start time
            end_time: End time

        Returns:
            Initial list of segments
        """
        if not face_positions:
            # No faces detected - entire segment is horizontal
            return [ContentSegment(start_time, end_time, ContentMode.HORIZONTAL, 1.0)]

        # Sort timestamps
        sorted_timestamps = sorted(face_positions.keys())
        filtered_timestamps = [
            ts for ts in sorted_timestamps
            if start_time <= ts <= end_time
        ]

        if not filtered_timestamps:
            return [ContentSegment(start_time, end_time, ContentMode.HORIZONTAL, 1.0)]

        segments = []
        current_mode = ContentMode.FACE
        segment_start = start_time
        last_face_time = None

        # Sample interval (estimate based on typical sample rate of 5 frames)
        sample_interval = 5.0 / fps

        # Iterate through time range
        t = start_time
        time_step = sample_interval

        while t <= end_time:
            # Check if we have face detection at or near this time
            has_face = any(
                abs(ts - t) < sample_interval * 1.5
                for ts in filtered_timestamps
            )

            if has_face:
                last_face_time = t

                # If we were in horizontal mode, check if we should switch back
                if current_mode == ContentMode.HORIZONTAL:
                    # Need consistent face detection to switch back
                    face_duration = t - segment_start
                    if face_duration >= self.face_return_threshold:
                        # Switch to face mode
                        segments.append(ContentSegment(
                            segment_start, t, ContentMode.HORIZONTAL, 0.9
                        ))
                        segment_start = t
                        current_mode = ContentMode.FACE
            else:
                # No face detected
                if current_mode == ContentMode.FACE and last_face_time is not None:
                    # Check if face has been lost long enough
                    time_since_face = t - last_face_time
                    if time_since_face >= self.face_loss_threshold:
                        # Switch to horizontal mode
                        segments.append(ContentSegment(
                            segment_start, t, ContentMode.FACE, 0.9
                        ))
                        segment_start = t
                        current_mode = ContentMode.HORIZONTAL

            t += time_step

        # Add final segment
        if segment_start < end_time:
            segments.append(ContentSegment(
                segment_start, end_time, current_mode, 0.9
            ))

        return segments

    def _analyze_content_frames(
        self,
        video_path: str,
        segments: List[ContentSegment],
        fps: float,
        progress_callback: Optional[callable] = None
    ) -> Dict[float, float]:
        """
        Analyze frames for content indicators (text, UI elements, etc.).

        Args:
            video_path: Path to video
            segments: Initial segments to analyze
            fps: Frame rate
            progress_callback: Progress callback

        Returns:
            Dictionary mapping timestamp -> content score (0-1)
        """
        content_scores = {}
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            logger.warning(f"Could not open video for content analysis: {video_path}")
            return content_scores

        try:
            # Analyze frames in potential horizontal segments
            horizontal_segments = [s for s in segments if s.mode == ContentMode.HORIZONTAL]

            if not horizontal_segments:
                return content_scores

            total_checks = len(horizontal_segments) * 3  # Sample 3 frames per segment
            checks_done = 0

            for segment in horizontal_segments:
                # Sample frames at start, middle, end of segment
                sample_times = [
                    segment.start_time,
                    (segment.start_time + segment.end_time) / 2,
                    segment.end_time
                ]

                for sample_time in sample_times:
                    frame_num = int(sample_time * fps)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                    ret, frame = cap.read()

                    if ret:
                        content_score = self._calculate_content_score(frame)
                        content_scores[sample_time] = content_score

                    checks_done += 1
                    if progress_callback and checks_done % 5 == 0:
                        progress = int((checks_done / total_checks) * 100)
                        progress_callback(progress, f"Analyzing content frames: {progress}%")

        finally:
            cap.release()

        return content_scores

    def _calculate_content_score(self, frame: np.ndarray) -> float:
        """
        Calculate content score for a frame (0 = face-like, 1 = content-like).

        Analyzes:
        - Text density (OCR)
        - Edge density (sharp UI elements)
        - Color distribution (UI vs natural scenes)

        Args:
            frame: Video frame (BGR)

        Returns:
            Content score (0-1)
        """
        scores = []

        # 1. Text density via OCR
        if self.use_ocr:
            text_score = self._detect_text_density(frame)
            scores.append(text_score * 2.0)  # Weight text heavily

        # 2. Edge density (sharp edges indicate UI/text)
        edge_score = self._calculate_edge_density(frame)
        scores.append(edge_score)

        # 3. Color saturation (natural scenes vs UI)
        saturation_score = self._calculate_saturation_score(frame)
        scores.append(saturation_score)

        # Average scores
        if not scores:
            return 0.5

        final_score = np.mean(scores)
        return min(1.0, max(0.0, final_score))

    def _detect_text_density(self, frame: np.ndarray) -> float:
        """
        Detect text density using OCR.

        Args:
            frame: Video frame

        Returns:
            Text density score (0-1)
        """
        if not self.use_ocr:
            return 0.0

        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Apply threshold for better OCR
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Get bounding boxes of detected text
            data = pytesseract.image_to_data(binary, output_type=pytesseract.Output.DICT)

            # Calculate text coverage
            text_area = 0
            for i, conf in enumerate(data['conf']):
                if int(conf) > 30:  # Confidence threshold
                    w = data['width'][i]
                    h = data['height'][i]
                    text_area += w * h

            frame_area = frame.shape[0] * frame.shape[1]
            text_density = text_area / frame_area if frame_area > 0 else 0

            # Normalize to 0-1 range (assume 10% coverage = maximum)
            normalized = text_density / 0.1
            return min(1.0, normalized)

        except Exception as e:
            logger.debug(f"OCR failed: {e}")
            return 0.0

    def _calculate_edge_density(self, frame: np.ndarray) -> float:
        """
        Calculate edge density (high edges = UI/content, low edges = natural scenes).

        Args:
            frame: Video frame

        Returns:
            Edge density score (0-1)
        """
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Apply Canny edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Calculate percentage of edge pixels
        edge_density = np.count_nonzero(edges) / edges.size

        # Normalize (assume 5% edges = content, 0.5% = face)
        # Map 0.5%-5% to 0-1
        normalized = (edge_density - 0.005) / (0.05 - 0.005)
        return min(1.0, max(0.0, normalized))

    def _calculate_saturation_score(self, frame: np.ndarray) -> float:
        """
        Calculate saturation score (low saturation = UI/content).

        Args:
            frame: Video frame

        Returns:
            Content score based on saturation (0-1)
        """
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Calculate mean saturation
        mean_saturation = np.mean(hsv[:, :, 1]) / 255.0

        # Low saturation suggests UI/document (black/white/gray)
        # Map high saturation (0.3+) to 0, low saturation (0.1-) to 1
        if mean_saturation > 0.3:
            return 0.0
        elif mean_saturation < 0.1:
            return 1.0
        else:
            return (0.3 - mean_saturation) / 0.2

    def _refine_timeline_with_content(
        self,
        segments: List[ContentSegment],
        content_scores: Dict[float, float]
    ) -> List[ContentSegment]:
        """
        Refine segment timeline using content scores.

        Args:
            segments: Initial segments
            content_scores: Timestamp -> content score mapping

        Returns:
            Refined segments
        """
        if not content_scores:
            return segments

        refined = []

        for segment in segments:
            # Get content scores for this segment
            segment_scores = [
                score for ts, score in content_scores.items()
                if segment.start_time <= ts <= segment.end_time
            ]

            if not segment_scores:
                refined.append(segment)
                continue

            avg_score = np.mean(segment_scores)

            # If segment is marked as horizontal but content score is low, reconsider
            if segment.mode == ContentMode.HORIZONTAL and avg_score < 0.3:
                # Low content score - maybe not actually content
                segment.mode = ContentMode.FACE
                segment.confidence = 0.7

            # If segment is marked as face but content score is high, reconsider
            elif segment.mode == ContentMode.FACE and avg_score > 0.7:
                # High content score - maybe showing content
                segment.mode = ContentMode.HORIZONTAL
                segment.confidence = 0.8

            # Update confidence based on content score alignment
            if segment.mode == ContentMode.HORIZONTAL:
                segment.confidence = min(1.0, avg_score + 0.3)
            else:
                segment.confidence = min(1.0, (1.0 - avg_score) + 0.3)

            refined.append(segment)

        return refined

    def _smooth_segments(
        self,
        segments: List[ContentSegment],
        fps: float
    ) -> List[ContentSegment]:
        """
        Smooth segments to avoid rapid mode switching (debouncing).

        Args:
            segments: Raw segments
            fps: Frame rate

        Returns:
            Smoothed segments
        """
        if len(segments) <= 1:
            return segments

        smoothed = [segments[0]]

        for i in range(1, len(segments)):
            current = segments[i]
            previous = smoothed[-1]

            # If mode didn't change, merge segments
            if current.mode == previous.mode:
                previous.end_time = current.end_time
                previous.confidence = (previous.confidence + current.confidence) / 2
            else:
                smoothed.append(current)

        return smoothed

    def _merge_short_segments(
        self,
        segments: List[ContentSegment]
    ) -> List[ContentSegment]:
        """
        Merge segments shorter than minimum duration into adjacent segments.

        Args:
            segments: Input segments

        Returns:
            Merged segments
        """
        if len(segments) <= 1:
            return segments

        merged = []
        i = 0

        while i < len(segments):
            current = segments[i]

            # If segment is too short, merge with adjacent
            if current.duration() < self.min_segment_duration:
                # Merge with previous if available
                if merged:
                    merged[-1].end_time = current.end_time
                # Otherwise merge with next if available
                elif i + 1 < len(segments):
                    segments[i + 1].start_time = current.start_time
                else:
                    # Last segment, keep it
                    merged.append(current)
            else:
                merged.append(current)

            i += 1

        return merged

    def _log_segment_summary(self, segments: List[ContentSegment]):
        """Log summary of detected segments."""
        face_duration = sum(s.duration() for s in segments if s.mode == ContentMode.FACE)
        horizontal_duration = sum(s.duration() for s in segments if s.mode == ContentMode.HORIZONTAL)
        total_duration = face_duration + horizontal_duration

        logger.info(f"Segment summary:")
        logger.info(f"  Total duration: {total_duration:.1f}s")
        logger.info(f"  Face mode: {face_duration:.1f}s ({face_duration/total_duration*100:.1f}%)")
        logger.info(f"  Horizontal mode: {horizontal_duration:.1f}s ({horizontal_duration/total_duration*100:.1f}%)")
        logger.info(f"  Segments: {len(segments)}")

        for i, segment in enumerate(segments):
            logger.debug(
                f"  Segment {i+1}: {segment.start_time:.1f}s-{segment.end_time:.1f}s "
                f"[{segment.mode.value}] (confidence: {segment.confidence:.2f})"
            )
