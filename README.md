# VideoHelper (AI Video Creator)

Unified app to generate short-form videos through two workflows from a single UI:
- Create videos purrely with AI (AI script + stock footage + subtitles + optional background music)
- Create videos from compilations (TikTok-style compilations from a YouTube URL)

The project contains a FastAPI backend and a React (Vite + TypeScript + Tailwind + shadcn/ui) frontend. Vendored copies of the original backends live under the backend folder so you can run everything in one place.

## Repository layout
```
cat-video-creator/
  backend/        FastAPI server that orchestrates both workflows
    vendors/      Vendored copies of MoneyPrinter and Brainrot backends (+ fonts)
  frontend/       Vite + React app (shadcn/ui, Tailwind)
  output/         Unified output directory for generated media and jobs.json
requirements.txt  Python dependencies for the backend
```

## Prerequisites
- Windows, macOS, or Linux
- Python 3.10+
- Node.js 18+ and npm
- FFmpeg installed and available on PATH (recommended)
  - MoviePy can auto-download an FFmpeg binary via imageio, but a system install is more reliable
- Optional (GPU encoding): NVIDIA GPU + NVENC-enabled FFmpeg for `h264_nvenc`

## Quick start
### 1) Backend
```powershell
cd cat-video-creator/backend
python -m venv .venv
. .venv/Scripts/Activate.ps1   # PowerShell on Windows
# source .venv/bin/activate    # macOS/Linux
pip install -r ../../requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

### 2) Frontend
```powershell
cd cat-video-creator/frontend
npm install
npm run dev
```
- Frontend dev server: http://localhost:5173
- Backend server: http://localhost:8080

## Environment variables
MoneyPrinter flow requires:
- `PEXELS_API_KEY`: for stock footage search and downloads
- One of: `GOOGLE_API_KEY` or `GEMINI_API_KEY`: for script generation models

Where to set them:
- In your shell before starting the backend, or
- Create a `.env` file adjacent to `cat-video-creator/backend/vendors/moneyprinter/` and export the vars there (the vendored code reads environment variables at runtime)

Optional:
- `VIDEOHELPER_OUTPUT_DIR`: override unified output dir (defaults to `cat-video-creator/output`)

## Using the app
1) Start the backend and frontend as above.
2) Open the frontend (http://localhost:5173).
3) Choose a workflow tab, fill in the form, and submit.
4) Watch live progress and logs. When complete, a download link or output directory will appear.

Generated outputs
- MoneyPrinter: final MP4 and subtitles are placed under `cat-video-creator/output/`
- Brainrot: compilations directory is placed under the unified output directory as reported by the job result

## API (for advanced use)
The backend exposes a simple job API with polling and WebSocket updates.

- GET `/api/health` — quick status and vendor presence
- GET `/api/models` — available Gemini model IDs
- GET `/api/voices` — available Kokoro voices for TTS
- POST `/api/moneyprinter/generate` — start MoneyPrinter flow
- POST `/api/brainrot/generate` — start Brainrot flow
- GET `/api/jobs/{jobId}` — job status (queued | running | done | error | cancelled)
- POST `/api/jobs/{jobId}/cancel` — request cancellation
- WebSocket `/ws/jobs/{jobId}` — live job updates
- GET `/api/download?path=...` — download a generated file (only within approved output roots)
- GET `/api/list-videos?dir=...` — list MP4s in an output directory

Example (PowerShell, MoneyPrinter):
```powershell
$body = @{ 
  videoSubject = "Cute cats doing funny things"
  aiModel = "gemini-2.0-flash"
  paragraphNumber = 1
  threads = 2
  subtitlesPosition = "center,bottom"
  color = "#FFFF00"
  useMusic = $true
  zipUrl = $null
  automateYoutubeUpload = $false
  useGPU = $false
  voice = "af_bella"
  customPrompt = $null
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/moneyprinter/generate -ContentType 'application/json' -Body $body
```

## GPU and performance notes
- Set `useGPU=true` in the MoneyPrinter form to attempt NVENC (`h264_nvenc`). If your FFmpeg build lacks NVENC, set `useGPU=false`.
- Use the `threads` field to tune CPU thread usage for rendering.

## Troubleshooting
- Fonts/TextClip/Pillow errors: MoneyPrinter’s subtitle rendering requires a valid font. A vendored font exists under `backend/vendors/fonts/`. The backend logs will hint if there’s a font configuration issue.
- FFmpeg not found: ensure FFmpeg is on PATH, or let imageio download it on first MoviePy use. A system install is recommended for GPU encoding.
- Missing environment variables: jobs will fail early with a clear message if `PEXELS_API_KEY` or a Google/Gemini key is missing.
- Port conflicts: change frontend port (Vite) in `cat-video-creator/frontend/vite.config.ts`, backend port via `--port` flag.

## Development
- Backend code: `cat-video-creator/backend/app.py`
- Frontend code: `cat-video-creator/frontend/src/`
- Vendored backends live under `cat-video-creator/backend/vendors/` and are imported without modification at runtime.

## License
This repository vendors third-party code under `cat-video-creator/backend/vendors/`. Check original licenses before redistribution. No root license is currently declared for this repo.
