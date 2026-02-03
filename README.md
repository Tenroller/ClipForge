# ClipForge

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **🎬 AI-powered video generation platform for creating viral short-form content.**

ClipForge is a comprehensive platform for generating short-form videos through multiple AI-powered workflows. Create viral TikTok compilations, podcast highlight clips, and AI-generated content with automatic subtitles, face tracking, and intelligent editing.

## ✨ Features

### 🎯 **Video Generation Workflows**

| Workflow | Description |
|----------|-------------|
| **🎙️ PodcastClips** | Extract viral moments from podcasts with speaker diarization, face tracking, and intelligent cropping |
| **🔥 Compilations** | Create TikTok-style compilation videos from YouTube content with scene detection and smart editing |
| **✨ Creator** | AI-powered video creation with script generation, stock footage, and TTS narration |

### 🚀 **Key Capabilities**

- **AI-Powered Content Detection** - Automatically identify viral-worthy moments using OpenRouter AI
- **Speaker Diarization** - Identify and track different speakers in podcast content
- **Face Tracking & Recognition** - Smart cropping based on active speaker detection
- **Auto-Subtitles** - Word-level subtitle animation with customizable styling
- **9:16 Optimization** - All outputs optimized for TikTok, Instagram Reels, and YouTube Shorts

## 🏗️ Architecture

ClipForge uses a modern microservices architecture with three main components:

```
┌─────────────────────────────────────────────────────────────────┐
│                          ClipForge                               │
├─────────────────┬─────────────────────┬─────────────────────────┤
│   Frontend      │      Backend        │    Video Processor      │
│   (Next.js)     │      (FastAPI)      │      (FastAPI)          │
│   Port 3000     │      Port 9000      │      Port 8090          │
├─────────────────┼─────────────────────┼─────────────────────────┤
│ • React 19      │ • Job Queue         │ • Video Processing      │
│ • App Router    │ • Authentication    │ • AI Integration        │
│ • shadcn/ui     │ • API Gateway       │ • TTS Generation        │
│ • TailwindCSS   │ • PostgreSQL        │ • Subtitle Rendering    │
└─────────────────┴─────────────────────┴─────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16, React 19, TypeScript, TailwindCSS, shadcn/ui |
| **Backend** | FastAPI, Python 3.10+, PostgreSQL, SQLAlchemy |
| **Video Processing** | MoviePy, FFmpeg, OpenCV, yt-dlp |
| **AI/ML** | OpenRouter (GPT-4, Claude), Whisper (ASR), pyannote-audio |
| **Authentication** | JWT-based authentication |

## 📁 Project Structure

```
clipforge/
├── backend/                    # FastAPI backend server (Port 9000)
│   ├── api/                    # API route handlers
│   ├── core/                   # App configuration & lifespan
│   ├── services/               # Business logic layer
│   ├── models/                 # Pydantic models
│   ├── middleware/             # Auth & rate limiting
│   ├── utils/                  # Shared utilities
│   └── database.py             # PostgreSQL persistence
│
├── video-processor/            # Video processing service (Port 8090)
│   ├── src/                    # FastAPI app
│   ├── vendors/                # Workflow implementations
│   │   ├── PodcastClips/       # Podcast highlight extraction
│   │   ├── Compilation/        # TikTok compilation generator
│   │   └── AIvideos/           # AI video creator
│   └── utils/                  # Processing utilities
│
├── frontend/                   # Next.js frontend (Port 3000)
│   └── src/
│       ├── app/                # App Router pages
│       │   ├── (protected)/    # Authenticated routes
│       │   │   ├── podcastclips/
│       │   │   ├── compilations/
│       │   │   ├── creator/
│       │   │   ├── videos/
│       │   │   └── job/
│       │   └── login/
│       └── components/         # React components (shadcn/ui)
│
├── start.sh                    # Start all services (macOS/Linux)
├── start.bat                   # Start all services (Windows)
├── docker-compose.yml          # Docker deployment
└── .env                        # Environment configuration
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** with pip/uv
- **Node.js 18+** with npm
- **PostgreSQL 15+** (required for job persistence)
- **FFmpeg** (required for video processing)

```bash
# macOS
brew install python node postgresql ffmpeg

# Ubuntu/Debian
sudo apt install python3 nodejs postgresql ffmpeg
```

### 1. Clone & Configure

```bash
git clone https://github.com/your-repo/clipforge.git
cd clipforge

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
```

