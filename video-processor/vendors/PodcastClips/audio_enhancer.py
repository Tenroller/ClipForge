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
            video_enhanced = video.with_audio(enhanced_audio)

            # Determine output path
            if output_path is None:
                output_path = video_path

            # Get source FPS to preserve during re-encoding (prevent video freezing)
            source_fps = getattr(video, 'fps', 30)

            # Detect and correct doubled FPS (common MoviePy bug with frame functions)
            # Only halve if FPS matches common doubled patterns (59.94->29.97, 60->30, 50->25, 48->24)
            # Don't halve legitimate high-FPS content (120fps, 144fps, etc.)
            common_doubled_fps = [59.94, 60, 50, 48]
            if any(abs(source_fps - doubled) < 0.1 for doubled in common_doubled_fps):
                original_fps = source_fps
                source_fps = source_fps / 2
                logger.warning(f"Detected doubled FPS in enhance_video_audio, correcting: {original_fps} -> {source_fps}")

            logger.debug(f"Re-encoding with preserved FPS: {source_fps}")

            # Calculate keyframe interval for stable playback
            keyframe_interval = int(source_fps)

            # Write video with enhanced audio
            video_enhanced.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                fps=source_fps,  # Preserve source FPS to prevent freezing
                temp_audiofile='temp-audio-enhanced.m4a',
                remove_temp=True,
                logger=None,
                ffmpeg_params=[
                    '-g', str(keyframe_interval),
                    '-keyint_min', str(keyframe_interval),
                    '-sc_threshold', '0'
                ]
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
        Uses FFmpeg for audio replacement to avoid video re-encoding issues.

        Args:
            video_path: Input video path
            output_path: Output path (optional)

        Returns:
            Path to normalized video
        """
        import subprocess
        import tempfile
        import shutil

        try:
            logger.info(f"Quick normalizing audio for {Path(video_path).name}")

            # Determine output path
            if output_path is None:
                output_path = video_path

            # Create temporary files for audio processing
            temp_dir = tempfile.mkdtemp(prefix="audio_norm_")
            temp_audio_extract = Path(temp_dir) / "extracted_audio.wav"
            temp_audio_normalized = Path(temp_dir) / "normalized_audio.wav"
            temp_video_output = Path(temp_dir) / "output_video.mp4"

            try:
                # Step 1: Extract audio using FFmpeg
                logger.debug("Extracting audio with FFmpeg")
                extract_cmd = [
                    'ffmpeg', '-i', video_path,
                    '-vn',  # No video
                    '-acodec', 'pcm_s16le',  # PCM audio for processing
                    '-ar', '44100',  # Standard sample rate
                    '-ac', '2',  # Stereo
                    '-y',  # Overwrite
                    str(temp_audio_extract)
                ]

                result = subprocess.run(extract_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"FFmpeg audio extraction failed: {result.stderr}")
                    # Video might not have audio or audio is corrupted
                    logger.info("Video has no valid audio track, skipping normalization")
                    return video_path

                # Step 2: Load and normalize audio with MoviePy
                logger.debug("Loading and normalizing audio")
                audio_clip = AudioFileClip(str(temp_audio_extract))
                audio_array = audio_clip.to_soundarray(fps=audio_clip.fps)
                sample_rate = audio_clip.fps

                # Normalize audio
                normalized = self._normalize_audio(audio_array, target_loudness=-14.0)
                normalized = self._limit_peaks(normalized)

                # Step 3: Write normalized audio back to file
                logger.debug("Writing normalized audio")
                from moviepy.audio.AudioClip import AudioArrayClip
                normalized_audio = AudioArrayClip(normalized, fps=sample_rate)
                normalized_audio.write_audiofile(
                    str(temp_audio_normalized),
                    fps=sample_rate,
                    codec='pcm_s16le',
                    logger=None
                )

                # Clean up audio clips
                audio_clip.close()
                normalized_audio.close()

                # Step 4: Merge normalized audio with original video using FFmpeg
                # Use -c:v copy to avoid re-encoding video (preserves original quality and avoids freezing)
                logger.debug("Merging normalized audio with video (no video re-encoding)")
                merge_cmd = [
                    'ffmpeg', '-i', video_path,  # Input video
                    '-i', str(temp_audio_normalized),  # Input normalized audio
                    '-map', '0:v:0',  # Take video from first input
                    '-map', '1:a:0',  # Take audio from second input
                    '-c:v', 'copy',  # Copy video stream without re-encoding (KEY FIX)
                    '-c:a', 'aac',  # Encode audio as AAC
                    '-b:a', '192k',  # Audio bitrate
                    '-shortest',  # Match shortest stream duration
                    '-y',  # Overwrite
                    str(temp_video_output)
                ]

                result = subprocess.run(merge_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"FFmpeg merge failed: {result.stderr}")

                # Step 5: Replace original file with processed file
                shutil.move(str(temp_video_output), output_path)

                logger.info(f"Quick normalization complete using FFmpeg (no video re-encoding)")

                return output_path

            finally:
                # Clean up temporary directory
                try:
                    shutil.rmtree(temp_dir)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temp dir: {cleanup_error}")

        except Exception as e:
            logger.error(f"Quick normalization failed: {e}", exc_info=True)
            # Return original path on failure
            return video_path
