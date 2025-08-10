## AI Video Creator – Integration Plan

### Goals
- Create a new unified app that exposes both existing workflows from a single UI.
- Keep `MoneyPrinter/` and `brainrot-generator/` unchanged.
- Provide a modern React (Vite + TS) frontend using Shadcn UI.
- Provide a Python backend (FastAPI) that orchestrates both workflows.
- Deliver clear UX with workflow selection, progress indicators, and error handling.

### Source Projects Analysis (Summary)
- MoneyPrinter (Python + Flask, simple HTML frontend)
  - Orchestration: `MoneyPrinter/Backend/main.py` exposes `/api/generate` integrating:
    - Script generation: `Backend/gpt.py`
    - Search terms: `Backend/gpt.py:get_search_terms`
    - Stock video search & download: `Backend/search.py`
    - TTS: `Backend/tiktokvoice.py`
    - Subtitles: `Backend/video.py:generate_subtitles`
    - Concatenate videos: `Backend/video.py:combine_videos`
    - Compose final video: `Backend/video.py:generate_video`
    - Optional YouTube upload: `Backend/youtube.py`
  - Relies on env vars: `PEXELS_API_KEY`, `TIKTOK_SESSION_ID`, `IMAGEMAGICK_BINARY`, optional OpenAI.
  - Uses relative paths under `MoneyPrinter/` (e.g., `../temp`, `../subtitles`).

- Brainrot Generator (Python package-style, CLI & refactor)
  - Orchestration: `tikyou_video_generator/generator.py` and refactor `generator_refactored.py`
  - Flow: YouTube download -> pillarbox crop -> scene detection -> clip splitting -> compilations -> optional TTS intro
  - Outputs under `final_videos/`, `temp_vertical/` with relative paths to its own repo root.
  - Requires ffmpeg, yt-dlp, opencv; works best with GPU.

### Integration Strategy
- Backend: New FastAPI app under `cat-video-creator/backend/`.
  - Expose endpoints:
    - `POST /api/moneyprinter/generate` – mirrors MoneyPrinter JSON shape; runs MoneyPrinter flow.
    - `POST /api/brainrot/generate` – accepts `youtubeUrl`, `numCompilations`, `minDuration`, `maxDuration`, `maxReuse`.
    - `GET /api/health` – status & environment check.
    - `GET /api/jobs/{id}` – optional progress polling.
  - Isolation: Change working directory per workflow so original modules’ relative paths remain valid:
    - MoneyPrinter: chdir to `MoneyPrinter/Backend/` during execution, then revert.
    - Brainrot: chdir to `brainrot-generator/` during execution, then revert.
  - Import original modules without modifying them (sys.path injection during runtime).
  - Provide minimal in-memory job/progress store for UX.

- Frontend: New Vite React (TypeScript) app under `cat-video-creator/frontend/` using Shadcn UI.
  - Pages/sections:
    - Workflow selector (tabs/cards): MoneyPrinter vs Brainrot.
    - MoneyPrinter form: subject, aiModel, paragraphNumber, threads, subtitlesPosition, text color, useMusic, zipUrl, voice, customPrompt, useGPU, automateYouTubeUpload (optional).
    - Brainrot form: youtubeUrl, numCompilations, minDuration, maxDuration, maxReuse.
  - UX: start job, show progress (polling `/api/jobs/{id}`), results panel with output paths.
  - Error handling with toasts and clear validation.

### Dependencies (Backend)
- Choose unified modern stack compatible with both:
  - FastAPI, uvicorn
  - moviepy==2.x, imageio-ffmpeg
  - requests, python-dotenv, termcolor
  - google-generativeai and google-genai (both), openai
  - scenedetect, opencv-python, torch (optional GPU), yt-dlp
  - soundfile, rich, tqdm, psutil
- Keep originals’ env requirements; document `.env` placement for MoneyPrinter.

### Project Structure
```
cat-video-creator/
  backend/
    app.py
    requirements.txt
    README.md
  frontend/
    (Vite React TS + Shadcn UI project)
  README.md
```

### Execution Steps
1) Scaffold backend (FastAPI), implement both endpoints, health, and simple job store.
2) Create backend requirements and README with env and run instructions.
3) Scaffold frontend (Vite + TS), configure Tailwind + Shadcn UI, add core components.
4) Build workflow forms and API integration; implement progress polling view.
5) Wire end-to-end locally: run backend on 8080, frontend on 5173.
6) Document installation and usage.

### Risk & Mitigations
- Version conflicts (moviepy 1.x vs 2.x): use moviepy 2.x in unified app and run flows in original directories to minimize breakage.
- Relative paths in originals: isolate via per-workflow chdir and return output paths to the unified app.
- Progress integration: surface high-level step progress in wrappers; avoid deep patching originals.

### Deliverables
- New `cat-video-creator/` folder with backend + frontend, plus documentation.


