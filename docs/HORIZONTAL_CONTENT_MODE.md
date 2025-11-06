# Horizontal Content Mode for Podcast Clips

## Overview

The Horizontal Content Mode feature extends the PodcastClips workflow to intelligently detect and display horizontal content (screen recordings, articles, images, slides) in their original format within vertical 9:16 clips, instead of cropping them to focus on faces.

This feature automatically switches between:
- **Face-tracking mode**: Traditional vertical crop centered on the speaker's face
- **Horizontal content mode**: Full horizontal video centered in the 9:16 canvas with blurred background

## How It Works

### 1. Content Detection

The system analyzes each video segment using multiple detection methods:

#### Face Loss Detection
- Monitors face detection confidence over time
- Triggers horizontal mode when faces are lost for more than `faceLossThreshold` seconds (default: 1.0s)
- Returns to face mode when faces reappear for more than `faceReturnThreshold` seconds (default: 0.5s)

#### Visual Content Analysis (Optional)
When OCR is enabled (`useOCR: true`), the system performs additional analysis:

- **Text Density Detection**: Uses OCR (pytesseract) to detect readable text in frames
- **Edge Density Analysis**: Measures sharp edges that indicate UI elements or text
- **Color Saturation Scoring**: Low saturation suggests documents/UI vs. natural scenes

These indicators help confirm that content (not just a missing face) is being shown.

### 2. Segment Timeline Generation

The detector creates a timeline of content mode segments:

```json
[
  {"start": 0.0, "end": 4.5, "mode": "face", "confidence": 0.95},
  {"start": 4.5, "end": 10.2, "mode": "horizontal", "confidence": 0.87},
  {"start": 10.2, "end": 15.0, "mode": "face", "confidence": 0.92}
]
```

### 3. Smart Segmentation

- **Minimum Duration Filtering**: Segments shorter than `minSegmentDuration` (default: 0.5s) are merged to avoid flickering
- **Mode Smoothing**: Adjacent segments with the same mode are automatically merged
- **Confidence Scoring**: Each segment receives a confidence score based on detection quality

### 4. Visual Composition

#### Face-Tracking Mode (Traditional)
```
┌─────────────┐
│             │ ← Black bars (unused)
│   [FACE]    │ ← 9:16 crop centered on face
│             │
│   Speaking  │
│    Person   │
│             │
└─────────────┘
```

#### Horizontal Content Mode (New)
```
┌─────────────┐
│╔═══════════╗│ ← Blurred/darkened background
│║ ARTICLE   ║│ ← Horizontal content at original aspect ratio
│║ or SCREEN ║│ ← Scaled to fit (90% of height)
│╚═══════════╝│
└─────────────┘
```

**Composition Details:**
- Content scaled to fit within 90% of canvas height (preserves aspect ratio)
- Background created by blurring and darkening the same frame (50% brightness)
- Blur strength: 15% resize factor for smooth background
- Alternative: Solid dark background (configurable via `background_color`)

### 5. Smooth Transitions

When switching between modes, the system applies a crossfade transition:

```
Mode Change Detected
        ↓
[Clip 1 - Face Mode] ─┐
                       ├─→ [0.5s Crossfade] ─→ [Clip 2 - Horizontal Mode]
                       │   (FadeOut + FadeIn)
[Clip 2 - Horizontal] ─┘
```

**Transition Duration**: Configurable via `transitionDuration` (default: 0.5s)

## Configuration

### API Request Parameters

When making a PodcastClips request, include these optional parameters:

```json
{
  "youtubeUrl": "https://www.youtube.com/watch?v=...",
  "targetClipCount": 7,

  // Mixed-mode configuration
  "enableMixedMode": true,
  "faceLossThreshold": 1.0,
  "faceReturnThreshold": 0.5,
  "minSegmentDuration": 0.5,
  "useOCR": true,
  "transitionDuration": 0.5
}
```

### Parameter Reference

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `enableMixedMode` | boolean | `true` | - | Enable horizontal content mode detection |
| `faceLossThreshold` | float | `1.0` | 0.5-3.0 | Seconds without face to trigger horizontal mode |
| `faceReturnThreshold` | float | `0.5` | 0.2-2.0 | Seconds with face to return to face mode |
| `minSegmentDuration` | float | `0.5` | 0.3-2.0 | Minimum segment duration to avoid flicker (seconds) |
| `useOCR` | boolean | `true` | - | Use OCR for text-based content detection |
| `transitionDuration` | float | `0.5` | 0.2-1.0 | Crossfade duration between modes (seconds) |

