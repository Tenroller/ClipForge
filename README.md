# ClipForge - Enterprise Edition

[![CI/CD](https://github.com/your-repo/ai-video-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/your-repo/ai-video-generator/actions)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **🚀 Enterprise-grade AI video generation platform with advanced scaling, monitoring, and multi-workflow processing capabilities.**

A comprehensive, production-ready platform for generating short-form videos through multiple AI-powered workflows. Features horizontal scaling, advanced caching, real-time monitoring, speaker diarization, face tracking, and enterprise-grade reliability.

## ✨ Key Features

### 🎬 **Triple Video Generation Workflows**

1. **MoneyPrinter Flow** - AI script generation + stock footage + subtitles
   - AI-powered script generation from any topic
   - Automatic stock video search and download (Pexels)
   - Text-to-speech with multiple voices (Kokoro TTS)
   - Word-level subtitle animation
   - Optional background music integration

2. **Brainrot Flow** - TikTok-style compilation videos
   - YouTube video download and scene detection
   - Automatic splitting into viral moments
   - Compilation video creation with custom durations
   - Optional background video overlay
   - Optimized for social media (9:16 format)

3. **PodcastClips Flow** - **NEW!** Viral podcast highlights
   - AI-powered viral moment detection
   - **Speaker diarization** - Identify "who speaks when"
   - **Advanced face tracking** - Multi-person face recognition & tracking
   - **Gaze detection** - Identify attention-grabbing moments
   - Automatic 9:16 cropping with intelligent framing
   - Generate 5-10 optimized clips per podcast
   - Perfect for TikTok, Instagram Reels, YouTube Shorts

### 🎯 **Advanced AI Features**

- **Speaker Diarization (Phase 1 & 2)**
  - Identify and label different speakers in podcast content
  - Track speaker transitions for better clip boundaries
  - Provide speaker context to AI for improved moment detection
  - Support for multi-speaker podcasts

- **Face Tracking & Recognition**
  - Real-time face detection and tracking
  - Multi-person face recognition
  - Intelligent camera framing based on active speaker
  - Gaze detection for engagement analysis
  - Robust handling of occlusions and rapid movements

- **Content Intelligence**
  - AI-powered viral moment detection
  - Hook optimization for maximum engagement
  - Automated thumbnail generation with AI-suggested text
  - Clip scoring based on virality potential
  - Audio-visual fusion analysis

### 🌐 **Internationalization**

- **Multi-language Support** - English (EN) and Portuguese (PT-BR)
- Comprehensive i18n for all UI components
- Protected pages and dynamic content translation
- Easy extension for additional languages

### 🚀 **Enterprise Capabilities**

- **Cloud GPU Acceleration** - Modal integration for 10x faster processing with L40S/A100/H100 GPUs
- **Hybrid Processing** - Seamless switching between local and cloud GPU execution
- **Cost Optimization** - Automatic fallback to local processing with usage monitoring
- **Horizontal Scaling** - Redis-based job queue with worker distribution
- **Advanced Caching** - Multi-level caching (Memory/Redis/File) for 60-90% performance improvement
- **Batch Processing** - Bulk video generation with configurable concurrency
- **Real-time Monitoring** - Prometheus metrics with Grafana dashboards
- **Professional Thumbnails** - Automatic preview generation with multiple formats
- **High Availability** - PostgreSQL persistence, automatic failover, comprehensive logging

### 📊 **Production Features**

- **JWT Authentication** - Secure user authentication with token-based sessions
- **API Authentication** - Optional API key protection for all endpoints
- **Rate Limiting** - Configurable per-IP request limiting
- **Error Tracking** - Sentry integration for production monitoring
- **Docker Ready** - Complete containerization with docker-compose
- **CI/CD Pipeline** - Automated testing and deployment workflows
- **Comprehensive Testing** - 30+ test cases covering all functionality

### 🔄 **Job Management**

- **Job Resume & Recovery** - Resume failed or cancelled jobs from the last successful step
- **Artifact Persistence** - Save intermediate results for faster resume
- **Lineage Tracking** - Visualize job ancestry and resume attempts
- **Progress Tracking** - Real-time status updates with detailed logs
- **Auto-registration** - Videos automatically added to gallery on completion

## 🏗️ Architecture

### Tech Stack

- **Backend:** FastAPI (Python 3.10+), PostgreSQL (mandatory), Redis (optional), SQLAlchemy ORM
- **Frontend:** React 18 + TypeScript + Vite, Tailwind CSS, shadcn/ui components, i18next
- **Video Processing:** MoviePy, FFmpeg, OpenCV, yt-dlp
- **AI/ML:** Google Gemini (script generation), Kokoro TTS, Whisper (ASR), pyannote-audio (speaker diarization)
- **Infrastructure:** Docker, Prometheus metrics, JWT authentication

### Project Structure

```
ai-video-generator/
├── backend/                      # FastAPI server with enterprise features
│   ├── api/                      # API endpoint modules
│   │   └── routes/
│   │       ├── health.py         # Health checks
│   │       ├── video_generation.py   # MoneyPrinter, Brainrot, PodcastClips endpoints
│   │       ├── job_management.py     # Job CRUD and monitoring
│   │       ├── job_callbacks.py      # Job completion handling
│   │       ├── system.py         # System management (metrics, cache)
│   │       └── videos.py         # Video file operations
│   ├── services/                 # Business logic layer
│   │   ├── video_orchestrator.py # Multi-workflow orchestration
│   │   ├── video_generation.py   # Video generation services
│   │   ├── job_management.py     # Job lifecycle management
│   │   └── thumbnail_service.py  # Thumbnail generation
│   ├── models/
│   │   └── requests.py           # Pydantic request/response models
│   ├── middleware/
│   │   └── auth.py               # JWT authentication middleware
│   ├── utils/                    # Shared utilities
│   │   ├── youtube.py            # Centralized YouTube operations (ID extraction & download)
│   │   ├── error_handling.py     # Standardized error handling
│   │   ├── paths.py              # Path management
│   │   ├── gpu_manager.py        # GPU resource management
│   │   ├── ffmpeg_utils.py       # FFmpeg operations
│   │   ├── artifacts.py          # Job artifact persistence
│   │   └── cache_manager.py      # Multi-level caching
│   ├── vendors/                  # Third-party video engines
│   │   ├── AIvideos/             # MoneyPrinter workflow implementation
│   │   └── Compilation/          # Brainrot workflow implementation
│   ├── database.py               # PostgreSQL job persistence (mandatory)
│   ├── job_queue_unified.py      # Unified job queue system
│   ├── logging_config.py         # Centralized structured logging
│   ├── metrics.py                # Prometheus metrics collection
│   └── migrations/               # Database migration scripts
├── video-processor/              # Dedicated video processing service
│   ├── vendors/
│   │   └── PodcastClips/         # PodcastClips workflow implementation
│   │       ├── speaker_diarization.py  # Speaker identification
│   │       ├── face_tracker.py         # Face detection & tracking
│   │       ├── face_recognition.py     # Multi-person recognition
│   │       ├── gaze_detection.py       # Attention analysis
│   │       ├── content_detector.py     # Viral moment detection
│   │       ├── clip_generator.py       # Clip creation
│   │       └── processor.py            # Main workflow orchestrator
│   └── utils/                    # Processing utilities
├── frontend/                     # React + TypeScript + Tailwind UI
│   ├── src/
│   │   ├── pages/
│   │   │   ├── MoneyPrinter.tsx  # MoneyPrinter workflow UI
│   │   │   ├── Brainrot.tsx      # Brainrot workflow UI
│   │   │   ├── PodcastClips.tsx  # PodcastClips workflow UI (NEW)
│   │   │   ├── JobMonitoring.tsx # Job status & lineage tracking
│   │   │   ├── VideoGallery.tsx  # Video management & playback
│   │   │   └── Login.tsx         # Authentication
│   │   ├── components/ui/        # shadcn/ui components
│   │   ├── hooks/                # Custom React hooks
│   │   └── i18n/                 # Internationalization (EN, PT-BR)
│   └── package.json
├── docker/                       # Docker configuration
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
├── .env                          # Environment configuration (canonical)
├── CLAUDE.md                     # Developer documentation for Claude Code
└── requirements.txt              # Python dependencies
```

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-repo/ai-video-generator.git
cd ai-video-generator

# Start all services (includes PostgreSQL, Redis)
docker compose -f docker/docker-compose.yml up --build

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:9000
# Metrics: http://localhost:9090
```

### Option 2: Development Setup

#### Prerequisites

- **Python 3.10+** with pip
- **Node.js 18+** with npm
- **PostgreSQL 15+** (MANDATORY - for job persistence)
  - macOS: `brew install postgresql`
  - Ubuntu/Debian: `sudo apt install postgresql postgresql-contrib`
  - Windows: Download from [PostgreSQL website](https://www.postgresql.org/download/)
- **FFmpeg** (for video processing)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html)
- **espeak-ng** (for TTS generation)
  - macOS: `brew install espeak-ng`
  - Ubuntu/Debian: `sudo apt install espeak-ng`
  - Windows: Download from [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases)
- **Redis** (optional, for enhanced performance)
  - macOS: `brew install redis`
  - Ubuntu/Debian: `sudo apt install redis-server`

#### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r ../requirements.txt

# Set up PostgreSQL database
# Option 1: Using Docker (recommended)
docker run -d \
  --name videohelper_postgres \
  -e POSTGRES_DB=videohelper \
  -e POSTGRES_USER=videohelper_user \
  -e POSTGRES_PASSWORD=videohelper_password \
  -p 5432:5432 \
  postgres:15-alpine

# Option 2: Using local PostgreSQL installation
createdb videohelper
createuser videohelper_user
psql -c "ALTER USER videohelper_user PASSWORD 'videohelper_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE videohelper TO videohelper_user;"

# Configure environment (create .env file in project root)
export DATABASE_URL="postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper"

# Start the server
uvicorn app:app --host 0.0.0.0 --port 9000 --reload
```

#### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Access at http://localhost:5173
```

#### Cloud GPU Setup (Optional)

Enable cloud GPU acceleration via Modal for 10x faster processing:

```bash
# Install Modal
pip install modal

# Authenticate with Modal
python -m modal setup

# Deploy GPU functions
cd backend
python ../deploy_modal.py

# Test the integration
python test_modal_integration.py
```

**Benefits:**

- 🚀 **10x faster processing** with L40S, A100, or H100 GPUs
- 💰 **Pay-per-use** - only charged for actual GPU time
- 🌐 **No local GPU required** - works on any machine
- 🔄 **Automatic fallback** to local processing if Modal is unavailable

See `MODAL_GPU_SETUP.md` for detailed configuration and cost information.

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root (canonical location):

```bash
# === REQUIRED ===
# PostgreSQL Database (MANDATORY)
DATABASE_URL=postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper

# AI Service Keys (at least one required)
PEXELS_API_KEY=your_pexels_api_key          # For stock video search (MoneyPrinter)
GOOGLE_API_KEY=your_google_api_key          # For AI script generation
# OR
GEMINI_API_KEY=your_gemini_api_key

# For speaker diarization (PodcastClips)
HF_TOKEN=your_huggingface_token             # Required for pyannote-audio

# === Security & Authentication ===
JWT_SECRET_KEY=your_secret_jwt_key          # For authentication
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

API_KEY=your_secret_api_key                 # Optional: Additional API protection
CORS_ALLOW_ORIGINS=*                        # Comma-separated origins
RATE_LIMIT_PER_MINUTE=60                   # Optional: Rate limiting

# === Enhanced Features ===
REDIS_URL=redis://localhost:6379/0         # Job queue & caching
ENABLE_METRICS=true                         # Prometheus metrics
METRICS_PORT=9090                           # Metrics server port

# === Monitoring & Logging ===
SENTRY_DSN=your_sentry_dsn                 # Error tracking
LOG_LEVEL=INFO                              # DEBUG, INFO, WARNING, ERROR

# === Storage & Performance ===
VIDEOHELPER_OUTPUT_DIR=./output            # Video output directory
VIDEOHELPER_MAX_CONCURRENT_JOBS=1          # Concurrent processing limit (default: 1)
CACHE_DIR=./cache                          # File cache directory
MAX_CACHE_SIZE_GB=5                        # Cache size limit

# === Job Resume Settings ===
VIDEOHELPER_MAX_RESUME_ATTEMPTS=5          # Maximum resume attempts per job
```

### TTS/Kokoro Notes

- We pin Kokoro to `kokoro==0.7.16` in `requirements.txt` to ensure wheels are available on macOS ARM and CI
- This provides `KPipeline` used by the app
- If you prefer the newer API (`kokoro>=0.9.2`) and your platform has wheels, you can bump locally:

```bash
pip install 'kokoro>=0.9.2' soundfile
```

## 🎯 Usage Guide

### Authentication

The application requires authentication for all video generation features.

**Demo Accounts:**

- **Username:** `admin` / **Password:** `admin123`
- **Username:** `demo` / **Password:** `demo123`

**Authentication Flow:**

1. Navigate to <http://localhost:5173>
2. Login with credentials
3. JWT token stored in localStorage
4. Session persists until logout or token expiration

### 🎬 Web Interface

1. **Login**: Access <http://localhost:5173> and login
2. **Choose Workflow**: Select MoneyPrinter, Brainrot, or PodcastClips tab
3. **Configure Parameters**: Fill in video subject, voice, quality settings
4. **Generate Video**: Submit and watch real-time progress with detailed logs
5. **Monitor Jobs**: Track progress, view lineage, resume failed jobs
6. **Download Results**: Access generated videos from the video gallery

### Generated Content

- **Videos**: Final MP4 files with subtitles (MoneyPrinter, PodcastClips) or compilations (Brainrot)
- **Thumbnails**: Multiple sizes (320x180, 160x90, 80x45) with AI-suggested text
- **Previews**: Animated GIFs and contact sheets
- **Metadata**: Job details, processing logs, speaker information (PodcastClips), performance metrics
- **Artifacts**: Intermediate results saved for job resume capability

## 📋 API Reference

### Authentication Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login with username/password, returns JWT token |
| `/api/auth/logout` | POST | Logout (client-side token removal) |
| `/api/auth/me` | GET | Get current user info |
| `/api/auth/verify` | POST | Verify token validity |

### Video Generation Endpoints (Protected)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/moneyprinter/generate` | POST | AI script + stock footage workflow |
| `/api/brainrot/generate` | POST | YouTube compilation videos workflow |
| `/api/podcastclips/generate` | POST | **NEW!** Viral podcast highlights with speaker diarization |
| `/api/youtube/metadata` | GET | Extract YouTube video metadata without downloading |

### Job Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List jobs with filtering (status, workflow, user) |
| `/api/jobs/{id}` | GET | Get job status and detailed progress |
| `/api/jobs/{id}/cancel` | POST | Cancel running job |
| `/api/jobs/{id}/resume` | POST | **NEW!** Resume failed/cancelled job |
| `/api/jobs/{id}/lineage` | GET | **NEW!** Get job ancestry and descendant graph |
| `/api/jobs/stats` | GET | Job statistics and metrics |

### Video Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/videos` | GET | List videos in gallery |
| `/api/videos/{id}` | GET | Get video details |
| `/api/videos/{id}/thumbnails` | POST | Generate video previews |
| `/api/download` | GET | Download generated files |

### System Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health status |
| `/api/models` | GET | Available AI models |
| `/api/voices` | GET | Available TTS voices |
| `/api/metrics` | GET | Prometheus metrics |
| `/api/metrics/stats` | GET | Metrics summary |
| `/api/cache/stats` | GET | Cache performance |
| `/api/cache/clear` | POST | Clear cache levels |

## 🔧 API Usage Examples

### Authentication

```bash
# Login and get JWT token
curl -X POST http://localhost:9000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "tenroller"}'

# Returns: {"access_token": "eyJhbGc...", "token_type": "bearer"}
```

### MoneyPrinter Workflow

```bash
curl -X POST http://localhost:9000/api/moneyprinter/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "videoSubject": "Amazing space discoveries",
    "aiModel": "gemini-2.0-flash",
    "voice": "af_bella",
    "paragraphNumber": 2,
    "useMusic": true,
    "useTikTokSubtitles": true
  }'
```

### Brainrot Workflow

```bash
curl -X POST http://localhost:9000/api/brainrot/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "youtubeUrl": "https://www.youtube.com/watch?v=VIDEO_ID",
    "compilationLength": 60,
    "addBackgroundVideo": true
  }'
```

### PodcastClips Workflow (NEW!)

```bash
curl -X POST http://localhost:9000/api/podcastclips/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "youtubeUrl": "https://www.youtube.com/watch?v=PODCAST_ID",
    "aiModel": "gemini-2.0-flash",
    "whisperModel": "base",
    "minDuration": 30,
    "maxDuration": 60,
    "maxClipCount": 10,
    "enableSpeakerDiarization": true,
    "enableFaceTracking": true
  }'
```

### Job Resume

```bash
# Resume a failed or cancelled job
curl -X POST http://localhost:9000/api/jobs/{job_id}/resume \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# View job lineage
curl http://localhost:9000/api/jobs/{job_id}/lineage \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## ♻️ Job Resumption & Artifact Persistence

The system supports resuming failed or cancelled jobs with linkage metadata and partial continuation.

### How It Works

- **Persistent State**: Each job persists function name, args, kwargs, and priority
- **Resume Metadata**: `resumed_from`, `resumed_to` (list), `resume_attempt`, plus per-job `resume_data` JSON
- **Smart Resume**: `POST /api/jobs/{job_id}/resume` creates a new queued job from last successful step
- **Artifact Reuse**: Intermediate results saved under `output/<job_id>/artifacts/` for faster resume

### Resume Features by Workflow

**MoneyPrinter:**

- Records `start_step` for partial continuation
- Persists script, search terms, and other intermediate data
- Resumes from last successful step

**Brainrot:**

- Saves clip manifest for reuse
- Skips completed processing phases
- Continues from last failure point

**PodcastClips:**

- Preserves speaker diarization results
- Reuses face tracking data
- Resumes clip generation from last successful clip

### Lineage Tracking

```bash
GET /api/jobs/{id}/lineage
```

Returns ancestry & descendant graph:

```json
{
  "jobId": "<current>",
  "ancestors": [{"id": "root-job", "resume_attempt": 1}],
  "descendants": [{"id": "child-job", "resume_attempt": 2}],
  "ancestor_count": 1,
  "descendant_count": 2
}
```

**Frontend Visualization:**

- Ancestor chain with resume attempt numbers
- Descendant jobs with status badges
- Quick navigation and ID copying
- Manual refresh & force refresh (bypass 30s cache)

### Resume Limits

- **Max Attempts**: Configurable via `VIDEOHELPER_MAX_RESUME_ATTEMPTS` (default: 5)
- **Count Rule**: Original attempt counts as 1
- **Limit Enforcement**: Returns 400 error when limit exceeded

## 📊 Monitoring & Observability

### Health Checks

```bash
# System health
curl http://localhost:9000/api/health

# Detailed metrics
curl http://localhost:9000/api/metrics/stats

# Cache performance
curl http://localhost:9000/api/cache/stats
```

### Prometheus Metrics

- **Endpoint**: <http://localhost:9090/metrics>
- **Format**: Prometheus text format
- **Includes**: Request rates, job metrics, system resources, cache performance

### Key Metrics to Monitor

1. **Request Latency**: >5s requests indicate performance issues
2. **Job Queue Length**: High queue depth indicates bottlenecks
3. **Error Rates**: >5% error rate requires investigation
4. **Resource Usage**: >80% memory/disk usage needs attention
5. **Cache Hit Rates**: <70% hit rate suggests cache tuning needed

## 🔧 Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL connectivity
psql postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper -c "SELECT version();"

# View recent jobs
psql postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper -c "SELECT id, status, workflow, created_at FROM jobs ORDER BY created_at DESC LIMIT 5;"
```

### Video Generation Fails

```bash
# Check API keys and database
curl http://localhost:9000/api/health

# Verify FFmpeg installation
ffmpeg -version

# Check logs
docker-compose logs backend
```

### Speaker Diarization Issues (PodcastClips)

```bash
# Check if HF_TOKEN is set
echo $HF_TOKEN

# Verify pyannote-audio installation
pip show pyannote-audio

# Check model download (requires HuggingFace token)
# Visit: https://huggingface.co/pyannote/speaker-diarization
```

### Performance Issues

```bash
# Monitor resource usage
curl http://localhost:9000/api/metrics/stats

# Check cache performance
curl http://localhost:9000/api/cache/stats

# Check PostgreSQL performance
psql postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper -c "SELECT * FROM pg_stat_activity;"
```

## 🧪 Testing

### Run Test Suite

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test categories
pytest tests/test_api.py                    # API tests
pytest tests/test_enhanced_features.py      # Enhanced features
pytest tests/test_models.py                 # Data validation
pytest tests/test_job_management.py         # Job lifecycle tests
```

## 🎯 Performance Optimization

### Scaling Guidelines

| Concurrent Jobs | RAM Required | CPU Cores | PostgreSQL Memory | Redis Memory |
|----------------|--------------|-----------|-------------------|--------------|
| 1-5 jobs | 4GB | 2 cores | 1GB | 512MB |
| 5-20 jobs | 8GB | 4 cores | 2GB | 1GB |
| 20-50 jobs | 16GB | 8 cores | 4GB | 2GB |
| 50+ jobs | 32GB+ | 16+ cores | 8GB+ | 4GB+ |

### PostgreSQL Optimization

For production deployments:

```sql
-- Increase connection pool size
ALTER SYSTEM SET max_connections = 200;

-- Optimize for the workload
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Developer Documentation

See [CLAUDE.md](CLAUDE.md) for detailed developer documentation including:

- Service layer architecture
- Critical patterns and best practices
- Common development tasks
- Testing guidelines

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **MoneyPrinter**: Original AI video generation workflow
- **Brainrot**: YouTube compilation video processing
- **pyannote-audio**: Speaker diarization capabilities
- **FastAPI**: Modern Python web framework
- **React + TypeScript**: Frontend framework
- **Redis**: High-performance data store
- **Prometheus**: Monitoring and alerting toolkit

---

**🚀 Ready to scale your video generation to enterprise levels!**

For detailed developer documentation and Claude Code integration, see [CLAUDE.md](CLAUDE.md).

*Built with ❤️ by the ClipForge team*
