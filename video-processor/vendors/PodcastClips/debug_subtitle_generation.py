#!/usr/bin/env python3
"""
Debug Subtitle Generation Script

This script tests subtitle generation for podcast clips by:
1. Transcribing a video using Whisper (turbo model)
2. Generating karaoke-style or traditional subtitles
3. Overlaying subtitles on the video for visual debugging

Usage:
    python debug_subtitle_generation.py --video /path/to/video.mp4
    python debug_subtitle_generation.py --video /path/to/video.mp4 --output /path/to/output.mp4
    python debug_subtitle_generation.py --video /path/to/video.mp4 --no-karaoke  # Traditional style
    python debug_subtitle_generation.py --video /path/to/video.mp4 --model base  # Use base model
"""

import argparse
import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

# Add parent paths for imports
current_dir = Path(__file__).parent
video_processor_dir = current_dir.parent.parent
backend_dir = video_processor_dir.parent / 'backend'
project_root = video_processor_dir.parent

# Load .env file from project root
try:
    from dotenv import load_dotenv
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment from: {env_path}")
    else:
        # Try video-processor directory
        env_path = video_processor_dir / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded environment from: {env_path}")
except ImportError:
    logger.warning("python-dotenv not installed. Environment variables must be set manually.")

# Add paths for imports
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(video_processor_dir))
sys.path.insert(0, str(current_dir))

# Set up package structure to avoid circular imports
import types

# Create vendor packages to allow direct imports without triggering __init__.py
vendors_package = types.ModuleType('vendors')
vendors_package.__path__ = [str(current_dir.parent)]
sys.modules['vendors'] = vendors_package

# Import required modules directly
try:
    from moviepy import VideoFileClip

    # Import subtitle generator directly to avoid __init__.py dependencies
    import importlib.util

    # Load SubtitleGenerator module directly
    subtitle_gen_path = current_dir / "subtitle_generator.py"
    spec = importlib.util.spec_from_file_location("subtitle_generator", subtitle_gen_path)
    subtitle_gen_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(subtitle_gen_module)
    SubtitleGenerator = subtitle_gen_module.SubtitleGenerator

    # Monkey-patch the validation method to add more logging
    original_validate = SubtitleGenerator._validate_composite_clips

    def enhanced_validate(self, clips, context=""):
        """Enhanced validation with detailed logging."""
        valid_clips = []
        for i, clip in enumerate(clips):
            if hasattr(clip, 'w') and hasattr(clip, 'h'):
                if clip.w > 0 and clip.h > 0:
                    valid_clips.append(clip)
                else:
                    logger.warning(
                        f"Skipping clip {i} in {context}: zero dimensions w={clip.w}, h={clip.h}, "
                        f"clip_type={type(clip).__name__}"
                    )
            else:
                logger.warning(f"Skipping clip {i} in {context}: missing dimension attributes")

        logger.debug(f"Validation for {context}: {len(valid_clips)}/{len(clips)} clips valid")
        return valid_clips

    SubtitleGenerator._validate_composite_clips = enhanced_validate

    # Load stable_ts module directly
    stable_ts_path = video_processor_dir / "vendors" / "AIvideos" / "stable_ts_enhanced_subtitles.py"
    spec = importlib.util.spec_from_file_location("stable_ts_enhanced_subtitles", stable_ts_path)
    stable_ts_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stable_ts_module)
    extract_word_timings_with_stable_ts = stable_ts_module.extract_word_timings_with_stable_ts

    logger.info("Successfully imported required modules")
except Exception as e:
    logger.error(f"Failed to import modules: {e}")
    import traceback
    traceback.print_exc()
    logger.error("Make sure all dependencies are installed:")
    logger.error("  pip install moviepy stable-ts whisper opencv-python numpy pillow loguru")
    sys.exit(1)


