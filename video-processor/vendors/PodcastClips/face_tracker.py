"""
Face tracking module using OpenCV for intelligent person-focused cropping.
"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional, List, Callable, Any
from dataclasses import dataclass, field
from loguru import logger as loguru_logger
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d
import os
import sys
from .face_tracker_filters import smooth_trajectory_with_one_euro

# =============================================================================
# CONFIGURATION PARAMETERS - Adjust these values to tune face tracking behavior
# =============================================================================

# Face Detection Parameters
# -------------------------
# Minimum face size as ratio of frame area (0.002-0.1)
# Faces smaller than this are filtered out (background/audience members)
# Default: 0.035 (3.5% of frame) - filters small background faces and distant people
MIN_FACE_SIZE_RATIO = 0.035

# Maximum number of faces to track simultaneously (1-8)
# 1: Track only largest face (simplest)
# 2-4: Track main subjects (recommended for podcasts with multiple speakers)
MAX_TRACKED_FACES = 2

# Minimum frames required to keep a face track (avoids tracking false detections)
# Lower value = more sensitive to brief appearances
# Higher value = only tracks faces that appear consistently
MIN_TRACK_FRAMES = 10

# Minimum average confidence for a face track to be kept (0-1)
# Lower value = more lenient, may include uncertain detections
# Higher value = stricter, only high-confidence tracks
MIN_AVG_CONFIDENCE = 0.6

# IoU (Intersection over Union) threshold for NMS (Non-Maximum Suppression)
# Lower value = stricter duplicate removal (fewer duplicates)
# Higher value = more lenient (may keep some duplicates)
NMS_IOU_THRESHOLD = 0.3

# Maximum velocity for face movement tracking (as fraction of frame width)
# Lower value = stricter association, prevents ID switching
# Higher value = more lenient, allows faster movement
MAX_FACE_VELOCITY = 0.4

# Speaker Detection Parameters
# ----------------------------
# Speaker switching debounce time (seconds)
# Prevents rapid switching between speakers
SPEAKER_SWITCH_DEBOUNCE = 0.3

# Speaker switching hysteresis (0-1)
# Margin required before switching to a different speaker
# Higher value = more stable (fewer switches)
SPEAKER_SWITCH_HYSTERESIS = 0.3

# Face separation threshold for split-screen detection (0-1)
# Fraction of frame width required to consider faces "separated"
# Higher value = stricter (only very separated faces trigger split-screen)
FACE_SEPARATION_THRESHOLD = 0.7

# Face persistence window (seconds)
# How long to persist last known face position during temporary gaps
# Prevents false switches during wide shots or occlusions
FACE_PERSISTENCE_WINDOW = 2.0

# Smoothing Parameters
# --------------------
# Default smoothing window for crop box calculation (seconds)
# Larger value = smoother but slower to respond to movement
SMOOTHING_WINDOW = 1.5

# Reduced smoothing window near mode transitions (seconds)
# Prevents jitter when switching between vertical/horizontal modes
TRANSITION_SMOOTHING_WINDOW = 1

# Face aspect ratio validation range (height/width)
# Real human faces typically have ratios between 0.75 and 1.5
# Filters out false detections like logos, text, rectangular objects
MIN_FACE_ASPECT_RATIO = 0.75
MAX_FACE_ASPECT_RATIO = 1.5

# =============================================================================
# END CONFIGURATION PARAMETERS
# =============================================================================

# Import speaker diarization for speaker-to-face mapping
try:
    from .speaker_diarization import SpeakerDiarizer, is_speaker_diarization_available
    SPEAKER_DIARIZATION_AVAILABLE = is_speaker_diarization_available()
except ImportError:
    SPEAKER_DIARIZATION_AVAILABLE = False

# Import OpenCV YuNet face detector (primary and only backend)
try:
    from .face_detector_opencv import OpenCVFaceDetector, is_opencv_face_detection_available
    OPENCV_FACE_DETECTION_AVAILABLE = is_opencv_face_detection_available()
except ImportError:
    OPENCV_FACE_DETECTION_AVAILABLE = False
    raise ImportError("OpenCV face detection is required but not available")

# Import new enhancement modules
try:
    from .face_recognition import FaceRecognitionEngine
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

try:
    from .gaze_detection import GazeDetector
    GAZE_DETECTION_AVAILABLE = True
except ImportError:
    GAZE_DETECTION_AVAILABLE = False

try:
    from .audio_visual_fusion import AudioVisualFusion
    AUDIO_VISUAL_FUSION_AVAILABLE = True
except ImportError:
    AUDIO_VISUAL_FUSION_AVAILABLE = False

try:
    from .scene_detector import SceneDetector
    SCENE_DETECTOR_AVAILABLE = True
except ImportError:
    SCENE_DETECTOR_AVAILABLE = False

try:
    from .face_cache import FaceDetectionCache
    FACE_CACHE_AVAILABLE = True
except ImportError:
    FACE_CACHE_AVAILABLE = False

try:
    from .tracking_metrics import TrackingMetricsCalculator
    TRACKING_METRICS_AVAILABLE = True
except ImportError:
    TRACKING_METRICS_AVAILABLE = False

# Import GPU manager for intelligent GPU usage decisions
try:
    # Add backend path to import gpu_manager
    backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from utils.gpu_manager import should_use_gpu
    GPU_MANAGER_AVAILABLE = True
except ImportError:
    GPU_MANAGER_AVAILABLE = False

logger = loguru_logger.bind(name="PodcastClips.face_tracker")


@dataclass
class FaceBox:
    """Face bounding box information."""
    x: int  # Left coordinate
    y: int  # Top coordinate
    width: int
    height: int
    confidence: float
    face_id: int = 0  # ID for tracking multiple faces
    is_background: bool = False  # NEW (Phase 3): True if face is background/audience

    @property
    def center(self) -> Tuple[int, int]:
        """Get center point of face box."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def area(self) -> int:
        """Get area of face box."""
        return self.width * self.height

    def area_ratio(self, frame_width: int, frame_height: int) -> float:
        """Get face area as ratio of total frame area."""
        frame_area = frame_width * frame_height
        return self.area / frame_area if frame_area > 0 else 0.0

    @property
    def aspect_ratio(self) -> float:
        """Get aspect ratio of face box (height/width)."""
        return self.height / self.width if self.width > 0 else 0.0

    def is_valid_face_shape(self) -> bool:
        """
        Validate that the face box has a realistic aspect ratio.

        Real human faces have aspect ratios between 0.75 and 1.5 (height/width).
        This filters out false detections like logos, text, or rectangular objects.

        Returns:
            True if aspect ratio is within valid range, False otherwise
        """
        ratio = self.aspect_ratio
        return MIN_FACE_ASPECT_RATIO <= ratio <= MAX_FACE_ASPECT_RATIO

    def quality_score(self, frame_width: int, frame_height: int) -> float:
        """
        Calculate overall detection quality score (0-1).

        Combines:
        - Size: Larger faces (more likely main subject) = higher score
        - Confidence: Higher detection confidence = higher score  
        - Centrality: Centered faces (more likely main subject) = higher score

        This is used to filter low-quality detections from mode decisions.

        Returns:
            Quality score from 0 to 1
        """
        # Size component (0-1, normalized to 10% of frame = max)
        size_score = min(1.0, self.area_ratio(frame_width, frame_height) / 0.10)

        # Confidence component (already 0-1)
        conf_score = self.confidence

        # Centrality component (0-1, center = 1, edges = 0)
        center_x, center_y = self.center
        norm_x = center_x / frame_width if frame_width > 0 else 0.5
        norm_y = center_y / frame_height if frame_height > 0 else 0.5
        distance_from_center = ((norm_x - 0.5)**2 + (norm_y - 0.5)**2)**0.5
        max_distance = 0.707  # Corner distance
        centrality_score = 1.0 - (distance_from_center / max_distance)

        # Combined: 40% size, 40% confidence, 20% centrality
        return size_score * 0.40 + conf_score * 0.40 + centrality_score * 0.20


@dataclass
class FaceTrack:
    """Tracks a single person's face across multiple frames."""
    face_id: int
    positions: Dict[float, FaceBox] = field(default_factory=dict)  # timestamp -> FaceBox
    avg_area_ratio: float = 0.0  # Average size relative to frame
    avg_position: Tuple[int, int] = (0, 0)  # Average center position
    is_foreground: bool = True  # Whether this is a foreground (main) subject
    speech_correlation: float = 0.0  # Correlation with speech activity (0-1)
    lip_activity_scores: Dict[float, float] = field(default_factory=dict)  # timestamp -> lip movement score (0-1)
    avg_lip_activity: float = 0.0  # Average lip movement activity
    avg_confidence: float = 0.0  # Average detection confidence across all frames (0-1)

    def update_statistics(self, frame_width: int, frame_height: int):
        """Update aggregate statistics for this face track."""
        if not self.positions:
            return

        # Calculate average area ratio
        area_ratios = [
            face.area_ratio(frame_width, frame_height)
            for face in self.positions.values()
        ]
        self.avg_area_ratio = float(np.mean(area_ratios))

        # Calculate average position
        centers = [face.center for face in self.positions.values()]
        self.avg_position = (
            int(np.mean([c[0] for c in centers])),
            int(np.mean([c[1] for c in centers]))
        )

        # Calculate average confidence
        confidences = [face.confidence for face in self.positions.values()]
        self.avg_confidence = float(np.mean(confidences))

        # Calculate average lip activity if available
        if self.lip_activity_scores:
            self.avg_lip_activity = float(np.mean(list(self.lip_activity_scores.values())))


