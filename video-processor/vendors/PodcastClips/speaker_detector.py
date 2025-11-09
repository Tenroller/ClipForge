"""
Speaker Detection Module for PodcastClips

Uses audio analysis (librosa + optionally WebRTC VAD) to detect speech activity
and correlate it with video timestamps to identify who is speaking.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np

try:
    import librosa
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logging.warning("librosa not available - speaker detection disabled")

try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    logging.info("webrtcvad not available - using librosa-only speech detection")


@dataclass
class AudioSegment:
    """Represents a segment of audio with speech activity"""
    start_time: float  # Start time in seconds
    end_time: float  # End time in seconds
    energy: float  # Average energy level during this segment
    confidence: float  # Confidence that this segment contains speech (0-1)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def contains_time(self, time: float) -> bool:
        """Check if a given time falls within this segment"""
        return self.start_time <= time <= self.end_time


class SpeakerDetector:
    """
    Detects speech activity in audio using energy-based analysis.

    This class analyzes audio to identify when someone is speaking,
    which can then be correlated with face positions to determine
    which person in a video is the active speaker.
    """

    def __init__(
        self,
        energy_threshold: Optional[float] = None,
        min_speech_duration: float = 0.3,
        frame_duration: float = 0.02,  # 20ms frames
        use_vad: bool = True,
        vad_aggressiveness: int = 2,  # 0-3, higher = more aggressive filtering
    ):
        """
        Initialize speaker detector.

        Args:
            energy_threshold: RMS energy threshold for speech detection.
                             If None, will be auto-calibrated from audio.
            min_speech_duration: Minimum duration (seconds) for a speech segment
            frame_duration: Duration of each analysis frame in seconds
            use_vad: Whether to use WebRTC VAD if available (more accurate)
            vad_aggressiveness: VAD aggressiveness mode (0-3)
        """
        if not LIBROSA_AVAILABLE:
            raise ImportError("librosa is required for speaker detection. Install: pip install librosa")

        self.energy_threshold = energy_threshold
        self.min_speech_duration = min_speech_duration
        self.frame_duration = frame_duration
        self.use_vad = use_vad and VAD_AVAILABLE
        self.vad_aggressiveness = vad_aggressiveness
        self.logger = logging.getLogger(__name__)

        if self.use_vad:
            self.vad = webrtcvad.Vad(vad_aggressiveness)
            self.logger.info(f"Using WebRTC VAD with aggressiveness {vad_aggressiveness}")
        else:
            self.vad = None
            self.logger.info("Using librosa energy-based speech detection")

    def detect_speech_segments(
        self,
        audio_path: str,
        sr: Optional[int] = None
    ) -> List[AudioSegment]:
        """
        Detect speech segments in an audio file.

        Args:
            audio_path: Path to audio file
            sr: Target sample rate (if None, uses native rate)

        Returns:
            List of AudioSegment objects representing detected speech
        """
        self.logger.info(f"Analyzing audio for speech segments: {audio_path}")

        # Load audio
        y, sample_rate = librosa.load(audio_path, sr=sr)

        if self.use_vad:
            segments = self._detect_with_vad(y, sample_rate)
        else:
            segments = self._detect_with_energy(y, sample_rate)

        # Filter out very short segments
        filtered_segments = [
            seg for seg in segments
            if seg.duration >= self.min_speech_duration
        ]

        self.logger.info(
            f"Detected {len(filtered_segments)} speech segments "
            f"(filtered from {len(segments)} raw detections)"
        )

        return filtered_segments

    def _detect_with_energy(
        self,
        y: np.ndarray,
        sr: int
    ) -> List[AudioSegment]:
        """
        Detect speech using RMS energy and onset detection.

        Args:
            y: Audio time series
            sr: Sample rate

        Returns:
            List of detected speech segments
        """
        # Compute frame-level RMS energy
        hop_length = int(sr * self.frame_duration)
        rms = librosa.feature.rms(y=y, frame_length=hop_length*2, hop_length=hop_length)[0]

        # Auto-calibrate threshold if not set
        if self.energy_threshold is None:
            # Use median + 1.5 * IQR as threshold (robust to outliers)
            q1, q3 = np.percentile(rms, [25, 75])
            iqr = q3 - q1
            threshold = np.median(rms) + 1.5 * iqr
            self.logger.debug(f"Auto-calibrated energy threshold: {threshold:.4f}")
        else:
            threshold = self.energy_threshold

        # Detect onset events (start of speech)
        onset_frames = librosa.onset.onset_detect(
            y=y,
            sr=sr,
            hop_length=hop_length,
            backtrack=True,
            units='frames'
        )

        # Create binary speech mask
        speech_mask = rms > threshold

        # Convert frames to time
        frame_times = librosa.frames_to_time(
            np.arange(len(rms)),
            sr=sr,
            hop_length=hop_length
        )

        # Find continuous speech segments
        segments = []
        in_speech = False
        start_time = 0.0
        accumulated_energy = 0.0
        frame_count = 0

        for i, (time, is_speech) in enumerate(zip(frame_times, speech_mask)):
            if is_speech and not in_speech:
                # Start of speech segment
                in_speech = True
                start_time = time
                accumulated_energy = rms[i]
                frame_count = 1
            elif is_speech and in_speech:
                # Continue speech segment
                accumulated_energy += rms[i]
                frame_count += 1
            elif not is_speech and in_speech:
                # End of speech segment
                in_speech = False
                avg_energy = accumulated_energy / frame_count if frame_count > 0 else 0

                # Confidence based on energy level and proximity to onsets
                confidence = self._calculate_confidence(
                    avg_energy, threshold, start_time, time, onset_frames, frame_times
                )

                segments.append(AudioSegment(
                    start_time=start_time,
                    end_time=time,
                    energy=float(avg_energy),
                    confidence=confidence
                ))

        # Handle case where audio ends during speech
        if in_speech:
            avg_energy = accumulated_energy / frame_count if frame_count > 0 else 0
            confidence = self._calculate_confidence(
                avg_energy, threshold, start_time, frame_times[-1], onset_frames, frame_times
            )
            segments.append(AudioSegment(
                start_time=start_time,
                end_time=frame_times[-1],
                energy=float(avg_energy),
                confidence=confidence
            ))

        return segments

    def _detect_with_vad(
        self,
        y: np.ndarray,
        sr: int
    ) -> List[AudioSegment]:
        """
        Detect speech using WebRTC VAD.

        Args:
            y: Audio time series
            sr: Sample rate

        Returns:
            List of detected speech segments
        """
        # WebRTC VAD requires 16kHz, 16-bit PCM
        target_sr = 16000
        if sr != target_sr:
            y_resampled = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
        else:
            y_resampled = y

        # Convert to 16-bit PCM
        audio_int16 = (y_resampled * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()

        # WebRTC VAD works on 10, 20, or 30ms frames
        # We'll use 30ms for better accuracy
        frame_duration_ms = 30
        frame_size = int(target_sr * frame_duration_ms / 1000)
        frame_size_bytes = frame_size * 2  # 2 bytes per sample (int16)

        segments = []
        in_speech = False
        start_time = 0.0
        current_time = 0.0

        # Also compute RMS for energy values
        hop_length = int(target_sr * frame_duration_ms / 1000)
        rms = librosa.feature.rms(y=y_resampled, hop_length=hop_length)[0]

        # Process audio in frames
        for i in range(0, len(audio_bytes) - frame_size_bytes, frame_size_bytes):
            frame = audio_bytes[i:i + frame_size_bytes]
            current_time = i / (target_sr * 2)  # 2 bytes per sample

            is_speech = self.vad.is_speech(frame, target_sr)

            if is_speech and not in_speech:
                # Start of speech
                in_speech = True
                start_time = current_time
            elif not is_speech and in_speech:
                # End of speech
                in_speech = False

                # Calculate energy for this segment
                start_frame = int(start_time * target_sr / hop_length)
                end_frame = int(current_time * target_sr / hop_length)
                segment_energy = np.mean(rms[start_frame:end_frame]) if end_frame > start_frame else 0.0

                segments.append(AudioSegment(
                    start_time=start_time,
                    end_time=current_time,
                    energy=float(segment_energy),
                    confidence=0.9  # VAD is quite reliable
                ))

        # Handle case where audio ends during speech
        if in_speech:
            end_time = len(audio_bytes) / (target_sr * 2)
            start_frame = int(start_time * target_sr / hop_length)
            end_frame = int(end_time * target_sr / hop_length)
            segment_energy = np.mean(rms[start_frame:end_frame]) if end_frame > start_frame else 0.0

            segments.append(AudioSegment(
                start_time=start_time,
                end_time=end_time,
                energy=float(segment_energy),
                confidence=0.9
            ))

        return segments

    def _calculate_confidence(
        self,
        energy: float,
        threshold: float,
        start_time: float,
        end_time: float,
        onset_frames: np.ndarray,
        frame_times: np.ndarray
    ) -> float:
        """
        Calculate confidence score for a speech segment.

        Args:
            energy: Average energy of the segment
            threshold: Energy threshold
            start_time: Segment start time
            end_time: Segment end time
            onset_frames: Frame indices of detected onsets
            frame_times: Time values for each frame

        Returns:
            Confidence score between 0 and 1
        """
        # Base confidence from energy level
        energy_confidence = min(energy / (threshold * 2), 1.0)

        # Boost confidence if segment contains an onset event
        onset_times = frame_times[onset_frames] if len(onset_frames) > 0 else np.array([])
        has_onset = np.any((onset_times >= start_time) & (onset_times <= end_time))
        onset_boost = 0.2 if has_onset else 0.0

        confidence = min(energy_confidence + onset_boost, 1.0)
        return float(confidence)

    def is_speech_at_time(
        self,
        time: float,
        segments: List[AudioSegment],
        min_confidence: float = 0.5
    ) -> Tuple[bool, float]:
        """
        Check if there is speech activity at a given time.

        Args:
            time: Time to check (in seconds)
            segments: List of detected speech segments
            min_confidence: Minimum confidence threshold

        Returns:
            Tuple of (is_speech, energy) where is_speech is True if
            speech is detected at the given time
        """
        for segment in segments:
            if segment.contains_time(time) and segment.confidence >= min_confidence:
                return True, segment.energy

        return False, 0.0

    def get_speech_energy_at_time(
        self,
        time: float,
        segments: List[AudioSegment]
    ) -> float:
        """
        Get the speech energy level at a specific time.

        Args:
            time: Time to check (in seconds)
            segments: List of detected speech segments

        Returns:
            Energy level (0.0 if no speech detected)
        """
        for segment in segments:
            if segment.contains_time(time):
                return segment.energy
        return 0.0
