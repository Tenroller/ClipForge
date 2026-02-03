"""
Video processing services for the processor API
"""

import os
import sys
import time
import asyncio
import subprocess
import json
from pathlib import Path
from typing import Dict, Any
import platform

# =============================================================================
# FFmpeg DLL Configuration for torio/torchaudio (MUST be FIRST before imports)
# This enables pyannote.audio speaker diarization on Windows
# =============================================================================
if platform.system() == "Windows":
    FFMPEG_SHARED_BIN = r"C:\ffmpeg-shared\ffmpeg-6.1.1-full_build-shared\bin"
    if os.path.exists(FFMPEG_SHARED_BIN):
        # CRITICAL: For Python 3.8+ on Windows, we must use os.add_dll_directory()
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(FFMPEG_SHARED_BIN)
            except Exception:
                pass  # Already added or other issues
        # Also add to PATH for subprocess calls
        current_path = os.environ.get("PATH", "")
        if FFMPEG_SHARED_BIN not in current_path:
            os.environ["PATH"] = FFMPEG_SHARED_BIN + os.pathsep + current_path

# FFmpeg pool for centralized process management
try:
    from utils.ffmpeg_pool import run_ffmpeg_command, get_ffmpeg_pool
    HAS_FFMPEG_POOL = True
except ImportError:
    HAS_FFMPEG_POOL = False
    # Fallback if pool not available
    def run_ffmpeg_command(cmd, description="FFmpeg", **kwargs):
        import subprocess
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

# Add vendors to path for video processing modules
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
vendors_path = project_root / "vendors"

# Add vendors directory to Python path for imports
if vendors_path.exists():
    sys.path.insert(0, str(vendors_path))
    print(f"Added vendors path to sys.path: {vendors_path}")
else:
    print(f"Warning: Could not find vendors directory at {vendors_path}")
    print("Video processing features may not work.")

from ..models import MoneyPrinterRequest, BrainrotRequest, PodcastClipsRequest, WorkflowType
from ..core.config import ProcessorConfig

from loguru import logger

# Bind logger with context for this module
logger = logger.bind(name="video_generator")


