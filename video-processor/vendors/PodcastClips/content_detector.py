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
from loguru import logger as loguru_logger

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    loguru_logger.warning("pytesseract not available - OCR-based content detection disabled")

from .face_tracker import FaceBox

logger = loguru_logger.bind(name="PodcastClips.content_detector")


class ContentMode(Enum):
    """Video content display mode."""
    FACE = "face"  # Face-tracked vertical crop
    HORIZONTAL = "horizontal"  # Full horizontal content display
    SPLIT_SCREEN = "split_screen"  # Multi-person split-screen layout


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
        use_ocr: bool = True,
        ocr_height: int = 720,
        face_tracker: Optional['FaceTracker'] = None
    ):
        """
        Initialize content mode detector.

        Args:
            face_loss_threshold: Seconds without face detection to trigger horizontal mode
            face_return_threshold: Seconds with face detection to return to face mode
            min_segment_duration: Minimum segment duration to avoid flicker (seconds)
            text_density_threshold: Minimum text density to confirm content (0-1)
            use_ocr: Whether to use OCR for text detection (requires pytesseract)
            ocr_height: Target height for OCR processing (default 720p for 2x speedup)
            face_tracker: Optional FaceTracker for split-screen detection
        """
        self.face_loss_threshold = face_loss_threshold
        self.face_return_threshold = face_return_threshold
        self.min_segment_duration = min_segment_duration
        self.text_density_threshold = text_density_threshold
        self.use_ocr = use_ocr and HAS_OCR
        self.ocr_height = ocr_height
        self.face_tracker = face_tracker

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
        video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if end_time is None:
            end_time = total_frames / fps

        cap.release()

        # Step 1: Analyze ALL frames for content presence (content-first approach)
        content_scores = self._analyze_all_frames_for_content(
            video_path, fps, start_time, end_time,
            face_positions, video_width, video_height,
            progress_callback
        )

        # Step 2: Create timeline based on content scores AND face detection
        segments = self._create_content_first_timeline(
            content_scores, face_positions, fps, start_time, end_time,
            video_width, video_height
        )

        # Step 3: Apply smoothing to avoid rapid mode switching
        segments = self._smooth_segments(segments, fps)

        # Step 4: Merge short segments below minimum duration
        segments = self._merge_short_segments(segments)

        logger.info(f"Content analysis complete: {len(segments)} segments detected")
        self._log_segment_summary(segments)

        return segments

    def _analyze_all_frames_for_content(
        self,
        video_path: str,
        fps: float,
        start_time: float,
        end_time: float,
        face_positions: Dict[float, FaceBox],
        video_width: int,
        video_height: int,
        progress_callback: Optional[callable] = None
    ) -> Dict[float, float]:
        """
        Analyze ALL frames for content presence (not just face-loss frames).

        This is the PRIMARY detection method - content presence matters more than face absence.

        Args:
            video_path: Path to video
            fps: Frame rate
            start_time: Start time
            end_time: End time
            face_positions: Face detections (for context)
            video_width: Video width
            video_height: Video height
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
            # Sample frames throughout the entire time range
            # Use same sampling rate as face detection (every ~5 frames at 30fps = ~6 samples/sec)
            sample_interval = 5.0 / fps
            sample_times = []
            t = start_time
            while t <= end_time:
                sample_times.append(t)
                t += sample_interval

            total_samples = len(sample_times)
            samples_done = 0

            logger.info(f"Analyzing {total_samples} frames for content detection")

            for sample_time in sample_times:
                frame_num = int(sample_time * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()

                if ret:
                    # Calculate content score for this frame
                    content_score = self._calculate_content_score(frame)

                    # Adjust score based on face size (if face present)
                    face_at_time = face_positions.get(sample_time)
                    if face_at_time:
                        face_area_ratio = face_at_time.area / (video_width * video_height)
                        # If face is small (<15% of frame), boost content score
                        if face_area_ratio < 0.15:
                            content_score = min(1.0, content_score * 1.3)
                            logger.debug(f"Small face detected at {sample_time:.1f}s ({face_area_ratio*100:.1f}% of frame), boosting content score to {content_score:.2f}")

                    content_scores[sample_time] = content_score

                samples_done += 1
                if progress_callback and samples_done % 20 == 0:
                    progress = int((samples_done / total_samples) * 100)
                    progress_callback(progress, f"Analyzing content: {progress}%")

        finally:
            cap.release()

        logger.info(f"Content analysis complete: {len(content_scores)} frames analyzed")
        return content_scores

    def _create_content_first_timeline(
        self,
        content_scores: Dict[float, float],
        face_positions: Dict[float, FaceBox],
        fps: float,
        start_time: float,
        end_time: float,
        video_width: int,
        video_height: int
    ) -> List[ContentSegment]:
        """
        Create timeline with content detection as PRIMARY factor.

        Decision logic:
        1. High content score (>0.6) → HORIZONTAL mode (even with face present)
        2. Low content score (<0.3) + face present → FACE mode
        3. Medium content score (0.3-0.6) → check face size:
           - Small face (<20% of frame) → HORIZONTAL mode
           - Large face (>=20% of frame) → FACE mode
        4. No data → default to FACE mode

        Args:
            content_scores: Timestamp -> content score mapping
            face_positions: Timestamp -> face box mapping
            fps: Frame rate
            start_time: Start time
            end_time: End time
            video_width: Video width
            video_height: Video height

        Returns:
            List of content segments
        """
        if not content_scores and not face_positions:
            # No data at all - default to horizontal
            return [ContentSegment(start_time, end_time, ContentMode.HORIZONTAL, 0.5)]

        segments = []
        current_mode = ContentMode.FACE
        segment_start = start_time

        # Get all timestamps and sort
        all_timestamps = sorted(set(list(content_scores.keys()) + list(face_positions.keys())))
        all_timestamps = [ts for ts in all_timestamps if start_time <= ts <= end_time]

        if not all_timestamps:
            return [ContentSegment(start_time, end_time, ContentMode.FACE, 0.5)]

        # Thresholds for content detection
        HIGH_CONTENT_THRESHOLD = 0.6  # Strong content indicator
        LOW_CONTENT_THRESHOLD = 0.3   # Weak content indicator
        SMALL_FACE_THRESHOLD = 0.12   # Face area ratio threshold (reduced from 0.20 to only detect true PiP, not normal podcasts)

        for i, timestamp in enumerate(all_timestamps):
            # Get content score and face info for this timestamp
            content_score = content_scores.get(timestamp, 0.0)
            face_box = face_positions.get(timestamp)

            # Calculate face area ratio if face present
            face_area_ratio = 0.0
            if face_box:
                face_area_ratio = face_box.area / (video_width * video_height)

            # Determine mode based on content-first logic, with split-screen detection
            should_be_horizontal = False
            should_be_split_screen = False

            # PRIORITY 0: Check for extreme content (overrides everything)
            if content_score > 0.7:
                # Extreme content signal → horizontal mode (definitely real content)
                should_be_horizontal = True
                logger.debug(f"[{timestamp:.1f}s] Extreme content score: {content_score:.2f} → HORIZONTAL")

            # PRIORITY 1: Large face presence override (prevents false positives from background text)
            elif face_box and face_area_ratio > 0.15:
                # Large face present → default to FACE mode (prevents podcast backgrounds from triggering horizontal)
                should_be_horizontal = False
                logger.debug(f"[{timestamp:.1f}s] Face override (size={face_area_ratio*100:.1f}%, score={content_score:.2f}) → FACE")

            # PRIORITY 2: Check for split-screen scenario (2 separated people)
            elif hasattr(self.face_tracker, 'detect_face_groups') and self.face_tracker:
                face_group_info = self.face_tracker.detect_face_groups(timestamp)
                if (face_group_info["mode"] == "separated" and
                    len(face_group_info["faces"]) >= 2):
                    should_be_split_screen = True
                    logger.debug(
                        f"[{timestamp:.1f}s] Separated faces detected "
                        f"(separation={face_group_info['separation_score']:.2f}) → SPLIT_SCREEN"
                    )
                else:
                    # Not split-screen, continue with content-based logic
                    should_be_horizontal = False

            elif content_score < LOW_CONTENT_THRESHOLD:
                # Weak content signal
                if face_box:
                    # Face present → face mode
                    should_be_horizontal = False
                    logger.debug(f"[{timestamp:.1f}s] Low content ({content_score:.2f}) + face → FACE")
                else:
                    # No face, low content → could be transition, check context
                    # Look ahead/behind for pattern
                    should_be_horizontal = current_mode == ContentMode.HORIZONTAL
                    logger.debug(f"[{timestamp:.1f}s] Low content, no face → maintain {current_mode.value}")

            else:
                # Medium content score (0.3-0.6) → check face size
                if face_box:
                    if face_area_ratio < SMALL_FACE_THRESHOLD:
                        # Small face + medium content → horizontal mode (likely PiP)
                        should_be_horizontal = True
                        logger.debug(f"[{timestamp:.1f}s] Medium content ({content_score:.2f}) + small face ({face_area_ratio*100:.1f}%) → HORIZONTAL")
                    else:
                        # Large face + medium content → face mode
                        should_be_horizontal = False
                        logger.debug(f"[{timestamp:.1f}s] Medium content ({content_score:.2f}) + large face ({face_area_ratio*100:.1f}%) → FACE")
                else:
                    # No face, medium content → horizontal mode
                    should_be_horizontal = True
                    logger.debug(f"[{timestamp:.1f}s] Medium content ({content_score:.2f}), no face → HORIZONTAL")

            # Determine target mode
            if should_be_horizontal:
                target_mode = ContentMode.HORIZONTAL
            elif should_be_split_screen:
                target_mode = ContentMode.SPLIT_SCREEN
            else:
                target_mode = ContentMode.FACE

            # Check if mode changed
            if target_mode != current_mode:
                # Mode switch - save previous segment
                if timestamp > segment_start:
                    confidence = self._calculate_segment_confidence(
                        content_scores, segment_start, timestamp
                    )
                    segments.append(ContentSegment(
                        segment_start, timestamp, current_mode, confidence
                    ))
                    logger.info(f"Segment created: {segment_start:.1f}s-{timestamp:.1f}s [{current_mode.value}] confidence={confidence:.2f}")

                # Start new segment
                segment_start = timestamp
                current_mode = target_mode

        # Add final segment
        if segment_start < end_time:
            confidence = self._calculate_segment_confidence(
                content_scores, segment_start, end_time
            )
            segments.append(ContentSegment(
                segment_start, end_time, current_mode, confidence
            ))
            logger.info(f"Final segment: {segment_start:.1f}s-{end_time:.1f}s [{current_mode.value}] confidence={confidence:.2f}")

        return segments

    def _calculate_segment_confidence(
        self,
        content_scores: Dict[float, float],
        start_time: float,
        end_time: float
    ) -> float:
        """
        Calculate confidence score for a segment based on content scores.

        Args:
            content_scores: Timestamp -> content score mapping
            start_time: Segment start
            end_time: Segment end

        Returns:
            Confidence score (0-1)
        """
        scores_in_range = [
            score for ts, score in content_scores.items()
            if start_time <= ts <= end_time
        ]

        if not scores_in_range:
            return 0.7  # Default moderate confidence

        # High consistency = high confidence
        avg_score = np.mean(scores_in_range)
        std_score = np.std(scores_in_range) if len(scores_in_range) > 1 else 0.0

        # Low standard deviation = consistent signal = high confidence
        consistency_score = 1.0 - min(std_score, 0.3) / 0.3
        confidence = 0.5 + (consistency_score * 0.5)

        return min(1.0, max(0.5, confidence))

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
            scores.append(text_score * 1.5)  # Weight text moderately (reduced from 2.0 to prevent OCR false positives from dominating)

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
            # Downscale frame for faster OCR if needed
            original_height = frame.shape[0]
            if original_height > self.ocr_height:
                scale_factor = self.ocr_height / original_height
                ocr_width = int(frame.shape[1] * scale_factor)
                frame = cv2.resize(
                    frame,
                    (ocr_width, self.ocr_height),
                    interpolation=cv2.INTER_AREA  # Best for downscaling
                )

            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Apply threshold for better OCR
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Get bounding boxes of detected text
            data = pytesseract.image_to_data(binary, output_type=pytesseract.Output.DICT)

            # Calculate text coverage and collect region centers for clustering analysis
            text_area = 0
            text_regions = []
            frame_height, frame_width = frame.shape[0], frame.shape[1]

            for i, conf in enumerate(data['conf']):
                if int(conf) > 65:  # Confidence threshold (increased to reduce false positives from background text)
                    w = data['width'][i]
                    h = data['height'][i]
                    x = data['left'][i]
                    y = data['top'][i]

                    text_area += w * h
                    # Store region center (normalized to 0-1 range)
                    center_x = (x + w / 2) / frame_width
                    center_y = (y + h / 2) / frame_height
                    text_regions.append((center_x, center_y))

            frame_area = frame_height * frame_width
            text_density = text_area / frame_area if frame_area > 0 else 0

            # Apply spatial clustering penalty for scattered text (decorative vs content)
            if len(text_regions) >= 3:
                # Calculate spatial variance (std dev of region centers)
                centers_array = np.array(text_regions)
                spatial_variance = np.std(centers_array)

                # High variance = scattered decorative text → reduce density score
                # Low variance = clustered content text → keep full score
                # Threshold: variance > 0.25 indicates scattered text
                if spatial_variance > 0.25:
                    scatter_penalty = 0.3  # Reduce to 30% of original score
                    text_density *= scatter_penalty
                    logger.debug(f"Spatial clustering: variance={spatial_variance:.2f} → scattered text penalty applied")

            # Normalize to 0-1 range (assume 15% coverage = maximum, more realistic for actual content)
            normalized = text_density / 0.15
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
        split_screen_duration = sum(s.duration() for s in segments if s.mode == ContentMode.SPLIT_SCREEN)
        total_duration = face_duration + horizontal_duration + split_screen_duration

        logger.info(f"Segment summary:")
        logger.info(f"  Total duration: {total_duration:.1f}s")
        logger.info(f"  Face mode: {face_duration:.1f}s ({face_duration/total_duration*100:.1f}%)")
        logger.info(f"  Split-screen mode: {split_screen_duration:.1f}s ({split_screen_duration/total_duration*100:.1f}%)")
        logger.info(f"  Horizontal mode: {horizontal_duration:.1f}s ({horizontal_duration/total_duration*100:.1f}%)")
        logger.info(f"  Segments: {len(segments)}")

        for i, segment in enumerate(segments):
            logger.debug(
                f"  Segment {i+1}: {segment.start_time:.1f}s-{segment.end_time:.1f}s "
                f"[{segment.mode.value}] (confidence: {segment.confidence:.2f})"
            )
