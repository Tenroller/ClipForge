"""
YOLO Person Detector for PodcastClips.

Uses YOLOv8 to detect persons in video frames when face detection fails.
This serves as a fallback for interview scenarios where profile faces
are not detected by the primary face detector.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from loguru import logger as loguru_logger

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False
    loguru_logger.warning("ultralytics not available - YOLO person detection disabled")

logger = loguru_logger.bind(name="PodcastClips.person_detector_yolo")

# YOLO model options (from smallest to largest)
# - yolov8n.pt: Nano (~6MB) - fastest, lowest accuracy
# - yolov8s.pt: Small (~22MB) - good balance
# - yolov8m.pt: Medium (~52MB) - better accuracy (RECOMMENDED for GPU)
# - yolov8l.pt: Large (~87MB) - high accuracy
# - yolov8x.pt: Extra Large (~137MB) - highest accuracy
DEFAULT_MODEL = "yolov8s.pt"  # Small model for CPU balance

# COCO class ID for person
PERSON_CLASS_ID = 0


@dataclass
class PersonBox:
    """Represents a detected person bounding box."""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    track_id: Optional[int] = None
    
    @property
    def center(self) -> Tuple[float, float]:
        """Get center point of the bounding box."""
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    @property
    def area(self) -> int:
        """Get area of the bounding box."""
        return self.width * self.height
    
    @property
    def top_third_center(self) -> Tuple[float, float]:
        """
        Get center of top third of bounding box (approximate head region).
        Useful for estimating face position from full-body detection.
        """
        head_height = self.height / 3
        return (self.x + self.width / 2, self.y + head_height / 2)
    
    def to_face_estimate(self) -> Tuple[int, int, int, int]:
        """
        Estimate face bounding box from person detection.
        
        For seated subjects (typical in interviews), the detection
        is mainly upper body, so face is a larger proportion.
        Uses aspect ratio heuristic to detect seated vs standing.
        
        Returns:
            Tuple of (x, y, width, height) for estimated face region.
        """
        # Heuristic: if aspect ratio suggests seated subject (detection is 
        # wider than tall or square-ish), use larger face proportion
        aspect_ratio = self.height / self.width if self.width > 0 else 1.0
        
        if aspect_ratio < 1.3:  # Wide/short detection = likely seated/upper body only
            # Seated: face is ~25-30% of visible height since we see less body
            face_height = int(self.height * 0.28)
            face_width = int(self.width * 0.5)
        else:  # Standing: face is ~15-18% of full body height
            face_height = int(self.height * 0.18)
            face_width = int(self.width * 0.6)
        
        # Center the face box horizontally
        face_x = self.x + (self.width - face_width) // 2
        face_y = self.y + int(self.height * 0.02)  # Small offset from top
        
        return (face_x, face_y, face_width, face_height)


class YOLOPersonDetector:
    """
    Person detector using YOLOv8.
    
    Detects full-body persons in video frames, useful as a fallback
    when face detection fails (e.g., profile faces in interviews).
    """
    
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        confidence_threshold: float = 0.5,
        use_gpu: bool = False,
        enable_tracking: bool = True
    ):
        """
        Initialize YOLO person detector.
        
        Args:
            model_name: YOLO model to use (e.g., 'yolov8m.pt')
            confidence_threshold: Minimum confidence for detections
            use_gpu: Whether to use GPU acceleration (CUDA) - IGNORED IN CPU MODE
            enable_tracking: Enable object tracking across frames
        """
        if not HAS_YOLO:
            raise ImportError(
                "ultralytics package not installed. "
                "Install with: pip install ultralytics"
            )
        
        self.confidence_threshold = confidence_threshold
        self.use_gpu = False # Force CPU
        self.enable_tracking = enable_tracking
        self.model_name = model_name
        
        # Load YOLO model
        logger.info(f"Loading YOLO model: {model_name}")
        self.model = YOLO(model_name)
        
        # Set device
        self.device = "cpu"
        logger.info(f"YOLO initialized on CPU (GPU disabled)")
        
        # Track IDs for persistent tracking
        self._track_history: Dict[int, List[PersonBox]] = {}
        
        logger.info(
            f"YOLO person detector initialized "
            f"(model={model_name}, device={self.device}, "
            f"conf={confidence_threshold}, tracking={enable_tracking})"
        )
    
    def detect(
        self,
        frame: np.ndarray,
        use_tracking: Optional[bool] = None
    ) -> List[PersonBox]:
        """
        Detect persons in a frame.
        
        Args:
            frame: BGR image (numpy array)
            use_tracking: Override tracking setting for this call
        
        Returns:
            List of PersonBox objects for detected persons
        """
        if frame is None or frame.size == 0:
            return []
        
        # Determine if tracking should be used
        tracking = use_tracking if use_tracking is not None else self.enable_tracking
        
        try:
            if tracking:
                # Use tracking mode for consistent IDs across frames
                results = self.model.track(
                    frame,
                    classes=[PERSON_CLASS_ID],
                    conf=self.confidence_threshold,
                    device=self.device,
                    persist=True,
                    verbose=False
                )
            else:
                # Simple detection without tracking
                results = self.model(
                    frame,
                    classes=[PERSON_CLASS_ID],
                    conf=self.confidence_threshold,
                    device=self.device,
                    verbose=False
                )
        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
            return []
        
        # Parse results
        persons = []
        for result in results:
            if result.boxes is None:
                continue
            
            boxes = result.boxes
            for i, box in enumerate(boxes):
                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0].cpu().numpy())
                
                # Get track ID if available
                track_id = None
                if tracking and box.id is not None:
                    track_id = int(box.id[0].cpu().numpy())
                
                person = PersonBox(
                    x=int(x1),
                    y=int(y1),
                    width=int(x2 - x1),
                    height=int(y2 - y1),
                    confidence=conf,
                    track_id=track_id
                )
                persons.append(person)
        
        # Sort by area (largest first, typically closest to camera)
        persons.sort(key=lambda p: p.area, reverse=True)
        
        return persons
    
    def detect_with_face_estimates(
        self,
        frame: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Detect persons and estimate their face positions.
        
        Useful for integrating with face tracking when face detection fails.
        
        Args:
            frame: BGR image (numpy array)
        
        Returns:
            List of dicts with 'person_box', 'face_estimate', and 'track_id'
        """
        persons = self.detect(frame)
        
        results = []
        for person in persons:
            face_x, face_y, face_w, face_h = person.to_face_estimate()
            
            results.append({
                "person_box": person,
                "face_estimate": {
                    "x": face_x,
                    "y": face_y,
                    "width": face_w,
                    "height": face_h
                },
                "track_id": person.track_id,
                "confidence": person.confidence
            })
        
        return results
    
    def get_person_count(self, frame: np.ndarray) -> int:
        """
        Get count of persons in frame (quick check).
        
        Args:
            frame: BGR image (numpy array)
        
        Returns:
            Number of persons detected
        """
        persons = self.detect(frame, use_tracking=False)
        return len(persons)
    
    def reset_tracking(self):
        """Reset tracking state for new video."""
        self._track_history.clear()
        # Reset YOLO's internal tracker
        self.model.predictor = None
        logger.debug("YOLO tracking state reset")


def create_person_detector(
    model_name: str = DEFAULT_MODEL,
    confidence_threshold: float = 0.5,
    use_gpu: bool = True
) -> Optional[YOLOPersonDetector]:
    """
    Create a YOLO person detector.
    
    Args:
        model_name: YOLO model to use
        confidence_threshold: Minimum confidence for detections
        use_gpu: Whether to use GPU
    
    Returns:
        YOLOPersonDetector instance, or None if YOLO not available
    """
    if not HAS_YOLO:
        logger.warning("Cannot create person detector - ultralytics not installed")
        return None
    
    try:
        return YOLOPersonDetector(
            model_name=model_name,
            confidence_threshold=confidence_threshold,
            use_gpu=use_gpu
        )
    except Exception as e:
        logger.error(f"Failed to create person detector: {e}")
        return None


def is_yolo_available() -> bool:
    """Check if YOLO person detection is available."""
    return HAS_YOLO
