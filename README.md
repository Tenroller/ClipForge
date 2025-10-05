# AI Video Generator

## Authentication

This application now includes user authentication to protect the video generation features.

### Demo Accounts

- **Username:** `admin` / **Password:** `admin123`
- **Username:** `demo` / **Password:** `demo123`

### How Authentication Works

1. **Landing Page**: Users first see a landing page with information about the application
2. **Login Required**: To access video generation tools, users must login
3. **JWT Tokens**: Authentication uses JWT tokens stored in localStorage
4. **Protected Routes**: All video generation endpoints require authentication
5. **Session Management**: Users stay logged in until they logout or the token expires

### API Endpoints

#### Authentication Endpoints
- `POST /api/auth/login` - Login with username/password
- `POST /api/auth/logout` - Logout (client-side)
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/verify` - Verify token validity

#### Protected Endpoints
All video generation endpoints now require authentication:
- `POST /api/moneyprinter/generate`
- `POST /api/brainrot/generate`
- `GET /api/jobs`
- `POST /api/jobs/{job_id}/cancel`
- And all other job management endpoints

### Running the Application

1. **Backend**: `uvicorn app:app --host 0.0.0.0 --port 9000 --reload`
2. **Frontend**: `npm run dev` (serves on port 5173)

The frontend will automatically redirect unauthenticated users to login. with Cloud GPU Support

An AI-powered video generation platform that supports both local processing and cloud GPU acceleration via Modal. - Enterprise Edition

[![CI/CD](https://github.com/your-repo/ai-video-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/your-repo/ai-video-generator/actions)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **🚀 Enterprise-grade AI video generation platform with advanced scaling, monitoring, and batch processing capabilities.**

A comprehensive, production-ready platform for generating short-form videos through multiple AI-powered workflows. Features horizontal scaling, advanced caching, real-time monitoring, and enterprise-grade reliability.

## ✨ Key Features

### 🎬 **Dual Video Generation Workflows**
- **MoneyPrinter Flow**: AI script generation + stock footage + subtitles + optional music
- **Brainrot Flow**: TikTok-style compilation videos from YouTube URLs
- **Unified Interface**: Single UI for both workflows with live progress tracking
 - **Simplified YouTube Handling**: Centralized `backend/utils/youtube.py` utility (ID extraction & download) reduces duplicated yt-dlp logic

### 🚀 **Enterprise Capabilities**
- **Cloud GPU Acceleration**: Modal integration for 10x faster processing with L40S/A100/H100 GPUs
- **Hybrid Processing**: Seamless switching between local and cloud GPU execution
- **Cost Optimization**: Automatic fallback to local processing with usage monitoring
- **Horizontal Scaling**: Redis-based job queue with worker distribution
- **Advanced Caching**: Multi-level caching (Memory/Redis/File) for 60-90% performance improvement
- **Batch Processing**: Bulk video generation with configurable concurrency
- **Real-time Monitoring**: Prometheus metrics with Grafana dashboards
- **Professional Thumbnails**: Automatic preview generation with multiple formats
- **High Availability**: Database persistence, automatic failover, comprehensive logging

### 📊 **Production Features**
- **API Authentication**: Optional API key protection for all endpoints
- **Rate Limiting**: Configurable per-IP request limiting
- **Error Tracking**: Sentry integration for production monitoring
- **Docker Ready**: Complete containerization with docker-compose
- **CI/CD Pipeline**: Automated testing and deployment workflows
- **Comprehensive Testing**: 30+ test cases covering all functionality

## 🏗️ Architecture

```
ai-video-generator/
├── backend/                  # FastAPI server with enterprise features
│   ├── vendors/              # Vendored MoneyPrinter & Brainrot backends
│   ├── tests/                # Comprehensive test suite
│   ├── modal_config.py       # Modal GPU cloud configuration
│   ├── modal_gpu_functions.py# GPU-accelerated processing functions
│   ├── modal_service.py      # Cloud GPU service layer
│   ├── modal_integration.py  # Sync wrappers for existing code
│   ├── database.py           # PostgreSQL job persistence (MANDATORY)
│   ├── caching.py            # Multi-level caching system
│   ├── metrics.py            # Prometheus metrics collection
│   ├── job_queue_unified.py  # Unified job queue system
│   ├── batch_processing.py   # Bulk operation orchestration
│   └── thumbnail_generator.py# Video preview generation
├── frontend/                 # React + TypeScript + Tailwind UI
├── docker/                   # Dockerfiles and compose
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── docker-compose.yml
│   └── init-db.sql           # PostgreSQL database initialization
├── .github/workflows/        # CI/CD automation
├── deploy_modal.py           # Modal deployment script
├── MODAL_GPU_SETUP.md        # Cloud GPU setup guide
└── requirements.txt          # Python dependencies
```

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-repo/ai-video-generator.git
cd ai-video-generator

# Start all services (includes Redis for enhanced features)
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
- **espeak-ng** (for TTS generation)
  - macOS: `brew install espeak-ng`
  - Ubuntu/Debian: `sudo apt install espeak-ng`
  - Windows: Download from [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases)
- **Redis** (optional, for enhanced performance)

#### TTS/Kokoro notes

- We pin Kokoro in `requirements.txt` to `kokoro==0.7.16` to ensure wheels are available on macOS ARM and CI. This provides `KPipeline` used by the app.
- If you prefer the newer API (e.g., `kokoro>=0.9.2` as in the example below) and your platform has wheels or you can build from source, you can bump locally:

```bash
pip install 'kokoro>=0.9.2' soundfile
# macOS
brew install espeak-ng
# Ubuntu/Debian
sudo apt-get -y install espeak-ng
```

Example usage for reference:

```python
from kokoro import KPipeline
pipeline = KPipeline(lang_code='a')
for i, (gs, ps, audio) in enumerate(pipeline("Hello", voice='af_heart')):
    pass
