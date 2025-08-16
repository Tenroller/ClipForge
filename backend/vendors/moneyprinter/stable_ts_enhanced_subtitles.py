"""
Enhanced subtitle creation using stable-ts for better word-level timestamps.

This module implements the research recommendation to use stable-ts instead of 
raw OpenAI Whisper for improved timestamp accuracy and post-processing capabilities.
"""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

try:
    import stable_whisper
    STABLE_TS_AVAILABLE = True
except ImportError:
    STABLE_TS_AVAILABLE = False
    stable_whisper = None
    print("stable-ts not available. Install with: pip install stable-ts")

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    print("PyTorch not available. GPU acceleration disabled.")


def extract_word_timings_with_stable_ts(
    audio_path: str,
    model_size: str = "base",
    use_gpu: bool = True,
    vad_threshold: float = 0.35,
    refine_whisper_precision: float = 0.15
) -> List[Dict[str, Any]]:
    """
    Extract word-level timings using stable-ts for enhanced precision.
    
    This implements the research recommendation to use stable-ts for better
    timestamp accuracy through VAD post-processing and timestamp refinement.
    
    Args:
        audio_path: Path to the audio file
        model_size: Whisper model size ("tiny", "base", "small", "medium", "large")
        use_gpu: Whether to use CUDA if available
        vad_threshold: Voice activity detection threshold (0.0-1.0)
        refine_whisper_precision: Precision threshold for timestamp refinement
        
    Returns:
        List of word timing dictionaries with enhanced timestamps
    """
    if not STABLE_TS_AVAILABLE:
        raise ImportError("stable-ts is required for enhanced word timing. Install with: pip install stable-ts")
    
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    # Determine device
    if TORCH_AVAILABLE and torch and use_gpu and torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print(f"Using device: {device}")
    
    # Load stable-ts model with GPU support
    print(f"Loading stable-ts model: {model_size}")
    try:
        if not stable_whisper:
            raise RuntimeError("stable_whisper not available")
        model = stable_whisper.load_model(model_size, device=device)
        print(f"✅ Model loaded successfully on {device}")
    except Exception as e:
        print(f"Failed to load model on {device}: {e}")
        if device == "cuda" and stable_whisper:
            print("Falling back to CPU...")
            model = stable_whisper.load_model(model_size, device="cpu")
            device = "cpu"
        else:
            raise
    
    # Transcribe with enhanced options
    print(f"Transcribing audio file: {audio_path}")
    
    try:
        # Use stable-ts specific options for better timing
        result = model.transcribe(
            audio_path,
            # Basic Whisper options
            task="transcribe",
            language=None,  # Auto-detect
            
            # stable-ts specific enhancements
            vad=True,  # Enable Voice Activity Detection
            vad_threshold=vad_threshold,  # VAD sensitivity
            min_word_dur=0.1,  # Minimum word duration
            
            # Word-level timing options
            word_timestamps=True,
            prepend_punctuations="\"'([{-",
            append_punctuations="\"'.。,!?::)]}、",
            
            # Refinement options
            refine_whisper_precision=refine_whisper_precision,
            min_silence_dur=0.1  # Minimum silence duration for word boundaries
        )
        
        print("✅ Transcription completed with stable-ts")
        
    except Exception as e:
        print(f"stable-ts transcription failed: {e}")
        print("Falling back to basic transcription...")
        # Fallback to basic transcription if advanced options fail
        result = model.transcribe(
            audio_path,
            task="transcribe",
            word_timestamps=True,
        )
    
    # Extract word timings with enhanced metadata
    word_timings = []
    sentence_index = 0
    word_index = 0
    
    # Process segments with stable-ts enhancements
    for segment in result.segments:
        segment_text = str(segment.text).strip()
        
        # Access words with proper stable-ts structure
        segment_words = getattr(segment, 'words', [])
        
        if segment_words:
            for word_data in segment_words:
                # Extract word with proper stable-ts attributes
                word_text = str(getattr(word_data, 'word', '')).strip()
                start_time = float(getattr(word_data, 'start', 0.0))
                end_time = float(getattr(word_data, 'end', 0.0))
                probability = float(getattr(word_data, 'probability', 1.0))
                
                # Skip empty words or invalid timings
                if not word_text or end_time <= start_time:
                    continue
                
                word_timings.append({
                    'word': word_text,
                    'start_time': start_time,
                    'end_time': end_time,
                    'sentence_index': sentence_index,
                    'word_index': word_index,
                    'sentence': segment_text,
                    'confidence': probability,
                    # Enhanced metadata from stable-ts
                    'method': 'stable_ts_enhanced',
                    'vad_processed': True,
                    'model_size': model_size,
                    'device_used': device
                })
                word_index += 1
            
            sentence_index += 1
    
    # Apply post-processing improvements if available
    if hasattr(result, 'refine'):
        try:
            print("Applying stable-ts refinement...")
            result = result.refine(
                audio_path,
                precision=refine_whisper_precision,
                rel_prob_decrease=0.05,  # Relative probability decrease threshold
            )
            
            # Re-extract refined timings
            word_timings = []
            sentence_index = 0
            word_index = 0
            
            for segment in result.segments:
                segment_text = str(segment.text).strip()
                segment_words = getattr(segment, 'words', [])
                
                if segment_words:
                    for word_data in segment_words:
                        word_text = str(getattr(word_data, 'word', '')).strip()
                        start_time = float(getattr(word_data, 'start', 0.0))
                        end_time = float(getattr(word_data, 'end', 0.0))
                        probability = float(getattr(word_data, 'probability', 1.0))
                        
                        if not word_text or end_time <= start_time:
                            continue
                        
                        word_timings.append({
                            'word': word_text,
                            'start_time': start_time,
                            'end_time': end_time,
                            'sentence_index': sentence_index,
                            'word_index': word_index,
                            'sentence': segment_text,
                            'confidence': probability,
                            'method': 'stable_ts_refined',
                            'vad_processed': True,
                            'refined': True,
                            'model_size': model_size,
                            'device_used': device
                        })
                        word_index += 1
                    
                    sentence_index += 1
            
            print("✅ Refinement applied successfully")
            
        except Exception as e:
            print(f"Refinement failed: {e}")
            print("Using non-refined results")
    
    print(f"✅ Extracted {len(word_timings)} words with stable-ts enhanced timing")
    return word_timings