### Tuning Guidelines

#### Conservative Detection (Fewer Mode Switches)
```json
{
  "faceLossThreshold": 2.0,    // Require 2 seconds without face
  "faceReturnThreshold": 0.3,  // Quick return to face mode
  "minSegmentDuration": 1.0    // Longer minimum segment
}
```

#### Aggressive Detection (More Responsive)
```json
{
  "faceLossThreshold": 0.5,    // Switch quickly when face lost
  "faceReturnThreshold": 1.0,  // Require 1 second to confirm face return
  "minSegmentDuration": 0.3    // Allow shorter segments
}
```

## Use Cases

### 1. Tech Tutorial Podcasts
**Scenario**: Host shares code, terminal windows, or browser tabs

**Before**: Zoomed-in vertical crop cuts off important UI elements
```
┌─────┐
│ [CO │  ← Code/terminal cut off
│ [DE │
│ [SHO│
└─────┘
```

**After**: Full horizontal display with readable content
```
┌─────────────┐
│╔═══════════╗│
│║ FULL CODE ║│  ← Complete horizontal view
│║  VISIBLE  ║│
│╚═══════════╝│
└─────────────┘
```

### 2. News Commentary
**Scenario**: Podcaster shows news articles or tweets

**Benefit**: Viewers can read the full article/tweet without horizontal scrolling

### 3. Product Reviews
**Scenario**: Host displays product images, websites, or spec sheets

**Benefit**: Product details remain legible and properly framed

### 4. Educational Content
**Scenario**: Instructor shares slides, diagrams, or charts

**Benefit**: Visual aids displayed at optimal size without cropping

## Implementation Architecture

### Class Hierarchy

```
PodcastClipsProcessor
    ↓
    ├─ FaceTracker (MediaPipe)
    │   └─ Analyzes video for face positions
    │
    ├─ ContentModeDetector (NEW)
    │   ├─ analyze_video_segments()
    │   ├─ _detect_text_density() [OCR]
    │   ├─ _calculate_edge_density()
    │   └─ _calculate_saturation_score()
    │
    └─ ClipGenerator
        ├─ generate_clip()
        ├─ generate_mixed_mode_clip() (NEW)
        ├─ create_face_tracked_clip()
        ├─ create_horizontal_content_clip() (NEW)
        └─ apply_crossfade_transition() (NEW)
```

### Processing Flow

```
1. Face Tracker analyzes video
   ↓ (face_positions: Dict[timestamp -> FaceBox])

2. ContentModeDetector analyzes segments
   ├─ Checks face loss/return patterns
   ├─ Optionally runs OCR/visual analysis
   └─ Generates segment timeline
   ↓ (segments: List[ContentSegment])

3. ClipGenerator processes each segment
   ├─ IF mode == FACE:
   │   └─ create_face_tracked_clip()
   └─ IF mode == HORIZONTAL:
       └─ create_horizontal_content_clip()
   ↓

4. Apply transitions between mode changes
   └─ apply_crossfade_transition()
   ↓

5. Concatenate segments + add subtitles
   └─ Final 9:16 clip with mixed modes
```

## Technical Details

### Dependencies

**Required:**
- `moviepy` - Video composition and effects
- `cv2` (OpenCV) - Frame analysis
- `numpy` - Array operations
- `mediapipe` - Face detection (already required)

**Optional:**
- `pytesseract` - OCR for text detection (improves content detection accuracy)
  - Install: `pip install pytesseract`
  - Requires Tesseract OCR binary: https://github.com/tesseract-ocr/tesseract

### Performance Considerations

#### Processing Overhead
- **Face tracking**: ~5-10 ms per frame (already present)
- **Content detection (without OCR)**: +2-5 ms per frame
- **Content detection (with OCR)**: +20-50 ms per sampled frame (only on potential content segments)

#### Optimization Strategies
1. **Selective OCR**: Only runs on frames in horizontal mode candidates
2. **Frame Sampling**: Analyzes 3 frames per segment (start, middle, end)
3. **Caching**: Face positions cached across segment analysis
4. **Parallel Processing**: Clip generation remains parallelized (3 workers default)