@dataclass
class CropBox:
    """Crop box for 9:16 format video."""
    x: int  # Left coordinate
    y: int  # Top coordinate (always 0 for horizontal videos)
    width: int
    height: int

    def to_moviepy_crop(self) -> Tuple[int, int, int, int]:
        """Convert to MoviePy crop format (x1, y1, x2, y2)."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)


class FaceTracker:
    """
    Face tracking using OpenCV YuNet Face Detection.

    Analyzes video frames to detect faces and provides optimal crop boxes
    for converting horizontal podcast videos to 9:16 vertical format while
    keeping the speaker centered.
    """

    def __init__(
        self,
        use_gpu: bool = True,
        detection_height: int = 0,  # 0 = adaptive (use video resolution), otherwise fixed height
        batch_size: int = 4,
        min_face_size_ratio: Optional[float] = None,  # Optional override for MIN_FACE_SIZE_RATIO
        max_tracked_faces: Optional[int] = None,  # Optional override for MAX_TRACKED_FACES
        enable_speaker_detection: bool = False,
        enable_lip_detection: bool = False,
        detector_backend: str = "opencv",  
        # New enhancement features
        enable_face_recognition: bool = False,
        enable_gaze_detection: bool = False,
        enable_av_fusion: bool = False,
        enable_scene_detection: bool = False,
        enable_caching: bool = True,
        enable_quality_metrics: bool = False,
        cache_dir: str = ".face_detection_cache"
    ):
        """
        Initialize face tracker with OpenCV.

        Args:
            use_gpu: Whether to prefer GPU acceleration (will fallback to CPU if GPU unavailable)
            detection_height: Target height for face detection processing
                             - 0: Adaptive (uses video resolution for best accuracy) - DEFAULT
                             - 1080: No downscaling for 1080p videos
                             - 720: Balanced (2-3x faster, minimal accuracy loss)
                             - 480: Fast (4-5x faster, good for simple podcasts)
            batch_size: Number of frames to process per batch (1-8)
                       - 1: No batching (simple, works on CPU)
                       - 4: Balanced batching (recommended for GPU) - DEFAULT
                       - 8: Aggressive batching (best GPU utilization)
            min_face_size_ratio: Optional override for MIN_FACE_SIZE_RATIO constant
            max_tracked_faces: Optional override for MAX_TRACKED_FACES constant
            enable_speaker_detection: Enable audio-based speaker detection
            enable_lip_detection: Deprecated (MediaPipe removed), kept for compatibility
            detector_backend: Deprecated (only OpenCV now), kept for compatibility
            enable_face_recognition: Enable InsightFace embeddings for persistent identity (NEW)
            enable_gaze_detection: Enable iris-based gaze direction detection (NEW)
            enable_av_fusion: Enable audio-visual fusion for improved speaker detection (NEW)
            enable_scene_detection: Enable scene change detection and auto-reset (NEW)
            enable_caching: Enable face detection caching for performance (NEW)
            enable_quality_metrics: Enable tracking quality metrics computation (NEW)
            cache_dir: Directory for face detection cache
        """
        
        # Warn about deprecated parameters
        if enable_lip_detection:
            logger.warning("enable_lip_detection is deprecated (MediaPipe removed). Ignoring.")
        if detector_backend != "opencv":
            logger.warning(f"detector_backend='{detector_backend}' is deprecated. Only OpenCV is supported now.")
        
        self.use_gpu_requested = use_gpu
        self.use_gpu_actual = False  # Will be set based on GPU manager decision
        self.detection_height = detection_height
        self.batch_size = max(1, min(8, batch_size))  # Clamp to 1-8 range
        
        # Use provided values or fall back to configuration constants
        self.min_face_size_ratio = min_face_size_ratio if min_face_size_ratio is not None else MIN_FACE_SIZE_RATIO
        self.max_tracked_faces = max_tracked_faces if max_tracked_faces is not None else MAX_TRACKED_FACES
        self.enable_speaker_detection = enable_speaker_detection

        # Make intelligent GPU decision using GPU manager
        if use_gpu and GPU_MANAGER_AVAILABLE:
            try:
                # Estimate ~1.5GB GPU memory for face detection
                gpu_decision = should_use_gpu(estimated_memory_gb=1.5)
                self.use_gpu_actual = gpu_decision.get('use_gpu', False)

                if self.use_gpu_actual:
                    logger.info(f"✓ Using GPU for face detection: {gpu_decision.get('reason', 'GPU available')}")
                    # Try to enable OpenCV GPU acceleration if available
                    try:
                        if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                            logger.info(f"  OpenCV CUDA devices available: {cv2.cuda.getCudaEnabledDeviceCount()}")
                    except:
                        pass
                else:
                    logger.info(f"→ GPU requested but using CPU: {gpu_decision.get('reason', 'GPU not recommended')}")

            except Exception as e:
                logger.warning(f"GPU manager check failed, falling back to CPU: {e}")
                self.use_gpu_actual = False
        else:
            if not use_gpu:
                logger.info("→ CPU mode requested for face detection")
            else:
                logger.info("→ GPU manager not available, MediaPipe will auto-detect GPU")
                self.use_gpu_actual = use_gpu  # Let MediaPipe handle it

        # Initialize OpenCV YuNet face detector (only backend)
        if not OPENCV_FACE_DETECTION_AVAILABLE:
            raise RuntimeError("OpenCV face detection is required but not available")
        
        try:
            logger.info("Initializing OpenCV YuNet face detector...")
            self.opencv_detector = OpenCVFaceDetector(
                conf_threshold=0.5,
                nms_threshold=NMS_IOU_THRESHOLD,
                model_dir=cache_dir
            )
            logger.info("✓ Using OpenCV YuNet face detector")
        except Exception as e:
            logger.error(f"Failed to initialize OpenCV detector: {e}")
            raise RuntimeError(f"OpenCV detector initialization failed: {e}")

        # Storage for detected face positions over time
        self.face_positions: Dict[float, FaceBox] = {}  # Legacy: single face per timestamp
        self.face_tracks: List[FaceTrack] = []  # Multi-face tracking
        self.video_width = 0
        self.video_height = 0
        self.target_aspect = 9 / 16  # Vertical format
        self.speech_segments: List = []  # Will store AudioSegment objects from speaker_detector

        # Speaker detection integration
        if self.enable_speaker_detection:
            try:
                from .speaker_detector import SpeakerDetector
                self.speaker_detector = SpeakerDetector()
                logger.info("Speaker detection enabled")
            except ImportError as e:
                logger.warning(f"Speaker detection requested but unavailable: {e}")
                self.speaker_detector = None
                self.enable_speaker_detection = False
        else:
            self.speaker_detector = None

        # Speaker switching hysteresis state (uses config constants)
        self.current_active_speaker_id: Optional[int] = None
        self.last_speaker_switch_time: float = 0.0
        self.speaker_switch_debounce: float = SPEAKER_SWITCH_DEBOUNCE
        self.speaker_switch_hysteresis: float = SPEAKER_SWITCH_HYSTERESIS

        # Speaker diarization integration
        self.diarization_segments: List = []  # List of SpeakerSegment objects
        self.speaker_to_face_map: Dict[str, int] = {}  # Maps SPEAKER_00 -> face_track_id
        self.face_to_speaker_map: Dict[int, str] = {}  # Maps face_track_id -> SPEAKER_00
        self.diarizer: Optional[Any] = None

        # Initialize new enhancement modules
        self.enable_face_recognition = enable_face_recognition
        self.enable_gaze_detection = enable_gaze_detection
        self.enable_av_fusion = enable_av_fusion
        self.enable_scene_detection = enable_scene_detection
        self.enable_caching = enable_caching
        self.enable_quality_metrics = enable_quality_metrics

        # Face recognition engine
        if self.enable_face_recognition and FACE_RECOGNITION_AVAILABLE:
            try:
                self.face_recognition = FaceRecognitionEngine(
                    model_name="buffalo_l",
                    similarity_threshold=0.6,
                    gpu_id=0 if self.use_gpu_actual else -1
                )
                logger.info("Face recognition enabled (InsightFace)")
            except Exception as e:
                logger.warning(f"Failed to initialize face recognition: {e}")
                self.face_recognition = None
                self.enable_face_recognition = False
        else:
            self.face_recognition = None
            if enable_face_recognition and not FACE_RECOGNITION_AVAILABLE:
                logger.warning("Face recognition requested but module not available")
                
        # Audio-visual fusion
        if self.enable_av_fusion and AUDIO_VISUAL_FUSION_AVAILABLE:
            try:
                self.av_fusion = AudioVisualFusion(
                    sync_threshold=0.3,
                    max_lag_ms=200.0,
                    window_size_sec=0.5
                )
                logger.info("Audio-visual fusion enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize AV fusion: {e}")
                self.av_fusion = None
                self.enable_av_fusion = False
        else:
            self.av_fusion = None
            if enable_av_fusion and not AUDIO_VISUAL_FUSION_AVAILABLE:
                logger.warning("AV fusion requested but module not available")

        # Scene detector
        if self.enable_scene_detection and SCENE_DETECTOR_AVAILABLE:
            try:
                self.scene_detector = SceneDetector(
                    cut_threshold=0.5,
                    fade_threshold=0.7,
                    fade_window=5,
                    check_interval=1
                )
                self.scene_changes = []
                logger.info("Scene detection enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize scene detector: {e}")
                self.scene_detector = None
                self.enable_scene_detection = False
        else:
            self.scene_detector = None
            self.scene_changes = []
            if enable_scene_detection and not SCENE_DETECTOR_AVAILABLE:
                logger.warning("Scene detection requested but module not available")

        # Face detection cache
        if self.enable_caching and FACE_CACHE_AVAILABLE:
            try:
                self.face_cache = FaceDetectionCache(
                    cache_dir=cache_dir,
                    enable_cache=True,
                    hash_method="quick"
                )
                logger.info("Face detection caching enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize face cache: {e}")
                self.face_cache = None
                self.enable_caching = False
        else:
            self.face_cache = None
            if enable_caching and not FACE_CACHE_AVAILABLE:
                logger.warning("Face caching requested but module not available")

        # Quality metrics calculator
        if self.enable_quality_metrics and TRACKING_METRICS_AVAILABLE:
            try:
                self.metrics_calculator = TrackingMetricsCalculator()
                logger.info("Quality metrics enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize metrics calculator: {e}")
                self.metrics_calculator = None
                self.enable_quality_metrics = False
        else:
            self.metrics_calculator = None
            if enable_quality_metrics and not TRACKING_METRICS_AVAILABLE:
                logger.warning("Quality metrics requested but module not available")

    @staticmethod
    def _validate_face_landmarks(landmarks: dict) -> bool:
        """
        Validate that facial landmarks are anatomically consistent.

        Checks:
        1. Eyes are roughly horizontally aligned (±20% tolerance)
        2. Nose is below eyes
        3. Mouth is below nose
        4. Eyes are not too far apart or too close

        Args:
            landmarks: Dict with 'right_eye', 'left_eye', 'nose', 'right_mouth', 'left_mouth' keys

        Returns:
            True if landmarks are consistent, False otherwise
        """
        try:
            right_eye = landmarks['right_eye']
            left_eye = landmarks['left_eye']
            nose = landmarks['nose']
            right_mouth = landmarks['right_mouth']
            left_mouth = landmarks['left_mouth']

            # 1. Check eyes are horizontally aligned (±20% tolerance)
            eye_y_diff = abs(right_eye[1] - left_eye[1])
            eye_distance = abs(right_eye[0] - left_eye[0])
            if eye_distance > 0:
                eye_alignment_ratio = eye_y_diff / eye_distance
                if eye_alignment_ratio > 0.2:  # Eyes differ by more than 20% of distance
                    logger.debug(
                        f"Rejected landmarks: eyes not horizontally aligned "
                        f"(y_diff={eye_y_diff}, distance={eye_distance}, ratio={eye_alignment_ratio:.2f})"
                    )
                    return False

            # 2. Check nose is below eyes (average eye y-position)
            avg_eye_y = (right_eye[1] + left_eye[1]) / 2
            if nose[1] <= avg_eye_y:
                logger.debug(
                    f"Rejected landmarks: nose not below eyes "
                    f"(nose_y={nose[1]}, avg_eye_y={avg_eye_y})"
                )
                return False

            # 3. Check mouth is below nose
            avg_mouth_y = (right_mouth[1] + left_mouth[1]) / 2
            if avg_mouth_y <= nose[1]:
                # Only log if significantly above (avoid spam)
                if avg_mouth_y < nose[1] - 10:
                    logger.debug(
                        f"Rejected landmarks: mouth significantly above nose "
                        f"(mouth_y={avg_mouth_y}, nose_y={nose[1]})"
                    )
                return False

            # Note: Eye distance check removed - was generating too many false warnings
            # (ratio of 1.0 when eye_distance == face_width is normal for some faces)

            return True

        except (KeyError, IndexError, ZeroDivisionError) as e:
            logger.debug(f"Landmark validation failed: {e}")
            return False

    @staticmethod
    def _estimate_face_angle_from_landmarks(landmarks: dict) -> float:
        """
        Estimate face angle (yaw) from eye positions.

        Args:
            landmarks: Dict with landmark positions

        Returns:
            Estimated face angle in degrees (0 = frontal, ±90 = profile)
        """
        try:
            right_eye = landmarks['right_eye']
            left_eye = landmarks['left_eye']
            nose = landmarks['nose']

            # Calculate center between eyes
            eye_center_x = (right_eye[0] + left_eye[0]) / 2

            # Calculate nose offset from eye center
            nose_offset = nose[0] - eye_center_x

            # Calculate eye distance for normalization
            eye_distance = abs(right_eye[0] - left_eye[0])

            if eye_distance > 0:
                # Normalized offset: -1 (full left) to +1 (full right)
                normalized_offset = nose_offset / (eye_distance / 2)

                # Convert to approximate angle (simplified model)
                # At profile view (~90°), nose appears ~50% offset from center
                angle = normalized_offset * 60  # Scale to degrees

                return angle
            return 0.0

        except (KeyError, IndexError, ZeroDivisionError):
            return 0.0

    @staticmethod
    def _calculate_iou(box1: FaceBox, box2: FaceBox) -> float:
        """
        Calculate Intersection over Union (IoU) between two face boxes.

        Args:
            box1: First face box
            box2: Second face box

        Returns:
            IoU value between 0 and 1
        """
        # Calculate intersection coordinates
        x1 = max(box1.x, box2.x)
        y1 = max(box1.y, box2.y)
        x2 = min(box1.x + box1.width, box2.x + box2.width)
        y2 = min(box1.y + box1.height, box2.y + box2.height)

        # Calculate intersection area
        intersection_width = max(0, x2 - x1)
        intersection_height = max(0, y2 - y1)
        intersection_area = intersection_width * intersection_height

        # Calculate union area
        box1_area = box1.area
        box2_area = box2.area
        union_area = box1_area + box2_area - intersection_area

        # Calculate IoU
        if union_area == 0:
            return 0.0
        return intersection_area / union_area

    def _calculate_center_score(self, face: FaceBox) -> float:
        """
        Calculate how centered a face is in the frame.

        Main speakers are typically positioned in the center of the frame.
        This returns a score from 0 (at edge) to 1 (perfectly centered).

        Args:
            face: Face box to score

        Returns:
            Center score from 0 to 1
        """
        center_x, center_y = face.center

        # Normalize to 0-1 range
        normalized_x = center_x / self.video_width
        normalized_y = center_y / self.video_height

        # Calculate distance from center (0.5, 0.5)
        dx = abs(normalized_x - 0.5)
        dy = abs(normalized_y - 0.5)

        # Euclidean distance from center
        distance_from_center = np.sqrt(dx**2 + dy**2)

        # Convert to score (0 at corner, 1 at center)
        # Maximum distance to corner is sqrt(0.5^2 + 0.5^2) = ~0.707
        max_distance = 0.707
        center_score = 1.0 - (distance_from_center / max_distance)

        return max(0.0, min(1.0, center_score))

    def _calculate_face_priority_score(self, face: FaceBox) -> float:
        """
        Calculate a priority score for face selection.

        Combines multiple factors to identify the main speaker:
        - Size: Larger faces are likely closer/more important (40% weight)
        - Centrality: Center faces are likely main subjects (50% weight)
        - Confidence: Higher confidence detections (10% weight)

        Args:
            face: Face box to score

        Returns:
            Priority score (higher = more likely to be main speaker)
        """
        # Size score (normalized by frame area)
        area_ratio = face.area_ratio(self.video_width, self.video_height)
        # Normalize to reasonable range (0.01 to 0.2 of frame = 0 to 1)
        size_score = min(1.0, area_ratio / 0.15)

        # Center score
        center_score = self._calculate_center_score(face)

        # Confidence score
        confidence_score = face.confidence

        # Combined score with weights - prioritize center position
        priority_score = (size_score * 0.40) + (center_score * 0.50) + (confidence_score * 0.10)

        return priority_score

    def _is_background_face(self, face: FaceBox, all_faces: List[FaceBox]) -> bool:
        """
        Detect if a face is likely a background/audience member.

        Background faces are identified by:
        1. Very small size (< 2% of frame area)
        2. Small size (< 3%) combined with low quality
        
        These faces should be filtered from tracking to prevent them
        from interfering with speaker selection.

        Args:
            face: Face box to check
            all_faces: All faces detected in frame (for context)

        Returns:
            True if face is background, False otherwise
        """
        area_ratio = face.area_ratio(self.video_width, self.video_height)
        
        # Rule 1: Very small faces are always background
        if area_ratio < 0.02:  # < 2% of frame
            logger.debug(
                f"Background face detected (very small): "
                f"size={area_ratio*100:.1f}%, conf={face.confidence:.2f}"
            )
            return True
        
        # Rule 2: Small + low quality = background
        if area_ratio < 0.03:  # < 3% of frame
            quality = face.quality_score(self.video_width, self.video_height)
            if quality < 0.25:
                logger.debug(
                    f"Background face detected (small + low quality): "
                    f"size={area_ratio*100:.1f}%, quality={quality:.2f}"
                )
                return True
        
        return False

    @staticmethod
    def _apply_nms(faces: List[FaceBox], iou_threshold: float = NMS_IOU_THRESHOLD) -> List[FaceBox]:
        """
        Apply Non-Maximum Suppression to remove overlapping face detections.
        
        Uses configurable IoU threshold for stricter duplicate removal.
        Groups overlapping faces and selects the best from each group.
        """
        if len(faces) <= 1:
            return faces

        # Group overlapping faces first
        face_groups = []
        processed = set()
        
        for i, face_i in enumerate(faces):
            if i in processed:
                continue
                
            # Start a new group with this face
            group = [face_i]
            processed.add(i)
            
            # Find all faces that overlap with any face in this group
            for j in range(i + 1, len(faces)):
                if j in processed:
                    continue
                    
                face_j = faces[j]
                
                # Check if face_j overlaps with any face in the current group
                for group_face in group:
                    iou = FaceTracker._calculate_iou(group_face, face_j)
                    if iou > iou_threshold:  # Using 0.25 instead of 0.3
                        group.append(face_j)
                        processed.add(j)
                        break
            
            face_groups.append(group)
        
        # From each group, select the best face
        result = []
        for group in face_groups:
            # Select face with best combined score (confidence + size)
            def score_face(face):
                # Give preference to larger faces when confidence is similar
                size_bonus = min(0.3, face.area / 50000)  # Normalize to 0-0.3 range
                return face.confidence + size_bonus
            
            best_face = max(group, key=score_face)
            result.append(best_face)
        
        logger.debug(f"NMS: Reduced {len(faces)} faces to {len(result)} (removed {len(faces)-len(result)} duplicates)")
        return result

    

    def _merge_duplicate_tracks(self):
        """
        Merge face tracks that likely represent the same person.

        This reduces track fragmentation caused by temporary detection gaps,
        movement, or occlusions. Same person shouldn't have multiple track IDs.

        Tracks are merged if they:
        1. Have no temporal overlap (can't be same person if both exist simultaneously)
        2. Are temporally close (one ends, another starts within 3 seconds)
        3. Have similar average position (within 40% of frame width)
        4. Have similar average size (within 2x size ratio)
        """
        if len(self.face_tracks) <= 1:
            return

        # Sort tracks by start time
        sorted_tracks = sorted(self.face_tracks, key=lambda t: min(t.positions.keys()))

        merged_indices = set()  # Tracks that have been merged away

        for i in range(len(sorted_tracks)):
            if i in merged_indices:
                continue

            track_a = sorted_tracks[i]
            timestamps_a = sorted(track_a.positions.keys())
            time_start_a = timestamps_a[0]
            time_end_a = timestamps_a[-1]

            for j in range(i + 1, len(sorted_tracks)):
                if j in merged_indices:
                    continue

                track_b = sorted_tracks[j]
                timestamps_b = sorted(track_b.positions.keys())
                time_start_b = timestamps_b[0]
                time_end_b = timestamps_b[-1]

                # Check 1: No temporal overlap
                if time_end_a >= time_start_b and time_start_a <= time_end_b:
                    # Tracks overlap in time - can't be same person
                    continue

                # Check 2: Temporally close
                # Calculate gap between tracks (one ends, another starts)
                if time_start_b > time_end_a:
                    gap = time_start_b - time_end_a
                elif time_start_a > time_end_b:
                    gap = time_start_a - time_end_b
                else:
                    continue  # Shouldn't happen if check 1 passed

                if gap > 3.0:  # More than 3 seconds gap
                    continue

                # Check 3: Similar average position
                pos_a = track_a.avg_position
                pos_b = track_b.avg_position
                distance = np.sqrt((pos_a[0] - pos_b[0])**2 + (pos_a[1] - pos_b[1])**2)
                position_threshold = self.video_width * 0.4  # 40% of frame width

                if distance > position_threshold:
                    continue

                # Check 4: Similar size
                size_ratio = track_b.avg_area_ratio / track_a.avg_area_ratio if track_a.avg_area_ratio > 0 else 0
                if size_ratio < 0.5 or size_ratio > 2.0:  # More than 2x difference
                    continue

                # All checks passed - merge track_b into track_a
                logger.debug(
                    f"Merging tracks: {track_b.face_id} -> {track_a.face_id} "
                    f"(gap={gap:.2f}s, dist={distance:.0f}px, size_ratio={size_ratio:.2f})"
                )

                # Merge positions
                track_a.positions.update(track_b.positions)

                # Merge lip activity scores if available
                if hasattr(track_a, 'lip_activity_scores') and hasattr(track_b, 'lip_activity_scores'):
                    track_a.lip_activity_scores.update(track_b.lip_activity_scores)

                # Update statistics for merged track
                track_a.update_statistics(self.video_width, self.video_height)

                # Mark track_b for removal
                merged_indices.add(j)

        # Remove merged tracks
        if merged_indices:
            self.face_tracks = [
                track for idx, track in enumerate(sorted_tracks)
                if idx not in merged_indices
            ]
            logger.info(f"Merged {len(merged_indices)} duplicate tracks (reduced from {len(sorted_tracks)} to {len(self.face_tracks)} tracks)")

    def analyze_video(
        self,
        video_path: str,
        sample_rate: int = 2,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict[float, FaceBox]:
        """
        Analyze video and detect face positions at sampled frames.

        Args:
            video_path: Path to video file
            sample_rate: Sample every Nth frame (default 2 = 15fps sampling at 30fps video)
            start_time: Optional start time in seconds (for analyzing specific segments)
            end_time: Optional end time in seconds
            progress_callback: Optional callback function(progress_pct, message) for progress updates

        Returns:
            Dictionary mapping timestamps to face boxes
        """
        logger.info(f"Analyzing video for face detection: {video_path}")
        logger.info(f"  GPU mode: {'Enabled' if self.use_gpu_actual else 'CPU fallback'}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        # Get video properties
        self.video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video properties: {self.video_width}x{self.video_height} @ {fps} fps, {total_frames} frames")

        # Calculate detection resolution and scaling factors
        # Adaptive detection height: use original resolution for best accuracy with small faces
        MIN_DIMENSION = 10

        if self.detection_height == 0:
            # Adaptive mode: use original resolution (best for wide shots with small faces)
            detection_height_final = self.video_height
            detection_width = self.video_width
            logger.info(f"  Using adaptive detection height (original resolution for best accuracy)")
        else:
            # Fixed detection height
            detection_height_final = max(MIN_DIMENSION, self.detection_height)
            detection_width = int(self.video_width * (detection_height_final / self.video_height))
            detection_width = max(MIN_DIMENSION, detection_width)

        # Update detection_height to the validated value
        self.detection_height = detection_height_final

        scale_x = self.video_width / detection_width
        scale_y = self.video_height / detection_height_final

        if detection_height_final < self.video_height:
            logger.info(f"  Downscaling for face detection: {self.video_width}x{self.video_height} -> {detection_width}x{detection_height_final}")
            logger.info(f"  Scaling factors: x={scale_x:.3f}, y={scale_y:.3f}")
        else:
            logger.info(f"  Processing at original resolution (no downscaling)")

        # Determine frame range
        start_frame = int(start_time * fps) if start_time else 0
        end_frame = int(end_time * fps) if end_time else total_frames

        # Calculate total frames to process (with sampling)
        total_frames_to_process = (end_frame - start_frame) // sample_rate
        logger.info(f"Will analyze {total_frames_to_process} frames (sampling every {sample_rate} frames)")

        if self.batch_size > 1:
            logger.info(f"  Batch processing enabled: {self.batch_size} frames per batch")

        face_positions = {}
        all_faces_by_timestamp = {}  # Store ALL detected faces for multi-face tracking
        frames_processed = 0
        faces_detected = 0
        last_progress_pct = 0

        # Batch processing buffers
        frame_batch = []
        frame_batch_metadata = []  # Store (frame_num, timestamp) for each frame in batch

        def process_batch():
            """Process accumulated batch of frames through MediaPipe."""
            nonlocal faces_detected, frames_processed, last_progress_pct

            if not frame_batch:
                return

            # Process each frame in batch
            for idx, frame_rgb in enumerate(frame_batch):
                frame_num, timestamp = frame_batch_metadata[idx]
                valid_faces = []

                # Detect faces using OpenCV YuNet detector
                if not self.opencv_detector:
                    logger.warning("OpenCV face detector not initialized, skipping frame")
                    continue

                # OpenCV YuNet detection
                # Convert RGB back to BGR for OpenCV
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

                # Use detect_with_landmarks for landmark validation
                detections_with_landmarks = self.opencv_detector.detect_with_landmarks(frame_bgr)

                for det_data in detections_with_landmarks[:self.max_tracked_faces]:
                        # Extract detection data
                        x, y, w, h = det_data['bbox']
                        confidence = det_data['confidence']
                        landmarks = det_data['landmarks']

                        # Scale back to original resolution if downscaled
                        if detection_height_final < self.video_height:
                            x = int(x * scale_x)
                            y = int(y * scale_y)
                            w = int(w * scale_x)
                            h = int(h * scale_y)

                            # Scale landmarks too
                            scaled_landmarks = {}
                            for key, (lx, ly) in landmarks.items():
                                scaled_landmarks[key] = (int(lx * scale_x), int(ly * scale_y))
                            landmarks = scaled_landmarks

                        # Ensure coordinates are within frame bounds
                        x = max(0, x)
                        y = max(0, y)
                        w = min(w, self.video_width - x)
                        h = min(h, self.video_height - y)

                        # Create face box
                        face_box = FaceBox(x=x, y=y, width=w, height=h, confidence=confidence)

                        # Conservative filtering to reduce false positives
                        # 1. Size filter (keep original threshold)
                        area_ratio = face_box.area_ratio(self.video_width, self.video_height)
                        if area_ratio < self.min_face_size_ratio:
                            continue

                        # 2. Geometric validation (stricter - filter unrealistic face shapes)
                        aspect_ratio = face_box.aspect_ratio
                        if aspect_ratio < MIN_FACE_ASPECT_RATIO or aspect_ratio > MAX_FACE_ASPECT_RATIO:
                            logger.debug(
                                f"Rejected detection: aspect ratio {aspect_ratio:.2f} out of range [{MIN_FACE_ASPECT_RATIO}-{MAX_FACE_ASPECT_RATIO}]"
                            )
                            continue

                        # 4. Background face filter (NEW - Phase 1)
                        # Filter out small background/audience faces from tracking
                        # This is done BEFORE adding to valid_faces to prevent them
                        # from being tracked and interfering with speaker selection
                        if self._is_background_face(face_box, valid_faces):
                            # Background face - skip it entirely
                            continue

                        valid_faces.append(face_box)

                # Store valid faces
                if valid_faces:
                    # Apply Non-Maximum Suppression to remove overlapping detections
                    valid_faces = self._apply_nms(valid_faces)

                    # Additional confidence filter after NMS to ensure high-quality detections
                    # This removes any remaining low-confidence faces that passed initial filters
                    MIN_DETECTION_CONFIDENCE = 0.65
                    valid_faces = [f for f in valid_faces if f.confidence >= MIN_DETECTION_CONFIDENCE]

                    # Only proceed if we still have valid faces after confidence filter
                    if valid_faces:
                        # Sort by priority score (size + centrality + confidence) to identify main speaker
                        # This prioritizes larger faces that are centered in the frame
                        valid_faces.sort(key=lambda f: self._calculate_face_priority_score(f), reverse=True)

                        # Store highest priority face for legacy single-face tracking
                        face_positions[timestamp] = valid_faces[0]
                        faces_detected += 1

                        # Store ALL valid faces for multi-face tracking
                        all_faces_by_timestamp[timestamp] = valid_faces

                frames_processed += 1

                # Log progress every 10% or every 50 frames (whichever comes first)
                progress_pct = int((frames_processed / total_frames_to_process) * 100)
                if progress_pct >= last_progress_pct + 10 or frames_processed % 50 == 0:
                    detection_rate = (faces_detected / frames_processed * 100) if frames_processed > 0 else 0
                    message = f"Face detection: {progress_pct}% ({frames_processed}/{total_frames_to_process} frames) - {faces_detected} faces found ({detection_rate:.1f}% detection rate)"
                    logger.info(message)

                    # Call progress callback if provided
                    if progress_callback:
                        try:
                            progress_callback(progress_pct, message)
                        except Exception as e:
                            logger.warning(f"Progress callback failed: {e}")

                    last_progress_pct = progress_pct

            # Clear batch
            frame_batch.clear()
            frame_batch_metadata.clear()

        try:
            for frame_num in range(start_frame, end_frame, sample_rate):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()

                if not ret:
                    break

                # Convert BGR to RGB for MediaPipe
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Downscale frame for face detection if needed
                if detection_height_final < self.video_height:
                    frame_rgb = cv2.resize(
                        frame_rgb,
                        (detection_width, detection_height_final),
                        interpolation=cv2.INTER_AREA  # Best for downscaling
                    )

                timestamp = frame_num / fps

                # Add to batch
                frame_batch.append(frame_rgb)
                frame_batch_metadata.append((frame_num, timestamp))

                # Process batch when full
                if len(frame_batch) >= self.batch_size:
                    process_batch()

            # Process remaining frames in batch
            if frame_batch:
                process_batch()

        finally:
            cap.release()

        self.face_positions = face_positions

        # Build face tracks from all detected faces for multi-face support
        if self.max_tracked_faces > 1:
            self._build_face_tracks(all_faces_by_timestamp)

        detection_rate = (faces_detected / frames_processed * 100) if frames_processed > 0 else 0
        logger.info(f"Face detection complete: {faces_detected}/{frames_processed} frames ({detection_rate:.1f}%)")
        if self.face_tracks:
            logger.info(f"Built {len(self.face_tracks)} face tracks for multi-person tracking")

        return face_positions

    
    def _build_face_tracks(self, all_faces_by_timestamp: Dict[float, List[FaceBox]]):
        """
        Build face tracks from detected faces across all frames.
        
        Uses configurable velocity constraints to prevent ID switching.
        Applies NMS and filters tracks based on minimum frames and confidence.
        """
        if not all_faces_by_timestamp:
            return

        logger.info("Building face tracks with velocity constraints...")

        current_tracks: List[FaceTrack] = []
        track_id_counter = 0

        # Use configurable max velocity from constants
        max_velocity = self.video_width * MAX_FACE_VELOCITY

        for timestamp in sorted(all_faces_by_timestamp.keys()):
            faces = all_faces_by_timestamp[timestamp]
            
            # Apply NMS before tracking (uses configured threshold)
            faces = self._apply_nms(faces)

            for face in faces:
                best_track = None
                best_score = float('inf')
                
                # FIXED: Stricter position threshold
                POSITION_THRESHOLD = self.video_width * 0.25  # Changed from 0.5

                for track in current_tracks:
                    if track.positions:
                        recent_timestamps = sorted(track.positions.keys())
                        last_timestamp = recent_timestamps[-1]
                        last_face = track.positions[last_timestamp]

                        time_elapsed = timestamp - last_timestamp

                        # FIXED: Stricter time gap
                        if time_elapsed > 1.5:  # Changed from 5.0
                            continue

                        # Calculate distance
                        face_x, face_y = face.center
                        last_x, last_y = last_face.center
                        distance = np.sqrt((face_x - last_x)**2 + (face_y - last_y)**2)

                        # Velocity constraint
                        if time_elapsed > 0:
                            velocity = distance / time_elapsed
                            if velocity > max_velocity:
                                logger.debug(
                                    f"Rejected track match: velocity {velocity:.1f} px/s "
                                    f"exceeds max {max_velocity:.1f} px/s"
                                )
                                continue

                        # Size similarity check
                        size_ratio = face.area / last_face.area if last_face.area > 0 else 1
                        if size_ratio < 0.5 or size_ratio > 2.0:  # Face size shouldn't change too much
                            continue

                        # Calculate match score
                        position_score = distance / self.video_width
                        size_diff = abs(1 - size_ratio)
                        match_score = position_score + size_diff * 0.5

                        if match_score < best_score and position_score < POSITION_THRESHOLD / self.video_width:
                            best_score = match_score
                            best_track = track

                if best_track:
                    face.face_id = best_track.face_id
                    best_track.positions[timestamp] = face
                else:
                    # Create new track
                    new_track = FaceTrack(
                        face_id=track_id_counter,
                        positions={timestamp: face}
                    )
                    face.face_id = track_id_counter
                    current_tracks.append(new_track)
                    track_id_counter += 1

        # Filter tracks based on minimum frames (uses configuration constant)
        self.face_tracks = [
            track for track in current_tracks
            if len(track.positions) >= MIN_TRACK_FRAMES
        ]

        # Update statistics
        for track in self.face_tracks:
            track.update_statistics(self.video_width, self.video_height)

        # Merge duplicate tracks
        self._merge_duplicate_tracks()

        # Filter by minimum confidence (uses configuration constant)
        self.face_tracks = [
            track for track in self.face_tracks
            if track.avg_confidence >= MIN_AVG_CONFIDENCE
        ]

        self.face_tracks.sort(key=lambda t: t.avg_area_ratio, reverse=True)
        logger.info(f"Built {len(self.face_tracks)} face tracks")

    def analyze_audio_for_speech(
        self,
        audio_path: str,
        sr: Optional[int] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List:
        """
        Analyze audio file for speech activity using speaker detector.

        Args:
            audio_path: Path to audio file
            sr: Target sample rate (if None, uses native rate)
            start_time: Optional start time in seconds (for analyzing specific segments)
            end_time: Optional end time in seconds

        Returns:
            List of AudioSegment objects
        """
        if not self.enable_speaker_detection or not self.speaker_detector:
            logger.warning("Speaker detection not enabled")
            return []

        if start_time is not None or end_time is not None:
            logger.info(
                f"Analyzing audio segment for speech: {audio_path} "
                f"[{start_time or 0:.1f}s - {end_time or 'end'}s]"
            )
        else:
            logger.info(f"Analyzing audio for speech detection: {audio_path}")

        self.speech_segments = self.speaker_detector.detect_speech_segments(
            audio_path, sr=sr, start_time=start_time, end_time=end_time
        )
        logger.info(f"Detected {len(self.speech_segments)} speech segments")

        return self.speech_segments

    def get_active_speaker_at_time(
        self,
        timestamp: float,
        min_confidence: float = 0.5
    ) -> Optional[FaceBox]:
        """
        Get the face of the active speaker at a specific timestamp.

        Uses speaker diarization (if available) or speech correlation to determine
        which face is most likely speaking, with hysteresis to prevent rapid switching.

        Args:
            timestamp: Time in seconds
            min_confidence: Minimum speech confidence threshold

        Returns:
            FaceBox of active speaker, or None if no speaker detected
        """
        # PRIORITY 1: Use speaker diarization if available
        if self.diarization_segments and self.speaker_to_face_map:
            # Get who is speaking at this timestamp from diarization
            current_speaker = self.get_speaker_at_time(timestamp)

            if current_speaker:
                # Get the face track ID for this speaker
                face_track_id = self.speaker_to_face_map.get(current_speaker)

                if face_track_id is not None:
                    # Find the face track
                    track = next(
                        (t for t in self.face_tracks if t.face_id == face_track_id),
                        None
                    )

                    if track and track.positions:
                        # Get face position from this track
                        track_timestamps = sorted(track.positions.keys())
                        closest_ts = min(track_timestamps, key=lambda ts: abs(ts - timestamp))

                        # Check position staleness
                        time_diff = abs(closest_ts - timestamp)

                        # If diarization face is stale, check for currently detected faces
                        # with high speech correlation - they might be the actual speaker
                        STALENESS_THRESHOLD = 3.0  # seconds - allow temporary occlusions (increased from 0.5)

                        if time_diff > STALENESS_THRESHOLD:
                            # Diarization face is stale - find the best currently visible face
                            # using combined score of speech correlation, confidence, and size

                            # Helper to get average confidence for a track
                            def get_track_avg_confidence(t):
                                if not t.positions:
                                    return 0.0
                                return sum(pos.confidence for pos in t.positions.values()) / len(t.positions)

                            # Find ALL tracks that are currently visible (detected in this frame)
                            current_tracks = [
                                t for t in self.face_tracks
                                if t.face_id != face_track_id and  # Exclude the stale diarization face
                                any(abs(ts - timestamp) < 0.2 for ts in t.positions.keys())  # Must be recent
                            ]

                            if current_tracks:
                                # Score by speech correlation, confidence, size, and centrality
                                # PHASE 2 FIX: Prioritize speech correlation to select actual speakers
                                def get_combined_score(t):
                                    avg_conf = get_track_avg_confidence(t)
                                    # Calculate centrality (distance from center)
                                    center_x_norm = t.avg_position[0] / self.video_width
                                    center_y_norm = t.avg_position[1] / self.video_height
                                    distance_from_center = np.sqrt(
                                        (center_x_norm - 0.5)**2 + (center_y_norm - 0.5)**2
                                    )
                                    max_distance = np.sqrt(0.5**2 + 0.5**2)
                                    centrality = 1.0 - (distance_from_center / max_distance)

                                    # NEW Weights (Phase 2): 50% speech, 25% size, 15% confidence, 10% centrality
                                    # Speech correlation is now the PRIMARY factor for selecting speakers
                                    # This prevents audience members from being selected over actual speakers
                                    return (t.speech_correlation * 0.50 +  # INCREASED from 0.30
                                            t.avg_area_ratio * 0.25 +      # DECREASED from 0.45
                                            avg_conf * 0.15 +               # Same
                                            centrality * 0.10)              # Same

                                # Phase 2: Filter by minimum speech activity
                                # Only consider faces that have meaningful speech correlation
                                # This prevents audience members (speech ~0.3) from being selected
                                MIN_SPEECH_FOR_SPEAKER = 0.40
                                speech_filtered_tracks = [
                                    t for t in current_tracks
                                    if t.speech_correlation >= MIN_SPEECH_FOR_SPEAKER
                                ]
                                
                                if speech_filtered_tracks:
                                    logger.debug(
                                        f"Filtered to {len(speech_filtered_tracks)}/{len(current_tracks)} "
                                        f"tracks with speech >= {MIN_SPEECH_FOR_SPEAKER}"
                                    )
                                    current_tracks = speech_filtered_tracks
                                else:
                                    logger.debug(
                                        f"No tracks with speech >= {MIN_SPEECH_FOR_SPEAKER}, "
                                        f"using all {len(current_tracks)} tracks"
                                    )

                                # Filter by instantaneous confidence (reject very low current frame confidence)
                                MIN_INSTANT_CONFIDENCE = 0.25
                                viable_tracks = []
                                for t in current_tracks:
                                    # Get the most recent detection for this track
                                    recent_ts = min(t.positions.keys(), key=lambda ts: abs(ts - timestamp))
                                    instant_conf = t.positions[recent_ts].confidence
                                    if instant_conf >= MIN_INSTANT_CONFIDENCE:
                                        viable_tracks.append(t)
                                    else:
                                        logger.debug(
                                            f"Rejected Track {t.face_id} in fallback: instant_conf={instant_conf:.2f} < {MIN_INSTANT_CONFIDENCE}"
                                        )

                                # Filter by minimum face size (reject tiny faces < 1% of frame)
                                MIN_FALLBACK_SIZE = 0.01
                                size_filtered_tracks = []
                                for t in viable_tracks:
                                    if t.avg_area_ratio >= MIN_FALLBACK_SIZE:
                                        size_filtered_tracks.append(t)
                                    else:
                                        logger.debug(
                                            f"Rejected Track {t.face_id} in fallback: size={t.avg_area_ratio:.4f} < {MIN_FALLBACK_SIZE}"
                                        )
                                viable_tracks = size_filtered_tracks

                                if not viable_tracks:
                                    logger.debug("No viable tracks after instantaneous confidence filtering")
                                    current_tracks = []  # Trigger fallback to center crop
                                else:
                                    current_tracks = viable_tracks

                                best_track = max(current_tracks, key=get_combined_score) if current_tracks else None

                                if best_track:
                                    best_ts = min(best_track.positions.keys(), key=lambda ts: abs(ts - timestamp))
                                    best_score = get_combined_score(best_track)

                                    logger.debug(
                                        f"Diarization: {current_speaker} -> Face {face_track_id} is stale "
                                        f"({time_diff:.1f}s), using Face {best_track.face_id} instead "
                                        f"(score={best_score:.2f}, speech={best_track.speech_correlation:.2f}, "
                                        f"conf={get_track_avg_confidence(best_track):.2f})"
                                    )
                                    return best_track.positions[best_ts]

                            # No currently visible faces - return None to trigger center crop fallback
                            # This handles wide shots where faces are too small to detect
                            logger.debug(
                                f"Diarization: {current_speaker} -> Face {face_track_id} "
                                f"is stale ({time_diff:.1f}s) and no current faces detected - "
                                f"returning None for center crop fallback"
                            )
                            return None
                        else:
                            logger.debug(
                                f"Diarization: {current_speaker} -> Face {face_track_id} "
                                f"at t={timestamp:.2f}s"
                            )

                        return track.positions[closest_ts]

            # No speaker at this time according to diarization
            # Fall back to largest face
            return self.get_face_position_at_time(timestamp)

        # PRIORITY 2: Fall back to speech correlation method
        # If speaker detection disabled, fall back to largest face
        if not self.enable_speaker_detection or not self.speech_segments or not self.speaker_detector:
            return self.get_face_position_at_time(timestamp)

        # Check if there's speech activity at this time
        is_speech, energy = self.speaker_detector.is_speech_at_time(
            timestamp,
            self.speech_segments,
            min_confidence=min_confidence
        )

        if not is_speech:
            # No speech - just return largest face
            return self.get_face_position_at_time(timestamp)

        # Get all face tracks that have data near this timestamp
        active_tracks = [
            track for track in self.face_tracks
            if any(abs(ts - timestamp) < 0.5 for ts in track.positions.keys())
        ]

        if not active_tracks:
            # Fall back to single face tracking
            return self.get_face_position_at_time(timestamp)

        # Helper to get average confidence for a track
        def get_avg_confidence(track: FaceTrack) -> float:
            if not track.positions:
                return 0.0
            return sum(pos.confidence for pos in track.positions.values()) / len(track.positions)

        # Score each track based on combined factors
        # No threshold filtering - always pick the best by score
        # Confidence is included in score, so low-confidence faces score lower naturally
        def calculate_score(track: FaceTrack) -> float:
            """Calculate composite score for speaker selection."""
            avg_conf = get_avg_confidence(track)
            score = (
                track.speech_correlation * 0.5 +
                avg_conf * 0.3 +  # Higher weight on confidence to favor real faces
                track.avg_area_ratio * 0.1 +
                (0.1 if any(abs(ts - timestamp) < 0.1 for ts in track.positions.keys()) else 0)
            )
            return score

        # Calculate scores for all active tracks - always pick the best one
        track_scores = {track.face_id: calculate_score(track) for track in active_tracks}

        # Find best candidate
        best_track_id = max(track_scores.keys(), key=lambda tid: track_scores[tid])
        best_score = track_scores[best_track_id]

        # Apply hysteresis: require significant confidence margin before switching speakers
        if self.current_active_speaker_id is not None:
            # Check if we should stay with current speaker
            current_track_id = self.current_active_speaker_id

            # Check if current speaker still exists in active tracks
            if current_track_id in track_scores:
                current_score = track_scores[current_track_id]

                # Apply hysteresis margin: new speaker must be significantly better
                # Also check debounce timer to prevent rapid oscillation
                time_since_switch = timestamp - self.last_speaker_switch_time

                if (best_track_id != current_track_id and
                    time_since_switch < self.speaker_switch_debounce):
                    # Within debounce period - stick with current speaker
                    best_track_id = current_track_id
                    logger.debug(
                        f"Staying with speaker {current_track_id} due to debounce "
                        f"(elapsed: {time_since_switch:.3f}s)"
                    )
                elif (best_track_id != current_track_id and
                      best_score < current_score + self.speaker_switch_hysteresis):
                    # New speaker not significantly better - stick with current
                    best_track_id = current_track_id
                    logger.debug(
                        f"Staying with speaker {current_track_id} due to hysteresis "
                        f"(best: {best_score:.3f}, current: {current_score:.3f}, "
                        f"margin: {self.speaker_switch_hysteresis:.3f})"
                    )
                elif best_track_id != current_track_id:
                    # Legitimate switch - update tracking state
                    logger.debug(
                        f"Switching from speaker {current_track_id} to {best_track_id} "
                        f"at t={timestamp:.2f}s (scores: {current_score:.3f} -> {best_score:.3f})"
                    )
                    self.current_active_speaker_id = best_track_id
                    self.last_speaker_switch_time = timestamp
        else:
            # First speaker assignment
            self.current_active_speaker_id = best_track_id
            self.last_speaker_switch_time = timestamp
            logger.debug(f"Initial speaker assignment: {best_track_id} at t={timestamp:.2f}s")

        # Get the selected track
        best_track = next(t for t in active_tracks if t.face_id == best_track_id)

        # Get face position from best track at this timestamp
        # Find closest timestamp in track
        track_timestamps = sorted(best_track.positions.keys())
        closest_ts = min(track_timestamps, key=lambda ts: abs(ts - timestamp))

        return best_track.positions[closest_ts]

    def get_active_speaker_realtime(
        self,
        timestamp: float,
        min_confidence: float = 0.5,
        historical_weight: float = 0.4,
        current_weight: float = 0.6
    ) -> Optional[FaceBox]:
        """
        Get active speaker using real-time audio-visual fusion.

        Combines historical speech correlation with current audio energy
        for more responsive speaker tracking during clip generation.

        Args:
            timestamp: Time in seconds
            min_confidence: Minimum speech confidence threshold
            historical_weight: Weight for historical speech_correlation (0-1)
            current_weight: Weight for current audio energy (0-1)

        Returns:
            FaceBox of active speaker, or None if no speaker detected
        """
        # If speaker detection disabled, fall back to largest face
        if not self.enable_speaker_detection or not self.speech_segments:
            return self.get_face_position_at_time(timestamp)

        # Check if there's speech activity at this time with energy level
        if self.speaker_detector is None:
            return self.get_face_position_at_time(timestamp)
            
        is_speech, current_energy = self.speaker_detector.is_speech_at_time(
            timestamp,
            self.speech_segments,
            min_confidence=min_confidence
        )

        if not is_speech:
            # No speech - just return largest face
            return self.get_face_position_at_time(timestamp)

        # Get all face tracks that have data near this timestamp
        active_tracks = [
            track for track in self.face_tracks
            if any(abs(ts - timestamp) < 0.5 for ts in track.positions.keys())
        ]

        if not active_tracks:
            # Fall back to single face tracking
            return self.get_face_position_at_time(timestamp)

        # Normalize current energy to 0-1 range (energy is typically 0-100+)
        normalized_energy = min(1.0, current_energy / 50.0)  # Assume 50 is high energy

        # Score each track combining historical and current data
        def calculate_realtime_score(track: FaceTrack) -> float:
            """Calculate real-time score with audio-visual fusion."""
            # Historical component: speech correlation
            historical_score = track.speech_correlation

            # Current component: assume track with highest correlation is likely speaking
            # Weight by current audio energy
            current_score = normalized_energy

            # Lip activity component (if available)
            lip_bonus = 0.0
            if track.lip_activity_scores:
                # Find lip score at current timestamp (within 0.2s window)
                nearby_lip_scores = [
                    score for ts, score in track.lip_activity_scores.items()
                    if abs(ts - timestamp) < 0.2
                ]
                if nearby_lip_scores:
                    lip_bonus = np.mean(nearby_lip_scores) * 0.15  # 15% weight for lip movement

            # Combine scores
            composite_score = (
                historical_score * historical_weight +
                current_score * current_weight +
                track.avg_area_ratio * 0.15 +  # Face size bonus (reduced to make room for lip)
                lip_bonus +  # Lip movement bonus
                (0.1 if any(abs(ts - timestamp) < 0.1 for ts in track.positions.keys()) else 0)  # Temporal proximity
            )

            return float(composite_score)

        # Calculate scores for all tracks
        track_scores = {track.face_id: calculate_realtime_score(track) for track in active_tracks}

        # Find best candidate
        best_track_id = max(track_scores.keys(), key=lambda tid: track_scores[tid])
        best_score = track_scores[best_track_id]

        # Apply hysteresis (same as get_active_speaker_at_time)
        if self.current_active_speaker_id is not None:
            current_track_id = self.current_active_speaker_id

            if current_track_id in track_scores:
                current_score = track_scores[current_track_id]
                time_since_switch = timestamp - self.last_speaker_switch_time

                if (best_track_id != current_track_id and
                    time_since_switch < self.speaker_switch_debounce):
                    best_track_id = current_track_id
                elif (best_track_id != current_track_id and
                      best_score < current_score + self.speaker_switch_hysteresis):
                    best_track_id = current_track_id
                elif best_track_id != current_track_id:
                    logger.debug(
                        f"[Realtime] Switching speaker {current_track_id} -> {best_track_id} "
                        f"at t={timestamp:.2f}s (energy={current_energy:.1f})"
                    )
                    self.current_active_speaker_id = best_track_id
                    self.last_speaker_switch_time = timestamp
        else:
            self.current_active_speaker_id = best_track_id
            self.last_speaker_switch_time = timestamp

        # Get the selected track
        best_track = next(t for t in active_tracks if t.face_id == best_track_id)

        # Get face position from best track at this timestamp
        track_timestamps = sorted(best_track.positions.keys())
        closest_ts = min(track_timestamps, key=lambda ts: abs(ts - timestamp))

        return best_track.positions[closest_ts]

    def correlate_faces_with_speech(self):
        """
        Correlate detected face tracks with speech activity.

        Updates speech_correlation scores for each face track based on
        how well the face's presence aligns with detected speech segments.
        """
        if not self.enable_speaker_detection or not self.speech_segments or not self.speaker_detector:
            logger.info("Speaker detection not enabled or no speech segments - skipping correlation")
            return

        logger.info(f"Correlating {len(self.face_tracks)} face tracks with {len(self.speech_segments)} speech segments")

        for track in self.face_tracks:
            # Count how many times this face appears during speech vs silence
            speech_appearances = 0
            total_appearances = len(track.positions)

            for timestamp in track.positions.keys():
                is_speech, _ = self.speaker_detector.is_speech_at_time(
                    timestamp,
                    self.speech_segments,
                    min_confidence=0.5
                )
                if is_speech:
                    speech_appearances += 1

            # Calculate correlation ratio
            track.speech_correlation = (
                speech_appearances / total_appearances
                if total_appearances > 0 else 0.0
            )

            logger.debug(
                f"Face track {track.face_id}: "
                f"{speech_appearances}/{total_appearances} appearances during speech "
                f"(correlation: {track.speech_correlation:.2f})"
            )

        # Log summary
        if self.face_tracks:
            correlations = [t.speech_correlation for t in self.face_tracks]
            logger.info(
                f"Speech correlation scores: "
                f"min={min(correlations):.2f}, max={max(correlations):.2f}, "
                f"mean={np.mean(correlations):.2f}"
            )

    def run_speaker_diarization(
        self,
        audio_path: str,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> List:
        """
        Run speaker diarization to identify WHO is speaking WHEN.

        Args:
            audio_path: Path to audio file
            min_speakers: Minimum number of speakers (None = auto-detect)
            max_speakers: Maximum number of speakers (None = auto-detect)

        Returns:
            List of SpeakerSegment objects
        """
        if not SPEAKER_DIARIZATION_AVAILABLE:
            logger.warning("Speaker diarization not available. Install pyannote-audio.")
            return []

        logger.info(f"Running speaker diarization on: {audio_path}")

        try:
            # Initialize diarizer if not already done
            if self.diarizer is None:
                self.diarizer = SpeakerDiarizer(
                    use_gpu=self.use_gpu_actual,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )

            # Run diarization
            self.diarization_segments = self.diarizer.diarize(
                audio_path,
                min_speakers=min_speakers,
                max_speakers=max_speakers
            )

            logger.info(f"Diarization complete: {len(self.diarization_segments)} segments")
            return self.diarization_segments

        except Exception as e:
            logger.error(f"Speaker diarization failed: {e}")
            return []

    def build_speaker_face_mapping(self):
        """
        Build mapping between diarization speakers and face tracks.

        Uses temporal correlation: for each speaker, find which face track
        appears most consistently during that speaker's segments.
        """
        if not self.diarization_segments or not self.face_tracks:
            logger.warning("Cannot build speaker-face mapping: missing diarization or face tracks")
            return

        logger.info("Building speaker-to-face mapping...")

        # Get unique speakers from diarization
        speakers = set(seg.speaker for seg in self.diarization_segments)
        logger.info(f"Found {len(speakers)} speakers in diarization")

        # For each speaker, calculate correlation with each face track
        speaker_face_scores: Dict[str, Dict[int, float]] = {}

        for speaker in speakers:
            speaker_face_scores[speaker] = {}

            # Get all segments for this speaker
            speaker_segs = [s for s in self.diarization_segments if s.speaker == speaker]
            total_speaker_time = sum(s.duration for s in speaker_segs)

            if total_speaker_time == 0:
                continue

            # For each face track, calculate how much it appears during this speaker's time
            for track in self.face_tracks:
                overlap_time = 0.0

                # Calculate expected FPS from actual track data instead of hardcoding
                if len(track.positions) >= 2:
                    track_timestamps = sorted(track.positions.keys())
                    track_duration_calc = track_timestamps[-1] - track_timestamps[0]
                    expected_fps = len(track.positions) / track_duration_calc if track_duration_calc > 0 else 7.5
                else:
                    expected_fps = 7.5  # Fallback for very short tracks

                for seg in speaker_segs:
                    # Count face track positions that fall within this speaker segment
                    positions_in_segment = [
                        ts for ts in track.positions.keys()
                        if seg.start_time <= ts <= seg.end_time
                    ]

                    if positions_in_segment:
                        # Calculate coverage: what percentage of expected detections did we get?
                        expected_detections = seg.duration * expected_fps
                        if expected_detections > 0:
                            coverage_ratio = min(1.0, len(positions_in_segment) / expected_detections)
                            overlap_time += seg.duration * coverage_ratio
                        else:
                            overlap_time += seg.duration  # Short segment, give full credit

                # Calculate overlap ratio
                overlap_ratio = overlap_time / total_speaker_time if total_speaker_time > 0 else 0

                # Calculate track consistency (penalize fragmented tracks)
                # A consistent track should have detections throughout its duration
                if len(track.positions) >= 2:
                    track_timestamps = sorted(track.positions.keys())
                    track_duration = track_timestamps[-1] - track_timestamps[0]
                    if track_duration > 0:
                        expected_track_detections = track_duration * expected_fps
                        consistency = min(1.0, len(track.positions) / max(1, expected_track_detections))
                    else:
                        consistency = 0.5  # Single point in time
                else:
                    consistency = 0.1  # Very short track, penalize heavily

                # Size bonus (larger faces are more likely main speakers)
                size_bonus = track.avg_area_ratio

                # Position-based scoring (for 2-person podcasts)
                position_score = 0.0
                if track.avg_position[0] < self.video_width * 0.4:  # Left side
                    if speaker.endswith("_00"):
                        position_score = 0.1
                elif track.avg_position[0] > self.video_width * 0.6:  # Right side
                    if speaker.endswith("_01"):
                        position_score = 0.1

                # Calculate foreground score (larger faces are more likely foreground)
                # Normalize to 5% area as "max foreground"
                foreground_score = min(1.0, track.avg_area_ratio / 0.05)

                # Calculate centrality score (faces near center are more likely main speakers)
                # Distance from center normalized to 0-1 (0 = edge, 1 = center)
                center_x_norm = track.avg_position[0] / self.video_width
                center_y_norm = track.avg_position[1] / self.video_height
                distance_from_center = np.sqrt(
                    (center_x_norm - 0.5)**2 + (center_y_norm - 0.5)**2
                )
                max_distance = np.sqrt(0.5**2 + 0.5**2)  # Corner distance
                centrality_score = 1.0 - (distance_from_center / max_distance)

                # Calculate confidence score (higher detection confidence = more reliable)
                confidence_score = track.avg_confidence

                # Progressive edge penalty (gradual penalty from center outward)
                # Faces near center (x=0.5) get no penalty, faces near edges get increasing penalty
                normalized_x = track.avg_position[0] / self.video_width
                center_distance = abs(normalized_x - 0.5)  # Distance from center (0 to 0.5)
                # Progressive penalty: center=1.0 (no penalty), edge=0.5 (50% penalty)
                edge_penalty = max(0.5, 1.0 - (center_distance * 1.0))

                # PHASE 4: Updated scoring formula to prioritize speech correlation
                # - 35% speech correlation (INCREASED from 25% - who's actually speaking)
                # - 20% overlap ratio (temporal match with diarization)
                # - 20% foreground/size (larger faces are main speakers)
                # - 10% centrality (DECREASED from 25% - position less important)
                # - 10% confidence (detection quality)
                # - 5% consistency (temporal consistency)
                final_score = (
                    track.speech_correlation * 0.35 +  # INCREASED from 0.25
                    overlap_ratio * 0.20 +             # INCREASED from 0.15
                    foreground_score * 0.20 +          # INCREASED from 0.15
                    centrality_score * 0.10 +          # DECREASED from 0.25
                    confidence_score * 0.10 +          # Same
                    consistency * 0.05                 # DECREASED from 0.10
                ) * edge_penalty
                speaker_face_scores[speaker][track.face_id] = final_score

                logger.debug(
                    f"  {speaker} -> Track {track.face_id}: "
                    f"speech={track.speech_correlation:.2f}, central={centrality_score:.2f}, "
                    f"fg={foreground_score:.2f}, overlap={overlap_ratio:.2f}, "
                    f"conf={confidence_score:.2f}, consist={consistency:.2f}, "
                    f"edge_pen={edge_penalty:.2f}, total={final_score:.2f}"
                )

        # Assign speakers to face tracks (greedy assignment)
        # Each speaker maps to their highest-scoring unassigned face track
        assigned_faces = set()
        self.speaker_to_face_map = {}
        self.face_to_speaker_map = {}

        # Sort speakers by their best score (assign most confident first)
        speaker_order = sorted(
            speakers,
            key=lambda s: max(speaker_face_scores[s].values()) if speaker_face_scores[s] else 0,
            reverse=True
        )

        for speaker in speaker_order:
            if not speaker_face_scores[speaker]:
                continue

            # Find best unassigned face track for this speaker
            best_face_id = None
            best_score = -1

            for face_id, score in speaker_face_scores[speaker].items():
                if face_id not in assigned_faces and score > best_score:
                    best_score = score
                    best_face_id = face_id

            if best_face_id is not None:
                self.speaker_to_face_map[speaker] = best_face_id
                self.face_to_speaker_map[best_face_id] = speaker
                assigned_faces.add(best_face_id)

                # Find the face track to get position info
                track = next((t for t in self.face_tracks if t.face_id == best_face_id), None)
                pos_str = f"pos=({track.avg_position[0]}, {track.avg_position[1]})" if track else ""

                logger.info(
                    f"Mapped {speaker} -> Face Track {best_face_id} "
                    f"(score={best_score:.2f}, {pos_str})"
                )

        logger.info(f"Speaker-face mapping complete: {len(self.speaker_to_face_map)} mappings")

    def get_speaker_at_time(self, timestamp: float) -> Optional[str]:
        """
        Get the diarization speaker label at a specific timestamp.

        Args:
            timestamp: Time in seconds

        Returns:
            Speaker label (e.g., "SPEAKER_00") or None
        """
        for seg in self.diarization_segments:
            if seg.start_time <= timestamp <= seg.end_time:
                return seg.speaker
        return None

    def get_face_for_speaker(self, speaker: str) -> Optional[int]:
        """
        Get the face track ID for a diarization speaker.

        Args:
            speaker: Speaker label (e.g., "SPEAKER_00")

        Returns:
            Face track ID or None
        """
        return self.speaker_to_face_map.get(speaker)

    def detect_face_groups(
        self,
        timestamp: float,
        separation_threshold: float = FACE_SEPARATION_THRESHOLD
    ) -> Dict[str, Any]:
        """
        Analyze faces at timestamp to detect spatial grouping.

        Determines if faces are separated (far apart), grouped (close together),
        or if there's only a single face.

        Args:
            timestamp: Time in seconds to analyze
            separation_threshold: Distance threshold (as fraction of frame width)
                                 for considering faces "separated" (uses config constant)

        Returns:
            Dictionary with:
                - mode: "single", "grouped", or "separated"
                - faces: List of FaceBox objects detected
                - separation_score: 0-1, higher means more separated
        """
        # Get all detected faces near this timestamp (within 0.5s window)
        nearby_timestamps = [
            ts for ts in sorted(self.face_positions.keys())
            if abs(ts - timestamp) <= 0.5
        ]

        if not nearby_timestamps:
            return {
                "mode": "single",
                "faces": [],
                "separation_score": 0.0
            }

        # Get the closest timestamp
        closest_ts = min(nearby_timestamps, key=lambda ts: abs(ts - timestamp))

        # For now, we only have single-face tracking in face_positions
        # But we can detect if there are multiple face_tracks with data
        if not self.face_tracks:
            # Fallback to legacy single-face mode
            face = self.face_positions.get(closest_ts)
            return {
                "mode": "single",
                "faces": [face] if face else [],
                "separation_score": 0.0
            }

        # Get all faces from tracks that have data near this timestamp
        active_faces = []
        for track in self.face_tracks:
            # Find closest timestamp in this track
            track_timestamps = [ts for ts in track.positions.keys() if abs(ts - timestamp) <= 0.5]
            if track_timestamps:
                closest_track_ts = min(track_timestamps, key=lambda ts: abs(ts - timestamp))
                active_faces.append(track.positions[closest_track_ts])

        if len(active_faces) <= 1:
            return {
                "mode": "single",
                "faces": active_faces,
                "separation_score": 0.0
            }

        # Sort faces by size (largest first)
        active_faces.sort(key=lambda f: f.area, reverse=True)

        # Analyze top 2 faces for separation
        face1, face2 = active_faces[0], active_faces[1]
        separation_score = self._calculate_face_separation_score(face1, face2)

        # Determine mode based on separation
        if separation_score >= separation_threshold:
            mode = "separated"
        else:
            mode = "grouped"

        return {
            "mode": mode,
            "faces": active_faces[:2],  # Return top 2 faces
            "separation_score": separation_score
        }

    def _calculate_face_separation_score(
        self,
        face1: FaceBox,
        face2: FaceBox
    ) -> float:
        """
        Calculate spatial separation score between two faces.

        Args:
            face1: First face bounding box
            face2: Second face bounding box

        Returns:
            Separation score (0-1), where:
                - 0.0 = faces overlap or very close
                - 0.5 = moderate separation
                - 1.0 = faces are on opposite sides of frame
        """
        if not self.video_width or self.video_width == 0:
            return 0.0

        center1_x, center1_y = face1.center
        center2_x, center2_y = face2.center

        # Calculate horizontal distance as percentage of frame width
        horizontal_distance = abs(center2_x - center1_x) / self.video_width

        # Calculate gap between faces (if they don't overlap)
        if face1.x < face2.x:
            # face1 is on the left
            face1_right = face1.x + face1.width
            gap = max(0, face2.x - face1_right)
        else:
            # face2 is on the left
            face2_right = face2.x + face2.width
            gap = max(0, face1.x - face2_right)

        gap_ratio = gap / self.video_width

        # Separation score is the maximum of distance and gap
        # (either metric can indicate separation)
        # Reduced gap weight from 2.0 to 0.5 to prevent oversensitivity
        separation_score = max(horizontal_distance, gap_ratio * 0.5)

        # Clamp to [0, 1]
        return min(1.0, separation_score)

    def get_separated_faces_at_time(
        self,
        timestamp: float,
        separation_threshold: float = FACE_SEPARATION_THRESHOLD
    ) -> Optional[List[FaceBox]]:
        """
        Get the 2 most prominent separated faces at a timestamp.

        This is used by the clip generator to create split-screen layouts.

        Args:
            timestamp: Time in seconds
            separation_threshold: Minimum separation score required (uses config constant)

        Returns:
            List of 2 FaceBox objects if faces are separated, None otherwise
        """
        face_group = self.detect_face_groups(timestamp, separation_threshold)

        if face_group["mode"] == "separated" and len(face_group["faces"]) >= 2:
            return face_group["faces"][:2]  # Return top 2 faces

        return None

    def get_optimal_crop_box(
        self,
        start_time: float,
        end_time: float,
        padding_factor: float = 1.5
    ) -> CropBox:
        """
        Calculate optimal crop box for a video segment (9:16 format).

        Uses face positions to determine where to crop the video horizontally,
        ensuring the speaker stays centered throughout the clip.

        Args:
            start_time: Clip start time in seconds
            end_time: Clip end time in seconds
            padding_factor: How much padding around face (1.0 = tight, 2.0 = loose)

        Returns:
            CropBox defining the optimal crop region
        """
        # Get face positions within the time range
        relevant_faces = [
            face for timestamp, face in self.face_positions.items()
            if start_time <= timestamp <= end_time
        ]

        if not relevant_faces:
            logger.warning(f"No faces detected in clip {start_time:.1f}s-{end_time:.1f}s, using center crop")
            return self._get_center_crop_box()

        # Calculate average face center position (for stable crop)
        avg_face_center_x = int(np.mean([face.center[0] for face in relevant_faces]))
        avg_face_center_y = int(np.mean([face.center[1] for face in relevant_faces]))

        # Calculate target width for 9:16 aspect ratio
        target_width = int(self.video_height * self.target_aspect)

        # If video is already narrower than target, use full width
        if self.video_width <= target_width:
            logger.info("Video already narrow enough for 9:16, no horizontal crop needed")
            return CropBox(x=0, y=0, width=self.video_width, height=self.video_height)

        # Calculate crop box centered on average face position
        crop_x = avg_face_center_x - target_width // 2

        # Ensure crop box stays within video bounds
        crop_x = max(0, min(crop_x, self.video_width - target_width))

        logger.info(f"Crop box for {start_time:.1f}s-{end_time:.1f}s: x={crop_x}, width={target_width}, centered on face at ({avg_face_center_x}, {avg_face_center_y})")

        return CropBox(
            x=crop_x,
            y=0,
            width=target_width,
            height=self.video_height
        )

    def _get_center_crop_box(self) -> CropBox:
        """
        Get center crop box when no faces detected (fallback).

        Returns:
            CropBox for center-cropped 9:16 video
        """
        target_width = int(self.video_height * self.target_aspect)

        if self.video_width <= target_width:
            return CropBox(x=0, y=0, width=self.video_width, height=self.video_height)

        crop_x = (self.video_width - target_width) // 2

        return CropBox(
            x=crop_x,
            y=0,
            width=target_width,
            height=self.video_height
        )

    def get_face_position_with_persistence(
        self,
        timestamp: float,
        persistence_window: float = FACE_PERSISTENCE_WINDOW
    ) -> Optional[FaceBox]:
        """
        Get face position with temporal persistence for speech-active periods.

        When no face is detected at the exact timestamp but speech is active,
        this returns the most recent face position within the persistence window.
        This prevents false switches to horizontal mode during wide shots.

        Args:
            timestamp: Time in seconds
            persistence_window: How far back to look for a face (uses config constant)

        Returns:
            FaceBox (current, interpolated, or persisted), or None if no face found
        """
        # First try to get face at exact time or interpolated
        face = self.get_face_position_at_time(timestamp)
        if face:
            return face

        # No face at this time - check if we should persist the last known face
        if not self.face_positions:
            return None

        # Find the most recent face within persistence window
        recent_timestamps = [
            ts for ts in self.face_positions.keys()
            if timestamp - persistence_window <= ts < timestamp
        ]

        if not recent_timestamps:
            return None

        # Get the most recent face
        last_face_time = max(recent_timestamps)
        last_face = self.face_positions[last_face_time]

        # Check if speech is active (if speaker detection enabled)
        # If speech is active, persist the last face to avoid false horizontal mode
        if self.enable_speaker_detection and self.speech_segments and self.speaker_detector:
            is_speech, energy = self.speaker_detector.is_speech_at_time(
                timestamp, self.speech_segments, min_confidence=0.3
            )
            if is_speech:
                logger.debug(
                    f"Persisting face from {last_face_time:.2f}s at t={timestamp:.2f}s "
                    f"(speech active, energy={energy:.1f})"
                )
                return last_face

        return None

    def get_face_position_at_time(self, timestamp: float) -> Optional[FaceBox]:
        """
        Get interpolated face position at a specific timestamp.

        Uses linear interpolation between detected face positions for smooth tracking.

        Args:
            timestamp: Time in seconds

        Returns:
            Interpolated FaceBox, or None if no nearby face positions found
        """
        if not self.face_positions:
            return None

        # Get sorted timestamps
        timestamps = sorted(self.face_positions.keys())

        # Find exact match
        if timestamp in self.face_positions:
            return self.face_positions[timestamp]

        # Find bounding timestamps for interpolation
        before_ts = None
        after_ts = None

        for ts in timestamps:
            if ts <= timestamp:
                before_ts = ts
            elif ts > timestamp and after_ts is None:
                after_ts = ts
                break

        # If timestamp is before all detections
        if before_ts is None and after_ts is not None:
            return self.face_positions[after_ts]

        # If timestamp is after all detections
        if after_ts is None and before_ts is not None:
            return self.face_positions[before_ts]

        # If we have no face positions at all
        if before_ts is None and after_ts is None:
            return None

        # Type guard: ensure both timestamps are valid before interpolation
        if before_ts is None or after_ts is None:
            return None

        # Interpolate between before and after
        face_before = self.face_positions[before_ts]
        face_after = self.face_positions[after_ts]

        # Calculate interpolation factor
        time_diff = after_ts - before_ts
        if time_diff == 0:
            return face_before

        t = (timestamp - before_ts) / time_diff

        # Linear interpolation of face box properties
        interpolated_x = int(face_before.x + t * (face_after.x - face_before.x))
        interpolated_y = int(face_before.y + t * (face_after.y - face_before.y))
        interpolated_w = int(face_before.width + t * (face_after.width - face_before.width))
        interpolated_h = int(face_before.height + t * (face_after.height - face_before.height))
        interpolated_conf = face_before.confidence + t * (face_after.confidence - face_before.confidence)

        return FaceBox(
            x=interpolated_x,
            y=interpolated_y,
            width=interpolated_w,
            height=interpolated_h,
            confidence=interpolated_conf
        )

    def get_dynamic_crop_box_at_time(
        self,
        timestamp: float,
        padding_factor: float = 1.5,
        smoothing_window: float = SMOOTHING_WINDOW,
        content_timeline: Optional[List] = None
    ) -> CropBox:
        """
        Get crop box for a specific timestamp with adaptive smoothing for stable tracking.

        If speaker detection is enabled, this will prioritize the active speaker's face.
        Smoothing window is automatically reduced near mode transitions to prevent jitter.

        Args:
            timestamp: Time in seconds
            padding_factor: How much padding around face (1.0 = tight, 2.0 = loose)
            smoothing_window: Window in seconds to average face positions (uses config constant)
            content_timeline: Optional list of ContentSegment objects for adaptive smoothing

        Returns:
            CropBox for the specified timestamp
        """
        # Adaptive smoothing: reduce window near mode transitions
        if content_timeline:
            # Find if we're near a segment boundary (within 0.5s)
            for i, segment in enumerate(content_timeline):
                # Check distance to segment start/end
                dist_to_start = abs(timestamp - segment.start_time)
                dist_to_end = abs(timestamp - segment.end_time)

                # Check if mode changes at this boundary
                mode_changes = False
                if i > 0 and dist_to_start < 0.5:
                    # Near start boundary - check if mode changed from previous
                    if content_timeline[i-1].mode != segment.mode:
                        mode_changes = True
                if i < len(content_timeline) - 1 and dist_to_end < 0.5:
                    # Near end boundary - check if mode changes to next
                    if content_timeline[i+1].mode != segment.mode:
                        mode_changes = True

                if mode_changes:
                    # Near a mode transition - use tighter smoothing window
                    smoothing_window = 0.5
                    logger.debug(
                        f"Adaptive smoothing: reduced window to 0.5s near mode transition at t={timestamp:.2f}s"
                    )
                    break

        # If speaker detection enabled, get active speaker's face
        if self.enable_speaker_detection and self.speech_segments:
            speaker_face = self.get_active_speaker_at_time(timestamp)
            if not speaker_face:
                # No active speaker detected (e.g., wide shot with no detectable faces)
                # Use center crop as fallback
                return self._get_center_crop_box()

            # Use speaker's face with smoothing window
            relevant_faces = [
                face for ts, face in self.face_positions.items()
                if timestamp - smoothing_window / 2 <= ts <= timestamp + smoothing_window / 2
                # Filter to faces similar in position to speaker (within 20% of frame width)
                and abs(face.center[0] - speaker_face.center[0]) < (self.video_width * 0.2)
            ]

            if relevant_faces:
                avg_face_center_x = int(np.mean([face.center[0] for face in relevant_faces]))
            else:
                avg_face_center_x = speaker_face.center[0]

            # Calculate target width for 9:16 aspect ratio
            target_width = int(self.video_height * self.target_aspect)

            # If video is already narrower than target, use full width
            if self.video_width <= target_width:
                return CropBox(x=0, y=0, width=self.video_width, height=self.video_height)

            # Calculate crop box centered on speaker
            crop_x = avg_face_center_x - target_width // 2
            crop_x = max(0, min(crop_x, self.video_width - target_width))

            return CropBox(
                x=crop_x,
                y=0,
                width=target_width,
                height=self.video_height
            )

        # Legacy behavior: use largest face with smoothing
        # Get face positions within smoothing window
        relevant_faces = [
            face for ts, face in self.face_positions.items()
            if timestamp - smoothing_window / 2 <= ts <= timestamp + smoothing_window / 2
        ]

        if not relevant_faces:
            # Fallback to interpolated position
            face = self.get_face_position_at_time(timestamp)
            if face:
                relevant_faces = [face]
            else:
                return self._get_center_crop_box()

        # Calculate smoothed face center position
        avg_face_center_x = int(np.mean([face.center[0] for face in relevant_faces]))

        # Calculate target width for 9:16 aspect ratio
        target_width = int(self.video_height * self.target_aspect)

        # If video is already narrower than target, use full width
        if self.video_width <= target_width:
            return CropBox(x=0, y=0, width=self.video_width, height=self.video_height)

        # Calculate crop box centered on smoothed face position
        crop_x = avg_face_center_x - target_width // 2

        # Ensure crop box stays within video bounds
        crop_x = max(0, min(crop_x, self.video_width - target_width))

        return CropBox(
            x=crop_x,
            y=0,
            width=target_width,
            height=self.video_height
        )

    def compute_smoothed_trajectory(
        self,
        start_time: float,
        end_time: float,
        smoothing_strength: int = 11,
        fps: float = 30.0,
        filter_type: str = "savgol"
    ) -> Optional[Callable[[float], float]]:
        """
        Pre-compute smoothed face trajectory using advanced filtering.

        This creates a smooth interpolation function that eliminates jumpy camera motion
        when tracking faces. The result is professional-quality smooth camera movement.

        Args:
            start_time: Clip start time in seconds
            end_time: Clip end time in seconds
            smoothing_strength: Window length for Savitzky-Golay filter (must be odd)
                               - 5: Light smoothing (more responsive, slight jitter)
                               - 11: Medium smoothing (balanced, recommended)
                               - 21: Strong smoothing (very smooth, may lag on fast motion)
            fps: Video frame rate (used for interpolation)
            filter_type: Type of filter to use
                        - "savgol": Savitzky-Golay filter (default, good for general use)
                        - "one_euro": One-Euro filter (adaptive, best for variable motion)
                        - "both": Apply both filters in sequence (maximum smoothness)

        Returns:
            Interpolation function that takes timestamp and returns smoothed x-coordinate,
            or None if insufficient face data
        """
        # Get face positions within the time range
        relevant_timestamps = [
            ts for ts in sorted(self.face_positions.keys())
            if start_time <= ts <= end_time
        ]

        if len(relevant_timestamps) < 4:
            logger.warning(
                f"Insufficient face data for smoothing ({len(relevant_timestamps)} points), "
                "falling back to regular tracking"
            )
            return None

        # Extract x-coordinates of face centers
        x_positions = np.array([self.face_positions[ts].center[0] for ts in relevant_timestamps])
        timestamps_array = np.array(relevant_timestamps)

        try:
            # Apply selected filtering method
            if filter_type == "one_euro":
                # Use One-Euro filter for adaptive smoothing
                smoothed_x = smooth_trajectory_with_one_euro(
                    timestamps_array,
                    x_positions,
                    fps=fps,
                    min_cutoff=1.0,  # Balanced smoothing
                    beta=0.007  # Moderate adaptation to velocity
                )
                logger.info(
                    f"Computed One-Euro smoothed trajectory for {start_time:.1f}s-{end_time:.1f}s "
                    f"({len(relevant_timestamps)} points)"
                )

            elif filter_type == "both":
                # Apply One-Euro first, then Savitzky-Golay for maximum smoothness
                intermediate_x = smooth_trajectory_with_one_euro(
                    timestamps_array,
                    x_positions,
                    fps=fps,
                    min_cutoff=1.0,
                    beta=0.007
                )

                # Then apply Savitzky-Golay
                window_length = min(smoothing_strength, len(intermediate_x))
                if window_length % 2 == 0:
                    window_length -= 1
                window_length = max(3, window_length)
                polyorder = min(3, window_length - 1)

                smoothed_x = savgol_filter(
                    intermediate_x,
                    window_length=window_length,
                    polyorder=polyorder,
                    mode='nearest'
                )
                logger.info(
                    f"Computed dual-filtered trajectory for {start_time:.1f}s-{end_time:.1f}s "
                    f"(One-Euro + Savitzky-Golay, {len(relevant_timestamps)} points)"
                )

            else:  # "savgol" (default)
                # Ensure smoothing window doesn't exceed data length
                window_length = min(smoothing_strength, len(x_positions))
                # Window length must be odd
                if window_length % 2 == 0:
                    window_length -= 1
                # Window length must be at least 3
                window_length = max(3, window_length)

                # Polynomial order must be less than window length
                polyorder = min(3, window_length - 1)

                # Apply Savitzky-Golay filter for smooth trajectory
                smoothed_x = savgol_filter(
                    x_positions,
                    window_length=window_length,
                    polyorder=polyorder,
                    mode='nearest'
                )
                logger.info(
                    f"Computed Savitzky-Golay smoothed trajectory for {start_time:.1f}s-{end_time:.1f}s "
                    f"({len(relevant_timestamps)} points, window={window_length}, poly={polyorder})"
                )

            # Create cubic spline interpolation for smooth lookup at any timestamp
            # fill_value="extrapolate" allows extrapolation beyond data range automatically
            interpolator = interp1d(
                relevant_timestamps,
                smoothed_x,
                kind='cubic',
                bounds_error=False,
                fill_value=0.0  # Changed from "extrapolate" for type compatibility
            )

            return interpolator

        except Exception as e:
            logger.error(f"Failed to compute smoothed trajectory with {filter_type}: {e}")
            return None

    def get_crop_box_from_position(self, face_center_x: float) -> CropBox:
        """
        Calculate crop box from a face center x-coordinate.

        Helper method for use with pre-computed smoothed trajectories.

        Args:
            face_center_x: X-coordinate of face center

        Returns:
            CropBox centered on the face position
        """
        # Calculate target width for 9:16 aspect ratio
        target_width = int(self.video_height * self.target_aspect)

        # If video is already narrower than target, use full width
        if self.video_width <= target_width:
            return CropBox(x=0, y=0, width=self.video_width, height=self.video_height)

        # Calculate crop box centered on face position
        crop_x = int(face_center_x - target_width // 2)

        # Ensure crop box stays within video bounds
        crop_x = max(0, min(crop_x, self.video_width - target_width))

        return CropBox(
            x=crop_x,
            y=0,
            width=target_width,
            height=self.video_height
        )

    def get_face_coverage_percentage(self, start_time: float, end_time: float) -> float:
        """
        Calculate what percentage of the time range has face detections.

        Args:
            start_time: Start time in seconds
            end_time: End time in seconds

        Returns:
            Percentage (0-100) of time with face detections
        """
        if not self.face_positions:
            return 0.0

        timestamps_in_range = [
            ts for ts in self.face_positions.keys()
            if start_time <= ts <= end_time
        ]

        if not timestamps_in_range:
            return 0.0

        # Estimate coverage based on sampled points
        duration = end_time - start_time
        time_between_samples = 2.0 / 30.0  # Assuming sample_rate=2, ~15 samples per second at 30fps
        expected_samples = duration / time_between_samples

        coverage = (len(timestamps_in_range) / expected_samples) * 100 if expected_samples > 0 else 0
        return min(100.0, coverage)

    def get_quality_metrics(
        self,
        start_time: float = 0.0,
        end_time: Optional[float] = None
    ):
        """
        Get tracking quality metrics for analysis.

        Args:
            start_time: Start time for metrics calculation
            end_time: End time (None = use full duration)

        Returns:
            TrackingQualityMetrics object or None if metrics disabled
        """
        if not self.enable_quality_metrics or not self.metrics_calculator:
            return None

        if end_time is None:
            timestamps = list(self.face_positions.keys())
            end_time = max(timestamps) if timestamps else start_time

        return self.metrics_calculator.compute_metrics(
            face_positions=self.face_positions,
            face_tracks=self.face_tracks,
            start_time=start_time,
            end_time=end_time,
            video_width=self.video_width,
            video_height=self.video_height,
            speech_segments=self.speech_segments if self.enable_speaker_detection else None,
            scene_changes=self.scene_changes if self.enable_scene_detection else None
        )

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'opencv_detector') and self.opencv_detector is not None:
            # OpenCV detector doesn't need explicit cleanup
            pass
        self.face_positions.clear()

        # Cleanup enhancement modules
        if hasattr(self, 'face_recognition') and self.face_recognition:
            self.face_recognition.cleanup()
        if hasattr(self, 'scene_detector') and self.scene_detector:
            self.scene_detector.cleanup()