class VideoProcessingService:
    """Service for processing video generation workflows."""

    def __init__(self, config: ProcessorConfig, job_queue=None):
        self.config = config
        self.job_queue = job_queue
        self.setup_environment()
    
    def setup_environment(self):
        """Setup environment variables for video processing."""
        # Set API keys
        if self.config.pexels_api_key:
            os.environ["PEXELS_API_KEY"] = self.config.pexels_api_key
        if self.config.openrouter_api_key:
            os.environ["OPENROUTER_API_KEY"] = self.config.openrouter_api_key
        
        # Set output directories
        os.environ["VIDEOHELPER_OUTPUT_DIR"] = str(self.config.output_dir)
        
        # Setup espeak for TTS
        self.setup_espeak_environment()
    
    def setup_espeak_environment(self):
        """Setup espeak-ng environment for Kokoro TTS."""
        # Clear potentially problematic espeakng_loader environment variables
        for key in ['ESPEAK_DATA_PATH', 'ESPEAKNG_DATA_PATH', 'PHONEMIZER_ESPEAK_DATA_PATH', 'PHONEMIZER_ESPEAK_LIBRARY']:
            if key in os.environ:
                del os.environ[key]

        # Use system espeak-ng if available
        system_espeak_paths = [
            '/opt/homebrew/bin/espeak-ng',  # Homebrew ARM64
            '/usr/local/bin/espeak-ng',    # Homebrew x86_64
            '/usr/bin/espeak-ng',          # System package (Linux)
            'C:\\Program Files\\eSpeak NG\\espeak-ng.exe',  # Windows winget installation
            'C:\\Program Files (x86)\\eSpeak NG\\espeak-ng.exe'  # Windows 32-bit
        ]

        system_espeak_data_paths = [
            '/opt/homebrew/share/espeak-ng-data',  # Homebrew ARM64
            '/usr/local/share/espeak-ng-data',    # Homebrew x86_64
            '/usr/share/espeak-ng-data',          # System package (Linux) - standard location
            '/usr/lib/aarch64-linux-gnu/espeak-ng-data',  # Container location for ARM64
            '/usr/lib/x86_64-linux-gnu/espeak-ng-data',   # Container location for x86_64
            'C:\\Program Files\\eSpeak NG\\espeak-ng-data',  # Windows winget installation
            'C:\\Program Files (x86)\\eSpeak NG\\espeak-ng-data'  # Windows 32-bit
        ]

        system_espeak = None
        system_data = None

        for espeak_path in system_espeak_paths:
            if os.path.exists(espeak_path):
                system_espeak = espeak_path
                break

        for data_path in system_espeak_data_paths:
            if os.path.exists(data_path):
                system_data = data_path
                break

        if system_espeak and system_data:
            os.environ['PHONEMIZER_ESPEAK_PATH'] = system_espeak
            os.environ['ESPEAK_DATA_PATH'] = system_data

            # For Windows, also add to PATH if it's not already there
            if system_espeak.startswith('C:\\Program Files'):
                espeak_dir = os.path.dirname(system_espeak)
                current_path = os.environ.get('PATH', '')
                if espeak_dir not in current_path:
                    os.environ['PATH'] = espeak_dir + os.pathsep + current_path

            logger.info(f"✅ Configured system espeak-ng for Kokoro TTS:")
            logger.info(f"   ESPEAK_PATH: {system_espeak}")
            logger.info(f"   DATA_PATH: {system_data}")
        else:
            # Fallback to espeakng_loader if system installation not found
            try:
                import espeakng_loader  # type: ignore
                espeak_data_path = espeakng_loader.get_data_path()
                espeak_lib_path = espeakng_loader.get_library_path()
                if espeak_data_path and os.path.exists(espeak_data_path):
                    os.environ['ESPEAK_DATA_PATH'] = espeak_data_path
                    os.environ['PHONEMIZER_ESPEAK_DATA_PATH'] = espeak_data_path
                if espeak_lib_path and os.path.exists(espeak_lib_path):
                    os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = espeak_lib_path
                logger.warning(f"⚠️  Using espeakng_loader (may have issues):")
                logger.warning(f"   DATA_PATH: {espeak_data_path}")
                logger.warning(f"   LIB_PATH: {espeak_lib_path}")
            except ImportError:
                logger.error("❌ Neither system espeak-ng nor espeakng_loader found - Kokoro TTS may not work")
                logger.error("   Install espeak-ng: brew install espeak-ng (macOS) or apt install espeak-ng (Ubuntu)")
            except Exception as e:
                logger.error(f"⚠️  Error setting up espeak-ng environment: {e}")

    async def process_moneyprinter_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a MoneyPrinter video generation job."""
        job_id = job_data["job_id"]
        request_data = job_data["request_data"]

        logger.info(f"Starting MoneyPrinter job {job_id}")

        try:
            # Parse request
            req = MoneyPrinterRequest(**request_data)

            # Import video generation dependencies from local vendors
            vendor_imports_available = False
            try:
                from AIvideos.utils import fetch_songs, check_env_vars
                from AIvideos.gpt import generate_script
                from AIvideos.tiktokvoice import tts
                vendor_imports_available = True
                logger.info(f"Job {job_id}: Successfully imported from local vendors")
            except ImportError as e:
                logger.warning(f"Job {job_id}: Could not import from local vendors: {e}")
                logger.info(f"Job {job_id}: Using fallback implementations")
                from ..utils.backend_fallbacks import check_env_vars, generate_script_fallback as generate_script, tts_fallback as tts

                # Define fallback fetch_songs function
                def fetch_songs(zip_url):
                    logger.warning(f"Job {job_id}: fetch_songs not available - skipping music download")
                    pass

            # Validate environment
            logger.info(f"Job {job_id}: Validating environment")
            try:
                check_env_vars()
            except SystemExit:
                raise RuntimeError("Missing required AIvideos environment variables")

            # Create job-specific output directory
            job_output_dir = self.config.output_dir / job_id
            job_output_dir.mkdir(parents=True, exist_ok=True)

            # Music handling - run in thread pool to avoid blocking
            if req.useMusic and req.zipUrl:
                logger.info(f"Job {job_id}: Fetching background music")
                await asyncio.to_thread(fetch_songs, req.zipUrl)

            # Generate script - run in thread pool to avoid blocking the event loop
            logger.info(f"Job {job_id}: Generating script")
            script = await asyncio.to_thread(
                generate_script,
                req.videoSubject,
                req.paragraphNumber,
                req.aiModel,
                req.voice,
                req.customPrompt or ""
            )

            if not script:
                raise RuntimeError("Failed to generate script")

            logger.info(f"Job {job_id}: Generated script ({len(script)} characters)")

            # Generate TTS - run in thread pool to avoid blocking
            logger.info(f"Job {job_id}: Generating text-to-speech")
            audio_file = str(job_output_dir / f"{job_id}_audio.wav")
            await asyncio.to_thread(tts, script, req.voice, audio_file)
            
            # Generate video with background footage or simple background
            logger.info(f"Job {job_id}: Generating video")
            try:
                # Create video output path
                output_video = str(job_output_dir / f"{job_id}_video.mp4")
                
                # Option 1: Try to get background videos if API key is available
                background_videos = []
                pexels_key = os.getenv("PEXELS_API_KEY", "")
                
                if pexels_key:
                    try:
                        if vendor_imports_available:
                            from AIvideos.search import search_for_stock_videos
                        else:
                            from ..utils.backend_fallbacks import search_for_stock_videos_fallback as search_for_stock_videos
                        
                        logger.info(f"Job {job_id}: Searching for background videos")
                        background_videos = search_for_stock_videos(
                            query=req.videoSubject[:50],
                            api_key=pexels_key,
                            it=5,  # Get 5 videos
                            min_dur=10
                        )
                        logger.info(f"Job {job_id}: Found {len(background_videos)} background videos")
                    except ImportError as e:
                        logger.error(f"Job {job_id}: Could not import video search module: {e}")
                        background_videos = []  # Fallback to no background videos
                    except Exception as search_error:
                        logger.warning(f"Job {job_id}: Background video search failed: {search_error}")
                        background_videos = []  # Fallback to no background videos
                
                # Get audio duration for video length - run in thread pool
                duration = 30  # Default fallback
                try:
                    def get_audio_duration():
                        probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', audio_file]
                        result = run_ffmpeg_command(probe_cmd, description=f"Probe audio duration: {job_id}", check=False)
                        if result.returncode == 0:
                            probe_data = json.loads(result.stdout)
                            format_info = probe_data.get('format', {})
                            return float(format_info.get('duration', 0))
                        return 30

                    duration = await asyncio.to_thread(get_audio_duration)
                    logger.info(f"Job {job_id}: Audio duration is {duration:.2f} seconds")
                except Exception as duration_error:
                    logger.warning(f"Job {job_id}: Could not get audio duration: {duration_error}")
                
                # Create video using ffmpeg - run in thread pool to avoid blocking
                if background_videos:
                    # Option A: Use background videos
                    logger.info(f"Job {job_id}: Creating video with background footage")

                    # Download first background video for now (simplified)
                    import requests
                    import tempfile

                    def download_and_process_video():
                        """Download background video and combine with audio using ffmpeg."""
                        bg_video_url = background_videos[0]
                        logger.info(f"Job {job_id}: Downloading background video")

                        response = requests.get(bg_video_url, stream=True)
                        response.raise_for_status()

                        # Save to temp file
                        temp_bg_video = str(job_output_dir / f"{job_id}_background.mp4")
                        with open(temp_bg_video, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)

                        # Combine background video with audio using ffmpeg
                        ffmpeg_cmd = [
                            'ffmpeg', '-y',
                            '-i', temp_bg_video,  # Background video
                            '-i', audio_file,     # Audio
                            '-t', str(duration),  # Duration
                            '-c:v', 'libx264', '-c:a', 'aac',
                            '-map', '0:v:0', '-map', '1:a:0',
                            '-shortest', output_video
                        ]

                        result = run_ffmpeg_command(ffmpeg_cmd, description=f"Combine bg video + audio: {job_id}", check=False)
                        if result.returncode != 0:
                            raise RuntimeError(f"FFmpeg background video failed: {result.stderr}")

                        # Clean up temp file
                        try:
                            os.unlink(temp_bg_video)
                        except:
                            pass

                    try:
                        await asyncio.to_thread(download_and_process_video)
                    except Exception as bg_error:
                        logger.warning(f"Job {job_id}: Background video processing failed: {bg_error}")
                        raise bg_error

                else:
                    # Option B: Create simple black background video
                    logger.info(f"Job {job_id}: Creating video with black background")

                    def create_simple_video():
                        """Create simple black background video with audio."""
                        ffmpeg_cmd = [
                            'ffmpeg', '-y',
                            '-f', 'lavfi', '-i', f'color=black:size=1080x1920:duration={duration}:rate=24',
                            '-i', audio_file,
                            '-c:v', 'libx264', '-c:a', 'aac',
                            '-shortest', output_video
                        ]

                        result = run_ffmpeg_command(ffmpeg_cmd, description=f"Create simple video: {job_id}", check=False)
                        if result.returncode != 0:
                            raise RuntimeError(f"FFmpeg simple video failed: {result.stderr}")

                    await asyncio.to_thread(create_simple_video)
                
                # Verify video file was created
                if not os.path.exists(output_video):
                    raise RuntimeError("Video file was not created")
                
                # Get video file size for logging
                video_size = os.path.getsize(output_video) / (1024 * 1024)  # MB
                logger.info(f"Job {job_id}: Video generation completed. File size: {video_size:.1f}MB")
                
                return {
                    "status": "completed",
                    "script": script,
                    "audio_file": audio_file,
                    "video_file": output_video,
                    "output_dir": str(job_output_dir),
                    "job_id": job_id,
                    "message": "MoneyPrinter job completed with video generation"
                }
                
            except Exception as video_error:
                logger.error(f"Job {job_id} video generation failed: {video_error}")
                logger.info(f"Job {job_id}: Falling back to audio-only result")
                
                # Fallback to audio-only result
                return {
                    "status": "completed",
                    "script": script,
                    "audio_file": audio_file,
                    "output_dir": str(job_output_dir),
                    "job_id": job_id,
                    "message": "MoneyPrinter job completed (audio only - video generation failed)",
                    "error": f"Video generation error: {video_error}"
                }
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            raise
    
    async def process_brainrot_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a Brainrot compilation job."""
        job_id = job_data["job_id"]
        request_data = job_data["request_data"]
        
        logger.info(f"Starting Brainrot job {job_id}")
        
        try:
            # Parse request
            req = BrainrotRequest(**request_data)
            
            # Import brainrot dependencies from local vendors
            try:
                from Compilation.generator import TikYouGenerator
            except ImportError as e:
                logger.error(f"Job {job_id}: Could not import TikYouGenerator from local vendors: {e}")
                logger.error("This feature requires vendor modules to be available")
                raise RuntimeError("Brainrot processing requires vendor dependency that is not available")
            
            # Create job-specific output directory
            job_output_dir = self.config.output_dir / job_id
            job_output_dir.mkdir(parents=True, exist_ok=True)
            output_dir_str = str(job_output_dir.resolve())
            
            # Create generator
            generator = TikYouGenerator(output_dir=output_dir_str, tracker=None, request=req)

            # Process video - run in thread pool to avoid blocking
            logger.info(f"Job {job_id}: Processing source video")
            if req.youtubeUrl:
                # Process YouTube video (original functionality) - run in thread pool
                video_clips = await asyncio.to_thread(generator.process_single_video, req.youtubeUrl)
            elif req.uploadedVideoPath:
                # Process uploaded video file - run in thread pool
                video_clips = await asyncio.to_thread(self._process_uploaded_video, generator, req.uploadedVideoPath, job_id)
            else:
                raise RuntimeError("No video source provided")

            if not video_clips:
                raise RuntimeError("No clips generated from source video")

            logger.info(f"Job {job_id}: Generated {len(video_clips)} clips")

            # Generate compilations - run in thread pool to avoid blocking
            logger.info(f"Job {job_id}: Generating compilation videos")

            # Use appropriate video identifier for generate_tikyou_videos
            video_identifier = req.youtubeUrl if req.youtubeUrl else req.uploadedVideoPath

            generated_videos = await asyncio.to_thread(
                generator.generate_tikyou_videos,
                video_identifier,
                num_compilations=None if req.unlimited else req.numCompilations,
                min_duration=req.minDuration,
                max_duration=req.maxDuration,
                video_clips=video_clips
            )
            
            # Collect output files and convert to generated_videos format
            import os
            generated_videos = []
            for video_file in job_output_dir.rglob("*.mp4"):
                if video_file.is_file():
                    file_size_mb = os.path.getsize(video_file) / (1024 * 1024)  # Convert to MB

                    # Try to extract compilation info from filename
                    filename_lower = video_file.name.lower()
                    compilation_type = None
                    compilation_num = None

                    if "_normal" in filename_lower:
                        compilation_type = "normal"
                    elif "_tts" in filename_lower:
                        compilation_type = "tts"

                    # Extract compilation number
                    if "_compilation_" in filename_lower:
                        try:
                            parts = filename_lower.split("_compilation_")
                            if len(parts) > 1:
                                num_part = parts[1].split("_")[0].split(".")[0]
                                compilation_num = int(num_part)
                        except (ValueError, IndexError):
                            pass

                    generated_videos.append({
                        "path": str(video_file),
                        "size_mb": round(file_size_mb, 2),
                        "compilation_type": compilation_type,
                        "compilation_num": compilation_num,
                        "posted": False
                    })

            logger.info(f"Job {job_id}: Brainrot compilation completed, generated {len(generated_videos)} videos")

            return {
                "status": "completed",
                "generated_videos": generated_videos,
                "clips_count": len(video_clips),
                "job_id": job_id
            }
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            raise

    async def process_podcastclips_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a PodcastClips viral short-form video generation job."""
        job_id = job_data["job_id"]
        request_data = job_data["request_data"]

        logger.info(f"Starting PodcastClips job {job_id}")

        try:
            # Parse request
            req = PodcastClipsRequest(**request_data)

            # Import podcast clips processor from local vendors
            try:
                from PodcastClips.processor import process_podcast_clips
            except ImportError as e:
                logger.error(f"Job {job_id}: Could not import PodcastClips processor from local vendors: {e}")
                logger.error("This feature requires vendor modules to be available")
                raise RuntimeError("PodcastClips processing requires vendor dependency that is not available")

            # Create job-specific output directory
            job_output_dir = self.config.output_dir / job_id
            job_output_dir.mkdir(parents=True, exist_ok=True)
            output_dir_str = str(job_output_dir.resolve())

            logger.info(f"Job {job_id}: Processing podcast from {req.youtubeUrl}")

            # Get the current event loop to pass to the processor
            loop = asyncio.get_event_loop()

            # Process podcast clips using our processor - run in thread pool to avoid blocking
            result = await asyncio.to_thread(
                process_podcast_clips,
                job_id=job_id,
                parameters=request_data,
                output_dir=output_dir_str,
                job_queue=self.job_queue,
                loop=loop
            )

            # Collect output files and convert to generated_videos format with full AI metadata
            import os
            generated_videos = []
            
            # Get clips from result which contains full AI metadata
            clips_with_metadata = result.get("clips", result.get("generated_videos", []))
            
            for clip in clips_with_metadata:
                # Get the output path from clip data
                output_path = clip.get("output_path", "")
                
                # Verify file exists
                if output_path and os.path.isfile(output_path):
                    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    
                    # Extract AI metadata if available
                    ai_metadata = clip.get("ai_metadata", {})
                    
                    generated_videos.append({
                        "path": output_path,
                        "size_mb": round(file_size_mb, 2),
                        "posted": False,
                        # Include rich metadata for frontend
                        "title": clip.get("title", ai_metadata.get("title", "")),
                        "clip_index": clip.get("clip_index", 0),
                        "duration": clip.get("duration", 0),
                        "start_time": ai_metadata.get("start_time", clip.get("start_time", 0)),
                        "end_time": ai_metadata.get("end_time", clip.get("end_time", 0)),
                        "viral_score": ai_metadata.get("viral_score", clip.get("viral_score", 0)),
                        "hook_strength": ai_metadata.get("hook_strength", clip.get("hook_strength", 0)),
                        "confidence": ai_metadata.get("confidence", clip.get("confidence", 0)),
                        "hook": ai_metadata.get("hook", clip.get("hook", "")),
                        "caption": ai_metadata.get("caption", clip.get("caption", "")),
                        "reason": ai_metadata.get("reason", clip.get("viral_reason", "")),
                        "tags": ai_metadata.get("tags", clip.get("tags", [])),
                        "thumbnail_text": ai_metadata.get("thumbnail_text", clip.get("thumbnail_text", "")),
                        "face_coverage_pct": clip.get("face_coverage_pct", 0),
                    })
                else:
                    logger.warning(f"Clip file not found: {output_path}")
            
            # Fallback: If no clips from metadata, scan directory for files
            if not generated_videos:
                logger.warning("No clips found in result metadata, scanning directory")
                for video_file in job_output_dir.rglob("*.mp4"):
                    if video_file.is_file() and "_clip_" in video_file.name:
                        file_size_mb = os.path.getsize(video_file) / (1024 * 1024)
                        generated_videos.append({
                            "path": str(video_file),
                            "size_mb": round(file_size_mb, 2),
                            "posted": False
                        })

            logger.info(f"Job {job_id}: PodcastClips job completed, generated {len(generated_videos)} clips")

            return {
                "status": "completed",
                "generated_videos": generated_videos,
                "clips_count": result.get("total_clips_generated", len(generated_videos)),
                "job_id": job_id,
                "summary": result
            }

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            raise

    def _process_uploaded_video(self, generator, uploaded_video_path: str, job_id: str):
        """
        Process an uploaded video file (skip YouTube download step).
        
        This method replicates the video processing logic from process_single_video
        but starts from an already downloaded video file.
        """
        import os
        
        logger.info(f"Job {job_id}: Processing uploaded video file: {uploaded_video_path}")
        
        if not os.path.exists(uploaded_video_path):
            raise RuntimeError(f"Uploaded video file not found: {uploaded_video_path}")
        
        video_path = uploaded_video_path
        
        # Extract a video ID from the filename for consistency
        video_id = os.path.splitext(os.path.basename(uploaded_video_path))[0]
        
        # 1. Detect and crop pillarboxes on the main video (same as process_single_video)
        logger.info(f"Job {job_id}: Detecting and cropping pillarboxes from uploaded video")
        cropped_video_path = generator.processor.crop_video_if_vertical_with_blur(video_path)
        if cropped_video_path != video_path:
            logger.info(f"Job {job_id}: Pillarboxes detected and cropped")
            video_path = cropped_video_path
        else:
            logger.info(f"Job {job_id}: No pillarboxes detected or cropping not needed")
        
        # 2. Analyze the video for scenes (same as process_single_video)
        logger.info(f"Job {job_id}: Analyzing video for scenes")
        
        # Try to get cached analysis first
        cached_analysis = generator._get_cached_scene_analysis(video_path)
        if cached_analysis:
            logger.info(f"Job {job_id}: Using cached scene analysis")
            analysis = cached_analysis
        else:
            logger.info(f"Job {job_id}: Performing new scene analysis")
            analysis = generator.processor.analyze_video_scenes(video_path, threshold=15, method='scenedetect')
            # Cache the results
            generator._cache_scene_analysis(video_path, analysis)
            logger.info(f"Job {job_id}: Scene analysis completed and cached")
        
        is_compilation = analysis['is_compilation']
        scenes = analysis['scenes']
        
        logger.info(f"Job {job_id}: Analysis Results - Compilation: {is_compilation}, Scenes: {len(scenes)}, Duration: {analysis['duration']:.1f}s")
        
        video_clips = []
        
        if is_compilation and len(scenes) > 1:
            logger.info(f"Job {job_id}: Splitting compilation into {len(scenes)} scenes")
            # Split the video into scenes (same as process_single_video)
            temp_dir, split_videos = generator.processor.split_video_from_scenes(video_path, video_id, scenes)
            
            for split_info in split_videos:
                if os.path.exists(split_info['path']):
                    # Detect and crop pillarboxes on each clip
                    logger.info(f"Job {job_id}: Processing clip: {os.path.basename(split_info['path'])}")
                    cropped_clip_path = generator.processor.crop_video_if_vertical_with_blur(split_info['path'])
                    
                    # Get video info and orientation for the cropped clip
                    video_info = generator.processor.get_video_info(cropped_clip_path)
                    orientation = generator.processor.get_video_orientation(video_info)
                    
                    clip_info = {
                        'path': cropped_clip_path,
                        'start_time': split_info['start_time'],
                        'end_time': split_info['end_time'],
                        'duration': split_info['duration'],
                        'scene_number': split_info['scene_number'],
                        'orientation': orientation,
                        'temp_dir': temp_dir
                    }
                    video_clips.append(clip_info)
                    logger.info(f"Job {job_id}: Processed clip {split_info['scene_number']}: {cropped_clip_path}")
        else:
            # Single video or no scenes detected (same as process_single_video)
            logger.info(f"Job {job_id}: Processing as single video (no scene splitting)")
            
            # Get video info and orientation for the single video
            video_info = generator.processor.get_video_info(video_path)
            orientation = generator.processor.get_video_orientation(video_info)
            
            clip_info = {
                'path': video_path,
                'start_time': 0,
                'end_time': analysis['duration'],
                'duration': analysis['duration'],
                'scene_number': 1,
                'orientation': orientation,
                'temp_dir': None
            }
            video_clips.append(clip_info)
        
        logger.info(f"Job {job_id}: Uploaded video processing completed, generated {len(video_clips)} clips")
        return video_clips