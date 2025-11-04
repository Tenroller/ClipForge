"""
Request models for API endpoints.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

from ..validation import (
    validate_youtube_url, validate_subject, validate_custom_prompt,
    validate_zip_url, validate_color, validate_subtitle_position,
    validate_ai_model, validate_voice
)


class MoneyPrinterRequest(BaseModel):
    videoSubject: str
    aiModel: str = "gemini-2.0-flash"
    paragraphNumber: int = Field(default=1, ge=1, le=10)
    threads: Optional[int] = Field(default=None, ge=1, le=16)
    subtitlesPosition: str = "center,bottom"
    color: str = "#FFFF00"
    useMusic: bool = False
    zipUrl: Optional[str] = None
    automateYoutubeUpload: bool = False
    useGPU: bool = True
    voice: str = "af_bella"
    customPrompt: Optional[str] = None
    
    # Enhanced subtitle options
    useTikTokSubtitles: bool = False
    useWhisperEnhanced: bool = False  # Use Whisper for precise word timing
    whisperModel: str = "base"  # Whisper model size: tiny, base, small, medium, large
    subtitleFont: str = "Arial-Bold"
    subtitleFontSize: int = Field(default=48, ge=20, le=100)
    subtitleDefaultColor: str = "#FFFFFF"
    subtitleHighlightColor: str = "#FFFFFF"  # Changed to white for new style
    subtitleStrokeColor: str = "#000000"
    subtitleBackgroundColor: str = "#000000"
    subtitleStrokeWidth: int = Field(default=0, ge=0, le=10)  # Disabled for new style
    subtitleBackgroundOpacity: float = Field(default=0.0, ge=0.0, le=1.0)  # Disabled for new style
    subtitlePaddingX: int = Field(default=20, ge=0, le=50)  # Increased padding
    subtitlePaddingY: int = Field(default=16, ge=0, le=50)
    
    # 3D Blue Shadow Layers for Enhanced Subtitles
    shadowLayersCount: int = Field(default=4, ge=2, le=4)  # Number of shadow layers (2, 3, or 4)
    shadowLayer1Color: str = "#4A90E2"  # Light blue (closest to text)
    shadowLayer2Color: str = "#357ABD"  # Medium blue
    shadowLayer3Color: str = "#2E5F8A"  # Dark blue
    shadowLayer4Color: str = "#1E3F5A"  # Darkest blue (furthest from text)
    
    # Shared content fields for benchmarking (optional)
    shared_content: Optional[bool] = Field(default=False)
    shared_content_dir: Optional[str] = Field(default=None)
    shared_script: Optional[str] = Field(default=None)
    shared_search_terms: Optional[List[str]] = Field(default=None)
    shared_sentences: Optional[List[str]] = Field(default=None)
    shared_voice: Optional[str] = Field(default=None)
    shared_stock_videos: Optional[List[str]] = Field(default=None)
    shared_tts_path: Optional[str] = Field(default=None)
    shared_subtitles_path: Optional[str] = Field(default=None)
    shared_manifest: Optional[Dict[str, Any]] = Field(default=None)

    @field_validator('videoSubject')
    @classmethod
    def validate_subject_field(cls, v):
        return validate_subject(v)

    @field_validator('aiModel')
    @classmethod
    def validate_ai_model_field(cls, v):
        return validate_ai_model(v)

    @field_validator('voice')
    @classmethod
    def validate_voice_field(cls, v):
        return validate_voice(v)

    @field_validator('color')
    @classmethod
    def validate_color_field(cls, v):
        return validate_color(v)

    @field_validator('subtitlesPosition')
    @classmethod
    def validate_subtitle_position_field(cls, v):
        return validate_subtitle_position(v)

    @field_validator('zipUrl')
    @classmethod
    def validate_zip_url_field(cls, v):
        return validate_zip_url(v)

    @field_validator('customPrompt')
    @classmethod
    def validate_custom_prompt_field(cls, v):
        return validate_custom_prompt(v)
    
    @field_validator('subtitleFont')
    @classmethod
    def validate_subtitle_font_field(cls, v):
        from ..validation import validate_subtitle_font
        return validate_subtitle_font(v)
    
    @field_validator('subtitleDefaultColor', 'subtitleHighlightColor', 'subtitleStrokeColor', 'subtitleBackgroundColor', 'shadowLayer1Color', 'shadowLayer2Color', 'shadowLayer3Color', 'shadowLayer4Color')
    @classmethod
    def validate_subtitle_color_fields(cls, v):
        return validate_color(v)
    
    @field_validator('subtitleBackgroundOpacity')
    @classmethod
    def validate_subtitle_opacity_field(cls, v):
        from ..validation import validate_subtitle_opacity
        return validate_subtitle_opacity(v)


class BrainrotRequest(BaseModel):
    youtubeUrl: Optional[str] = Field(default=None, description="YouTube URL to download and process")
    uploadedVideoPath: Optional[str] = Field(default=None, description="Path to uploaded video file (alternative to YouTube URL)")
    numCompilations: int = Field(default=1, ge=1)
    minDuration: int = Field(default=60, ge=10, le=3600)
    maxDuration: int = Field(default=110, ge=10, le=3600)
    maxReuse: int = Field(default=3, ge=1)
    unlimited: bool = Field(default=False)
    
    # New variation options
    generateNoBackground: bool = Field(default=True, description="Generate third variation without white background")
    blurredPillarboxThreshold: float = Field(default=0.1, ge=0.05, le=0.5, description="Aspect ratio tolerance for 9:16 format (0.5625)")

    @field_validator('youtubeUrl')
    @classmethod
    def validate_youtube_url_field(cls, v):
        if v is not None:
            return validate_youtube_url(v)
        return v
        
    @field_validator('uploadedVideoPath')
    @classmethod
    def validate_uploaded_video_path(cls, v):
        if v is not None:
            from ..validation import validate_video_file_path
            return validate_video_file_path(v)
        return v
        
    def model_post_init(self, __context) -> None:
        """Ensure exactly one of youtubeUrl or uploadedVideoPath is provided"""
        if not self.youtubeUrl and not self.uploadedVideoPath:
            raise ValueError("Either youtubeUrl or uploadedVideoPath must be provided")
        if self.youtubeUrl and self.uploadedVideoPath:
            raise ValueError("Cannot provide both youtubeUrl and uploadedVideoPath - choose one input method")


class PodcastClipsRequest(BaseModel):
    """Request model for podcast clips workflow - generates viral short-form videos from podcasts."""
    youtubeUrl: str = Field(..., description="YouTube URL of the podcast to process")
    aiModel: str = Field(default="gemini-2.0-flash", description="AI model for viral moment detection")
    whisperModel: str = Field(default="base", description="Whisper model size: tiny, base, small, medium, large")
    targetClipCount: int = Field(default=7, ge=5, le=10, description="Target number of clips (AI decides final count within range)")
    minDuration: int = Field(default=20, ge=15, le=60, description="Minimum clip duration in seconds")
    maxDuration: int = Field(default=70, ge=30, le=120, description="Maximum clip duration in seconds")
    useGPU: bool = Field(default=True, description="Use GPU acceleration for processing")
    subtitleFontSize: int = Field(default=40, ge=20, le=80, description="Subtitle font size")
    subtitleColor: str = Field(default="#FFFFFF", description="Subtitle text color (hex format)")
    subtitleStrokeColor: str = Field(default="#000000", description="Subtitle stroke/outline color")
    subtitleStrokeWidth: int = Field(default=2, ge=0, le=5, description="Subtitle stroke width")
    viralFocusKeywords: List[str] = Field(default=[], description="Optional keywords to prioritize when detecting viral moments")

    @field_validator('youtubeUrl')
    @classmethod
    def validate_youtube_url_field(cls, v):
        return validate_youtube_url(v)

    @field_validator('aiModel')
    @classmethod
    def validate_ai_model_field(cls, v):
        return validate_ai_model(v)

    @field_validator('subtitleColor', 'subtitleStrokeColor')
    @classmethod
    def validate_subtitle_color_fields(cls, v):
        return validate_color(v)

    @field_validator('minDuration', 'maxDuration')
    @classmethod
    def validate_duration_fields(cls, v):
        if v < 10:
            raise ValueError("Duration must be at least 10 seconds")
        if v > 300:
            raise ValueError("Duration cannot exceed 300 seconds (5 minutes)")
        return v


class SuggestSubjectRequest(BaseModel):
    aiModel: str | None = None
    examples: list[str] | None = None
    topicHint: str | None = None


class PlaylistBatchRequest(BaseModel):
    playlistUrl: str
    name: Optional[str] = None
    limit: Optional[int] = None
    sample: Optional[int] = None
    shuffle: bool = False
    priority: str = "normal"
    maxConcurrent: int = 3
    stopOnError: bool = False
    # AIvideos common params
    numCompilations: int = Field(default=1, ge=1)
    minDuration: int = Field(default=60, ge=10, le=3600)
    maxDuration: int = Field(default=110, ge=10, le=3600)


class LoginRequest(BaseModel):
    """Login request with username and password."""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Login response with access token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class TokenVerifyResponse(BaseModel):
    """Token verification response."""
    valid: bool
    user: Optional[dict] = None
