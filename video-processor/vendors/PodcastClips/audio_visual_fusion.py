"""
Audio-visual fusion module for improved speaker detection.

Combines audio energy analysis with lip movement detection to determine
who is speaking with higher accuracy than audio or visual alone.
"""

import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from scipy import signal
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.audio_visual_fusion")


@dataclass
class AudioVisualCorrelation:
    """Audio-visual synchronization score."""
    correlation: float  # Cross-correlation coefficient (-1 to 1)
    lag: float         # Temporal lag in seconds (positive = audio leads)
    confidence: float  # Confidence in correlation (0-1)
    is_synchronized: bool  # Whether audio and visual are in sync


class AudioVisualFusion:
    """
    Audio-visual fusion for speaker detection.

    Combines:
    1. Audio energy envelope
    2. Lip movement patterns
    3. Cross-correlation analysis

    To determine who is speaking with high confidence.
    """

    def __init__(
        self,
        sync_threshold: float = 0.3,
        max_lag_ms: float = 200.0,
        window_size_sec: float = 0.5
    ):
        """
        Initialize audio-visual fusion engine.

        Args:
            sync_threshold: Minimum correlation for "synchronized" (0-1)
                          - 0.2: Very permissive
                          - 0.3: Balanced (recommended)
                          - 0.5: Strict
            max_lag_ms: Maximum audio-visual lag to check (milliseconds)
                       Typical lip-sync lag: 0-150ms
            window_size_sec: Window size for correlation analysis
        """
        self.sync_threshold = sync_threshold
        self.max_lag_ms = max_lag_ms
        self.window_size_sec = window_size_sec

    def compute_audio_envelope(
        self,
        audio_samples: np.ndarray,
        sample_rate: int,
        smoothing_window_ms: float = 50.0
    ) -> np.ndarray:
        """
        Compute audio energy envelope.

        Args:
            audio_samples: Audio waveform
            sample_rate: Audio sample rate (Hz)
            smoothing_window_ms: Smoothing window size (milliseconds)

        Returns:
            Smoothed energy envelope
        """
        # Compute short-time energy
        frame_length = int(smoothing_window_ms * sample_rate / 1000.0)
        energy = np.array([
            np.sum(audio_samples[i:i+frame_length]**2)
            for i in range(0, len(audio_samples) - frame_length, frame_length // 2)
        ])

        # Normalize to [0, 1]
        if len(energy) > 0 and np.max(energy) > 0:
            energy = energy / np.max(energy)

        return energy

    def compute_lip_movement_envelope(
        self,
        lip_scores: List[float],
        timestamps: List[float],
        target_rate: float = 20.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert discrete lip movement scores to continuous envelope.

        Args:
            lip_scores: List of lip movement scores (0-1)
            timestamps: Corresponding timestamps
            target_rate: Target sampling rate (Hz) for envelope

        Returns:
            (envelope, time_axis) tuple
        """
        if len(lip_scores) == 0:
            return np.array([]), np.array([])

        # Create continuous timeline
        t_start = timestamps[0]
        t_end = timestamps[-1]
        duration = t_end - t_start

        if duration <= 0:
            return np.array([lip_scores[0]]), np.array([t_start])

        # Resample to uniform rate
        num_samples = int(duration * target_rate)
        time_axis = np.linspace(t_start, t_end, num_samples)

        # Interpolate lip scores
        from scipy.interpolate import interp1d

        if len(lip_scores) > 1:
            interpolator = interp1d(
                timestamps,
                lip_scores,
                kind='linear',
                bounds_error=False,
                fill_value=0.0
            )
            envelope = interpolator(time_axis)
        else:
            envelope = np.full(num_samples, lip_scores[0])

        return envelope, time_axis

    def compute_cross_correlation(
        self,
        audio_envelope: np.ndarray,
        lip_envelope: np.ndarray,
        sample_rate: float
    ) -> AudioVisualCorrelation:
        """
        Compute cross-correlation between audio and lip movement.

        Args:
            audio_envelope: Audio energy envelope
            lip_envelope: Lip movement envelope
            sample_rate: Envelope sample rate (Hz)

        Returns:
            AudioVisualCorrelation object
        """
        if len(audio_envelope) == 0 or len(lip_envelope) == 0:
            return AudioVisualCorrelation(
                correlation=0.0,
                lag=0.0,
                confidence=0.0,
                is_synchronized=False
            )

        # Ensure same length (trim to shorter)
        min_len = min(len(audio_envelope), len(lip_envelope))
        audio_envelope = audio_envelope[:min_len]
        lip_envelope = lip_envelope[:min_len]

        # Compute cross-correlation
        max_lag_samples = int(self.max_lag_ms * sample_rate / 1000.0)

        # Use correlate with 'same' mode for centered correlation
        correlation = signal.correlate(
            audio_envelope - np.mean(audio_envelope),
            lip_envelope - np.mean(lip_envelope),
            mode='same'
        )

        # Normalize correlation
        audio_std = np.std(audio_envelope)
        lip_std = np.std(lip_envelope)

        if audio_std > 0 and lip_std > 0:
            correlation = correlation / (len(audio_envelope) * audio_std * lip_std)
        else:
            correlation = np.zeros_like(correlation)

        # Find peak correlation within max lag
        center = len(correlation) // 2
        search_start = max(0, center - max_lag_samples)
        search_end = min(len(correlation), center + max_lag_samples + 1)

        search_region = correlation[search_start:search_end]
        peak_idx = np.argmax(np.abs(search_region))
        peak_correlation = search_region[peak_idx]

        # Calculate lag in seconds
        lag_samples = (search_start + peak_idx) - center
        lag_seconds = lag_samples / sample_rate

        # Calculate confidence based on peak sharpness
        # Sharp peak = high confidence, flat correlation = low confidence
        correlation_std = np.std(search_region)
        peak_sharpness = abs(peak_correlation) / (correlation_std + 1e-6)
        confidence = min(1.0, peak_sharpness / 3.0)  # Normalize

        # Determine if synchronized
        is_synchronized = (
            abs(peak_correlation) > self.sync_threshold and
            abs(lag_seconds) < (self.max_lag_ms / 1000.0)
        )

        return AudioVisualCorrelation(
            correlation=float(peak_correlation),
            lag=float(lag_seconds),
            confidence=float(confidence),
            is_synchronized=is_synchronized
        )

    def analyze_lip_sync(
        self,
        audio_samples: np.ndarray,
        audio_sample_rate: int,
        lip_scores: List[float],
        lip_timestamps: List[float],
        start_time: float = 0.0
    ) -> AudioVisualCorrelation:
        """
        Analyze lip-sync correlation between audio and visual.

        Args:
            audio_samples: Audio waveform
            audio_sample_rate: Audio sample rate (Hz)
            lip_scores: List of lip movement scores
            lip_timestamps: Timestamps for lip scores
            start_time: Start time offset for alignment

        Returns:
            AudioVisualCorrelation result
        """
        try:
            # Compute audio envelope
            audio_envelope = self.compute_audio_envelope(
                audio_samples,
                audio_sample_rate
            )

            # Compute lip movement envelope
            target_rate = 20.0  # 20Hz for both signals
            lip_envelope, lip_time_axis = self.compute_lip_movement_envelope(
                lip_scores,
                lip_timestamps,
                target_rate
            )

            # Resample audio envelope to match lip envelope rate
            if len(audio_envelope) > 0:
                from scipy.interpolate import interp1d

                # Create time axis for audio envelope
                audio_duration = len(audio_samples) / audio_sample_rate
                audio_time_axis = np.linspace(
                    start_time,
                    start_time + audio_duration,
                    len(audio_envelope)
                )

                # Resample to target rate
                if len(audio_time_axis) > 1:
                    audio_interpolator = interp1d(
                        audio_time_axis,
                        audio_envelope,
                        kind='linear',
                        bounds_error=False,
                        fill_value=0.0
                    )

                    # Resample to match lip timeline
                    if len(lip_time_axis) > 0:
                        audio_envelope_resampled = audio_interpolator(lip_time_axis)
                    else:
                        audio_envelope_resampled = np.array([])
                else:
                    audio_envelope_resampled = audio_envelope
            else:
                audio_envelope_resampled = np.array([])

            # Compute cross-correlation
            correlation = self.compute_cross_correlation(
                audio_envelope_resampled,
                lip_envelope,
                target_rate
            )

            logger.debug(
                f"Lip-sync analysis: correlation={correlation.correlation:.3f}, "
                f"lag={correlation.lag*1000:.1f}ms, "
                f"confidence={correlation.confidence:.3f}, "
                f"synchronized={correlation.is_synchronized}"
            )

            return correlation

        except Exception as e:
            logger.error(f"Failed to analyze lip-sync: {e}")
            return AudioVisualCorrelation(
                correlation=0.0,
                lag=0.0,
                confidence=0.0,
                is_synchronized=False
            )

    def compute_speaker_score(
        self,
        audio_energy: float,
        lip_movement: float,
        av_correlation: Optional[AudioVisualCorrelation] = None,
        face_size_ratio: float = 0.1
    ) -> float:
        """
        Compute composite speaker score for a face.

        Combines multiple cues:
        - Audio energy at this time
        - Lip movement score
        - Audio-visual correlation (if available)
        - Face size (larger = more likely to be speaking)

        Args:
            audio_energy: Current audio energy (0-1)
            lip_movement: Current lip movement score (0-1)
            av_correlation: Audio-visual correlation result (optional)
            face_size_ratio: Face size as ratio of frame (0-1)

        Returns:
            Speaker score (0-1)
        """
        # Base weights
        audio_weight = 0.3
        lip_weight = 0.4
        size_weight = 0.1
        sync_weight = 0.2

        # Compute base score
        score = (
            audio_energy * audio_weight +
            lip_movement * lip_weight +
            face_size_ratio * size_weight
        )

        # Add synchronization bonus if available
        if av_correlation is not None and av_correlation.is_synchronized:
            sync_bonus = abs(av_correlation.correlation) * av_correlation.confidence
            score += sync_bonus * sync_weight

        # Clamp to [0, 1]
        return min(1.0, max(0.0, score))

    def detect_active_speaker_window(
        self,
        audio_samples: np.ndarray,
        audio_sample_rate: int,
        face_lip_data: Dict[int, Tuple[List[float], List[float]]],
        window_start: float,
        window_duration: float
    ) -> Optional[int]:
        """
        Detect which face is speaking in a time window.

        Args:
            audio_samples: Audio waveform for the window
            audio_sample_rate: Audio sample rate
            face_lip_data: Dict mapping face_id -> (lip_scores, timestamps)
            window_start: Window start time
            window_duration: Window duration

        Returns:
            face_id of active speaker, or None
        """
        if len(face_lip_data) == 0:
            return None

        # Analyze each face
        face_scores = {}

        for face_id, (lip_scores, timestamps) in face_lip_data.items():
            # Filter lip data to window
            window_end = window_start + window_duration
            windowed_lips = [
                (score, ts) for score, ts in zip(lip_scores, timestamps)
                if window_start <= ts <= window_end
            ]

            if not windowed_lips:
                face_scores[face_id] = 0.0
                continue

            lip_scores_window = [s for s, _ in windowed_lips]
            timestamps_window = [ts for _, ts in windowed_lips]

            # Compute audio-visual correlation for this face
            correlation = self.analyze_lip_sync(
                audio_samples,
                audio_sample_rate,
                lip_scores_window,
                timestamps_window,
                window_start
            )

            # Compute speaker score
            avg_lip_movement = np.mean(lip_scores_window)
            audio_energy = np.mean(np.abs(audio_samples))

            score = self.compute_speaker_score(
                audio_energy,
                avg_lip_movement,
                correlation
            )

            face_scores[face_id] = score

        # Return face with highest score
        if face_scores:
            best_face_id = max(face_scores.keys(), key=lambda fid: face_scores[fid])
            best_score = face_scores[best_face_id]

            if best_score > 0.3:  # Minimum threshold
                logger.debug(
                    f"Active speaker in window [{window_start:.1f}s-{window_start+window_duration:.1f}s]: "
                    f"face {best_face_id} (score: {best_score:.3f})"
                )
                return best_face_id

        return None
