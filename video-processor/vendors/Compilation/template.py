import argparse
import os
import re
import uuid
import tempfile
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip
from PIL import Image, ImageDraw, ImageFont
from .processor import clean_text_for_filename
import torch

class TextToImageRenderer:
    def __init__(self):
        # Add GPU detection
        self.has_gpu = False

    def close(self):
        """Cleanup method for compatibility (no-op for Pillow)"""
        pass

    def _parse_color(self, color_str):
        """Parse color string to RGB tuple"""
        if color_str.startswith('#'):
            # Hex color
            color_str = color_str.lstrip('#')
            if len(color_str) == 6:
                return tuple(int(color_str[i:i+2], 16) for i in (0, 2, 4))
        elif color_str.startswith('rgba'):
            # Extract RGB from rgba (ignore alpha for now)
            import re
            match = re.search(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', color_str)
            if match:
                return tuple(int(x) for x in match.groups())

        # Named colors
        color_map = {
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
        }
        return color_map.get(color_str.lower(), (0, 0, 0))

    def render_text_to_image(self, text, output_path, width=1080, height=200, font_size=32, font_color="black", background_color="white"):
        """Render text to an image using PIL/Pillow"""
        # Parse colors
        bg_color = self._parse_color(background_color)
        text_color = self._parse_color(font_color)

        # Create image with background color
        image = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(image)

        # Try to load a TrueType font, fall back to default if not available
        try:
            # Try to use a bold font
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            try:
                # Fallback to default DejaVu Sans
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                # Last resort: use default font
                font = ImageFont.load_default()

        # Word wrap the text to fit within the width
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= width - 40:  # 20px padding on each side
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        # Calculate total text height
        line_height = font_size + 10
        total_text_height = len(lines) * line_height

        # Start Y position to center text vertically
        y = (height - total_text_height) // 2

        # Draw each line centered
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (width - text_width) // 2

            # Draw text shadow for better visibility
            shadow_offset = 2
            draw.text((x + shadow_offset, y + shadow_offset), line, font=font, fill=(0, 0, 0, 128))

            # Draw main text
            draw.text((x, y), line, font=font, fill=text_color)

            y += line_height

        # Save the image
        image.save(output_path)
        return output_path

def get_next_video_number(output_dir):
    """Get the next available video number in the output directory"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        return 1
    
    existing_files = [f for f in os.listdir(output_dir) if f.endswith('.mp4')]
    if not existing_files:
        return 1
    
    numbers = []
    for filename in existing_files:
        try:
            number = int(filename.split('_')[0])
            numbers.append(number)
        except (ValueError, IndexError):
            continue
    
    return max(numbers) + 1 if numbers else 1

def create_video(video_path, text, output_path=None, title=None, target_resolution=None):
    """
    Creates a video with HTML-rendered text at the top and a video below.
    Optionally includes a title overlay at the very top.
    Resolution is determined dynamically based on input video aspect ratio.
    """
    # Use dynamic resolution if provided, otherwise detect from video
    if target_resolution:
        W, H = target_resolution
    else:
        from .config import TikYouConfig
        config = TikYouConfig()
        config.set_dynamic_resolution(video_path)
        W, H = config.video.width, config.video.height
    
    # Use appropriate background color based on aspect ratio
    if W > H:  # Horizontal
        BACKGROUND_COLOR = (0, 0, 0)  # Black for horizontal videos
    else:  # Vertical or square
        BACKGROUND_COLOR = (255, 255, 255)  # White for vertical/square videos

    # Create output directory and generate filename
    final_videos_dir = os.getenv("VIDEOHELPER_OUTPUT_DIR", "final_videos")
    if output_path is None:
        video_number = get_next_video_number(final_videos_dir)
        cleaned_text = clean_text_for_filename(text)
        filename = f"{video_number:03d}_{cleaned_text}.mp4"
        output_path = os.path.join(final_videos_dir, filename)

    # Load the input video
    video_clip = VideoFileClip(video_path, audio=True)
    
    # Resize video appropriately based on aspect ratio
    if W > H:  # Horizontal layout - fill most of the frame
        video_clip = video_clip.resized(width=W, height=H)  # Fill entire frame
    else:  # Vertical layout - traditional template style
        video_clip = video_clip.resized(width=W)  # Resize by width as before
        
        # Apply rounded corners for vertical layout with white background
        if BACKGROUND_COLOR == (255, 255, 255):  # Only for white background
            try:
                from .video_effects import apply_rounded_corners_simple
                corner_radius = 25  # Template corner radius
                video_clip = apply_rounded_corners_simple(video_clip, corner_radius)
                print(f"        ✨ Applied rounded corners to template video (radius: {corner_radius}px)")
            except Exception as e:
                print(f"        ⚠️  Warning: Could not apply rounded corners: {e}")
                # Continue without rounded corners if there's an error
                pass

    # Create the text layout using HTML + CSS - smaller height for more compact layout
    renderer = TextToImageRenderer()
    text_image_path = renderer.render_text_to_image(text, "temp_text.png", width=W, height=200)
    text_clip = ImageClip(text_image_path).with_duration(video_clip.duration)

    # Create title overlay if provided
    title_clip = None
    if title:
        title_image_path = renderer.render_text_to_image(title, "temp_title.png", width=W, height=150, 
                                                       font_size=48, font_color="#FF6B35", 
                                                       background_color="rgba(0,0,0,0.7)")
        title_clip = ImageClip(title_image_path).with_duration(video_clip.duration)

    # Create a white background clip
    background = ColorClip(size=(W, H), color=BACKGROUND_COLOR, duration=video_clip.duration)

    # Calculate positions based on layout type
    if W > H:  # Horizontal layout - overlay text on video
        text_y_position = 50   # Position text at top
        video_y_position = 0   # Video fills entire frame
    else:  # Vertical layout - traditional template style
        text_y_position = 450  # Move text down significantly 
        video_y_position = 650  # Position video in the middle area of the frame
    
    # Set positions for the clips
    text_clip = text_clip.with_position(('center', text_y_position))  # type: ignore
    video_clip = video_clip.with_position(('center', video_y_position))  # type: ignore
    
    # Add title at the very top if provided
    clips_to_composite = [background, text_clip, video_clip]
    if title_clip:
        title_clip = title_clip.with_position(('center', 100))  # type: ignore  # Position title at the top
        clips_to_composite.insert(1, title_clip)  # Insert after background but before text
    
    # Composite all the clips together
    final_clip = CompositeVideoClip(clips_to_composite)
    
    # Set the duration and audio
    final_clip.duration = video_clip.duration
    final_clip.audio = video_clip.audio

    # Use GPU encoding if available
    codec = 'h264_nvenc' if (hasattr(renderer, 'has_gpu') and renderer.has_gpu) else 'libx264'
    ffmpeg_params = [
        '-movflags', 'faststart',
        '-pix_fmt', 'yuv420p',
        '-profile:v', 'high',
        '-level', '4.1',
    ]
    
    # IMPROVED: Add CPU-specific quality settings
    preset = 'p3' if (hasattr(renderer, 'has_gpu') and renderer.has_gpu) else 'slow'
    bitrate = '6000k'  # IMPROVED: Add bitrate control for better quality
    
    # Log encoding mode
    use_gpu = hasattr(renderer, 'has_gpu') and renderer.has_gpu
    codec_name = 'h264_nvenc (GPU)' if use_gpu else 'libx264 (CPU)'
    preset_name = 'p3 (GPU)' if use_gpu else 'slow (CPU)'
    print(f"🎬 Template video encoding: {codec_name}, preset={preset_name}, bitrate={bitrate}")
    
    if not (hasattr(renderer, 'has_gpu') and renderer.has_gpu):
        # Add CRF for better quality on CPU encoding
        ffmpeg_params.extend([
            '-crf', '20',
            '-maxrate', bitrate,
            '-bufsize', '12000k'
        ])
        print(f"   - CPU Options: crf=20, maxrate={bitrate}, bufsize=12000k")
    else:
        print(f"   - GPU Options: Using NVENC hardware acceleration")
    
    final_clip.write_videofile(
        output_path,
        codec=codec,
        audio_codec='aac',
        temp_audiofile=os.path.join(tempfile.gettempdir(), f'temp-audio-{uuid.uuid4().hex}.m4a'),
        remove_temp=True,
        fps=30,
        preset=preset,  # IMPROVED: Use quality preset instead of veryfast
        threads=4,
        logger=None,
        bitrate=bitrate,  # IMPROVED: Add bitrate control
        ffmpeg_params=ffmpeg_params
    )
    print("Done.")

    # Clean up the temporary text image
    if os.path.exists(text_image_path):
        os.remove(text_image_path)
    
    # Clean up temporary title image if it exists
    if title and os.path.exists("temp_title.png"):
        os.remove("temp_title.png")
    
    # Close the renderer
    renderer.close()

def main():
    parser = argparse.ArgumentParser(description="Create a portrait video with text and a source video.")
    parser.add_argument("video_path", help="Path to the source 1:1 video file.")
    parser.add_argument("text", help="The text to display at the top of the video.")
    parser.add_argument("-o", "--output", help="Path to the output video file.", default=None)
    args = parser.parse_args()

    create_video(args.video_path, args.text, args.output)

if __name__ == "__main__":
    main() 