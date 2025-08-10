# MoviePy 2.0 Complete Manual

**A comprehensive guide to MoviePy version 2.1.2 - The Pythonic Video Editing Library**

## Table of Contents

1. [Introduction](#introduction)
2. [Installation & Setup](#installation--setup)
3. [Quick Start Guide](#quick-start-guide)
4. [Core Concepts](#core-concepts)
5. [Loading Media](#loading-media)
6. [Clip Transformations](#clip-transformations)
7. [Effects System](#effects-system)
8. [Compositing & Layering](#compositing--layering)
9. [Rendering & Export](#rendering--export)
10. [Complete API Reference](#complete-api-reference)
11. [Practical Examples](#practical-examples)
12. [Migration from v1.x](#migration-from-v1x)
13. [Troubleshooting](#troubleshooting)
14. [Resources & Community](#resources--community)

---

## Introduction

MoviePy is a Python library for video editing: cutting, concatenations, title insertions, video compositing (also known as non-linear editing), video processing, and creation of custom effects.

### Key Features

- **Simple and Intuitive**: Basic operations can be accomplished in single lines of code
- **Flexible**: Full control over frames and audio samples through NumPy arrays
- **Portable**: Cross-platform compatibility (Windows, macOS, Linux)
- **Pythonic**: Integrates seamlessly with the Python ecosystem

### Design Principles (v2.0)

1. **Immutability**: All transformations return new clip objects (functional programming style)
2. **Method Chaining**: Natural workflow through chainable methods
3. **Type Safety**: Clear distinction between video and audio operations
4. **Effect Classes**: Organized, reusable effect system

### Architecture Overview

```
MoviePy Architecture:
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Python Code   │ -> │   MoviePy    │ -> │    FFmpeg       │
│   (High-level)  │    │  (Wrapper)   │    │  (Backend)      │
└─────────────────┘    └──────────────┘    └─────────────────┘
                              │
                       ┌──────────────┐
                       │    NumPy     │
                       │  (Arrays)    │
                       └──────────────┘
```

---

## Installation & Setup

### Standard Installation

```bash
pip install moviepy
```

This installs MoviePy 2.1.2 and core dependencies:
- `numpy` - Array processing
- `imageio` - Media I/O
- `decorator` - Function decorators
- `proglog` - Progress logging

### FFmpeg Dependency

MoviePy automatically handles FFmpeg installation:
- On first use, `imageio` downloads appropriate FFmpeg binary
- For manual installation: [FFmpeg Official Site](https://ffmpeg.org/download.html)

### Verification

```python
import moviepy
print(f"MoviePy version: {moviepy.__version__}")
# Should output: MoviePy version: 2.1.2
```

---

## Quick Start Guide

### 10-Second Example

```python
from moviepy import VideoFileClip

# Load, trim, and save a video
video = VideoFileClip("input.mp4")
clip = video.subclipped(10, 20)  # Extract 10-second segment
clip.write_videofile("output.mp4")
```

### Basic Workflow

```python
from moviepy import VideoFileClip, TextClip, CompositeVideoClip

# 1. Load media
video = VideoFileClip("vacation.mp4")

# 2. Create text overlay
title = TextClip(
    text="My Vacation",
    font="Arial.ttf",
    font_size=50,
    color='white'
).with_duration(5).with_position('center')

# 3. Compose layers
final = CompositeVideoClip([video, title])

# 4. Export
final.write_videofile("vacation_with_title.mp4")
```

---

## Core Concepts

### The Clip Object

Everything in MoviePy is a **Clip** - an abstract representation of media with these key attributes:

```python
clip.duration    # Duration in seconds (float)
clip.start       # Start time in composition (float)
clip.end         # End time in composition (float)
clip.fps         # Frames per second (VideoClip only)
clip.size        # (width, height) tuple (VideoClip only)
clip.audio       # Associated AudioClip (VideoClip only)
```

### Clip Types

#### VideoClip Family
- `VideoClip` - Base class for visual media
- `VideoFileClip` - Video from file
- `ImageClip` - Video from static image
- `TextClip` - Video from rendered text
- `ColorClip` - Video of solid color
- `CompositeVideoClip` - Layered composition

#### AudioClip Family
- `AudioClip` - Base class for audio media
- `AudioFileClip` - Audio from file
- `CompositeAudioClip` - Mixed audio composition

### Immutability Principle

```python
# ❌ v1.x style (mutating)
clip.set_duration(10)

# ✅ v2.0 style (immutable)
new_clip = clip.with_duration(10)

# ✅ Method chaining
final_clip = (clip
    .with_duration(10)
    .with_position('center')
    .resized(width=720))
```

---

## Loading Media

### From Video Files

```python
from moviepy import VideoFileClip

# Basic loading
video = VideoFileClip("movie.mp4")

# With options
video = VideoFileClip(
    "movie.mp4",
    decode_file=True,    # Decode to RAM (faster processing)
    has_mask=False       # No transparency mask
)

# Audio-only from video file
audio = video.audio
```

**Supported formats**: MP4, AVI, MOV, MKV, WebM, and all FFmpeg-supported formats

### From Audio Files

```python
from moviepy import AudioFileClip

# Load audio
music = AudioFileClip("soundtrack.mp3")
voice = AudioFileClip("narration.wav")

# Extract audio segment
intro_music = music.subclipped(0, 30)  # First 30 seconds
```

**Supported formats**: MP3, WAV, AAC, FLAC, OGG, and all FFmpeg-supported formats

### From Images

```python
from moviepy import ImageClip, ImageSequenceClip

# Single image as video
logo = ImageClip("logo.png").with_duration(5)

# Image sequence (animation)
frames = ["frame001.png", "frame002.png", "frame003.png"]
animation = ImageSequenceClip(frames, fps=24)

# From NumPy array
import numpy as np
array = np.random.rand(480, 640, 3) * 255  # Random image
clip = ImageClip(array, duration=3)
```

### Generated Content

#### Text Clips

```python
from moviepy import TextClip

text = TextClip(
    text="Hello, World!",
    font="Arial.ttf",           # Required in v2.0
    font_size=50,
    color='white',
    bg_color='black',           # Background color
    stroke_color='red',         # Outline color
    stroke_width=2              # Outline width
).with_duration(5)
```

#### Color Clips

```python
from moviepy import ColorClip

# Solid color background
background = ColorClip(
    size=(1920, 1080),
    color=(255, 0, 0),    # Red in RGB
    duration=10
)
```

---

## Clip Transformations

### Temporal Transformations

#### Time-based Operations

```python
# Extract segments
clip.subclipped(start, end)           # Extract time range
clip.subclipped(10, 30)               # Seconds 10-30
clip.subclipped("00:01:30", "00:02:45")  # HH:MM:SS format

# Timeline positioning
clip.with_start(5)                    # Start at 5 seconds
clip.with_end(15)                     # End at 15 seconds
clip.with_duration(10)                # Set duration to 10 seconds

# Cut out sections
clip.with_section_cut_out(5, 8)      # Remove seconds 5-8
```

#### Speed Control

```python
# Change playback speed
fast_clip = clip.with_speed_scaled(2.0)    # 2x speed (fast-forward)
slow_clip = clip.with_speed_scaled(0.5)    # 0.5x speed (slow motion)

# Using effects
from moviepy import vfx
speed_effect = clip.with_effects([vfx.MultiplySpeed(1.5)])
```

### Spatial Transformations

#### Resizing

```python
# Resize methods
clip.resized(width=720)               # Maintain aspect ratio
clip.resized(height=480)              # Maintain aspect ratio
clip.resized((640, 480))              # Exact dimensions
clip.resized(0.5)                     # Scale by factor
```

#### Cropping

```python
# Crop to region (x1, y1, x2, y2)
clip.cropped(100, 50, 500, 400)      # Rectangle coordinates

# Center crop to aspect ratio
def center_crop(clip, aspect_ratio):
    w, h = clip.size
    if w/h > aspect_ratio:
        # Too wide, crop width
        new_w = int(h * aspect_ratio)
        x1 = (w - new_w) // 2
        return clip.cropped(x1, 0, x1 + new_w, h)
    else:
        # Too tall, crop height
        new_h = int(w / aspect_ratio)
        y1 = (h - new_h) // 2
        return clip.cropped(0, y1, w, y1 + new_h)

# Usage
square_clip = center_crop(clip, 1.0)  # 1:1 aspect ratio
```

#### Rotation and Mirroring

```python
# Rotation
clip.rotated(90)                      # 90 degrees counterclockwise

# Mirroring with effects
from moviepy import vfx
mirrored_x = clip.with_effects([vfx.MirrorX()])  # Flip horizontally
mirrored_y = clip.with_effects([vfx.MirrorY()])  # Flip vertically
```

### Positioning in Compositions

```python
# Position methods
clip.with_position('center')          # Center of frame
clip.with_position('left')            # Left side
clip.with_position('right')           # Right side
clip.with_position('top')             # Top
clip.with_position('bottom')          # Bottom

# Precise positioning
clip.with_position((50, 100))         # Pixel coordinates (x, y)
clip.with_position(('left', 'top'))   # Corner positioning
clip.with_position(('center', 200))   # Centered horizontally, 200px from top

# Moving position
clip.with_position(lambda t: (100 + 50*t, 200))  # Dynamic positioning
```

### Audio Transformations

```python
# Volume control
clip.with_volume_scaled(0.5)          # Half volume
clip.with_volume_scaled(2.0)          # Double volume

# Audio replacement
new_clip = clip.with_audio(new_audio) # Replace audio track
silent_clip = clip.without_audio()    # Remove audio

# Audio effects
from moviepy import afx
quiet_clip = clip.with_effects([afx.MultiplyVolume(0.3)])
```

---

## Effects System

### Using Effects

MoviePy v2.0 uses a class-based effects system accessed via `with_effects()`:

```python
from moviepy import vfx, afx

# Apply single effect
clip_with_fade = clip.with_effects([vfx.FadeIn(1.0)])

# Apply multiple effects
enhanced_clip = clip.with_effects([
    vfx.FadeIn(1.0),           # 1-second fade in
    vfx.FadeOut(1.0),          # 1-second fade out
    vfx.Resize(width=720),     # Resize to 720p width
    afx.AudioFadeIn(0.5)       # 0.5-second audio fade in
])

# Apply to specific time range
clip.with_effects_on_subclip([vfx.BlackAndWhite()], 5, 10)
```

### Video Effects (vfx)

#### Fade Effects

```python
from moviepy import vfx

# Fade to/from black
vfx.FadeIn(duration)          # Fade from black
vfx.FadeOut(duration)         # Fade to black

# Fade to/from transparent (for overlays)
vfx.CrossFadeIn(duration)     # Fade from transparent
vfx.CrossFadeOut(duration)    # Fade to transparent

# Example usage
intro = clip.with_effects([
    vfx.FadeIn(2),            # 2-second fade in
    vfx.FadeOut(1)            # 1-second fade out
])
```

#### Color Effects

```python
# Black and white
vfx.BlackAndWhite()

# Color inversion
vfx.InvertColors()

# Color multiplication (brightness/tint)
vfx.MultiplyColor(factor)     # Factor > 1 = brighter, < 1 = darker

# Gamma correction
vfx.GammaCorrection(gamma)    # Gamma > 1 = darker, < 1 = brighter

# Example: Vintage look
vintage = clip.with_effects([
    vfx.GammaCorrection(1.2),
    vfx.MultiplyColor(0.8)
])
```

#### Motion Effects

```python
# Speed control
vfx.MultiplySpeed(factor)     # 2.0 = double speed, 0.5 = half speed

# Acceleration/deceleration
vfx.AccelDecel(start_speed, end_speed)

# Time mirroring
vfx.TimeMirror()              # Play backwards
vfx.TimeSymmetrize()          # Play forward then backward

# Freeze effects
vfx.Freeze(t, freeze_duration)    # Freeze at time t
```

#### Transform Effects

```python
# Geometric transformations
vfx.Resize(width=None, height=None)
vfx.Crop(x1, y1, x2, y2)
vfx.Rotate(angle, center=None, expand=True)
vfx.MirrorX()                 # Horizontal flip
vfx.MirrorY()                 # Vertical flip

# Margins and borders
vfx.Margin(mar=None, left=0, right=0, top=0, bottom=0, color=(0,0,0))

# Example: Create frame border
framed = clip.with_effects([
    vfx.Margin(10, color=(255, 255, 255))  # 10px white border
])
```

### Audio Effects (afx)

```python
from moviepy import afx

# Volume effects
afx.MultiplyVolume(factor)               # Volume multiplication
afx.MultiplyStereoVolume(left, right)    # Separate L/R control
afx.AudioNormalize()                     # Normalize to 0dB

# Fade effects
afx.AudioFadeIn(duration)                # Audio fade in
afx.AudioFadeOut(duration)               # Audio fade out

# Creative effects
afx.AudioLoop(n_loops=None, duration=None)  # Loop audio
afx.AudioDelay(delay, n_repeat, decay)   # Echo/delay effect

# Example: Audio processing
processed_audio = clip.with_effects([
    afx.AudioNormalize(),                # Normalize first
    afx.AudioFadeIn(1),                  # 1-second fade in
    afx.AudioFadeOut(2),                 # 2-second fade out
    afx.MultiplyVolume(0.8)              # Reduce to 80% volume
])
```

---

## Compositing & Layering

### Sequential Composition (Concatenation)

Join clips end-to-end in sequence:

```python
from moviepy import concatenate_videoclips, concatenate_audioclips

# Basic concatenation
clips = [clip1, clip2, clip3]
final_video = concatenate_videoclips(clips)

# Handle different sizes
final_video = concatenate_videoclips(clips, method="compose")

# Audio concatenation
audio_clips = [audio1, audio2, audio3]
final_audio = concatenate_audioclips(audio_clips)
```

### Parallel Composition (Layering)

Overlay clips on top of each other:

```python
from moviepy import CompositeVideoClip

# Basic layering (later clips appear on top)
composite = CompositeVideoClip([
    background_video,    # Base layer
    logo.with_position(('right', 'top')),     # Logo overlay
    title.with_position(('center', 'bottom')) # Title overlay
])

# Complex positioning
composite = CompositeVideoClip([
    background,
    watermark.with_position((50, 50)),              # Absolute position
    title.with_position('center').with_start(2),    # Delayed start
    credits.with_position('bottom').with_start(10)  # End credits
])
```

### Grid Layouts

Arrange clips in a grid pattern:

```python
from moviepy import clips_array

# 2x2 grid
grid = clips_array([
    [clip1, clip2],
    [clip3, clip4]
])

# 1x3 horizontal strip
strip = clips_array([[clip1, clip2, clip3]])

# 3x1 vertical strip
column = clips_array([
    [clip1],
    [clip2],
    [clip3]
])
```

### Picture-in-Picture

```python
def create_pip(main_video, pip_video, position='top-right', scale=0.25):
    """Create picture-in-picture effect"""
    
    # Scale the PiP video
    pip_scaled = pip_video.resized(scale)
    
    # Position calculation
    main_w, main_h = main_video.size
    pip_w, pip_h = pip_scaled.size
    
    positions = {
        'top-left': (20, 20),
        'top-right': (main_w - pip_w - 20, 20),
        'bottom-left': (20, main_h - pip_h - 20),
        'bottom-right': (main_w - pip_w - 20, main_h - pip_h - 20)
    }
    
    pip_positioned = pip_scaled.with_position(positions[position])
    
    return CompositeVideoClip([main_video, pip_positioned])

# Usage
pip_video = create_pip(main_clip, webcam_clip, 'bottom-right', 0.3)
```

---

## Rendering & Export

### Basic Export

```python
# Basic video export
clip.write_videofile("output.mp4")

# With parameters
clip.write_videofile(
    "output.mp4",
    fps=30,                    # Frame rate
    codec='libx264',           # Video codec
    audio_codec='aac',         # Audio codec
    bitrate='5000k',           # Video bitrate
    preset='medium'            # Encoding speed/quality
)
```

### Export Parameters Reference

| Parameter | Type | Description | Common Values |
|-----------|------|-------------|---------------|
| `filename` | str | Output file path | `"output.mp4"`, `"video.webm"` |
| `fps` | int/float | Frames per second | `24`, `30`, `60` |
| `codec` | str | Video codec | `'libx264'`, `'libx265'`, `'mpeg4'` |
| `audio_codec` | str | Audio codec | `'aac'`, `'libmp3lame'`, `'libvorbis'` |
| `bitrate` | str | Video bitrate | `'1000k'`, `'5000k'`, `'10M'` |
| `preset` | str | Encoding preset | `'ultrafast'`, `'medium'`, `'slow'` |

### Quality Presets

```python
# High quality (large file)
clip.write_videofile(
    "high_quality.mp4",
    codec='libx264',
    bitrate='10000k',
    preset='slow',
    audio_bitrate='320k'
)

# Web optimized
clip.write_videofile(
    "web_optimized.mp4",
    codec='libx264',
    bitrate='2000k',
    preset='medium',
    audio_bitrate='128k'
)

# Small file size
clip.write_videofile(
    "compressed.mp4",
    codec='libx264',
    bitrate='500k',
    preset='fast',
    audio_bitrate='64k'
)
```

### Specialized Export Formats

#### Animated GIFs

```python
# Basic GIF
clip.write_gif("animation.gif", fps=15)

# Optimized GIF
clip.write_gif(
    "optimized.gif",
    fps=12,
    opt='OptimizePlus',        # Optimization level
    fuzz=2                     # Color reduction
)
```

#### Image Sequences

```python
# Export as image sequence
clip.write_images_sequence("frames/frame_%04d.png", fps=24)

# JPEG sequence (smaller files)
clip.write_images_sequence("frames/frame_%04d.jpg", fps=24)
```

#### Audio Only

```python
# Export audio track
clip.write_audiofile("soundtrack.mp3")

# High quality audio
clip.write_audiofile(
    "audio_hq.wav",
    codec='pcm_s24le',         # 24-bit PCM
    bitrate='1411k'            # CD quality
)
```

### Preview and Testing

```python
# Preview in window (requires ffplay)
clip.preview(fps=24)

# Preview specific segment
clip.subclipped(10, 20).preview(fps=15)

# Preview resized (for performance)
clip.resized(0.5).preview(fps=24)

# Save preview frame
frame = clip.get_frame(10)  # Frame at 10 seconds
from PIL import Image
Image.fromarray(frame).save("preview_frame.jpg")
```

---

## Complete API Reference

### Core Classes

#### VideoFileClip

Load video from file.

```python
VideoFileClip(filename, decode_file=True, has_mask=False, ...)
```

**Key Methods:**
- `subclipped(start, end)` - Extract time segment
- `resized(width, height)` - Resize video
- `cropped(x1, y1, x2, y2)` - Crop to rectangle
- `rotated(angle)` - Rotate by angle
- `with_duration(duration)` - Set duration
- `with_start(time)` - Set start time
- `with_position(pos)` - Set position in composition
- `with_effects(effects_list)` - Apply effects
- `write_videofile(filename, ...)` - Export video

#### AudioFileClip

Load audio from file.

```python
AudioFileClip(filename, decode_file=True, buffersize=200000, ...)
```

#### TextClip

Generate video from text.

```python
TextClip(font, text, font_size=16, color='black', bg_color=None, ...)
```

**Required Parameters:**
- `font` - Path to font file (.ttf, .otf)
- `text` - Text content

#### ImageClip

Create video from image.

```python
ImageClip(img, is_mask=False, transparent=False, ...)
```

#### ColorClip

Generate solid color video.

```python
ColorClip(size, color, is_mask=False, duration=None)
```

#### CompositeVideoClip

Layer multiple clips.

```python
CompositeVideoClip(clips, size=None, bg_color=None, ...)
```

### Utility Functions

#### concatenate_videoclips

Join clips sequentially.

```python
concatenate_videoclips(clips, method='chain', transition=None)
```

#### concatenate_audioclips

Join audio clips sequentially.

```python
concatenate_audioclips(clips)
```

#### clips_array

Arrange clips in grid.

```python
clips_array(array, rows_widths=None, cols_widths=None, bg_color=None)
```

#### convert_to_seconds

Convert time to seconds.

```python
convert_to_seconds(time)
```

**Accepts:**
- Numbers (seconds): `30`, `45.5`
- Tuples (min, sec): `(1, 30)`
- Strings: `"01:30"`, `"00:01:30.500"`

### Complete Method Reference

#### VideoClip Methods (18 with_* methods)

```python
# Temporal control
.with_duration(duration)              # Set clip duration
.with_start(time)                    # Set start time in composition
.with_end(time)                      # Set end time in composition
.with_section_cut_out(start, end)    # Remove time section
.with_speed_scaled(factor)           # Change playback speed

# Spatial control
.with_position(pos)                  # Set position in composition
.with_layer_index(index)             # Set layering order

# Visual properties
.with_opacity(opacity)               # Set transparency (0-1)
.with_mask(mask)                     # Apply transparency mask
.with_background_color(color)        # Set background color

# Audio control
.with_audio(audio_clip)              # Set audio track
.with_volume_scaled(factor)          # Adjust volume

# Effects and processing
.with_effects(effects_list)          # Apply list of effects
.with_effects_on_subclip(effects, start, end)  # Apply effects to time range
.with_updated_frame_function(func)   # Custom frame processing

# Technical
.with_fps(fps)                       # Set frame rate
.with_is_mask(value)                 # Set as mask
.with_memoize(value)                 # Enable/disable caching
```

#### Transformation Methods (4 *ed methods)

```python
.subclipped(start, end)              # Extract time segment
.resized(width, height)              # Resize dimensions
.cropped(x1, y1, x2, y2)            # Crop to rectangle
.rotated(angle)                      # Rotate by angle
```

#### Export Methods (3 write_* methods)

```python
.write_videofile(filename, ...)      # Export as video
.write_gif(filename, ...)            # Export as animated GIF
.write_images_sequence(pattern, ...) # Export as image sequence
```

### Video Effects Reference

#### Fade Effects
- `vfx.FadeIn(duration)` - Fade from black
- `vfx.FadeOut(duration)` - Fade to black
- `vfx.CrossFadeIn(duration)` - Fade from transparent
- `vfx.CrossFadeOut(duration)` - Fade to transparent

#### Color Effects
- `vfx.BlackAndWhite()` - Convert to grayscale
- `vfx.InvertColors()` - Invert colors
- `vfx.MultiplyColor(factor)` - Adjust brightness/tint
- `vfx.GammaCorrection(gamma)` - Gamma correction

#### Motion Effects
- `vfx.MultiplySpeed(factor)` - Change playback speed
- `vfx.AccelDecel(start_speed, end_speed)` - Speed ramping
- `vfx.TimeMirror()` - Play backwards
- `vfx.TimeSymmetrize()` - Play forward then backward

#### Transform Effects
- `vfx.Resize(width, height)` - Resize video
- `vfx.Crop(x1, y1, x2, y2)` - Crop video
- `vfx.Rotate(angle, center, expand)` - Rotate video
- `vfx.MirrorX()` - Flip horizontally
- `vfx.MirrorY()` - Flip vertically
- `vfx.Margin(margin, color)` - Add border

#### Creative Effects
- `vfx.Blink(on_duration, off_duration)` - Blinking effect
- `vfx.Painting()` - Artistic painting filter
- `vfx.HeadBlur(fx, fy)` - Motion blur
- `vfx.SuperSample(n_frames, d)` - Anti-aliasing
- `vfx.Loop(duration)` - Loop clip
- `vfx.MakeLoopable(cross_duration)` - Seamless loop

#### Animation Effects
- `vfx.SlideIn(duration, side)` - Slide in from edge
- `vfx.SlideOut(duration, side)` - Slide out to edge
- `vfx.Scroll(w, h, x_speed, y_speed)` - Scrolling effect

#### Technical Effects
- `vfx.EvenSize()` - Ensure even dimensions
- `vfx.Freeze(t, freeze_duration)` - Freeze frame
- `vfx.FreezeRegion(region, t, freeze_duration)` - Freeze region

### Audio Effects Reference

#### Volume Effects
- `afx.MultiplyVolume(factor)` - Volume multiplication
- `afx.MultiplyStereoVolume(left, right)` - Stereo volume control
- `afx.AudioNormalize()` - Normalize to 0dB

#### Fade Effects
- `afx.AudioFadeIn(duration)` - Audio fade in
- `afx.AudioFadeOut(duration)` - Audio fade out

#### Creative Effects
- `afx.AudioLoop(n_loops, duration)` - Loop audio
- `afx.AudioDelay(delay, n_repeat, decay)` - Echo/delay effect

---

## Practical Examples

### Example 1: Create a Slideshow

```python
from moviepy import *
import json

def create_slideshow(images, output_file):
    """Create a slideshow from a list of images"""
    
    segments = []
    slide_duration = 4
    transition_duration = 1
    
    for i, image_path in enumerate(images):
        # Create image clip
        img_clip = (ImageClip(image_path)
                   .with_duration(slide_duration)
                   .resized(height=720))
        
        # Add fade transition
        if i == 0:
            img_clip = img_clip.with_effects([vfx.FadeIn(transition_duration)])
        if i == len(images) - 1:
            img_clip = img_clip.with_effects([vfx.FadeOut(transition_duration)])
        
        segments.append(img_clip)
    
    # Concatenate with crossfade
    final = concatenate_videoclips(segments, method="compose")
    
    # Export
    final.write_videofile(output_file, fps=24)
    return final

# Usage
images = ['photo1.jpg', 'photo2.jpg', 'photo3.jpg']
slideshow = create_slideshow(images, 'my_slideshow.mp4')
```

### Example 2: Add Watermark

```python
def add_watermark(video_path, watermark_path, output_path):
    """Add a watermark to a video"""
    
    # Load video and watermark
    video = VideoFileClip(video_path)
    watermark = (ImageClip(watermark_path)
                .with_duration(video.duration)
                .resized(height=50)  # 50px height
                .with_opacity(0.7)   # 70% opacity
                .with_position(('right', 'bottom')))
    
    # Compose and export
    final = CompositeVideoClip([video, watermark])
    final.write_videofile(output_path)
    
    return final

# Usage
watermarked = add_watermark('input.mp4', 'logo.png', 'output.mp4')
```

### Example 3: Picture-in-Picture

```python
def create_pip(main_path, pip_path, output_path):
    """Create picture-in-picture video"""
    
    # Load videos
    main = VideoFileClip(main_path)
    pip_video = VideoFileClip(pip_path)
    
    # Resize and position PiP
    pip_resized = (pip_video
                  .resized(0.25)  # 25% of original size
                  .with_position(('right', 'top'))
                  .with_start(5)  # Start after 5 seconds
                  .with_duration(10))  # Show for 10 seconds
    
    # Add border to PiP
    pip_with_border = pip_resized.with_effects([
        vfx.Margin(2, color=(255, 255, 255))
    ])
    
    # Compose and export
    result = CompositeVideoClip([main, pip_with_border])
    result.write_videofile(output_path)
    
    return result

# Usage
pip_result = create_pip('main.mp4', 'webcam.mp4', 'pip_output.mp4')
```

### Example 4: Batch Processing

```python
import os
from pathlib import Path

def batch_process(input_dir, output_dir, process_func):
    """Batch process videos in a directory"""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    for video_file in input_path.glob("*.mp4"):
        print(f"Processing {video_file.name}...")
        
        try:
            # Load and process
            clip = VideoFileClip(str(video_file))
            processed = process_func(clip)
            
            # Save with same name
            output_file = output_path / video_file.name
            processed.write_videofile(str(output_file))
            
            # Cleanup
            clip.close()
            processed.close()
            
        except Exception as e:
            print(f"Error processing {video_file.name}: {e}")

# Example processing function
def add_intro(clip):
    """Add a 3-second intro title"""
    intro = (TextClip(
        text="My Video",
        font="Arial.ttf",
        font_size=60,
        color='white'
    ).with_duration(3)
     .with_background_color('black')
     .with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)]))
    
    return concatenate_videoclips([intro, clip])

# Process all videos
batch_process("input_videos/", "output_videos/", add_intro)
```

---

## Migration from v1.x

### Key Breaking Changes Summary

| v1.x | v2.0 | Notes |
|------|------|-------|
| `from moviepy.editor import *` | `from moviepy import *` | New import style |
| `clip.set_duration(10)` | `clip.with_duration(10)` | Immutable operations |
| `clip.subclip(0, 10)` | `clip.subclipped(0, 10)` | Past participle naming |
| `clip.resize(0.5)` | `clip.resized(0.5)` | Past participle naming |
| `clip.fx(vfx.fadein, 1)` | `clip.with_effects([vfx.FadeIn(1)])` | Class-based effects |
| `TextClip("Hello")` | `TextClip(text="Hello", font="font.ttf")` | Font required |

### Migration Steps

1. **Update imports**:
   ```python
   # Old
   from moviepy.editor import VideoFileClip, TextClip
   
   # New
   from moviepy import VideoFileClip, TextClip
   ```

2. **Convert set_* methods to with_* methods**:
   ```python
   # Old
   clip.set_duration(10).set_start(5)
   
   # New
   clip.with_duration(10).with_start(5)
   ```

3. **Update transformation methods**:
   ```python
   # Old
   clip.subclip(0, 10).resize(0.5)
   
   # New
   clip.subclipped(0, 10).resized(0.5)
   ```

4. **Convert fx() calls to with_effects()**:
   ```python
   # Old
   clip.fx(vfx.fadein, 1).fx(vfx.resize, 0.5)
   
   # New
   clip.with_effects([vfx.FadeIn(1), vfx.Resize(0.5)])
   ```

5. **Update TextClip usage**:
   ```python
   # Old
   TextClip("Hello World", fontsize=50)
   
   # New
   TextClip(text="Hello World", font="arial.ttf", font_size=50)
   ```

---

## Troubleshooting

### Common Issues and Solutions

#### Installation Issues

**Problem**: `pip install moviepy` fails
**Solution**: Update pip first: `pip install --upgrade pip`

**Problem**: FFmpeg not found
**Solution**: Let imageio download FFmpeg automatically on first use, or install manually from [ffmpeg.org](https://ffmpeg.org)

#### Runtime Issues

**Problem**: Video dimensions are odd, causing codec issues
```
[libx264 @ 0x...] width or height not divisible by 2
```

**Solution**:
```python
# Use EvenSize effect
from moviepy import vfx
clip = clip.with_effects([vfx.EvenSize()])
```

**Problem**: TextClip fails in v2.0
**Solution**: Always provide font file path:
```python
text = TextClip(
    text="Hello World",
    font="C:/Windows/Fonts/arial.ttf",  # Windows
    font_size=50,
    color='white'
)
```

**Problem**: Memory errors with large videos
**Solution**: Process in segments or at lower resolution:
```python
# Lower resolution during processing
low_res = clip.resized(0.5)
processed = apply_effects(low_res)
final = processed.resized(clip.size)
```

**Problem**: Slow preview/rendering
**Solution**: 
```python
# Lower preview fps
clip.preview(fps=15)

# Preview at lower resolution
clip.resized(0.5).preview(fps=24)

# Use more CPU threads
clip.write_videofile("output.mp4", threads=8)
```

### Performance Tips

```python
# Close clips when done
clip = VideoFileClip("video.mp4")
# ... process clip ...
clip.close()

# Use context managers
with VideoFileClip("video.mp4") as clip:
    processed = clip.with_effects([vfx.FadeIn(1)])
    processed.write_videofile("output.mp4")

# Optimize rendering
clip.write_videofile(
    "output.mp4",
    preset='fast',        # Faster encoding
    threads=8,           # Use multiple cores
    bitrate='2000k'      # Reasonable bitrate
)
```

---

## Resources & Community

### Official Resources

- **GitHub Repository**: [https://github.com/Zulko/moviepy](https://github.com/Zulko/moviepy)
- **Documentation**: [https://moviepy.readthedocs.io/](https://moviepy.readthedocs.io/)
- **PyPI Package**: [https://pypi.org/project/moviepy/](https://pypi.org/project/moviepy/)

### Community

- **Reddit**: [r/MoviePy](https://www.reddit.com/r/MoviePy/) - Questions, examples, discussions
- **Stack Overflow**: Tag `moviepy` for technical questions
- **GitHub Issues**: Bug reports and feature requests

### Related Tools

- **FFmpeg**: [https://ffmpeg.org/](https://ffmpeg.org/) - Underlying media processing
- **OpenCV**: [https://opencv.org/](https://opencv.org/) - Computer vision integration
- **Pillow**: [https://pillow.readthedocs.io/](https://pillow.readthedocs.io/) - Image processing
- **NumPy**: [https://numpy.org/](https://numpy.org/) - Array operations

### Font Resources

For TextClip usage, you'll need font files:

**Free Font Sources**:
- **Google Fonts**: [https://fonts.google.com/](https://fonts.google.com/)
- **Font Squirrel**: [https://www.fontsquirrel.com/](https://www.fontsquirrel.com/)

**System Font Locations**:
- Windows: `C:/Windows/Fonts/`
- macOS: `/System/Library/Fonts/`, `/Library/Fonts/`
- Linux: `/usr/share/fonts/`, `~/.fonts/`

### Contributing

MoviePy welcomes contributions! See the [Contributing Guidelines](https://github.com/Zulko/moviepy/blob/main/CONTRIBUTING.md) for details.

### License

MoviePy is released under the MIT License, making it suitable for both personal and commercial projects.

---

## Conclusion

MoviePy 2.0 represents a mature, powerful library for programmatic video editing in Python. Its immutable design, comprehensive effects system, and seamless integration with the Python ecosystem make it an excellent choice for:

- Automated video processing workflows
- Content creation pipelines  
- Educational projects
- Rapid prototyping of video applications
- Integration with web frameworks
- Data visualization animations

Whether you're building a simple video converter or a complex automated editing system, MoviePy provides the tools and flexibility to bring your vision to life.

For the latest updates and community discussions, visit the [official GitHub repository](https://github.com/Zulko/moviepy) and join the [MoviePy subreddit](https://www.reddit.com/r/MoviePy/).

Happy video editing! 🎬
