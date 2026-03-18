#!/usr/bin/env python3
"""
AI-Powered Clip Scoring Module

Scores video clips based on engagement potential for TikTok optimization.
Uses face detection, motion analysis, audio energy, and visual clarity
to predict which clips will perform best as hooks and content.
"""

import os
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path

# Audio analysis
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    print("⚠️  librosa not available - audio scoring disabled")

# Face detection with MediaPipe
try:
    import mediapipe as mp
    if hasattr(mp, 'tasks') and hasattr(mp.tasks, 'vision'):
        HAS_MEDIAPIPE = True
        _MP_FACE_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
        _MP_FACE_MODEL_PATH = os.path.join(
            os.environ.get("HOME", "/tmp"), ".cache", "mediapipe", "blaze_face_short_range.tflite"
        )
    elif hasattr(mp, 'solutions'):
        HAS_MEDIAPIPE = True
    else:
        HAS_MEDIAPIPE = False
        print("⚠️  mediapipe installed but missing tasks/solutions API - using OpenCV face detection fallback")
except ImportError:
    HAS_MEDIAPIPE = False
    print("⚠️  mediapipe not available - using OpenCV face detection fallback")

from loguru import logger

logger = logger.bind(name="Compilation.clip_scorer")


@dataclass
class ClipScore:
    """Score results for a video clip"""
    overall_score: float = 0.0  # 0-100 engagement score
    face_score: float = 0.0     # 0-100 face presence/size score
    motion_score: float = 0.0   # 0-100 motion intensity score
    audio_score: float = 0.0    # 0-100 audio energy score
    clarity_score: float = 0.0  # 0-100 visual clarity score
    
    # Detailed metadata
    face_count: int = 0
    max_face_size: float = 0.0  # 0-1 relative to frame
    avg_motion: float = 0.0
    peak_audio_db: float = -60.0
    blur_level: float = 0.0
    
    # Recommendations
    is_hook_candidate: bool = False  # Good for first clip
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'overall_score': self.overall_score,
            'face_score': self.face_score,
            'motion_score': self.motion_score,
            'audio_score': self.audio_score,
            'clarity_score': self.clarity_score,
            'face_count': self.face_count,
            'max_face_size': self.max_face_size,
            'avg_motion': self.avg_motion,
            'peak_audio_db': self.peak_audio_db,
            'blur_level': self.blur_level,
            'is_hook_candidate': self.is_hook_candidate,
            'is_duplicate': self.is_duplicate,
            'duplicate_of': self.duplicate_of
        }


@dataclass
class ScoringConfig:
    """Configuration for clip scoring weights and thresholds"""
    # Score weights (must sum to 1.0)
    face_weight: float = 0.35
    motion_weight: float = 0.25
    audio_weight: float = 0.25
    clarity_weight: float = 0.15
    
    # Thresholds
    min_face_confidence: float = 0.7
    min_face_size_for_hook: float = 0.05  # 5% of frame area
    motion_high_threshold: float = 30.0   # Frame diff threshold
    blur_threshold: float = 100.0         # Laplacian variance threshold
    
    # Sampling
    sample_frames: int = 5  # Frames to sample per clip
    sample_audio_duration: float = 2.0  # Seconds to sample for audio