```

## ♻️ Job Resumption & Partial Continuation

The system supports resuming failed or cancelled jobs with linkage metadata and (early) partial step continuation.

### How It Works
- Each job persists: function name, args, kwargs, priority.
- Resume metadata columns: `resumed_from`, `resumed_to` (list), `resume_attempt`, plus per-job `resume_data` JSON (e.g. `{start_step: 'script_generation'}`).
- `POST /api/jobs/{job_id}/resume` creates a new queued job if original status is `error` or `cancelled`.
- The frontend now calls this endpoint from `JobManager.resumeJob` and registers the new job locally.

### Partial Continuation (Current State)
- MoneyPrinter: new job records a `start_step` but currently replays pipeline from that step when full extraction is implemented (stub logic until full migration of legacy steps).
- Brainrot: if parent failed after `process_video`, resume logs skip of that phase (clip reuse not yet implemented) and proceeds to `generate_compilations` (placeholder path).

### Inspecting Resume Metadata
```
GET /api/jobs/{job_id}
{
  "resumed_from": "<parent-id>",
  "resumed_to": ["<child-id>", ...],
  "resume_attempt": 2,
  "resume_data": {"start_step": "script_generation", ...}
}
```

### Migration Script
Development environments can add resume columns without Alembic:
```
python -m backend.migrations.001_add_resume_columns
```
This script is idempotent and safe to re-run.

### Artifact Persistence (Early)
Lightweight JSON artifacts are written under `output/<job_id>/artifacts/`:

- MoneyPrinter: `script_generation/script.json`, `search_terms/terms.json` (more to follow)
- Brainrot: `process_video/clips.json` (clip manifest reused on resume)

Each job also has an `artifacts/manifest.json` indexing persisted step keys.

On resume, if `resume_data.start_step` is beyond an artifact-producing step, the system attempts to load that artifact instead of recomputing it.

### Resume Attempt Limits
Config value: `VIDEOHELPER_MAX_RESUME_ATTEMPTS` (default 5) — counts original attempt as 1. Further resume requests after the limit return 400 with a descriptive error.

### Lineage Endpoint
`GET /api/jobs/{id}/lineage` returns ancestry & descendant graph:
```json
{
  "jobId": "<current>",
  "ancestors": [ {"id": "root-job", "resume_attempt": 1}, ... ],
  "descendants": [ {"id": "child-job", "resume_attempt": 2}, ... ],
  "ancestor_count": 1,
  "descendant_count": 2
}
```
This powers future UI visualization (frontend now exposes `fetchJobLineage`).

### Frontend Lineage Visualization
On the Job Monitoring page, a new Lineage panel displays:
- Ancestor chain (root job to current) with resume attempt numbers.
- Descendant jobs (all resumed children) with status and attempt badges.
- Manual refresh & force refresh (bypass 30s cache) controls.
- Quick navigation: clicking any job ID jumps to its monitoring page; copy icon copies the full ID.

This helps trace retry chains, diagnose repeated failures, and confirm resume attempt limits. Data is sourced directly from the lineage endpoint above.

### Upcoming Enhancements
- Additional MoneyPrinter step artifacts (stock downloads, subtitles, final composition)
- True partial skip for MoneyPrinter beyond script/search terms
- Frontend lineage graph component
- Artifact inspection panel in UI

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

# Configure environment
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
```

