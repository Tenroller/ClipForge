"""
Gaze detection module using MediaPipe Face Mesh iris landmarks.

Detects gaze direction to determine if a person is looking at the camera,
at another person, or off-screen. Useful for prioritizing faces and
improving crop decisions.
"""

import numpy as np
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.gaze_detection")


@dataclass
class GazeVector:
    """Gaze direction vector."""
    horizontal_angle: float  # Degrees: negative=left, positive=right
    vertical_angle: float    # Degrees: negative=up, positive=down
    confidence: float        # 0-1
    is_looking_at_camera: bool
    is_looking_offscreen: bool


class GazeDetector:
    """
    Gaze detection using MediaPipe Face Mesh iris landmarks.

    Estimates gaze direction from iris position relative to eye boundaries.
    Note: This provides approximate gaze direction, not precise eye tracking.
    """

    def __init__(
        self,
        camera_threshold: float = 10.0,
        offscreen_threshold: float = 25.0
    ):
        """
        Initialize gaze detector.

        Args:
            camera_threshold: Angle threshold (degrees) for "looking at camera"
                             - < 10°: Looking at camera
                             - 10-25°: Looking slightly off
                             - > 25°: Looking away
            offscreen_threshold: Angle threshold for "looking offscreen"
        """
        self.camera_threshold = camera_threshold
        self.offscreen_threshold = offscreen_threshold

        # MediaPipe Face Mesh landmark indices
        # Iris landmarks (need refine_landmarks=True in Face Mesh)
        self.LEFT_IRIS_CENTER = 468
        self.RIGHT_IRIS_CENTER = 473

        # Eye landmarks for reference
        self.LEFT_EYE_LEFT_CORNER = 33
        self.LEFT_EYE_RIGHT_CORNER = 133
        self.LEFT_EYE_TOP = 159
        self.LEFT_EYE_BOTTOM = 145

        self.RIGHT_EYE_LEFT_CORNER = 362
        self.RIGHT_EYE_RIGHT_CORNER = 263
        self.RIGHT_EYE_TOP = 386
        self.RIGHT_EYE_BOTTOM = 374

    def estimate_gaze(
        self,
        face_landmarks,
        frame_width: int,
        frame_height: int
    ) -> Optional[GazeVector]:
        """
        Estimate gaze direction from face landmarks.

        Args:
            face_landmarks: MediaPipe Face Mesh landmarks
            frame_width: Video frame width
            frame_height: Video frame height

        Returns:
            GazeVector with direction estimates, or None if estimation failed
        """
        try:
            # Get iris centers
            left_iris = face_landmarks.landmark[self.LEFT_IRIS_CENTER]
            right_iris = face_landmarks.landmark[self.RIGHT_IRIS_CENTER]

            # Get eye corners for reference frame
            left_eye_left = face_landmarks.landmark[self.LEFT_EYE_LEFT_CORNER]
            left_eye_right = face_landmarks.landmark[self.LEFT_EYE_RIGHT_CORNER]
            left_eye_top = face_landmarks.landmark[self.LEFT_EYE_TOP]
            left_eye_bottom = face_landmarks.landmark[self.LEFT_EYE_BOTTOM]

            right_eye_left = face_landmarks.landmark[self.RIGHT_EYE_LEFT_CORNER]
            right_eye_right = face_landmarks.landmark[self.RIGHT_EYE_RIGHT_CORNER]
            right_eye_top = face_landmarks.landmark[self.RIGHT_EYE_TOP]
            right_eye_bottom = face_landmarks.landmark[self.RIGHT_EYE_BOTTOM]

            # Calculate horizontal gaze for left eye
            left_eye_width = abs(left_eye_right.x - left_eye_left.x)
            left_iris_offset = (left_iris.x - left_eye_left.x) / left_eye_width if left_eye_width > 0 else 0.5

            # Calculate horizontal gaze for right eye
            right_eye_width = abs(right_eye_right.x - right_eye_left.x)
            right_iris_offset = (right_iris.x - right_eye_left.x) / right_eye_width if right_eye_width > 0 else 0.5

            # Average horizontal offset (0.5 = center, < 0.5 = looking left, > 0.5 = looking right)
            horizontal_offset = (left_iris_offset + right_iris_offset) / 2.0

            # Convert to angle (approximate)
            # Assumption: ±0.25 offset corresponds to ±30 degrees
            horizontal_angle = (horizontal_offset - 0.5) * 120.0  # Maps [0, 1] -> [-60, 60] degrees

            # Calculate vertical gaze (using left eye as primary)
            left_eye_height = abs(left_eye_bottom.y - left_eye_top.y)
            vertical_iris_offset = (left_iris.y - left_eye_top.y) / left_eye_height if left_eye_height > 0 else 0.5

            # Convert to angle
            vertical_angle = (vertical_iris_offset - 0.5) * 60.0  # Maps [0, 1] -> [-30, 30] degrees

            # Calculate confidence based on eye openness and landmark quality
            # More open eyes = higher confidence
            eye_openness = left_eye_height * frame_height / (left_eye_width * frame_width) if left_eye_width > 0 else 0.0
            confidence = min(1.0, eye_openness * 5.0)  # Normalize to 0-1

            # Determine gaze state
            total_angle = np.sqrt(horizontal_angle**2 + vertical_angle**2)
            is_looking_at_camera = total_angle < self.camera_threshold
            is_looking_offscreen = total_angle > self.offscreen_threshold

            return GazeVector(
                horizontal_angle=horizontal_angle,
                vertical_angle=vertical_angle,
                confidence=confidence,
                is_looking_at_camera=is_looking_at_camera,
                is_looking_offscreen=is_looking_offscreen
            )

        except (IndexError, AttributeError, ZeroDivisionError) as e:
            logger.debug(f"Failed to estimate gaze: {e}")
            return None

    def get_gaze_target(
        self,
        gaze: GazeVector,
        face_position: Tuple[int, int],
        frame_width: int,
        frame_height: int
    ) -> Tuple[int, int]:
        """
        Estimate where on screen the person is looking.

        Args:
            gaze: Gaze vector
            face_position: (x, y) center of face
            frame_width: Video frame width
            frame_height: Video frame height

        Returns:
            (x, y) estimated gaze target point on screen
        """
        face_x, face_y = face_position

        # Convert angles to pixel offsets
        # Rough approximation: 1 degree ≈ 1% of frame width at arm's length
        horizontal_offset = int((gaze.horizontal_angle / 100.0) * frame_width)
        vertical_offset = int((gaze.vertical_angle / 100.0) * frame_height)

        target_x = face_x + horizontal_offset
        target_y = face_y + vertical_offset

        # Clamp to frame boundaries
        target_x = max(0, min(frame_width - 1, target_x))
        target_y = max(0, min(frame_height - 1, target_y))

        return (target_x, target_y)

    def is_looking_at_other_face(
        self,
        gaze: GazeVector,
        source_face_pos: Tuple[int, int],
        target_face_pos: Tuple[int, int],
        frame_width: int,
        tolerance_degrees: float = 15.0
    ) -> bool:
        """
        Determine if one face is looking at another face.

        Args:
            gaze: Gaze vector of source face
            source_face_pos: (x, y) position of source face center
            target_face_pos: (x, y) position of target face center
            frame_width: Video frame width
            tolerance_degrees: Angular tolerance for "looking at"

        Returns:
            True if source face is looking at target face
        """
        # Calculate actual angle between faces
        dx = target_face_pos[0] - source_face_pos[0]
        dy = target_face_pos[1] - source_face_pos[1]

        # Convert to angle
        actual_horizontal_angle = np.degrees(np.arctan2(dx, frame_width * 0.5))
        actual_vertical_angle = np.degrees(np.arctan2(dy, frame_width * 0.5))

        # Compare with gaze direction
        horizontal_diff = abs(gaze.horizontal_angle - actual_horizontal_angle)
        vertical_diff = abs(gaze.vertical_angle - actual_vertical_angle)

        # Check if within tolerance
        return (horizontal_diff < tolerance_degrees and
                vertical_diff < tolerance_degrees)

    def compute_average_gaze(
        self,
        gaze_vectors: list[GazeVector]
    ) -> Optional[GazeVector]:
        """
        Compute average gaze direction from multiple measurements.

        Args:
            gaze_vectors: List of GazeVector measurements

        Returns:
            Averaged GazeVector, or None if empty list
        """
        if not gaze_vectors:
            return None

        # Filter out low-confidence measurements
        high_conf_gazes = [g for g in gaze_vectors if g.confidence > 0.5]

        if not high_conf_gazes:
            high_conf_gazes = gaze_vectors  # Fall back to all if none are high confidence

        # Compute averages
        avg_horizontal = np.mean([g.horizontal_angle for g in high_conf_gazes])
        avg_vertical = np.mean([g.vertical_angle for g in high_conf_gazes])
        avg_confidence = np.mean([g.confidence for g in high_conf_gazes])

        # Determine states based on average
        total_angle = np.sqrt(avg_horizontal**2 + avg_vertical**2)
        is_looking_at_camera = total_angle < self.camera_threshold
        is_looking_offscreen = total_angle > self.offscreen_threshold

        return GazeVector(
            horizontal_angle=avg_horizontal,
            vertical_angle=avg_vertical,
            confidence=avg_confidence,
            is_looking_at_camera=is_looking_at_camera,
            is_looking_offscreen=is_looking_offscreen
        )

    def get_gaze_description(self, gaze: GazeVector) -> str:
        """
        Get human-readable description of gaze direction.

        Args:
            gaze: GazeVector

        Returns:
            Descriptive string (e.g., "Looking at camera", "Looking left")
        """
        if gaze.is_looking_at_camera:
            return "Looking at camera"

        if gaze.is_looking_offscreen:
            direction = []

            if abs(gaze.horizontal_angle) > 15:
                direction.append("left" if gaze.horizontal_angle < 0 else "right")

            if abs(gaze.vertical_angle) > 15:
                direction.append("up" if gaze.vertical_angle < 0 else "down")

            if direction:
                return f"Looking {' and '.join(direction)} (offscreen)"
            else:
                return "Looking offscreen"

        # Moderate angle
        direction = []

        if abs(gaze.horizontal_angle) > 5:
            direction.append("left" if gaze.horizontal_angle < 0 else "right")

        if abs(gaze.vertical_angle) > 5:
            direction.append("up" if gaze.vertical_angle < 0 else "down")

        if direction:
            return f"Looking {' and '.join(direction)}"
        else:
            return "Looking forward"
