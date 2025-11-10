# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VideoHelper is an enterprise-grade AI video generation platform with dual workflows, cloud GPU acceleration, and comprehensive monitoring capabilities. It combines MoneyPrinter (AI script generation + stock footage) and Brainrot (YouTube compilation videos) workflows into a unified system.

**Tech Stack:**
- **Backend:** FastAPI (Python), PostgreSQL (mandatory), Redis (optional), SQLAlchemy ORM
- **Frontend:** React 18 + TypeScript + Vite, Tailwind CSS, shadcn/ui components
- **Video Processing:** MoviePy, FFmpeg, OpenCV
- **AI/ML:** Google Gemini for script generation, Kokoro TTS, Whisper for ASR
- **Infrastructure:** Docker, Prometheus metrics, JWT authentication

## Development Commands

### Backend Development
```bash
# Start backend server (development mode with auto-reload)
cd backend
uvicorn app:app --host 0.0.0.0 --port 9000 --reload

# Or use the startup script from project root
python run_backend.py

# Run tests
cd backend
pytest                                    # Run all tests
pytest tests/test_api.py                 # Run specific test file
pytest --cov=. --cov-report=html        # Run with coverage
```

### Frontend Development
```bash
cd frontend
npm install          # Install dependencies
npm run dev          # Start dev server (port 5173)
npm run build        # Build for production
npm run preview      # Preview production build
```

### Database Setup
```bash
# Using Docker (recommended for development)
docker run -d \
  --name videohelper_postgres \
  -e POSTGRES_DB=videohelper \
  -e POSTGRES_USER=videohelper_user \
  -e POSTGRES_PASSWORD=videohelper_password \
  -p 5432:5432 \
  postgres:15-alpine

# Or use local PostgreSQL
createdb videohelper
createuser videohelper_user
psql -c "ALTER USER videohelper_user PASSWORD 'videohelper_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE videohelper TO videohelper_user;"

# Run migration scripts (if needed)
python -m backend.migrations.001_add_resume_columns
```

### Docker Commands
```bash
# Full stack deployment
docker compose up --build -d

# Development mode (with hot reload)
docker compose -f docker-compose.dev.yml up --build

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Stop all services
docker compose down
```

### All-in-One Development Start
```bash
# Start all services (frontend, backend, video-processor)
./start.sh          # Linux/macOS
start.bat           # Windows
```

## Architecture

### Backend Structure

The backend follows a **service layer architecture** with clear separation of concerns:

```
backend/
├── app.py                    # FastAPI application factory (main entry point)
├── main.py                   # Application startup
├── database.py               # PostgreSQL job persistence (SQLAlchemy)
├── job_queue_unified.py      # Unified job queue system
├── logging_config.py         # Centralized structured logging
├── metrics.py                # Prometheus metrics
├── validation.py             # Input validation utilities
├── core/
│   └── config.py            # Environment-based configuration
├── api/
│   └── routes/              # API endpoint modules
│       ├── health.py        # Health checks
│       ├── video_generation.py  # MoneyPrinter & Brainrot endpoints
│       ├── job_management.py    # Job CRUD and monitoring
│       ├── system.py        # System management (metrics, cache)
│       └── videos.py        # Video file operations
├── services/                # Business logic layer
│   ├── video_generation.py  # Video generation orchestration
│   ├── job_management.py    # Job lifecycle management
│   ├── thumbnail_service.py # Thumbnail generation
│   └── video_service.py     # Video operations
├── models/
│   └── requests.py          # Pydantic request/response models
├── utils/                   # Shared utilities
│   ├── youtube.py           # YouTube download/extraction (centralized)
│   ├── error_handling.py    # Standardized error handling
│   ├── paths.py             # Path management
│   ├── gpu_manager.py       # GPU resource management
│   ├── ffmpeg_utils.py      # FFmpeg operations
│   ├── artifacts.py         # Job artifact persistence
│   └── cache_manager.py     # Multi-level caching
└── vendors/                 # Third-party video engines
    ├── AIvideos/            # MoneyPrinter workflow implementation
    ├── Compilation/         # Brainrot workflow implementation
    └── fonts/               # Font resources
```

### Frontend Structure

