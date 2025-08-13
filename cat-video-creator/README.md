AI Video Creator

Unified app combining two existing backends into a single UI and API.
Create videos purrely with AI, or create videos from compilations.

Structure
```
cat-video-creator/
  backend/  # FastAPI
  frontend/ # React + Vite + Shadcn
  (vendored backends live inside backend/vendors)
```

Quickstart
1) Backend
```bash
cd cat-video-creator/backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

2) Frontend
```bash
cd cat-video-creator/frontend
npm install
npm run dev
```

Usage
- Open the frontend dev URL (e.g., `http://localhost:5173/`), pick a workflow, submit a job, view progress and results.

Notes
- All code is now inside `cat-video-creator/`. The original two are vendored under `backend/vendors/`.
- Canonical env file is the repo root `.env` (at project root). The backend will auto-load it.
- Optional overrides: `.env` in `cat-video-creator/backend/` and `cat-video-creator/backend/vendors/moneyprinter/` will also be loaded if present.
- Required keys include `PEXELS_API_KEY` and either `GOOGLE_API_KEY` or `GEMINI_API_KEY`. See the root `README.md` for the full list.