def transcribe_video(
    video_path: str,
    model_size: str = "turbo",
    use_gpu: bool = True
) -> List[Dict[str, Any]]:
    """
    Transcribe video using Whisper with word-level timing.

    Args:
        video_path: Path to input video
        model_size: Whisper model size ("tiny", "base", "small", "medium", "large", "turbo")
        use_gpu: Whether to use GPU acceleration

    Returns:
        List of word timing dictionaries
    """
    logger.info(f"Starting transcription with Whisper model: {model_size}")

    try:
        word_timings = extract_word_timings_with_stable_ts(
            audio_path=video_path,
            model_size=model_size,
            use_gpu=use_gpu,
            vad_threshold=0.35
        )

        logger.info(f"Transcription complete: {len(word_timings)} words detected")

        # Log sample of first few words
        if word_timings:
            logger.info("Sample words:")
            for i, word_data in enumerate(word_timings[:5]):
                word = word_data.get('word', '')
                start = word_data.get('start_time', 0)
                end = word_data.get('end_time', 0)
                logger.info(f"  [{i}] '{word}' @ {start:.2f}s - {end:.2f}s")

        return word_timings

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise


def generate_subtitled_video(
    video_path: str,
    output_path: str,
    word_timings: List[Dict[str, Any]],
    use_karaoke: bool = True,
    font_size: int = 50,
    vertical_offset: int = 400,
    highlight_color: str = "#FFEB3B",
    max_words_visible: int = 5,
    export_transcript: bool = False,
    min_word_duration: float = 0.1
) -> Dict[str, Any]:
    """
    Generate video with subtitles overlaid.

    Args:
        video_path: Path to input video
        output_path: Path for output video
        word_timings: Word timing data from Whisper
        use_karaoke: Use karaoke-style subtitles (default: True)
        font_size: Font size in points
        vertical_offset: Distance from bottom in pixels
        highlight_color: Background highlight color (hex format)
        max_words_visible: Maximum words visible at once (karaoke mode)
        export_transcript: Export transcript to JSON file
        min_word_duration: Minimum word duration in seconds (default: 0.1)

    Returns:
        Dictionary with processing statistics
    """
    logger.info(f"Processing video: {video_path}")
    logger.info(f"Subtitle style: {'Karaoke' if use_karaoke else 'Traditional'}")

    # Filter out words with very short durations to avoid MoviePy rendering issues
    original_word_count = len(word_timings)
    filtered_timings = []

    for word_data in word_timings:
        duration = word_data.get('end_time', 0) - word_data.get('start_time', 0)
        if duration >= min_word_duration:
            filtered_timings.append(word_data)
        else:
            logger.debug(
                f"Filtering out word '{word_data.get('word', '')}' "
                f"(duration {duration:.3f}s < {min_word_duration}s)"
            )

    if filtered_timings != word_timings:
        logger.info(
            f"Filtered {original_word_count - len(filtered_timings)} words "
            f"with duration < {min_word_duration}s"
        )
        word_timings = filtered_timings

    # Load video
    video_clip = VideoFileClip(video_path)
    logger.info(f"Video loaded: {video_clip.w}x{video_clip.h} @ {video_clip.fps}fps, duration: {video_clip.duration:.1f}s")

    # Initialize subtitle generator
    subtitle_gen = SubtitleGenerator(
        font_size=font_size,
        color="#FFFFFF",
        stroke_color="#000000",
        stroke_width=3,
        position="bottom",
        vertical_offset=vertical_offset,
        highlight_color=highlight_color,
        max_words_visible=max_words_visible
    )

    # Generate subtitled video
    logger.info("Generating subtitles...")
    try:
        subtitled_clip = subtitle_gen.add_subtitles_to_video(
            video_clip=video_clip,
            word_timings=word_timings,
            clip_start_time=0.0,
            use_karaoke_style=use_karaoke
        )

        # Validate the composite clip
        logger.info(f"Validating composite clip: {subtitled_clip.w}x{subtitled_clip.h}")

        if subtitled_clip.w <= 0 or subtitled_clip.h <= 0:
            raise ValueError(f"Invalid composite dimensions: {subtitled_clip.w}x{subtitled_clip.h}")

    except Exception as e:
        logger.error(f"Failed to create subtitled video: {e}")
        raise

    # Write output video
    logger.info(f"Writing output video to: {output_path}")
    try:
        # Use ffmpeg_params to add more robust encoding options
        subtitled_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=video_clip.fps,
            preset='medium',
            threads=4,
            # Add ffmpeg params to handle edge cases better
            ffmpeg_params=[
                '-pix_fmt', 'yuv420p',  # Ensure compatible pixel format
                '-movflags', '+faststart'  # Enable streaming
            ],
            logger=None,  # Suppress moviepy's default logger
            temp_audiofile=None,  # Let MoviePy handle temp files
            remove_temp=True
        )
    except Exception as e:
        logger.error(f"Failed to write video file: {e}")
        logger.info("Attempting to render a test frame to diagnose the issue...")

        try:
            # Try to render the first frame to see what fails
            test_frame = subtitled_clip.get_frame(0)
            logger.info(f"Test frame shape: {test_frame.shape}")
        except Exception as frame_error:
            logger.error(f"Frame rendering failed: {frame_error}")

        # Try alternative rendering approach using iter_frames
        logger.info("Trying alternative rendering approach with manual frame iteration...")
        alternative_success = False
        try:
            import cv2
            import numpy as np

            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out_writer = cv2.VideoWriter(
                output_path.replace('.mp4', '_opencv.mp4'),
                fourcc,
                video_clip.fps,
                (video_clip.w, video_clip.h)
            )

            frame_count = 0
            total_frames = int(video_clip.duration * video_clip.fps)

            logger.info(f"Rendering {total_frames} frames manually...")

            for t in np.arange(0, video_clip.duration, 1.0/video_clip.fps):
                try:
                    frame = subtitled_clip.get_frame(t)
                    # Convert RGB to BGR for OpenCV
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    out_writer.write(frame_bgr)
                    frame_count += 1

                    if frame_count % 100 == 0:
                        logger.info(f"Rendered {frame_count}/{total_frames} frames...")

                except Exception as frame_err:
                    logger.error(f"Failed to render frame at t={t:.3f}s: {frame_err}")
                    # Use the last good frame or a blank frame
                    if frame_count > 0:
                        out_writer.write(frame_bgr)  # Repeat last frame
                    frame_count += 1

            out_writer.release()
            opencv_output = output_path.replace('.mp4', '_opencv.mp4')
            logger.info(f"Alternative rendering complete: {opencv_output}")

            # Merge audio from original video into the OpenCV-rendered video
            logger.info("Merging audio from original video...")
            try:
                import subprocess

                final_output = output_path.replace('.mp4', '_final.mp4')

                # Use ffmpeg to copy audio from original and video from opencv output
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-i', opencv_output,  # Video source (no audio)
                    '-i', video_path,  # Audio source
                    '-c:v', 'copy',  # Copy video stream
                    '-c:a', 'aac',  # Encode audio as AAC
                    '-map', '0:v:0',  # Take video from first input
                    '-map', '1:a:0',  # Take audio from second input
                    '-shortest',  # Match shortest stream duration
                    final_output
                ]

                subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
                logger.info(f"Audio merged successfully: {final_output}")
                logger.info(f"✅ Final video with subtitles and audio: {final_output}")

                # Clean up the no-audio version
                import os
                os.remove(opencv_output)
                logger.info("Cleaned up intermediate OpenCV file")

                # Update the output path so stats reflect the final file
                output_path = final_output
                alternative_success = True

            except Exception as audio_error:
                logger.error(f"Failed to merge audio: {audio_error}")
                logger.info(f"You can manually merge audio using:")
                logger.info(f"  ffmpeg -i {opencv_output} -i {video_path} -c:a aac -map 0:v:0 -map 1:a:0 {final_output}")
                # Even without audio, we have a video file
                output_path = opencv_output
                alternative_success = True

        except Exception as alt_error:
            logger.error(f"Alternative rendering also failed: {alt_error}")

        # Only raise if alternative rendering also failed
        if not alternative_success:
            raise

    # Cleanup
    video_clip.close()
    subtitled_clip.close()

    # Export transcript if requested
    if export_transcript:
        transcript_path = output_path.replace('.mp4', '_transcript.json')
        transcript_text = ' '.join([w.get('word', '') for w in word_timings])

        with open(transcript_path, 'w') as f:
            json.dump({
                'word_count': len(word_timings),
                'transcript': transcript_text,
                'word_timings': word_timings
            }, f, indent=2)

        logger.info(f"Exported transcript to: {transcript_path}")

    stats = {
        'video_path': video_path,
        'output_path': output_path,
        'duration': video_clip.duration,
        'word_count': len(word_timings),
        'style': 'karaoke' if use_karaoke else 'traditional'
    }

    logger.info("Processing complete!")
    logger.info(f"Statistics:")
    logger.info(f"  Duration: {stats['duration']:.1f}s")
    logger.info(f"  Words: {stats['word_count']}")
    logger.info(f"  Style: {stats['style']}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Debug subtitle generation for podcast clips",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with karaoke-style subtitles
  python debug_subtitle_generation.py --video podcast.mp4

  # Custom output path
  python debug_subtitle_generation.py --video podcast.mp4 --output debug_output.mp4

  # Traditional subtitle style (no karaoke highlighting)
  python debug_subtitle_generation.py --video podcast.mp4 --no-karaoke

  # Use different Whisper model
  python debug_subtitle_generation.py --video podcast.mp4 --model base

  # Customize subtitle appearance
  python debug_subtitle_generation.py --video podcast.mp4 --font-size 80 --highlight-color "#FF5733"

  # Export transcript to JSON
  python debug_subtitle_generation.py --video podcast.mp4 --export-transcript

  # Disable GPU (use CPU)
  python debug_subtitle_generation.py --video podcast.mp4 --no-gpu

  # Adjust minimum word duration filter (to handle very short words)
  python debug_subtitle_generation.py --video podcast.mp4 --min-duration 0.05
        """
    )

    parser.add_argument(
        '--video', '-v',
        required=True,
        help='Path to input video file (9:16 format recommended)'
    )

    parser.add_argument(
        '--output', '-o',
        help='Path for output video (default: <input>_subtitled.mp4)'
    )

    parser.add_argument(
        '--model',
        type=str,
        default='turbo',
        choices=['tiny', 'base', 'small', 'medium', 'large', 'turbo'],
        help='Whisper model size (default: turbo)'
    )

    parser.add_argument(
        '--no-karaoke',
        action='store_true',
        help='Use traditional subtitle style instead of karaoke highlighting'
    )

    parser.add_argument(
        '--font-size',
        type=int,
        default=50,
        help='Font size in points (default: 50)'
    )

    parser.add_argument(
        '--vertical-offset',
        type=int,
        default=400,
        help='Distance from bottom in pixels (default: 400)'
    )

    parser.add_argument(
        '--highlight-color',
        type=str,
        default='#FFEB3B',
        help='Background highlight color in hex format (default: #FFEB3B)'
    )

    parser.add_argument(
        '--max-words',
        type=int,
        default=5,
        help='Maximum words visible at once in karaoke mode (default: 5)'
    )

    parser.add_argument(
        '--export-transcript',
        action='store_true',
        help='Export transcript to JSON file'
    )

    parser.add_argument(
        '--no-gpu',
        action='store_true',
        help='Disable GPU acceleration (use CPU instead)'
    )

    parser.add_argument(
        '--min-duration',
        type=float,
        default=0.1,
        help='Minimum word duration in seconds (default: 0.1). Words shorter than this are filtered out to avoid rendering issues.'
    )

    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.video):
        logger.error(f"Video file not found: {args.video}")
        sys.exit(1)

    # Set output path
    if args.output:
        output_path = args.output
    else:
        video_dir = os.path.dirname(args.video)
        video_name = os.path.splitext(os.path.basename(args.video))[0]
        output_path = os.path.join(video_dir, f"{video_name}_subtitled.mp4")

    # Run processing
    try:
        logger.info("=" * 60)
        logger.info("SUBTITLE GENERATION DEBUG SCRIPT")
        logger.info("=" * 60)

        # Step 1: Transcribe video
        logger.info("\nStep 1/2: Transcribing video with Whisper...")
        word_timings = transcribe_video(
            video_path=args.video,
            model_size=args.model,
            use_gpu=not args.no_gpu
        )

        if not word_timings:
            logger.error("No words detected in transcription. Please check your video has audio.")
            sys.exit(1)

        # Step 2: Generate subtitled video
        logger.info("\nStep 2/2: Generating subtitled video...")
        stats = generate_subtitled_video(
            video_path=args.video,
            output_path=output_path,
            word_timings=word_timings,
            use_karaoke=not args.no_karaoke,
            font_size=args.font_size,
            vertical_offset=args.vertical_offset,
            highlight_color=args.highlight_color,
            max_words_visible=args.max_words,
            export_transcript=args.export_transcript,
            min_word_duration=args.min_duration
        )

        logger.info("\n" + "=" * 60)
        logger.info("SUCCESS!")
        logger.info("=" * 60)
        print(f"\nSubtitled video saved to: {output_path}")

        if args.export_transcript:
            transcript_path = output_path.replace('.mp4', '_transcript.json')
            print(f"Transcript saved to: {transcript_path}")

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