#### Cloud GPU Setup (Optional)

To enable cloud GPU acceleration via Modal:

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

**Benefits of Cloud GPU acceleration:**
- 🚀 **10x faster processing** with L40S, A100, or H100 GPUs
- 💰 **Pay-per-use** - only charged for actual GPU time
- 🌐 **No local GPU required** - works on any machine
- 🔄 **Automatic fallback** to local processing if Modal is unavailable

See `MODAL_GPU_SETUP.md` for detailed configuration and cost information.

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root (canonical location). The backend also supports optional overrides from `backend/.env` and `backend/vendors/moneyprinter/.env` if present.

```bash
# === REQUIRED ===
# PostgreSQL Database (MANDATORY)
DATABASE_URL=postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper

# AI Service Keys (at least one required)
PEXELS_API_KEY=your_pexels_api_key
GOOGLE_API_KEY=your_google_api_key
# OR
GEMINI_API_KEY=your_gemini_api_key

# === Security & API ===
API_KEY=your_secret_api_key          # Optional: Protect endpoints
CORS_ALLOW_ORIGINS=*                 # Comma-separated origins
RATE_LIMIT_PER_MINUTE=60            # Optional: Rate limiting

# === Enhanced Features ===
REDIS_URL=redis://localhost:6379/0  # Job queue & caching
ENABLE_METRICS=true                  # Prometheus metrics
METRICS_PORT=9090                    # Metrics server port

# === Monitoring & Logging ===
SENTRY_DSN=your_sentry_dsn          # Error tracking
LOG_LEVEL=INFO                       # DEBUG, INFO, WARNING, ERROR

# === Storage & Performance ===
VIDEOHELPER_OUTPUT_DIR=./output     # Video output directory
MAX_CONCURRENT_JOBS=4               # Concurrent processing limit
CACHE_DIR=./cache                   # File cache directory
MAX_CACHE_SIZE_GB=5                 # Cache size limit
```

## 📋 Usage Guide

### 🎬 Web Interface

1. **Access the App**: Open http://localhost:5173
2. **Choose Workflow**: Select MoneyPrinter or Brainrot tab
3. **Configure Parameters**: Fill in video subject, voice, quality settings
4. **Generate Video**: Submit and watch real-time progress
5. **Download Results**: Access generated videos, thumbnails, and previews

### Generated Content
- **Videos**: Final MP4 files with subtitles
- **Thumbnails**: Multiple sizes (320x180, 160x90, 80x45)
- **Previews**: Animated GIFs and contact sheets
- **Metadata**: Job details, processing logs, performance metrics

### 🔧 API Usage

#### Authentication
```bash
# All requests require API key header (if API_KEY is set)
curl -H "X-API-Key: your-secret-key" http://localhost:9000/api/health
```

#### Single Video Generation
```bash
# MoneyPrinter workflow
curl -X POST http://localhost:9000/api/moneyprinter/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "videoSubject": "Amazing space discoveries",
    "aiModel": "gemini-2.0-flash",
    "voice": "af_bella",
    "paragraphNumber": 2,
    "useMusic": true
  }'
```

#### Batch Processing
```bash
# Create a batch of videos
curl -X POST http://localhost:9000/api/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{
    "name": "Science Video Series",
    "workflow": "moneyprinter", 
    "job_parameters": [
      {"videoSubject": "Quantum Physics"},
      {"videoSubject": "Climate Change"},
      {"videoSubject": "Space Exploration"}
    ],
    "max_concurrent": 2,
    "priority": "high"
  }'

# Start batch processing
curl -X POST http://localhost:9000/api/batch/{batch_id}/start \
  -H "X-API-Key: your-key"

# Monitor progress
curl http://localhost:9000/api/batch/{batch_id} \
  -H "X-API-Key: your-key"
```

