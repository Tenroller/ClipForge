#!/usr/bin/env python3
"""
TTS Phrase Manager

This module handles:
1. Batch generation of intro phrases at the start of video generation
2. Caching and reusing TTS audio files
3. Providing random phrases from the pre-generated pool
"""

import os
import sys
import random
import tempfile
import hashlib
import warnings
import soundfile as sf
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from kokoro import KPipeline
import torch
from loguru import logger

# Add project root to Python path for imports
_project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import OpenRouter client
try:
    from backend.utils.openrouter_client import generate_content as openrouter_generate_content
except ImportError:
    openrouter_generate_content = None

# Initialize logger for this module
logger = logger.bind(name="Compilation.tts_phrase_manager")


class TTSPhraseManager:
    """
    Centralized manager for TTS phrases and audio files.
    Generates phrases once and reuses them across all TTS compilations.
    """
    
    def __init__(self, api_key=None, num_phrases=20, cache_dir=None):
        """
        Initialize TTS Phrase Manager
        
        Args:
            api_key (str): OpenRouter API key
            num_phrases (int): Number of phrases to pre-generate
            cache_dir (str): Directory to cache audio files
        """
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable or pass api_key parameter.")
        
        self.num_phrases = num_phrases
        self.phrases = []
        self.audio_cache = {}  # phrase -> audio_file_path mapping
        self.voice_cache = {}  # phrase -> voice mapping
        
        # Setup cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(tempfile.gettempdir()) / "tts_phrase_cache"
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        
        # Set environment variable for the client
        os.environ['OPENROUTER_API_KEY'] = self.api_key
        
        # Initialize Kokoro TTS pipeline
        logger.info("Initializing Kokoro TTS pipeline for phrase manager...")
        
        # Suppress known warnings from the Kokoro model
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="torch.nn.modules.rnn")
            warnings.filterwarnings("ignore", category=FutureWarning, module="torch.nn.utils.weight_norm")
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
        
        # Add GPU detection
        self.has_gpu = torch.cuda.is_available()
        
        print(f"✅ TTS Phrase Manager initialized")
        print(f"   🎯 Will generate {self.num_phrases} phrases")
        print(f"   📁 Cache directory: {self.cache_dir}")
        print(f"   🎤 Available voices: {len(self.voices)}")
        
        self._generated = False  # Track if phrases have been generated
    
    def _get_lang_code_for_voice(self, voice):
        """Get the language code for a given voice"""
        if voice.startswith('b'):
            return 'b'
        return 'a'
    
    def _switch_language_if_needed(self, voice):
        """Switch TTS pipeline language if needed for the given voice"""
        required_lang_code = self._get_lang_code_for_voice(voice)
        if self.current_lang_code != required_lang_code:
            logger.debug(f"Switching TTS language from '{self.current_lang_code}' to '{required_lang_code}' for voice '{voice}'")
            self.tts_pipeline = KPipeline(lang_code=required_lang_code, repo_id='hexgrad/Kokoro-82M')
            self.current_lang_code = required_lang_code
    
    def _extract_clean_phrase(self, text):
        """Extract a clean intro phrase from potentially messy AI-generated text"""
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
    
    def generate_phrases(self, contexts=None):
        """
        Generate a batch of intro phrases
        
        Args:
            contexts (list): List of contexts for phrase generation
        """
        if self._generated:
            print(f"✅ Phrases already generated ({len(self.phrases)} available)")
            return
        
        print(f"\n🎙️ Generating {self.num_phrases} intro phrases...")
        
        if not contexts:
            contexts = [
                "cat videos",
                "feline fun",
                "purr-fect moments", 
                "kitty compilation",
                "cat content",
                "cute cats",
                "funny cats",
                "adorable kittens"
            ]
        
        # Enhanced fallback phrases in case AI generation fails
        fallback_phrases = [
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
            "Kitty chaos unleashed!",
            "Paws and claws compilation!",
            "Maximum meow mode activated!",
            "Fluffy friends await!",
            "Cat compilation incoming!",
            "Ready for feline greatness!",
            "Whisker wonderland ahead!"
        ]
        
        generated_count = 0
        
        # Try to generate phrases using AI
        for i in range(self.num_phrases):
            try:
                context = random.choice(contexts)
                
                # Improved prompt for better results
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

