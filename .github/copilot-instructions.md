# AI Coding Agent Instructions for AI Video Generator

## Project Overview
- **Enterprise-grade AI video generation platform** supporting dual workflows: MoneyPrinter (script + stock footage) and Brainrot (YouTube compilations).
- **Backend:** FastAPI (Python), PostgreSQL, Redis (optional), modular service layer, unified job queue, centralized logging.
- **Frontend:** React + TypeScript + Tailwind, shadcn/ui, Vite, Nginx for production.
- **Docker:** Multi-container setup for backend, frontend, database, and cache.

## Key Architectural Patterns
- **Service Layer:** Business logic in `backend/services/`, accessed by API routes in `backend/api/routes/`.
- **Job Queue:** Centralized in `backend/job_queue_unified.py` for all workflows.
- **Database:** PostgreSQL for job persistence (`backend/database.py`).
- **Logging:** Use `backend/logging_config.py` for all logging; prefer structured logs and job-specific events.
- **YouTube Handling:** Use `backend/utils/youtube.py` for all YouTube ID extraction and downloads (avoid duplicating yt-dlp logic).

## Developer Workflows
- **Run Backend:** `uvicorn app:app --host 0.0.0.0 --port 9000 --reload` (from `backend/`)
- **Run Frontend:** `npm run dev` (from `frontend/`)
- **Docker Compose:** `docker compose -f docker-compose.yml up --build -d`
- **Tests:** Backend tests in `backend/tests/` (use pytest, FastAPI test client, realistic API/video scenarios)
- **Authentication:** All video generation endpoints require JWT login; see `/api/auth/*` endpoints.

## API Conventions
- **Base URL:** `http://localhost:9000/api/`
- **Authentication:** JWT via localStorage (frontend) or `X-API-Key` header (optional, backend)
- **Endpoints:**
  - `/api/moneyprinter/generate` (MoneyPrinter)
  - `/api/brainrot/generate` (Brainrot)
  - `/api/jobs`, `/api/jobs/{job_id}/cancel` (Job management)
- **Error Handling:** Use FastAPI exceptions; log errors with context.

## Project-Specific Patterns
- **Frontend:** Use shadcn/ui components from `frontend/src/components/components/ui/`. Organize pages in `frontend/src/pages/`.
- **Backend:** Use Pydantic models for requests/responses in `backend/models/`. Keep business logic out of route handlers.
- **Video Engines:** MoneyPrinter logic in `backend/vendors/AIvideos/`, Brainrot in `backend/vendors/Compilation/`.
- **Testing:** Place all tests in `backend/tests/`; use fixtures for sample videos and mock responses.

## Integration Points
- **Cloud GPU:** Modal integration for cloud acceleration (see backend config).
- **External APIs:** Pexels (stock footage), Google/Gemini (AI script), yt-dlp (YouTube download).
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
