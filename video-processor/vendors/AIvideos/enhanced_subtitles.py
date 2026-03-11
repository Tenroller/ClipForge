"""
Enhanced subtitle system with TikTok-style word highlighting.

This implementation uses whisper-timestamped for accurate word-level timestamps
and creates ASS subtitle files for smooth word-by-word highlighting.
"""

import os
import uuid
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
import whisper_timestamped as whisper

# Add path to access video-processor utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


@dataclass
class SubtitleConfig:
    """Configuration for ASS subtitle styling."""

    # Font settings - Impact for bold, readable subtitles (matching podcast clips style)
    font_family: str = "Impact"
    font_size: int = 60

    # Colors (ASS format &HAABBGGRR)
    primary_color: str = "&H00FFFFFF"      # White text
    border_color: str = "&H00000000"       # Black border
    highlight_color: str = "&H0000D7FF"    # Yellow highlight box color (BGR)

    # Additional color fields for compatibility
    default_color: str = "&H00FFFFFF"      # Default text color (alias for primary_color)
    stroke_color: str = "&H00000000"       # Stroke/outline color (alias for border_color)
    background_color: str = "&H00000000"   # Background color

    # Styling - bold outline with shadow (matching podcast clips style)
    stroke_width: int = 3                  # Outline width
    background_opacity: float = 0.0        # Background opacity (0.0 to 1.0)
    padding_x: int = 20                    # Horizontal padding
    padding_y: int = 16                    # Vertical padding

    # Position - safer positioning to prevent cropping
    position: str = "center,bottom"

    # Shadow settings
    shadow_layers_count: int = 0           # Number of shadow layers
    shadow_layer_1_color: str = "&H00000000"  # Shadow layer 1 color
    shadow_layer_2_color: str = "&H00000000"  # Shadow layer 2 color
    shadow_layer_3_color: str = "&H00000000"  # Shadow layer 3 color
    shadow_layer_4_color: str = "&H00000000"  # Shadow layer 4 color

    # Whisper model settings
    whisper_model: str = "base"  # tiny, base, small, medium, large


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

    Delegates to the centralized SubtitleGenerator in utils/subtitle_generator.py.

    Args:
        word_level_data: The transcription result from whisper-timestamped.
        ass_path: The path to save the output .ass file.
        config: Subtitle configuration
    """
    print("Creating .ass subtitle file with karaoke effect...")

    try:
        from utils.subtitle_generator import (
            SubtitleGenerator as ASSGenerator,
            whisper_data_to_segments,
        )

        segments = whisper_data_to_segments(word_level_data)
        if not segments:
            print("Warning: No segments found in word-level data")
            return False

        generator = ASSGenerator.from_config(config)
        generator.generate(segments, ass_path)

        print(f"Successfully created .ass file at: {ass_path}")
        return True

    except Exception as e:
        print(f"Error creating .ass file: {e}")
        return False


def burn_subtitles_to_video(video_path: str, ass_path: str, output_path: str):
    """
    Burns the .ass subtitles into the video file using FFmpeg.

    Delegates to the centralized burn_subtitles in utils/video_ffmpeg.py.

    Args:
        video_path: The path to the original input video.
        ass_path: The path to the generated .ass subtitle file.
        output_path: The path for the final output video.
    """
    print("Burning subtitles into video... This may take some time.")
    try:
        from utils.video_ffmpeg import burn_subtitles
        success = burn_subtitles(video_path, ass_path, output_path)
        if success:
            print(f"Successfully burned subtitles into video at: {output_path}")
        return success
    except Exception as e:
        print(f"An error occurred during video composition: {e}")
        return False


# Color utilities are now centralized in backend/utils/colors.py


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
    font_family: str = "Impact",
    font_size: int = 60,
    primary_color: str = "&H00FFFFFF",
    highlight_color: str = "&H0000D7FF",
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
        font_family=config.get('font_family', 'Impact'),
        font_size=config.get('font_size', 28),
        primary_color=primary_color,
        default_color=primary_color,  # Set default_color to match primary_color
        border_color=config.get('border_color', config.get('stroke_color', '&H00000000')),
        stroke_color=config.get('stroke_color', config.get('border_color', '&H00000000')),
        highlight_color=config.get('highlight_color', '&H0000D7FF'),
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
