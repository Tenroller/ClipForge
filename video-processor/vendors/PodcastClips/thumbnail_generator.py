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
        face_bbox: Optional[Tuple[int, int, int, int]] = None,
        catchy_phrase: Optional[str] = None,
        use_red_box: bool = True,
        apply_blur: bool = True,
        blur_intensity: float = 0.3,
        red_box_config: Optional[dict] = None,
        crop_style: str = "mid"
    ) -> str:
        """
        Generate thumbnail from video clip.

        Args:
            video_path: Path to video file
            title: Clip title for text overlay (fallback if no catchy_phrase)
            output_path: Path to save thumbnail
            timestamp: Specific timestamp to extract frame (default: middle of video)
            face_bbox: Optional face bounding box (x, y, width, height) for framing
            catchy_phrase: AI-generated catchy phrase for red box overlay
            use_red_box: Whether to use red box overlay (default: True)
            apply_blur: Whether to apply background blur effect (default: True)
            blur_intensity: Blur/darken intensity (0.0-1.0, default: 0.3)
            red_box_config: Configuration dict for red box (color, opacity, padding, etc.)
            crop_style: AI-recommended crop style ("close-up", "mid", "wide", "focus-on-person-X")

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

            # Apply AI-recommended cropping before resizing
            img = self._apply_smart_crop(img, crop_style)

            # Resize to target dimensions
            img = img.resize(self.target_size, Image.Resampling.LANCZOS)

            # Apply enhancements
            img = self._enhance_image(img)

            # Apply background blur if requested
            if apply_blur:
                img = self._apply_background_blur(img, intensity=blur_intensity)

            # Use red box overlay if catchy phrase provided
            if use_red_box and catchy_phrase:
                img = self._apply_red_box_overlay(img, catchy_phrase, red_box_config)
            else:
                # Fallback to old text overlay style
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

    def _apply_smart_crop(self, img: Image.Image, crop_style: str) -> Image.Image:
        """
        Apply AI-recommended cropping to focus on the most important part of the frame.

        Args:
            img: Input image
            crop_style: One of "close-up", "mid", "wide", or "focus-on-person-X"

        Returns:
            Cropped image
        """
        width, height = img.size

        # Normalize crop_style
        crop_style = crop_style.lower() if crop_style else "mid"

        logger.debug(f"Applying crop style: {crop_style}")

        if crop_style == "close-up" or crop_style.startswith("focus-on-person"):
            # Close-up: Crop to center 60% for tighter framing
            # Great for emotional reactions and facial expressions
            crop_factor = 0.6
            new_width = int(width * crop_factor)
            new_height = int(height * crop_factor)

            # Center crop
            left = (width - new_width) // 2
            top = (height - new_height) // 2
            right = left + new_width
            bottom = top + new_height

            img = img.crop((left, top, right, bottom))
            logger.debug(f"Applied close-up crop: {new_width}x{new_height}")

        elif crop_style == "mid":
            # Mid shot: Crop to center 80% (slight zoom)
            # Balanced framing for most content
            crop_factor = 0.8
            new_width = int(width * crop_factor)
            new_height = int(height * crop_factor)

            left = (width - new_width) // 2
            top = (height - new_height) // 2
            right = left + new_width
            bottom = top + new_height

            img = img.crop((left, top, right, bottom))
            logger.debug(f"Applied mid crop: {new_width}x{new_height}")

        elif crop_style == "wide":
            # Wide shot: No cropping, keep full frame
            # Good for showing context or multiple people
            logger.debug("Keeping wide shot (no crop)")
            pass

        else:
            # Unknown crop style, default to mid
            logger.warning(f"Unknown crop style '{crop_style}', defaulting to mid")
            return self._apply_smart_crop(img, "mid")

        return img

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

    def _apply_background_blur(self, img: Image.Image, intensity: float = 0.3) -> Image.Image:
        """
        Apply subtle blur and darkening to background for focus.

        Args:
            img: Input image
            intensity: Blur/darken intensity (0.0-1.0)

        Returns:
            Image with blurred/darkened background
        """
        # Create darkening overlay
        width, height = img.size
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Calculate alpha for darkening effect
        alpha = int(intensity * 100)  # 0.3 -> 30% darkness

        # Draw semi-transparent dark overlay
        draw.rectangle([0, 0, width, height], fill=(0, 0, 0, alpha))

        # Apply overlay to image
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)

        return img.convert('RGB')

    def _apply_red_box_overlay(
        self,
        img: Image.Image,
        catchy_phrase: str,
        config: Optional[dict] = None
    ) -> Image.Image:
        """
        Apply viral-style red box overlay with catchy phrase.

        Creates a bold red rectangular box with white/yellow text overlay,
        positioned for maximum engagement.

        Args:
            img: Input image
            catchy_phrase: AI-generated catchy phrase text
            config: Optional configuration dict with:
                - box_color: RGB tuple (default: red #DC2626)
                - text_color: RGB tuple (default: yellow-tinted white)
                - padding: Box padding in pixels
                - position: 'bottom', 'center', or 'top'

        Returns:
            Image with red box overlay
        """
        # Default configuration
        default_config = {
            'box_color': (220, 38, 38),      # Red #DC2626
            'text_color': (255, 255, 100),   # Yellow-tinted white #FFFF64
            'padding': 30,
            'position': 'bottom',
            'opacity': 0.95,
            'stroke_width': 5,
            'stroke_color': (0, 0, 0)
        }

        # Merge with provided config
        if config:
            default_config.update(config)

        cfg = default_config
        width, height = img.size

        # Convert to RGBA for transparency
        img = img.convert('RGBA')

        # Create overlay layer
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Prepare text
        text = catchy_phrase.upper()  # All caps for impact

        # Load font (larger size for red box)
        try:
            font_paths = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "C:\\Windows\\Fonts\\arialbd.ttf",
            ]

            font = None
            for font_path in font_paths:
                if Path(font_path).exists():
                    font = ImageFont.truetype(font_path, 90)
                    break

            if font is None:
                font = ImageFont.load_default()

        except Exception:
            font = ImageFont.load_default()

        # Calculate text dimensions
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Calculate box dimensions (with padding)
        box_width = text_width + (cfg['padding'] * 2)
        box_height = text_height + (cfg['padding'] * 2)

        # Position box based on config
        if cfg['position'] == 'bottom':
            box_x = (width - box_width) // 2
            box_y = int(height * 0.65)  # Lower third
        elif cfg['position'] == 'center':
            box_x = (width - box_width) // 2
            box_y = (height - box_height) // 2
        else:  # top
            box_x = (width - box_width) // 2
            box_y = int(height * 0.15)

        # Calculate text position (centered in box)
        text_x = box_x + cfg['padding']
        text_y = box_y + cfg['padding']

        # Draw red box with opacity
        box_color_with_alpha = cfg['box_color'] + (int(cfg['opacity'] * 255),)
        draw.rectangle(
            [box_x, box_y, box_x + box_width, box_y + box_height],
            fill=box_color_with_alpha
        )

        # Draw text with stroke (for readability)
        stroke_width = cfg['stroke_width']

        # Draw stroke (black outline)
        for offset_x in range(-stroke_width, stroke_width + 1):
            for offset_y in range(-stroke_width, stroke_width + 1):
                if offset_x == 0 and offset_y == 0:
                    continue
                draw.text(
                    (text_x + offset_x, text_y + offset_y),
                    text,
                    font=font,
                    fill=cfg['stroke_color'] + (255,)
                )

        # Draw main text (yellow-tinted white)
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=cfg['text_color'] + (255,)
        )

        # Composite overlay onto image
        img = Image.alpha_composite(img, overlay)

        return img.convert('RGB')

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
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        thumbnail_paths = []

        for clip_data in clips_data:
            video_path = clip_data.get('video_path')
            title = clip_data.get('title', 'Viral Moment')
            timestamp = clip_data.get('timestamp')

            # Generate output path
            video_name = Path(video_path).stem
            thumbnail_path = output_path / f"{video_name}_thumbnail.jpg"

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
