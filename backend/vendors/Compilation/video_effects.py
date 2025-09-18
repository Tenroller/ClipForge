#!/usr/bin/env python3
"""
Video Effects Utilities

Contains utility functions for applying visual effects to video clips,
including rounded corners, masking, and other transformations.
"""

import numpy as np
from moviepy import VideoClip, ImageClip
from PIL import Image, ImageDraw
import os
import tempfile


def create_rounded_rectangle_mask(size, radius):
    """
    Create a rounded rectangle mask image.
    
    Args:
        size: Tuple of (width, height) for the mask
        radius: Corner radius in pixels
        
    Returns:
        PIL Image object with the rounded rectangle mask
    """
    width, height = size
    
    # Create a new image with L mode (grayscale) for mask
    img = Image.new('L', (width, height), 0)  # Black background
    draw = ImageDraw.Draw(img)
    
    # Draw a rounded rectangle (filled with white for the mask)
    draw.rounded_rectangle(
        [(0, 0), (width-1, height-1)], 
        radius=radius, 
        fill=255  # White for mask
    )
    
    return img


def apply_rounded_corners(video_clip, corner_radius=30):
    """
    Apply rounded corners to a video clip.
    
    Args:
        video_clip: MoviePy VideoClip object
        corner_radius: Radius of the rounded corners in pixels
        
    Returns:
        VideoClip with rounded corners applied
    """
    # Get video dimensions
    width, height = video_clip.size
    
    # Create the rounded rectangle mask
    mask_img = create_rounded_rectangle_mask((width, height), corner_radius)
    
    # Save mask to temporary file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        mask_img.save(temp_file.name)
        temp_mask_path = temp_file.name
    
    try:
        # Create a mask clip from the image
        mask_clip = ImageClip(temp_mask_path, duration=video_clip.duration)
        
        # Convert the mask clip to a proper mask by making it grayscale
        def make_mask_frame(get_frame, t):
            frame = get_frame(t)
            # Convert to grayscale and normalize to 0-1 range
            if len(frame.shape) == 3:
                gray = np.dot(frame[...,:3], [0.2989, 0.5870, 0.1140])
            else:
                gray = frame
            return gray / 255.0
        
        mask_clip = mask_clip.transform(make_mask_frame)
        
        # Apply the mask to the video clip
        rounded_video = video_clip.with_mask(mask_clip)
        
        return rounded_video
        
    finally:
        # Clean up the temporary mask file
        try:
            os.unlink(temp_mask_path)
        except:
            pass


def apply_rounded_corners_simple(video_clip, corner_radius=30):
    """
    Simple implementation using frame transformation.
    Apply rounded corners to a video clip using direct frame manipulation.
    
    Args:
        video_clip: MoviePy VideoClip object
        corner_radius: Radius of the rounded corners in pixels
        
    Returns:
        VideoClip with rounded corners applied
    """
    width, height = video_clip.size
    
    # Pre-compute the mask
    mask_img = create_rounded_rectangle_mask((width, height), corner_radius)
    mask_array = np.array(mask_img) / 255.0  # Normalize to 0-1
    
    def apply_mask_to_frame(get_frame, t):
        frame = get_frame(t)
        
        # Apply mask to each channel
        if len(frame.shape) == 3:  # Color
            masked_frame = frame.copy().astype(float)
            for c in range(3):
                masked_frame[:, :, c] *= mask_array
            return masked_frame.astype(np.uint8)
        else:  # Grayscale
            return (frame.astype(float) * mask_array).astype(np.uint8)
    
    return video_clip.transform(apply_mask_to_frame)


def apply_rounded_corners_with_fade_edges(video_clip, corner_radius=30, fade_width=5):
    """
    Apply rounded corners with soft/anti-aliased edges for smoother appearance.
    
    Args:
        video_clip: MoviePy VideoClip object
        corner_radius: Radius of the rounded corners in pixels
        fade_width: Width of the fade/anti-aliasing effect in pixels
        
    Returns:
        VideoClip with rounded corners and soft edges
    """
    width, height = video_clip.size
    
    # Create a mask with anti-aliasing
    # We'll create a larger image and downsample for anti-aliasing effect
    scale_factor = 4
    large_width = width * scale_factor
    large_height = height * scale_factor
    large_radius = corner_radius * scale_factor
    
    # Create large mask
    large_img = Image.new('L', (large_width, large_height), 0)  # Grayscale, black background
    draw = ImageDraw.Draw(large_img)
    
    # Draw rounded rectangle
    draw.rounded_rectangle(
        [(0, 0), (large_width-1, large_height-1)], 
        radius=large_radius, 
        fill=255  # White fill
    )
    
    # Resize down for anti-aliasing effect
    mask_img = large_img.resize((width, height), Image.Resampling.LANCZOS)
    
    # Convert to numpy array for processing
    mask_array = np.array(mask_img) / 255.0
    
    def apply_mask_to_frame(get_frame, t):
        frame = get_frame(t)
        
        # Apply mask to each channel
        if len(frame.shape) == 3:  # Color
            masked_frame = frame.copy().astype(float)
            for c in range(3):
                masked_frame[:, :, c] *= mask_array
            return masked_frame.astype(np.uint8)
        else:  # Grayscale
            return (frame.astype(float) * mask_array).astype(np.uint8)
    
    return video_clip.transform(apply_mask_to_frame)