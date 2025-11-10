"""
Thumbnail generator for podcast clips.

Creates eye-catching thumbnails optimized for social media engagement.
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger as loguru_logger

logger = loguru_logger.bind(name="PodcastClips.thumbnail_generator")


class ThumbnailGenerator:
    """
    Generate eye-catching thumbnails for viral clips.

    Creates thumbnails with:
    - Best facial expression frame
    - Text overlay with title
    - High contrast borders/effects
    - Platform-specific sizing
    """

    def __init__(self, platform: str = "universal"):
        """
        Initialize thumbnail generator.

        Args:
            platform: Target platform ("tiktok", "instagram", "youtube", "universal")
        """
        self.platform = platform

        # Platform-specific dimensions (width x height)
        self.dimensions = {
            "tiktok": (1080, 1920),      # 9:16 vertical
            "instagram": (1080, 1920),    # 9:16 vertical
            "youtube": (1080, 1920),      # 9:16 vertical (Shorts)
            "universal": (1080, 1920)     # 9:16 vertical (universal)
        }

        self.target_size = self.dimensions.get(platform, (1080, 1920))

    def generate_thumbnail(
        self,
        video_path: str,
        title: str,
        output_path: str,
        timestamp: Optional[float] = None,
        face_bbox: Optional[Tuple[int, int, int, int]] = None
    ) -> str:
        """
        Generate thumbnail from video clip.

        Args:
            video_path: Path to video file
            title: Clip title for text overlay
            output_path: Path to save thumbnail
            timestamp: Specific timestamp to extract frame (default: middle of video)
            face_bbox: Optional face bounding box (x, y, width, height) for framing

        Returns:
            Path to generated thumbnail
        """
        try:
            logger.info(f"Generating thumbnail for {Path(video_path).name}")

            # Extract best frame
            frame = self._extract_best_frame(video_path, timestamp)

            if frame is None:
                raise ValueError("Could not extract frame from video")

            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Create PIL Image
            img = Image.fromarray(frame_rgb)

            # Resize to target dimensions
            img = img.resize(self.target_size, Image.Resampling.LANCZOS)

            # Apply enhancements
            img = self._enhance_image(img)

            # Add text overlay
            img = self._add_text_overlay(img, title)

            # Add borders/effects
            img = self._add_border_effects(img)

            # Save thumbnail
            img.save(output_path, "JPEG", quality=95, optimize=True)

            logger.info(f"Thumbnail saved: {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}", exc_info=True)
            raise

    def _extract_best_frame(
        self,
        video_path: str,
        timestamp: Optional[float] = None
    ) -> Optional[np.ndarray]:
        """
        Extract the best frame for thumbnail.

        Uses frame quality metrics to find the clearest, most engaging frame.

        Args:
            video_path: Path to video file
            timestamp: Specific timestamp (seconds), or None for auto-detection

        Returns:
            Frame as numpy array (BGR format)
        """
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            logger.error(f"Could not open video: {video_path}")
            return None

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if timestamp is not None:
                # Extract specific timestamp
                frame_num = int(timestamp * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                return frame if ret else None

            # Auto-detect best frame (sample frames from first 3 seconds for hook)
            best_frame = None
            best_score = 0

            # Sample frames in first 3 seconds (most engaging part)
            sample_duration = min(3.0, total_frames / fps)
            sample_frames = int(sample_duration * fps)

            for i in range(0, sample_frames, int(fps / 3)):  # Sample 3 frames per second
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()

                if not ret:
                    continue

                # Score frame quality (sharpness + brightness + contrast)
                score = self._score_frame_quality(frame)

                if score > best_score:
                    best_score = score
                    best_frame = frame.copy()

            return best_frame

        finally:
            cap.release()

    def _score_frame_quality(self, frame: np.ndarray) -> float:
        """
        Score frame quality for thumbnail selection.

        Combines multiple metrics:
        - Sharpness (Laplacian variance)
        - Brightness (mean luminance)
        - Contrast (std dev of luminance)

        Returns:
            Quality score (higher is better)
        """
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Sharpness (Laplacian variance)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = laplacian.var()

        # Brightness (mean)
        brightness = gray.mean()

        # Contrast (std dev)
        contrast = gray.std()

        # Combined score (normalized)
        # Prefer sharp, well-lit, high-contrast frames
        score = (sharpness / 1000) + (brightness / 255) + (contrast / 128)

        return score

    def _enhance_image(self, img: Image.Image) -> Image.Image:
        """
        Enhance image for better thumbnail appeal.

        Applies:
        - Contrast boost
        - Saturation boost
        - Sharpness enhancement
        """
        # Increase contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)

        # Increase saturation
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.3)

        # Sharpen
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.5)

        return img

    def _add_text_overlay(self, img: Image.Image, title: str) -> Image.Image:
        """
        Add text overlay with title.

        Creates bold, high-contrast text with stroke/shadow for readability.
        """
        draw = ImageDraw.Draw(img)
        width, height = img.size

        # Prepare title text (limit length, add emoji if engaging)
        title = self._format_title(title, max_length=60)

        # Try to load a bold font, fallback to default
        try:
            # Try multiple font locations
            font_paths = [
                "/System/Library/Fonts/Helvetica.ttc",  # macOS
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
                "C:\\Windows\\Fonts\\arial.ttf",  # Windows
            ]

            font = None
            for font_path in font_paths:
                if Path(font_path).exists():
                    font = ImageFont.truetype(font_path, 80)
                    break

            if font is None:
                font = ImageFont.load_default()

        except Exception:
            font = ImageFont.load_default()

        # Calculate text position (bottom third)
        # Use textbbox for accurate text dimensions
        bbox = draw.textbbox((0, 0), title, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Center horizontally, place in bottom third
        x = (width - text_width) // 2
        y = int(height * 0.7)

        # Draw text with stroke (for readability)
        stroke_width = 5

        # Draw stroke (black)
        for offset_x in range(-stroke_width, stroke_width + 1):
            for offset_y in range(-stroke_width, stroke_width + 1):
                draw.text((x + offset_x, y + offset_y), title, font=font, fill=(0, 0, 0, 255))

        # Draw main text (white with yellow tint for "viral" look)
        draw.text((x, y), title, font=font, fill=(255, 255, 100, 255))

        return img

    def _add_border_effects(self, img: Image.Image) -> Image.Image:
        """
        Add border effects for attention-grabbing thumbnail.

        Adds subtle vignette effect to focus attention.
        """
        width, height = img.size

        # Create vignette overlay
        vignette = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(vignette)

        # Draw radial gradient for vignette
        for i in range(100):
            alpha = int((i / 100) * 100)  # Gradually increase darkness
            rect_padding = int((i / 100) * min(width, height) * 0.3)
            draw.rectangle(
                [rect_padding, rect_padding, width - rect_padding, height - rect_padding],
                outline=(0, 0, 0, alpha)
            )

        # Apply vignette
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, vignette)

        return img.convert('RGB')

    def _format_title(self, title: str, max_length: int = 60) -> str:
        """
        Format title for thumbnail display.

        Args:
            title: Original title
            max_length: Maximum character length

        Returns:
            Formatted title
        """
        # Truncate if too long
        if len(title) > max_length:
            title = title[:max_length - 3] + "..."

        # Capitalize first letter of each word for better readability
        title = title.upper()  # All caps for impact

        return title

    def generate_batch_thumbnails(
        self,
        clips_data: list,
        output_dir: str
    ) -> list:
        """
        Generate thumbnails for multiple clips in batch.

        Args:
            clips_data: List of dicts with keys: video_path, title, timestamp (optional)
            output_dir: Directory to save thumbnails

        Returns:
            List of generated thumbnail paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        thumbnail_paths = []

        for clip_data in clips_data:
            video_path = clip_data.get('video_path')
            title = clip_data.get('title', 'Viral Moment')
            timestamp = clip_data.get('timestamp')

            # Generate output path
            video_name = Path(video_path).stem
            thumbnail_path = output_dir / f"{video_name}_thumbnail.jpg"

            try:
                path = self.generate_thumbnail(
                    video_path=video_path,
                    title=title,
                    output_path=str(thumbnail_path),
                    timestamp=timestamp
                )
                thumbnail_paths.append(path)
            except Exception as e:
                logger.error(f"Failed to generate thumbnail for {video_name}: {e}")
                continue

        logger.info(f"Generated {len(thumbnail_paths)}/{len(clips_data)} thumbnails")

        return thumbnail_paths
