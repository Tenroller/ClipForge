import argparse
import os
import re
import uuid
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip
from playwright.sync_api import sync_playwright
from .processor import clean_text_for_filename
import torch

class TextToImageRenderer:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        # Add GPU detection
        self.has_gpu = torch.cuda.is_available()
        
    def init_browser(self):
        """Initialize browser if not already initialized"""
        if not self.playwright:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch()
            self.page = self.browser.new_page()
    
    def close(self):
        """Close browser and playwright"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def render_text_to_image(self, text, output_path, width=1080, height=200, font_size=32, font_color="black", background_color="white"):
        """Render text to an image using HTML/CSS and Playwright"""
        self.init_browser()

        if not self.page:
            print("Failed to initialize browser page")
            return output_path

        # Create an HTML document with the text
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    width: {width}px;
                    height: {height}px;
                    background: {background_color};
                    box-sizing: border-box;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .text-container {{
                    font-family: Arial, sans-serif;
                    font-size: {font_size}px;
                    color: {font_color};
                    text-align: center;
                    word-wrap: break-word;
                    max-width: 100%;
                    font-weight: bold;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
                }}
            </style>
        </head>
        <body>
            <div class="text-container">{text}</div>
        </body>
        </html>
        """

        # Set viewport size
        self.page.set_viewport_size({"width": width, "height": height})

        # Set content and wait for it to load
        self.page.set_content(html_content)
        self.page.wait_for_load_state("networkidle")

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

def create_video(video_path, text, output_path=None, title=None):
    """
    Creates a 1080x1920 video with HTML-rendered text at the top and a 1:1 video below.
    Optionally includes a title overlay at the very top.
    """
    W, H = 1080, 1920
    BACKGROUND_COLOR = (255, 255, 255)  # White

    # Create output directory and generate filename
    final_videos_dir = os.getenv("VIDEOHELPER_OUTPUT_DIR", "final_videos")
    if output_path is None:
        video_number = get_next_video_number(final_videos_dir)
        cleaned_text = clean_text_for_filename(text)
        filename = f"{video_number:03d}_{cleaned_text}.mp4"
        output_path = os.path.join(final_videos_dir, filename)

    # Load the input video
    video_clip = VideoFileClip(video_path, audio=True)
    video_clip = video_clip.resized(width=W)

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

    # Calculate positions for a more compact layout
    # Position content more towards the center/middle of the frame
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
        temp_audiofile=f'temp-audio-{uuid.uuid4().hex}.m4a',
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