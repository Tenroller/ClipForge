"""
Integration module for optimized subtitle rendering.

This module integrates the new optimized subtitle renderer and stable-ts
enhanced ASR into the existing video generation pipeline.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from moviepy import CompositeVideoClip, VideoFileClip

def create_optimized_enhanced_subtitles(
    sentences: List[str],
    audio_clips: List[Any],
    audio_path: Optional[str] = None,
    video_size: Tuple[int, int] = (1080, 1920),
    fps: float = 30.0,
    duration: float = 0.0,
    use_stable_ts: bool = True,
    use_optimized_renderer: bool = True,
    whisper_model: str = "base",
    use_gpu: bool = True,
    config_overrides: Optional[Dict[str, Any]] = None
) -> Tuple[Union[CompositeVideoClip, Any], str]:
    """
    Create enhanced subtitles using the new optimized pipeline.
    
    This function integrates both major optimizations:
    1. stable-ts for better word-level timestamps
    2. Pre-rendered frame optimization for better performance
    
    Args:
        sentences: List of sentence strings (fallback only)
        audio_clips: List of audio clip objects (fallback only)
        audio_path: Path to audio file (required for stable-ts)
        video_size: Video dimensions (width, height)
        fps: Video frame rate
        duration: Total video duration in seconds
        use_stable_ts: Whether to use stable-ts for enhanced timing
        use_optimized_renderer: Whether to use pre-rendered frame optimization
        whisper_model: Model size to use
        use_gpu: Whether to use GPU acceleration
        config_overrides: Optional configuration overrides
        
    Returns:
        Tuple of (subtitle_clip, subtitle_data_path)
    """
    print(f"🚀 Creating optimized enhanced subtitles...")
    print(f"   - stable-ts: {'✅ Enabled' if use_stable_ts else '❌ Disabled'}")
    print(f"   - Optimized renderer: {'✅ Enabled' if use_optimized_renderer else '❌ Disabled'}")
    print(f"   - Model: {whisper_model}")
    print(f"   - GPU: {'✅ Enabled' if use_gpu else '❌ Disabled'}")
    
    subtitle_data_path = None
    
    # Step 1: Generate enhanced subtitle data with improved ASR
    if use_stable_ts and audio_path:
        try:
            from .stable_ts_enhanced_subtitles import generate_enhanced_subtitles_with_stable_ts
            
            print("📝 Generating subtitles with stable-ts...")
            subtitle_data_path = generate_enhanced_subtitles_with_stable_ts(
                sentences=sentences,
                audio_clips=audio_clips,
                audio_path=audio_path,
                use_stable_ts=True,
                model_size=whisper_model,
                use_gpu=use_gpu,
                config=config_overrides,
                video_size=video_size
            )
            print(f"✅ stable-ts subtitles generated: {subtitle_data_path}")
            
        except Exception as e:
            print(f"❌ stable-ts failed: {e}")
            print("🔄 Falling back to standard Whisper...")
            use_stable_ts = False
    
    # Fallback to standard Whisper if stable-ts failed or not requested
    if not subtitle_data_path:
        try:
            from .whisper_enhanced_subtitles import generate_enhanced_subtitles_with_optional_whisper
            
            print("📝 Generating subtitles with standard Whisper...")
            subtitle_data_path = generate_enhanced_subtitles_with_optional_whisper(
                sentences=sentences,
                audio_clips=audio_clips,
                audio_path=audio_path,
                use_whisper=True,
                whisper_model=whisper_model,
                config=config_overrides,
                video_size=video_size
            )
            print(f"✅ Whisper subtitles generated: {subtitle_data_path}")
            
        except Exception as e:
            print(f"❌ Standard Whisper also failed: {e}")
            # Ultimate fallback - create basic subtitle data
            subtitle_data_path = _create_fallback_subtitle_data(
                sentences, audio_clips, video_size, config_overrides
            )
    
    if not subtitle_data_path or not os.path.exists(subtitle_data_path):
        raise RuntimeError("Failed to generate subtitle data with all available methods")
    
    # Step 2: Create subtitle clip using optimized renderer
    if use_optimized_renderer:
        try:
            from .optimized_subtitle_renderer import create_optimized_subtitle_clip_from_file
            
            print("🎨 Rendering subtitles with optimized pre-rendered frames...")
            subtitle_clip = create_optimized_subtitle_clip_from_file(
                subtitle_path=subtitle_data_path,
                video_size=video_size,
                fps=fps,
                duration=duration
            )
            print("✅ Optimized subtitle rendering completed!")
            return subtitle_clip, subtitle_data_path
            
        except Exception as e:
            print(f"❌ Optimized renderer failed: {e}")
            print("🔄 Falling back to standard renderer...")
    
    # Fallback to standard word highlighting renderer
    try:
        from .word_highlight_subtitles import create_word_highlight_subtitles_from_file
        
        print("🎨 Rendering subtitles with standard word highlighting...")
        subtitle_clip = create_word_highlight_subtitles_from_file(
            subtitle_path=subtitle_data_path,
            video_size=video_size
        )
        print("✅ Standard subtitle rendering completed!")
        return subtitle_clip, subtitle_data_path
        
    except Exception as e:
        print(f"❌ Standard renderer also failed: {e}")
        raise RuntimeError(f"All subtitle rendering methods failed. Last error: {e}")


def _create_fallback_subtitle_data(
    sentences: List[str],
    audio_clips: List[Any],
    video_size: Tuple[int, int],
    config_overrides: Optional[Dict[str, Any]]
) -> str:
    """Create basic fallback subtitle data when all ASR methods fail."""
    
    import uuid
    from datetime import datetime
    
    print("🆘 Creating fallback subtitle data...")
    
    # Calculate basic timing based on audio clip durations
    word_timings = []
    sentence_index = 0
    word_index = 0
    current_time = 0.0
    
    for sentence_idx, (sentence, audio_clip) in enumerate(zip(sentences, audio_clips)):
        sentence_duration = getattr(audio_clip, 'duration', 3.0)  # Default 3 seconds
        words = sentence.split()
        word_duration = sentence_duration / max(len(words), 1)
        
        sentence_start = current_time
        for word in words:
            word_timings.append({
                'word': word,
                'start_time': current_time,
                'end_time': current_time + word_duration,
                'sentence_index': sentence_index,
                'word_index': word_index,
                'sentence': sentence,
                'confidence': 0.5,  # Low confidence for fallback
                'method': 'fallback_estimation'
            })
            current_time += word_duration
            word_index += 1
        
        sentence_index += 1
    
    # Basic configuration
    config = {
        'font_family': 'Arial-Bold',
        'font_size': 48,
        'default_color': '#FFFFFF',
        'highlight_color': '#FF0000',
        'stroke_color': '#000000',
        'stroke_width': 2,
        'position': 'center,bottom'
    }
    
    if config_overrides:
        config.update(config_overrides)
    
    # Create subtitle data structure
    subtitle_data = {
        'version': '2.0',
        'type': 'tiktok_enhanced_fallback',
        'config': config,
        'video_size': video_size,
        'sentences': [
            {
                'text': sentence,
                'index': i,
                'start_time': word_timings[0]['start_time'] if word_timings else 0,
                'end_time': word_timings[-1]['end_time'] if word_timings else 3
            }
            for i, sentence in enumerate(sentences)
        ],
        'word_timings': word_timings,
        'metadata': {
            'total_words': len(word_timings),
            'total_sentences': len(sentences),
            'total_duration': current_time,
            'generation_method': 'fallback_estimation',
            'created_at': datetime.now().isoformat()
        }
    }
    
    # Save fallback data
    fallback_id = uuid.uuid4().hex[:8]
    output_path = f"subtitles/fallback_{fallback_id}_enhanced.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
    
    print(f"🆘 Fallback subtitle data created: {output_path}")
    return output_path


def is_optimized_subtitle_available() -> Dict[str, bool]:
    """Check availability of optimized subtitle components."""
    
    availability = {
        'stable_ts': False,
        'torch': False,
        'cuda': False,
        'optimized_renderer': False
    }
    
    # Check stable-ts
    try:
        import stable_whisper
        availability['stable_ts'] = True
    except ImportError:
        pass
    
    # Check PyTorch
    try:
        import torch
        availability['torch'] = True
        if torch.cuda.is_available():
            availability['cuda'] = True
    except ImportError:
        pass
    
    # Check optimized renderer (always available if PIL is available)
    try:
        from PIL import Image, ImageDraw, ImageFont
        availability['optimized_renderer'] = True
    except ImportError:
        pass
    
    return availability


def get_recommended_settings() -> Dict[str, Any]:
    """Get recommended settings based on available hardware and libraries."""
    
    availability = is_optimized_subtitle_available()
    
    settings = {
        'use_stable_ts': availability['stable_ts'],
        'use_optimized_renderer': availability['optimized_renderer'],
        'use_gpu': availability['cuda'],
        'whisper_model': 'base'  # Safe default
    }
    
    # Adjust model size based on GPU availability
    if availability['cuda']:
        # With GPU, can use larger models
        settings['whisper_model'] = 'small'  # Good balance of speed/accuracy
    else:
        # CPU only - use smaller model
        settings['whisper_model'] = 'tiny'  # Faster on CPU
    
    print("🔧 Recommended settings based on your system:")
    print(f"   - stable-ts: {'✅ Available' if availability['stable_ts'] else '❌ Install: pip install stable-ts'}")
    print(f"   - PyTorch: {'✅ Available' if availability['torch'] else '❌ Install PyTorch'}")
    print(f"   - CUDA: {'✅ Available' if availability['cuda'] else '❌ No CUDA GPU detected'}")
    print(f"   - Optimized renderer: {'✅ Available' if availability['optimized_renderer'] else '❌ Missing PIL'}")
    print(f"   - Recommended model: {settings['whisper_model']}")
    
    return settings
