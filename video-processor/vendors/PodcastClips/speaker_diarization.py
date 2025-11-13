"""
Speaker diarization for podcast clips.

Uses pyannote-audio to identify who is speaking when, enabling
better moment detection by providing speaker context to the AI.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import os

from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.speaker_diarization")

# Check if pyannote is available
try:
    from pyannote.audio import Pipeline
    import torch
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False
    logger.warning("pyannote-audio not available. Speaker diarization will be disabled. Install: pip install pyannote-audio")


@dataclass
class SpeakerSegment:
    """Represents a time segment with speaker label."""
    start_time: float
    end_time: float
    speaker: str  # e.g., "SPEAKER_00", "SPEAKER_01"

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self.end_time - self.start_time

    def contains_time(self, time: float) -> bool:
        """Check if a given time falls within this segment."""
        return self.start_time <= time <= self.end_time

    def overlaps_with(self, start: float, end: float) -> bool:
        """Check if this segment overlaps with a time range."""
        return not (self.end_time < start or self.start_time > end)


class SpeakerDiarizer:
    """
    Speaker diarization using pyannote-audio.

    Identifies "who speaks when" in audio to provide better context
    for AI moment detection and scoring.
    """

    def __init__(
        self,
        hf_token: Optional[str] = None,
        use_auth_token: bool = True,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        use_gpu: bool = True
    ):
        """
        Initialize speaker diarizer.

        Args:
            hf_token: HuggingFace token for pyannote model access.
                     If None, will try to read from HF_TOKEN env var.
            use_auth_token: Whether to use authentication token (legacy parameter)
            min_speakers: Minimum number of speakers (None = auto-detect)
            max_speakers: Maximum number of speakers (None = auto-detect)
            use_gpu: Whether to use GPU acceleration if available
        """
        if not PYANNOTE_AVAILABLE:
            raise ImportError(
                "pyannote-audio is required for speaker diarization.\n"
                "Install with: pip install pyannote-audio\n"
                "Then get a HuggingFace token from: https://huggingface.co/settings/tokens"
            )

        # Get HuggingFace token
        self.hf_token = hf_token or os.getenv('HF_TOKEN') or os.getenv('HUGGINGFACE_TOKEN')
        if not self.hf_token and use_auth_token:
            logger.warning(
                "No HuggingFace token provided. Set HF_TOKEN env var or pass hf_token parameter.\n"
                "Get token from: https://huggingface.co/settings/tokens"
            )

        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.use_gpu = use_gpu
        self.pipeline = None

        logger.info("Speaker diarizer initialized")

    def _load_pipeline(self):
        """Lazy-load the pyannote pipeline."""
        if self.pipeline is not None:
            return

        logger.info("Loading pyannote speaker diarization pipeline...")

        try:
            # Load the pre-trained pipeline
            # Use 'token' parameter for newer pyannote versions, fallback to 'use_auth_token' for older versions
            try:
                self.pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    token=self.hf_token if self.hf_token else True
                )
            except TypeError:
                # Fallback for older pyannote versions
                self.pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=self.hf_token if self.hf_token else True
                )

            # Move to GPU if requested and available
            if self.use_gpu and torch.cuda.is_available():
                self.pipeline = self.pipeline.to(torch.device("cuda"))
                logger.info("✓ Using GPU for speaker diarization")
            else:
                logger.info("Using CPU for speaker diarization")

            logger.info("✓ Pyannote pipeline loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load pyannote pipeline: {e}")
            raise RuntimeError(
                f"Could not load pyannote-audio pipeline: {e}\n"
                "Make sure you have:\n"
                "1. Installed pyannote-audio: pip install pyannote-audio\n"
                "2. Accepted model conditions at: https://huggingface.co/pyannote/speaker-diarization-3.1\n"
                "3. Set HF_TOKEN environment variable with your HuggingFace token"
            )

    def diarize(
        self,
        audio_path: str,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> List[SpeakerSegment]:
        """
        Perform speaker diarization on an audio file.

        Args:
            audio_path: Path to audio file
            min_speakers: Override minimum number of speakers
            max_speakers: Override maximum number of speakers

        Returns:
            List of SpeakerSegment objects with timing and labels
        """
        self._load_pipeline()

        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Running speaker diarization on: {audio_path}")

        # Use provided values or fall back to instance values
        min_spk = min_speakers if min_speakers is not None else self.min_speakers
        max_spk = max_speakers if max_speakers is not None else self.max_speakers

        # Run diarization
        try:
            diarization_params = {}
            if min_spk is not None:
                diarization_params['min_speakers'] = min_spk
            if max_spk is not None:
                diarization_params['max_speakers'] = max_spk

            diarization = self.pipeline(audio_path, **diarization_params)

        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            raise RuntimeError(f"Speaker diarization failed: {e}")

        # Convert pyannote output to SpeakerSegment objects
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(SpeakerSegment(
                start_time=turn.start,
                end_time=turn.end,
                speaker=speaker
            ))

        # Get speaker statistics
        speakers = set(seg.speaker for seg in segments)
        total_duration = sum(seg.duration for seg in segments)

        logger.info(
            f"✓ Diarization complete: {len(segments)} segments, "
            f"{len(speakers)} speakers detected, "
            f"{total_duration:.1f}s total speech"
        )

        # Log speaker breakdown
        for speaker in sorted(speakers):
            speaker_segments = [s for s in segments if s.speaker == speaker]
            speaker_duration = sum(s.duration for s in speaker_segments)
            speaker_pct = (speaker_duration / total_duration * 100) if total_duration > 0 else 0
            logger.info(
                f"  {speaker}: {len(speaker_segments)} segments, "
                f"{speaker_duration:.1f}s ({speaker_pct:.1f}%)"
            )

        return segments

    def get_speaker_at_time(
        self,
        segments: List[SpeakerSegment],
        time: float
    ) -> Optional[str]:
        """
        Get the speaker label at a specific time.

        Args:
            segments: List of speaker segments
            time: Time in seconds

        Returns:
            Speaker label or None if no speaker at that time
        """
        for segment in segments:
            if segment.contains_time(time):
                return segment.speaker
        return None

    def get_speakers_in_range(
        self,
        segments: List[SpeakerSegment],
        start_time: float,
        end_time: float
    ) -> List[Tuple[str, float]]:
        """
        Get all speakers active in a time range with their speaking duration.

        Args:
            segments: List of speaker segments
            start_time: Range start in seconds
            end_time: Range end in seconds

        Returns:
            List of (speaker, duration) tuples sorted by duration descending
        """
        speaker_durations = {}

        for segment in segments:
            if segment.overlaps_with(start_time, end_time):
                # Calculate overlap duration
                overlap_start = max(segment.start_time, start_time)
                overlap_end = min(segment.end_time, end_time)
                overlap_duration = overlap_end - overlap_start

                speaker = segment.speaker
                speaker_durations[speaker] = speaker_durations.get(speaker, 0) + overlap_duration

        # Sort by duration descending
        return sorted(speaker_durations.items(), key=lambda x: x[1], reverse=True)

    def annotate_word_timings(
        self,
        word_timings: List[Dict[str, Any]],
        segments: List[SpeakerSegment]
    ) -> List[Dict[str, Any]]:
        """
        Add speaker labels to word timing data.

        Args:
            word_timings: List of word dicts with 'start_time', 'end_time', 'word'
            segments: List of speaker segments from diarization

        Returns:
            Annotated word timings with 'speaker' field added
        """
        logger.info(f"Annotating {len(word_timings)} words with speaker labels")

        annotated = []
        for word in word_timings:
            word_copy = word.copy()

            # Get speaker at word's midpoint
            word_time = (word.get('start_time', 0) + word.get('end_time', 0)) / 2
            speaker = self.get_speaker_at_time(segments, word_time)

            word_copy['speaker'] = speaker or "UNKNOWN"
            annotated.append(word_copy)

        # Log speaker word counts
        speaker_counts = {}
        for word in annotated:
            speaker = word.get('speaker', 'UNKNOWN')
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1

        logger.info("Speaker word distribution:")
        for speaker, count in sorted(speaker_counts.items()):
            pct = (count / len(annotated) * 100) if annotated else 0
            logger.info(f"  {speaker}: {count} words ({pct:.1f}%)")

        return annotated

    def count_speaker_changes(
        self,
        segments: List[SpeakerSegment],
        start_time: float,
        end_time: float
    ) -> int:
        """
        Count number of speaker changes in a time range.

        Args:
            segments: List of speaker segments
            start_time: Range start in seconds
            end_time: Range end in seconds

        Returns:
            Number of speaker transitions in the range
        """
        relevant_segments = [
            s for s in segments
            if s.overlaps_with(start_time, end_time)
        ]

        if len(relevant_segments) <= 1:
            return 0

        # Sort by start time
        relevant_segments.sort(key=lambda s: s.start_time)

        # Count changes
        changes = 0
        prev_speaker = relevant_segments[0].speaker
        for segment in relevant_segments[1:]:
            if segment.speaker != prev_speaker:
                changes += 1
                prev_speaker = segment.speaker

        return changes

    def identify_main_speaker(
        self,
        segments: List[SpeakerSegment]
    ) -> Tuple[str, float]:
        """
        Identify the main speaker (most speaking time).

        Args:
            segments: List of speaker segments

        Returns:
            Tuple of (speaker_label, percentage_of_total_time)
        """
        if not segments:
            return ("UNKNOWN", 0.0)

        # Calculate total speaking time per speaker
        speaker_times = {}
        for segment in segments:
            speaker = segment.speaker
            speaker_times[speaker] = speaker_times.get(speaker, 0) + segment.duration

        # Find speaker with most time
        total_time = sum(speaker_times.values())
        main_speaker = max(speaker_times.items(), key=lambda x: x[1])

        percentage = (main_speaker[1] / total_time * 100) if total_time > 0 else 0

        logger.info(f"Main speaker: {main_speaker[0]} ({percentage:.1f}% of speaking time)")

        return main_speaker[0], percentage

    def get_speaker_statistics(
        self,
        segments: List[SpeakerSegment]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed statistics for each speaker.

        Args:
            segments: List of speaker segments

        Returns:
            Dict mapping speaker to statistics:
            {
                "SPEAKER_00": {
                    "total_time": 45.3,
                    "segment_count": 12,
                    "percentage": 65.2,
                    "avg_segment_duration": 3.78,
                    "role": "main" | "secondary" | "minor"
                }
            }
        """
        if not segments:
            return {}

        # Calculate per-speaker stats
        speaker_stats = {}
        total_time = sum(s.duration for s in segments)

        for speaker in set(s.speaker for s in segments):
            speaker_segments = [s for s in segments if s.speaker == speaker]
            speaker_time = sum(s.duration for s in speaker_segments)
            percentage = (speaker_time / total_time * 100) if total_time > 0 else 0

            # Determine role
            if percentage >= 50:
                role = "main"
            elif percentage >= 20:
                role = "secondary"
            else:
                role = "minor"

            speaker_stats[speaker] = {
                "total_time": speaker_time,
                "segment_count": len(speaker_segments),
                "percentage": percentage,
                "avg_segment_duration": speaker_time / len(speaker_segments) if speaker_segments else 0,
                "role": role
            }

        return speaker_stats

    def detect_interaction_patterns(
        self,
        segments: List[SpeakerSegment],
        start_time: float,
        end_time: float
    ) -> Dict[str, Any]:
        """
        Detect speaker interaction patterns in a time range.

        Args:
            segments: List of speaker segments
            start_time: Range start in seconds
            end_time: Range end in seconds

        Returns:
            Dict with interaction analysis:
            {
                "has_exchange": bool,  # Multiple speakers present
                "speaker_changes": int,
                "dominant_speaker": str,  # Speaker with most time
                "speakers_present": List[str],
                "interaction_type": "monologue" | "dialogue" | "multi-party",
                "avg_turn_duration": float
            }
        """
        relevant_segments = [
            s for s in segments
            if s.overlaps_with(start_time, end_time)
        ]

        if not relevant_segments:
            return {
                "has_exchange": False,
                "speaker_changes": 0,
                "dominant_speaker": None,
                "speakers_present": [],
                "interaction_type": "monologue",
                "avg_turn_duration": 0.0
            }

        # Get speakers in range with durations
        speakers_in_range = self.get_speakers_in_range(segments, start_time, end_time)
        speaker_changes = self.count_speaker_changes(segments, start_time, end_time)

        # Determine interaction type
        num_speakers = len(speakers_in_range)
        if num_speakers == 1:
            interaction_type = "monologue"
        elif num_speakers == 2:
            interaction_type = "dialogue"
        else:
            interaction_type = "multi-party"

        # Calculate average turn duration
        avg_turn = sum(s.duration for s in relevant_segments) / len(relevant_segments)

        return {
            "has_exchange": num_speakers > 1,
            "speaker_changes": speaker_changes,
            "dominant_speaker": speakers_in_range[0][0] if speakers_in_range else None,
            "speakers_present": [s[0] for s in speakers_in_range],
            "interaction_type": interaction_type,
            "avg_turn_duration": avg_turn
        }

    def filter_moments_by_speaker(
        self,
        moments: List[Dict[str, Any]],
        segments: List[SpeakerSegment],
        target_speaker: Optional[str] = None,
        min_speaker_percentage: float = 0.0,
        require_exchange: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Filter moments based on speaker criteria.

        Args:
            moments: List of moment dicts with 'start_time', 'end_time'
            segments: List of speaker segments
            target_speaker: Specific speaker to focus on (None = any)
            min_speaker_percentage: Minimum % of time target speaker must speak
            require_exchange: Whether moment must have multiple speakers

        Returns:
            Filtered list of moments meeting speaker criteria
        """
        filtered = []

        for moment in moments:
            start = moment.get('start_time', 0)
            end = moment.get('end_time', 0)

            # Get speakers in this moment
            speakers_in_moment = self.get_speakers_in_range(segments, start, end)

            if not speakers_in_moment:
                continue

            # Check exchange requirement
            if require_exchange and len(speakers_in_moment) < 2:
                continue

            # Check target speaker
            if target_speaker:
                # Find target speaker's duration
                target_duration = next(
                    (duration for speaker, duration in speakers_in_moment if speaker == target_speaker),
                    0.0
                )
                total_duration = sum(d for _, d in speakers_in_moment)
                percentage = (target_duration / total_duration * 100) if total_duration > 0 else 0

                if percentage < min_speaker_percentage:
                    continue

            filtered.append(moment)

        logger.info(f"Filtered {len(moments)} moments → {len(filtered)} meeting speaker criteria")
        return filtered


def is_speaker_diarization_available() -> bool:
    """Check if speaker diarization is available."""
    return PYANNOTE_AVAILABLE