```
frontend/
├── src/
│   ├── main.tsx             # React entry point
│   ├── App.tsx              # Main app with routing
│   ├── pages/               # Application pages
│   │   ├── MoneyPrinter.tsx # MoneyPrinter workflow UI
│   │   ├── Brainrot.tsx     # Brainrot workflow UI
│   │   ├── JobMonitoring.tsx # Job status monitoring
│   │   └── Login.tsx        # Authentication
│   ├── components/
│   │   └── ui/              # shadcn/ui components
│   └── hooks/               # Custom React hooks
├── package.json
└── vite.config.ts
```

### Video Generation Workflows

**MoneyPrinter Flow** (`/api/moneyprinter/generate`):
1. AI script generation from subject (using Gemini)
2. Extract search terms from script
3. Download stock videos from Pexels
4. Generate TTS audio (Kokoro)
5. Create word-level subtitles (using Whisper)
6. Compose final video with MoviePy

**Brainrot Flow** (`/api/brainrot/generate`):
1. Download YouTube video via yt-dlp
2. Scene detection and splitting
3. Create compilation videos with specified duration
4. Optional background video overlay

**Key Implementation Details:**
- Both workflows use `backend/job_queue_unified.py` for async processing
- Job status persisted in PostgreSQL via `backend/database.py`
- YouTube operations centralized in `backend/utils/youtube.py` (always use this, never duplicate yt-dlp logic)
- Video engines in `backend/vendors/AIvideos/` and `backend/vendors/Compilation/`

## Critical Patterns

### Service Layer Pattern
All business logic goes in service classes, **not** in route handlers:

```python
# backend/services/video_generation.py
from backend.logging_config import get_logger
from backend.database import get_job_store
from backend.job_queue_unified import get_job_queue

class VideoGenerationService:
    def __init__(self):
        self.logger = get_logger("video_generation.service")
        self.job_store = get_job_store()
        self.job_queue = get_job_queue()

    def generate_video(self, request: VideoRequest) -> Dict[str, Any]:
        # Business logic here
        job_id = str(uuid.uuid4())
        self.job_store.create_job(job_id, "moneyprinter", request.dict())
        self.job_queue.submit_job(job_id, "moneyprinter", request.dict())
        return {"job_id": job_id, "status": "queued"}
```

### Database Operations
PostgreSQL is **mandatory**. Use the job store pattern:

```python
from backend.database import get_job_store

job_store = get_job_store()
job_store.create_job(job_id, workflow, parameters)
job_store.update_job_progress(job_id, progress=50, status="processing", step="tts_generation")
job = job_store.get_job(job_id)
```

### Logging Pattern
Use centralized logging with structured context:

```python
from backend.logging_config import get_logger, log_job_event

logger = get_logger("module_name")
logger.info("Processing started", extra={"job_id": job_id, "workflow": "moneyprinter"})

# For job-specific events
log_job_event(logger, job_id, workflow, "tts_complete", duration=15.3, voice="af_bella")
```

### Error Handling
Use standardized error handling:

```python
from backend.utils.error_handling import handle_error, VideoHelperError

try:
    result = risky_operation()
except Exception as e:
    error_response = handle_error(e, context={"job_id": job_id, "step": "tts"})
    # Update job status to error
    job_store.update_job_progress(job_id, -1, "error", error_message=str(e))
```

### YouTube Operations
**Always** use the centralized YouTube utility:

```python
from backend.utils.youtube import extract_video_id, download_video

# Extract video ID from URL
video_id = extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# Download video
result = download_video(
    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    output_path="/path/to/output",
    format="best"
)
```

**Never** duplicate yt-dlp logic in workflow code.

### Job Resume & Artifact Persistence
Jobs can be resumed after failure/cancellation:

```python
# Resume a job
POST /api/jobs/{job_id}/resume

# Resume metadata stored in database
{
  "resumed_from": "<parent-job-id>",
  "resumed_to": ["<child-job-id>"],
  "resume_attempt": 2,
  "resume_data": {"start_step": "script_generation"}
}

# Artifacts written to output/<job_id>/artifacts/
# - manifest.json (index of all artifacts)
# - <step_name>/<artifact>.json (step-specific data)
```

Use `backend/utils/artifacts.py` for artifact operations.

## Configuration

Environment variables managed via `backend/core/config.py`:

```python
from backend.core.config import AppConfig

config = AppConfig.from_env()
# Access: config.database_url, config.api_key, config.pexels_api_key, etc.
```