Generate ONE unique phrase now:"""
                
                response = openrouter_generate_content(
                    prompt=prompt,
                    model="openrouter/auto",
                    temperature=0.7,
                    max_tokens=50
                )
                
                raw_text = response.strip() if response else ""
                phrase = self._extract_clean_phrase(raw_text)
                
                # Validate and add phrase
                if phrase and phrase not in self.phrases and len(phrase) <= 50:
                    self.phrases.append(phrase)
                    generated_count += 1
                    if generated_count % 5 == 0:
                        print(f"   ✅ Generated {generated_count}/{self.num_phrases} phrases")
                else:
                    # Use fallback if generation failed
                    if fallback_phrases:
                        fallback = fallback_phrases.pop(0)
                        if fallback not in self.phrases:
                            self.phrases.append(fallback)
                            generated_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to generate phrase {i+1}: {e}")
                # Use fallback
                if fallback_phrases:
                    fallback = fallback_phrases.pop(0)
                    if fallback not in self.phrases:
                        self.phrases.append(fallback)
                        generated_count += 1
        
        # Fill any remaining slots with fallbacks
        while len(self.phrases) < self.num_phrases and fallback_phrases:
            fallback = fallback_phrases.pop(0)
            if fallback not in self.phrases:
                self.phrases.append(fallback)
        
        self._generated = True
        print(f"✅ Phrase generation complete: {len(self.phrases)} unique phrases ready")
        
        # Show some examples
        sample_phrases = random.sample(self.phrases, min(5, len(self.phrases)))
        print(f"   📝 Sample phrases: {sample_phrases}")
    
    def get_phrase_audio_path(self, phrase, voice=None):
        """
        Get cached audio path for a phrase, generating if needed
        
        Args:
            phrase (str): The phrase text
            voice (str): Voice to use (random if None)
            
        Returns:
            tuple: (audio_path, voice_used)
        """
        if not voice:
            voice = random.choice(self.voices)
        
        # Create cache key
        cache_key = hashlib.md5(f"{phrase}_{voice}".encode()).hexdigest()
        audio_path = self.cache_dir / f"tts_{cache_key}.wav"
        
        # Return cached file if exists
        if audio_path.exists():
            return str(audio_path), voice
        
        # Generate audio
        try:
            self._switch_language_if_needed(voice)
            
            # Generate audio using Kokoro
            generator = self.tts_pipeline(phrase, voice=voice)
            
            # Get the audio data from the generator
            audio_data = None
            for i, (gs, ps, audio) in enumerate(generator):
                audio_data = audio
                break  # Take the first (and usually only) result
            
            if audio_data is not None:
                # Save audio file
                sf.write(str(audio_path), audio_data, 24000)  # Kokoro uses 24kHz sample rate
                return str(audio_path), voice
            else:
                raise Exception("No audio data generated")
                
        except Exception as e:
            logger.error(f"Failed to generate TTS audio for '{phrase}' with voice '{voice}': {e}")
            return None, voice
    
    def get_random_phrase_with_audio(self):
        """
        Get a random phrase with its audio file
        
        Returns:
            tuple: (phrase, audio_path, voice) or (None, None, None) if failed
        """
        if not self._generated or not self.phrases:
            logger.error("Phrases not generated yet. Call generate_phrases() first.")
            return None, None, None
        
        phrase = random.choice(self.phrases)
        audio_path, voice = self.get_phrase_audio_path(phrase)
        
        if audio_path:
            return phrase, audio_path, voice
        else:
            return phrase, None, voice
    
    def cleanup_cache(self, max_age_hours=24):
        """
        Clean up old cache files
        
        Args:
            max_age_hours (int): Maximum age of cache files in hours
        """
        import time
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0
        
        for cache_file in self.cache_dir.glob("tts_*.wav"):
            try:
                if current_time - cache_file.stat().st_mtime > max_age_seconds:
                    cache_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to clean cache file {cache_file}: {e}")
        
        if cleaned_count > 0:
            print(f"🧹 Cleaned {cleaned_count} old TTS cache files")
    
    def get_stats(self):
        """Get statistics about the phrase manager"""
        return {
            'total_phrases': len(self.phrases),
            'generated': self._generated,
            'cache_dir': str(self.cache_dir),
            'cached_audio_files': len(list(self.cache_dir.glob("tts_*.wav")))
        }