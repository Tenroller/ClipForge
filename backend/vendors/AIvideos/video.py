import os
import uuid
import subprocess
import sys

import requests
import srt_equalizer
import assemblyai as aai
from .enhanced_subtitles import SubtitleConfig

# Add path to access backend logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from logging_config import get_logger, log_generation_step, log_file_operation, log_api_call

# Initialize logger for this module
logger = get_logger("video_generator.ai_videos")


from typing import List, Dict, Optional, Union, Any, cast, Tuple
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    TextClip,
    ColorClip,
    concatenate_videoclips,
)

# Import centralized font utility
try:
    from font_detection import get_font_fallback_list
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    backend_dir = Path(__file__).resolve().parent.parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from font_detection import get_font_fallback_list
from termcolor import colored
from dotenv import load_dotenv
from pathlib import Path
from datetime import timedelta
from moviepy import vfx
from moviepy.video.tools.subtitles import SubtitlesClip
import inspect
try:
    # Use imageio-ffmpeg to reliably locate ffmpeg on all platforms
    from imageio_ffmpeg import get_ffmpeg_exe  # type: ignore
except Exception:  # pragma: no cover - optional dependency resolution
    get_ffmpeg_exe = None  # type: ignore

try:
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    load_dotenv("../.env")

ASSEMBLY_AI_API_KEY = os.getenv("ASSEMBLY_AI_API_KEY")