**Required Environment Variables:**
```bash
# Database (MANDATORY)
DATABASE_URL=postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper

# AI Services (at least one required)
PEXELS_API_KEY=your_pexels_api_key
GOOGLE_API_KEY=your_google_api_key  # or GEMINI_API_KEY

# Optional
REDIS_URL=redis://localhost:6379/0
API_KEY=your_secret_api_key         # Optional API protection
CORS_ALLOW_ORIGINS=*
LOG_LEVEL=INFO
```

**Environment File Locations:**
1. `.env` (project root, canonical)
2. `backend/.env` (optional override)
3. `backend/vendors/moneyprinter/.env` (legacy override)

## API Routes

All routes follow REST conventions with `/api` prefix:

**Authentication:**
- `POST /api/auth/login` - Login with username/password
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user info

**Video Generation (requires authentication):**
- `POST /api/moneyprinter/generate` - MoneyPrinter workflow
- `POST /api/brainrot/generate` - Brainrot workflow

**Job Management:**
- `GET /api/jobs` - List jobs (with filtering)
- `GET /api/jobs/{job_id}` - Get job status
- `POST /api/jobs/{job_id}/cancel` - Cancel job
- `POST /api/jobs/{job_id}/resume` - Resume failed/cancelled job
- `GET /api/jobs/{job_id}/lineage` - Get job ancestry/descendants

**System:**
- `GET /api/health` - Health check
- `GET /api/models` - Available AI models
- `GET /api/voices` - Available TTS voices
- `GET /api/metrics` - Prometheus metrics
- `GET /api/cache/stats` - Cache statistics

**Files:**
- `GET /api/download` - Download generated files
- `GET /api/list-videos` - List videos in directory

## Testing

Tests located in `backend/tests/`:
- `test_api.py` - API endpoint tests
- `test_enhanced_features.py` - Enterprise features
- `test_models.py` - Data validation
- `test_job_management.py` - Job lifecycle tests

Use FastAPI test client for API tests:
```python
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_generate_video():
    response = client.post("/api/moneyprinter/generate", json={
        "video_subject": "Amazing space discoveries",
        "ai_model": "gemini-2.0-flash",
        "voice": "af_bella"
    })
    assert response.status_code == 200
    assert "job_id" in response.json()
```

## Common Development Tasks

### Adding a New API Endpoint
1. Define Pydantic models in `backend/models/requests.py`
2. Create service method in appropriate `backend/services/*.py`
3. Add route handler in `backend/api/routes/*.py`
4. Register router in `backend/app.py`
5. Add tests in `backend/tests/`

### Adding a New Video Processing Step
1. Implement logic in vendor directory (`backend/vendors/AIvideos/` or `backend/vendors/Compilation/`)
2. Update job progress via `job_store.update_job_progress()`
3. Log events using `log_job_event()`
4. Persist artifacts using `backend/utils/artifacts.py` if reusable
5. Update frontend UI to show new step in progress tracking

### Working with Database Migrations
Migrations in `backend/migrations/`:
```bash
python -m backend.migrations.001_add_resume_columns
```

Migrations are idempotent and safe to re-run.

## Important Notes

- **PostgreSQL is mandatory** - SQLite removed, all jobs require persistent database
- **Authentication required** - All video generation endpoints require JWT login
- **Use centralized YouTube utility** - Never duplicate yt-dlp logic
- **Follow service layer pattern** - Keep business logic out of route handlers
- **Use structured logging** - Always include job_id and workflow in log context
- **Error handling** - Use standardized error handling utilities
- **Path management** - Use `backend/utils/paths.py` for all path operations
- **Artifact persistence** - Use `backend/utils/artifacts.py` for job artifacts

## GPU & Performance

- **Cloud GPU:** Modal integration for L40S/A100/H100 acceleration (optional)
- **Caching:** Multi-level (Memory/Redis/File) via `backend/utils/cache_manager.py`
- **GPU Management:** Use `backend/utils/gpu_manager.py` for local GPU operations
- **Job Processing:** Sequential processing by default (1 job at a time) for resource-constrained environments
  - Configure via `VIDEOHELPER_MAX_CONCURRENT_JOBS` environment variable
  - Default: 1 (recommended for most deployments)
  - Increase only if you have sufficient CPU/memory/GPU resources

## Authentication

JWT-based authentication with localStorage storage (frontend):
- Demo accounts: `admin/admin123`, `demo/demo123`
- Tokens stored in localStorage
- Protected routes require valid token
- Session persists until logout or token expiration


## Libraries

For libraries documentation use the MCP context7 always