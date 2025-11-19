"""
Scene change detection module using histogram comparison.

Detects cuts, transitions, and scene changes in video to reset
face tracking and prevent identity confusion.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.scene_detector")


@dataclass
class SceneChange:
    """Detected scene change."""
    timestamp: float
    frame_number: int
    change_score: float  # 0-1, higher = more abrupt change
    change_type: str     # "cut", "fade", "gradual"


class SceneDetector:
    """
    Scene change detector using histogram comparison.

    Detects:
    - Hard cuts (abrupt scene changes)
    - Fades (gradual transitions)
    - Camera switches in multi-camera setups
    """

    def __init__(
        self,
        cut_threshold: float = 0.5,
        fade_threshold: float = 0.7,
        fade_window: int = 5,
        check_interval: int = 1
    ):
        """
        Initialize scene detector.

        Args:
            cut_threshold: Similarity threshold for detecting cuts (0-1)
                          - < 0.3: Very strict (only dramatic changes)
                          - 0.5: Balanced (recommended)
                          - > 0.7: Permissive (catches small changes)
            fade_threshold: Threshold for detecting fades
            fade_window: Number of frames to check for fade detection
            check_interval: Check every Nth frame (1 = every frame, 2 = every other)
        """
        self.cut_threshold = cut_threshold
        self.fade_threshold = fade_threshold
        self.fade_window = fade_window
        self.check_interval = check_interval

        # History for fade detection
        self.frame_history: List[Tuple[int, np.ndarray]] = []
        self.max_history = fade_window * 2

    def compute_frame_histogram(
        self,
        frame: np.ndarray,
        bins: int = 32
    ) -> np.ndarray:
        """
        Compute color histogram for a frame.

        Args:
            frame: Video frame (BGR format)
            bins: Number of histogram bins per channel

        Returns:
            Flattened histogram array
        """
        # Convert to HSV for better scene comparison
        # (HSV is more robust to lighting changes than RGB)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Compute histogram for H and S channels
        # (ignore V channel as it's sensitive to lighting)
        h_hist = cv2.calcHist([hsv], [0], None, [bins], [0, 180])
        s_hist = cv2.calcHist([hsv], [1], None, [bins], [0, 256])

        # Normalize histograms
        h_hist = cv2.normalize(h_hist, h_hist).flatten()
        s_hist = cv2.normalize(s_hist, s_hist).flatten()

        # Concatenate H and S histograms
        histogram = np.concatenate([h_hist, s_hist])

        return histogram

    def compare_histograms(
        self,
        hist1: np.ndarray,
        hist2: np.ndarray,
        method: int = cv2.HISTCMP_CORREL
    ) -> float:
        """
        Compare two histograms.

        Args:
            hist1: First histogram
            hist2: Second histogram
            method: OpenCV comparison method
                   - HISTCMP_CORREL: Correlation (1 = identical, -1 = opposite)
                   - HISTCMP_CHISQR: Chi-Square (0 = identical, higher = different)
                   - HISTCMP_INTERSECT: Intersection (higher = more similar)
                   - HISTCMP_BHATTACHARYYA: Bhattacharyya distance (0 = identical)

        Returns:
            Similarity score (normalized to 0-1, where 1 = most similar)
        """
        similarity = cv2.compareHist(
            hist1.reshape(-1, 1).astype(np.float32),
            hist2.reshape(-1, 1).astype(np.float32),
            method
        )

        # Normalize based on method
        if method == cv2.HISTCMP_CORREL:
            # Correlation: [-1, 1] -> [0, 1]
            similarity = (similarity + 1.0) / 2.0
        elif method == cv2.HISTCMP_CHISQR:
            # Chi-Square: [0, inf] -> [0, 1] (inverse)
            similarity = 1.0 / (1.0 + similarity)
        elif method == cv2.HISTCMP_BHATTACHARYYA:
            # Bhattacharyya: [0, 1] -> [0, 1] (inverse)
            similarity = 1.0 - similarity

        return float(similarity)

    def detect_scene_change(
        self,
        frame: np.ndarray,
        frame_number: int,
        timestamp: float
    ) -> Optional[SceneChange]:
        """
        Detect if current frame represents a scene change.

        Args:
            frame: Current video frame
            frame_number: Frame index
            timestamp: Frame timestamp in seconds

        Returns:
            SceneChange object if change detected, None otherwise
        """
        # Only check at intervals
        if frame_number % self.check_interval != 0:
            return None

        # Compute histogram for current frame
        current_hist = self.compute_frame_histogram(frame)

        # Add to history
        self.frame_history.append((frame_number, current_hist))

        # Keep history limited
        if len(self.frame_history) > self.max_history:
            self.frame_history = self.frame_history[-self.max_history:]

        # Need at least 2 frames to compare
        if len(self.frame_history) < 2:
            return None

        # Compare with previous frame
        prev_frame_num, prev_hist = self.frame_history[-2]
        similarity = self.compare_histograms(current_hist, prev_hist)

        # Detect hard cut
        if similarity < self.cut_threshold:
            change_score = 1.0 - similarity

            logger.info(
                f"Scene cut detected at frame {frame_number} "
                f"(t={timestamp:.2f}s, score={change_score:.3f})"
            )

            return SceneChange(
                timestamp=timestamp,
                frame_number=frame_number,
                change_score=change_score,
                change_type="cut"
            )

        # Detect fade (gradual change over multiple frames)
        if len(self.frame_history) >= self.fade_window:
            # Compare current frame with frame from fade_window ago
            old_frame_num, old_hist = self.frame_history[-self.fade_window]
            fade_similarity = self.compare_histograms(current_hist, old_hist)

            # Check if there's been a gradual change
            if fade_similarity < self.fade_threshold:
                # Verify it's gradual (not just intermittent changes)
                is_gradual = True
                for i in range(-self.fade_window, -1):
                    if i + 1 < -len(self.frame_history):
                        continue

                    _, hist_i = self.frame_history[i]
                    _, hist_i_next = self.frame_history[i + 1]

                    step_similarity = self.compare_histograms(hist_i, hist_i_next)

                    # If any step is too abrupt, it's not a fade
                    if step_similarity < self.cut_threshold:
                        is_gradual = False
                        break

                if is_gradual:
                    change_score = 1.0 - fade_similarity

                    logger.info(
                        f"Scene fade detected at frame {frame_number} "
                        f"(t={timestamp:.2f}s, score={change_score:.3f})"
                    )

                    return SceneChange(
                        timestamp=timestamp,
                        frame_number=frame_number,
                        change_score=change_score,
                        change_type="fade"
                    )

        return None

    def detect_all_scene_changes(
        self,
        video_path: str,
        sample_rate: int = 1,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[SceneChange]:
        """
        Detect all scene changes in a video.

        Args:
            video_path: Path to video file
            sample_rate: Process every Nth frame
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            List of detected scene changes
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        start_frame = int(start_time * fps) if start_time else 0
        end_frame = int(end_time * fps) if end_time else total_frames

        logger.info(
            f"Detecting scene changes in {video_path} "
            f"(frames {start_frame}-{end_frame})"
        )

        scene_changes = []
        self.frame_history.clear()

        try:
            for frame_num in range(start_frame, end_frame, sample_rate):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()

                if not ret:
                    break

                timestamp = frame_num / fps

                # Detect scene change
                change = self.detect_scene_change(frame, frame_num, timestamp)

                if change is not None:
                    scene_changes.append(change)

        finally:
            cap.release()

        logger.info(f"Detected {len(scene_changes)} scene changes")

        return scene_changes

    def should_reset_tracking(
        self,
        scene_change: SceneChange,
        min_change_score: float = 0.6
    ) -> bool:
        """
        Determine if tracking should be reset for a scene change.

        Args:
            scene_change: Detected scene change
            min_change_score: Minimum score to trigger reset

        Returns:
            True if tracking should be reset
        """
        # Always reset on hard cuts
        if scene_change.change_type == "cut":
            return True

        # Reset on significant fades
        if scene_change.change_type == "fade" and scene_change.change_score >= min_change_score:
            return True

        return False

    def get_scene_segments(
        self,
        scene_changes: List[SceneChange],
        video_duration: float
    ) -> List[Tuple[float, float]]:
        """
        Convert scene changes into continuous scene segments.

        Args:
            scene_changes: List of detected scene changes
            video_duration: Total video duration in seconds

        Returns:
            List of (start_time, end_time) tuples for each scene
        """
        if not scene_changes:
            return [(0.0, video_duration)]

        segments = []
        current_start = 0.0

        for change in scene_changes:
            # Close current segment
            segments.append((current_start, change.timestamp))
            # Start new segment
            current_start = change.timestamp

        # Add final segment
        segments.append((current_start, video_duration))

        return segments

    def cleanup(self):
        """Clean up resources."""
        self.frame_history.clear()
