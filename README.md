# AI Video Generator - Enterprise Edition

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

### 🚀 **Enterprise Capabilities**
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
├── cat-video-creator/
│   ├── backend/              # FastAPI server with enterprise features
│   │   ├── vendors/          # Vendored MoneyPrinter & Brainrot backends
│   │   ├── tests/            # Comprehensive test suite
│   │   ├── database.py       # SQLite/PostgreSQL job persistence
│   │   ├── caching.py        # Multi-level caching system
│   │   ├── metrics.py        # Prometheus metrics collection
│   │   ├── job_queue.py      # Redis-based job queue
│   │   ├── batch_processing.py  # Bulk operation orchestration
│   │   └── thumbnail_generator.py  # Video preview generation
│   └── frontend/             # React + TypeScript + Tailwind UI
├── docker-compose.yml        # Production deployment
├── .github/workflows/        # CI/CD automation
└── requirements.txt          # Python dependencies
```

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-repo/ai-video-generator.git
cd ai-video-generator

# Start all services (includes Redis for enhanced features)
docker-compose up --build

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8080
# Metrics: http://localhost:9090
```

### Option 2: Development Setup

#### Prerequisites
- **Python 3.10+** with pip
- **Node.js 18+** with npm
- **FFmpeg** (for video processing)
- **espeak-ng** (for TTS generation)
  - macOS: `brew install espeak-ng`
  - Ubuntu/Debian: `sudo apt install espeak-ng`
  - Windows: Download from [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases)
- **Redis** (optional, for enhanced performance)
#### Backend Setup
```bash
cd cat-video-creator/backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r ../../requirements.txt

# Start the server
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

#### Frontend Setup
```bash
cd cat-video-creator/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root (canonical location). The backend also supports optional overrides from `cat-video-creator/backend/.env` and `cat-video-creator/backend/vendors/moneyprinter/.env` if present.

```bash
# === Required for Video Generation ===
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
curl -H "X-API-Key: your-secret-key" http://localhost:8080/api/health
```

#### Single Video Generation
```bash
# MoneyPrinter workflow
curl -X POST http://localhost:8080/api/moneyprinter/generate \
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
curl -X POST http://localhost:8080/api/batch \
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
curl -X POST http://localhost:8080/api/batch/{batch_id}/start \
  -H "X-API-Key: your-key"

# Monitor progress
curl http://localhost:8080/api/batch/{batch_id} \
  -H "X-API-Key: your-key"
```

#### Thumbnail Generation
```bash
# Generate thumbnails for completed video
curl -X POST http://localhost:8080/api/videos/{job_id}/thumbnails \
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
curl http://localhost:8080/api/health

# Detailed metrics
curl http://localhost:8080/api/metrics/stats

# Cache performance
curl http://localhost:8080/api/cache/stats
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

#### Video Generation Fails
```bash
# Check API keys
curl http://localhost:8080/api/health

# Verify FFmpeg installation
ffmpeg -version

# Check logs
docker-compose logs backend
```

#### Performance Issues
```bash
# Monitor resource usage
curl http://localhost:8080/api/metrics/stats

# Check cache performance
curl http://localhost:8080/api/cache/stats

# Optimize cache settings
curl -X POST http://localhost:8080/api/cache/clear
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
cd cat-video-creator/backend

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

| Concurrent Jobs | RAM Required | CPU Cores | Redis Memory |
|----------------|--------------|-----------|--------------|
| 1-5 jobs | 4GB | 2 cores | 512MB |
| 5-20 jobs | 8GB | 4 cores | 1GB |
| 20-50 jobs | 16GB | 8 cores | 2GB |
| 50+ jobs | 32GB+ | 16+ cores | 4GB+ |

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
