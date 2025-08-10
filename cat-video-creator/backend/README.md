AI Video Creator – Backend

Python FastAPI backend that unifies both existing workflows without modifying original projects.

Prerequisites
- Python 3.10+
- FFmpeg installed and on PATH
- Ensure original projects exist at sibling paths:
  - `MoneyPrinter/` (contains `Backend/`)
  - `brainrot-generator/`

For MoneyPrinter flow, create `MoneyPrinter/.env` with vars per `MoneyPrinter/EnvironmentVariables.md`.

Install
```bash
cd cat-video-creator/backend
python -m venv .venv
. .venv/Scripts/activate  # on Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
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

Returned paths are relative to the original project directories.

