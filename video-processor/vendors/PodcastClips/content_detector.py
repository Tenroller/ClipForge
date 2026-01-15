"""
Content mode detection module for identifying horizontal content segments.

Detects when video shows content (screen recordings, articles, images) instead of faces,
and determines when to switch between face-tracking vertical mode and horizontal content mode.
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from loguru import logger as loguru_logger

try:
    import pytesseract
    # Configure tesseract executable path for Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    loguru_logger.warning("pytesseract not available - OCR-based content detection disabled")

from .face_tracker import FaceBox, FaceTracker

logger = loguru_logger.bind(name="PodcastClips.content_detector")

# Interview/Conversation Detection Constants
INTERVIEW_MIN_FACE_SIZE = 0.04  # 4% of frame (larger than audience)
INTERVIEW_MAX_FACE_SIZE = 0.25  # 25% of frame (smaller than close-ups)
INTERVIEW_DIALOGUE_CONFIDENCE = 0.7  # 70% confidence for dialogue
INTERVIEW_FACE_CONSISTENCY_WINDOW = 2.0  # 2 seconds consistency check


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
        progress_callback: Optional[Callable] = None
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
        progress_callback: Optional[Callable] = None
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
        # Store video dimensions for interview detection
        self.video_width = video_width
        self.video_height = video_height

        # INTERVIEW DETECTION VIA SPEAKER MAPPING
        # If we have exactly 2 speakers mapped to 2 different face tracks,
        # this is definitively an interview - use SPLIT_SCREEN for the entire video
        self.is_confirmed_interview = False
        if (self.face_tracker and
            hasattr(self.face_tracker, 'speaker_to_face_map') and
            self.face_tracker.speaker_to_face_map):

            num_speakers = len(self.face_tracker.speaker_to_face_map)
            unique_face_tracks = len(set(self.face_tracker.speaker_to_face_map.values()))

            if num_speakers == 2 and unique_face_tracks == 2:
                self.is_confirmed_interview = True
                logger.info(
                    f"🎯 INTERVIEW CONFIRMED via speaker mapping: "
                    f"{num_speakers} speakers → {unique_face_tracks} face tracks"
                )
                for speaker, face_id in self.face_tracker.speaker_to_face_map.items():
                    logger.info(f"  {speaker} → Face Track {face_id}")
            elif num_speakers >= 3:
                logger.info(
                    f"🎯 GROUP/PANEL detected via speaker mapping: "
                    f"{num_speakers} speakers → HORIZONTAL mode"
                )

        if not content_scores and not face_positions:
            # No data at all - but if confirmed interview, use SPLIT_SCREEN
            if self.is_confirmed_interview:
                return [ContentSegment(start_time, end_time, ContentMode.SPLIT_SCREEN, 0.9)]
            return [ContentSegment(start_time, end_time, ContentMode.HORIZONTAL, 0.5)]

        segments = []
        # Start with SPLIT_SCREEN if confirmed interview, otherwise FACE
        current_mode = ContentMode.SPLIT_SCREEN if self.is_confirmed_interview else ContentMode.FACE
        segment_start = start_time

        # Get all timestamps and sort
        all_timestamps = sorted(set(list(content_scores.keys()) + list(face_positions.keys())))
        all_timestamps = [ts for ts in all_timestamps if start_time <= ts <= end_time]

        if not all_timestamps:
            if self.is_confirmed_interview:
                return [ContentSegment(start_time, end_time, ContentMode.SPLIT_SCREEN, 0.9)]
            return [ContentSegment(start_time, end_time, ContentMode.FACE, 0.5)]

        # Thresholds for content detection
        HIGH_CONTENT_THRESHOLD = 0.6  # Strong content indicator
        LOW_CONTENT_THRESHOLD = 0.3   # Weak content indicator
        SMALL_FACE_THRESHOLD = 0.12   # Face area ratio threshold (reduced from 0.20 to only detect true PiP, not normal podcasts)

        for i, timestamp in enumerate(all_timestamps):
            # PRIORITY -2: CONFIRMED INTERVIEW (from speaker mapping)
            # If we confirmed this is a 2-person interview, check if BOTH faces are visible
            # Only use SPLIT_SCREEN when both people are in frame, otherwise use FACE mode
            if self.is_confirmed_interview:
                # Check if both interview faces are visible at this timestamp
                interview_faces = None
                if hasattr(self.face_tracker, 'get_interview_faces_from_speaker_mapping'):
                    interview_faces = self.face_tracker.get_interview_faces_from_speaker_mapping(
                        timestamp, persistence_window=2.0
                    )

                if interview_faces and len(interview_faces) == 2:
                    # Both faces visible → SPLIT_SCREEN
                    target_mode = ContentMode.SPLIT_SCREEN
                else:
                    # Only 1 face or no faces → FACE mode (zoom on active speaker)
                    target_mode = ContentMode.FACE

                if target_mode != current_mode:
                    if timestamp > segment_start:
                        confidence = 0.90 if target_mode == ContentMode.SPLIT_SCREEN else 0.80
                        segments.append(ContentSegment(
                            segment_start, timestamp, current_mode, confidence
                        ))
                    segment_start = timestamp
                    current_mode = target_mode
                continue  # Skip other checks for confirmed interviews

            # Get content score and face info for this timestamp
            content_score = content_scores.get(timestamp, 0.0)

            # TWO-TIER face detection check:
            # 1. ACTUAL detection (tight tolerance) - for wide shot detection
            # 2. PERSISTED detection (loose tolerance) - for continuity
            
            current_frame_has_actual_detection = False
            current_frame_has_faces = False
            detected_face = None
            
            if self.face_tracker:
                # Check 1: ACTUAL detection in current frame (1.0s tolerance)
                # This is used for wide shot detection - we want to know if faces are 
                # REALLY detected right now, not just persisted from earlier
                # Tolerance increased from 0.5s to 1.0s to handle profile faces and detection gaps
                # (face detection can fail briefly when speaker looks down or sideways)
                ACTUAL_DETECTION_TOLERANCE = 1.0  # ~30 frames at 30fps
                if self.face_tracker.face_tracks:
                    current_frame_has_actual_detection = any(
                        any(abs(ts - timestamp) <= ACTUAL_DETECTION_TOLERANCE for ts in track.positions.keys())
                        for track in self.face_tracker.face_tracks
                    )
                
                # Check 2: PERSISTED detection (uses face tracker's persistence logic)
                # This is used for continuity - to maintain stable tracking even during brief occlusions
                if hasattr(self.face_tracker, 'get_active_speaker_at_time'):
                    detected_face = self.face_tracker.get_active_speaker_at_time(timestamp)
                
                # Fallback to largest face if no active speaker
                if not detected_face and hasattr(self.face_tracker, 'get_face_position_at_time'):
                    detected_face = self.face_tracker.get_face_position_at_time(timestamp)
                
                current_frame_has_faces = detected_face is not None
                
                # DEBUG: Log for troubleshooting
                if 76.0 <= timestamp <= 77.0:  # Frame 3540 area (wide shot)
                    logger.info(
                        f"🔍 DEBUG [{timestamp:.2f}s]: "
                        f"actual_detection={current_frame_has_actual_detection}, "
                        f"has_faces_w_persistence={current_frame_has_faces}, "
                        f"detected_face={detected_face.face_id if detected_face else None}"
                    )
                    if self.face_tracker.face_tracks:
                        for track in self.face_tracker.face_tracks[:3]:
                            nearby_timestamps = sorted([ts for ts in track.positions.keys() 
                                                       if abs(ts - timestamp) < 1.0])[:5]
                            logger.info(
                                f"  Track {track.face_id}: nearby_times={[f'{t:.2f}' for t in nearby_timestamps]}"
                            )

            # Use face tracker's persistence method if available for better wide shot handling
            if self.face_tracker and hasattr(self.face_tracker, 'get_face_position_with_persistence'):
                face_box = self.face_tracker.get_face_position_with_persistence(timestamp, persistence_window=2.0)
            else:
                face_box = face_positions.get(timestamp)

            # Quality filtering: Only use HIGH QUALITY faces for mode decisions
            # This prevents small background false positives from blocking horizontal mode
            MIN_QUALITY_FOR_MODE = 0.35  # Face must be reasonably sized, confident, and centered
            face_is_high_quality = False
            face_area_ratio = 0.0
            
            if face_box:
                face_area_ratio = face_box.area / (video_width * video_height)
                quality = face_box.quality_score(video_width, video_height)
                face_is_high_quality = quality >= MIN_QUALITY_FOR_MODE
                
                if not face_is_high_quality:
                    logger.debug(
                        f"[{timestamp:.1f}s] Ignoring low-quality face "
                        f"(quality={quality:.2f}, size={face_area_ratio*100:.1f}%) for mode decision"
                    )
                    # Treat as if no face detected for mode purposes
                    face_box_for_mode = None
                else:
                    face_box_for_mode = face_box
            else:
                face_box_for_mode = None

            # Determine mode based on content-first logic, with split-screen detection
            should_be_horizontal = False
            should_be_split_screen = False

            # PRIORITY -1: Check diarization - if someone is speaking, check for split-screen first
            # This is the highest priority check because diarization KNOWS who is talking
            diarization_speaker = None
            if (self.face_tracker and
                hasattr(self.face_tracker, 'diarization_segments') and
                self.face_tracker.diarization_segments and
                hasattr(self.face_tracker, 'speaker_to_face_map') and
                self.face_tracker.speaker_to_face_map):
                diarization_speaker = self.face_tracker.get_speaker_at_time(timestamp)
                if diarization_speaker:
                    # PHASE 1: Wide shot detection with diarization
                    # If someone is speaking but NO FACES ACTUALLY DETECTED,
                    # this is likely a wide audience shot → use horizontal mode
                    # Use ACTUAL detection, not persistence
                    if not current_frame_has_actual_detection:
                        # Speech active but no actual face detection → wide shot
                        should_be_horizontal = True
                        logger.info(
                            f"[{timestamp:.1f}s] 🎯 WIDE SHOT (diarization): "
                            f"{diarization_speaker} speaking but no actual detection → HORIZONTAL"
                        )
                        target_mode = ContentMode.HORIZONTAL
                    else:
                        # PHASE 2: Check for SPLIT-SCREEN before defaulting to FACE
                        # If two separated faces are detected, use split-screen mode
                        face_group_info = self.face_tracker.detect_face_groups(timestamp)
                        if (face_group_info["mode"] == "separated" and
                            len(face_group_info["faces"]) >= 2):
                            should_be_split_screen = True
                            logger.info(
                                f"[{timestamp:.1f}s] 🎯 SPLIT-SCREEN (diarization): "
                                f"{diarization_speaker} speaking with 2 separated faces "
                                f"(separation={face_group_info['separation_score']:.2f}) → SPLIT_SCREEN"
                            )
                            target_mode = ContentMode.SPLIT_SCREEN
                        else:
                            # Normal case: speaker detected with visible face
                            should_be_horizontal = False
                            face_id = self.face_tracker.speaker_to_face_map.get(diarization_speaker, "?")
                            logger.debug(
                                f"[{timestamp:.1f}s] Diarization override: {diarization_speaker} -> Face {face_id} → FACE"
                            )
                            target_mode = ContentMode.FACE

                    # Check if mode changed
                    if target_mode != current_mode:
                        if timestamp > segment_start:
                            confidence = self._calculate_segment_confidence(
                                content_scores, segment_start, timestamp
                            )
                            segments.append(ContentSegment(
                                segment_start, timestamp, current_mode, confidence
                            ))
                        segment_start = timestamp
                        current_mode = target_mode
                    continue  # Skip to next timestamp

            # PRIORITY -0.75: INTERVIEW/CONVERSATION DETECTION
            # If 2 medium-sized faces are detected in a dialogue pattern,
            # use SPLIT_SCREEN mode to show both speakers (9:16 vertical with stacked view)
            if self.face_tracker and hasattr(self.face_tracker, 'detect_face_groups'):
                face_group_info = self.face_tracker.detect_face_groups(timestamp)

                # Get interaction pattern if diarization available
                interaction_pattern = None
                if (self.face_tracker and
                    hasattr(self.face_tracker, 'diarization_segments') and
                    self.face_tracker.diarization_segments):
                    # Get interaction pattern for current segment
                    segment_start_check = max(0, timestamp - 2.0)
                    segment_end_check = timestamp + 2.0

                    if hasattr(self.face_tracker, 'diarizer') and self.face_tracker.diarizer:
                        interaction_pattern = self.face_tracker.diarizer.detect_interaction_patterns(
                            self.face_tracker.diarization_segments,
                            segment_start_check,
                            segment_end_check
                        )

                # Check if this is an interview scenario
                is_interview = self._is_interview_scenario(
                    timestamp,
                    face_group_info,
                    interaction_pattern
                )

                if is_interview:
                    # Interview mode: Use SPLIT_SCREEN mode to show both speakers
                    # This creates a 9:16 vertical layout with both people visible
                    should_be_horizontal = False
                    should_be_split_screen = True

                    logger.info(
                        f"[{timestamp:.1f}s] INTERVIEW MODE: "
                        f"2 people conversation → SPLIT_SCREEN (show both speakers)"
                    )

                    target_mode = ContentMode.SPLIT_SCREEN

                    # Check if mode changed
                    if target_mode != current_mode:
                        if timestamp > segment_start:
                            confidence = self._calculate_segment_confidence(
                                content_scores, segment_start, timestamp
                            )
                            segments.append(ContentSegment(
                                segment_start, timestamp, current_mode, confidence
                            ))
                        segment_start = timestamp
                        current_mode = target_mode
                    continue  # Skip to next timestamp

            # PRIORITY -0.6: GROUP/PANEL DETECTION (3+ people)
            # Distinguish between:
            # - True panel (many similarly-sized faces) → HORIZONTAL
            # - 2 speakers + audience (2 large faces + small background) → SPLIT_SCREEN
            if self.face_tracker and hasattr(self.face_tracker, 'detect_face_groups'):
                face_group_info = self.face_tracker.detect_face_groups(timestamp)
                faces = face_group_info.get("faces", [])
                num_faces = len(faces)

                if num_faces >= 3:
                    # Check if there are 2 DOMINANT faces (main speakers) vs small faces (audience)
                    # Sort by area (already sorted in detect_face_groups)
                    face_areas = [f.area / (video_width * video_height) for f in faces]
                    
                    # Check if top 2 faces are significantly larger than the rest
                    top_2_avg = sum(face_areas[:2]) / 2 if len(face_areas) >= 2 else 0
                    rest_avg = sum(face_areas[2:]) / len(face_areas[2:]) if len(face_areas) > 2 else 0
                    
                    # If top 2 faces are at least 2x larger than remaining faces on average,
                    # this is likely "2 speakers + audience" → use SPLIT_SCREEN
                    # Also check that top 2 are reasonably sized (>2% of frame each)
                    MIN_SPEAKER_SIZE = 0.02  # 2% of frame
                    DOMINANCE_RATIO = 2.0  # Top 2 must be 2x larger than rest
                    
                    has_dominant_speakers = (
                        len(face_areas) >= 2 and
                        face_areas[0] >= MIN_SPEAKER_SIZE and
                        face_areas[1] >= MIN_SPEAKER_SIZE and
                        (rest_avg == 0 or top_2_avg / rest_avg >= DOMINANCE_RATIO)
                    )
                    
                    if has_dominant_speakers:
                        # 2 main speakers + background audience → SPLIT_SCREEN
                        should_be_horizontal = False
                        should_be_split_screen = True
                        
                        logger.info(
                            f"[{timestamp:.1f}s] 2 SPEAKERS + AUDIENCE: "
                            f"top2_avg={top_2_avg*100:.1f}%, rest_avg={rest_avg*100:.1f}% "
                            f"→ SPLIT_SCREEN"
                        )
                        target_mode = ContentMode.SPLIT_SCREEN
                    else:
                        # True panel/group scenario: Use HORIZONTAL mode
                        should_be_horizontal = True
                        should_be_split_screen = False

                        logger.info(
                            f"[{timestamp:.1f}s] GROUP MODE: "
                            f"{num_faces} similarly-sized faces → HORIZONTAL (panel)"
                        )
                        target_mode = ContentMode.HORIZONTAL

                    # Check if mode changed
                    if target_mode != current_mode:
                        if timestamp > segment_start:
                            confidence = self._calculate_segment_confidence(
                                content_scores, segment_start, timestamp
                            )
                            segments.append(ContentSegment(
                                segment_start, timestamp, current_mode, confidence
                            ))
                        segment_start = timestamp
                        current_mode = target_mode
                    continue  # Skip to next timestamp

            # PRIORITY -0.5: Wide shot detection - no faces actually detected
            # If there are NO faces ACTUALLY DETECTED in the current frame,
            # check if this is truly a wide audience shot or just a temporary
            # detection gap in an interview scenario
            if not current_frame_has_actual_detection:
                # NEW: First check if we have 2+ faces from any source (including YOLO)
                # This is more reliable than layout analysis for detecting interviews
                # with profile faces that the primary detector missed
                yolo_detected_interview = False
                
                # Log face_tracker status once per video at first timestamp
                if timestamp == start_time:
                    has_tracker = self.face_tracker is not None
                    has_method = hasattr(self.face_tracker, 'get_faces_at_time') if has_tracker else False
                    num_tracks = len(self.face_tracker.face_tracks) if (has_tracker and self.face_tracker.face_tracks) else 0
                    logger.info(
                        f"[Content Detector] Face tracker status: "
                        f"has_tracker={has_tracker}, has_method={has_method}, "
                        f"num_tracks={num_tracks}"
                    )
                
                if (self.face_tracker and 
                    hasattr(self.face_tracker, 'get_faces_at_time')):
                    faces_at_time = self.face_tracker.get_faces_at_time(timestamp, tolerance=1.0)
                    num_tracks = len(self.face_tracker.face_tracks) if self.face_tracker.face_tracks else 0
                    
                    # Log every 10 seconds to avoid spam but still get diagnostics
                    if int(timestamp) % 10 == 0:
                        logger.info(
                            f"[{timestamp:.1f}s] Track check: "
                            f"tracks={num_tracks}, faces_at_time={len(faces_at_time)}"
                        )
                    
                    # Also check if we have exactly 2 tracks globally (interview scenario)
                    # This works even if we can't find faces at this specific timestamp
                    if len(faces_at_time) >= 2:
                        yolo_detected_interview = True
                        logger.info(
                            f"[{timestamp:.1f}s] 🎯 YOLO/face backup: {len(faces_at_time)} subjects "
                            f"detected in tracks → SPLIT_SCREEN"
                        )
                        should_be_horizontal = False
                        should_be_split_screen = True
                        target_mode = ContentMode.SPLIT_SCREEN
                        
                        # Check if mode changed
                        if target_mode != current_mode:
                            if timestamp > segment_start:
                                confidence = self._calculate_segment_confidence(
                                    content_scores, segment_start, timestamp
                                )
                                segments.append(ContentSegment(
                                    segment_start, timestamp, current_mode, confidence
                                ))
                            segment_start = timestamp
                            current_mode = target_mode
                        continue  # Skip to next timestamp
                    elif num_tracks >= 2:
                        # Fallback: We have 2+ tracks globally, likely an interview
                        # This handles cases where timestamps don't align perfectly
                        # or when YOLO creates 3 tracks for 2-3 visible people
                        yolo_detected_interview = True
                        logger.info(
                            f"[{timestamp:.1f}s] 🎯 GLOBAL interview: {num_tracks} face tracks detected "
                            f"(no faces at exact timestamp) → SPLIT_SCREEN"
                        )
                        should_be_horizontal = False
                        should_be_split_screen = True
                        target_mode = ContentMode.SPLIT_SCREEN
                        
                        if target_mode != current_mode:
                            if timestamp > segment_start:
                                confidence = self._calculate_segment_confidence(
                                    content_scores, segment_start, timestamp
                                )
                                segments.append(ContentSegment(
                                    segment_start, timestamp, current_mode, confidence
                                ))
                            segment_start = timestamp
                            current_mode = target_mode
                        continue
                
                # Analyze scene layout from historical face tracking data
                scene_layout = self._analyze_scene_layout_from_tracks(timestamp, window_seconds=5.0)
                
                if scene_layout["layout_type"] == "interview":
                    # This is likely a brief detection gap in an interview
                    # Use SPLIT_SCREEN mode to maintain continuity with both speakers
                    should_be_horizontal = False
                    should_be_split_screen = True
                    logger.info(
                        f"[{timestamp:.1f}s] 🎯 INTERVIEW DETECTED (no current detection): "
                        f"historical layout={scene_layout['layout_type']}, "
                        f"dominant_count={scene_layout['dominant_face_count']}, "
                        f"confidence={scene_layout['confidence']:.2f} → SPLIT_SCREEN"
                    )
                    target_mode = ContentMode.SPLIT_SCREEN
                elif scene_layout["layout_type"] in ("single", "talking_head"):
                    # Single person or talking head video - maintain FACE mode during detection gap
                    should_be_horizontal = False
                    logger.info(
                        f"[{timestamp:.1f}s] 🎯 TALKING HEAD DETECTED (no current detection): "
                        f"historical layout={scene_layout['layout_type']}, "
                        f"avg_size={scene_layout['avg_face_size']:.2%}, "
                        f"confidence={scene_layout['confidence']:.2f} → FACE MODE"
                    )
                    target_mode = ContentMode.FACE
                else:
                    # Audience/unknown layout → wide shot, use horizontal mode
                    should_be_horizontal = True
                    logger.info(
                        f"[{timestamp:.1f}s] 🎯 WIDE SHOT DETECTED: "
                        f"layout={scene_layout['layout_type']}, "
                        f"actual_detection=False → HORIZONTAL MODE"
                    )
                    logger.debug(
                        f"  Face tracks: {len(self.face_tracker.face_tracks) if self.face_tracker else 0}, "
                        f"Has persisted face: {current_frame_has_faces}"
                    )
                    target_mode = ContentMode.HORIZONTAL
                
                # Check if mode changed
                if target_mode != current_mode:
                    if timestamp > segment_start:
                        confidence = self._calculate_segment_confidence(
                            content_scores, segment_start, timestamp
                        )
                        segments.append(ContentSegment(
                            segment_start, timestamp, current_mode, confidence
                        ))
                    segment_start = timestamp
                    current_mode = target_mode
                continue  # Skip to next timestamp
            else:
                # Faces exist - log for debugging
                logger.debug(
                    f"[{timestamp:.1f}s] Faces present in current frame, "
                    f"not triggering wide shot detection"
                )


            # PRIORITY 0: Check for extreme content (overrides everything)
            if content_score > 0.7:
                # Extreme content signal → horizontal mode (definitely real content)
                should_be_horizontal = True
                logger.debug(f"[{timestamp:.1f}s] Extreme content score: {content_score:.2f} → HORIZONTAL")

            # PRIORITY 1: Large HIGH-QUALITY face presence override (prevents false positives)
            elif face_box_for_mode and face_area_ratio > 0.15:
                # Large high-quality face present → default to FACE mode
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
                if face_box_for_mode:
                    # High-quality face present → face mode
                    should_be_horizontal = False
                    logger.debug(f"[{timestamp:.1f}s] Low content ({content_score:.2f}) + face → FACE")
                else:
                    # No high-quality face, low content → check speech activity
                    # If speech is active, someone is talking - prefer face mode
                    is_speech_active = False
                    if (self.face_tracker and
                        hasattr(self.face_tracker, 'speaker_detector') and
                        self.face_tracker.speaker_detector and
                        self.face_tracker.speech_segments):
                        is_speech, energy = self.face_tracker.speaker_detector.is_speech_at_time(
                            timestamp, self.face_tracker.speech_segments, min_confidence=0.3
                        )
                        is_speech_active = is_speech and energy > 5.0

                    if is_speech_active:
                        # Speech active → prefer face mode even without detected face
                        should_be_horizontal = False
                        logger.debug(f"[{timestamp:.1f}s] Low content, no face but speech active → FACE")
                    else:
                        # No face, no speech, low content → maintain current mode
                        should_be_horizontal = current_mode == ContentMode.HORIZONTAL
                        logger.debug(f"[{timestamp:.1f}s] Low content, no face, no speech → maintain {current_mode.value}")

            else:
                # Medium content score (0.3-0.7) → check face size
                if face_box_for_mode:
                    if face_area_ratio < SMALL_FACE_THRESHOLD:
                        # Small face + medium content → horizontal mode (likely PiP)
                        should_be_horizontal = True
                        logger.debug(f"[{timestamp:.1f}s] Medium content ({content_score:.2f}) + small face ({face_area_ratio*100:.1f}%) → HORIZONTAL")
                    else:
                        # Large face + medium content → face mode
                        should_be_horizontal = False
                        logger.debug(f"[{timestamp:.1f}s] Medium content ({content_score:.2f}) + large face ({face_area_ratio*100:.1f}%) → FACE")
                else:
                    # No face, medium content → check speech activity before deciding
                    # If speech is active, someone is probably talking - stay in face mode
                    is_speech_active = False
                    if (self.face_tracker and
                        hasattr(self.face_tracker, 'speaker_detector') and
                        self.face_tracker.speaker_detector and
                        self.face_tracker.speech_segments):
                        is_speech, energy = self.face_tracker.speaker_detector.is_speech_at_time(
                            timestamp, self.face_tracker.speech_segments, min_confidence=0.3
                        )
                        is_speech_active = is_speech and energy > 5.0  # Require some energy

                    if is_speech_active:
                        # Speech active but no face detected → stay in face mode (wide shot scenario)
                        should_be_horizontal = False
                        logger.debug(f"[{timestamp:.1f}s] Medium content ({content_score:.2f}), no face but speech active → FACE")
                    else:
                        # No face, no speech, medium content → horizontal mode
                        should_be_horizontal = True
                        logger.debug(f"[{timestamp:.1f}s] Medium content ({content_score:.2f}), no face, no speech → HORIZONTAL")

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
        avg_score = float(np.mean(scores_in_range))
        std_score = float(np.std(scores_in_range)) if len(scores_in_range) > 1 else 0.0

        # Low standard deviation = consistent signal = high confidence
        consistency_score = 1.0 - min(std_score, 0.3) / 0.3
        confidence = 0.5 + (consistency_score * 0.5)

        return float(min(1.0, max(0.5, confidence)))

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
        progress_callback: Optional[Callable] = None
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

        final_score = float(np.mean(scores))
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
            original_width = frame.shape[1]

            # Validate frame dimensions
            MIN_DIMENSION = 10
            if original_height == 0 or original_width == 0 or original_height < MIN_DIMENSION or original_width < MIN_DIMENSION:
                logger.warning(f"Frame has invalid dimensions for OCR: {frame.shape}. Skipping OCR.")
                return 0.0

            if original_height > self.ocr_height:
                scale_factor = self.ocr_height / original_height
                ocr_width = int(original_width * scale_factor)

                # Ensure minimum dimensions to prevent cv2.resize broadcast errors
                ocr_width = max(MIN_DIMENSION, ocr_width)
                ocr_height_final = max(MIN_DIMENSION, self.ocr_height)

                frame = cv2.resize(
                    frame,
                    (ocr_width, ocr_height_final),
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
            return float((0.3 - mean_saturation) / 0.2)

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
                segment.confidence = float(min(1.0, avg_score + 0.3))
            else:
                segment.confidence = float(min(1.0, (1.0 - avg_score) + 0.3))

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

    def _is_interview_scenario(
        self,
        timestamp: float,
        face_group_info: Dict[str, any],
        interaction_pattern: Optional[Dict[str, any]] = None
    ) -> bool:
        """
        Detect if current timestamp represents an interview/conversation scenario.

        Interview characteristics:
        - Exactly 2 faces detected consistently
        - Faces are medium-sized (not audience, not extreme close-ups)
        - Dialogue interaction pattern (if diarization available)

        NOTE: Both "grouped" and "separated" 2-person setups are considered interviews.
        Both will use SPLIT_SCREEN mode to show both speakers.

        Args:
            timestamp: Current timestamp
            face_group_info: Face grouping information from detect_face_groups()
            interaction_pattern: Diarization interaction pattern (optional)

        Returns:
            True if this is an interview scenario
        """
        # Check 1: Must have exactly 2 faces detected
        if len(face_group_info.get("faces", [])) != 2:
            return False

        # NOTE: We no longer exclude separated faces - both grouped and separated
        # 2-person setups are considered interviews and will use SPLIT_SCREEN

        # Check 3: Both faces must be medium-sized (not tiny audience members)
        faces = face_group_info["faces"]

        # Get video dimensions
        if hasattr(self, 'video_width') and hasattr(self, 'video_height'):
            frame_area = self.video_width * self.video_height
        else:
            # Fallback to common resolution
            frame_area = 1920 * 1080

        for face in faces:
            face_area_ratio = face.area / frame_area
            if face_area_ratio < INTERVIEW_MIN_FACE_SIZE or face_area_ratio > INTERVIEW_MAX_FACE_SIZE:
                # Face is too small (audience) or too large (portrait mode)
                return False

        # Check 4: Check for dialogue interaction pattern (if diarization available)
        if interaction_pattern:
            interaction_type = interaction_pattern.get("interaction_type")
            if interaction_type == "dialogue":
                logger.info(
                    f"[{timestamp:.1f}s] Interview detected: "
                    f"2 medium faces + dialogue pattern"
                )
                return True
            elif interaction_type == "monologue":
                # 2 faces but only 1 speaking → still interview (interviewer + guest)
                logger.info(
                    f"[{timestamp:.1f}s] Interview detected (monologue): "
                    f"2 medium faces, 1 speaker dominant"
                )
                return True

        # Check 5: Verify face consistency over time (prevent false positives)
        # Look at nearby timestamps to ensure 2 faces are consistently detected
        if self.face_tracker:
            consistent_count = 0
            check_window = INTERVIEW_FACE_CONSISTENCY_WINDOW
            check_times = [
                timestamp - check_window,
                timestamp - check_window / 2,
                timestamp,
                timestamp + check_window / 2,
                timestamp + check_window
            ]

            for check_time in check_times:
                check_group = self.face_tracker.detect_face_groups(check_time)
                if len(check_group.get("faces", [])) == 2:
                    consistent_count += 1

            # Require at least 3/5 samples to have 2 faces
            if consistent_count >= 3:
                logger.debug(
                    f"[{timestamp:.1f}s] Interview detected (consistency): "
                    f"{consistent_count}/5 samples have 2 faces"
                )
                return True

        return False

    def _analyze_scene_layout_from_tracks(
        self,
        timestamp: float,
        window_seconds: float = 5.0
    ) -> Dict[str, any]:
        """
        Analyze scene layout from GLOBAL face tracking history.
        
        Uses overall face track statistics to determine if this is an interview
        scenario (2 consistent faces) vs audience shot (many varying faces).
        Now uses GLOBAL track statistics rather than just a local time window.
        
        Args:
            timestamp: Current timestamp (used for logging)
            window_seconds: Not used anymore - kept for compatibility
            
        Returns:
            Dictionary with:
                - layout_type: "interview", "talking_head", "audience", "single", or "unknown"
                - dominant_face_count: Number of face tracks
                - avg_face_size: Average face size as ratio of frame
                - face_size_variance: Variance in face sizes (high = audience)
                - confidence: Confidence in the layout detection (0-1)
        """
        if not self.face_tracker or not self.face_tracker.face_tracks:
            return {
                "layout_type": "unknown",
                "dominant_face_count": 0,
                "avg_face_size": 0.0,
                "face_size_variance": 0.0,
                "confidence": 0.0
            }
        
        # Get frame dimensions
        if hasattr(self, 'video_width') and hasattr(self, 'video_height'):
            frame_area = self.video_width * self.video_height
        else:
            frame_area = 1920 * 1080  # Fallback
        
        # Use GLOBAL track statistics instead of time-window analysis
        # This gives us the overall scene pattern regardless of current detection gaps
        num_tracks = len(self.face_tracker.face_tracks)
        
        # Collect average face size from each track
        track_avg_sizes = []
        track_coverages = []  # What % of video each track covers
        
        total_video_frames = 0
        for track in self.face_tracker.face_tracks:
            if track.positions:
                # Get average size for this track
                sizes = [face.area / frame_area for face in track.positions.values()]
                track_avg_sizes.append(np.mean(sizes))
                
                # Track coverage = # of detections for this track
                track_coverages.append(len(track.positions))
                total_video_frames = max(total_video_frames, len(track.positions))
        
        if not track_avg_sizes:
            return {
                "layout_type": "unknown",
                "dominant_face_count": 0,
                "avg_face_size": 0.0,
                "face_size_variance": 0.0,
                "confidence": 0.0
            }
        
        avg_face_size = float(np.mean(track_avg_sizes))
        face_size_variance = float(np.std(track_avg_sizes)) if len(track_avg_sizes) > 1 else 0.0
        
        # Determine layout type based on GLOBAL track statistics
        layout_type = "unknown"
        confidence = 0.5
        
        # INTERVIEW: Exactly 2 tracks with medium-sized faces
        # OR: Exactly 2 tracks with YOLO-estimated faces (which are smaller but consistent)
        if num_tracks == 2:
            # Standard interview detection (normal-sized faces)
            if (INTERVIEW_MIN_FACE_SIZE <= avg_face_size <= INTERVIEW_MAX_FACE_SIZE and
                face_size_variance < 0.05):
                layout_type = "interview"
                confidence = 0.9
                logger.debug(
                    f"[{timestamp:.1f}s] GLOBAL Interview layout: "
                    f"tracks={num_tracks}, size={avg_face_size:.2%}, "
                    f"variance={face_size_variance:.3f}"
                )
            # NEW: YOLO-estimated interview (smaller faces but consistent 2-person setup)
            # YOLO face estimates are ~18% of body height, resulting in ~1.5-3% face area
            # for seated interview subjects. This is smaller than normal face detection
            # but still valid for interview scenarios.
            elif (avg_face_size >= 0.015 and  # Above tiny audience threshold
                  avg_face_size < INTERVIEW_MIN_FACE_SIZE and  # Below normal interview
                  face_size_variance < 0.03):  # Very consistent sizes (typical of YOLO estimates)
                layout_type = "interview"
                confidence = 0.75  # Lower confidence for YOLO-based detection
                logger.debug(
                    f"[{timestamp:.1f}s] YOLO-estimated interview layout: "
                    f"tracks={num_tracks}, size={avg_face_size:.2%}, "
                    f"variance={face_size_variance:.3f} (YOLO face estimates)"
                )
        
        # TALKING HEAD: 1 track with medium-to-large face
        elif num_tracks == 1:
            if avg_face_size >= INTERVIEW_MIN_FACE_SIZE:
                layout_type = "talking_head"
                confidence = 0.85
                logger.debug(
                    f"[{timestamp:.1f}s] GLOBAL Talking head layout: "
                    f"tracks={num_tracks}, size={avg_face_size:.2%}"
                )
            else:
                # Small single face - could be audience or dynamic scene
                layout_type = "single"
                confidence = 0.6
        
        # AUDIENCE: 3+ tracks OR high size variance OR very small faces
        # Relaxed threshold from 0.03 to 0.015 to account for YOLO face estimates
        # which are inherently smaller than actual face detections
        elif num_tracks >= 3 or face_size_variance > 0.08 or avg_face_size < 0.015:
            layout_type = "audience"
            confidence = 0.7
            logger.debug(
                f"[{timestamp:.1f}s] GLOBAL Audience layout: "
                f"tracks={num_tracks}, size={avg_face_size:.2%}, "
                f"variance={face_size_variance:.3f}"
            )
        
        return {
            "layout_type": layout_type,
            "dominant_face_count": num_tracks,
            "avg_face_size": avg_face_size,
            "face_size_variance": face_size_variance,
            "confidence": confidence
        }

    
    def _get_face_count_history(
        self,
        timestamp: float,
        window_seconds: float = 5.0
    ) -> Dict[str, any]:
        """
        Analyze face detection history to determine consistent scene pattern.
        
        Args:
            timestamp: Current timestamp
            window_seconds: Time window to analyze around current time
            
        Returns:
            - avg_face_count: Average faces detected in window
            - mode_face_count: Most common face count in window
            - consistency: How consistent the face count is (0-1)
        """
        if not self.face_tracker or not self.face_tracker.face_tracks:
            return {
                "avg_face_count": 0.0,
                "mode_face_count": 0,
                "consistency": 0.0
            }
        
        # Sample timestamps within the window
        start_ts = timestamp - window_seconds
        end_ts = timestamp + window_seconds
        
        # Count faces at each sample point (every 0.5 seconds)
        sample_counts = []
        sample_time = start_ts
        while sample_time <= end_ts:
            # Count how many tracks have positions near this sample time
            faces_at_time = 0
            for track in self.face_tracker.face_tracks:
                # Check if track has a position within 0.5s of sample time
                has_position = any(
                    abs(ts - sample_time) <= 0.5 
                    for ts in track.positions.keys()
                )
                if has_position:
                    faces_at_time += 1
            sample_counts.append(faces_at_time)
            sample_time += 0.5
        
        if not sample_counts:
            return {
                "avg_face_count": 0.0,
                "mode_face_count": 0,
                "consistency": 0.0
            }
        
        avg_count = float(np.mean(sample_counts))
        
        # Find mode (most common value)
        from collections import Counter
        count_freq = Counter(sample_counts)
        mode_count = count_freq.most_common(1)[0][0]
        mode_frequency = count_freq.most_common(1)[0][1]
        
        # Consistency is how often the mode appears
        consistency = mode_frequency / len(sample_counts)
        
        return {
            "avg_face_count": avg_count,
            "mode_face_count": mode_count,
            "consistency": consistency
        }
