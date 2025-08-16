"""
Enhanced word-level timing using OpenAI Whisper for more accurate subtitles.

This module provides precise word-level timing by using Whisper's word-level 
timestamps, which are much more accurate than the estimation method.
"""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("OpenAI Whisper not available. Install with: pip install openai-whisper")


def extract_word_timings_with_whisper(
    audio_path: str,
    model_size: str = "base"
) -> List[Dict[str, Any]]:
    """
    Extract word-level timings using OpenAI Whisper.
    
    Args:
        audio_path: Path to the audio file
        model_size: Whisper model size ("tiny", "base", "small", "medium", "large")
        
    Returns:
        List of word timing dictionaries with precise timestamps
    """
    if not WHISPER_AVAILABLE:
        raise ImportError("OpenAI Whisper is required for precise word timing. Install with: pip install openai-whisper")
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    # Import whisper here to avoid the lint error
    import whisper
    
    # Load Whisper model
    print(f"Loading Whisper model: {model_size}")
    model = whisper.load_model(model_size)
    
    # Transcribe with word-level timestamps
    print(f"Transcribing audio file: {audio_path}")
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        task="transcribe"
    )
    
    # Extract word timings
    word_timings = []
    sentence_index = 0
    word_index = 0
    
    # Process segments with proper type handling
    for segment in result.get("segments", []):
        segment_text = str(segment.get("text", "")).strip()  # type: ignore
        
        if "words" in segment and segment["words"]:  # type: ignore
            segment_words = segment["words"]  # type: ignore
            
            for word_data in segment_words:
                word_timings.append({
                    'word': str(word_data.get("word", "")).strip(),  # type: ignore
                    'start_time': float(word_data.get("start", 0.0)),  # type: ignore
                    'end_time': float(word_data.get("end", 0.0)),  # type: ignore
                    'sentence_index': sentence_index,
                    'word_index': word_index,
                    'sentence': segment_text,
                    'confidence': float(word_data.get("probability", 1.0))  # type: ignore
                })
                word_index += 1
            
            sentence_index += 1
    
    print(f"Extracted {len(word_timings)} words with precise timing")
    return word_timings


