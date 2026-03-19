"""
OpenCV YuNet Face Detector for PodcastClips.

Alternative face detector using OpenCV's FaceDetectorYN (YuNet model).
Better for small faces in wide shots compared to MediaPipe.
"""

import cv2
import numpy as np
import os
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.face_detector_opencv")

# YuNet model URL from OpenCV Zoo
YUNET_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
YUNET_MODEL_NAME = "face_detection_yunet_2023mar.onnx"


class OpenCVFaceDetector:
    """
    Face detector using OpenCV's FaceDetectorYN (YuNet model).

    YuNet advantages over MediaPipe:
    - Better small face detection in wide shots
    - Handles side faces well (important for podcasts)
    - Can use full frame resolution (not limited to 128x128)
    - Lower confidence threshold for difficult detections
    """

    def __init__(
        self,
        conf_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
        model_dir: str = "/tmp/face_detection_cache",
        use_gpu: bool = False
    ):
        """
        Initialize OpenCV YuNet face detector.

        Args:
            conf_threshold: Confidence threshold for detections (0.6 = balanced, higher = stricter)
            nms_threshold: Non-maximum suppression threshold
            top_k: Maximum number of faces to detect
            model_dir: Directory to store downloaded model
            use_gpu: Whether to use GPU acceleration - IGNORED IN CPU MODE
        """
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.top_k = top_k
        self.model_dir = Path(model_dir)
        self.use_gpu = False # Force CPU
        
        # Ensure model directory exists
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Download model if not present
        self.model_path = self.model_dir / YUNET_MODEL_NAME
        if not self.model_path.exists():
            self._download_model()
            
        # Configure backend and target for CPU (GPU logic removed)
        backend_id = cv2.dnn.DNN_BACKEND_DEFAULT
        target_id = cv2.dnn.DNN_TARGET_CPU
        
        # Create detector with CPU backend
        self.detector = cv2.FaceDetectorYN.create(
            str(self.model_path),
            "",
            (320, 320),
            self.conf_threshold,
            self.nms_threshold,
            self.top_k,
            backend_id,
            target_id
        )
        
        logger.info(
            f"OpenCV YuNet face detector initialized "
            f"(conf={conf_threshold}, nms={nms_threshold}, cpu_only=True)"
        )

    # _check_cuda_available removed (CPU Mode Only)

    def _download_model(self):
        """Download YuNet model from OpenCV Zoo."""
        logger.info(f"Downloading YuNet model from OpenCV Zoo...")

        try:
            # Download with progress
            def report_progress(block_num, block_size, total_size):
                if total_size > 0:
                    progress = block_num * block_size / total_size * 100
                    if block_num % 100 == 0:
                        logger.debug(f"Download progress: {progress:.1f}%")

            urllib.request.urlretrieve(
                YUNET_MODEL_URL,
                str(self.model_path),
                reporthook=report_progress
            )

            logger.info(f"✓ YuNet model downloaded to: {self.model_path}")

        except Exception as e:
            logger.error(f"Failed to download YuNet model: {e}")
            raise RuntimeError(
                f"Could not download YuNet model from {YUNET_MODEL_URL}\n"
                f"Error: {e}\n"
                "Please download manually from: "
                "https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet"
            )

    def detect(
        self,
        frame: np.ndarray,
        use_full_resolution: bool = True
    ) -> List[Tuple[int, int, int, int, float]]:
        """
        Detect faces in a frame.

        Args:
            frame: BGR image (numpy array)
            use_full_resolution: Use full frame size for better small face detection

        Returns:
            List of (x, y, width, height, confidence) tuples
        """
        if frame is None or frame.size == 0:
            return []

        height, width = frame.shape[:2]

        # Set input size to frame size for better small face detection
        if use_full_resolution:
            self.detector.setInputSize((width, height))

        # Run detection
        _, faces = self.detector.detect(frame)

        if faces is None:
            return []

        # Convert to list of tuples
        # YuNet output: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, score]
        # We only need: x, y, w, h, score
        results = []
        for face in faces:
            x = int(face[0])
            y = int(face[1])
            w = int(face[2])
            h = int(face[3])
            confidence = float(face[14])  # Last element is confidence

            # Ensure valid bounding box
            x = max(0, min(x, width - 1))
            y = max(0, min(y, height - 1))
            w = max(1, min(w, width - x))
            h = max(1, min(h, height - y))

            results.append((x, y, w, h, confidence))

        return results

    def detect_with_landmarks(
        self,
        frame: np.ndarray
    ) -> List[dict]:
        """
        Detect faces with facial landmarks.

        Args:
            frame: BGR image (numpy array)

        Returns:
            List of dicts with 'bbox', 'confidence', and 'landmarks' keys
        """
        if frame is None or frame.size == 0:
            return []

        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))

        _, faces = self.detector.detect(frame)

        if faces is None:
            return []

        results = []
        for face in faces:
            # Bounding box
            x, y, w, h = int(face[0]), int(face[1]), int(face[2]), int(face[3])

            # 5 facial landmarks: right eye, left eye, nose tip, right mouth, left mouth
            landmarks = {
                'right_eye': (int(face[4]), int(face[5])),
                'left_eye': (int(face[6]), int(face[7])),
                'nose': (int(face[8]), int(face[9])),
                'right_mouth': (int(face[10]), int(face[11])),
                'left_mouth': (int(face[12]), int(face[13]))
            }

            results.append({
                'bbox': (x, y, w, h),
                'confidence': float(face[14]),
                'landmarks': landmarks
            })

        return results


def create_opencv_detector(
    conf_threshold: float = 0.6,
    nms_threshold: float = 0.3,
    model_dir: str = "/tmp/face_detection_cache"
) -> OpenCVFaceDetector:
    """
    Create an OpenCV YuNet face detector.

    Args:
        conf_threshold: Confidence threshold (higher = stricter, reduces false positives)
        nms_threshold: Non-maximum suppression threshold
        model_dir: Directory to store model

    Returns:
        OpenCVFaceDetector instance
    """
    return OpenCVFaceDetector(
        conf_threshold=conf_threshold,
        nms_threshold=nms_threshold,
        model_dir=model_dir
    )


# Convenience function to check if OpenCV face detection is available
def is_opencv_face_detection_available() -> bool:
    """Check if OpenCV FaceDetectorYN is available."""
    return hasattr(cv2, 'FaceDetectorYN')
