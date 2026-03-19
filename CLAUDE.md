# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ClipForge is an AI video generation platform with three workflows:
- **MoneyPrinter (AIvideos)** — AI-generated scripts + stock footage from Pexels with TTS narration
- **Compilations (Brainrot)** — YouTube compilation videos with AI clip scoring and scene detection
- **PodcastClips** — Podcast highlight extraction with speaker diarization and face tracking

## Architecture

Three services communicate over HTTP, orchestrated via Docker Compose:

| Service | Stack | Port | Entry Point |
|---------|-------|------|-------------|
| **Backend** | FastAPI + SQLAlchemy + PostgreSQL | 9000 | `backend/app.py` |
| **Video Processor** | FastAPI + MoviePy + Whisper + PyTorch | 8090 | `video-processor/main.py` |
| **Frontend** | Next.js 16 + React 19 + TypeScript + Tailwind | 3000 | `frontend/src/app/layout.tsx` |

**Flow:** Frontend -> Backend (job queue + orchestration) -> Video Processor (rendering) -> callback to Backend on completion.

The backend uses an in-memory job queue (`backend/job_queue_unified.py`) with a ThreadPoolExecutor — no Redis dependency for job processing.

## Common Commands

### Backend (run from `backend/`)
```bash
uvicorn app:app --host 0.0.0.0 --port 9000 --reload     # Dev server
python -m pytest tests/ -v --tb=short                     # All tests
python -m pytest tests/test_auth.py -v                    # Single test file
python -m pytest tests/test_auth.py::test_login -v        # Single test
ruff check backend/                                       # Lint backend
ruff check video-processor/                               # Lint video-processor
```

### Frontend (run from `frontend/`)
```bash
npm run dev       # Dev server (port 3000)
npm run build     # Production build
npm run lint      # ESLint
```

### Docker
```bash
docker compose -f docker-compose.yml up --build -d        # Full stack
docker compose -f docker-compose.local.yml up --build -d  # Local dev
```

## Key Architectural Decisions

- **Service layer pattern:** Business logic lives in `backend/services/`, route handlers in `backend/api/routes/` are thin wrappers.
- **Video vendor engines:** Each workflow has its own directory under `video-processor/vendors/` (AIvideos, Compilation, PodcastClips) — these are self-contained processing pipelines.
- **Auth:** JWT tokens via HTTP-only cookies. `JWT_SECRET_KEY` and `AUTH_PASSWORD` env vars are required — app refuses to start without them.
- **Protected routes:** Frontend uses route group `(protected)/` in the App Router, which wraps authenticated pages.
- **i18n:** Frontend uses `next-intl` for internationalization.
- **UI components:** shadcn/ui (Radix-based) in `frontend/src/components/ui/`.
- **State management:** TanStack React Query for server state.
- **Request models:** Pydantic models in `backend/models/requests.py` (MoneyPrinterRequest, BrainrotRequest, PodcastClipsRequest).
- **Database:** PostgreSQL with schema in `init-db.sql`. Two tables: `jobs` and `videos`. SQLAlchemy ORM in `backend/database.py`.
- **Progress tracking:** Real-time updates via SSE (Server-Sent Events) at `/api/sse/`.
- **Logging:** Structured logging via Loguru (`backend/logging_config.py`).

## Environment

Required env vars (see `.env.example` for full list):
- `JWT_SECRET_KEY`, `AUTH_PASSWORD` — authentication (app won't start without these)
- `PEXELS_API_KEY` — stock footage search
- `OPENROUTER_API_KEY` — AI text generation via OpenRouter
- `DATABASE_URL` — PostgreSQL connection string

## CI/CD

GitHub Actions workflow (`.github/workflows/build.yml`) runs on push/PR to main:
1. Frontend lint (ESLint)
2. Backend lint (Ruff) — covers both `backend/` and `video-processor/`
3. Backend tests (pytest)
4. Docker build verification
5. SonarQube analysis

## Testing

Backend tests use FastAPI's TestClient with mocked database and job queue (see `backend/tests/conftest.py`). Tests set `TESTING=1` and use SQLite. Test env vars are set in conftest, not `.env`.

## Path Aliases

Frontend TypeScript: `@/*` maps to `frontend/src/*`.
