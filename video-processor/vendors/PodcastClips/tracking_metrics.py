"""
Tracking quality metrics module for face tracking assessment.

Provides comprehensive metrics to evaluate face tracking quality,
helping identify problematic clips and optimize tracking parameters.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.tracking_metrics")


@dataclass
class TrackingQualityMetrics:
    """Comprehensive tracking quality metrics."""

    # Detection metrics
    avg_face_confidence: float = 0.0
    face_coverage_pct: float = 0.0  # % of frames with detected faces
    detection_rate: float = 0.0     # Faces detected / frames processed

    # Tracking stability metrics
    track_stability: float = 0.0     # Position consistency (0-1)
    avg_velocity: float = 0.0        # Average movement speed (px/s)
    max_velocity: float = 0.0        # Maximum movement speed (px/s)
    jitter_score: float = 0.0        # Jitter/shakiness (0-1, lower = smoother)

    # Multi-face tracking metrics
    num_faces_tracked: int = 0
    avg_faces_per_frame: float = 0.0
    speaker_switch_count: int = 0
    avg_speaker_duration: float = 0.0

    # Face size metrics
    avg_face_size_ratio: float = 0.0  # Average face size / frame area
    min_face_size_ratio: float = 0.0
    max_face_size_ratio: float = 0.0

    # Occlusion/loss metrics
    occlusion_events: int = 0         # Times face was lost then found
    avg_occlusion_duration: float = 0.0  # Average gap duration (seconds)

    # Audio-visual metrics (if available)
    avg_lip_activity: float = 0.0
    speech_correlation: float = 0.0
    av_sync_score: float = 0.0        # Audio-visual synchronization

    # Gaze metrics (if available)
    camera_gaze_pct: float = 0.0      # % of time looking at camera
    offscreen_gaze_pct: float = 0.0   # % of time looking offscreen

    # Scene metrics
    scene_changes: int = 0
    avg_scene_duration: float = 0.0

    # Overall quality
    overall_quality_score: float = 0.0  # Composite score (0-100)

    # Metadata
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    frames_analyzed: int = 0

    def to_dict(self) -> Dict:
        """Convert metrics to dictionary."""
        return {
            "detection": {
                "avg_confidence": round(self.avg_face_confidence, 3),
                "face_coverage_pct": round(self.face_coverage_pct, 2),
                "detection_rate": round(self.detection_rate, 3)
            },
            "stability": {
                "track_stability": round(self.track_stability, 3),
                "avg_velocity_px_s": round(self.avg_velocity, 2),
                "max_velocity_px_s": round(self.max_velocity, 2),
                "jitter_score": round(self.jitter_score, 3)
            },
            "tracking": {
                "num_faces_tracked": self.num_faces_tracked,
                "avg_faces_per_frame": round(self.avg_faces_per_frame, 2),
                "speaker_switches": self.speaker_switch_count,
                "avg_speaker_duration_sec": round(self.avg_speaker_duration, 2)
            },
            "face_size": {
                "avg_ratio": round(self.avg_face_size_ratio, 4),
                "min_ratio": round(self.min_face_size_ratio, 4),
                "max_ratio": round(self.max_face_size_ratio, 4)
            },
            "occlusion": {
                "events": self.occlusion_events,
                "avg_duration_sec": round(self.avg_occlusion_duration, 2)
            },
            "audio_visual": {
                "avg_lip_activity": round(self.avg_lip_activity, 3),
                "speech_correlation": round(self.speech_correlation, 3),
                "av_sync_score": round(self.av_sync_score, 3)
            },
            "gaze": {
                "camera_pct": round(self.camera_gaze_pct, 2),
                "offscreen_pct": round(self.offscreen_gaze_pct, 2)
            },
            "scenes": {
                "scene_changes": self.scene_changes,
                "avg_scene_duration_sec": round(self.avg_scene_duration, 2)
            },
            "overall": {
                "quality_score": round(self.overall_quality_score, 2),
                "rating": self.get_quality_rating()
            },
            "metadata": {
                "start_time": round(self.start_time, 2),
                "end_time": round(self.end_time, 2),
                "duration": round(self.duration, 2),
                "frames_analyzed": self.frames_analyzed
            }
        }

    def get_quality_rating(self) -> str:
        """Get human-readable quality rating."""
        score = self.overall_quality_score

        if score >= 85:
            return "Excellent"
        elif score >= 70:
            return "Good"
        elif score >= 50:
            return "Fair"
        elif score >= 30:
            return "Poor"
        else:
            return "Very Poor"


class TrackingMetricsCalculator:
    """Calculator for face tracking quality metrics."""

    def __init__(self):
        """Initialize metrics calculator."""
        pass

    def compute_track_stability(
        self,
        positions: Dict[float, Tuple[int, int]]
    ) -> float:
        """
        Compute tracking stability from position history.

        Measures how consistently the tracking follows a smooth trajectory.

        Args:
            positions: Dict of timestamp -> (x, y) position

        Returns:
            Stability score (0-1), where 1 = perfectly stable
        """
        if len(positions) < 3:
            return 0.0

        timestamps = sorted(positions.keys())
        coords = [positions[ts] for ts in timestamps]

        # Compute velocity variations
        velocities = []
        for i in range(len(coords) - 1):
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            dt = timestamps[i + 1] - timestamps[i]

            if dt > 0:
                vx = (x2 - x1) / dt
                vy = (y2 - y1) / dt
                velocity = np.sqrt(vx**2 + vy**2)
                velocities.append(velocity)

        if not velocities:
            return 0.0

        # Compute velocity variation coefficient
        mean_velocity = np.mean(velocities)
        std_velocity = np.std(velocities)

        if mean_velocity > 0:
            cv = std_velocity / mean_velocity
            # Lower CV = more stable (convert to 0-1 score)
            stability = 1.0 / (1.0 + cv)
        else:
            stability = 1.0

        return float(stability)

    def compute_jitter_score(
        self,
        positions: Dict[float, Tuple[int, int]]
    ) -> float:
        """
        Compute jitter/shakiness score.

        Measures high-frequency position variations.

        Args:
            positions: Dict of timestamp -> (x, y) position

        Returns:
            Jitter score (0-1), where 0 = smooth, 1 = very jittery
        """
        if len(positions) < 5:
            return 0.0

        timestamps = sorted(positions.keys())
        x_coords = [positions[ts][0] for ts in timestamps]

        # Compute second derivative (acceleration) to detect jitter
        accelerations = []
        for i in range(1, len(x_coords) - 1):
            # Second derivative approximation
            accel = abs(x_coords[i - 1] - 2 * x_coords[i] + x_coords[i + 1])
            accelerations.append(accel)

        if not accelerations:
            return 0.0

        # Normalize by max possible acceleration
        max_accel = max(accelerations) if accelerations else 0
        avg_accel = np.mean(accelerations)

        # Higher average acceleration = more jitter
        # Normalize to 0-1 range (assume 100px is high jitter)
        jitter = min(1.0, avg_accel / 100.0)

        return float(jitter)

    def detect_occlusion_events(
        self,
        positions: Dict[float, any],
        max_gap_sec: float = 2.0
    ) -> Tuple[int, float]:
        """
        Detect occlusion events (gaps in tracking).

        Args:
            positions: Dict of timestamp -> face data
            max_gap_sec: Maximum gap to consider as occlusion (vs. intentional)

        Returns:
            (num_occlusions, avg_occlusion_duration)
        """
        if len(positions) < 2:
            return 0, 0.0

        timestamps = sorted(positions.keys())

        gaps = []
        for i in range(len(timestamps) - 1):
            gap = timestamps[i + 1] - timestamps[i]

            # If gap is larger than expected (assuming ~30fps sampling every 2 frames)
            expected_gap = 2.0 / 30.0  # ~0.067 seconds

            if gap > expected_gap * 3 and gap <= max_gap_sec:
                gaps.append(gap)

        num_occlusions = len(gaps)
        avg_duration = np.mean(gaps) if gaps else 0.0

        return num_occlusions, float(avg_duration)

    def compute_metrics(
        self,
        face_positions: Dict[float, any],
        face_tracks: List[any],
        start_time: float,
        end_time: float,
        video_width: int,
        video_height: int,
        frames_analyzed: int = 0,
        speech_segments: Optional[List] = None,
        scene_changes: Optional[List] = None,
        gaze_data: Optional[Dict] = None
    ) -> TrackingQualityMetrics:
        """
        Compute comprehensive tracking quality metrics.

        Args:
            face_positions: Dict of timestamp -> FaceBox
            face_tracks: List of FaceTrack objects
            start_time: Segment start time
            end_time: Segment end time
            video_width: Video width
            video_height: Video height
            frames_analyzed: Number of frames analyzed
            speech_segments: Optional speech segments
            scene_changes: Optional scene changes
            gaze_data: Optional gaze detection data

        Returns:
            TrackingQualityMetrics object
        """
        metrics = TrackingQualityMetrics()

        metrics.start_time = start_time
        metrics.end_time = end_time
        metrics.duration = end_time - start_time
        metrics.frames_analyzed = frames_analyzed if frames_analyzed > 0 else len(face_positions)

        # Detection metrics
        if face_positions:
            confidences = [
                fb.confidence for fb in face_positions.values()
                if hasattr(fb, 'confidence')
            ]

            if confidences:
                metrics.avg_face_confidence = float(np.mean(confidences))

            # Coverage
            expected_frames = metrics.duration * 15  # Assuming 15 fps effective sampling
            metrics.face_coverage_pct = (len(face_positions) / expected_frames * 100) if expected_frames > 0 else 0

            metrics.detection_rate = len(face_positions) / metrics.frames_analyzed if metrics.frames_analyzed > 0 else 0

        # Tracking stability
        if face_positions:
            positions_dict = {
                ts: (fb.center[0], fb.center[1]) for ts, fb in face_positions.items()
                if hasattr(fb, 'center')
            }

            if positions_dict:
                metrics.track_stability = self.compute_track_stability(positions_dict)
                metrics.jitter_score = self.compute_jitter_score(positions_dict)

                # Velocity metrics
                timestamps = sorted(positions_dict.keys())
                velocities = []

                for i in range(len(timestamps) - 1):
                    x1, y1 = positions_dict[timestamps[i]]
                    x2, y2 = positions_dict[timestamps[i + 1]]
                    dt = timestamps[i + 1] - timestamps[i]

                    if dt > 0:
                        velocity = np.sqrt((x2 - x1)**2 + (y2 - y1)**2) / dt
                        velocities.append(velocity)

                if velocities:
                    metrics.avg_velocity = float(np.mean(velocities))
                    metrics.max_velocity = float(np.max(velocities))

        # Multi-face tracking metrics
        metrics.num_faces_tracked = len(face_tracks)

        if face_tracks:
            # Average faces per frame
            timestamps_with_faces = set()
            for track in face_tracks:
                if hasattr(track, 'positions'):
                    timestamps_with_faces.update(track.positions.keys())

            if timestamps_with_faces:
                face_counts = []
                for ts in timestamps_with_faces:
                    count = sum(1 for track in face_tracks if ts in track.positions)
                    face_counts.append(count)

                metrics.avg_faces_per_frame = float(np.mean(face_counts)) if face_counts else 0

        # Face size metrics
        if face_positions:
            frame_area = video_width * video_height

            size_ratios = [
                (fb.width * fb.height) / frame_area
                for fb in face_positions.values()
                if hasattr(fb, 'width') and hasattr(fb, 'height')
            ]

            if size_ratios:
                metrics.avg_face_size_ratio = float(np.mean(size_ratios))
                metrics.min_face_size_ratio = float(np.min(size_ratios))
                metrics.max_face_size_ratio = float(np.max(size_ratios))

        # Occlusion metrics
        occlusions, avg_duration = self.detect_occlusion_events(face_positions)
        metrics.occlusion_events = occlusions
        metrics.avg_occlusion_duration = avg_duration

        # Audio-visual metrics
        if face_tracks:
            lip_activities = [
                track.avg_lip_activity for track in face_tracks
                if hasattr(track, 'avg_lip_activity')
            ]

            if lip_activities:
                metrics.avg_lip_activity = float(np.mean(lip_activities))

            speech_correlations = [
                track.speech_correlation for track in face_tracks
                if hasattr(track, 'speech_correlation')
            ]

            if speech_correlations:
                metrics.speech_correlation = float(np.max(speech_correlations))

        # Scene metrics
        if scene_changes:
            metrics.scene_changes = len(scene_changes)

            if len(scene_changes) > 0:
                # Average scene duration
                scene_durations = []
                for i in range(len(scene_changes) + 1):
                    if i == 0:
                        duration = scene_changes[0].timestamp - start_time
                    elif i == len(scene_changes):
                        duration = end_time - scene_changes[-1].timestamp
                    else:
                        duration = scene_changes[i].timestamp - scene_changes[i - 1].timestamp

                    scene_durations.append(duration)

                metrics.avg_scene_duration = float(np.mean(scene_durations))
            else:
                metrics.avg_scene_duration = metrics.duration

        # Compute overall quality score
        metrics.overall_quality_score = self.compute_overall_score(metrics)

        return metrics

    def compute_overall_score(self, metrics: TrackingQualityMetrics) -> float:
        """
        Compute overall quality score (0-100).

        Weights different metrics to produce a single quality score.

        Args:
            metrics: TrackingQualityMetrics object

        Returns:
            Overall score (0-100)
        """
        score = 0.0

        # Detection quality (30 points)
        score += metrics.avg_face_confidence * 10  # 0-10 pts
        score += (metrics.face_coverage_pct / 100.0) * 10  # 0-10 pts
        score += metrics.detection_rate * 10  # 0-10 pts

        # Tracking stability (30 points)
        score += metrics.track_stability * 15  # 0-15 pts
        score += (1.0 - metrics.jitter_score) * 15  # 0-15 pts (inverted)

        # Face size quality (10 points)
        # Prefer medium-sized faces (0.05-0.3 of frame)
        if 0.05 <= metrics.avg_face_size_ratio <= 0.3:
            score += 10
        elif metrics.avg_face_size_ratio > 0.0:
            score += 5

        # Occlusion penalty (10 points)
        # Fewer occlusions = higher score
        occlusion_penalty = min(10, metrics.occlusion_events * 2)
        score += (10 - occlusion_penalty)

        # Audio-visual quality (10 points)
        if metrics.speech_correlation > 0:
            score += metrics.speech_correlation * 5
            score += metrics.avg_lip_activity * 5

        # Scene stability (10 points)
        # Fewer scene changes = more stable
        if metrics.scene_changes == 0:
            score += 10
        elif metrics.scene_changes <= 2:
            score += 7
        elif metrics.scene_changes <= 5:
            score += 4
        else:
            score += 2

        return min(100.0, max(0.0, score))
