#!/usr/bin/env python3
"""
TTS Generator

This module handles:
1. Generating catchy intro messages using OpenRouter API
2. Converting text to speech using Kokoro TTS
3. Adding TTS audio to the beginning of compilations
"""

from functools import lru_cache
import os
import sys
import random
import tempfile
import warnings
import soundfile as sf
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, afx
from kokoro import KPipeline
import torch
from pathlib import Path


import uuid
from loguru import logger

# Add project root to Python path for imports
_project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, environment variables must be set manually
    pass

# Import OpenRouter client
try:
    from backend.utils.openrouter_client import generate_content as openrouter_generate_content
except ImportError:
    openrouter_generate_content = None

# Initialize logger for this module
logger = logger.bind(name="Compilation.tts_generator")

# Define placeholder logging functions that were imported but may not exist
def log_generation_step(logger, *args, **kwargs):
    logger.info(f"Generation step: {args}, {kwargs}")

def log_file_operation(logger, operation, path, **kwargs):
    logger.info(f"File {operation}: {path}, {kwargs}")


class TTSGenerator:
    def _extract_clean_phrase(self, text):
        """
        Extract a clean intro phrase from potentially messy AI-generated text
        
        Args:
            text (str): Raw text from AI
            
        Returns:
            str: Clean phrase or None if no suitable phrase found
        """
        import re
        
        if not text:
            return None
            
        # Remove markdown formatting first
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Remove **bold**
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Remove *italic*
        
        # Split into lines and process each
        lines = text.split('\n')
        candidate_phrases = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Remove list markers and bullets
            line = re.sub(r'^[\s\*\-\•\d+\.\)]+', '', line).strip()
            
            # Clean up quotes and punctuation
            line = line.strip('"\'""''')
            line = re.sub(r'^[^\w]+', '', line)  # Remove leading non-word chars
            
            # If line has a dash, take only the part before the dash (likely the quote)
            if ' - ' in line:
                line = line.split(' - ')[0].strip()
            
            # Skip lines that look like instructions or explanations (AFTER dash processing)
            skip_words = ['here', 'example', 'phrase', 'generate', 'create', 'compilation', 'perfect', 'requirement', 'instruction', 'like this']
            if any(word in line.lower() for word in skip_words):
                continue
            
            # Check if this looks like a good intro phrase
            words = line.split()
            if 2 <= len(words) <= 10:  # Reasonable phrase length
                # Clean up any trailing quotes or punctuation, then add exclamation
                line = line.rstrip("\"'!.?") + '!'
                candidate_phrases.append((line, len(words)))
        
        # Return the shortest reasonable phrase (usually the best)
        if candidate_phrases:
            candidate_phrases.sort(key=lambda x: x[1])  # Sort by word count
            return candidate_phrases[0][0]
            
        # If no good candidates, try to extract from first line
        first_line = lines[0] if lines else text
        first_line = re.sub(r'^[^\w]+', '', first_line.strip())
        first_line = first_line.strip('"\'""''')
        if len(first_line.split()) <= 15:  # Not too long
            return first_line.rstrip('!.?') + '!'
            
        return None

    def __init__(self, api_key=None):
        """
        Initialize TTS Generator
        
        Args:
            api_key (str): OpenRouter API key. If None, will try to get from environment.
        """
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable or pass api_key parameter.")
        
        # Set environment variable for the client
        os.environ['OPENROUTER_API_KEY'] = self.api_key
        
        # Initialize Kokoro TTS pipeline
        logger.info("Initializing Kokoro TTS pipeline...")
        
        # Suppress known warnings from the Kokoro model
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="torch.nn.modules.rnn")
            warnings.filterwarnings("ignore", category=FutureWarning, module="torch.nn.utils.weight_norm")
            # Initialize with American English by default, will switch dynamically
            self.tts_pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
            self.current_lang_code = 'a'
        
        # Available voices in Kokoro (B-grade and above only)
        self.voices = [
            # American English (lang_code='a') - B-grade and above
            'af_heart',    # Female, warm (A grade)
            'af_bella',    # Female, energetic (A- grade) 
            'af_nicole',   # Female, professional (B- grade)
            'af_sarah',    # Female, clear (C+ grade but B target quality)
            'af_aoede',    # Female (C+ grade but B target quality)
            'af_kore',     # Female (C+ grade but B target quality)
            'am_michael',  # Male, professional (C+ grade but B target quality)
            'am_fenrir',   # Male (C+ grade but B target quality)
            'am_puck',     # Male (C+ grade but B target quality)
            
            # British English (lang_code='b') - B-grade and above
            'bf_emma',     # Female (B- grade)
            'bf_isabella', # Female (C grade but B target quality)
            'bm_fable',    # Male (C grade but B target quality)
            'bm_george',   # Male (C grade but B target quality)
        ]
        
        print(f"✅ TTS Generator initialized with {len(self.voices)} voices")
        
        # Add GPU detection
        self.has_gpu = torch.cuda.is_available()
    
    def _get_lang_code_for_voice(self, voice):
        """
        Get the language code for a given voice
        
        Args:
            voice (str): Voice name
            
        Returns:
            str: Language code ('a' for American English, 'b' for British English)
        """
        # British English voices start with 'b'
        if voice.startswith('b'):
            return 'b'
        # American English voices start with 'a'
        return 'a'
    
    def _switch_language_if_needed(self, voice):
        """
        Switch TTS pipeline language if needed for the given voice
        
        Args:
            voice (str): Voice name
        """
        required_lang_code = self._get_lang_code_for_voice(voice)
        if self.current_lang_code != required_lang_code:
            print(f"🔄 Switching TTS language from '{self.current_lang_code}' to '{required_lang_code}' for voice '{voice}'")
            self.tts_pipeline = KPipeline(lang_code=required_lang_code, repo_id='hexgrad/Kokoro-82M')
            self.current_lang_code = required_lang_code
    
    def generate_intro_message(self, context="cat videos"):
        """
        Generate a catchy intro message using OpenRouter API
        
        Args:
            context (str): Context for the intro message
            
        Returns:
            str: Generated intro message
        """
        if openrouter_generate_content is None:
            print("⚠️ OpenRouter client not available, using fallback")
            fallback_messages = [
                "Cat videos of the day!",
                "Daily dose of cats!",
                "Your feline fix is here!",
                "Purrfect moments ahead!",
                "Get ready for some cat magic!",
                "Cute cats incoming!",
                "Time for your cat therapy!",
                "Cuteness overload alert!",
            ]
            message = random.choice(fallback_messages)
            print(f"🎙️ Using fallback intro: '{message}'")
            return message
            
        try:
            # Much more specific and clear prompt to get just ONE clean phrase
            prompt = f"""Create ONE short, catchy intro phrase for a {context} compilation video that would be perfect for TikTok/social media.

REQUIREMENTS:
- Maximum 8 words
- High energy and fun
- Must end with exclamation mark
- No formatting, no lists, no explanations
- Just return the phrase itself

EXAMPLES:
"Cat videos of the day!"
"Daily dose of cats!"
"Purrfect moments ahead!"

Generate ONE phrase now:"""
            
            raw_text = openrouter_generate_content(
                prompt=prompt,
                model="openrouter/auto",
                temperature=0.7,
                max_tokens=50
            )
            
            raw_text = raw_text.strip() if raw_text else ""
            
            # Show what AI actually returned for debugging
            if len(raw_text) > 100:
                print(f"🤖 AI returned (truncated): '{raw_text[:100]}...'")
            else:
                print(f"🤖 AI returned: '{raw_text}'")
            
            # Use the enhanced extraction method
            intro_message = self._extract_clean_phrase(raw_text)
            
            # Final validation - if extraction failed or result is invalid, use fallback
            if not intro_message or len(intro_message) > 50 or any(word in intro_message.lower() for word in ['here are', 'examples', 'phrases', 'perfect for']):
                raise ValueError("Generated text appears to be instructions rather than a phrase")
            
            print(f"🎙️ Extracted clean intro: '{intro_message}'")
            return intro_message
            
        except Exception as e:
            print(f"⚠️ Error generating intro with OpenRouter: {e}")

            # Enhanced fallback with more variety
            fallback_messages = [
                "Cat videos of the day!",
                "Daily dose of cats!",
                "Your feline fix is here!",
                "Purrfect moments ahead!",
                "Get ready for some cat magic!",
                "Cute cats incoming!",
                "Time for your cat therapy!",
                "Whiskers and wags await!",
                "Meow-gical moments incoming!",
                "Cuteness overload alert!",
                "Feline frenzy time!",
                "Your daily catnip dose!",
                "Prepare for peak purrfection!",
                "Kitty chaos unleashed!"
            ]
            message = random.choice(fallback_messages)
            print(f"🎙️ Using fallback intro: '{message}'")
            return message
    
    def text_to_speech(self, text, voice=None, output_path=None):
        """
        Convert text to speech using Kokoro TTS
        
        Args:
            text (str): Text to convert to speech
            voice (str): Voice to use (random if None)
            output_path (str): Output audio file path
            
        Returns:
            str: Path to generated audio file
        """
        try:
            if voice is None:
                voice = random.choice(self.voices)
            
            if output_path is None:
                output_path = tempfile.mktemp(suffix='.wav')
            
            print(f"🎤 Converting text to speech: '{text}' (voice: {voice})")
            
            # Switch language if needed for this voice
            self._switch_language_if_needed(voice)
            
            # Generate audio using Kokoro
            generator = self.tts_pipeline(text, voice=voice)
            
            # Get the audio data from the generator
            audio_data = None
            for i, (gs, ps, audio) in enumerate(generator):
                audio_data = audio
                break  # Take the first (and usually only) result
            
            if audio_data is not None:
                # Save audio file
                sf.write(output_path, audio_data, 24000)  # Kokoro uses 24kHz sample rate
                print(f"✅ TTS audio saved: {output_path}")
                return output_path
            else:
                raise Exception("No audio data generated")
                
        except Exception as e:
            print(f"❌ Error generating TTS: {e}")
            return None
    
    def add_tts_intro_to_video(self, video_path, output_path, intro_text=None, voice=None, fade_duration=0.5):
        """
        Add TTS intro to the beginning of a video
        
        Args:
            video_path (str): Path to input video
            output_path (str): Path to output video
            intro_text (str): Intro text (auto-generated if None)
            voice (str): Voice to use (random if None)
            fade_duration (float): Fade duration in seconds
            
        Returns:
            str: Path to output video with TTS intro
        """
        try:
            # Generate intro text if not provided
            if intro_text is None:
                intro_text = self.generate_intro_message()
            
            # Use cached audio if available, otherwise generate new TTS audio
            tts_audio_path = None
            if hasattr(self, '_cached_audio_path') and self._cached_audio_path and os.path.exists(self._cached_audio_path):
                tts_audio_path = self._cached_audio_path
                print(f"   🎵 Using cached TTS audio: {os.path.basename(tts_audio_path)}")
            else:
                # Generate TTS audio
                tts_audio_path = self.text_to_speech(intro_text, voice)
                if not tts_audio_path:
                    print("❌ Failed to generate TTS audio")
                    return None
            
            # Load video and audio clips
            video_clip = VideoFileClip(video_path)
            tts_audio = AudioFileClip(tts_audio_path)
            
            # Validate TTS audio
            if tts_audio.duration is None or tts_audio.duration <= 0:
                raise Exception("TTS audio has invalid duration")
            
            # Add fade-out to TTS audio (v2.0 class-based effect)
            tts_audio = tts_audio.with_effects([afx.AudioFadeOut(fade_duration)])
            
            # Create silence gap after TTS
            silence_duration = 0.3  # 300ms gap
            
            # Adjust video audio to start after TTS + silence, but reduce volume during TTS
            original_audio = video_clip.audio
            if original_audio and original_audio.duration is not None:
                # Lower the volume of original audio during TTS intro
                # Ensure tts_audio.duration is not None before calculation
                if tts_audio.duration is None:
                    raise Exception("TTS audio duration is None after validation")
                tts_end_time = tts_audio.duration + silence_duration
                
                # Split original audio into TTS period and after TTS
                if original_audio.duration > tts_end_time:
                    # During TTS: lower volume significantly
                    audio_during_tts = original_audio.subclipped(0, tts_end_time).with_volume_scaled(0.1)
                    # After TTS: normal volume with fade in
                    audio_after_tts = original_audio.subclipped(tts_end_time).with_volume_scaled(1.0).with_start(tts_end_time)
                    
                    # Composite all audio tracks
                    final_audio = CompositeAudioClip([tts_audio, audio_during_tts, audio_after_tts])
                else:
                    # Video is shorter than TTS, just overlay TTS with reduced original volume
                    reduced_audio = original_audio.with_volume_scaled(0.1)
                    final_audio = CompositeAudioClip([tts_audio, reduced_audio])
            else:
                final_audio = tts_audio
            
            # Create final video with new audio - NO FRAME EXTENSION
            final_video = video_clip.with_audio(final_audio)
            
            # Validate the final video before writing
            if final_video.duration is None or final_video.duration <= 0:
                raise Exception("Final video has invalid duration")
            
            if final_video.audio is None:
                print("⚠️ Warning: Final video has no audio track")
            
            # Ensure audio duration matches video duration
            if final_video.audio and final_video.audio.duration != final_video.duration:
                print(f"⚠️ Audio duration ({final_video.audio.duration:.2f}s) doesn't match video duration ({final_video.duration:.2f}s)")
                # Extend or trim audio to match video duration
                if final_video.audio.duration < final_video.duration:
                    # Extend audio with silence
                    from moviepy import AudioClip
                    silence_duration = final_video.duration - final_video.audio.duration
                    silence = AudioClip(lambda t: [0, 0], duration=silence_duration, fps=final_video.audio.fps)
                    extended_audio = CompositeAudioClip([final_video.audio, silence.with_start(final_video.audio.duration)])
                    final_video = final_video.with_audio(extended_audio)
                else:
                    # Trim audio to match video duration
                    trimmed_audio = final_video.audio.subclipped(0, final_video.duration)
                    final_video = final_video.with_audio(trimmed_audio)
            
            # Use GPU encoding if available and set high-quality parameters
            codec = 'h264_nvenc' if (hasattr(self, 'has_gpu') and self.has_gpu) else 'libx264'
            bitrate = '6000k' if (hasattr(self, 'has_gpu') and self.has_gpu) else '5000k'
            preset = 'p4' if (hasattr(self, 'has_gpu') and self.has_gpu) else 'slow'

            ffmpeg_params = [
                '-movflags', 'faststart',
                '-pix_fmt', 'yuv420p',
                '-profile:v', 'high',
                '-level', '4.1',
            ]
            
            # Add CPU-specific quality flags
            if not (hasattr(self, 'has_gpu') and self.has_gpu):
                ffmpeg_params.extend([
                    '-crf', '22',
                    '-maxrate', bitrate,
                    '-bufsize', str(int(bitrate.replace('k', '')) * 2) + 'k'
                ])

            final_video.write_videofile(
                output_path,
                codec=codec,
                audio_codec='aac',
                temp_audiofile=os.path.join(tempfile.gettempdir(), f'temp-audio-{uuid.uuid4().hex}.m4a'),
                remove_temp=True,
                fps=30,
                preset=preset,
                threads=4,
                logger=None,
                bitrate=bitrate,
                ffmpeg_params=ffmpeg_params
            )
            
            # Cleanup
            try:
                video_clip.close()
                tts_audio.close()
                final_video.close()
                if original_audio:
                    original_audio.close()
            except Exception as cleanup_error:
                print(f"⚠️ Warning during cleanup: {cleanup_error}")
            
            # Remove temporary TTS file (only if not from cache)
            if (os.path.exists(tts_audio_path) and 
                not (hasattr(self, '_cached_audio_path') and tts_audio_path == self._cached_audio_path)):
                os.remove(tts_audio_path)
            
            print(f"✅ TTS intro video created: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error adding TTS intro: {e}")
            return None
    
    def create_tts_compilation(self, selected_clips, output_path, compilation_num=1, generator=None):
        """
        Create a compilation with TTS intro
        
        Args:
            selected_clips (list): List of selected video clips
            output_path (str): Output path for the compilation
            compilation_num (int): Compilation number
            generator: TikYouGenerator instance to avoid circular imports
            
        Returns:
            str: Path to created compilation or None if failed
        """
        try:
            print(f"🎙️ Creating TTS compilation {compilation_num}...")
            
            # Validate input clips
            if not selected_clips:
                print("❌ No clips provided for TTS compilation")
                return None
            
            print(f"   📹 Processing {len(selected_clips)} clips for TTS compilation")
            
            # First create a temporary normal compilation
            temp_compilation = output_path.replace('.mp4', '_temp.mp4')
            
            # Use the passed generator instance or create one
            if generator is None:
                # Avoid circular import by importing here only if needed
                from .generator import TikYouGenerator
                generator = TikYouGenerator()
            
            # Create normal compilation first
            temp_result = generator.create_single_compilation(selected_clips, temp_compilation, compilation_num)
            if not temp_result:
                print("❌ Failed to create base compilation")
                return None
            
            # Get intro text from phrase manager if available, otherwise generate new one
            intro_text = None
            if hasattr(generator, 'tts_phrase_manager') and generator.tts_phrase_manager and generator.tts_phrase_manager._generated:
                try:
                    phrase, audio_path, voice = generator.tts_phrase_manager.get_random_phrase_with_audio()
                    intro_text = phrase
                    print(f"   🎯 Using pre-generated phrase: '{intro_text}' (voice: {voice})")
                    
                    # Store the audio path for reuse
                    self._cached_audio_path = audio_path
                    self._cached_voice = voice
                except Exception as e:
                    print(f"   ⚠️  Failed to get pre-generated phrase: {e}")
            
            if not intro_text:
                # Fallback to original method
                print(f"   🔄 Generating new phrase...")
                context_messages = [
                    "cat videos",
                    "feline fun", 
                    "purr-fect moments",
                    "kitty compilation",
                    "cat content"
                ]
                context = random.choice(context_messages)
                intro_text = self.generate_intro_message(context)
                self._cached_audio_path = None
                self._cached_voice = None
            
            # Add TTS intro to the compilation
            final_result = self.add_tts_intro_to_video(
                temp_compilation, 
                output_path, 
                intro_text=intro_text
            )
            
            # Clean up temporary file
            if os.path.exists(temp_compilation):
                os.remove(temp_compilation)
            
            return final_result
            
        except Exception as e:
            print(f"❌ Error creating TTS compilation: {e}")
            return None