### 2. Set Up Database

```bash
# Option A: Using Docker (recommended)
docker run -d \
  --name clipforge_postgres \
  -e POSTGRES_DB=videohelper \
  -e POSTGRES_USER=videohelper_user \
  -e POSTGRES_PASSWORD=videohelper_password \
  -p 5432:5432 \
  postgres:15-alpine

# Option B: Local PostgreSQL
createdb videohelper
createuser videohelper_user
psql -c "ALTER USER videohelper_user PASSWORD 'videohelper_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE videohelper TO videohelper_user;"
```

### 3. Start Services

```bash
# Start all services with one command
./start.sh

# Services will be available at:
# Frontend:        http://localhost:3000
# Backend API:     http://localhost:9000
# Video Processor: http://localhost:8090
```

### Manual Start (Alternative)

```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 9000 --reload

# Terminal 2: Video Processor
cd video-processor
pip install -r requirements.txt
python main.py

# Terminal 3: Frontend
cd frontend
npm install
npm run dev
```

## ⚙️ Configuration

Create a `.env` file in the project root:

```bash
# ============================================================================
# REQUIRED
# ============================================================================

# OpenRouter API Key (for AI text generation)
# Get your key at: https://openrouter.ai/settings/keys
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Pexels API Key (for stock video search - Creator workflow)
PEXELS_API_KEY=your_pexels_key_here

# PostgreSQL Database
DATABASE_URL=postgresql://videohelper_user:videohelper_password@localhost:5432/videohelper

# ============================================================================
# AUTHENTICATION
# ============================================================================

# JWT Secret (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-secret-key-change-this-in-production

# Demo credentials
AUTH_USERNAME=admin
AUTH_PASSWORD=your-password

# ============================================================================
# OPTIONAL
# ============================================================================

# HuggingFace Token (for speaker diarization - PodcastClips)
HF_TOKEN=your_huggingface_token

# Video processing settings
VIDEOHELPER_MAX_CONCURRENT_JOBS=1
VIDEOHELPER_OUTPUT_DIR=./output

# Service URLs
VIDEO_PROCESSOR_URLS=http://localhost:8090
BACKEND_CALLBACK_URL=http://localhost:9000

# Logging
LOG_LEVEL=INFO
```

## 🎯 Usage

### Web Interface

1. **Login** - Navigate to `http://localhost:3000` and sign in
2. **Choose Workflow** - Select PodcastClips, Compilations, or Creator
3. **Configure** - Set your video parameters and options
4. **Generate** - Submit and monitor real-time progress
5. **Download** - Access generated videos from the gallery

### API Examples

```bash
# Get JWT token
TOKEN=$(curl -s -X POST http://localhost:9000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}' | jq -r '.access_token')

# Generate podcast clips
curl -X POST http://localhost:9000/api/podcastclips/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "youtubeUrl": "https://youtube.com/watch?v=VIDEO_ID",
    "minDuration": 30,
    "maxDuration": 60,
    "maxClipCount": 5
  }'

# Check job status
curl http://localhost:9000/api/jobs/{job_id} \
  -H "Authorization: Bearer $TOKEN"
```

## 📋 API Reference

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login, returns JWT token |
| `/api/auth/me` | GET | Get current user info |

### Video Generation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/podcastclips/generate` | POST | Generate podcast highlight clips |
| `/api/compilations/generate` | POST | Create TikTok compilations |
| `/api/creator/generate` | POST | AI video generation |

### Job Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List all jobs |
| `/api/jobs/{id}` | GET | Get job status |
| `/api/jobs/{id}/cancel` | POST | Cancel job |

### System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/voices` | GET | Available TTS voices |

## 🐳 Docker Deployment

```bash
# Start all services with Docker
docker-compose up --build

# Or with local docker-compose
docker-compose -f docker-compose.local.yml up --build
```

## 🔧 Troubleshooting

### Common Issues

**Database connection failed**
```bash
# Check PostgreSQL is running
psql -h localhost -U videohelper_user -d videohelper -c "SELECT 1;"
```

**FFmpeg not found**
```bash
# Verify installation
ffmpeg -version

# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg
```

**OpenRouter API errors**
```bash
# Verify your API key is set
echo $OPENROUTER_API_KEY

# Test the API
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

**Video processor not responding**
```bash
# Check if service is running
curl http://localhost:8090/health
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**🎬 Ready to create viral content!**

*Built with ❤️ by the ClipForge team*