def test_gpu_encoding():
    """Test if GPU encoding is actually working by running a simple FFmpeg command."""
    try:
        # First check for FFMPEG_PATH environment variable
        ffmpeg_cmd = 'ffmpeg'
        ffmpeg_path_env = os.getenv('FFMPEG_PATH')
        if ffmpeg_path_env:
            ffmpeg_cmd = ffmpeg_path_env
        else:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg_cmd = get_ffmpeg_exe() if get_ffmpeg_exe else 'ffmpeg'

        # Test NVENC encoding
        result = subprocess.run([
            ffmpeg_cmd, '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
            '-c:v', 'h264_nvenc', '-f', 'null', '-'
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            print(colored("[+] GPU encoding test PASSED - NVENC is working", "green"))
            return True
        else:
            print(colored(f"[-] GPU encoding test FAILED: {result.stderr}", "red"))
            return False
    except Exception as e:
        print(colored(f"[-] GPU encoding test ERROR: {e}", "red"))
        return False

def detect_gpu_codec() -> Optional[Dict[str, Union[str, List[str]]]]:
    """
    Detects available GPU encoders and returns optimal codec settings.
    
    Returns:
        Dict with codec settings if GPU encoder is available, None otherwise
    """
    try:
        # Resolve ffmpeg executable path (works even if ffmpeg isn't on PATH)
        ffmpeg_cmd: str = 'ffmpeg'
        
        # First check for FFMPEG_PATH environment variable
        ffmpeg_path_env = os.getenv('FFMPEG_PATH')
        if ffmpeg_path_env:
            ffmpeg_cmd = ffmpeg_path_env
            print(colored(f"[i] Using FFMPEG_PATH from environment: {ffmpeg_cmd}", "blue"))
        elif get_ffmpeg_exe:
            try:
                ffmpeg_cmd = get_ffmpeg_exe()  # type: ignore[assignment]
            except Exception:
                # Final fallback - check environment variable again
                ffmpeg_path_env = os.getenv('FFMPEG_PATH')
                ffmpeg_cmd = ffmpeg_path_env if ffmpeg_path_env else 'ffmpeg'

        # Check for available encoders to determine GPU support
        print(colored(f"[i] Using ffmpeg at: {ffmpeg_cmd}", "blue"))
        result = subprocess.run([ffmpeg_cmd, '-encoders'],
                                capture_output=True, text=True, timeout=10)
        encoders_output = result.stdout
        # Log a short snippet to help debug encoder availability
        if encoders_output:
            has_nvenc = ('h264_nvenc' in encoders_output) or ('hevc_nvenc' in encoders_output) or ('av1_nvenc' in encoders_output)
            has_qsv = ('h264_qsv' in encoders_output) or ('hevc_qsv' in encoders_output)
            has_amf = ('h264_amf' in encoders_output) or ('hevc_amf' in encoders_output)
            print(colored(f"[i] ffmpeg GPU encoders — NVENC:{has_nvenc} QSV:{has_qsv} AMF:{has_amf}", "blue"))
        
        if 'h264_nvenc' in encoders_output:
            print(colored("[+] NVIDIA GPU encoder (NVENC) detected!", "green"))
            # Test if GPU encoding actually works
            if test_gpu_encoding():
                print(colored("[+] GPU encoding test PASSED - using NVENC", "green"))
            else:
                print(colored("[-] GPU encoding test FAILED - falling back to CPU", "red"))
                return None
            return {
                'codec': 'h264_nvenc',
                'ffmpeg_params': [
                    '-preset', 'fast',
                    '-crf', '18',
                    '-b:v', '5M',
                    '-maxrate', '10M',
                    '-bufsize', '20M',
                    '-profile:v', 'high'
                ]
            }
        elif 'h264_qsv' in encoders_output:
            print(colored("[+] Intel Quick Sync Video encoder detected!", "green"))
            return {
                'codec': 'h264_qsv',
                'ffmpeg_params': [
                    '-preset', 'fast',
                    '-global_quality', '18',
                    '-b:v', '5M',
                    '-maxrate', '10M',
                    '-bufsize', '20M'
                ]
            }
        elif 'h264_amf' in encoders_output:
            print(colored("[+] AMD AMF encoder detected!", "green"))
            return {
                'codec': 'h264_amf',
                'ffmpeg_params': [
                    '-quality', 'speed',
                    '-rc', 'vbr_peak',
                    '-crf', '18',
                    '-b:v', '5M',
                    '-maxrate', '10M',
                    '-bufsize', '20M'
                ]
            }
        else:
            print(colored("[-] No GPU encoders detected, falling back to CPU encoding", "yellow"))
            return None
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        print(colored("[-] Could not detect GPU encoders, falling back to CPU encoding", "yellow"))
        return None


def get_video_codec_settings(use_gpu: bool = True) -> Dict[str, Any]:
    """
    Returns optimal video codec settings based on available hardware.
    
    Args:
        use_gpu (bool): Whether to attempt GPU acceleration
        
    Returns:
        Dict with codec settings for moviepy
    """
    if use_gpu:
        gpu_config = detect_gpu_codec()
        if gpu_config:
            return {
                'codec': gpu_config['codec'],
                'ffmpeg_params': gpu_config['ffmpeg_params'],
                'logger': None,
            }
    
    # Fallback to optimized CPU encoding
    print(colored("[+] Using optimized CPU encoding", "blue"))
    return {
        'codec': 'libx264',
        'ffmpeg_params': [
            '-preset', 'fast',
            '-crf', '18',
            '-profile:v', 'high',
            '-pix_fmt', 'yuv420p'
        ],
        'logger': None,
    }


def save_video(video_url: str, directory: str = "../../../temp") -> str:
    """
    Saves a video from a given URL and returns the path to the video.

    Args:
        video_url (str): The URL of the video to save.
        directory (str): The path of the temporary directory to save the video to

    Returns:
        str: The path to the saved video.
    """
    video_id = uuid.uuid4()
    video_path = f"{directory}/{video_id}.mp4"
    
    max_retries = 3
    timeout = 120  # 2 minutes timeout
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Video download attempt {attempt + 1}/{max_retries}: {video_url[:60]}...")
            
            # Use streaming download with timeout
            response = requests.get(video_url, timeout=timeout, stream=True)
            response.raise_for_status()  # Raises an exception for HTTP error codes
            
            with open(video_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive chunks
                        f.write(chunk)
            
            file_size = os.path.getsize(video_path)
            logger.info(f"Video downloaded successfully: {file_size:,} bytes")
            return video_path
            
        except requests.exceptions.Timeout:
            logger.warning(f"Download timeout on attempt {attempt + 1}")
            if attempt == max_retries - 1:
                raise RuntimeError(f"Video download timed out after {max_retries} attempts (timeout: {timeout}s)")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise RuntimeError(f"Video download failed after {max_retries} attempts: {str(e)}")
                
        except Exception as e:
            logger.warning(f"Unexpected error on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise RuntimeError(f"Video download failed with unexpected error: {str(e)}")
        
        # Clean up partial file if it exists
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except:
                pass
                
        # Wait before retry
        if attempt < max_retries - 1:
            import time
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            print(colored(f"[info] Waiting {wait_time}s before retry...", "blue"))
            time.sleep(wait_time)
    
    # This should never be reached due to the raise statements above, but satisfy type checker
    raise RuntimeError("Video download failed after all retry attempts")


def __generate_subtitles_assemblyai(audio_path: str, voice: str) -> str:
    """
    Generates subtitles from a given audio file and returns the path to the subtitles.

    Args:
        audio_path (str): The path to the audio file to generate subtitles from.

    Returns:
        str: The generated subtitles
    """

    language_mapping = {
        "br": "pt",
        "id": "en", #AssemblyAI doesn't have Indonesian 
        "jp": "ja",
        "kr": "ko",
    }

    if voice in language_mapping:
        lang_code = language_mapping[voice]
    else:
        lang_code = voice

    aai.settings.api_key = ASSEMBLY_AI_API_KEY
    config = aai.TranscriptionConfig(language_code=lang_code)
    transcriber = aai.Transcriber(config=config)
    transcript = transcriber.transcribe(audio_path)
    subtitles = transcript.export_subtitles_srt()

    return subtitles


def __generate_subtitles_locally(sentences: List[str], audio_clips: List[AudioFileClip]) -> str:
    """
    Generates subtitles from a given audio file and returns the path to the subtitles.

    Args:
        sentences (List[str]): all the sentences said out loud in the audio clips
        audio_clips (List[AudioFileClip]): all the individual audio clips which will make up the final audio track
    Returns:
        str: The generated subtitles
    """

    def convert_to_srt_time_format(total_seconds):
        # Convert total seconds to the SRT time format: HH:MM:SS,mmm
        if total_seconds == 0:
            return "0:00:00,0"
        return str(timedelta(seconds=total_seconds)).rstrip('0').replace('.', ',')

    start_time = 0
    subtitles = []

    for i, (sentence, audio_clip) in enumerate(zip(sentences, audio_clips), start=1):
        duration = audio_clip.duration
        end_time = start_time + duration

        # Format: subtitle index, start time --> end time, sentence
        subtitle_entry = f"{i}\n{convert_to_srt_time_format(start_time)} --> {convert_to_srt_time_format(end_time)}\n{sentence}\n"
        subtitles.append(subtitle_entry)

        start_time += duration  # Update start time for the next subtitle

    return "\n".join(subtitles)


def convert_enhanced_to_srt_fallback(enhanced_subtitle_path: str) -> str | None:
    """
    Convert enhanced subtitle JSON format to SRT format for fallback processing.
    
    Args:
        enhanced_subtitle_path: Path to the enhanced subtitle JSON file
        
    Returns:
        str: Path to the generated SRT file, or None if conversion fails
    """
    try:
        import json
        from pathlib import Path
        
        # Load enhanced subtitle data
        with open(enhanced_subtitle_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract sentences and timing data
        sentences = data.get('sentences', [])
        word_timings = data.get('word_timings', [])
        
        if not sentences or not word_timings:
            print("No sentence or timing data found in enhanced subtitle file")
            return None
        
        # Group word timings by sentence
        sentence_timings = {}
        for word_timing in word_timings:
            sentence_idx = word_timing.get('sentence_index', 0)
            if sentence_idx not in sentence_timings:
                sentence_timings[sentence_idx] = []
            sentence_timings[sentence_idx].append(word_timing)
        
        # Convert to SRT format
        def convert_to_srt_time_format(total_seconds):
            if total_seconds == 0:
                return "00:00:00,000"
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            milliseconds = int((total_seconds % 1) * 1000)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
        
        srt_entries = []
        for i, sentence in enumerate(sentences):
            if i in sentence_timings and sentence_timings[i]:
                # Get timing from word timings
                words = sentence_timings[i]
                start_time = min(word['start_time'] for word in words)
                end_time = max(word['end_time'] for word in words)
            else:
                # Fallback: estimate timing based on sentence index
                start_time = i * 2.0  # 2 seconds per sentence
                end_time = (i + 1) * 2.0
            
            # Create SRT entry
            srt_entry = f"{i + 1}\n{convert_to_srt_time_format(start_time)} --> {convert_to_srt_time_format(end_time)}\n{sentence}\n"
            srt_entries.append(srt_entry)
        
        # Generate SRT file path
        enhanced_path = Path(enhanced_subtitle_path)
        srt_path = enhanced_path.with_suffix('.srt')
        
        # Write SRT file
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(srt_entries))
        
        return str(srt_path)
        
    except Exception as e:
        print(f"Error converting enhanced subtitles to SRT: {e}")
        return None


def generate_enhanced_subtitles_for_video(sentences: List[str], audio_clips: List[AudioFileClip], config: Optional[SubtitleConfig] = None) -> str:
    """
    Generate enhanced subtitles using whisper-timestamped for direct video integration.

    Args:
        sentences: List of sentences to transcribe
        audio_clips: List of audio clips for timing
        config: Subtitle configuration

    Returns:
        Path to enhanced subtitle file
    """
    from .enhanced_subtitles import generate_enhanced_subtitles, create_tiktok_style_config

    if config is None:
        config = create_tiktok_style_config()

    return generate_enhanced_subtitles(sentences, audio_clips, config)


def generate_subtitles(audio_path: str, sentences: List[str], audio_clips: List[AudioFileClip], voice: str) -> str:
    """
    Generates subtitles from a given audio file and returns the path to the subtitles.

    Args:
        audio_path (str): The path to the audio file to generate subtitles from.
        sentences (List[str]): all the sentences said out loud in the audio clips
        audio_clips (List[AudioFileClip]): all the individual audio clips which will make up the final audio track

    Returns:
        str: The path to the generated subtitles.
    """

    def equalize_subtitles(srt_path: str, max_chars: int = 70) -> None:
        # Equalize subtitles - increased max_chars from 50 to 70 for better text fitting
        srt_equalizer.equalize_srt_file(srt_path, srt_path, max_chars)

    # Save subtitles
    subtitles_path = f"./subtitles/{uuid.uuid4()}.srt"

    if ASSEMBLY_AI_API_KEY is not None and ASSEMBLY_AI_API_KEY != "":
        print(colored("[+] Creating subtitles using AssemblyAI", "blue"))
        subtitles = __generate_subtitles_assemblyai(audio_path, voice)
    else:
        print(colored("[+] Creating subtitles locally", "blue"))
        subtitles = __generate_subtitles_locally(sentences, audio_clips)
        # print(colored("[-] Local subtitle generation has been disabled for the time being.", "red"))
        # print(colored("[-] Exiting.", "red"))
        # sys.exit(1)

    # Ensure subtitles directory exists
    from pathlib import Path as _Path  # local alias to avoid confusion
    _Path(subtitles_path).parent.mkdir(parents=True, exist_ok=True)

    with open(subtitles_path, "w", encoding="utf-8") as file:
        file.write(subtitles)

    # Equalize subtitles
    equalize_subtitles(subtitles_path)

    print(colored("[+] Subtitles generated.", "green"))

    return subtitles_path


def combine_videos(video_paths: List[str], max_duration: int, max_clip_duration: int, threads: int, use_gpu: bool = True, use_streaming: bool = False) -> str:
    """
    Combines a list of videos into one video and returns the path to the combined video.

    Args:
        video_paths (List): A list of paths to the videos to combine.
        max_duration (int): The maximum duration of the combined video.
        max_clip_duration (int): The maximum duration of each clip.
        threads (int): The number of threads to use for the video processing.
        use_gpu (bool): Whether to use GPU acceleration.
        use_streaming (bool): Whether to use streaming processing for memory efficiency.

    Returns:
        str: The path to the combined video.
    """
    # Try streaming mode first if requested
    if use_streaming:
        try:
            from ...utils.streaming_processor import get_streaming_processor
            processor = get_streaming_processor()

            print(colored("[+] Attempting streaming video combination for memory efficiency...", "blue"))

            result = processor.combine_videos_streaming(
                video_paths=video_paths,
                target_duration=float(max_duration),
                min_clip_duration=float(max_clip_duration),
                max_threads=threads,
                use_gpu=use_gpu
            )

            if result:
                print(colored(f"[+] Streaming combination successful: {result}", "green"))
                return result
            else:
                print(colored("[-] Streaming combination failed, falling back to traditional method", "yellow"))
        except Exception as e:
            print(colored(f"[-] Streaming combination error: {e}, falling back to traditional method", "yellow"))
    video_id = uuid.uuid4()
    combined_video_path = f"../../../temp/{video_id}.mp4"
    
    # Required duration of each clip
    req_dur = max_duration / len(video_paths)

    print(colored("[+] Combining videos...", "blue"))
    print(colored(f"[+] Each clip will be maximum {req_dur} seconds long.", "blue"))

    clips = []
    tot_dur = 0
    # Add downloaded clips over and over until the duration of the audio (max_duration) has been reached
    while tot_dur < max_duration:
        for video_path in video_paths:
            try:
                clip = VideoFileClip(video_path)
                clip = clip.without_audio()
                
                # Check if clip is longer than the remaining audio
                if (max_duration - tot_dur) < clip.duration:
                    clip = clip.subclipped(0, (max_duration - tot_dur))
                # Only shorten clips if the calculated clip length (req_dur) is shorter than the actual clip to prevent still image
                elif req_dur < clip.duration:
                    clip = clip.subclipped(0, req_dur)
                    
                # Ensure consistent fps
                clip = clip.with_fps(30)

                # Handle different aspect ratios and sizes more robustly
                # Target aspect ratio is 9:16 (0.5625)
                current_aspect = clip.w / clip.h
                target_aspect = 9 / 16  # 0.5625
                
                print(f"Processing clip: {clip.w}x{clip.h}, aspect: {current_aspect:.4f}, target: {target_aspect:.4f}")
                
                if abs(current_aspect - target_aspect) > 0.01:  # Need aspect ratio adjustment
                    if current_aspect < target_aspect:
                        # Clip is too tall, crop height
                        new_height = round(clip.w / target_aspect)
                        # Ensure even height for H.264 compatibility
                        new_height = new_height if new_height % 2 == 0 else new_height - 1
                        if new_height < clip.h and new_height > 0:
                            clip = clip.with_effects([vfx.Crop(
                                width=clip.w, 
                                height=new_height,
                                x_center=clip.w / 2, 
                                y_center=clip.h / 2
                            )])
                    else:
                        # Clip is too wide, crop width  
                        new_width = round(clip.h * target_aspect)
                        # Ensure even width for H.264 compatibility
                        new_width = new_width if new_width % 2 == 0 else new_width - 1
                        if new_width < clip.w and new_width > 0:
                            clip = clip.with_effects([vfx.Crop(
                                width=new_width,
                                height=clip.h,
                                x_center=clip.w / 2, 
                                y_center=clip.h / 2
                            )])
                
                # Resize to target dimensions (1080x1920) - ensure even dimensions
                target_width = 1080  # Already even
                target_height = 1920  # Already even
                clip = clip.with_effects([vfx.Resize(width=target_width, height=target_height)])

                # Limit clip duration if needed
                if clip.duration > max_clip_duration:
                    clip = clip.subclipped(0, max_clip_duration)

                clips.append(clip)
                tot_dur += clip.duration
                
                print(f"Added clip: duration={clip.duration:.2f}s, total_duration={tot_dur:.2f}s")
                
            except Exception as e:
                print(f"Error processing video {video_path}: {e}")
                continue

    if not clips:
        raise ValueError("No valid clips could be processed")
        
    print(f"Concatenating {len(clips)} clips with total duration {tot_dur:.2f}s...")
    final_clip = concatenate_videoclips(clips, method="compose")
    final_clip = final_clip.with_fps(30)
    
    # Get GPU-optimized codec settings
    codec_settings = get_video_codec_settings(use_gpu)
    # Remove 'logger' from codec_settings to avoid parameter conflict
    write_settings = {k: v for k, v in codec_settings.items() if k != 'logger'}

    # Debug: Print actual codec settings being used
    print(colored(f"[debug] Using codec: {write_settings.get('codec', 'unknown')}", "cyan"))
    print(colored(f"[debug] FFmpeg params: {write_settings.get('ffmpeg_params', 'none')}", "cyan"))
    
    try:
        final_clip_typed: CompositeVideoClip = cast(CompositeVideoClip, final_clip)
        final_clip_typed.write_videofile(
            combined_video_path,
            threads=threads,
            logger="bar",
            **write_settings
        )
        
        # Clean up clips to free memory
        for clip in clips:
            try:
                clip.close()
            except:
                pass
                
        try:
            final_clip.close()
        except:
            pass
            
    except Exception as e:
        # Clean up on error
        for clip in clips:
            try:
                clip.close()
            except:
                pass
        try:
            final_clip.close()  
        except:
            pass
        raise Exception(f"Video write failed: {e}")

    return combined_video_path


def create_simple_subtitle_fallback(subtitles_path: str, video_size: Tuple[int, int], subtitles_position: str, text_color: str) -> CompositeVideoClip:
    """
    Create a simple subtitle fallback when enhanced subtitles fail.
    
    This function attempts to extract text from the enhanced subtitle file
    and create basic text clips as a fallback.
    """
    try:
        import json
        with open(subtitles_path, 'r', encoding='utf-8') as f:
            subtitle_data = json.load(f)
        
        # Extract sentences from enhanced subtitle data
        sentences = subtitle_data.get('sentences', [])
        if not sentences:
            return create_empty_subtitle_clip(video_size)
        
        # Create simple text clips for each sentence
        clips = []
        current_time = 0.0
        
        for sentence_data in sentences:
            sentence_text = sentence_data.get('text', '')
            sentence_duration = sentence_data.get('end_time', 0) - sentence_data.get('start_time', 0)
            
            if sentence_duration <= 0:
                sentence_duration = 2.0  # Default duration
            
            if sentence_text.strip():
                try:
                    # Create simple text clip with proper font handling
                    # Use the user's text color and add stroke for better visibility
                    # Use Arial font with fallbacks for compatibility
                    text_clip = TextClip(
                        text=sentence_text,
                        font_size=48,
                        color=text_color,
                        stroke_color="black",
                        stroke_width=2,
                        font=get_font_fallback_list()[0] or "Arial",  # Use centralized font
                        method='caption',
                        size=(int(video_size[0] * 0.8), None)
                    )
                    
                    # Position the clip using the user's specified position
                    positioned_clip = text_clip.with_position(subtitles_position).with_start(current_time).with_duration(sentence_duration)
                    clips.append(positioned_clip)
                    
                except Exception as e:
                    print(colored(f"[warn] Failed to create fallback text clip for sentence: {e}", "yellow"))
                    continue
            
            current_time += sentence_duration
        
        if clips:
            return CompositeVideoClip(clips)  # Let it size naturally
        else:
            return create_empty_subtitle_clip(video_size)
            
    except Exception as e:
        print(colored(f"[warn] Simple subtitle fallback failed: {e}", "yellow"))
        return create_empty_subtitle_clip(video_size)


def create_empty_subtitle_clip(video_size: Tuple[int, int]) -> CompositeVideoClip:
    """Create an empty transparent subtitle clip."""
    from moviepy import ColorClip
    empty_clip = ColorClip(size=video_size, color=(0,0,0,0)).with_opacity(0).with_duration(0.1)
    return empty_clip


def create_fallback_subtitle_clip(subtitles_path: str, video_size: Tuple[int, int], subtitles_position: str, text_color: str) -> CompositeVideoClip:
    """Create a fallback subtitle clip when the main subtitle system fails."""
    try:
        return create_simple_subtitle_fallback(subtitles_path, video_size, subtitles_position, text_color)
    except Exception:
        return create_empty_subtitle_clip(video_size)




def generate_video(combined_video_path: str, tts_path: str, subtitles_path: str, threads: int, subtitles_position: str, text_color: str, use_gpu: bool = True) -> str:
    """
    This function creates the final video, with subtitles and audio.

    Args:
        combined_video_path (str): The path to the combined video.
        tts_path (str): The path to the text-to-speech audio.
        subtitles_path (str): The path to the subtitles.
        threads (int): The number of threads to use for the video processing.
        subtitles_position (str): The position of the subtitles.

    Returns:
        str: The path to the final video.
    """
    # URGENT TEST: Verify this function is being called
    print(colored(f"[URGENT TEST] generate_video called with subtitles_path: {subtitles_path}", "red"))
    
    # Log inputs
    try:
        print(colored(f"[debug] generate_video: combined={combined_video_path} tts={tts_path} subs={subtitles_path}", "blue"))
        try:
            from PIL import __version__ as PIL_VERSION  # type: ignore
            print(colored(f"[debug] pillow version: {PIL_VERSION}", "blue"))
        except Exception:
            print(colored("[debug] pillow version: unknown (PIL import failed)", "yellow"))
        sig = None
        try:
            sig = str(inspect.signature(SubtitlesClip))
        except Exception:
            sig = "<signature unavailable>"
        print(colored(f"[debug] SubtitlesClip signature: {sig}", "blue"))
    except Exception:
        pass

    # Load base clip first to determine video dimensions
    base_clip = VideoFileClip(combined_video_path)
    video_size = (base_clip.w, base_clip.h)
    
    # Check if this is an enhanced subtitle file
    from .enhanced_subtitles import is_enhanced_subtitle_file, create_enhanced_subtitle_clip
    
    # Initialize variables
    is_enhanced = False
    subtitles = None
    
    # NEW: Try optimized subtitle pipeline first - but only if subtitles don't already exist
    try:
        from .optimized_subtitle_integration import (
            create_optimized_enhanced_subtitles,
            is_optimized_subtitle_available,
        )
    except ImportError as ie:
        print(colored(f"[warn] Optimized subtitle pipeline not available: {ie}", "yellow"))
        print(colored("[info] Using traditional subtitle processing", "blue"))

    # Traditional enhanced subtitle check (only if optimized pipeline didn't succeed)
    if subtitles is None:
        is_enhanced = is_enhanced_subtitle_file(subtitles_path) if subtitles_path else False
        print(colored(f"[debug] Enhanced subtitles detected: {is_enhanced}", "cyan"))
        
        # Additional validation for enhanced subtitle file
        if is_enhanced and subtitles_path:
            try:
                # Check if the enhanced subtitle file exists and has content
                if os.path.exists(subtitles_path) and os.path.getsize(subtitles_path) > 0:
                    print(colored(f"[debug] Enhanced subtitle file validated: {subtitles_path}", "green"))
                else:
                    print(colored(f"[warn] Enhanced subtitle file missing or empty: {subtitles_path}", "yellow"))
                    is_enhanced = False  # Fallback to traditional subtitles
            except Exception as file_check_error:
                print(colored(f"[warn] Enhanced subtitle file check failed: {file_check_error}", "yellow"))
                is_enhanced = False  # Fallback to traditional subtitles
    
    # Generator that returns a CompositeVideoClip (background box + text)
    def generator(txt: str):
        # Calculate font size relative to video height (targeting ~40-50px for 1920px height)
        try:
            video_height = int(getattr(base_clip, 'h', 1920) or 1920)
            # Scale font size based on video height - aim for 2.5% of video height
            font_size = max(24, int(video_height * 0.025))
        except Exception:
            video_height = 1920  # Fallback height
            font_size = 48  # Fallback for ~1920px height
            
        # Create TextClip with centralized font choices
        font_choices = get_font_fallback_list()
        text_clip = None
        
        for font_choice in font_choices:
            try:
                # Calculate video width for text wrapping
                video_width = int(getattr(base_clip, 'w', 1080) or 1080)
                max_text_width = int(video_width * 0.85)  # Use 85% of video width for better text fitting
                
                # Dynamically adjust font size for very long text to prevent cropping
                text_length = len(txt)
                if text_length > 100:  # Very long text
                    font_size = max(20, int(video_height * 0.02))
                elif text_length > 50:  # Moderately long text
                    font_size = max(22, int(video_height * 0.022))
                
                text_clip = TextClip(
                    text=txt,
                    font_size=font_size,
                    color=text_color,
                    stroke_color="black",
                    stroke_width=2,
                    font=font_choice,
                    method='caption',  # Use caption method for better text rendering
                    size=(max_text_width, None),  # Set max width for text wrapping
                )
                # Test if the clip has valid dimensions
                if hasattr(text_clip, 'w') and hasattr(text_clip, 'h') and text_clip.w > 0 and text_clip.h > 0:
                    print(colored(f"[debug] Successfully created TextClip with font: {font_choice or 'default'}, size: {text_clip.w}x{text_clip.h}", "green"))
                    break
                else:
                    print(colored(f"[warn] TextClip with font {font_choice} has invalid dimensions", "yellow"))
                    text_clip = None
            except Exception as e:
                print(colored(f"[warn] Font {font_choice} failed: {e}", "yellow"))
                text_clip = None
        
        # Final fallback with minimal parameters
        if text_clip is None:
            try:
                video_width = int(getattr(base_clip, 'w', 1080) or 1080)
                max_text_width = int(video_width * 0.85)  # Use 85% of video width for better text fitting
                
                # Dynamically adjust font size for very long text to prevent cropping
                text_length = len(txt)
                if text_length > 100:  # Very long text
                    font_size = max(20, int(video_height * 0.02))
                elif text_length > 50:  # Moderately long text
                    font_size = max(22, int(video_height * 0.022))
                
                text_clip = TextClip(
                    text=txt,
                    font_size=font_size,
                    color=text_color,
                    font=get_font_fallback_list()[0] or "Arial",  # Use centralized font
                    size=(max_text_width, None),
                )
                print(colored(f"[info] Using minimal TextClip fallback, size: {getattr(text_clip, 'w', 'unknown')}x{getattr(text_clip, 'h', 'unknown')}", "cyan"))
            except Exception as e:
                print(colored(f"[error] All TextClip creation methods failed: {e}", "red"))
                raise e
        # Match frontend padding: px-3 py-2 = 12px horizontal, 8px vertical
        pad_x = 12
        pad_y = 8
        bg_w = int(getattr(text_clip, 'w', 0) or 0) + 2 * pad_x
        bg_h = int(getattr(text_clip, 'h', 0) or 0) + 2 * pad_y
        # Semi-transparent background box - match frontend bg-black/40
        bg = ColorClip(size=(max(bg_w, 1), max(bg_h, 1)), color=(0, 0, 0)).with_opacity(0.4)
        composed = CompositeVideoClip([
            bg,
            text_clip.with_position((pad_x, pad_y)),
        ])
        return composed

    # Normalize and split the subtitles position
    # Supports:
    #  - "left,top" grid values (existing)
    #  - "pct:x,y" where x,y are percentages for the CENTER of the subtitle box
    #  - "px:x,y"  where x,y are absolute pixels for the TOP-LEFT of the subtitle box
    raw_pos = (subtitles_position or '').strip().lower()
    pos_mode = 'grid'
    pct_xy = (50.0, 85.0)
    px_xy = (0, 0)
    try:
        if raw_pos.startswith('pct:'):
            pos_mode = 'pct'
            import re as _re
            m = _re.match(r"pct:\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*([0-9]+(?:\.[0-9]+)?)", raw_pos)
            if m:
                pct_xy = (max(0.0, min(100.0, float(m.group(1)))), max(0.0, min(100.0, float(m.group(2)))))
        elif raw_pos.startswith('px:'):
            pos_mode = 'px'
            import re as _re
            m = _re.match(r"px:\s*([0-9]+)\s*,\s*([0-9]+)", raw_pos)
            if m:
                px_xy = (max(0, int(m.group(1))), max(0, int(m.group(2))))
        else:
            parts = [p.strip().lower() for p in raw_pos.split(',')]
            horizontal_subtitles_position = parts[0] if parts and parts[0] in ('left', 'center', 'right') else 'center'
            vertical_subtitles_position = parts[1] if len(parts) > 1 and parts[1] in ('top', 'center', 'bottom', 'botton') else 'bottom'
            if vertical_subtitles_position == 'botton':
                vertical_subtitles_position = 'bottom'
    except Exception:
        pos_mode = 'grid'
        horizontal_subtitles_position, vertical_subtitles_position = 'center', 'bottom'

    # Initialize subtitles variable to None to prevent UnboundLocalError
    subtitles = None

    # Handle different subtitle formats
    if is_enhanced:
        # Use new ASS-based enhanced subtitles
        print(colored(f"[debug] Using new ASS-based enhanced subtitles from: {subtitles_path}", "blue"))
        try:
            # For enhanced subtitles, we use a transparent placeholder since
            # the actual subtitles are burned in via FFmpeg
            subtitles = create_enhanced_subtitle_clip(subtitles_path, video_size)
            print(colored(f"[debug] Enhanced subtitle placeholder created successfully", "green"))

        except Exception as e:
            print(colored(f"[error] Enhanced subtitle creation failed: {e}", "red"))
            print(colored(f"[info] Falling back to simple subtitle fallback", "blue"))
            import traceback
            print(colored(f"[error] Traceback: {traceback.format_exc()}", "red"))

            # Fall back to simple subtitle fallback instead of raising
            is_enhanced = False
            subtitles = None  # Clear any partially created subtitle object

            # Try to create simple subtitle fallback
            try:
                subtitles = create_simple_subtitle_fallback(subtitles_path, video_size, subtitles_position, text_color)
                print(colored(f"[debug] Simple subtitle fallback created successfully", "green"))
            except Exception as fallback_error:
                print(colored(f"[warn] Simple subtitle fallback also failed: {fallback_error}", "yellow"))
                # Create empty subtitle as last resort
                subtitles = create_empty_subtitle_clip(video_size)
                print(colored(f"[debug] Created empty subtitle clip as final fallback", "yellow"))

    if not is_enhanced:
        # Use traditional SRT subtitles
        print(colored(f"[debug] Creating traditional SubtitlesClip from: {subtitles_path}", "blue"))
        
        # Validate subtitle file before creating SubtitlesClip
        try:
            from pathlib import Path as _Path
            srt_path = _Path(subtitles_path)
            if not srt_path.exists():
                raise FileNotFoundError(f"Subtitle file does not exist: {subtitles_path}")
            
            # Read and validate subtitle content
            with srt_path.open("r", encoding="utf-8") as f:
                subtitle_content = f.read().strip()
                if not subtitle_content:
                    raise ValueError("Subtitle file is empty")
                print(colored(f"[debug] Subtitle file size: {len(subtitle_content)} chars, first 200 chars: {subtitle_content[:200]}", "cyan"))
                
                # Additional check for SRT format vs JSON format
                if subtitle_content.startswith('{') and '"type"' in subtitle_content:
                    print(colored(f"[warn] Detected JSON format in subtitle file, but expected SRT format", "yellow"))
                    # This might be an enhanced subtitle file that wasn't converted properly
                    # Try to convert it
                    if '"tiktok_enhanced"' in subtitle_content:
                        converted_srt = convert_enhanced_to_srt_fallback(str(srt_path))
                        if converted_srt and _Path(converted_srt).exists():
                            subtitles_path = converted_srt
                            print(colored(f"[debug] Converted enhanced subtitle to SRT: {converted_srt}", "green"))
                        else:
                            raise ValueError("Failed to convert enhanced subtitle to SRT format")
                            
        except Exception as e:
            print(colored(f"[error] Subtitle file validation failed: {e}", "red"))
            # Last resort: create an empty subtitle to prevent crash
            print(colored(f"[warn] Creating empty subtitle clip to prevent crash", "yellow"))
            subtitles = create_empty_subtitle_clip(video_size)
            print(colored(f"[debug] Created empty subtitle clip as fallback", "yellow"))
        
        # Only try to create SubtitlesClip if subtitles is not already set (i.e., validation failed)
        if 'subtitles' not in locals():
            # Burn the subtitles into the video, applying safe-area positioning via a function
            # This aligns runtime rendering with the frontend preview (10%/50%/90% horizontally; 15%/50%/85% vertically)
            try:
                subtitles = SubtitlesClip(subtitles_path, make_textclip=generator)  # type: ignore[arg-type]
                print(colored(f"[debug] SubtitlesClip created successfully with make_textclip", "green"))
            except TypeError as e:
                # Fallback for older moviepy where positional arg is expected
                print(colored(f"[warn] SubtitlesClip(make_textclip=...) failed ({e}), retrying positional.", "yellow"))
                try:
                    subtitles = SubtitlesClip(subtitles_path, generator)
                    print(colored(f"[debug] SubtitlesClip created successfully with positional arg", "green"))
                except Exception as e2:
                    print(colored(f"[error] Both SubtitlesClip creation methods failed: {e2}", "red"))
                    # Create empty subtitle clip as last resort
                    subtitles = create_empty_subtitle_clip(video_size)
                    print(colored(f"[debug] Created empty subtitle clip as final fallback", "yellow"))

    # Position function computes px coords using base video size and current subtitle size
    def _safe_area_pos_fn(t):
        try:
            w = int(getattr(base_clip, 'w', 1080) or 1080)
            h = int(getattr(base_clip, 'h', 1920) or 1920)
            
            # Try to get current subtitle frame size at time t
            # SubtitlesClip may not expose w/h directly, so we need to be more clever
            sw = 0
            sh = 0
            
            try:
                # Try to get the current subtitle clip at this time
                current_clip = None
                if subtitles is not None and hasattr(subtitles, 'get_frame'):
                    current_clip = subtitles.get_frame(t)
                
                if current_clip is not None and hasattr(current_clip, 'shape'):
                    sh, sw = current_clip.shape[:2]  # numpy array shape is (height, width, channels)
                else:
                    # Fallback: try direct attribute access
                    if subtitles is not None:
                        sw = int(getattr(subtitles, 'w', 0) or 0)
                        sh = int(getattr(subtitles, 'h', 0) or 0)
            except Exception:
                # Final fallback: estimate based on video size and typical subtitle proportions
                if sw == 0 or sh == 0:
                    sw = int(w * 0.8)  # Assume subtitle is ~80% of video width
                    sh = int(h * 0.08)  # Assume subtitle is ~8% of video height
                    
            # Debug positioning calculations
            if sw > 0 and sh > 0:
                print(colored(f"[debug] Video: {w}x{h}, Subtitle: {sw}x{sh}, Position: {pos_mode}", "cyan"))
            else:
                print(colored(f"[warn] Using fallback subtitle dimensions: {sw}x{sh}", "yellow"))
                
        except Exception as e:
            print(colored(f"[warn] Error getting clip dimensions: {e}", "yellow"))
            w, h, sw, sh = 1080, 1920, int(1080 * 0.8), int(1920 * 0.08)

        if pos_mode == 'pct':
            # pct anchors are CENTER of subtitle box, expressed in percentages
            cx = int((pct_xy[0] / 100.0) * w)
            cy = int((pct_xy[1] / 100.0) * h)
            left = max(min(cx - int(sw / 2), w - sw), 0)
            top = max(min(cy - int(sh / 2), h - sh), 0)
            return (left, top)

        if pos_mode == 'px':
            # px anchors are TOP-LEFT of subtitle box
            left = max(min(px_xy[0], max(w - sw, 0)), 0)
            top = max(min(px_xy[1], max(h - sh, 0)), 0)
            return (left, top)

        def _x_from_h(hpos: str) -> int:
            # Align to the same grid model used by the frontend preview
            # Grid anchors are interpreted as the CENTER of the subtitle box
            # at 10% / 50% / 90% horizontally.
            if sw > 0:
                half_sw = int(sw / 2)
                if hpos == 'left':
                    x = int(0.10 * w) - half_sw
                    return max(min(x, w - sw), 0)
                if hpos == 'right':
                    x = int(0.90 * w) - half_sw
                    return max(min(x, w - sw), 0)
                # center
                return max(int((w - sw) / 2), 0)
            else:
                # Fallback positioning when subtitle width unknown
                if hpos == 'left':
                    return int(0.05 * w)  # 5% from left edge
                if hpos == 'right':
                    return int(0.75 * w)  # 75% from left (assuming 20% subtitle width)
                # center
                return int(0.50 * w)  # Center of video

        def _y_from_v(vpos: str) -> int:
            # Align to the same grid model used by the frontend preview
            # Grid anchors are interpreted as the CENTER of the subtitle box
            # at 15% / 50% / 85% vertically.
            if sh > 0:
                half_sh = int(sh / 2)
                if vpos == 'top':
                    y = int(0.15 * h) - half_sh
                    return max(min(y, h - sh), 0)
                if vpos == 'bottom':
                    # Changed to align subtitle bottom with 85% line instead of centering
                    y = int(0.85 * h) - sh
                    return max(min(y, h - sh), 0)
                # center
                return max(int((h - sh) / 2), 0)
            else:
                # Fallback positioning when subtitle height unknown
                if vpos == 'top':
                    return int(0.10 * h)  # 10% from top
                if vpos == 'bottom':
                    return int(0.80 * h)  # 80% from top (assuming ~5% subtitle height)
                # center
                return int(0.45 * h)  # Slightly above center

        final_x = _x_from_h(locals().get('horizontal_subtitles_position', 'center'))
        final_y = _y_from_v(locals().get('vertical_subtitles_position', 'bottom'))
        print(colored(f"[debug] Final subtitle position: ({final_x}, {final_y}) for {locals().get('horizontal_subtitles_position', 'center')},{locals().get('vertical_subtitles_position', 'bottom')}", "cyan"))
        return (final_x, final_y)

    # Handle positioning based on subtitle type with robust error handling
    if subtitles is None:
        # No subtitles available, create empty clip with video dimensions
        positioned_subs = create_empty_subtitle_clip(video_size)
        print(colored(f"[warn] No subtitles available, using transparent empty clip", "yellow"))
    elif is_enhanced:
        # Enhanced subtitles handle their own positioning
        positioned_subs = subtitles
        print(colored(f"[debug] Using enhanced subtitle positioning", "cyan"))
        print(colored(f"[debug] Enhanced subtitle type: {type(subtitles)}", "cyan"))
        # Only access clips on CompositeVideoClip, not SubtitlesClip
        if isinstance(subtitles, CompositeVideoClip):
            enhanced_subs = cast(CompositeVideoClip, subtitles)
            if hasattr(enhanced_subs, 'clips'):
                print(colored(f"[debug] Enhanced subtitle has {len(enhanced_subs.clips)} clips", "cyan"))
    else:
        # Traditional subtitles need manual positioning
        positioned_subs = subtitles.with_position(_safe_area_pos_fn)
        print(colored(f"[debug] Using traditional subtitle positioning", "cyan"))
    
    # Validate subtitle clip before composition to prevent mask dimension errors
    try:
        # Test if subtitle clip has valid dimensions and mask
        if hasattr(positioned_subs, 'w') and hasattr(positioned_subs, 'h'):
            subtitle_w = getattr(positioned_subs, 'w', 0) or 0
            subtitle_h = getattr(positioned_subs, 'h', 0) or 0
            print(colored(f"[debug] Subtitle clip dimensions: {subtitle_w}x{subtitle_h}", "cyan"))
            
            # Check for zero dimensions which can cause broadcasting errors
            if subtitle_w <= 0 or subtitle_h <= 0:
                print(colored(f"[warn] Subtitle clip has invalid dimensions ({subtitle_w}x{subtitle_h}), using simple subtitle fallback", "yellow"))
                positioned_subs = create_fallback_subtitle_clip(subtitles_path, video_size, subtitles_position, text_color)
        
        # Test subtitle clip by getting a test frame to validate mask consistency
        # Skip frame test for enhanced subtitles since they're working correctly
        if not is_enhanced:
            try:
                if hasattr(positioned_subs, 'duration') and positioned_subs.duration > 0:
                    test_time = min(0.1, positioned_subs.duration / 2)  # Use safe test time
                    test_frame = positioned_subs.get_frame(test_time)
                    if test_frame is not None and len(test_frame.shape) >= 2:
                        # Additional validation: check for zero-width or zero-height frames
                        frame_height, frame_width = test_frame.shape[:2]
                        if frame_width > 0 and frame_height > 0:
                            print(colored(f"[debug] Subtitle clip test frame shape: {test_frame.shape}", "green"))
                        else:
                            print(colored(f"[warn] Subtitle clip test frame has zero dimensions: {test_frame.shape}, using simple subtitle fallback", "yellow"))
                            print(colored(f"[debug] TRIGGERING FALLBACK: Frame dimensions are zero", "red"))
                            positioned_subs = create_simple_subtitle_fallback(subtitles_path, video_size, subtitles_position, text_color)
                    else:
                        print(colored(f"[warn] Subtitle clip test frame is invalid, using simple subtitle fallback", "yellow"))
                        print(colored(f"[debug] TRIGGERING FALLBACK: Invalid test frame", "red"))
                        positioned_subs = create_simple_subtitle_fallback(subtitles_path, video_size, subtitles_position, text_color)
                else:
                    print(colored(f"[warn] Subtitle clip has zero or invalid duration, using simple subtitle fallback", "yellow"))
                    print(colored(f"[debug] TRIGGERING FALLBACK: Invalid duration", "red"))
                    positioned_subs = create_simple_subtitle_fallback(subtitles_path, video_size, subtitles_position, text_color)
            except Exception as frame_test_error:
                print(colored(f"[warn] Subtitle clip frame test failed ({frame_test_error}), using simple subtitle fallback", "yellow"))
                print(colored(f"[debug] TRIGGERING FALLBACK: Frame test exception", "red"))
                # Try to create a more robust fallback that won't fail
                try:
                    positioned_subs = create_simple_subtitle_fallback(subtitles_path, video_size, subtitles_position, text_color)
                    if positioned_subs is None:
                        positioned_subs = create_empty_subtitle_clip(video_size)
                except Exception as fallback_error:
                    print(colored(f"[warn] Simple subtitle fallback also failed: {fallback_error}, using empty subtitle", "yellow"))
                    positioned_subs = create_empty_subtitle_clip(video_size)
        else:
            print(colored(f"[debug] Skipping frame test for enhanced subtitles - they are working correctly", "green"))
            
    except Exception as validation_error:
        print(colored(f"[warn] Subtitle validation failed ({validation_error}), using simple subtitle fallback", "yellow"))
        positioned_subs = create_fallback_subtitle_clip(subtitles_path, video_size, subtitles_position, text_color)
    
    # Ensure subtitle clips are properly prepared for composition
    try:
        # Remove any masks from subtitle clips to prevent broadcasting errors
        # Subtitles are text overlays and don't need transparency masking
        # Only access clips on CompositeVideoClip, not SubtitlesClip
        if isinstance(positioned_subs, CompositeVideoClip):
            composite_subs = cast(CompositeVideoClip, positioned_subs)
            if hasattr(composite_subs, 'clips') and composite_subs.clips:
                print(colored(f"[debug] Processing {len(composite_subs.clips)} subtitle clips - removing masks", "cyan"))
                for i, clip in enumerate(composite_subs.clips):
                    try:
                        if hasattr(clip, 'mask') and clip.mask is not None:
                            # Remove mask since subtitles don't need transparency
                            composite_subs.clips[i] = clip.without_mask()
                            print(colored(f"[debug] Removed mask from subtitle clip {i}", "yellow"))
                    except Exception as clip_fix_error:
                        print(colored(f"[warn] Could not remove mask from clip {i}: {clip_fix_error}", "yellow"))

        result: CompositeVideoClip = CompositeVideoClip([
            base_clip,
            positioned_subs,
        ])
        print(colored(f"[debug] Video composition successful", "green"))
    except Exception as composition_error:
        print(colored(f"[error] Video composition failed: {composition_error}", "red"))
        print(colored(f"[info] Creating fallback composition without subtitles", "blue"))

        # Simple fallback: create composition without subtitles
        empty_subs = create_empty_subtitle_clip(video_size)
        result: CompositeVideoClip = CompositeVideoClip([
            base_clip,
            empty_subs,
        ])
        print(colored(f"[debug] Fallback video composition successful", "yellow"))

    # Add the audio
    audio = AudioFileClip(tts_path)
    result = result.with_audio(audio)

    # Get GPU-optimized codec settings
    codec_settings = get_video_codec_settings(use_gpu)

    # Debug: Print actual codec settings being used
    print(colored(f"[debug] Using codec: {codec_settings.get('codec', 'unknown')}", "cyan"))
    print(colored(f"[debug] FFmpeg params: {codec_settings.get('ffmpeg_params', 'none')}", "cyan"))

    from typing import Any
    result_any: Any = result

    # Determine unified output directory (defaults to root output folder)
    unified_output_dir_env = os.getenv("VIDEOHELPER_OUTPUT_DIR")
    if unified_output_dir_env:
        output_dir_path = Path(unified_output_dir_env)
    else:
        # Default to the root output directory of the project
        # Go up from vendors/moneyprinter to backend, then to root, then to output
        output_dir_path = (Path(__file__).resolve().parent / ".." / ".." / ".." / "output").resolve()

    # Ensure directory exists
    output_dir_path.mkdir(parents=True, exist_ok=True)

    # Create a unique filename to avoid collisions
    output_filename = f"moneyprinter_{uuid.uuid4()}.mp4"
    final_output_path = output_dir_path / output_filename

    # Remove 'logger' from codec_settings to avoid parameter conflict
    write_settings = {k: v for k, v in codec_settings.items() if k != 'logger'}

    # Handle enhanced subtitles with ASS subtitle burning
    if is_enhanced and subtitles_path:
        print(colored(f"[debug] Burning enhanced subtitles into video using FFmpeg", "blue"))

        # First write the video without subtitles
        temp_video_path = final_output_path.with_suffix('.temp.mp4')
        result_any.write_videofile(
            str(temp_video_path),
            threads=threads or 2,
            logger=None,
            **write_settings,
        )

        # Burn enhanced subtitles using FFmpeg
        try:
            from .enhanced_subtitles import convert_json_to_ass_and_burn
            success = convert_json_to_ass_and_burn(
                json_subtitle_path=subtitles_path,
                video_path=str(temp_video_path),
                output_path=str(final_output_path)
            )

            if success:
                print(colored(f"[success] Enhanced subtitles burned into video successfully", "green"))
                # Clean up temporary video
                try:
                    os.remove(temp_video_path)
                except:
                    pass
            else:
                print(colored(f"[warn] Enhanced subtitle processing failed, using video without subtitles", "yellow"))
                # Move temp video to final location
                import shutil
                shutil.move(str(temp_video_path), str(final_output_path))

        except Exception as e:
            print(colored(f"[error] Enhanced subtitle processing failed: {e}", "red"))
            # Move temp video to final location
            import shutil
            shutil.move(str(temp_video_path), str(final_output_path))
    else:
        # Write the final video normally (traditional subtitles or no subtitles)
        result_any.write_videofile(
            str(final_output_path),
            threads=threads or 2,
            logger=None,  # Explicitly set logger to avoid conflicts
            **write_settings,
        )

    # Return absolute path if unified dir is set; otherwise return relative to vendors root as before
    return str(final_output_path)