def main():
    """Interactive CLI for TTS Generator (model reused)"""
    import argparse
    import shlex
    print("\n🗣️  Interactive TTS Generator CLI (model is loaded once and reused)")
    print("Type 'help' for commands, 'exit' or 'quit' to leave.\n")

    # Initialize model ONCE
    try:
        generator = TTSGenerator()
    except Exception as e:
        print(f"❌ Error initializing TTSGenerator: {e}")
        return

    def print_help():
        print("""
Commands:
  tts --text "TEXT" [--output FILE] [--voice VOICE]
      Generate TTS audio from text.
  intro --video VIDEO --output FILE [--text "TEXT"] [--voice VOICE]
      Add TTS intro to a video (optionally specify intro text).
  help
      Show this help message.
  exit | quit
      Exit the CLI.
""")

    print_help()
    while True:
        try:
            inp = input("TTS> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not inp:
            continue
        if inp.lower() in ("exit", "quit"):
            print("Exiting.")
            break
        if inp.lower() == "help":
            print_help()
            continue
        # Parse command
        try:
            args = shlex.split(inp)
        except Exception as e:
            print(f"Parse error: {e}")
            continue
        if not args:
            continue
        cmd = args[0]
        cmd_args = args[1:]
        if cmd == "tts":
            import argparse as ap
            parser = ap.ArgumentParser(prog="tts", add_help=False)
            parser.add_argument("--text", required=True)
            parser.add_argument("--output", default="tts_out.wav")
            parser.add_argument("--voice", default=None)
            try:
                opts = parser.parse_args(cmd_args)
                result = generator.text_to_speech(opts.text, voice=opts.voice, output_path=opts.output)
                if result:
                    print(f"✅ TTS audio created: {result}")
                else:
                    print("❌ Failed to create TTS audio")
            except SystemExit:
                pass
            except Exception as e:
                print(f"❌ Error: {e}")
        elif cmd == "intro":
            import argparse as ap
            parser = ap.ArgumentParser(prog="intro", add_help=False)
            parser.add_argument("--video", required=True)
            parser.add_argument("--output", required=True)
            parser.add_argument("--text", default=None)
            parser.add_argument("--voice", default=None)
            try:
                opts = parser.parse_args(cmd_args)
                result = generator.add_tts_intro_to_video(opts.video, opts.output, intro_text=opts.text, voice=opts.voice)
                if result:
                    print(f"✅ TTS video created: {result}")
                else:
                    print("❌ Failed to create TTS video")
            except SystemExit:
                pass
            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")


if __name__ == "__main__":
    main() 