def create_enhanced_subtitles_with_whisper(
    audio_path: str,
    output_path: Optional[str] = None,
    video_size: Tuple[int, int] = (1080, 1920),
    whisper_model: str = "base",
    config_overrides: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create enhanced subtitles using Whisper for precise word timing.
    
    Args:
        audio_path: Path to the audio file
        output_path: Optional output path for the JSON file
        video_size: Video dimensions (width, height)
        whisper_model: Whisper model size to use
        config_overrides: Optional configuration overrides
        
    Returns:
        Path to the generated enhanced subtitle JSON file
    """
    if not WHISPER_AVAILABLE:
        raise ImportError("OpenAI Whisper is required. Install with: pip install openai-whisper")
    
    # Extract word timings using Whisper
    word_timings = extract_word_timings_with_whisper(audio_path, whisper_model)
    
    if not word_timings:
        raise ValueError("No word timings extracted from audio")
    
    # Group words into sentences
    sentences = []
    current_sentence_idx = -1
    
    for word_data in word_timings:
        if word_data['sentence_index'] != current_sentence_idx:
            current_sentence_idx = word_data['sentence_index']
            sentences.append({
                'text': word_data['sentence'],
                'index': current_sentence_idx,
                'start_time': word_data['start_time'],
                'end_time': word_data['end_time']
            })
        else:
            # Extend the sentence end time
            sentences[-1]['end_time'] = max(sentences[-1]['end_time'], word_data['end_time'])
    
    # Default configuration optimized for 3-word windows
    default_config = {
        'font_family': 'Arial-Bold',
        'font_size': 48,
        'font_bold': True,
        'default_color': '#FFFFFF',      # White for unspoken words
        'highlight_color': '#FF0000',    # Red for currently spoken word
        'stroke_color': '#000000',       # Black outline
        'background_color': '#000000',   # Black background
        'stroke_width': 3,
        'background_opacity': 0.6,
        'padding_x': 16,
        'padding_y': 12,
        'highlight_transition': 0.1,
        'word_appear_delay': 0.05,
        'position': 'center,bottom',
        'max_width_percent': 0.85,
        'line_spacing': 1.2,
        'shadow_enabled': True,
        'shadow_color': '#000000',
        'shadow_offset_x': 2,
        'shadow_offset_y': 2,
        'glow_enabled': False,
        'glow_color': '#FFFFFF',
        'glow_intensity': 0.3
    }
    
    # Apply config overrides
    if config_overrides:
        default_config.update(config_overrides)
    
    # Create subtitle data structure
    subtitle_data = {
        'version': '2.0',  # Updated version for Whisper-enhanced
        'type': 'tiktok_enhanced',
        'config': default_config,
        'video_size': video_size,
        'sentences': sentences,
        'word_timings': word_timings,
        'metadata': {
            'total_words': len(word_timings),
            'total_sentences': len(sentences),
            'total_duration': max(wt['end_time'] for wt in word_timings) if word_timings else 0,
            'whisper_model': whisper_model,
            'generation_method': 'whisper_enhanced'
        }
    }
    
    # Generate output path if not provided
    if output_path is None:
        import uuid
        audio_name = Path(audio_path).stem
        output_path = f"subtitles/{audio_name}_{uuid.uuid4().hex[:8]}_whisper_enhanced.json"
    
    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
    
    print(f"Enhanced subtitles with Whisper timing saved to: {output_path}")
    return output_path


def improve_existing_subtitles_with_whisper(
    existing_subtitle_path: str,
    audio_path: str,
    whisper_model: str = "base"
) -> str:
    """
    Improve existing enhanced subtitles by replacing word timings with Whisper-generated ones.
    
    Args:
        existing_subtitle_path: Path to existing enhanced subtitle JSON
        audio_path: Path to the audio file
        whisper_model: Whisper model to use
        
    Returns:
        Path to the improved subtitle file
    """
    if not WHISPER_AVAILABLE:
        raise ImportError("OpenAI Whisper is required. Install with: pip install openai-whisper")
    
    # Load existing subtitle data
    with open(existing_subtitle_path, 'r', encoding='utf-8') as f:
        subtitle_data = json.load(f)
    
    # Extract new word timings using Whisper
    print(f"Improving word timings for: {existing_subtitle_path}")
    new_word_timings = extract_word_timings_with_whisper(audio_path, whisper_model)
    
    # Update the subtitle data with new timings
    subtitle_data['word_timings'] = new_word_timings
    subtitle_data['metadata']['whisper_model'] = whisper_model
    subtitle_data['metadata']['generation_method'] = 'whisper_enhanced'
    subtitle_data['version'] = '2.0'
    
    # Rebuild sentences with new timing
    sentences = []
    current_sentence_idx = -1
    
    for word_data in new_word_timings:
        if word_data['sentence_index'] != current_sentence_idx:
            current_sentence_idx = word_data['sentence_index']
            sentences.append({
                'text': word_data['sentence'],
                'index': current_sentence_idx,
                'start_time': word_data['start_time'],
                'end_time': word_data['end_time']
            })
        else:
            sentences[-1]['end_time'] = max(sentences[-1]['end_time'], word_data['end_time'])
    
    subtitle_data['sentences'] = sentences
    subtitle_data['metadata']['total_words'] = len(new_word_timings)
    subtitle_data['metadata']['total_sentences'] = len(sentences)
    subtitle_data['metadata']['total_duration'] = max(wt['end_time'] for wt in new_word_timings) if new_word_timings else 0
    
    # Save improved version
    improved_path = existing_subtitle_path.replace('.json', '_whisper_improved.json')
    with open(improved_path, 'w', encoding='utf-8') as f:
        json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
    
    print(f"Improved subtitles saved to: {improved_path}")
    return improved_path


# Integration function for the main system
def generate_enhanced_subtitles_with_optional_whisper(
    sentences: List[str],
    audio_clips: List[Any],
    audio_path: Optional[str] = None,
    use_whisper: bool = False,
    whisper_model: str = "base",
    config: Optional[Dict[str, Any]] = None,
    video_size: Tuple[int, int] = (1080, 1920)
) -> str:
    """
    Generate enhanced subtitles with optional Whisper integration.
    
    Falls back to estimation method if Whisper is not available or not requested.
    
    Args:
        sentences: List of sentence strings (for fallback)
        audio_clips: List of audio clip objects (for fallback)
        audio_path: Path to audio file (required if use_whisper=True)
        use_whisper: Whether to use Whisper for word timing
        whisper_model: Whisper model size to use
        config: Optional configuration overrides
        video_size: Video dimensions
        
    Returns:
        Path to generated enhanced subtitle JSON file
    """
    if use_whisper and WHISPER_AVAILABLE and audio_path:
        try:
            print("Using Whisper for precise word timing...")
            return create_enhanced_subtitles_with_whisper(
                audio_path=audio_path,
                video_size=video_size,
                whisper_model=whisper_model,
                config_overrides=config
            )
        except Exception as e:
            print(f"Whisper processing failed: {e}")
            print("Falling back to estimation method...")
    
    # Fall back to the original estimation method
    from enhanced_subtitles import generate_enhanced_subtitles, SubtitleConfig
    
    if config:
        subtitle_config = SubtitleConfig(**config)
    else:
        subtitle_config = None
    
    return generate_enhanced_subtitles(
        sentences=sentences,
        audio_clips=audio_clips,
        config=subtitle_config,
        video_size=video_size
    )