#### Thumbnail Generation
```bash
# Generate thumbnails for completed video
curl -X POST http://localhost:9000/api/videos/{job_id}/thumbnails \
  -H "X-API-Key: your-key"
```

## 🔧 API Reference

### Core Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health status |
| `/api/models` | GET | Available AI models |
| `/api/voices` | GET | Available TTS voices |
| `/api/jobs/{id}` | GET | Job status and progress |
| `/api/jobs/{id}/cancel` | POST | Cancel running job |
| `/api/jobs` | GET | List jobs with filtering |
| `/api/jobs/stats` | GET | Job statistics |

### Video Generation
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/moneyprinter/generate` | POST | AI script + stock footage |
| `/api/brainrot/generate` | POST | YouTube compilation videos |
| `/api/videos/{id}/thumbnails` | POST | Generate video previews |

### Batch Processing
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/batch` | POST | Create new batch |
| `/api/batch/{id}/start` | POST | Start batch processing |
| `/api/batch/{id}` | GET | Batch status and progress |
| `/api/batch/{id}/results` | GET | Detailed batch results |
| `/api/batch/{id}/cancel` | POST | Cancel batch |
| `/api/batches` | GET | List all batches |
| `/api/batch/template` | POST | Create from template |

### System Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/metrics` | GET | Prometheus metrics |
| `/api/metrics/stats` | GET | Metrics summary |
| `/api/cache/stats` | GET | Cache performance |
| `/api/cache/clear` | POST | Clear cache levels |

### File Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/download` | GET | Download generated files |
| `/api/list-videos` | GET | List videos in directory |

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
- **Endpoint**: http://localhost:9090/metrics
- **Format**: Prometheus text format
- **Includes**: Request rates, job metrics, system resources, cache performance

### Key Metrics to Monitor
1. **Request Latency**: >5s requests indicate performance issues
2. **Job Queue Length**: High queue depth indicates bottlenecks
3. **Error Rates**: >5% error rate requires investigation
4. **Resource Usage**: >80% memory/disk usage needs attention
5. **Cache Hit Rates**: <70% hit rate suggests cache tuning needed

## 🔧 Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check PostgreSQL connectivity
psql postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper -c "SELECT version();"

# Check database tables
psql postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper -c "\dt"

# View recent jobs
psql postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper -c "SELECT id, status, workflow, created_at FROM jobs ORDER BY created_at DESC LIMIT 5;"
```

#### Video Generation Fails
```bash
# Check API keys and database
curl http://localhost:9000/api/health

# Verify FFmpeg installation
ffmpeg -version

# Check logs
docker-compose logs backend
```

#### Performance Issues
```bash
# Monitor resource usage
curl http://localhost:9000/api/metrics/stats

# Check cache performance
curl http://localhost:9000/api/cache/stats

# Optimize cache settings
curl -X POST http://localhost:9000/api/cache/clear

# Check PostgreSQL performance
psql postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper -c "SELECT * FROM pg_stat_activity;"
```

#### Redis Connection Issues
```bash
# Test Redis connectivity
redis-cli ping

# Check Redis logs
docker-compose logs redis

# Fallback mode still works without Redis
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
pytest tests/test_api.py          # API tests
pytest tests/test_enhanced_features.py  # Enhanced features
pytest tests/test_models.py       # Data validation
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

For production deployments, consider these PostgreSQL optimizations:

```sql
-- Increase connection pool size
ALTER SYSTEM SET max_connections = 200;

-- Optimize for the workload
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';

-- Enable query logging for monitoring
ALTER SYSTEM SET log_statement = 'ddl';
ALTER SYSTEM SET log_duration = on;
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **MoneyPrinter**: Original AI video generation workflow
- **Brainrot**: YouTube compilation video processing
- **FastAPI**: Modern Python web framework
- **React + TypeScript**: Frontend framework
- **Redis**: High-performance data store
- **Prometheus**: Monitoring and alerting toolkit

---

**🚀 Ready to scale your video generation to enterprise levels!**

*Built with ❤️ by the AI Video Generator team*
