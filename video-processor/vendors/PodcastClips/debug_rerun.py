"""
PodcastClips Debug Step Rerunner

Handles rerunning individual processing steps with modified parameters.
Allows parameter tuning and comparison of results.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.debug_rerun")


class StepRerunner:
    """Manages rerunning individual processing steps"""

    def __init__(self, job_id: str, output_dir: str):
        self.job_id = job_id
        self.output_dir = Path(output_dir)
        self.artifacts_dir = self.output_dir / "artifacts"
        self.debug_dir = self.artifacts_dir / "debug"
        self.rerun_dir = self.debug_dir / "reruns"

        # Create rerun directory
        self.rerun_dir.mkdir(parents=True, exist_ok=True)

    def rerun_transcription(self, whisper_model: str = "turbo") -> Dict[str, Any]:
        """
        Rerun transcription with a different Whisper model.

        Args:
            whisper_model: Whisper model to use (turbo, base, small, medium, large)

        Returns:
            Result dictionary with status and data
        """
        try:
            logger.info(f"Rerunning transcription with model: {whisper_model}")

            # Get video path
            video_metadata = self._load_artifact("download/video_metadata.json")
            if not video_metadata:
                return {"status": "error", "message": "Video metadata not found"}

            video_path = video_metadata.get('video_path')
            if not video_path or not Path(video_path).exists():
                return {"status": "error", "message": f"Video file not found: {video_path}"}

            # Import subtitle generator
            from .subtitle_generator import SubtitleGenerator

            # Initialize generator
            subtitle_gen = SubtitleGenerator()

            # Generate transcription
            result = subtitle_gen.generate_subtitles(
                video_path=video_path,
                model_size=whisper_model
            )

            # Save to rerun directory
            rerun_file = self.rerun_dir / f"transcription_{whisper_model}.json"
            with open(rerun_file, 'w') as f:
                json.dump(result, f, indent=2)

            logger.info(f"Transcription rerun complete. Saved to {rerun_file}")

            return {
                "status": "success",
                "message": f"Transcription completed with model {whisper_model}",
                "data": result,
                "saved_to": str(rerun_file)
            }

        except Exception as e:
            logger.error(f"Error rerunning transcription: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error: {str(e)}"
            }

    def rerun_speaker_diarization(
        self,
        min_speakers: int = 2,
        max_speakers: int = 5
    ) -> Dict[str, Any]:
        """
        Rerun speaker diarization with different parameters.

        Args:
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers

        Returns:
            Result dictionary
        """
        try:
            logger.info(f"Rerunning speaker diarization (min={min_speakers}, max={max_speakers})")

            # Get video path
            video_metadata = self._load_artifact("download/video_metadata.json")
            if not video_metadata:
                return {"status": "error", "message": "Video metadata not found"}

            video_path = video_metadata.get('video_path')

            # Get transcription data
            transcript_data = self._load_artifact("transcription/transcript.json")
            if not transcript_data:
                return {"status": "error", "message": "Transcription data not found"}

            # Import speaker diarization
            from .speaker_diarization import SpeakerDiarization

            # Initialize diarization
            diarization = SpeakerDiarization()

            # Run diarization
            result = diarization.diarize_speakers(
                audio_path=video_path,
                word_timings=transcript_data.get('word_timings', []),
                min_speakers=min_speakers,
                max_speakers=max_speakers
            )

            # Save result
            rerun_file = self.rerun_dir / f"diarization_min{min_speakers}_max{max_speakers}.json"
            with open(rerun_file, 'w') as f:
                json.dump(result, f, indent=2)

            logger.info(f"Speaker diarization rerun complete. Saved to {rerun_file}")

            return {
                "status": "success",
                "message": f"Diarization completed (min={min_speakers}, max={max_speakers})",
                "data": result,
                "saved_to": str(rerun_file)
            }

        except Exception as e:
            logger.error(f"Error rerunning speaker diarization: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error: {str(e)}"
            }

    def rerun_ai_analysis(
        self,
        ai_model: str = "gemini-2.0-flash",
        keywords: str = ""
    ) -> Dict[str, Any]:
        """
        Rerun AI viral moment detection with different parameters.

        Args:
            ai_model: AI model to use (e.g., gemini-2.0-flash, gemini-1.5-pro, etc.)
            keywords: Comma-separated viral focus keywords

        Returns:
            Result dictionary
        """
        try:
            logger.info(f"Rerunning AI analysis with model: {ai_model}, keywords: {keywords}")

            # Get transcription
            transcript_data = self._load_artifact("transcription/transcript.json")
            if not transcript_data:
                return {"status": "error", "message": "Transcription data not found"}

            # Import clip generator
            from .clip_generator import ClipGenerator

            # Initialize generator
            clip_gen = ClipGenerator()

            # Parse keywords
            keyword_list = [k.strip() for k in keywords.split(',')] if keywords else []

            # Detect viral moments
            viral_moments = clip_gen.detect_viral_moments(
                word_timings=transcript_data.get('word_timings', []),
                ai_model=ai_model,
                viral_keywords=keyword_list
            )

            # Save result
            keyword_str = keywords.replace(',', '_').replace(' ', '') if keywords else 'default'
            rerun_file = self.rerun_dir / f"ai_analysis_{ai_model}_{keyword_str}.json"
            with open(rerun_file, 'w') as f:
                json.dump(viral_moments, f, indent=2)

            logger.info(f"AI analysis rerun complete. Saved to {rerun_file}")

            return {
                "status": "success",
                "message": f"AI analysis completed with {ai_model}",
                "data": viral_moments,
                "saved_to": str(rerun_file),
                "moments_count": len(viral_moments) if isinstance(viral_moments, list) else len(viral_moments.get('moments', []))
            }

        except Exception as e:
            logger.error(f"Error rerunning AI analysis: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error: {str(e)}"
            }

    def rerun_face_tracking(
        self,
        smoothing_strength: int = 70,
        max_tracked_faces: int = 2
    ) -> Dict[str, Any]:
        """
        Rerun face tracking with different parameters.

        Args:
            smoothing_strength: Smoothing strength (0-100)
            max_tracked_faces: Maximum number of faces to track

        Returns:
            Result dictionary
        """
        try:
            logger.info(f"Rerunning face tracking (smoothing={smoothing_strength}, max_faces={max_tracked_faces})")

            # Get video path
            video_metadata = self._load_artifact("download/video_metadata.json")
            if not video_metadata:
                return {"status": "error", "message": "Video metadata not found"}

            video_path = video_metadata.get('video_path')

            # Import face tracker
            from .face_tracker import FaceTracker

            # Initialize tracker
            face_tracker = FaceTracker(
                smoothing_strength=smoothing_strength,
                max_tracked_faces=max_tracked_faces
            )

            # For testing, just analyze a short segment (first 30 seconds)
            test_duration = 30.0

            # Track faces
            result = face_tracker.track_faces_in_segment(
                video_path=video_path,
                start_time=0.0,
                end_time=test_duration
            )

            # Save result
            rerun_file = self.rerun_dir / f"face_tracking_s{smoothing_strength}_f{max_tracked_faces}.json"
            with open(rerun_file, 'w') as f:
                json.dump(result, f, indent=2)

            logger.info(f"Face tracking rerun complete. Saved to {rerun_file}")

            return {
                "status": "success",
                "message": f"Face tracking completed (30s test segment)",
                "data": result,
                "saved_to": str(rerun_file)
            }

        except Exception as e:
            logger.error(f"Error rerunning face tracking: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error: {str(e)}"
            }

    def generate_face_overlay(
        self,
        smoothing_strength: int = 70,
        max_tracked_faces: int = 2
    ) -> Dict[str, Any]:
        """
        Generate face tracking overlay video.

        Args:
            smoothing_strength: Smoothing strength for tracking
            max_tracked_faces: Max faces to track

        Returns:
            Result with overlay video path
        """
        try:
            logger.info("Generating face tracking overlay video")

            # Check if we have debug face data
            face_data_file = self.debug_dir / "face_boxes_by_frame.json"
            if not face_data_file.exists():
                return {
                    "status": "error",
                    "message": "No face tracking debug data found. Run processing with debug_mode=True first."
                }

            with open(face_data_file, 'r') as f:
                face_boxes_data = json.load(f)

            # Get video path
            video_metadata = self._load_artifact("download/video_metadata.json")
            if not video_metadata:
                return {"status": "error", "message": "Video metadata not found"}

            video_path = video_metadata.get('video_path')

            # Generate overlay
            from .debug_visualizer import generate_face_tracking_overlay

            output_path = str(self.debug_dir / "face_tracking_overlay.mp4")

            success = generate_face_tracking_overlay(
                video_path=video_path,
                face_boxes_data=face_boxes_data,
                output_path=output_path
            )

            if success:
                return {
                    "status": "success",
                    "message": "Face tracking overlay generated successfully",
                    "video_path": output_path
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to generate overlay video"
                }

        except Exception as e:
            logger.error(f"Error generating face overlay: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error: {str(e)}"
            }

    def _load_artifact(self, artifact_path: str) -> Optional[Dict[str, Any]]:
        """Load an artifact JSON file"""
        full_path = self.artifacts_dir / artifact_path
        if not full_path.exists():
            return None

        try:
            with open(full_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading artifact {artifact_path}: {e}")
            return None

    def get_rerun_history(self) -> Dict[str, list]:
        """Get list of all rerun results"""
        history = {
            'transcription': [],
            'speaker_diarization': [],
            'ai_analysis': [],
            'face_tracking': []
        }

        for file in self.rerun_dir.glob("*.json"):
            filename = file.stem

            if filename.startswith('transcription_'):
                history['transcription'].append({
                    'file': str(file),
                    'name': filename,
                    'timestamp': file.stat().st_mtime
                })
            elif filename.startswith('diarization_'):
                history['speaker_diarization'].append({
                    'file': str(file),
                    'name': filename,
                    'timestamp': file.stat().st_mtime
                })
            elif filename.startswith('ai_analysis_'):
                history['ai_analysis'].append({
                    'file': str(file),
                    'name': filename,
                    'timestamp': file.stat().st_mtime
                })
            elif filename.startswith('face_tracking_'):
                history['face_tracking'].append({
                    'file': str(file),
                    'name': filename,
                    'timestamp': file.stat().st_mtime
                })

        # Sort by timestamp (most recent first)
        for key in history:
            history[key] = sorted(history[key], key=lambda x: x['timestamp'], reverse=True)

        return history
