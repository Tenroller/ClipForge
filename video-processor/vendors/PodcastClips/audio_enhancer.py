"""
Audio enhancement module for podcast clips.

Provides normalization, noise reduction, and audio quality improvements.
"""

import logging
from pathlib import Path
from typing import Optional
from moviepy import AudioFileClip, VideoFileClip
import numpy as np

logger = logging.getLogger(__name__)


class AudioEnhancer:
    """
    Audio enhancement for podcast clips.

    Features:
    - Volume normalization
    - Dynamic range compression
    - Basic noise gate
    - Peak limiting
    """

    def __init__(self):
        """Initialize audio enhancer."""
        pass

    def enhance_video_audio(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        target_loudness: float = -14.0,  # LUFS (standard for social media)
        compression_ratio: float = 3.0,
        noise_gate_threshold: float = -40.0  # dB
    ) -> str:
        """
        Enhance audio in video file.

        Args:
            video_path: Path to input video
            output_path: Path for output (default: overwrites input)
            target_loudness: Target loudness in LUFS (-14 is standard)
            compression_ratio: Dynamic range compression ratio
            noise_gate_threshold: Noise gate threshold in dB

        Returns:
            Path to enhanced video
        """
        try:
            logger.info(f"Enhancing audio for {Path(video_path).name}")

            # Load video
            video = VideoFileClip(video_path)

            if video.audio is None:
                logger.warning("Video has no audio track, skipping enhancement")
                return video_path

            # Extract audio
            audio = video.audio

            # Get audio as numpy array
            audio_array = audio.to_soundarray(fps=audio.fps)

            # Enhance audio
            enhanced_array = self._enhance_audio_array(
                audio_array,
                sample_rate=audio.fps,
                target_loudness=target_loudness,
                compression_ratio=compression_ratio,
                noise_gate_threshold=noise_gate_threshold
            )

            # Create new audio clip from enhanced array
            from moviepy.audio.AudioClip import AudioArrayClip
            enhanced_audio = AudioArrayClip(enhanced_array, fps=audio.fps)

            # Set enhanced audio to video
            video_enhanced = video.set_audio(enhanced_audio)

            # Determine output path
            if output_path is None:
                output_path = video_path

            # Write video with enhanced audio
            video_enhanced.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio-enhanced.m4a',
                remove_temp=True,
                logger=None
            )

            # Clean up
            video.close()
            video_enhanced.close()

            logger.info(f"Audio enhancement complete: {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"Audio enhancement failed: {e}", exc_info=True)
            # Return original path if enhancement fails
            return video_path

    def _enhance_audio_array(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        target_loudness: float,
        compression_ratio: float,
        noise_gate_threshold: float
    ) -> np.ndarray:
        """
        Enhance audio array with normalization and compression.

        Args:
            audio_array: Audio data as numpy array (shape: [samples, channels])
            sample_rate: Sample rate in Hz
            target_loudness: Target loudness (approximate, in LUFS-like units)
            compression_ratio: Compression ratio for dynamics
            noise_gate_threshold: Threshold for noise gate (linear, 0-1)

        Returns:
            Enhanced audio array
        """
        # Work with a copy
        enhanced = audio_array.copy()

        # Handle mono/stereo
        if len(enhanced.shape) == 1:
            enhanced = enhanced.reshape(-1, 1)

        # 1. Noise Gate (simple threshold-based)
        enhanced = self._apply_noise_gate(enhanced, noise_gate_threshold)

        # 2. Normalize (RMS-based)
        enhanced = self._normalize_audio(enhanced, target_loudness)

        # 3. Compression (simple soft-knee compressor)
        enhanced = self._compress_dynamics(enhanced, compression_ratio)

        # 4. Peak Limiting (prevent clipping)
        enhanced = self._limit_peaks(enhanced)

        return enhanced

    def _apply_noise_gate(self, audio: np.ndarray, threshold_db: float) -> np.ndarray:
        """
        Apply simple noise gate to reduce background noise.

        Args:
            audio: Audio array
            threshold_db: Threshold in dB below which audio is attenuated

        Returns:
            Gated audio
        """
        # Convert dB to linear
        threshold_linear = 10 ** (threshold_db / 20)

        # Calculate envelope (RMS over small windows)
        window_size = 1024
        envelope = np.array([
            np.sqrt(np.mean(audio[max(0, i-window_size):i+window_size]**2))
            for i in range(len(audio))
        ])

        # Create gate mask (smooth transitions)
        gate = np.where(envelope > threshold_linear, 1.0, 0.1)  # 0.1 = -20dB attenuation

        # Apply gate
        if len(audio.shape) == 2:
            gate = gate.reshape(-1, 1)

        return audio * gate

    def _normalize_audio(self, audio: np.ndarray, target_loudness: float) -> np.ndarray:
        """
        Normalize audio to target loudness (RMS-based approximation).

        Args:
            audio: Audio array
            target_loudness: Target loudness in LUFS-like units

        Returns:
            Normalized audio
        """
        # Calculate RMS
        rms = np.sqrt(np.mean(audio ** 2))

        if rms == 0:
            return audio

        # Convert target LUFS to approximate linear scale
        # LUFS ≈ -23 dB for reference level, we map to 0-1 scale
        target_rms = 10 ** ((target_loudness + 23) / 20) * 0.3  # Approximate mapping

        # Calculate gain
        gain = target_rms / rms

        # Limit gain to prevent excessive amplification
        gain = min(gain, 4.0)  # Max +12dB boost

        return audio * gain

    def _compress_dynamics(self, audio: np.ndarray, ratio: float) -> np.ndarray:
        """
        Apply dynamic range compression (simple soft-knee compressor).

        Args:
            audio: Audio array
            ratio: Compression ratio (e.g., 3.0 = 3:1)

        Returns:
            Compressed audio
        """
        threshold = 0.3  # Compression threshold (linear, ~-10dB)
        knee_width = 0.1  # Soft knee width

        def compress_sample(x):
            """Compress a single sample using soft-knee compression."""
            abs_x = abs(x)

            if abs_x < threshold - knee_width / 2:
                # Below threshold - no compression
                return x
            elif abs_x > threshold + knee_width / 2:
                # Above threshold - full compression
                compressed = threshold + (abs_x - threshold) / ratio
                return np.sign(x) * compressed
            else:
                # In knee region - gradual compression
                knee_factor = (abs_x - (threshold - knee_width / 2)) / knee_width
                compressed = abs_x + knee_factor * (threshold + (abs_x - threshold) / ratio - abs_x)
                return np.sign(x) * compressed

        # Vectorize compression function
        compress_vec = np.vectorize(compress_sample)

        return compress_vec(audio)

    def _limit_peaks(self, audio: np.ndarray, ceiling: float = 0.95) -> np.ndarray:
        """
        Apply peak limiting to prevent clipping.

        Args:
            audio: Audio array
            ceiling: Maximum peak level (0-1)

        Returns:
            Limited audio
        """
        # Find peak
        peak = np.max(np.abs(audio))

        if peak > ceiling:
            # Apply brick-wall limiting with soft transition
            gain = ceiling / peak
            # Smooth the gain to avoid harsh limiting artifacts
            audio = audio * gain * 0.99  # Slight headroom

        return np.clip(audio, -1.0, 1.0)

    def quick_normalize(self, video_path: str, output_path: Optional[str] = None) -> str:
        """
        Quick audio normalization without full enhancement.

        Faster than full enhancement - just normalizes volume.

        Args:
            video_path: Input video path
            output_path: Output path (optional)

        Returns:
            Path to normalized video
        """
        try:
            logger.info(f"Quick normalizing audio for {Path(video_path).name}")

            # Load video
            video = VideoFileClip(video_path)

            if video.audio is None:
                return video_path

            # Simple volume normalization
            audio = video.audio
            audio_array = audio.to_soundarray(fps=audio.fps)

            # Normalize to -14 LUFS equivalent
            normalized = self._normalize_audio(audio_array, sample_rate=audio.fps, target_loudness=-14.0)
            normalized = self._limit_peaks(normalized)

            # Create new audio
            from moviepy.audio.AudioClip import AudioArrayClip
            normalized_audio = AudioArrayClip(normalized, fps=audio.fps)

            # Set to video
            video_normalized = video.set_audio(normalized_audio)

            # Write
            if output_path is None:
                output_path = video_path

            video_normalized.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio-normalized.m4a',
                remove_temp=True,
                logger=None
            )

            video.close()
            video_normalized.close()

            logger.info(f"Quick normalization complete")

            return output_path

        except Exception as e:
            logger.error(f"Quick normalization failed: {e}")
            return video_path
