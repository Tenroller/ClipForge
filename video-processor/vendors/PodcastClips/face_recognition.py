"""
Face recognition module using InsightFace for persistent identity tracking.

This module provides facial embeddings for person re-identification, enabling
persistent tracking even when faces leave and return to frame, or when paths cross.
"""

import numpy as np
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
import os
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.face_recognition")

# Module availability flag (exported for face_tracker.py)
try:
    import insightface
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False


@dataclass
class FaceEmbedding:
    """Face embedding for recognition."""
    embedding: np.ndarray  # 512-dim embedding vector
    face_id: int
    confidence: float
    timestamp: float  # When this embedding was extracted


class FaceRecognitionEngine:
    """
    Face recognition engine using InsightFace for persistent identity.

    Uses ArcFace embeddings to recognize faces across frames, enabling
    persistent identity even when faces temporarily leave the frame.
    """

    def __init__(
        self,
        model_name: str = "buffalo_l",  # buffalo_l, buffalo_s (smaller/faster)
        similarity_threshold: float = 0.6,
        gpu_id: int = 0
    ):
        """
        Initialize face recognition engine.

        Args:
            model_name: InsightFace model to use
                - buffalo_l: Large model (better accuracy)
                - buffalo_s: Small model (faster, good for real-time)
            similarity_threshold: Cosine similarity threshold for matching (0-1)
                - 0.4: Very permissive (may match different people)
                - 0.6: Balanced (recommended)
                - 0.8: Strict (may miss same person)
            gpu_id: GPU device ID (-1 for CPU)
        """
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.gpu_id = gpu_id

        # Check if InsightFace is available
        if not FACE_RECOGNITION_AVAILABLE:
            logger.warning(
                "InsightFace not installed. Face recognition disabled. "
                "Install with: pip install insightface onnxruntime-gpu"
            )
            self.model = None
            return

        # Initialize model
        try:
            from insightface.app import FaceAnalysis

            # Initialize face analysis app
            self.model = FaceAnalysis(
                name=model_name,
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider'] if gpu_id >= 0
                         else ['CPUExecutionProvider']
            )

            # Prepare model
            ctx_id = gpu_id if gpu_id >= 0 else -1
            self.model.prepare(ctx_id=ctx_id, det_size=(640, 640))

            logger.info(
                f"Face recognition initialized with {model_name} "
                f"({'GPU' if gpu_id >= 0 else 'CPU'} mode)"
            )

        except Exception as e:
            logger.error(f"Failed to initialize InsightFace: {e}")
            self.model = None

        # Storage for face embeddings by ID
        self.face_embeddings: Dict[int, List[FaceEmbedding]] = {}

    def extract_embedding(
        self,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int]
    ) -> Optional[np.ndarray]:
        """
        Extract face embedding from a face crop.

        Args:
            frame: Full video frame (BGR format)
            bbox: Face bounding box (x, y, width, height)

        Returns:
            512-dim embedding vector, or None if extraction failed
        """
        if self.model is None:
            return None

        try:
            x, y, w, h = bbox

            # Ensure valid crop coordinates
            frame_h, frame_w = frame.shape[:2]
            x = max(0, min(x, frame_w - 1))
            y = max(0, min(y, frame_h - 1))
            w = min(w, frame_w - x)
            h = min(h, frame_h - y)

            if w <= 0 or h <= 0:
                logger.debug(f"Invalid face crop dimensions: {bbox}")
                return None

            # Crop face region with padding for better recognition
            pad_ratio = 0.2  # 20% padding
            pad_w = int(w * pad_ratio)
            pad_h = int(h * pad_ratio)

            x1 = max(0, x - pad_w)
            y1 = max(0, y - pad_h)
            x2 = min(frame_w, x + w + pad_w)
            y2 = min(frame_h, y + h + pad_h)

            face_crop = frame[y1:y2, x1:x2]

            # Get face embeddings
            faces = self.model.get(face_crop)

            if len(faces) == 0:
                logger.debug("No face detected in crop")
                return None

            # Return embedding of the largest face (should be the only one)
            # InsightFace returns embeddings as 512-dim normalized vectors
            embedding = faces[0].normed_embedding

            return embedding

        except Exception as e:
            logger.debug(f"Failed to extract embedding: {e}")
            return None

    def match_face(
        self,
        embedding: np.ndarray,
        timestamp: float
    ) -> Optional[int]:
        """
        Match a face embedding to existing tracked faces.

        Uses cosine similarity to find the best match among tracked faces.

        Args:
            embedding: 512-dim face embedding
            timestamp: Current timestamp

        Returns:
            face_id of best match, or None if no match found
        """
        if embedding is None:
            return None

        best_match_id = None
        best_similarity = 0.0

        for face_id, embeddings_list in self.face_embeddings.items():
            # Calculate similarity with all stored embeddings for this face
            # Use recent embeddings (last 5) for better matching
            recent_embeddings = embeddings_list[-5:]

            similarities = []
            for face_emb in recent_embeddings:
                # Cosine similarity (embeddings are already normalized)
                similarity = float(np.dot(embedding, face_emb.embedding))
                similarities.append(similarity)

            # Use max similarity among recent embeddings
            max_similarity = max(similarities) if similarities else 0.0

            # Check if this is the best match so far
            if max_similarity > self.similarity_threshold and max_similarity > best_similarity:
                best_similarity = max_similarity
                best_match_id = face_id

        if best_match_id is not None:
            logger.debug(
                f"Matched face to ID {best_match_id} "
                f"(similarity: {best_similarity:.3f})"
            )

        return best_match_id

    def add_face_embedding(
        self,
        face_id: int,
        embedding: np.ndarray,
        confidence: float,
        timestamp: float
    ):
        """
        Add a face embedding to the database.

        Args:
            face_id: ID of the face track
            embedding: 512-dim face embedding
            confidence: Face detection confidence
            timestamp: Current timestamp
        """
        if embedding is None:
            return

        face_emb = FaceEmbedding(
            embedding=embedding,
            face_id=face_id,
            confidence=confidence,
            timestamp=timestamp
        )

        if face_id not in self.face_embeddings:
            self.face_embeddings[face_id] = []

        self.face_embeddings[face_id].append(face_emb)

        # Keep only recent embeddings to save memory (max 20 per face)
        if len(self.face_embeddings[face_id]) > 20:
            self.face_embeddings[face_id] = self.face_embeddings[face_id][-20:]

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Similarity score (0-1)
        """
        if embedding1 is None or embedding2 is None:
            return 0.0

        # Cosine similarity (embeddings are normalized)
        similarity = float(np.dot(embedding1, embedding2))

        return max(0.0, min(1.0, similarity))  # Clamp to [0, 1]

    def get_face_summary(self) -> Dict[int, Dict]:
        """
        Get summary of tracked faces.

        Returns:
            Dictionary mapping face_id to summary statistics
        """
        summary = {}

        for face_id, embeddings_list in self.face_embeddings.items():
            if embeddings_list:
                summary[face_id] = {
                    "num_embeddings": len(embeddings_list),
                    "avg_confidence": np.mean([e.confidence for e in embeddings_list]),
                    "time_span": (
                        embeddings_list[-1].timestamp - embeddings_list[0].timestamp
                    ) if len(embeddings_list) > 1 else 0.0
                }

        return summary

    def cleanup(self):
        """Clean up resources."""
        self.face_embeddings.clear()
