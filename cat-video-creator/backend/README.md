AI Video Creator – Backend

Python FastAPI backend that unifies the MoneyPrinter and Brainrot workflows (vendored under `backend/vendors`).

Prerequisites
- Python 3.10+
- FFmpeg installed and on PATH

Environment
- Canonical env file: create `.env` at the repository root. The backend auto-loads it.
- Optional overrides: `cat-video-creator/backend/.env` and `cat-video-creator/backend/vendors/moneyprinter/.env` are also loaded if present.
- Required keys: `PEXELS_API_KEY` and either `GOOGLE_API_KEY` or `GEMINI_API_KEY`.

Install
```bash
cd cat-video-creator/backend
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r ../../requirements.txt
```

Run
```bash
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

API
- GET `/api/health`
- POST `/api/moneyprinter/generate`
- POST `/api/brainrot/generate`
- GET `/api/jobs/{id}`

See the root `README.md` for full documentation.
