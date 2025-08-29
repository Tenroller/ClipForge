"""
Enhanced subtitle system with TikTok-style word highlighting.

This implementation uses whisper-timestamped for accurate word-level timestamps
and creates ASS subtitle files for smooth word-by-word highlighting.
"""

import os
import re
import uuid
import json
import argparse
import ffmpeg
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
import pysubs2
import whisper_timestamped as whisper
from moviepy import VideoFileClip


@dataclass
class SubtitleConfig:
    """Configuration for ASS subtitle styling."""

    # Font settings
    font_family: str = "Arial"
    font_size: int = 28

    # Colors (ASS format &HAABBGGRR)
    primary_color: str = "&H00FFFFFF"      # White text
    border_color: str = "&H00000000"       # Black border
    highlight_color: str = "&H0000FFFF"    # Yellow highlight
    
    # Additional color fields for compatibility
    default_color: str = "&H00FFFFFF"      # Default text color (alias for primary_color)
    stroke_color: str = "&H00000000"       # Stroke/outline color (alias for border_color)
    background_color: str = "&H00000000"   # Background color

    # Styling
    stroke_width: int = 2                  # Stroke/outline width
    background_opacity: float = 0.0        # Background opacity (0.0 to 1.0)
    padding_x: int = 16                    # Horizontal padding
    padding_y: int = 12                    # Vertical padding

    # Position
    position: str = "center,bottom"

    # Shadow settings
    shadow_layers_count: int = 0           # Number of shadow layers
    shadow_layer_1_color: str = "&H00000000"  # Shadow layer 1 color
    shadow_layer_2_color: str = "&H00000000"  # Shadow layer 2 color
    shadow_layer_3_color: str = "&H00000000"  # Shadow layer 3 color
    shadow_layer_4_color: str = "&H00000000"  # Shadow layer 4 color

    # Whisper model settings
    whisper_model: str = "base"  # tiny, base, small, medium, large


def extract_audio(video_path: str) -> str | None:
    """
    Extracts audio from a video file and saves it as a temporary WAV file.

    Args:
        video_path: The path to the input video file.

    Returns:
        The path to the extracted audio file, or None if an error occurred.
    """
    print("Extracting audio from video...")
    try:
        # Create a temporary path for the audio file
        temp_audio_path = "temp_audio.wav"

        # Load the video clip using moviepy
        video_clip = VideoFileClip(video_path)

        # Write the audio from the video clip to the temporary file
        video_clip.audio.write_audiofile(temp_audio_path, codec='pcm_s16le') # type: ignore
        video_clip.close()

        print(f"Successfully extracted audio to {temp_audio_path}")
        return temp_audio_path
    except Exception as e:
        print(f"Error during audio extraction: {e}")
        return None


