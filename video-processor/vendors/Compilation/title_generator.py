#!/usr/bin/env python3
"""
Title Generator

This module handles:
1. Generating random catchy titles using OpenRouter API
2. Creating title overlays for videos
3. Following the same pattern as tts_generator.py for consistency
"""

import os
import sys
import random
import tempfile
import warnings
import torch
from pathlib import Path

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
    from backend.utils.openrouter_client import generate_content
except ImportError:
    # Fallback if import fails
    generate_content = None


class TitleGenerator:
    def __init__(self, api_key=None):
        """
        Initialize Title Generator
        
        Args:
            api_key (str): OpenRouter API key. If None, will try to get from environment.
        """
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable or pass api_key parameter.")
        
        # Set environment variable for the client
        os.environ['OPENROUTER_API_KEY'] = self.api_key
        
        print(f"✅ Title Generator initialized with OpenRouter API")
        
        # Add GPU detection
        self.has_gpu = torch.cuda.is_available()
    
    def generate_random_title(self, context="cat videos"):
        """
        Generate a random catchy title using OpenRouter API
        
        Args:
            context (str): Context for the title generation
            
        Returns:
            str: Generated title
        """
        if generate_content is None:
            return self._fallback_title()
            
        try:
            prompt = f"""You are a creative content creator who makes catchy, viral titles for {context} compilations. 
            Generate ONE short, engaging title phrase that would be perfect for TikTok/social media. 
            Keep it under 7 words and make it exciting and trending.
            Examples: "Cat Chaos Compilation", "Feline Frenzy", "Purrfect Moments", "Whisker Wonders", "Cat-tastic Compilation"
            Be creative but keep the energy high and the tone fun. Avoid generic phrases.
            IMPORTANT: Return only ONE title, not a list.
            
            Generate a catchy title for a cat video compilation."""
            
            response = generate_content(
                prompt=prompt,
                model=\"openrouter/auto\",
                temperature=0.9,
                max_tokens=45
            )
            
            title = response.strip() if response else ""
            # Clean up the title (remove quotes, extra punctuation)
            title = title.strip('"\'')
            
            # If multiple titles were returned, take the first one
            if '\n' in title or '*' in title:
                # Split by newlines or asterisks and take the first non-empty line
                lines = [line.strip().strip('*').strip() for line in title.split('\n') if line.strip().strip('*').strip()]
                if lines:
                    title = lines[0]
            
            if title:
                print(f"🎬 Generated title: '{title}'")
                return title
            else:
                return self._fallback_title()
            
        except Exception as e:
            print(f"⚠️ Error generating title with OpenRouter: {e}")
            return self._fallback_title()
    
    def _fallback_title(self):
        """Return a fallback title from predefined list"""
        fallback_titles = [
            "Cat Chaos Compilation",
            "Feline Frenzy",
            "Purrfect Moments",
            "Whisker Wonders",
            "Cat-tastic Compilation",
            "Furry Fun Times",
            "Meow Mix Magic",
            "Pawsome Compilation",
            "Cat Comedy Gold",
            "Feline Fiesta"
        ]
        title = random.choice(fallback_titles)
        print(f"🎬 Using fallback title: '{title}'")
        return title
    
    def generate_title_for_video(self, video_context="cat videos", style="trending"):
        """
        Generate a title specifically for video compilation
        
        Args:
            video_context (str): Context of the video content
            style (str): Style of title ("trending", "funny", "cute", "epic")
            
        Returns:
            str: Generated title
        """
        if generate_content is None:
            return self._fallback_styled_title(style)
            
        try:
            style_prompts = {
                "trending": "trending viral style",
                "funny": "humorous and witty style", 
                "cute": "adorable and heartwarming style",
                "epic": "dramatic and epic style"
            }
            
            style_prompt = style_prompts.get(style, "trending viral style")
            
            prompt = f"""You are a viral content creator who makes {style_prompt} titles for {video_context} compilations. 
            Generate ONE short, catchy title phrase that would trend on TikTok/social media. 
            Keep it under 8 words and make it exciting and engaging.
            Focus on {style} elements while keeping it fun and shareable.
            IMPORTANT: Return ONLY the title text, nothing else. No explanations, no lists, no formatting.
            
            Generate a {style} title for a {video_context} compilation."""
            
            response = generate_content(
                prompt=prompt,
                model=\"openrouter/auto\",
                temperature=0.8,
            )
            
            title = response.strip() if response else ""
            # Clean up the title (remove quotes, extra punctuation)
            title = title.strip('"\'')
            
            # If multiple titles were returned, take the first one
            if '\n' in title or '*' in title:
                # Split by newlines or asterisks and take the first non-empty line
                lines = [line.strip().strip('*').strip() for line in title.split('\n') if line.strip().strip('*').strip()]
                if lines:
                    title = lines[0]
            
            # Remove any remaining formatting or explanatory text
            if '**' in title:
                title = title.replace('**', '')
            if 'Okay, here are' in title or 'title options' in title:
                # Extract just the title part
                parts = title.split('**')
                if len(parts) > 1:
                    title = parts[1].strip()
                else:
                    # Fallback: take first meaningful line
                    lines = [line.strip() for line in title.split('\n') if line.strip() and not line.startswith('*') and not 'Okay' in line]
                    if lines:
                        title = lines[0]
            
            if title:
                print(f"🎬 Generated {style} title: '{title}'")
                return title
            else:
                return self._fallback_styled_title(style)
            
        except Exception as e:
            print(f"⚠️ Error generating {style} title with OpenRouter: {e}")
            return self._fallback_styled_title(style)
    
    def _fallback_styled_title(self, style):
        """Return a fallback title based on style"""
        fallback_titles = {
            "trending": ["Cat Chaos Compilation", "Feline Frenzy", "Purrfect Moments"],
            "funny": ["Cat Comedy Gold", "Feline Fails", "Whisker Woes"],
            "cute": ["Adorable Cats", "Purrfect Babies", "Furry Friends"],
            "epic": ["Epic Cat Moments", "Legendary Felines", "Cat Masterpiece"]
        }
        
        titles = fallback_titles.get(style, fallback_titles["trending"])
        title = random.choice(titles)
        print(f"🎬 Using fallback {style} title: '{title}'")
        return title