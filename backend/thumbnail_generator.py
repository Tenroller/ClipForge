"""
Video thumbnail generation for the AI Video Generator.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import base64

from logging_config import get_logger

logger = get_logger("thumbnail_generator")


class ThumbnailGenerator:
    """Generate thumbnails and preview images for videos."""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
        self._verify_ffmpeg()
    
    def _verify_ffmpeg(self):
        """Verify FFmpeg is available."""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise Exception("FFmpeg not working properly")
            logger.info("✅ FFmpeg available for thumbnail generation")
        except Exception as e:
            logger.error(f"❌ FFmpeg not available: {e}")
            raise
    
    def extract_frame(self, video_path: Path, timestamp: str = "00:00:01", 
                     output_path: Optional[Path] = None) -> Path:
        """Extract a single frame from video at specified timestamp."""
        if output_path is None:
            output_path = video_path.with_suffix('.jpg')
        
        try:
            cmd = [
                self.ffmpeg_path,
                "-i", str(video_path),
                "-ss", timestamp,
                "-vframes", "1",
                "-q:v", "2",  # High quality
                "-y",  # Overwrite
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg failed: {result.stderr}")
            
            if not output_path.exists():
                raise Exception("Thumbnail file not created")
            
            logger.info(f"✅ Extracted frame from {video_path.name} at {timestamp}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to extract frame: {e}")
            raise
    
    def generate_thumbnail(self, video_path: Path, size: Tuple[int, int] = (320, 180),
                          timestamp: str = "00:00:01") -> Path:
        """Generate a thumbnail with specific size."""
        thumbnail_path = video_path.parent / f"{video_path.stem}_thumb.jpg"
        
        try:
            cmd = [
                self.ffmpeg_path,
                "-i", str(video_path),
                "-ss", timestamp,
                "-vframes", "1",
                "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2",
                "-q:v", "3",
                "-y",
                str(thumbnail_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg failed: {result.stderr}")
            
            logger.info(f"✅ Generated thumbnail {size[0]}x{size[1]} for {video_path.name}")
            return thumbnail_path
            
        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}")
            raise
    
    def generate_multiple_thumbnails(self, video_path: Path, count: int = 4,
                                   size: Tuple[int, int] = (160, 90)) -> List[Path]:
        """Generate multiple thumbnails at different timestamps."""
        thumbnails = []
        
        # Get video duration first
        duration = self.get_video_duration(video_path)
        if duration <= 0:
            duration = 10  # Fallback
        
        # Calculate timestamps
        interval = duration / (count + 1)
        timestamps = [interval * (i + 1) for i in range(count)]
        
        for i, timestamp in enumerate(timestamps):
            timestamp_str = f"{int(timestamp // 3600):02d}:{int((timestamp % 3600) // 60):02d}:{int(timestamp % 60):02d}"
            
            thumbnail_path = video_path.parent / f"{video_path.stem}_thumb_{i+1}.jpg"
            
            try:
                cmd = [
                    self.ffmpeg_path,
                    "-i", str(video_path),
                    "-ss", timestamp_str,
                    "-vframes", "1",
                    "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2",
                    "-q:v", "3",
                    "-y",
                    str(thumbnail_path)
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and thumbnail_path.exists():
                    thumbnails.append(thumbnail_path)
                
            except Exception as e:
                logger.error(f"Failed to generate thumbnail {i+1}: {e}")
        
        logger.info(f"✅ Generated {len(thumbnails)}/{count} thumbnails for {video_path.name}")
        return thumbnails
    
    def get_video_duration(self, video_path: Path) -> float:
        """Get video duration in seconds."""
        try:
            cmd = [
                self.ffmpeg_path,
                "-i", str(video_path),
                "-f", "null", "-"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse duration from stderr
            for line in result.stderr.split('\n'):
                if 'Duration:' in line:
                    duration_str = line.split('Duration:')[1].split(',')[0].strip()
                    # Parse HH:MM:SS.mmm
                    parts = duration_str.split(':')
                    if len(parts) == 3:
                        hours = float(parts[0])
                        minutes = float(parts[1])
                        seconds = float(parts[2])
                        return hours * 3600 + minutes * 60 + seconds
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to get video duration: {e}")
            return 0.0
    
    def create_preview_grid(self, thumbnails: List[Path], output_path: Path,
                          grid_size: Tuple[int, int] = (2, 2)) -> Path:
        """Create a grid of thumbnails as a preview image."""
        if not thumbnails:
            raise ValueError("No thumbnails provided")
        
        # Load all thumbnail images
        images = []
        for thumb_path in thumbnails[:grid_size[0] * grid_size[1]]:
            try:
                img = Image.open(thumb_path)
                images.append(img)
            except Exception as e:
                logger.error(f"Failed to load thumbnail {thumb_path}: {e}")
        
        if not images:
            raise Exception("No valid thumbnails to create grid")
        
        # Calculate grid dimensions
        thumb_width, thumb_height = images[0].size
        grid_width = grid_size[0] * thumb_width
        grid_height = grid_size[1] * thumb_height
        
        # Create grid image
        grid_image = Image.new('RGB', (grid_width, grid_height), (0, 0, 0))
        
        # Place thumbnails in grid
        for i, img in enumerate(images):
            row = i // grid_size[0]
            col = i % grid_size[0]
            x = col * thumb_width
            y = row * thumb_height
            grid_image.paste(img, (x, y))
        
        # Save grid
        grid_image.save(output_path, quality=90)
        logger.info(f"✅ Created preview grid: {output_path}")
        
        return output_path
    
    def add_text_overlay(self, image_path: Path, text: str, 
                        output_path: Optional[Path] = None,
                        font_size: int = 24, font_color: str = "white") -> Path:
        """Add text overlay to image."""
        if output_path is None:
            output_path = image_path.parent / f"{image_path.stem}_overlay{image_path.suffix}"
        
        try:
            # Load image
            image = Image.open(image_path)
            draw = ImageDraw.Draw(image)
            
            # Try to load a nice font
            font = None
            try:
                font = ImageFont.truetype("Arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
            
            # Calculate text position (centered at bottom)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (image.width - text_width) // 2
            y = image.height - text_height - 20
            
            # Add text shadow
            shadow_offset = 2
            draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill="black")
            draw.text((x, y), text, font=font, fill=font_color)
            
            # Save image
            image.save(output_path, quality=95)
            logger.info(f"✅ Added text overlay to {image_path.name}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to add text overlay: {e}")
            raise
    
    def generate_animated_gif(self, video_path: Path, duration: int = 3,
                            size: Tuple[int, int] = (320, 180),
                            fps: int = 10) -> Path:
        """Generate an animated GIF preview from video."""
        gif_path = video_path.parent / f"{video_path.stem}_preview.gif"
        
        try:
            cmd = [
                self.ffmpeg_path,
                "-i", str(video_path),
                "-t", str(duration),
                "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
                "-y",
                str(gif_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg failed: {result.stderr}")
            
            logger.info(f"✅ Generated animated GIF preview for {video_path.name}")
            return gif_path
            
        except Exception as e:
            logger.error(f"Failed to generate animated GIF: {e}")
            raise
    
    def extract_frames_for_analysis(self, video_path: Path, frame_count: int = 10) -> List[Path]:
        """Extract frames for content analysis."""
        frames = []
        duration = self.get_video_duration(video_path)
        
        if duration <= 0:
            return frames
        
        interval = duration / frame_count
        
        for i in range(frame_count):
            timestamp = interval * i
            timestamp_str = f"{int(timestamp // 3600):02d}:{int((timestamp % 3600) // 60):02d}:{int(timestamp % 60):02d}"
            
            frame_path = video_path.parent / f"{video_path.stem}_frame_{i:03d}.jpg"
            
            try:
                cmd = [
                    self.ffmpeg_path,
                    "-i", str(video_path),
                    "-ss", timestamp_str,
                    "-vframes", "1",
                    "-q:v", "2",
                    "-y",
                    str(frame_path)
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and frame_path.exists():
                    frames.append(frame_path)
                
            except Exception as e:
                logger.error(f"Failed to extract frame {i}: {e}")
        
        logger.info(f"✅ Extracted {len(frames)} frames from {video_path.name}")
        return frames
    
    def create_contact_sheet(self, video_path: Path, rows: int = 3, cols: int = 4,
                           output_path: Optional[Path] = None) -> Path:
        """Create a contact sheet with multiple frames from the video."""
        if output_path is None:
            output_path = video_path.parent / f"{video_path.stem}_contact_sheet.jpg"
        
        frame_count = rows * cols
        frames = self.extract_frames_for_analysis(video_path, frame_count)
        
        if not frames:
            raise Exception("No frames extracted for contact sheet")
        
        # Load first frame to get dimensions
        first_frame = Image.open(frames[0])
        frame_width, frame_height = first_frame.size
        
        # Calculate scaled size to fit in contact sheet
        max_frame_width = 200
        max_frame_height = 150
        scale = min(max_frame_width / frame_width, max_frame_height / frame_height)
        scaled_width = int(frame_width * scale)
        scaled_height = int(frame_height * scale)
        
        # Create contact sheet
        sheet_width = cols * scaled_width
        sheet_height = rows * scaled_height
        contact_sheet = Image.new('RGB', (sheet_width, sheet_height), (0, 0, 0))
        
        # Place frames
        for i, frame_path in enumerate(frames):
            if i >= frame_count:
                break
            
            row = i // cols
            col = i % cols
            
            try:
                frame = Image.open(frame_path)
                frame = frame.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
                
                x = col * scaled_width
                y = row * scaled_height
                contact_sheet.paste(frame, (x, y))
                
                # Clean up frame file
                frame_path.unlink(missing_ok=True)
                
            except Exception as e:
                logger.error(f"Failed to process frame {frame_path}: {e}")
        
        # Save contact sheet
        contact_sheet.save(output_path, quality=90)
        logger.info(f"✅ Created contact sheet: {output_path}")
        
        return output_path
    
    def get_video_info(self, video_path: Path) -> Dict[str, Any]:
        """Get comprehensive video information."""
        try:
            cmd = [
                self.ffmpeg_path,
                "-i", str(video_path),
                "-f", "null", "-"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            info = {
                "path": str(video_path),
                "size_bytes": video_path.stat().st_size,
                "duration": 0.0,
                "width": 0,
                "height": 0,
                "fps": 0.0,
                "bitrate": 0,
                "codec": "unknown"
            }
            
            # Parse ffmpeg output
            for line in result.stderr.split('\n'):
                if 'Duration:' in line:
                    duration_str = line.split('Duration:')[1].split(',')[0].strip()
                    parts = duration_str.split(':')
                    if len(parts) == 3:
                        hours = float(parts[0])
                        minutes = float(parts[1])
                        seconds = float(parts[2])
                        info["duration"] = hours * 3600 + minutes * 60 + seconds
                
                elif 'Video:' in line:
                    # Extract resolution
                    if ' x ' in line:
                        resolution = line.split(' x ')[0].split()[-1]
                        try:
                            info["width"] = int(resolution)
                            height_part = line.split(' x ')[1].split()[0]
                            info["height"] = int(height_part)
                        except:
                            pass
                    
                    # Extract fps
                    if ' fps' in line:
                        fps_part = line.split(' fps')[0].split()[-1]
                        try:
                            info["fps"] = float(fps_part)
                        except:
                            pass
                    
                    # Extract codec
                    if 'Video:' in line:
                        codec_part = line.split('Video:')[1].split()[0]
                        info["codec"] = codec_part
                
                elif 'bitrate:' in line:
                    bitrate_part = line.split('bitrate:')[1].split()[0]
                    try:
                        info["bitrate"] = int(bitrate_part)
                    except:
                        pass
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return {"error": str(e)}


# Global thumbnail generator instance
_thumbnail_generator: Optional[ThumbnailGenerator] = None


def get_thumbnail_generator() -> ThumbnailGenerator:
    """Get or create the global thumbnail generator instance."""
    global _thumbnail_generator
    if _thumbnail_generator is None:
        _thumbnail_generator = ThumbnailGenerator()
    return _thumbnail_generator


def generate_video_thumbnails(video_path: Path, sizes: List[Tuple[int, int]] = None) -> Dict[str, Path]:
    """Generate thumbnails in multiple sizes for a video."""
    if sizes is None:
        sizes = [(320, 180), (160, 90), (80, 45)]  # Standard video thumbnail sizes
    
    generator = get_thumbnail_generator()
    thumbnails = {}
    
    for width, height in sizes:
        try:
            thumb_path = generator.generate_thumbnail(video_path, (width, height))
            thumbnails[f"{width}x{height}"] = thumb_path
        except Exception as e:
            logger.error(f"Failed to generate {width}x{height} thumbnail: {e}")
    
    return thumbnails


def create_video_preview_package(video_path: Path) -> Dict[str, Any]:
    """Create a complete preview package for a video."""
    generator = get_thumbnail_generator()
    
    package = {
        "video_path": str(video_path),
        "info": generator.get_video_info(video_path),
        "thumbnails": {},
        "previews": {}
    }
    
    try:
        # Generate main thumbnail
        main_thumb = generator.generate_thumbnail(video_path, (320, 180))
        package["thumbnails"]["main"] = str(main_thumb)
        
        # Generate multiple thumbnails
        multi_thumbs = generator.generate_multiple_thumbnails(video_path, count=4)
        package["thumbnails"]["multiple"] = [str(p) for p in multi_thumbs]
        
        # Create preview grid
        if multi_thumbs:
            grid_path = generator.create_preview_grid(
                multi_thumbs,
                video_path.parent / f"{video_path.stem}_grid.jpg"
            )
            package["previews"]["grid"] = str(grid_path)
        
        # Generate animated GIF
        gif_path = generator.generate_animated_gif(video_path, duration=3)
        package["previews"]["gif"] = str(gif_path)
        
        # Create contact sheet
        contact_sheet = generator.create_contact_sheet(video_path)
        package["previews"]["contact_sheet"] = str(contact_sheet)
        
    except Exception as e:
        logger.error(f"Failed to create preview package: {e}")
        package["error"] = str(e)
    
    return package
