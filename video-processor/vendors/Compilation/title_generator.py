#!/usr/bin/env python3
"""
Title Generator

This module handles:
1. Generating random catchy titles using Gemini API
2. Creating title overlays for videos
3. Following the same pattern as tts_generator.py for consistency
"""

import os
import random
import tempfile
import warnings
from google import genai
from google.genai import types
import torch

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, environment variables must be set manually
    pass


class TitleGenerator:
    def __init__(self, api_key=None):
        """
        Initialize Title Generator
        
        Args:
            api_key (str): Google Gemini API key. If None, will try to get from environment.
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY environment variable or pass api_key parameter.")
        
        # Initialize Gemini client
        os.environ['GEMINI_API_KEY'] = self.api_key
        self.client = genai.Client()
        
        print(f"✅ Title Generator initialized with Gemini API")
        
        # Add GPU detection
        self.has_gpu = torch.cuda.is_available()
    
    def generate_random_title(self, context="cat videos"):
        """
        Generate a random catchy title using Gemini API
        
        Args:
            context (str): Context for the title generation
            
        Returns:
            str: Generated title
        """
        try:
            system_instruction = f"""You are a creative content creator who makes catchy, viral titles for {context} compilations. 
            Generate ONE short, engaging title phrase that would be perfect for TikTok/social media. 
            Keep it under 7 words and make it exciting and trending.
            Examples: "Cat Chaos Compilation", "Feline Frenzy", "Purrfect Moments", "Whisker Wonders", "Cat-tastic Compilation"
            Be creative but keep the energy high and the tone fun. Avoid generic phrases.
            IMPORTANT: Return only ONE title, not a list."""
            
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"{system_instruction}\n\nGenerate a catchy title for a cat video compilation.",
                config=types.GenerateContentConfig(
                    temperature=0.9,    
                    system_instruction=system_instruction,
                    max_output_tokens=45
                )
            )
            
            title = response.text.strip() if response.text else ""
            # Clean up the title (remove quotes, extra punctuation)
            title = title.strip('"\'')
            
            # If multiple titles were returned, take the first one
            if '\n' in title or '*' in title:
                # Split by newlines or asterisks and take the first non-empty line
                lines = [line.strip().strip('*').strip() for line in title.split('\n') if line.strip().strip('*').strip()]
                if lines:
                    title = lines[0]
            
            print(f"🎬 Generated title: '{title}'")
            return title
            
        except Exception as e:
            print(f"⚠️ Error generating title with Gemini: {e}")
            # Fallback to predefined titles
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
        try:
            style_prompts = {
                "trending": "trending viral style",
                "funny": "humorous and witty style", 
                "cute": "adorable and heartwarming style",
                "epic": "dramatic and epic style"
            }
            
            style_prompt = style_prompts.get(style, "trending viral style")
            
            system_instruction = f"""You are a viral content creator who makes {style_prompt} titles for {video_context} compilations. 
            Generate ONE short, catchy title phrase that would trend on TikTok/social media. 
            Keep it under 8 words and make it exciting and engaging.
            Focus on {style} elements while keeping it fun and shareable.
            IMPORTANT: Return ONLY the title text, nothing else. No explanations, no lists, no formatting."""
            
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"Generate a {style} title for a {video_context} compilation.",
                config=types.GenerateContentConfig(
                    temperature=0.8, 
                    system_instruction=system_instruction
                )
            )
            
            title = response.text.strip() if response.text else ""
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
            
            print(f"🎬 Generated {style} title: '{title}'")
            return title
            
        except Exception as e:
            print(f"⚠️ Error generating {style} title with Gemini: {e}")
            # Fallback to predefined titles based on style
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