class ClipScorer:
    """
    AI-powered clip scoring for TikTok-optimized selection.
    
    Analyzes clips based on:
    - Face presence and size (hook potential)
    - Motion intensity (action level)
    - Audio energy (excitement level)
    - Visual clarity (blur detection)
    """
    
    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()
        
        # Initialize face detector
        self._face_detector = None
        self._mp_face_detection = None
        
        # Perceptual hash cache for duplicate detection
        self._phash_cache: Dict[str, np.ndarray] = {}
        
        logger.info("ClipScorer initialized", 
                   weights=f"face={self.config.face_weight}, motion={self.config.motion_weight}, "
                          f"audio={self.config.audio_weight}, clarity={self.config.clarity_weight}")
    
    def _get_face_detector(self):
        """Lazy-load face detector"""
        if self._face_detector is None:
            if HAS_MEDIAPIPE:
                if hasattr(mp.tasks, 'vision'):
                    # Tasks API (mediapipe >= 0.10)
                    self._ensure_face_model()
                    options = mp.tasks.vision.FaceDetectorOptions(
                        base_options=mp.tasks.BaseOptions(model_asset_path=_MP_FACE_MODEL_PATH),
                        min_detection_confidence=self.config.min_face_confidence,
                    )
                    self._face_detector = mp.tasks.vision.FaceDetector.create_from_options(options)
                else:
                    # Legacy solutions API
                    self._mp_face_detection = mp.solutions.face_detection
                    self._face_detector = self._mp_face_detection.FaceDetection(
                        model_selection=0,
                        min_detection_confidence=self.config.min_face_confidence
                    )
                logger.info("Using MediaPipe face detection")
            else:
                # Fallback to OpenCV Haar cascades
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self._face_detector = cv2.CascadeClassifier(cascade_path)
                logger.info("Using OpenCV Haar cascade face detection")

        return self._face_detector

    @staticmethod
    def _ensure_face_model():
        """Download the MediaPipe face detection model if not cached."""
        if os.path.exists(_MP_FACE_MODEL_PATH):
            return
        os.makedirs(os.path.dirname(_MP_FACE_MODEL_PATH), exist_ok=True)
        import urllib.request
        logger.info(f"Downloading MediaPipe face detection model to {_MP_FACE_MODEL_PATH}")
        urllib.request.urlretrieve(_MP_FACE_MODEL_URL, _MP_FACE_MODEL_PATH)
        logger.info(f"Downloaded ({os.path.getsize(_MP_FACE_MODEL_PATH)} bytes)")
    
    def score_clip(self, clip_path: str) -> ClipScore:
        """
        Score a video clip for TikTok engagement potential.
        
        Args:
            clip_path: Path to video file
            
        Returns:
            ClipScore with overall and component scores
        """
        if not os.path.exists(clip_path):
            logger.warning(f"Clip not found: {clip_path}")
            return ClipScore()
        
        logger.info(f"Scoring clip: {os.path.basename(clip_path)}")
        
        score = ClipScore()
        
        try:
            # Score each component
            score.face_score, score.face_count, score.max_face_size = self._score_faces(clip_path)
            score.motion_score, score.avg_motion = self._score_motion(clip_path)
            score.audio_score, score.peak_audio_db = self._score_audio(clip_path)
            score.clarity_score, score.blur_level = self._score_clarity(clip_path)
            
            # Calculate weighted overall score
            score.overall_score = (
                score.face_score * self.config.face_weight +
                score.motion_score * self.config.motion_weight +
                score.audio_score * self.config.audio_weight +
                score.clarity_score * self.config.clarity_weight
            )
            
            # Determine if good hook candidate
            score.is_hook_candidate = (
                score.face_score >= 50 and 
                score.max_face_size >= self.config.min_face_size_for_hook and
                score.clarity_score >= 40
            )
            
            logger.info(f"Clip scored: overall={score.overall_score:.1f}, "
                       f"face={score.face_score:.1f}, motion={score.motion_score:.1f}, "
                       f"audio={score.audio_score:.1f}, clarity={score.clarity_score:.1f}, "
                       f"hook={score.is_hook_candidate}")
            
        except Exception as e:
            logger.error(f"Error scoring clip {clip_path}: {e}")
        
        return score
    
    def _score_faces(self, clip_path: str) -> Tuple[float, int, float]:
        """
        Score face presence and size in video.
        
        Returns:
            (face_score, face_count, max_face_size)
        """
        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            return 0.0, 0, 0.0
        
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames == 0:
                return 0.0, 0, 0.0
            
            frame_indices = np.linspace(0, total_frames - 1, self.config.sample_frames, dtype=int)
            
            face_detector = self._get_face_detector()
            all_face_sizes = []
            total_faces = 0
            
            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if not ret:
                    continue
                
                h, w = frame.shape[:2]
                frame_area = w * h
                
                if HAS_MEDIAPIPE:
                    # MediaPipe expects RGB
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                    if hasattr(mp.tasks, 'vision'):
                        # Tasks API (mediapipe >= 0.10)
                        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                        results = face_detector.detect(mp_image)
                        for detection in results.detections:
                            bbox = detection.bounding_box
                            face_area = (bbox.width * bbox.height) / (w * h)
                            all_face_sizes.append(face_area)
                            total_faces += 1
                    else:
                        # Legacy solutions API
                        results = face_detector.process(rgb_frame)
                        if results.detections:
                            for detection in results.detections:
                                bbox = detection.location_data.relative_bounding_box
                                face_area = bbox.width * bbox.height
                                all_face_sizes.append(face_area)
                                total_faces += 1
                else:
                    # OpenCV Haar cascade
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_detector.detectMultiScale(gray, 1.1, 4)
                    
                    for (x, y, fw, fh) in faces:
                        face_area = (fw * fh) / frame_area
                        all_face_sizes.append(face_area)
                        total_faces += 1
            
            if not all_face_sizes:
                return 0.0, 0, 0.0
            
            max_face_size = max(all_face_sizes)
            avg_face_count = total_faces / len(frame_indices)
            
            # Score calculation:
            # - Face presence: 50 points if any face detected
            # - Face size bonus: up to 30 points based on max face size (larger = better hook)
            # - Multiple faces bonus: up to 20 points
            
            score = 0.0
            if total_faces > 0:
                score += 50  # Base score for face presence
                score += min(30, max_face_size * 300)  # Size bonus (capped at 30)
                score += min(20, avg_face_count * 10)  # Multiple faces bonus
            
            return min(100, score), total_faces, max_face_size
            
        finally:
            cap.release()
    
    def _score_motion(self, clip_path: str) -> Tuple[float, float]:
        """
        Score motion intensity using frame differencing.
        
        Returns:
            (motion_score, avg_motion_value)
        """
        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            return 0.0, 0.0
        
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames < 2:
                return 0.0, 0.0
            
            # Sample consecutive frame pairs
            sample_count = min(self.config.sample_frames, total_frames - 1)
            frame_indices = np.linspace(0, total_frames - 2, sample_count, dtype=int)
            
            motion_values = []
            prev_gray = None
            
            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if not ret:
                    continue
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)  # Reduce noise
                
                # Read next frame for comparison
                ret2, frame2 = cap.read()
                if not ret2:
                    continue
                
                gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
                gray2 = cv2.GaussianBlur(gray2, (21, 21), 0)
                
                # Calculate frame difference
                frame_diff = cv2.absdiff(gray, gray2)
                motion_value = np.mean(frame_diff)
                motion_values.append(motion_value)
            
            if not motion_values:
                return 0.0, 0.0
            
            avg_motion = np.mean(motion_values)
            
            # Score: normalize motion to 0-100
            # Low motion (<5): 0-30
            # Medium motion (5-20): 30-70
            # High motion (>20): 70-100
            if avg_motion < 5:
                score = avg_motion * 6  # 0-30
            elif avg_motion < 20:
                score = 30 + ((avg_motion - 5) / 15) * 40  # 30-70
            else:
                score = 70 + min(30, (avg_motion - 20) * 1.5)  # 70-100
            
            return min(100, score), avg_motion
            
        finally:
            cap.release()
    
    def _score_audio(self, clip_path: str) -> Tuple[float, float]:
        """
        Score audio energy using librosa.
        
        Returns:
            (audio_score, peak_db)
        """
        if not HAS_LIBROSA:
            return 50.0, -20.0  # Default neutral score if librosa unavailable
        
        try:
            # Load audio with librosa
            y, sr = librosa.load(clip_path, sr=22050, duration=self.config.sample_audio_duration)
            
            if len(y) == 0:
                return 0.0, -60.0
            
            # Calculate RMS energy
            rms = librosa.feature.rms(y=y)[0]
            avg_rms = np.mean(rms)
            max_rms = np.max(rms)
            
            # Convert to dB
            peak_db = 20 * np.log10(max_rms + 1e-10)
            
            # Calculate spectral centroid (brightness)
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            avg_centroid = np.mean(spectral_centroids)
            
            # Score calculation:
            # - Base energy score (0-60 based on RMS)
            # - Spectral variety bonus (0-20 based on centroid variance)
            # - Peak presence bonus (0-20 if distinct peaks)
            
            # Normalize RMS (typical speech is around 0.1, loud audio around 0.3+)
            energy_score = min(60, avg_rms * 200)
            
            # Spectral brightness bonus (higher centroid = brighter/more exciting)
            brightness_score = min(20, (avg_centroid / sr) * 100)
            
            # Peak-to-average ratio (dynamic range)
            peak_ratio = max_rms / (avg_rms + 1e-10)
            dynamic_score = min(20, (peak_ratio - 1) * 10)
            
            score = energy_score + brightness_score + dynamic_score
            
            return min(100, max(0, score)), peak_db
            
        except Exception as e:
            logger.warning(f"Audio analysis failed: {e}")
            return 50.0, -20.0
    
    def _score_clarity(self, clip_path: str) -> Tuple[float, float]:
        """
        Score visual clarity using Laplacian variance (blur detection).
        
        Returns:
            (clarity_score, blur_level)
        """
        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            return 0.0, 0.0
        
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames == 0:
                return 0.0, 0.0
            
            frame_indices = np.linspace(0, total_frames - 1, self.config.sample_frames, dtype=int)
            
            clarity_values = []
            
            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if not ret:
                    continue
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Laplacian variance - higher = sharper image
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                variance = laplacian.var()
                clarity_values.append(variance)
            
            if not clarity_values:
                return 0.0, 0.0
            
            avg_clarity = np.mean(clarity_values)
            
            # Score: threshold at ~100 for "clear" videos
            # <50: blurry (0-30)
            # 50-150: acceptable (30-70)
            # >150: sharp (70-100)
            if avg_clarity < 50:
                score = avg_clarity * 0.6  # 0-30
            elif avg_clarity < 150:
                score = 30 + ((avg_clarity - 50) / 100) * 40  # 30-70
            else:
                score = 70 + min(30, (avg_clarity - 150) * 0.1)  # 70-100
            
            # Blur level is inverse of clarity (lower is better)
            blur_level = 1.0 / (avg_clarity + 1)
            
            return min(100, score), blur_level
            
        finally:
            cap.release()
    
    def compute_phash(self, clip_path: str, frame_idx: int = 0) -> Optional[np.ndarray]:
        """
        Compute perceptual hash for a video frame.
        
        Args:
            clip_path: Path to video
            frame_idx: Frame to hash (default: first frame)
            
        Returns:
            64-bit perceptual hash as numpy array
        """
        cache_key = f"{clip_path}:{frame_idx}"
        if cache_key in self._phash_cache:
            return self._phash_cache[cache_key]
        
        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            return None
        
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                return None
            
            # Resize to 32x32 and convert to grayscale
            resized = cv2.resize(frame, (32, 32), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            
            # DCT-based perceptual hash
            dct = cv2.dct(np.float32(gray))
            dct_low = dct[:8, :8]  # Keep low frequencies
            
            # Compute hash based on median
            median = np.median(dct_low)
            phash = (dct_low > median).flatten().astype(np.uint8)
            
            self._phash_cache[cache_key] = phash
            return phash
            
        finally:
            cap.release()
    
    def compute_similarity(self, clip1_path: str, clip2_path: str, 
                          sample_frames: int = 3) -> float:
        """
        Compute visual similarity between two clips using perceptual hashing.
        
        Returns:
            Similarity score 0-1 (1 = identical)
        """
        try:
            # Sample multiple frames for better comparison
            cap1 = cv2.VideoCapture(clip1_path)
            cap2 = cv2.VideoCapture(clip2_path)
            
            if not cap1.isOpened() or not cap2.isOpened():
                return 0.0
            
            frames1 = int(cap1.get(cv2.CAP_PROP_FRAME_COUNT))
            frames2 = int(cap2.get(cv2.CAP_PROP_FRAME_COUNT))
            cap1.release()
            cap2.release()
            
            if frames1 == 0 or frames2 == 0:
                return 0.0
            
            similarities = []
            
            for i in range(sample_frames):
                idx1 = int(frames1 * (i + 0.5) / sample_frames)
                idx2 = int(frames2 * (i + 0.5) / sample_frames)
                
                hash1 = self.compute_phash(clip1_path, idx1)
                hash2 = self.compute_phash(clip2_path, idx2)
                
                if hash1 is None or hash2 is None:
                    continue
                
                # Hamming similarity (1 - normalized hamming distance)
                hamming_dist = np.sum(hash1 != hash2)
                similarity = 1 - (hamming_dist / len(hash1))
                similarities.append(similarity)
            
            if not similarities:
                return 0.0
            
            return np.mean(similarities)
            
        except Exception as e:
            logger.warning(f"Similarity computation failed: {e}")
            return 0.0
    
    def _precompute_hashes(self, clips: List[Dict], sample_frames: int = 3, max_workers: int = 8) -> List[Optional[np.ndarray]]:
        """
        Pre-compute perceptual hashes for all clips in parallel.

        Returns a list of hash matrices (sample_frames x 64) per clip, or None if hashing failed.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def compute_clip_hashes(idx: int, clip_path: str) -> Tuple[int, Optional[np.ndarray]]:
            try:
                cap = cv2.VideoCapture(clip_path)
                if not cap.isOpened():
                    return (idx, None)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.release()
                if frame_count == 0:
                    return (idx, None)

                hashes = []
                for i in range(sample_frames):
                    frame_idx = int(frame_count * (i + 0.5) / sample_frames)
                    h = self.compute_phash(clip_path, frame_idx)
                    if h is not None:
                        hashes.append(h)

                if not hashes:
                    return (idx, None)
                return (idx, np.array(hashes, dtype=np.uint8))
            except Exception as e:
                logger.warning(f"Failed to hash clip {clip_path}: {e}")
                return (idx, None)

        results: List[Optional[np.ndarray]] = [None] * len(clips)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(compute_clip_hashes, i, clip['path']): i
                for i, clip in enumerate(clips)
            }
            for future in as_completed(futures):
                idx, hash_matrix = future.result()
                results[idx] = hash_matrix

        return results

    def detect_duplicates(self, clips: List[Dict], threshold: float = 0.85) -> List[Dict]:
        """
        Detect duplicate/similar clips in a list.

        Pre-computes all perceptual hashes in parallel, then compares them
        using vectorized numpy operations for fast O(n^2) in-memory comparison
        instead of opening video files per pair.

        Args:
            clips: List of clip dicts with 'path' key
            threshold: Similarity threshold for duplicate detection

        Returns:
            Updated clips with 'is_duplicate' and 'duplicate_of' fields
        """
        logger.info(f"Checking {len(clips)} clips for duplicates (threshold={threshold})")

        # Phase 1: Pre-compute all hashes in parallel
        logger.info(f"Pre-computing perceptual hashes for {len(clips)} clips...")
        all_hashes = self._precompute_hashes(clips)

        valid_count = sum(1 for h in all_hashes if h is not None)
        logger.info(f"Hashed {valid_count}/{len(clips)} clips successfully")

        # Phase 2: Vectorized pairwise comparison
        # For each valid pair, compute average hamming similarity across sample frames
        hash_len = 64  # 8x8 DCT hash

        for i in range(len(clips)):
            if clips[i].get('is_duplicate', False) or all_hashes[i] is None:
                continue

            hashes_i = all_hashes[i]  # shape: (sample_frames, 64)

            for j in range(i + 1, len(clips)):
                if clips[j].get('is_duplicate', False) or all_hashes[j] is None:
                    continue

                hashes_j = all_hashes[j]

                # Compare frame-by-frame using the minimum common sample count
                n_compare = min(len(hashes_i), len(hashes_j))
                hamming_dists = np.sum(hashes_i[:n_compare] != hashes_j[:n_compare], axis=1)
                similarity = float(np.mean(1.0 - hamming_dists / hash_len))

                if similarity >= threshold:
                    clips[j]['is_duplicate'] = True
                    clips[j]['duplicate_of'] = clips[i]['path']
                    logger.info(f"Duplicate detected: {os.path.basename(clips[j]['path'])} "
                               f"similar to {os.path.basename(clips[i]['path'])} ({similarity:.2f})")

        duplicates = sum(1 for c in clips if c.get('is_duplicate', False))
        logger.info(f"Found {duplicates} duplicate clips")

        return clips
    
    def score_all_clips(self, clips: List[Dict], detect_duplicates: bool = True, 
                        max_workers: int = 4) -> List[Dict]:
        """
        Score all clips in parallel and optionally detect duplicates.
        
        Args:
            clips: List of clip dicts with 'path' key
            detect_duplicates: Whether to run duplicate detection
            max_workers: Maximum parallel scoring workers (default: 4)
            
        Returns:
            Updated clips with 'score' field containing ClipScore
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        logger.info(f"Scoring {len(clips)} clips with {max_workers} workers...")
        
        # Define scoring function for parallel execution
        def score_single_clip(clip_idx: int, clip_path: str) -> Tuple[int, ClipScore]:
            """Score a single clip and return index + score."""
            try:
                score = self.score_clip(clip_path)
                return (clip_idx, score)
            except Exception as e:
                logger.warning(f"Failed to score clip {clip_path}: {e}")
                return (clip_idx, ClipScore())  # Return empty score on error
        
        # Parallel scoring with ThreadPoolExecutor
        scored_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all scoring tasks
            future_to_idx = {
                executor.submit(score_single_clip, idx, clip['path']): idx 
                for idx, clip in enumerate(clips)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_idx):
                try:
                    clip_idx, score = future.result()
                    clips[clip_idx]['score'] = score
                    clips[clip_idx]['engagement_score'] = score.overall_score
                    clips[clip_idx]['is_hook_candidate'] = score.is_hook_candidate
                    scored_count += 1
                except Exception as e:
                    idx = future_to_idx[future]
                    logger.error(f"Error retrieving score for clip {idx}: {e}")
                    clips[idx]['score'] = ClipScore()
                    clips[idx]['engagement_score'] = 0
                    clips[idx]['is_hook_candidate'] = False
        
        logger.info(f"Parallel scoring complete: {scored_count}/{len(clips)} clips scored")
        
        if detect_duplicates:
            clips = self.detect_duplicates(clips)
            for clip in clips:
                if clip.get('is_duplicate', False):
                    clip['score'].is_duplicate = True
                    clip['score'].duplicate_of = clip.get('duplicate_of')
        
        # Sort by engagement score (highest first)
        clips.sort(key=lambda c: c.get('engagement_score', 0), reverse=True)
        
        logger.info(f"Scoring complete. Top score: {clips[0].get('engagement_score', 0):.1f}" if clips else "No clips scored")
        
        return clips
    
    def select_best_clips_for_compilation(
        self, 
        clips: List[Dict],
        target_duration: float,
        min_duration: float = 50.0,
        max_reuse: int = 1,
        prioritize_variety: bool = True
    ) -> List[Dict]:
        """
        Select optimal clips for a TikTok compilation.
        
        Strategy:
        1. First clip: Best hook candidate (highest face score)
        2. Middle clips: Balanced by engagement + variety
        3. Last clip: High audio energy for satisfying ending
        
        Args:
            clips: Scored clips with 'score' field
            target_duration: Target compilation duration in seconds
            min_duration: Minimum compilation duration
            max_reuse: Maximum times a clip can be reused
            prioritize_variety: Avoid similar consecutive clips
            
        Returns:
            Selected clips in order
        """
        if not clips:
            return []
        
        # Filter out duplicates and already-overused clips
        available = [
            c for c in clips 
            if not c.get('score', ClipScore()).is_duplicate and
               c.get('usage_count', 0) < max_reuse
        ]
        
        if not available:
            logger.warning("No available clips after filtering")
            return []
        
        selected = []
        current_duration = 0.0
        used_paths = set()
        
        # 1. Select hook clip (best face score that's also a hook candidate)
        hook_candidates = [c for c in available if c.get('is_hook_candidate', False)]
        if hook_candidates:
            hook_candidates.sort(key=lambda c: c.get('score', ClipScore()).face_score, reverse=True)
            hook = hook_candidates[0]
        else:
            # Fallback to highest overall score
            available.sort(key=lambda c: c.get('engagement_score', 0), reverse=True)
            hook = available[0]
        
        selected.append(hook)
        current_duration += hook.get('duration', 0)
        used_paths.add(hook['path'])
        
        # 2. Fill middle with high-engagement variety
        remaining = [c for c in available if c['path'] not in used_paths]
        remaining.sort(key=lambda c: c.get('engagement_score', 0), reverse=True)
        
        for clip in remaining:
            if current_duration >= target_duration:
                break
            
            clip_duration = clip.get('duration', 0)
            
            # Check if adding this clip would exceed target too much
            if current_duration + clip_duration > target_duration * 1.2:
                continue
            
            # Variety check: avoid consecutive similar clips
            if prioritize_variety and selected:
                last_clip = selected[-1]
                similarity = self.compute_similarity(last_clip['path'], clip['path'])
                if similarity > 0.7:  # Too similar to previous
                    continue
            
            selected.append(clip)
            current_duration += clip_duration
            used_paths.add(clip['path'])
        
        # 3. Ensure we meet minimum duration
        if current_duration < min_duration:
            remaining = [c for c in available if c['path'] not in used_paths]
            for clip in remaining:
                if current_duration >= min_duration:
                    break
                selected.append(clip)
                current_duration += clip.get('duration', 0)
                used_paths.add(clip['path'])
        
        logger.info(f"Selected {len(selected)} clips, total duration: {current_duration:.1f}s")
        
        return selected
    
    def cleanup(self):
        """Release resources"""
        if HAS_MEDIAPIPE and self._face_detector is not None:
            self._face_detector.close()
        self._phash_cache.clear()
        logger.info("ClipScorer resources cleaned up")
