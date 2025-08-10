import os
import uuid
import subprocess

import requests
import srt_equalizer
import assemblyai as aai

from typing import List, Dict, Optional, Union, Any, cast
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    TextClip,
    ColorClip,
    concatenate_videoclips,
)
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


def detect_gpu_codec() -> Optional[Dict[str, Union[str, List[str]]]]:
    """
    Detects available GPU encoders and returns optimal codec settings.
    
    Returns:
        Dict with codec settings if GPU encoder is available, None otherwise
    """
    try:
        # Resolve ffmpeg executable path (works even if ffmpeg isn't on PATH)
        ffmpeg_cmd: str = 'ffmpeg'
        if get_ffmpeg_exe:
            try:
                ffmpeg_cmd = get_ffmpeg_exe()  # type: ignore[assignment]
            except Exception:
                ffmpeg_cmd = 'ffmpeg'

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


def save_video(video_url: str, directory: str = "../temp") -> str:
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
    with open(video_path, "wb") as f:
        f.write(requests.get(video_url).content)

    return video_path


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

    def equalize_subtitles(srt_path: str, max_chars: int = 50) -> None:
        # Equalize subtitles - increased max_chars from 10 to 50 for better readability
        srt_equalizer.equalize_srt_file(srt_path, srt_path, max_chars)

    # Save subtitles
    subtitles_path = f"../subtitles/{uuid.uuid4()}.srt"

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


def combine_videos(video_paths: List[str], max_duration: int, max_clip_duration: int, threads: int, use_gpu: bool = True) -> str:
    """
    Combines a list of videos into one video and returns the path to the combined video.

    Args:
        video_paths (List): A list of paths to the videos to combine.
        max_duration (int): The maximum duration of the combined video.
        max_clip_duration (int): The maximum duration of each clip.
        threads (int): The number of threads to use for the video processing.

    Returns:
        str: The path to the combined video.
    """
    video_id = uuid.uuid4()
    combined_video_path = f"../temp/{video_id}.mp4"
    
    # Required duration of each clip
    req_dur = max_duration / len(video_paths)

    print(colored("[+] Combining videos...", "blue"))
    print(colored(f"[+] Each clip will be maximum {req_dur} seconds long.", "blue"))

    clips = []
    tot_dur = 0
    # Add downloaded clips over and over until the duration of the audio (max_duration) has been reached
    while tot_dur < max_duration:
        for video_path in video_paths:
            clip = VideoFileClip(video_path)
            clip = clip.without_audio()
            # Check if clip is longer than the remaining audio
            if (max_duration - tot_dur) < clip.duration:
                clip = clip.subclipped(0, (max_duration - tot_dur))
            # Only shorten clips if the calculated clip length (req_dur) is shorter than the actual clip to prevent still image
            elif req_dur < clip.duration:
                clip = clip.subclipped(0, req_dur)
            clip = clip.with_fps(30)

            # Not all videos are same size,
            # so we need to resize them
            if round((clip.w/clip.h), 4) < 0.5625:
                clip = clip.with_effects([vfx.Crop(width=clip.w, height=round(clip.w/0.5625),  # type: ignore[attr-defined]
                            x_center=clip.w / 2, 
                            y_center=clip.h / 2)])
            else:
                clip = clip.with_effects([vfx.Crop(width=round(0.5625*clip.h), height=clip.h,  # type: ignore[attr-defined]
                            x_center=clip.w / 2, 
                            y_center=clip.h / 2)])
            clip = clip.with_effects([vfx.Resize(width=1080, height=1920)])

            if clip.duration > max_clip_duration:
                clip = clip.subclipped(0, max_clip_duration)

            clips.append(clip)
            tot_dur += clip.duration

    final_clip = concatenate_videoclips(clips)
    final_clip = final_clip.with_fps(30)
    
    # Get GPU-optimized codec settings
    codec_settings = get_video_codec_settings(use_gpu)
    
    final_clip_typed: CompositeVideoClip = cast(CompositeVideoClip, final_clip)
    final_clip_typed.write_videofile(
        combined_video_path, 
        threads=threads,
        **codec_settings
    )

    return combined_video_path


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
    
    # Generator that returns a CompositeVideoClip (background box + text)
    def generator(txt: str):
        # Calculate font size relative to video height (targeting ~40-50px for 1920px height)
        try:
            video_height = int(getattr(base_clip, 'h', 1920) or 1920)
            # Scale font size based on video height - aim for 2.5% of video height
            font_size = max(24, int(video_height * 0.025))
        except Exception:
            font_size = 48  # Fallback for ~1920px height
            
        # Create TextClip with reliable font choices and better error handling
        font_choices = ["Arial-Bold", "arial.ttf", "Arial", None]  # None uses MoviePy default
        text_clip = None
        
        for font_choice in font_choices:
            try:
                # Calculate video width for text wrapping
                video_width = int(getattr(base_clip, 'w', 1080) or 1080)
                max_text_width = int(video_width * 0.9)  # Use 90% of video width for text
                
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
                max_text_width = int(video_width * 0.9)
                
                text_clip = TextClip(
                    text=txt,
                    font_size=font_size,
                    color=text_color,
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

    # Validate subtitle file before creating SubtitlesClip
    print(colored(f"[debug] Creating SubtitlesClip from: {subtitles_path}", "blue"))
    try:
        from pathlib import Path as _Path
        srt_path = _Path(subtitles_path)
        if not srt_path.exists():
            raise FileNotFoundError(f"Subtitle file does not exist: {subtitles_path}")
        
        # Read and validate SRT content
        with srt_path.open("r", encoding="utf-8") as f:
            srt_content = f.read().strip()
            if not srt_content:
                raise ValueError("Subtitle file is empty")
            print(colored(f"[debug] SRT file size: {len(srt_content)} chars, first 200 chars: {srt_content[:200]}", "cyan"))
    except Exception as e:
        print(colored(f"[error] Subtitle file validation failed: {e}", "red"))
        raise e

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
            raise e2

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
                current_clip = subtitles.get_frame(t) if hasattr(subtitles, 'get_frame') else None
                if current_clip is not None and hasattr(current_clip, 'shape'):
                    sh, sw = current_clip.shape[:2]  # numpy array shape is (height, width, channels)
                else:
                    # Fallback: try direct attribute access
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
                    y = int(0.85 * h) - half_sh
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

    positioned_subs = subtitles.with_position(_safe_area_pos_fn)
    result: CompositeVideoClip = CompositeVideoClip([
        base_clip,
        positioned_subs,
    ])

    # Add the audio
    audio = AudioFileClip(tts_path)
    result = result.with_audio(audio)

    # Get GPU-optimized codec settings
    codec_settings = get_video_codec_settings(use_gpu)
    
    from typing import Any
    result_any: Any = result

    # Determine unified output directory (defaults to ../temp for backward compatibility)
    unified_output_dir_env = os.getenv("VIDEOHELPER_OUTPUT_DIR")
    if unified_output_dir_env:
        output_dir_path = Path(unified_output_dir_env)
    else:
        output_dir_path = (Path(__file__).resolve().parent / ".." / "temp").resolve()

    # Ensure directory exists
    output_dir_path.mkdir(parents=True, exist_ok=True)

    # Create a unique filename to avoid collisions
    output_filename = f"moneyprinter_{uuid.uuid4()}.mp4"
    final_output_path = output_dir_path / output_filename

    # Write the final video
    result_any.write_videofile(
        str(final_output_path),
        threads=threads or 2,
        **codec_settings,
    )

    # Return absolute path if unified dir is set; otherwise return relative to vendors root as before
    return str(final_output_path)