def transcribe_audio_with_word_timestamps(audio_path: str, model_size: str) -> dict:
    """
    Transcribes an audio file using whisper-timestamped to get word-level timestamps.

    Args:
        audio_path: The path to the audio file.
        model_size: The size of the Whisper model to use (e.g., "tiny", "base", "small").

    Returns:
        A dictionary containing the transcription result with word-level timestamps.
    """
    print(f"Loading Whisper model '{model_size}' for transcription...")
    try:
        # Load the audio file
        audio = whisper.load_audio(audio_path)
        print(f"Audio loaded, shape: {audio.shape if hasattr(audio, 'shape') else 'unknown'}")

        # Load the specified Whisper model
        model = whisper.load_model(model_size, device="cpu")
        print(f"Model '{model_size}' loaded successfully")

        # Transcribe the audio to get segments and word-level timestamps
        result = whisper.transcribe(model, audio, language="en", beam_size=5, best_of=5, temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0))

        print("Transcription complete.")
        print(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        if isinstance(result, dict):
            segments = result.get('segments', [])
            print(f"Number of segments: {len(segments)}")
            if segments:
                first_segment = segments[0]
                print(f"First segment keys: {list(first_segment.keys()) if isinstance(first_segment, dict) else 'Not a dict'}")
                if isinstance(first_segment, dict) and 'words' in first_segment:
                    print(f"Number of words in first segment: {len(first_segment['words'])}")
        
        return result
    except Exception as e:
        print(f"Error during transcription: {e}")
        import traceback
        traceback.print_exc()
        return {}


def create_ass_file(word_level_data: dict, ass_path: str, config: SubtitleConfig):
    """
    Generates an Advanced SubStation Alpha (.ass) subtitle file with a karaoke effect.

    Args:
        word_level_data: The transcription result from whisper-timestamped.
        ass_path: The path to save the output .ass file.
        config: Subtitle configuration
    """
    print("Creating .ass subtitle file with karaoke effect...")

    try:
        subs = pysubs2.SSAFile()

        # Convert hex color to RGB
        def hex_to_rgb(hex_color: str) -> tuple:
            """Convert hex color format #RRGGBB to RGB tuple."""
            if not hex_color.startswith('#'):
                return (255, 255, 255)  # Default to white
            try:
                # Extract RR, GG, BB from #RRGGBB
                color_part = hex_color[1:]  # Remove #
                if len(color_part) >= 6:
                    rr = int(color_part[0:2], 16)  # First 2 chars
                    gg = int(color_part[2:4], 16)  # Next 2 chars
                    bb = int(color_part[4:6], 16)  # Last 2 chars
                    return (rr, gg, bb)
            except (ValueError, IndexError):
                pass
            return (255, 255, 255)  # Default to white

        # Text wrapping function
        def wrap_text(text: str, max_chars_per_line: int = 25) -> List[str]:
            """Wrap text into multiple lines based on character count."""
            words = text.split()
            lines = []
            current_line = ""
            
            for word in words:
                # Check if adding this word would exceed the limit
                if len(current_line) + len(word) + 1 <= max_chars_per_line:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            # Add the last line if it has content
            if current_line:
                lines.append(current_line)
            
            return lines

        # Dynamic font sizing based on text length
        def get_optimal_font_size(base_font_size: int, text_length: int) -> int:
            """Reduce font size for very long text to keep it readable."""
            if text_length > 100:
                return max(base_font_size - 8, 20)  # Reduce by 8, minimum 20
            elif text_length > 80:
                return max(base_font_size - 6, 22)  # Reduce by 6, minimum 22
            elif text_length > 60:
                return max(base_font_size - 4, 24)  # Reduce by 4, minimum 24
            elif text_length > 40:
                return max(base_font_size - 2, 26)  # Reduce by 2, minimum 26
            else:
                return base_font_size

        # Get colors from config, converting hex to RGB
        primary_rgb = hex_to_rgb(config.primary_color if config.primary_color.startswith('#') else config.primary_color)
        highlight_rgb = hex_to_rgb(config.highlight_color if config.highlight_color.startswith('#') else config.highlight_color)
        border_rgb = hex_to_rgb(config.stroke_color if config.stroke_color.startswith('#') else config.stroke_color)
        background_rgb = hex_to_rgb(config.background_color if config.background_color.startswith('#') else config.background_color)

        # Parse position from config
        position = config.position.lower() if config.position else "center,bottom"
        horizontal_pos, vertical_pos = "center", "bottom"
        if "," in position:
            parts = position.split(",")
            horizontal_pos = parts[0].strip() if len(parts) > 0 else "center"
            vertical_pos = parts[1].strip() if len(parts) > 1 else "bottom"

        # Convert position to pysubs2 alignment
        alignment_map = {
            ("left", "top"): pysubs2.Alignment.TOP_LEFT,
            ("center", "top"): pysubs2.Alignment.TOP_CENTER,
            ("right", "top"): pysubs2.Alignment.TOP_RIGHT,
            ("left", "center"): pysubs2.Alignment.MIDDLE_LEFT,
            ("center", "center"): pysubs2.Alignment.MIDDLE_CENTER,
            ("right", "center"): pysubs2.Alignment.MIDDLE_RIGHT,
            ("left", "bottom"): pysubs2.Alignment.BOTTOM_LEFT,
            ("center", "bottom"): pysubs2.Alignment.BOTTOM_CENTER,
            ("right", "bottom"): pysubs2.Alignment.BOTTOM_RIGHT,
        }
        alignment = alignment_map.get((horizontal_pos, vertical_pos), pysubs2.Alignment.BOTTOM_CENTER)

        # Calculate margin based on position
        marginv = 30  # Default margin
        if vertical_pos == "top":
            marginv = 30 + config.padding_y
        elif vertical_pos == "center":
            marginv = 0  # Center positioning
        elif vertical_pos == "bottom":
            marginv = 30 + config.padding_y

        # Define the main style for the subtitles
        default_style = pysubs2.SSAStyle(
            fontname=config.font_family,
            fontsize=config.font_size,
            primarycolor=pysubs2.Color(r=primary_rgb[0], g=primary_rgb[1], b=primary_rgb[2], a=0),
            secondarycolor=pysubs2.Color(r=highlight_rgb[0], g=highlight_rgb[1], b=highlight_rgb[2], a=0),
            outlinecolor=pysubs2.Color(r=border_rgb[0], g=border_rgb[1], b=border_rgb[2], a=0),
            backcolor=pysubs2.Color(r=background_rgb[0], g=background_rgb[1], b=background_rgb[2], a=int(255 * config.background_opacity)),
            borderstyle=1,
            outline=config.stroke_width,
            shadow=1 if config.shadow_layers_count > 0 else 0,
            alignment=alignment,
            marginv=marginv
        )
        subs.styles["Default"] = default_style

        # Iterate through each segment (line) of the transcription
        segments = word_level_data.get("segments", [])
        print(f"Processing {len(segments)} segments for ASS file creation")
        
        for segment_idx, segment in enumerate(segments):
            words = segment.get("words", [])
            if not words:
                print(f"Warning: Segment {segment_idx} has no words, skipping")
                continue
                
            print(f"Processing segment {segment_idx}: {len(words)} words, duration: {segment.get('end', 0) - segment.get('start', 0):.2f}s")

            # Create individual subtitle events for each word timing
            for i, word in enumerate(segment["words"]):
                word_start_ms = int(word["start"] * 1000)
                word_end_ms = int(word["end"] * 1000)
                
                print(f"    Word {i}: '{word.get('text', '')}' at {word_start_ms}ms - {word_end_ms}ms")

                # Build sentence with only current word highlighted
                sentence_text = ""
                for j, word_info in enumerate(segment["words"]):
                    if j == i:
                        # Current word gets highlighted (highlight_color)
                        # Convert highlight color to ASS format
                        highlight_ass = f"&H00{highlight_rgb[2]:02X}{highlight_rgb[1]:02X}{highlight_rgb[0]:02X}"
                        sentence_text += f"{{\\c{highlight_ass}}}{word_info['text']}{{\\c&H00FFFFFF}}"
                    else:
                        # Other words use default color (primary_color)
                        sentence_text += word_info['text']

                    # Add space if not the last word
                    if j < len(segment["words"]) - 1:
                        sentence_text += " "

                # Get the original text length for font sizing (without ASS formatting)
                original_text = " ".join([w["text"] for w in segment["words"]])
                text_length = len(original_text)
                
                # Calculate optimal font size for this text
                optimal_font_size = get_optimal_font_size(config.font_size, text_length)
                
                # Wrap the sentence text into multiple lines with aggressive wrapping
                max_chars = 20 if text_length > 60 else 25  # More aggressive for long text
                wrapped_lines = wrap_text(sentence_text, max_chars_per_line=max_chars)
                
                # Join lines with \N (ASS line break)
                wrapped_text = "\\N".join(wrapped_lines)

                # Create subtitle event for this word's duration with custom font size
                event = pysubs2.SSAEvent(
                    start=word_start_ms,
                    end=word_end_ms,
                    text=wrapped_text,
                    style="Default"
                )
                
                # Create a custom style for this event with the optimal font size
                if optimal_font_size != config.font_size:
                    style_name = f"Style_{optimal_font_size}"
                    if style_name not in subs.styles:
                        custom_style = pysubs2.SSAStyle(
                            fontname=config.font_family,
                            fontsize=optimal_font_size,
                            primarycolor=pysubs2.Color(r=primary_rgb[0], g=primary_rgb[1], b=primary_rgb[2], a=0),
                            secondarycolor=pysubs2.Color(r=highlight_rgb[0], g=highlight_rgb[1], b=highlight_rgb[2], a=0),
                            outlinecolor=pysubs2.Color(r=border_rgb[0], g=border_rgb[1], b=border_rgb[2], a=0),
                            backcolor=pysubs2.Color(r=background_rgb[0], g=background_rgb[1], b=background_rgb[2], a=int(255 * config.background_opacity)),
                            borderstyle=1,
                            outline=config.stroke_width,
                            shadow=1 if config.shadow_layers_count > 0 else 0,
                            alignment=alignment,
                            marginv=marginv
                        )
                        subs.styles[style_name] = custom_style
                    
                    # Use the custom style for this event
                    event.style = style_name
                
                subs.append(event)

        # Save the complete .ass file
        subs.save(ass_path, encoding="utf-8")
        print(f"Successfully created .ass file at: {ass_path}")
        print(f"Total subtitle events created: {len(subs.events)}")
        return True

    except Exception as e:
        print(f"Error creating .ass file: {e}")
        return False


def burn_subtitles_to_video(video_path: str, ass_path: str, output_path: str):
    """
    Burns the .ass subtitles into the video file using FFmpeg.

    Args:
        video_path: The path to the original input video.
        ass_path: The path to the generated .ass subtitle file.
        output_path: The path for the final output video.
    """
    print("Burning subtitles into video... This may take some time.")
    try:
        # Define the input video stream
        input_video = ffmpeg.input(video_path)
        # The audio is taken from the original video file directly
        input_audio = input_video.audio

        # Apply the 'subtitles' video filter
        stream = ffmpeg.filter(input_video, 'subtitles', ass_path)

        # Combine the video stream (with subtitles) and the original audio stream
        stream = ffmpeg.output(stream, input_audio, output_path, vcodec='libx264', acodec='copy', preset='medium', crf=23)

        # Run the FFmpeg command, overwriting the output file if it exists
        ffmpeg.run(stream, overwrite_output=True, quiet=False)

        print(f"Successfully burned subtitles into video at: {output_path}")
        return True
    except ffmpeg.Error as e:
        if e.stderr:
            print("FFmpeg Error:", e.stderr.decode())
        else:
            print("FFmpeg Error occurred but no stderr output available")
        return False
    except Exception as e:
        print(f"An error occurred during video composition: {e}")
        return False


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return (255, 255, 255)  # Default to white
    try:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (255, 255, 255)


def process_video_with_enhanced_subtitles(
    video_path: str,
    output_path: str,
    config: Optional[SubtitleConfig] = None
) -> bool:
    """
    Process a video to add enhanced word-highlighting subtitles.

    Args:
        video_path: Path to the input video
        output_path: Path for the output video with subtitles
        config: Subtitle configuration

    Returns:
        True if successful, False otherwise
    """
    if config is None:
        config = SubtitleConfig()

    # Step 1: Extract audio
    audio_path = extract_audio(video_path)
    if not audio_path:
        return False

    try:
        # Step 2: Transcribe with word timestamps
        transcription_data = transcribe_audio_with_word_timestamps(audio_path, config.whisper_model)
        if not transcription_data:
            return False

        # Step 3: Create ASS subtitle file
        ass_path = "temp_subtitles.ass"
        if not create_ass_file(transcription_data, ass_path, config):
            return False

        # Step 4: Burn subtitles into video
        success = burn_subtitles_to_video(video_path, ass_path, output_path)

        # Cleanup
        try:
            os.remove(audio_path)
            if os.path.exists(ass_path):
                os.remove(ass_path)
        except OSError as e:
            print(f"Warning: Could not cleanup temporary files: {e}")

        return success

    except Exception as e:
        print(f"Error processing video with enhanced subtitles: {e}")
        # Cleanup on error
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
        except:
            pass
        return False


def generate_enhanced_subtitles(
    sentences: List[str],
    audio_clips: List[Any],
    config: Optional[SubtitleConfig] = None,
    output_path: Optional[str] = None,
    video_size: Optional[Tuple[int, int]] = None
) -> str:
    """
    Generate enhanced subtitle data using whisper transcription.

    Args:
        sentences: List of sentences to transcribe
        audio_clips: List of audio clips (for timing estimation as fallback)
        config: Subtitle configuration
        output_path: Path to save the enhanced subtitle file
        video_size: Optional video dimensions for positioning/styling

    Returns:
        Path to the enhanced subtitle JSON file
    """
    if config is None:
        config = SubtitleConfig()

    # Create temporary audio file from audio clips
    import tempfile
    from moviepy import concatenate_audioclips

    print(f"Creating audio file from {len(audio_clips)} audio clips")

    try:
        # Combine all audio clips
        if not audio_clips:
            print("Warning: No audio clips provided")
            return ""

        combined_audio = concatenate_audioclips(audio_clips)
        print(f"Combined audio duration: {combined_audio.duration}s")

        # Save to temporary file in project temp directory
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        temp_audio_path = str(temp_dir / f"temp_audio_{uuid.uuid4()}.wav")
        combined_audio.write_audiofile(temp_audio_path, codec='pcm_s16le')

        # Transcribe with word timestamps
        print(f"Starting transcription with model: {config.whisper_model}")
        transcription_data = transcribe_audio_with_word_timestamps(temp_audio_path, config.whisper_model)

        # Create subtitle data structure
        if transcription_data and isinstance(transcription_data, dict):
            segments = transcription_data.get('segments', [])
            if not segments:
                print("Warning: Transcription completed but no segments found")
                print(f"Transcription data keys: {list(transcription_data.keys())}")
                transcription_data = None
            else:
                print(f"Transcription successful with {len(segments)} segments")
                print(f"First segment keys: {list(segments[0].keys()) if segments else 'No segments'}")
        else:
            print("Warning: Transcription failed or returned invalid data")
            print(f"Transcription data type: {type(transcription_data)}")
            print(f"Transcription data: {transcription_data}")
            transcription_data = None

        if transcription_data:
            # Transform Whisper transcription data to expected format
            processed_sentences: List[Dict[str, Any]] = []
            word_timings = []

            for segment in transcription_data.get('segments', []):
                # Create sentence entry
                sentence_dict: Dict[str, Any] = {
                    'text': segment.get('text', '').strip(),
                    'start_time': segment.get('start', 0),
                    'end_time': segment.get('end', 0),
                    'confidence': segment.get('confidence', 0)
                }
                processed_sentences.append(sentence_dict)

                # Create word timing entries
                for word in segment.get('words', []):
                    word_timing = {
                        'word': word.get('text', ''),
                        'start_time': word.get('start', 0),
                        'end_time': word.get('end', 0),
                        'confidence': word.get('confidence', 0),
                        'sentence_index': len(processed_sentences) - 1,
                        'sentence': sentence_dict['text']
                    }
                    word_timings.append(word_timing)

            subtitle_data = {
                'version': '1.0',
                'type': 'enhanced_ass',
                'config': asdict(config),
                'sentences': processed_sentences,
                'word_timings': word_timings,
                'transcription': transcription_data,  # Keep original for compatibility
                'metadata': {
                    'total_segments': len(transcription_data.get('segments', [])),
                    'total_duration': transcription_data.get('duration', 0),
                    'total_sentences': len(processed_sentences),
                    'total_words': len(word_timings)
                }
            }
        else:
            # Fallback to basic structure using provided sentences
            print("Creating fallback subtitle structure from provided sentences")

            # Estimate timing based on audio clips
            fallback_sentences: List[Dict[str, Any]] = []
            fallback_word_timings = []
            current_time = 0.0

            for i, (sentence, audio_clip) in enumerate(zip(sentences, audio_clips)):
                # Get duration from audio clip
                duration = audio_clip.duration if hasattr(audio_clip, 'duration') else 2.0

                sentence_data = {
                    'text': sentence,
                    'start_time': current_time,
                    'end_time': current_time + duration,
                    'confidence': 1.0
                }
                fallback_sentences.append(sentence_data)

                # Create word-level timing (simple word-by-word split)
                words = sentence.split()
                word_duration = duration / max(len(words), 1)

                for j, word in enumerate(words):
                    word_start = current_time + (j * word_duration)
                    word_end = current_time + ((j + 1) * word_duration)

                    word_timing = {
                        'word': word,
                        'start_time': word_start,
                        'end_time': word_end,
                        'confidence': 1.0,
                        'sentence_index': i,
                        'sentence': sentence
                    }
                    fallback_word_timings.append(word_timing)

                current_time += duration

            subtitle_data = {
                'version': '1.0',
                'type': 'enhanced_ass',
                'config': asdict(config),
                'sentences': fallback_sentences,
                'word_timings': fallback_word_timings,
                'transcription': {},
                'metadata': {'total_segments': len(fallback_sentences), 'total_duration': current_time, 'total_sentences': len(fallback_sentences), 'total_words': len(fallback_word_timings)}
            }

        # Save to file
        if output_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            subtitles_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), 'subtitles')
            output_path = os.path.join(subtitles_dir, f"{uuid.uuid4()}_enhanced.json")

        # Ensure the output path is absolute
        output_path = os.path.abspath(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(subtitle_data, f, indent=2, ensure_ascii=False)

        print(f"Enhanced subtitle data saved to: {output_path}")

        # Cleanup temporary audio file
        try:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
                print(f"Cleaned up temporary audio file: {temp_audio_path}")
        except OSError as e:
            print(f"Warning: Could not cleanup temporary audio file: {e}")

        return output_path

    except Exception as e:
        print(f"Error generating enhanced subtitles: {e}")
        # Cleanup temporary audio file on error
        try:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
                print(f"Cleaned up temporary audio file after error: {temp_audio_path}")
        except OSError as cleanup_e:
            print(f"Warning: Could not cleanup temporary audio file after error: {cleanup_e}")

        # Return empty structure
        if output_path:
            subtitle_data = {
                'version': '1.0',
                'type': 'enhanced_ass',
                'config': asdict(config) if config else {},
                'sentences': [],
                'word_timings': [],
                'transcription': {},
                'metadata': {'total_segments': 0, 'total_duration': 0, 'total_sentences': 0, 'total_words': 0}
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
            return output_path
        return ""


def convert_json_to_ass_and_burn(
    json_subtitle_path: str,
    video_path: str,
    output_path: str,
    config: Optional[SubtitleConfig] = None
) -> bool:
    """
    Convert JSON subtitle data to ASS format and burn it into the video.
    
    Args:
        json_subtitle_path: Path to the JSON subtitle file
        video_path: Path to the input video
        output_path: Path for the output video with burned subtitles
        config: Subtitle configuration (optional, will be loaded from JSON if not provided)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load JSON subtitle data
        with open(json_subtitle_path, 'r', encoding='utf-8') as f:
            subtitle_data = json.load(f)
            
        print(f"Loaded subtitle file: {json_subtitle_path}")
        print(f"Absolute path: {os.path.abspath(json_subtitle_path)}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"File exists: {os.path.exists(json_subtitle_path)}")
        print(f"File size: {os.path.getsize(json_subtitle_path) if os.path.exists(json_subtitle_path) else 'N/A'} bytes")
        print(f"File contains keys: {list(subtitle_data.keys())}")
        print(f"Type: {subtitle_data.get('type', 'unknown')}")
        print(f"Version: {subtitle_data.get('version', 'unknown')}")
        
        # Load config from JSON if not provided
        if config is None and 'config' in subtitle_data:
            config_dict = subtitle_data['config']
            config = SubtitleConfig(**config_dict)
        elif config is None:
            config = SubtitleConfig()
        
        # Create temporary ASS file in project temp directory
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        ass_path = str(temp_dir / f"temp_subtitles_{uuid.uuid4()}.ass")
        
        # Check for required subtitle data
        sentences = subtitle_data.get('sentences', [])
        word_timings = subtitle_data.get('word_timings', [])
        
        print(f"Subtitle data validation: {len(sentences)} sentences, {len(word_timings)} word timings")
        
        if not sentences or not word_timings:
            print("No subtitle data found in JSON subtitle file")
            print(f"Available keys: {list(subtitle_data.keys())}")
            return False
            
        # Convert subtitle data to ASS format - use the sentences and word_timings
        # The create_ass_file function expects word-level data with segments
        transcription_data = {
            'segments': [
                {
                    'start': sentence.get('start_time', 0),
                    'end': sentence.get('end_time', 0),
                    'text': sentence.get('text', ''),
                    'words': [
                        {
                            'start': word.get('start_time', 0),
                            'end': word.get('end_time', 0),
                            'text': word.get('word', '')
                        }
                        for word in word_timings if word.get('sentence_index') == i
                    ]
                }
                for i, sentence in enumerate(sentences)
            ]
        }
        
        print(f"Converted transcription data: {len(transcription_data['segments'])} segments")
        for i, segment in enumerate(transcription_data['segments']):
            print(f"  Segment {i}: {len(segment['words'])} words, duration: {segment['end'] - segment['start']:.2f}s")
        
        # Create ASS file
        if not create_ass_file(transcription_data, ass_path, config):
            print("Failed to create ASS file")
            return False
        
        # Burn subtitles into video
        success = burn_subtitles_to_video(video_path, ass_path, output_path)
        
        # Cleanup temporary ASS file
        try:
            if os.path.exists(ass_path):
                os.remove(ass_path)
        except OSError as e:
            print(f"Warning: Could not cleanup temporary ASS file: {e}")
        
        return success
        
    except Exception as e:
        print(f"Error converting JSON to ASS and burning subtitles: {e}")
        return False


def create_enhanced_subtitle_clip(
    subtitle_path: str,
    video_size: Tuple[int, int]
) -> Optional[Any]:
    """
    Create enhanced subtitle clip from saved data.

    For the new ASS-based approach, this function creates a simple placeholder
    since the actual subtitle burning is done via FFmpeg.
    """
    from moviepy import ColorClip

    # Return a transparent clip - the actual subtitles are burned in via FFmpeg
    return ColorClip(size=video_size, color=(0,0,0,0), duration=0.1).with_opacity(0)


def is_enhanced_subtitle_file(subtitle_path: str) -> bool:
    """Check if a subtitle file is in enhanced format."""
    try:
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('type') in ['enhanced_ass', 'tiktok_enhanced']
    except (json.JSONDecodeError, FileNotFoundError, KeyError):
        return False


def create_tiktok_style_config(
    font_family: str = "Arial",
    font_size: int = 28,
    primary_color: str = "&H00FFFFFF",
    highlight_color: str = "&H0000FFFF",
    position: str = "center,bottom",
    **kwargs
) -> SubtitleConfig:
    """Create a TikTok-style subtitle configuration."""
    return SubtitleConfig(
        font_family=font_family,
        font_size=font_size,
        primary_color=primary_color,
        default_color=primary_color,  # Set default_color to match primary_color
        border_color=kwargs.get('border_color', '&H00000000'),
        stroke_color=kwargs.get('stroke_color', '&H00000000'),
        highlight_color=highlight_color,
        background_color=kwargs.get('background_color', '&H00000000'),
        stroke_width=kwargs.get('stroke_width', 2),
        background_opacity=kwargs.get('background_opacity', 0.0),
        padding_x=kwargs.get('padding_x', 16),
        padding_y=kwargs.get('padding_y', 12),
        position=position,
        shadow_layers_count=kwargs.get('shadow_layers_count', 0),
        shadow_layer_1_color=kwargs.get('shadow_layer_1_color', '&H00000000'),
        shadow_layer_2_color=kwargs.get('shadow_layer_2_color', '&H00000000'),
        shadow_layer_3_color=kwargs.get('shadow_layer_3_color', '&H00000000'),
        shadow_layer_4_color=kwargs.get('shadow_layer_4_color', '&H00000000'),
        whisper_model=kwargs.get('whisper_model', 'base')
    )


def create_subtitle_config_from_legacy(config: Dict[str, Any]) -> SubtitleConfig:
    """Convert legacy subtitle config format to new format."""
    # Handle color mapping: use primary_color if available, otherwise default_color, otherwise white
    primary_color = config.get('primary_color')
    if not primary_color:
        primary_color = config.get('default_color')
    if not primary_color:
        primary_color = '&H00FFFFFF'

    return SubtitleConfig(
        font_family=config.get('font_family', 'Arial'),
        font_size=config.get('font_size', 28),
        primary_color=primary_color,
        default_color=primary_color,  # Set default_color to match primary_color
        border_color=config.get('border_color', config.get('stroke_color', '&H00000000')),
        stroke_color=config.get('stroke_color', config.get('border_color', '&H00000000')),
        highlight_color=config.get('highlight_color', '&H0000FFFF'),
        background_color=config.get('background_color', '&H00000000'),
        stroke_width=config.get('stroke_width', 2),
        background_opacity=config.get('background_opacity', 0.0),
        padding_x=config.get('padding_x', 16),
        padding_y=config.get('padding_y', 12),
        position=config.get('position', 'center,bottom'),
        shadow_layers_count=config.get('shadow_layers_count', 0),
        shadow_layer_1_color=config.get('shadow_layer_1_color', '&H00000000'),
        shadow_layer_2_color=config.get('shadow_layer_2_color', '&H00000000'),
        shadow_layer_3_color=config.get('shadow_layer_3_color', '&H00000000'),
        shadow_layer_4_color=config.get('shadow_layer_4_color', '&H00000000'),
        whisper_model=config.get('whisper_model', 'base')
    )


# End of enhanced_subtitles.py