def create_enhanced_subtitles_with_stable_ts(
    audio_path: str,
    output_path: Optional[str] = None,
    video_size: Tuple[int, int] = (1080, 1920),
    model_size: str = "base",
    use_gpu: bool = True,
    config_overrides: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create enhanced subtitles using stable-ts for precise word timing.
    
    This implements the research recommendation to use stable-ts instead of
    raw Whisper for better timestamp accuracy.
    
    Args:
        audio_path: Path to the audio file
        output_path: Optional output path for the JSON file
        video_size: Video dimensions (width, height)
        model_size: stable-ts model size to use
        use_gpu: Whether to use CUDA GPU acceleration
        config_overrides: Optional configuration overrides
        
    Returns:
        Path to the generated enhanced subtitle JSON file
    """
    if not STABLE_TS_AVAILABLE:
        raise ImportError("stable-ts is required. Install with: pip install stable-ts")
    
    # Extract word timings using stable-ts
    print("🚀 Using stable-ts for enhanced word timing precision...")
    word_timings = extract_word_timings_with_stable_ts(
        audio_path=audio_path,
        model_size=model_size,
        use_gpu=use_gpu
    )
    
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
    
    # Enhanced configuration optimized for stable-ts
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
    
    # Create subtitle data structure with stable-ts metadata
    subtitle_data = {
        'version': '2.1',  # Updated version for stable-ts enhanced
        'type': 'tiktok_enhanced_stable_ts',
        'config': default_config,
        'video_size': video_size,
        'sentences': sentences,
        'word_timings': word_timings,
        'metadata': {
            'total_words': len(word_timings),
            'total_sentences': len(sentences),
            'total_duration': max(wt['end_time'] for wt in word_timings) if word_timings else 0,
            'generation_method': 'stable_ts_enhanced',
            'model_size': model_size,
            'vad_enabled': True,
            'refined': any(wt.get('refined', False) for wt in word_timings),
            'gpu_used': (TORCH_AVAILABLE and torch and torch.cuda.is_available() and use_gpu) if TORCH_AVAILABLE else False,
            'stable_ts_version': getattr(stable_whisper, '__version__', 'unknown') if stable_whisper else None
        }
    }
    
    # Generate output path if not provided
    if output_path is None:
        import uuid
        audio_name = Path(audio_path).stem
        output_path = f"subtitles/{audio_name}_{uuid.uuid4().hex[:8]}_stable_ts_enhanced.json"
    
    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Enhanced subtitles with stable-ts timing saved to: {output_path}")
    return output_path


def improve_existing_subtitles_with_stable_ts(
    existing_subtitle_path: str,
    audio_path: str,
    model_size: str = "base",
    use_gpu: bool = True
) -> str:
    """
    Improve existing enhanced subtitles by replacing word timings with stable-ts generated ones.
    
    Args:
        existing_subtitle_path: Path to existing enhanced subtitle JSON
        audio_path: Path to the audio file
        model_size: stable-ts model to use
        use_gpu: Whether to use GPU acceleration
        
    Returns:
        Path to the improved subtitle file
    """
    if not STABLE_TS_AVAILABLE:
        raise ImportError("stable-ts is required. Install with: pip install stable-ts")
    
    # Load existing subtitle data
    with open(existing_subtitle_path, 'r', encoding='utf-8') as f:
        subtitle_data = json.load(f)
    
    # Extract new word timings using stable-ts
    print(f"🔧 Improving word timings with stable-ts for: {existing_subtitle_path}")
    new_word_timings = extract_word_timings_with_stable_ts(
        audio_path=audio_path,
        model_size=model_size,
        use_gpu=use_gpu
    )
    
    # Update the subtitle data with new timings
    subtitle_data['word_timings'] = new_word_timings
    subtitle_data['metadata']['generation_method'] = 'stable_ts_enhanced'
    subtitle_data['metadata']['model_size'] = model_size
    subtitle_data['metadata']['vad_enabled'] = True
    subtitle_data['metadata']['improved_with_stable_ts'] = True
    subtitle_data['version'] = '2.1'
    subtitle_data['type'] = 'tiktok_enhanced_stable_ts'
    
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
    improved_path = existing_subtitle_path.replace('.json', '_stable_ts_improved.json')
    with open(improved_path, 'w', encoding='utf-8') as f:
        json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Improved subtitles with stable-ts saved to: {improved_path}")
    return improved_path


# Backwards compatibility and integration function
def generate_enhanced_subtitles_with_stable_ts(
    sentences: List[str],
    audio_clips: List[Any],
    audio_path: Optional[str] = None,
    use_stable_ts: bool = True,
    model_size: str = "base",
    use_gpu: bool = True,
    config: Optional[Dict[str, Any]] = None,
    video_size: Tuple[int, int] = (1080, 1920)
) -> str:
    """
    Generate enhanced subtitles with stable-ts integration.
    
    This is the recommended entry point that uses stable-ts when available,
    falling back to the original Whisper method if needed.
    
    Args:
        sentences: List of sentence strings (for fallback)
        audio_clips: List of audio clip objects (for fallback)
        audio_path: Path to audio file (required for stable-ts)
        use_stable_ts: Whether to use stable-ts for enhanced timing
        model_size: Model size to use
        use_gpu: Whether to use GPU acceleration
        config: Optional configuration overrides
        video_size: Video dimensions
        
    Returns:
        Path to generated enhanced subtitle JSON file
    """
    if use_stable_ts and STABLE_TS_AVAILABLE and audio_path:
        try:
            print("🚀 Using stable-ts for enhanced word timing precision...")
            return create_enhanced_subtitles_with_stable_ts(
                audio_path=audio_path,
                video_size=video_size,
                model_size=model_size,
                use_gpu=use_gpu,
                config_overrides=config
            )
        except Exception as e:
            print(f"stable-ts processing failed: {e}")
            print("Falling back to standard Whisper method...")
    
    # Fall back to the standard Whisper method
    from .whisper_enhanced_subtitles import generate_enhanced_subtitles_with_optional_whisper
    
    return generate_enhanced_subtitles_with_optional_whisper(
        sentences=sentences,
        audio_clips=audio_clips,
        audio_path=audio_path,
        use_whisper=True,
        whisper_model=model_size,
        config=config,
        video_size=video_size
    )