#### Estimated Performance Impact
- **Without OCR**: +5-10% total processing time
- **With OCR**: +10-20% total processing time

### Memory Requirements

- **ContentModeDetector**: ~10-20 MB for segment metadata
- **Blurred backgrounds**: Rendered on-the-fly, minimal additional memory
- **No significant change to existing memory footprint**

## Troubleshooting

### Issue: Too Many Mode Switches

**Symptoms**: Video flickers between modes rapidly

**Solutions:**
1. Increase `faceLossThreshold` to 1.5-2.0 seconds
2. Increase `minSegmentDuration` to 1.0-1.5 seconds
3. Enable OCR to improve content detection accuracy

### Issue: Content Not Detected

**Symptoms**: Screen recordings stay in face-tracking mode

**Solutions:**
1. Decrease `faceLossThreshold` to 0.5-0.7 seconds
2. Enable OCR: `"useOCR": true`
3. Check that faces are actually being lost during content display

### Issue: False Positives (Face Mode Detected as Content)

**Symptoms**: Face segments incorrectly switch to horizontal mode

**Solutions:**
1. Increase `faceReturnThreshold` to 0.8-1.0 seconds
2. Use OCR to confirm low text density in face segments
3. Check face detection quality (may need better lighting in source video)

### Issue: Poor Visual Quality in Horizontal Mode

**Symptoms**: Blurred background looks bad

**Solutions:**
1. Adjust blur strength in `create_horizontal_content_clip()` (default: 0.15)
2. Use solid background: modify `blur_background=False`
3. Increase content scaling from 90% to 95% of height

## API Examples

### Basic Usage (Default Settings)

```bash
curl -X POST http://localhost:9000/api/podcastclips/generate \
  -H "Content-Type: application/json" \
  -d '{
    "youtubeUrl": "https://www.youtube.com/watch?v=VIDEO_ID",
    "targetClipCount": 7
  }'
```

Mixed mode is enabled by default with optimal settings.

### Disable Mixed Mode (Traditional Behavior)

```bash
curl -X POST http://localhost:9000/api/podcastclips/generate \
  -H "Content-Type: application/json" \
  -d '{
    "youtubeUrl": "https://www.youtube.com/watch?v=VIDEO_ID",
    "targetClipCount": 7,
    "enableMixedMode": false
  }'
```

### Custom Configuration for Tech Content

```bash
curl -X POST http://localhost:9000/api/podcastclips/generate \
  -H "Content-Type: application/json" \
  -d '{
    "youtubeUrl": "https://www.youtube.com/watch?v=VIDEO_ID",
    "targetClipCount": 7,
    "enableMixedMode": true,
    "faceLossThreshold": 0.7,
    "useOCR": true,
    "transitionDuration": 0.3
  }'
```

## Future Enhancements

### Potential Improvements
- [ ] Automatic threshold tuning based on video content type
- [ ] Object detection to identify specific content types (code, charts, etc.)
- [ ] Zoom effects when transitioning to horizontal content
- [ ] Custom background styles (gradient, brand colors)
- [ ] Per-segment blurring intensity based on content complexity
- [ ] AI-based content type classification (ML model)

### Known Limitations
1. OCR requires external Tesseract binary installation
2. Transitions are crossfade only (no pan/zoom options yet)
3. Horizontal content always centered (no smart positioning)
4. Background blur quality depends on source video resolution

## Version History

### v1.0.0 (2025-01-XX)
- Initial release of horizontal content mode
- Face loss detection with configurable thresholds
- OCR-based text density analysis
- Blurred background rendering
- Crossfade transitions between modes
- Full API parameter support

## Support

For issues, questions, or feature requests related to horizontal content mode:
- **GitHub Issues**: https://github.com/Tenroller/ai-video-generator/issues
- **Documentation**: `/docs/HORIZONTAL_CONTENT_MODE.md`
- **CLAUDE.md**: Project-wide development guidelines

## References

- **MediaPipe Face Detection**: https://google.github.io/mediapipe/solutions/face_detection
- **MoviePy Documentation**: https://zulko.github.io/moviepy/
- **Tesseract OCR**: https://github.com/tesseract-ocr/tesseract
- **PodcastClips Workflow**: `/video-processor/vendors/PodcastClips/`
