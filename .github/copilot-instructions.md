# AI Coding Agent Instructions for ClipForge

## Project Overview
- **Production AI video generation platform** supporting three workflows: MoneyPrinter (AI script + stock footage), Compilations/Brainrot (YouTube compilations), and PodcastClips (podcast segment extraction).
- **Backend:** FastAPI (Python), PostgreSQL, modular service layer, unified job queue, centralized logging.
- **Video Processor:** Separate FastAPI service handling video rendering with vendor engines in `video-processor/vendors/`.
- **Frontend:** Next.js 16 + React + TypeScript + Tailwind, shadcn/ui, App Router.
- **Docker:** Multi-container setup (backend, video-processor, frontend, database).

## Key Architectural Patterns
- **Service Layer:** Business logic in `backend/services/`, accessed by API routes in `backend/api/routes/`.
- **Job Queue:** Centralized in `backend/job_queue_unified.py` for all workflows.
- **Database:** PostgreSQL for job persistence (`backend/database.py`).
- **Logging:** Use `backend/logging_config.py` for all logging; prefer structured logs and job-specific events.
- **YouTube Handling:** Use `backend/utils/youtube.py` for all YouTube ID extraction and downloads (avoid duplicating yt-dlp logic).
- **Video Engines:** MoneyPrinter in `video-processor/vendors/AIvideos/`, Compilation/Brainrot in `video-processor/vendors/Compilation/`, PodcastClips in `video-processor/vendors/PodcastClips/`.

## Developer Workflows
- **Run Backend:** `uvicorn app:app --host 0.0.0.0 --port 9000 --reload` (from `backend/`)
- **Run Frontend:** `npm run dev` (from `frontend/`)
- **Docker Compose:** `docker compose -f docker-compose.yml up --build -d`
- **Authentication:** All video generation endpoints require JWT login via HTTP-only cookies; see `/api/auth/*` endpoints.

## API Conventions
- **Base URL:** `http://localhost:9000/api/`
- **Authentication:** JWT via HTTP-only cookies (frontend) or `X-API-Key` header (optional, backend).
- **Endpoints:**
  - `/api/video/generate` (Video generation — MoneyPrinter, Compilations, PodcastClips)
  - `/api/jobs`, `/api/jobs/{job_id}/cancel` (Job management)
  - `/api/auth/login`, `/api/auth/logout`, `/api/auth/me` (Authentication)
- **Error Handling:** Use FastAPI exceptions; log errors with context.

## Project-Specific Patterns
- **Frontend:** Use shadcn/ui components from `frontend/src/components/ui/`. Organize pages in `frontend/src/app/` using Next.js App Router with route groups (`(protected)/` for authenticated pages).
- **Backend:** Use Pydantic models for requests/responses in `backend/models/`. Keep business logic out of route handlers.
- **Configuration:** Environment-based via `backend/core/config.py`. JWT_SECRET_KEY and AUTH_PASSWORD are required — app refuses to start without them.
- **i18n:** Frontend uses `next-intl` for internationalization.

## Integration Points
- **External APIs:** Pexels (stock footage), OpenRouter/Google (AI text generation), yt-dlp (YouTube download).
- **Environment Variables:** API keys, DB config, TTS voices, etc. (see `backend/core/config.py` and `.env.example`).

## Examples
- **Service Usage:**
  ```python
  from backend.services.video_generation import VideoGenerationService
  service = VideoGenerationService()
  result = service.generate_video(request)
  ```
- **Logging:**
  ```python
  from backend.logging_config import get_logger
  logger = get_logger("video_generation")
  logger.info("Started job", extra={"job_id": job_id})
  ```
- **YouTube Utility:**
  ```python
  from backend.utils.youtube import download_video
  result = download_video(url)
  ```

---
For unclear or missing conventions, consult `README.md`, `.cursor/rules/`, or ask for clarification.
