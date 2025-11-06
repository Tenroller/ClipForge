# Video Processor Test Examples

This directory contains example job configurations for testing the video processor service.

## Example Files

- **moneyprinter_example.json** - AI-generated video with script and stock footage
- **brainrot_example.json** - Compilation videos from YouTube source
- **podcastclips_example.json** - Extract viral moments from podcast videos

## Usage

### Using the test script with examples:

```bash
# Test MoneyPrinter workflow
python test_processor.py moneyprinter "Amazing AI discoveries in 2024"

# Test Brainrot workflow
python test_processor.py brainrot "https://www.youtube.com/watch?v=VIDEO_ID"

# Test PodcastClips workflow
python test_processor.py podcastclips "https://www.youtube.com/watch?v=PODCAST_ID"
```

### Using curl with example files:

```bash
# Submit a job using example configuration
JOB_ID=$(uuidgen)
curl -X POST http://localhost:8090/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "'$JOB_ID'",
    "workflow": "moneyprinter",
    "priority": "normal",
    "request_data": {
      "videoSubject": "The future of AI",
      "paragraphNumber": 3,
      "voice": "af_bella",
      "aiModel": "gemini-2.0-flash",
      "useMusic": false,
      "useTikTokSubtitles": true
    }
  }'

# Check job status
curl http://localhost:8090/api/v1/jobs/$JOB_ID
```

## Workflow Parameters

### MoneyPrinter

- `videoSubject` (required) - Subject for the video
- `paragraphNumber` - Number of paragraphs in script (default: 3)
- `voice` - Voice to use for TTS (default: "af_bella")
- `aiModel` - AI model for script generation (default: "gemini-2.0-flash")
- `useMusic` - Include background music (default: false)
- `useTikTokSubtitles` - Use TikTok-style subtitles (default: true)

### Brainrot

- `youtubeUrl` (required) - YouTube URL to process
- `numCompilations` - Number of compilations to generate (default: 1)
- `minDuration` - Minimum duration in seconds (default: 30)
- `maxDuration` - Maximum duration in seconds (default: 60)
- `maxReuse` - Maximum reuse count (default: 3)
- `unlimited` - Generate unlimited compilations (default: false)

### PodcastClips

- `youtubeUrl` (required) - YouTube URL of the podcast
- `aiModel` - AI model for viral moment detection (default: "gemini-2.0-flash")
- `whisperModel` - Whisper model size: tiny, base, small, medium, large (default: "base")
- `targetClipCount` - Target number of clips (default: 7)
- `minDuration` - Minimum clip duration in seconds (default: 20)
- `maxDuration` - Maximum clip duration in seconds (default: 70)
- `useGPU` - Use GPU acceleration (default: true)
- `viralFocusKeywords` - Keywords to prioritize (default: [])

## Available Voices (TTS)

Some popular voices for MoneyPrinter:
- `af_bella` - Female, US English
- `af_sarah` - Female, US English
- `en_male_jomboy` - Male, US English
- `en_us_001` - US English (neutral)
- `en_us_002` - US English (neutral)

## Tips

1. **Keep videos short** - Start with shorter durations to test faster
2. **Check API keys** - Make sure PEXELS_API_KEY and GEMINI_API_KEY are set in your environment
3. **Monitor progress** - Use the test script's monitoring feature to see real-time progress
4. **Check output** - Generated videos are saved to `video-processor/output/<job_id>/`
